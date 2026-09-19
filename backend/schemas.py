import re
from datetime import date, datetime
from typing import Optional, Any, Generic, TypeVar

from pydantic import BaseModel, Field, field_validator

T = TypeVar("T")


# ============================================================
# 统一响应包装（P1-4 基础，P0-2 异常也用此格式）
# ============================================================
class ApiResponse(BaseModel, Generic[T]):
    code: int = Field(0, description="0=成功, 其他=业务错误码")
    message: str = Field("ok", description="人类可读的提示文案")
    data: Optional[T] = Field(None, description="业务数据负载")
    trace_id: str = Field("", description="请求链路追踪ID, 排障用")


class PageMeta(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=200)
    total: int = Field(0, ge=0)
    total_pages: int = Field(0, ge=0)


class PagedResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: list[T] = Field(default_factory=list)
    page: PageMeta
    trace_id: str = ""


# ============================================================
# 认证 / 账户（P0-1）
# ============================================================
class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="登录用户名")
    password: str = Field(..., min_length=6, max_length=64, description="登录密码")
    nickname: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=20, description="手机号(可选)")

    @field_validator("username")
    @classmethod
    def _validate_username(cls, v: str) -> str:
        if not re.match(r"^[A-Za-z0-9_\-\u4e00-\u9fa5]{3,50}$", v):
            raise ValueError("用户名仅支持中英文、数字、下划线、中划线(3-50位)")
        return v

    @field_validator("password")
    @classmethod
    def _validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("密码至少 6 位")
        return v

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: Optional[str]) -> Optional[str]:
        # 空串/空白视为未填写（NULL），避免 MySQL UNIQUE 冲突
        if isinstance(v, str):
            v = v.strip()
            if v == "":
                return None
        if v and not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("手机号格式不正确（11位中国大陆手机号）")
        return v


class LoginRequest(BaseModel):
    username: str = Field(..., description="用户名/手机号")
    password: str = Field(..., description="密码")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="access_token 剩余秒数")
    user_id: str
    nickname: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=6)
    new_password: str = Field(..., min_length=6, max_length=64)


class UpdateProfileRequest(BaseModel):
    """个人资料更新（昵称/手机号/头像），全部选填，仅更新传入字段"""
    nickname: Optional[str] = Field(None, min_length=1, max_length=30, description="昵称")
    phone: Optional[str] = Field(None, max_length=20, description="手机号，空串表示解绑")
    avatar_url: Optional[str] = Field(None, max_length=500, description="头像 URL")


# ===== Onboarding =====
# 预算枚举（每餐人均元）：7 档
BUDGET_LEVELS = ["0~15", "16~25", "26~50", "51~100", "101~150", "151~200", "201及以上"]
# 预算旧值 → 新档（向后兼容：已有用户数据用"省钱/正常/吃好点"）
_BUDGET_LEGACY_MAP = {
    "省钱": "0~15",
    "正常": "16~25",
    "吃好点": "51~100",
}
# 厨艺水平：8 档细化
COOKING_SKILLS = ["完全不会", "会烧水/泡面", "会煮面条/粥", "一般会做点（炒简单菜）", "熟练（能做一桌家常菜）", "精通（会做复杂硬菜）", "专业水平（可媲美厨师）", "厨师/餐饮从业者"]
# 厨艺旧值兼容
_COOKING_LEGACY_MAP = {
    "新手": "会烧水/泡面",
    "一般": "一般会做点（炒简单菜）",
    "熟练": "熟练（能做一桌家常菜）",
}
# MBTI 16 种官方类型
MBTI_TYPES = ["INTJ","INTP","ENTJ","ENTP","INFJ","INFP","ENFJ","ENFP","ISTJ","ISFJ","ESTJ","ESFJ","ISTP","ISFP","ESTP","ESFP"]
# 菜系枚举（多选）
CUISINE_TYPES = ["川菜","粤菜","鲁菜","苏菜","浙菜","闽菜","湘菜","徽菜","东北菜","西北菜","云南菜","贵州菜","新疆菜","西藏菜","北京菜","上海菜","广东早茶","港式茶餐","日式","韩式","东南亚","意式","法式","美式","墨西哥","中东","其他菜系"]

def _normalize_budget(v: str) -> str:
    if not v: return BUDGET_LEVELS[1]
    if v in BUDGET_LEVELS: return v
    if v in _BUDGET_LEGACY_MAP: return _BUDGET_LEGACY_MAP[v]
    # 近似匹配
    if "201" in v or "以上" in v: return "201及以上"
    for lv in BUDGET_LEVELS:
        if v in lv: return lv
    return BUDGET_LEVELS[1]

