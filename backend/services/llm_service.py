import json
import hashlib
import time
from typing import Optional

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    retry_if_not_result,
)

from config import settings
from errors import BizError, ERR
from logging_config import get_logger

logger = get_logger("foodtime.llm")


# 断路器：某模型连续失败 N 次后熔断 M 秒
class _CircuitBreaker:
    def __init__(self, fail_threshold: int = 5, open_seconds: int = 60):
        self.fail_threshold = fail_threshold
        self.open_seconds = open_seconds
        self._fails: dict[str, int] = {}
        self._open_until: dict[str, float] = {}

    def is_open(self, name: str) -> bool:
        until = self._open_until.get(name, 0)
        if until and time.time() < until:
            return True
        if until:
            # 熔断时间到，自动半开
            self._open_until.pop(name, None)
            self._fails[name] = 0
        return False

    def record_fail(self, name: str) -> None:
        self._fails[name] = self._fails.get(name, 0) + 1
        if self._fails[name] >= self.fail_threshold:
            self._open_until[name] = time.time() + self.open_seconds
            logger.warning("Circuit breaker OPEN for %s (fail %s)", name, self._fails[name])

    def record_success(self, name: str) -> None:
        self._fails[name] = 0
        self._open_until.pop(name, None)


_circuit = _CircuitBreaker()


