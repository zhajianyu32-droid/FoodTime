import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Float, Text, JSON, DateTime, Date,
    ForeignKey, Boolean, SmallInteger, DECIMAL, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship

from database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now()


class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True, default=_uuid)
    device_id = Column(String(64), nullable=True)
    username = Column(String(50), nullable=True, unique=True)        # 登录账号（可选）
    phone = Column(String(20), nullable=True, unique=True)           # 手机号（可选）
    password_hash = Column(String(255), nullable=True)               # 密码哈希（不存明文）
    nickname = Column(String(50), nullable=False, default="")
    avatar_url = Column(String(500), nullable=True)
    status = Column(String(10), nullable=False, default="active")    # active / banned / deleted
    created_at = Column(DateTime, nullable=False, default=_now)
    last_active_at = Column(DateTime, nullable=True)
    total_cook_count = Column(Integer, nullable=False, default=0)
    total_takeout_count = Column(Integer, nullable=False, default=0)
    streak_days = Column(Integer, nullable=False, default=0)
    # P0-6 修复：refresh token 黑名单机制（字段级）
    # 所有签发时间 < token_valid_since 的 refresh / access token 一律作废；
    # 改密 / 挂失 / 登出时把该字段推进到当前时间，即可实现一次性失效旧 token。
    token_valid_since = Column(Float, nullable=False, default=0.0)


class UserPreference(Base):
    __tablename__ = "user_preferences"
    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    zodiac = Column(String(10), nullable=False, default="")
    mbti = Column(String(4), nullable=False, default="")
    chinese_zodiac = Column(String(5), nullable=False, default="")
    taste_preference = Column(String(10), nullable=False, default="不挑")
    taste_weights = Column(JSON, nullable=False, default=dict)
    budget_level = Column(String(30), nullable=False, default="16~25")
    cooking_skill = Column(String(20), nullable=False, default="一般会做点")
    cookware = Column(JSON, nullable=False, default=list)
    disliked_ingredients = Column(JSON, nullable=False, default=list)
    cuisines = Column(JSON, nullable=False, default=list, comment="喜欢的菜系列表（多选，枚举+自定义）")
    birth_date = Column(Date, nullable=True, comment="出生日期（用于设置页回显，星座/属相由其推算）")
    custom_disliked = Column(JSON, nullable=True, comment="自定义忌口：{分类/子类: [食材,...]}")
    liked_dishes = Column(JSON, nullable=False, default=list)
    liked_takeout_categories = Column(JSON, nullable=False, default=list)
    disliked_takeout_categories = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)


class Ingredient(Base):
    __tablename__ = "ingredients"
    __table_args__ = (
        Index("ix_ingredients_user_id", "user_id"),
        Index("ix_ingredients_user_status", "user_id", "status"),
    )
    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(50), nullable=False)
    category = Column(String(10), nullable=False)
    quantity = Column(String(20), nullable=False, default="")
    shelf_days = Column(Integer, nullable=True, default=None)  # 保质期天数，null 则按 category 默认
    expiry_date = Column(Date, nullable=True)
    photo_data = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    source = Column(String(10), nullable=False, default="manual")
    status = Column(String(10), nullable=False, default="available")
    location = Column(String(10), nullable=False, default="pool")  # pool|freezer|fridge|cooking
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)


class CookRecord(Base):
    __tablename__ = "cook_records"
    __table_args__ = (
        Index("ix_cook_records_user_id", "user_id"),
        Index("ix_cook_records_user_created", "user_id", "created_at"),
    )
    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    dish_name = Column(String(100), nullable=False)
    photo_url = Column(Text, nullable=True)
    mood = Column(String(10), nullable=False, default="")
    rating = Column(SmallInteger, nullable=True)
    cooking_time = Column(SmallInteger, nullable=True)
    difficulty = Column(String(10), nullable=False, default="")
    estimated_cost = Column(DECIMAL(6, 2), nullable=True)
    note = Column(String(200), nullable=False, default="")
    tags = Column(JSON, nullable=False, default=list)
    ai_recommend_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)


class TakeoutRecord(Base):
    __tablename__ = "takeout_records"
    __table_args__ = (
        Index("ix_takeout_records_user_id", "user_id"),
        Index("ix_takeout_records_user_created", "user_id", "created_at"),
    )
    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    fortune_id = Column(String(36), ForeignKey("daily_fortunes.id", ondelete="SET NULL"), nullable=True)
    mood = Column(String(10), nullable=False, default="")
    fortune_summary = Column(String(500), nullable=False, default="")
    fortune_keywords = Column(JSON, nullable=False, default=list)
    final_choice = Column(String(100), nullable=False, default="")
    choice_reason = Column(String(500), nullable=False, default="")
    conversation_rounds = Column(SmallInteger, nullable=True)
    satisfaction = Column(String(10), nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=_now)