def _normalize_skill(v: str) -> str:
    if not v: return COOKING_SKILLS[3]
    if v in COOKING_SKILLS: return v
    if v in _COOKING_LEGACY_MAP: return _COOKING_LEGACY_MAP[v]
    for lv in COOKING_SKILLS:
        if v and v in lv: return lv
    return COOKING_SKILLS[3]

class OnboardingRequest(BaseModel):
    user_id: str
    taste_preference: str = Field("", description="首选口味: 辣|甜|酸|咸|清淡|油腻|清爽|都行")
    birth_date: date = Field(..., description="出生日期, 后端推算星座/属相")
    mbti: str = Field("", max_length=4, description="MBTI类型，16种官方枚举")
    disliked_ingredients: list[str] = Field(default_factory=list, description="忌口食材列表（三级树+用户自定义其他）")
    cookware: list[str] = Field(default_factory=list, description="厨具列表")
    budget_level: str = Field(BUDGET_LEVELS[1], description="每餐预算: "+" / ".join(BUDGET_LEVELS))
    cooking_skill: str = Field(COOKING_SKILLS[3], description="厨艺水平")
    cuisines: list[str] = Field(default_factory=list, description="喜欢的菜系（多选，枚举+自定义其他）")
    custom_disliked: dict[str, list[str]] = Field(default_factory=dict, description="自定义忌口按节点分组：{分类/子类: [食材,...]}")

    @field_validator("mbti")
    @classmethod
    def _v_mbti(cls, v: str) -> str:
        if not v: return ""
        v = v.strip().upper()
        if len(v) == 4 and v in MBTI_TYPES:
            return v
        if v:  # 非空但非法 → 清空（避免脏数据写入；前端用下拉不会到此）
            return ""
        return ""

    @field_validator("budget_level")
    @classmethod
    def _v_budget(cls, v: str) -> str:
        return _normalize_budget(v)

    @field_validator("cooking_skill")
    @classmethod
    def _v_skill(cls, v: str) -> str:
        return _normalize_skill(v)

    @field_validator("cuisines")
    @classmethod
    def _v_cuisines(cls, v: list[str]) -> list[str]:
        out = []
        for x in (v or []):
            if isinstance(x, str):
                s = x.strip()
                if s and s not in out:
                    out.append(s)
        return out

    @field_validator("disliked_ingredients")
    @classmethod
    def _v_disliked(cls, v: list[str]) -> list[str]:
        out = []
        for x in (v or []):
            if isinstance(x, str):
                s = x.strip()
                if s and s not in out:
                    out.append(s)
        return out


class OnboardingResponse(BaseModel):
    user_id: str
    zodiac: str
    chinese_zodiac: str
    mbti: str
    taste_preference: str
    birth_date: Optional[date] = None
    budget_level: str = BUDGET_LEVELS[1]
    cooking_skill: str = COOKING_SKILLS[3]
    cuisines: list[str] = []
    disliked_ingredients: list[str] = []
    custom_disliked: dict[str, list[str]] = {}
    completed: bool = True


class OnboardingMetaResponse(BaseModel):
    """前端下拉枚举所需的元信息（一次性下发，避免前端写死）"""
    budget_levels: list[str] = BUDGET_LEVELS
    cooking_skills: list[str] = COOKING_SKILLS
    mbti_types: list[str] = MBTI_TYPES
    cuisine_types: list[str] = CUISINE_TYPES


# ===== Ingredients =====
class IngredientCreate(BaseModel):
    user_id: str
    name: str = Field(..., max_length=50)
    category: str = Field("其他", description="蔬菜|肉蛋|水产|主食|调料|乳制品|其他")
    quantity: str = Field("", description="如 3个, 半斤, 200g")
    shelf_days: Optional[int] = Field(None, ge=1, le=3650, description="保质期天数，null 则按分类默认")
    expiry_date: Optional[date] = None
    source: str = Field("manual", description="photo|voice|manual")
    location: str = Field("pool", description="pool|freezer|fridge|cooking")


class IngredientUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    quantity: Optional[str] = None
    shelf_days: Optional[int] = Field(None, ge=1, le=3650)
    expiry_date: Optional[date] = None
    status: Optional[str] = Field(None, description="available|used_up|expired")
    location: Optional[str] = Field(None, description="pool|freezer|fridge|cooking")


class IngredientOut(BaseModel):
    id: str
    user_id: str
    name: str
    category: str
    quantity: str
    shelf_days: Optional[int] = None
    expiry_date: Optional[date] = None
    source: str
    status: str
    location: str = "pool"
    created_at: datetime

    class Config:
        from_attributes = True


