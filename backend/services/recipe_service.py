import json
import time
from sqlalchemy.orm import Session

from models import RecipeCache, UserPreference
from schemas import RecipeRequest, RecipeItem, RecipeResponse
from services.llm_service import llm_service


class RecipeService:

    async def recommend(self, req: RecipeRequest, db: Session) -> RecipeResponse:
        prompt = await llm_service.generate_recipe_prompt(
            ingredients=req.ingredient_names,
            taste_weights=req.taste_weights,
            budget_level=req.budget_level,
            cooking_skill=req.cooking_skill,
            disliked=req.disliked_ingredients,
            exclude_recipes=req.exclude_recipes,
        )
        # P0-4 修复(缓存污染): 把 exclude_recipes 一并纳入 hash，否则"换一换"写入的 cache 会污染不带 exclude 的后续请求
        prompt_hash_src = prompt + "::exclude=" + ",".join(sorted(req.exclude_recipes or []))
        prompt_hash = llm_service.hash_prompt(prompt_hash_src)

        # 读缓存：仅当没有 exclude_recipes 时命中缓存（与写入端一致）
        cached = []
        if not req.exclude_recipes:
            cached = (
                db.query(RecipeCache)
                .filter(
                    RecipeCache.user_id == req.user_id,
                    RecipeCache.prompt_hash == prompt_hash,
                )
                .order_by(RecipeCache.created_at.desc())
                .limit(3)
                .all()
            )
            # P0-4 修复(缓存 TTL): 仅缓存 24 小时内的记录，避免长期运行下命中过期推荐
            cutoff = time.time() - 86400
            cached = [
                c for c in cached
                if c.created_at and c.created_at.timestamp() > cutoff
            ][:3]

        if cached:
            return RecipeResponse(
                recipes=[self._cache_to_item(c) for c in cached],
                model=cached[0].llm_model,
                prompt_hash=prompt_hash,
            )

        messages = [
            {"role": "system", "content": "你是一个独居青年的做饭助手，根据冰箱库存和偏好推荐菜谱。必须返回JSON格式。"},
            {"role": "user", "content": prompt},
        ]
        result = await llm_service.chat_completion(
            messages, temperature=0.7, response_format_json=True
        )

        try:
            data = json.loads(result["content"])
            recipe_list = data.get("recipes", data) if isinstance(data, dict) else data
            if not isinstance(recipe_list, list):
                raise TypeError("recipes not list")
        except (json.JSONDecodeError, TypeError, ValueError):
            recipe_list = self._fallback_recipes(req.ingredient_names)

        items: list[RecipeItem] = []
        for r in recipe_list[:3]:
            item = RecipeItem(
                id="",  # 先占位，_save_cache 里 flush 后再填
                name=r.get("name", "未知菜名"),
                difficulty=max(1, min(3, int(r.get("difficulty", 1) or 1))),
                cooking_time=str(r.get("cooking_time", "") or ""),
                estimated_cost=str(r.get("estimated_cost", "") or ""),
                reason=str(r.get("reason", "") or ""),
                steps=list(r.get("steps", []) or []),
                matched_ingredients=list(r.get("matched_ingredients", []) or []),
                missing_ingredients=list(r.get("missing_ingredients", []) or []),
            )
            cache_id = self._save_cache(req.user_id, item, prompt_hash, result["model"], db)
            item.id = cache_id or item.id
            items.append(item)

        db.commit()
        return RecipeResponse(
            recipes=items, model=result["model"], prompt_hash=prompt_hash
        )

    def _save_cache(
        self,
        user_id: str,
        item: RecipeItem,
        prompt_hash: str,
        model: str,
        db: Session,
    ) -> str:
        # 先查是否已存在相同 prompt_hash 的缓存，存在则直接复用（唯一键约束要求）
        existing = (
            db.query(RecipeCache)
            .filter(RecipeCache.prompt_hash == prompt_hash)
            .first()
        )
        if existing:
            return existing.id or ""
        cache = RecipeCache(
            user_id=user_id,
            recipe_name=item.name,
            difficulty=item.difficulty,
            cooking_time=item.cooking_time,
            estimated_cost=item.estimated_cost,
            reason=item.reason,
            steps=item.steps,
            matched_ingredients=item.matched_ingredients,
            missing_ingredients=item.missing_ingredients,
            llm_model=model,
            prompt_hash=prompt_hash,
        )
        db.add(cache)
        db.flush()
        return cache.id or ""

    def _cache_to_item(self, cache: RecipeCache) -> RecipeItem:
        return RecipeItem(
            id=cache.id or "",
            name=cache.recipe_name,
            difficulty=cache.difficulty,
            cooking_time=cache.cooking_time,
            estimated_cost=cache.estimated_cost,
            reason=cache.reason,
            steps=cache.steps or [],
            matched_ingredients=cache.matched_ingredients or [],
            missing_ingredients=cache.missing_ingredients or [],
        )

    def _fallback_recipes(self, ingredients: list[str]) -> list[dict]:
        return [
            {
                "name": "番茄炒蛋",
                "difficulty": 1,
                "cooking_time": "8min",
                "estimated_cost": "¥6",
                "reason": "冰箱现成食材，最快最省",
                "steps": ["西红柿切块", "鸡蛋打散炒熟", "下西红柿翻炒", "加盐糖调味出锅"],
                "matched_ingredients": [i for i in ingredients if i in ("西红柿", "鸡蛋")],
                "missing_ingredients": ["葱花"] if "葱花" not in ingredients else [],
            },
            {
                "name": "青菜肉末粥",
                "difficulty": 2,
                "cooking_time": "25min",
                "estimated_cost": "¥8",
                "reason": "热乎暖胃，适合疲惫的晚上",
                "steps": ["大米煮粥", "肉末炒香", "青菜切碎", "粥好后拌入肉末青菜"],
                "matched_ingredients": [i for i in ingredients if i in ("大米", "猪肉馅", "青菜")],
                "missing_ingredients": ["姜丝"] if "姜丝" not in ingredients else [],
            },
            {
                "name": "酱油炒饭",
                "difficulty": 1,
                "cooking_time": "10min",
                "estimated_cost": "¥5",
                "reason": "最快主食，剩饭的最佳归宿",
                "steps": ["剩米饭打散", "热油下饭翻炒", "加酱油调色", "撒葱花出锅"],
                "matched_ingredients": [i for i in ingredients if i in ("大米", "酱油")],
                "missing_ingredients": ["葱花"] if "葱花" not in ingredients else [],
            },
        ]


recipe_service = RecipeService()