class LLMService:
    def __init__(self):
        self.deepseek_key = settings.DEEPSEEK_API_KEY
        self.deepseek_url = settings.DEEPSEEK_BASE_URL
        self.deepseek_model = settings.DEEPSEEK_MODEL
        self.dashscope_key = settings.DASHSCOPE_API_KEY
        self.qwen_model = settings.QWEN_MODEL
        # 共享 httpx 客户端（连接池）
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0))

    async def chat_completion(
        self,
        messages: list[dict],
        model: str = "deepseek",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        response_format_json: bool = False,
    ) -> dict:
        # 优先用配置了 Key 的模型；熔断时自动切换
        providers = []
        if self.deepseek_key:
            providers.append(("deepseek", self._call_deepseek))
        if self.dashscope_key:
            providers.append(("qwen", self._call_qwen))
        # 过滤掉被熔断的
        available = [(n, fn) for n, fn in providers if not _circuit.is_open(n)]
        last_err: Optional[Exception] = None

        for name, fn in available:
            try:
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(3),
                    wait=wait_exponential(multiplier=1, min=1, max=8),
                    retry=retry_if_exception_type((
                        httpx.TransportError, httpx.TimeoutException,
                        httpx.HTTPStatusError,
                    )),
                    reraise=True,
                ):
                    with attempt:
                        t0 = time.perf_counter()
                        result = await fn(messages, temperature, max_tokens, response_format_json)
                        latency_ms = int((time.perf_counter() - t0) * 1000)
                        _circuit.record_success(name)
                        logger.info(
                            "LLM %s ok in %sms, tokens=%s",
                            name, latency_ms, result.get("total_tokens", 0),
                            llm_model=result.get("model", name),
                            tokens=result.get("total_tokens", 0),
                            latency_ms=latency_ms,
                        )
                        return result
            except Exception as exc:
                _circuit.record_fail(name)
                logger.warning(
                    "LLM %s failed (attempt %s): %s",
                    name, getattr(attempt, "attempt_number", "?"), exc,
                    llm_model=name,
                )
                last_err = exc
                continue  # 切换下一个 provider

        # 所有 provider 都失败 -> 降级 mock
        logger.error("All LLM providers failed. last_err=%s. Using fallback.", last_err)
        return {
            "content": self._mock_response(messages, response_format_json),
            "model": "mock_fallback",
            "total_tokens": 0,
            "degraded": True,
        }

    async def _call_deepseek(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        response_format_json: bool,
    ) -> dict:
        if _circuit.is_open("deepseek"):
            raise BizError(*ERR["LLM_UNAVAILABLE"])
        headers = {
            "Authorization": f"Bearer {self.deepseek_key}",
            "Content-Type": "application/json",
        }
        payload: dict = {
            "model": self.deepseek_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format_json:
            payload["response_format"] = {"type": "json_object"}

        resp = await self._client.post(
            f"{self.deepseek_url}/v1/chat/completions",
            headers=headers,
            json=payload,
        )
        # 429 限流 / 5xx 服务端错 → 触发重试
        if resp.status_code in (429, 500, 502, 503, 504):
            raise httpx.HTTPStatusError(
                "Upstream rate limit or error",
                request=resp.request, response=resp,
            )
        resp.raise_for_status()
        data = resp.json()

        return {
            "content": data["choices"][0]["message"]["content"],
            "model": self.deepseek_model,
            "total_tokens": data.get("usage", {}).get("total_tokens", 0),
        }

    async def _call_qwen(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        response_format_json: bool,
    ) -> dict:
        if _circuit.is_open("qwen"):
            raise BizError(*ERR["LLM_UNAVAILABLE"])
        headers = {
            "Authorization": f"Bearer {self.dashscope_key}",
            "Content-Type": "application/json",
        }
        payload: dict = {
            "model": self.qwen_model,
            "input": {"messages": messages},
            "parameters": {
                "temperature": temperature,
                "max_tokens": max_tokens,
                "result_format": "json" if response_format_json else "text",
            },
        }

        resp = await self._client.post(
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
            headers=headers,
            json=payload,
        )
        if resp.status_code in (429, 500, 502, 503, 504):
            raise httpx.HTTPStatusError(
                "Upstream rate limit or error",
                request=resp.request, response=resp,
            )
        resp.raise_for_status()
        data = resp.json()

        return {
            "content": data["output"]["text"],
            "model": self.qwen_model,
            "total_tokens": data.get("usage", {}).get("total_tokens", 0),
        }

    def _mock_response(self, messages: list[dict], json_mode: bool) -> str:
        user_msg = ""
        for m in reversed(messages):
            if m["role"] == "user":
                user_msg = m["content"]
                break

        if json_mode:
            return json.dumps(
                {
                    "recipes": [
                        {
                            "name": "番茄炒蛋",
                            "difficulty": 1,
                            "cooking_time": "8min",
                            "estimated_cost": "¥6",
                            "reason": "冰箱现成食材，最快最省",
                            "steps": ["西红柿切块", "鸡蛋打散炒熟", "下西红柿翻炒", "加盐糖调味出锅"],
                            "matched_ingredients": ["西红柿", "鸡蛋"],
                            "missing_ingredients": ["葱花"],
                        },
                        {
                            "name": "青菜肉末粥",
                            "difficulty": 2,
                            "cooking_time": "25min",
                            "estimated_cost": "¥8",
                            "reason": "热乎暖胃，适合疲惫的晚上",
                            "steps": ["大米煮粥", "肉末炒香", "青菜切碎", "粥好后拌入肉末青菜"],
                            "matched_ingredients": ["大米", "猪肉馅", "青菜"],
                            "missing_ingredients": ["姜丝"],
                        },
                        {
                            "name": "酱油炒饭",
                            "difficulty": 1,
                            "cooking_time": "10min",
                            "estimated_cost": "¥5",
                            "reason": "最快主食，剩饭的最佳归宿",
                            "steps": ["剩米饭打散", "热油下饭翻炒", "加酱油调色", "撒葱花出锅"],
                            "matched_ingredients": ["大米", "酱油"],
                            "missing_ingredients": ["葱花"],
                        },
                    ]
                },
                ensure_ascii=False,
            )
        return f"[MOCK] 基于输入: {user_msg[:100]}... (未配置API Key, 返回模拟数据)"

    @staticmethod
    def hash_prompt(prompt: str) -> str:
        return hashlib.md5(prompt.encode()).hexdigest()[:16]

    async def generate_recipe_prompt(
        self,
        ingredients: list[str],
        taste_weights: dict[str, float],
        budget_level: str,
        cooking_skill: str,
        disliked: list[str],
        exclude_recipes: list[str],
    ) -> str:
        top_tastes = sorted(taste_weights.items(), key=lambda x: x[1], reverse=True)[:3]
        taste_str = "、".join([f"{k}({v:.2f})" for k, v in top_tastes])
        exclude_str = "、".join(exclude_recipes) if exclude_recipes else "无"

        return (
            f"你是一个独居青年的做饭助手。根据冰箱库存和偏好，推荐3道菜。\n\n"
            f"【库存食材】{', '.join(ingredients)}\n"
            f"【口味权重】{taste_str}\n"
            f"【预算级别】{budget_level}\n"
            f"【厨艺水平】{cooking_skill}\n"
            f"【忌口食材】{', '.join(disliked) if disliked else '无'}\n"
            f"【排除菜品】{exclude_str}（换一换，不要推荐这些）\n\n"
            f"请返回JSON，格式如下：\n"
            f'{{"recipes": [{{"name":"菜名","difficulty":1-3,"cooking_time":"如8min",'
            f'"estimated_cost":"如¥6","reason":"推荐理由",'
            f'"steps":["步骤1","步骤2"],"matched_ingredients":["已匹配食材"],'
            f'"missing_ingredients":["缺少食材"]}}]}}'
        )


llm_service = LLMService()