# ===== Recipe =====
class RecipeRequest(BaseModel):
    user_id: str
    ingredient_names: list[str] = Field(default_factory=list, description="库存食材名称列表")
    taste_weights: dict[str, float] = Field(default_factory=dict, description="口味权重")
    budget_level: str = "正常"
    cooking_skill: str = "一般"
    disliked_ingredients: list[str] = Field(default_factory=list)
    exclude_recipes: list[str] = Field(default_factory=list, description="换一换: 排除已展示的菜名")
    regenerate_count: int = Field(0, ge=0, le=3, description="换一换次数")


class RecipeItem(BaseModel):
    id: str = Field("", description="RecipeCache ID，创建 Cook 日记时作为 ai_recommend_id 回传，用于归因")
    name: str
    difficulty: int = Field(1, ge=1, le=3)
    cooking_time: str
    estimated_cost: str
    reason: str
    steps: list[str] = Field(default_factory=list)
    matched_ingredients: list[str] = Field(default_factory=list)
    missing_ingredients: list[str] = Field(default_factory=list)


class RecipeResponse(BaseModel):
    recipes: list[RecipeItem]
    model: str = "deepseek-v3"
    prompt_hash: str = ""


# ===== Shopping List =====
class ShoppingItemCreate(BaseModel):
    user_id: str
    name: str
    category: str = "其他"
    quantity: str = ""
    source_recipe: str = ""


class ShoppingItemOut(BaseModel):
    id: str
    name: str
    category: str
    quantity: str
    checked: bool
    source_recipe: str

    class Config:
        from_attributes = True


class ShoppingItemCheck(BaseModel):
    checked: bool


# ===== Fortune =====
class FortuneResponse(BaseModel):
    id: str
    date: date
    zodiac: str
    chinese_zodiac: str
    mbti: str
    food_keywords: list[str] = Field(default_factory=list)
    lucky_color: str = ""
    lucky_number: Optional[int] = None
    lucky_food: str = ""
    suggestion: str = ""
    lunar_date: str = ""
    solar_term: str = ""
    yi: list[str] = Field(default_factory=list)
    ji: list[str] = Field(default_factory=list)
    cached: bool = False


# ===== Chat =====
class ChatSessionCreate(BaseModel):
    user_id: str
    mood: str = Field("", description="今日心情: 开心|难过|烦躁|焦虑|疲惫|庆祝|嘴馋|平淡")


class ChatTurnRequest(BaseModel):
    session_id: str
    answer: str = Field("", description="用户本轮选择")


class ChatTurnResponse(BaseModel):
    session_id: str
    current_round: int
    total_rounds: int = 5
    dimension: str
    question: str
    options: list[str] = Field(default_factory=list)
    status: str = "active"


class ChatFinalRecommend(BaseModel):
    session_id: str
    final_recommend: str
    recommend_reason: str
    alternatives: list[str] = Field(default_factory=list)
    meituan_url: str = ""
    delivery_urls: dict = Field(default_factory=dict, description="多平台外卖搜索链接: meituan/eleme/bing/baidu")


# ===== Diary =====
class DiaryStats(BaseModel):
    cook_count: int = 0
    takeout_count: int = 0
    total_cook_cost: float = 0.0
    total_takeout_cost: float = 0.0
    saved_money: float = 0.0
    avg_cook_rating: float = 0.0


class HeatmapDay(BaseModel):
    day: int
    date: str
    type: str = Field("", description="cook|order|both|empty")
    title: str = ""


class DiaryEntry(BaseModel):
    id: str
    date: str
    type: str
    title: str
    rating: int = 0
    mood: str = ""
    cost: float = 0.0

    class Config:
        from_attributes = True


class PreferenceWeight(BaseModel):
    dimension: str
    weight: float
    feedback_count: int = 0
    last_feedback: str = ""


class CookRecordCreate(BaseModel):
    user_id: str
    dish_name: str
    ai_recommend_id: str = Field("", description="菜谱推荐返回的 RecipeCache.id，用于归因统计推荐命中率")
    rating: int = Field(2, ge=1, le=3, description="1踩雷 2还行 3好吃")
    mood: str = ""
    cooking_time: Optional[int] = None
    difficulty: str = "简单"
    estimated_cost: Optional[float] = None
    note: str = ""
    tags: list[str] = Field(default_factory=list)


class TakeoutRecordCreate(BaseModel):
    user_id: str
    session_id: str = ""
    mood: str = ""
    final_choice: str
    choice_reason: str = ""
    satisfaction: str = Field("", description="好吃|一般|踩雷")
    conversation_rounds: int = 0


class FeedbackRequest(BaseModel):
    user_id: str
    recipe_name: str = ""
    dish_name: str = ""
    rating: int = Field(2, ge=1, le=3, description="1踩雷 2还行 3好吃")
    type: str = Field("cook", description="cook|order")
