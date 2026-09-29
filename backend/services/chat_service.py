import json
from datetime import datetime, timedelta
from urllib.parse import quote as url_quote

from sqlalchemy.orm import Session

from errors import BizError, ERR
from logging_config import get_logger
from models import ChatSession, ChatTurn
from quota_limiter import consume_quota, refund_quota, QuotaKind
from schemas import (
    ChatSessionCreate, ChatTurnRequest, ChatTurnResponse, ChatFinalRecommend,
)
from services.llm_service import llm_service
from services.preference_service import preference_service

logger = get_logger("foodtime.chat")

# P1-1 修复(点单会话可被无限创建): 同一用户最多同时持有 MAX_ACTIVE 个未完成的
# 对话。之前 /api/chat/session 既不扣配额、也不限数量，刷接口就能无上限灌
# chat_sessions 行；但加硬上限又会把"中途关掉页面"的用户永久锁死，
# 所以同时引入 STALE_MINUTES 自愈：超过该时长仍未继续的 active 会话
# 先自动置为 expired，再统计数量。
MAX_ACTIVE_CHAT_SESSIONS = 3
STALE_CHAT_SESSION_MINUTES = 30

ROUND_CONFIG = [
    {
        "dim": "口味倾向",
        "field": "taste_choice",
        "q": "今天想吃什么口味？",
        "opts": ["辣", "酸", "甜", "咸", "清淡", "油腻", "清爽", "无所谓"],
    },
    {
        "dim": "主食类型",
        "field": "staple_choice",
        "q": "想吃米饭还是面食？",
        "opts": ["米饭", "面条", "饺子", "汉堡", "无所谓"],
    },
    {
        "dim": "肉类偏好",
        "field": "meat_choice",
        "q": "想吃肉还是素？",
        "opts": ["鸡肉", "猪肉", "牛肉", "鱼肉", "素食"],
    },
    {
        "dim": "烹饪形式",
        "field": "form_choice",
        "q": "想吃什么形式的？",
        "opts": ["炒菜", "汤类", "烧烤", "火锅", "快餐"],
    },
    {
        "dim": "预算范围",
        "field": "budget_choice",
        "q": "今天的预算？",
        "opts": ["15以内", "15-30", "30-50", "50以上"],
    },
]


