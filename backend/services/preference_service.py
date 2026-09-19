from sqlalchemy.orm import Session
from sqlalchemy import func

from models import PreferenceWeight, CookRecord, TakeoutRecord
from schemas import PreferenceWeight as PreferenceWeightSchema, FeedbackRequest


DIMENSIONS = ["辣", "甜", "酸", "咸", "清淡", "油腻", "清爽", "预算", "快手"]
DEFAULT_WEIGHT = 0.500
ALPHA_OLD = 0.7
ALPHA_FEEDBACK = 0.3

FEEDBACK_SCORES = {"good": 1.0, "ok": 0.5, "bad": 0.0}


class PreferenceService:

    def init_weights(self, user_id: str, taste_pref: str, db: Session):
        for dim in DIMENSIONS:
            existing = (
                db.query(PreferenceWeight)
                .filter(
                    PreferenceWeight.user_id == user_id,
                    PreferenceWeight.dimension == dim,
                )
                .first()
            )
            if existing:
                continue
            initial = DEFAULT_WEIGHT
            if dim == taste_pref:
                initial = 0.800
            pw = PreferenceWeight(
                user_id=user_id,
                dimension=dim,
                weight=initial,
                feedback_count=0,
                last_feedback="",
            )
            db.add(pw)
        db.commit()

    def apply_feedback(
        self, req: FeedbackRequest, db: Session
    ) -> list[PreferenceWeightSchema]:
        feedback_score = FEEDBACK_SCORES.get(
            "good" if req.rating == 3 else "ok" if req.rating == 2 else "bad", 0.5
        )
        feedback_label = (
            "good" if req.rating == 3 else "ok" if req.rating == 2 else "bad"
        )

        if req.type == "cook":
            dims = self._infer_cook_dimensions(req.dish_name, db, req.user_id)
        else:
            dims = ["预算", "辣"]

        for dim in dims:
            pw = (
                db.query(PreferenceWeight)
                .filter(
                    PreferenceWeight.user_id == req.user_id,
                    PreferenceWeight.dimension == dim,
                )
                .first()
            )
            if not pw:
                pw = PreferenceWeight(
                    user_id=req.user_id,
                    dimension=dim,
                    weight=DEFAULT_WEIGHT,
                )
                db.add(pw)
                db.flush()

            old_w = float(pw.weight)
            new_w = old_w * ALPHA_OLD + feedback_score * ALPHA_FEEDBACK
            pw.weight = round(new_w, 3)
            pw.feedback_count += 1
            pw.last_feedback = feedback_label

        db.commit()
        return self.get_weights(req.user_id, db)

    def get_weights(
        self, user_id: str, db: Session
    ) -> list[PreferenceWeightSchema]:
        weights = (
            db.query(PreferenceWeight)
            .filter(PreferenceWeight.user_id == user_id)
            .order_by(PreferenceWeight.weight.desc())
            .all()
        )
        if not weights:
            self.init_weights(user_id, "", db)
            weights = (
                db.query(PreferenceWeight)
                .filter(PreferenceWeight.user_id == user_id)
                .order_by(PreferenceWeight.weight.desc())
                .all()
            )
        return [
            PreferenceWeightSchema(
                dimension=w.dimension,
                weight=float(w.weight),
                feedback_count=w.feedback_count,
                last_feedback=w.last_feedback,
            )
            for w in weights
        ]

    def get_weights_dict(self, user_id: str, db: Session) -> dict[str, float]:
        weights = self.get_weights(user_id, db)
        return {w.dimension: w.weight for w in weights}

    def _infer_cook_dimensions(
        self, dish_name: str, db: Session, user_id: str
    ) -> list[str]:
        dims = []
        spicy_keywords = ["辣", "麻", "香辣", "麻辣", "酸辣"]
        sweet_keywords = ["甜", "糖醋", "可乐"]
        sour_keywords = ["酸", "醋"]
        light_keywords = ["清", "蒸", "白灼", "粥", "汤"]

        for kw in spicy_keywords:
            if kw in dish_name:
                dims.append("辣")
                break
        for kw in sweet_keywords:
            if kw in dish_name:
                dims.append("甜")
                break
        for kw in sour_keywords:
            if kw in dish_name:
                dims.append("酸")
                break
        for kw in light_keywords:
            if kw in dish_name:
                dims.append("清淡")
                break

        if not dims:
            dims = ["预算", "快手"]

        cook_time = (
            db.query(func.min(CookRecord.cooking_time))
            .filter(CookRecord.user_id == user_id, CookRecord.dish_name == dish_name)
            .scalar()
        )
        if cook_time and cook_time <= 15:
            dims.append("快手")

        return list(set(dims))


preference_service = PreferenceService()