class ChatTurn(Base):
    __tablename__ = "chat_turns"
    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=True)
    takeout_id = Column(String(36), ForeignKey("takeout_records.id", ondelete="SET NULL"), nullable=True)
    turn = Column(SmallInteger, nullable=False)
    role = Column(String(10), nullable=False)
    content = Column(String(500), nullable=False, default="")
    ai_guess = Column(String(100), nullable=True)
    ai_confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)


class DailyFortune(Base):
    __tablename__ = "daily_fortunes"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_daily_fortunes_user_date"),
    )
    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    zodiac = Column(String(10), nullable=False)
    chinese_zodiac = Column(String(5), nullable=False)
    mbti = Column(String(4), nullable=False)
    zodiac_fortune = Column(String(500), nullable=False, default="")
    chinese_zodiac_fortune = Column(String(500), nullable=False, default="")
    mbti_energy = Column(String(300), nullable=False, default="")
    food_keywords = Column(JSON, nullable=False, default=list)
    lucky_color = Column(String(10), nullable=False, default="")
    lucky_number = Column(SmallInteger, nullable=True)
    suggestion = Column(String(1000), nullable=False, default="")
    lunar_date = Column(String(30), nullable=False, default="")
    solar_term = Column(String(20), nullable=False, default="")
    yi = Column(JSON, nullable=False, default=list)
    ji = Column(JSON, nullable=False, default=list)
    source = Column(String(50), nullable=False, default="llm_web_search")
    created_at = Column(DateTime, nullable=False, default=_now)


class ShoppingItem(Base):
    __tablename__ = "shopping_items"
    __table_args__ = (
        Index("ix_shopping_items_user_id", "user_id"),
    )
    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(50), nullable=False)
    category = Column(String(10), nullable=False)
    quantity = Column(String(20), nullable=False, default="")
    checked = Column(Boolean, nullable=False, default=False)
    source_recipe = Column(String(100), nullable=False, default="")
    source_cook_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)
    checked_at = Column(DateTime, nullable=True)


class PreferenceWeight(Base):
    __tablename__ = "preference_weights"
    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    dimension = Column(String(20), nullable=False)
    weight = Column(DECIMAL(4, 3), nullable=False, default=0.500)
    feedback_count = Column(Integer, nullable=False, default=0)
    last_feedback = Column(String(10), nullable=False, default="")
    updated_at = Column(DateTime, nullable=False, default=_now)


class RecipeCache(Base):
    __tablename__ = "recipe_cache"
    __table_args__ = (
        UniqueConstraint("prompt_hash", name="uq_recipe_cache_prompt_hash"),
        Index("ix_recipe_cache_user_id", "user_id"),
    )
    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    recipe_name = Column(String(100), nullable=False)
    difficulty = Column(SmallInteger, nullable=False, default=1)
    cooking_time = Column(String(10), nullable=False, default="")
    estimated_cost = Column(String(10), nullable=False, default="")
    reason = Column(String(500), nullable=False, default="")
    steps = Column(JSON, nullable=False, default=list)
    matched_ingredients = Column(JSON, nullable=False, default=list)
    missing_ingredients = Column(JSON, nullable=False, default=list)
    llm_model = Column(String(50), nullable=False, default="deepseek-v3")
    llm_temperature = Column(DECIMAL(3, 2), nullable=False, default=0.70)
    prompt_hash = Column(String(64), nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=_now)


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index("ix_chat_sessions_user_id", "user_id"),
    )
    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    takeout_id = Column(String(36), ForeignKey("takeout_records.id", ondelete="SET NULL"), nullable=True)
    current_round = Column(SmallInteger, nullable=False, default=1)
    total_rounds = Column(SmallInteger, nullable=False, default=5)
    status = Column(String(20), nullable=False, default="active")
    taste_choice = Column(String(20), nullable=False, default="")
    staple_choice = Column(String(20), nullable=False, default="")
    meat_choice = Column(String(20), nullable=False, default="")
    form_choice = Column(String(20), nullable=False, default="")
    budget_choice = Column(String(20), nullable=False, default="")
    final_recommend = Column(String(100), nullable=False, default="")
    recommend_reason = Column(String(500), nullable=False, default="")
    alternatives = Column(JSON, nullable=False, default=list)
    total_tokens = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=_now)
    completed_at = Column(DateTime, nullable=True)


class QuotaUsage(Base):
    """每日 LLM 配额使用记录（持久化，防止重启清零）"""
    __tablename__ = "quota_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "date", "kind", name="uq_quota_user_date_kind"),
    )
    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    kind = Column(String(20), nullable=False)
    used = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)