class ChatService:

    def create_session(
        self,
        req: ChatSessionCreate,
        db: Session,
        max_active: int = MAX_ACTIVE_CHAT_SESSIONS,
        stale_minutes: int = STALE_CHAT_SESSION_MINUTES,
    ) -> ChatTurnResponse:
        now = datetime.now()
        stale_before = now - timedelta(minutes=stale_minutes)
        expired_cnt = (
            db.query(ChatSession)
            .filter(
                ChatSession.user_id == req.user_id,
                ChatSession.status == "active",
                ChatSession.created_at < stale_before,
            )
            .update(
                {"status": "expired", "completed_at": now},
                synchronize_session=False,
            )
        )
        # 自愈先落库：即便下面因为超限被拒绝，用户也不该继续背着僵尸会话。
        db.commit()
        if expired_cnt:
            logger.info(
                "Auto-expired %s stale chat sessions user=%s",
                expired_cnt, req.user_id, user_id=req.user_id,
            )

        active_cnt = (
            db.query(ChatSession)
            .filter(
                ChatSession.user_id == req.user_id,
                ChatSession.status == "active",
            )
            .count()
        )
        if active_cnt >= max_active:
            raise BizError(*ERR["CHAT_TOO_MANY_SESSIONS"])

        session = ChatSession(
            user_id=req.user_id,
            current_round=1,
            total_rounds=5,
            status="active",
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        config = ROUND_CONFIG[0]
        return ChatTurnResponse(
            session_id=session.id,
            current_round=1,
            total_rounds=5,
            dimension=config["dim"],
            question=config["q"],
            options=config["opts"],
            status="active",
        )

    async def process_turn(
        self, req: ChatTurnRequest, db: Session
    ) -> ChatTurnResponse | ChatFinalRecommend:
        session = (
            db.query(ChatSession)
            .filter(ChatSession.id == req.session_id)
            .first()
        )
        if not session:
            return ChatFinalRecommend(
                session_id=req.session_id or "",
                final_recommend="",
                recommend_reason="会话不存在",
            )
        if session.status != "active":
            # 已完成会话被重复进入（刷新重试/误触）：回放已生成的结果，
            # 否则前端会拿到空推荐，把上一次的结论覆盖成空白。
            if session.final_recommend:
                return self._build_final_response(session)
            return ChatFinalRecommend(
                session_id=session.id,
                final_recommend="",
                recommend_reason="会话已结束，暂无推荐结果",
            )

        round_idx = session.current_round - 1
        config = ROUND_CONFIG[round_idx]
        setattr(session, config["field"], req.answer)

        ai_msg = self._build_ai_message(config, req.answer)
        db.add(ChatTurn(
            session_id=session.id,
            turn=session.current_round,
            role="user",
            content=req.answer,
        ))
        db.add(ChatTurn(
            session_id=session.id,
            turn=session.current_round,
            role="ai",
            content=config["q"],
            ai_guess=req.answer,
            ai_confidence=0.65,
        ))

        session.current_round += 1

        if session.current_round > 5:
            session.status = "completed"
            db.commit()
            return await self._generate_final_recommend(session, db)

        next_config = ROUND_CONFIG[session.current_round - 1]
        db.commit()
        return ChatTurnResponse(
            session_id=session.id,
            current_round=session.current_round,
            total_rounds=5,
            dimension=next_config["dim"],
            question=next_config["q"],
            options=next_config["opts"],
            status="active",
        )

    async def _generate_final_recommend(
        self, session: ChatSession, db: Session
    ) -> ChatFinalRecommend:
        prefs = preference_service.get_weights_dict(session.user_id, db)
        top_prefs = sorted(prefs.items(), key=lambda x: x[1], reverse=True)[:3]
        taste_str = "、".join([f"{k}({v:.2f})" for k, v in top_prefs])

        prompt = (
            f"你是一个独居青年的外卖推荐助手。根据以下5轮对话收集的偏好，推荐一份外卖。\n\n"
            f"口味倾向: {session.taste_choice}\n"
            f"主食类型: {session.staple_choice}\n"
            f"肉类偏好: {session.meat_choice}\n"
            f"烹饪形式: {session.form_choice}\n"
            f"预算范围: {session.budget_choice}\n"
            f"历史偏好权重: {taste_str}\n\n"
            f"请返回JSON: {{\"recommend\":\"菜名\",\"reason\":\"推荐理由(50字内)\","
            f"\"alternatives\":[\"备选1\",\"备选2\"]}}"
        )
        messages = [
            {"role": "system", "content": "你是外卖推荐助手，返回JSON格式。"},
            {"role": "user", "content": prompt},
        ]
        # P1-1 修复(配额扣减时机): 原实现是"LLM 返回之后"才 consume，
        # 于是配额已耗尽的用户每次仍会真打一次上游（花钱 + 等 30s 超时），
        # 直到 consume 抛错才拒绝 —— 配额拦截完全滞后。
        # 现在改为进入 LLM 前预扣；只有 chat_completion 彻底抛异常（它内部
        # 已含重试与降级 mock，抛出来就是真失败了）才把这一次归还。
        await consume_quota(session.user_id, QuotaKind.CHAT)
        try:
            result = await llm_service.chat_completion(
                messages, temperature=0.7, response_format_json=True
            )
        except Exception:
            await refund_quota(session.user_id, QuotaKind.CHAT)
            raise

        try:
            data = json.loads(result["content"])
            # 防御性校验：LLM/Mock 可能返回错结构（例如菜谱格式 recipes[]）
            if not isinstance(data, dict) or not data.get("recommend"):
                raise ValueError("missing recommend field")
        except (json.JSONDecodeError, TypeError, ValueError, KeyError):
            data = {
                "recommend": "川味牛肉面",
                "reason": "今日运势建议暖食，预算匹配且制作快",
                "alternatives": ["酸辣粉", "红烧牛肉饭"],
            }

        session.final_recommend = data.get("recommend", "")
        session.recommend_reason = data.get("reason", "")
        session.alternatives = data.get("alternatives", [])
        session.total_tokens = result.get("total_tokens", 0)
        db.commit()

        # 配额已在调用 LLM 之前预扣（见上方 P1-1 注释）。走到这里说明推荐结果
        # 已经落库，degraded/mock 兜底同样视为"成功给出结果"，不退款。
        return self._build_final_response(session)

    def _build_final_response(self, session: ChatSession) -> ChatFinalRecommend:
        """按已落库的推荐结果构造最终响应（供生成完成与重复进入两种场景复用）。"""
        keyword = session.final_recommend or "川味牛肉面"
        kw = url_quote(keyword)
        kw_with_tag = url_quote(keyword + " 外卖")
        # 注意：美团 H5 返回 403 禁止直接爬取，这里用搜索引擎聚合搜索绕开
        # 美团/饿了么 App Scheme 可唤起 App（若已安装），搜索引擎兜底 H5 搜索页
        delivery_urls = {
            "meituan": f"imeituan://www.meituan.com/search/{kw}",
            "bing": f"https://cn.bing.com/search?q={kw_with_tag}",
            "baidu": f"https://www.baidu.com/s?wd={kw_with_tag}",
        }
        # 兼容旧字段（前端目前读 meituan_url），用必应搜索作为默认值
        url = delivery_urls["bing"]

        return ChatFinalRecommend(
            session_id=session.id,
            final_recommend=session.final_recommend,
            recommend_reason=session.recommend_reason,
            alternatives=session.alternatives or [],
            meituan_url=url,
            delivery_urls=delivery_urls,
        )

    def _build_ai_message(self, config: dict, answer: str) -> str:
        return f"用户选择了: {answer} ({config['dim']})"


chat_service = ChatService()
