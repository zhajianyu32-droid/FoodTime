"""
FoodTime 后端主入口
已应用 P0/P1 工程化加固:
  P0-1 JWT 认证 + 资源归属校验
  P0-2 全局异常处理 + 统一 ApiResponse 包装
  P0-3 速率限制 + LLM 每日配额
  P1-1 结构化日志 + Trace ID
  P1-2 DB 事务回滚 + 原子计数器
  P1-4 分页支持 + 输入枚举校验
"""
import json
from datetime import date, datetime, timedelta
from typing import Optional, Union

from fastapi import FastAPI, Depends, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, update
from sqlalchemy.orm import Session

from config import settings
from database import engine, Base, get_db
from errors import BizError, ERR, register_exception_handlers, _resp
from logging_config import get_logger, setup_logging, get_trace_id
from models import (
    User, UserPreference, Ingredient, CookRecord, TakeoutRecord,
    ChatTurn, DailyFortune, ShoppingItem, PreferenceWeight,
    RecipeCache, ChatSession,
)
from quota_limiter import (
    limiter, attach_limiter, consume_quota, get_quota_info, QuotaKind,
)
from schemas import (
    ApiResponse, PagedResponse, PageMeta,
    RegisterRequest, LoginRequest, TokenResponse, RefreshTokenRequest, ChangePasswordRequest,
    UpdateProfileRequest,
    OnboardingRequest, OnboardingResponse, OnboardingMetaResponse,
    _normalize_budget, _normalize_skill,
    IngredientCreate, IngredientUpdate, IngredientOut,
    RecipeRequest, RecipeResponse,
    ShoppingItemCreate, ShoppingItemOut, ShoppingItemCheck,
    FortuneResponse,
    ChatSessionCreate, ChatTurnRequest, ChatTurnResponse, ChatFinalRecommend,
    DiaryStats, HeatmapDay, DiaryEntry,
    CookRecordCreate, TakeoutRecordCreate, FeedbackRequest,
    PreferenceWeight as PreferenceWeightSchema,
)
from security import (
    get_current_user, decode_token, TokenType, issue_tokens,
    hash_password, verify_password, require_owner,
)
from services.llm_service import llm_service
from services.recipe_service import recipe_service
from services.chat_service import chat_service
from services.fortune_service import fortune_service, calc_zodiac
from services.preference_service import preference_service

# ---------- 初始化 ----------
setup_logging()
logger = get_logger("foodtime.main")

app = FastAPI(
    title="FoodTime 食光 API",
    description="独居青年吃饭决策助手后端 — 已启用 JWT 认证/限流/日志/统一响应",
    version="2.1.0",
    docs_url="/docs" if settings.DEBUG else None,   # 生产环境关闭 Swagger
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_origin_regex=settings.cors_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "Authorization", "X-Trace-Id"],
    expose_headers=["X-Trace-Id", "X-Response-Time-Ms", "X-App-Env", "X-DB-Name"],
)

# P0-2: 全局异常 + 访问日志 + Trace ID
register_exception_handlers(app)
# P0-3: 速率限制
attach_limiter(app)


@app.on_event("startup")
def on_startup():
    if settings.DEBUG:
        Base.metadata.create_all(bind=engine)
    # P0-3 修复: 启动时把过期食材一次性置为 expired（进程重启也能保证数据干净）
    try:
        from sqlalchemy import update as _upd
        from datetime import date as _date_today
        with engine.connect() as conn:
            n = conn.execute(
                _upd(Ingredient)
                .where(Ingredient.status == "available")
                .where(Ingredient.expiry_date.is_not(None))
                .where(Ingredient.expiry_date < _date_today.today())
                .values(status="expired")
            ).rowcount
            if n:
                conn.commit()
                logger.info("Startup: auto-expired %s ingredients (expiry < today)", n)
    except Exception as exc:  # 启动时 DB 不可用也不能把进程带崩
        logger.warning("Startup ingredient auto-expire skipped: %s", exc)

    logger.info("FoodTime API started: env=%s db=%s debug=%s",
                settings.APP_ENV, settings.DB_NAME, settings.DEBUG)


@app.on_event("shutdown")
def on_shutdown():
    logger.info("FoodTime API shutdown")


# ============================================================
# 工具函数
# ============================================================
def ok(data=None, message: str = "ok", code: int = 0):
    return ApiResponse(code=code, message=message, data=data, trace_id=get_trace_id()).model_dump()


def paged(data: list, page: int, page_size: int, total: int):
    total_pages = (total + page_size - 1) // page_size if page_size else 0
    return PagedResponse(
        code=0, message="ok",
        data=data,
        page=PageMeta(page=page, page_size=page_size, total=total, total_pages=total_pages),
        trace_id=get_trace_id(),
    ).model_dump()


VALID_INGREDIENT_CATEGORIES = {"蔬菜", "肉蛋", "水产", "主食", "调料", "乳制品", "其他"}


def _check_category(value: str, field: str = "category") -> None:
    if value and value not in VALID_INGREDIENT_CATEGORIES:
        raise BizError(
            ERR["PARAM_INVALID"][0],
            f"{field} 必须是以下之一: {', '.join(sorted(VALID_INGREDIENT_CATEGORIES))}"
        )


# ============================================================
# P0-1: 认证 / 账户接口
# ============================================================
@app.post("/api/auth/register", response_model=ApiResponse[TokenResponse])
@limiter.limit("5/minute")
async def register(request: Request, req: RegisterRequest, db: Session = Depends(get_db)):
    """注册新账户 + 自动登录返回 token"""
    # 规范化 phone（防止 pydantic validator 被绕过）
    phone_value = req.phone
    if isinstance(phone_value, str) and phone_value.strip() == "":
        phone_value = None

    # 用户名/手机号去重（注意: 必须用 sqlalchemy and_/or_ 组合条件，不能用 Python &/| 直接与 bool 混算，否则 TypeError: bool & BinaryExpression）
    from sqlalchemy import and_, or_
    dup_filter = [User.username == req.username]
    # 只有非空 phone 才加入重复检查；否则 phone 都是 NULL 会匹配不到（UNIQUE 对 NULL 也不冲突）
    if phone_value:
        dup_filter.append(User.phone == phone_value)
    dup = db.query(User).filter(or_(*dup_filter)).first()
    if dup:
        if dup.username == req.username:
            raise BizError(*ERR["USERNAME_DUPLICATE"])
        raise BizError(*ERR["PHONE_DUPLICATE"])

    user = User(
        username=req.username,
        phone=phone_value,
        password_hash=hash_password(req.password),
        nickname=req.nickname or req.username,
        status="active",
    )
    db.add(user)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("register commit failed: %s", exc, exc_info=True)
        # 唯一键冲突等直接透传，让 errors.py 的异常处理器给出更友好的提示
        from sqlalchemy.exc import IntegrityError as _SaInteg
        if isinstance(exc, _SaInteg):
            raise
        raise BizError(*ERR["DB_ERROR"])
    db.refresh(user)

    tokens = issue_tokens(user.id)
    logger.info("User registered: %s (%s)", user.username, user.id, user_id=user.id)
    return ok(TokenResponse(
        user_id=user.id, nickname=user.nickname, **tokens,
    ))


@app.post("/api/auth/login", response_model=ApiResponse[TokenResponse])
@limiter.limit("10/minute")
async def login(request: Request, req: LoginRequest, db: Session = Depends(get_db)):
    """用户名 + 密码登录"""
    user = db.query(User).filter(
        (User.username == req.username) | (User.phone == req.username)
    ).first()
    if not user or not user.password_hash or not verify_password(req.password, user.password_hash):
        raise BizError(*ERR["AUTH_INVALID"])
    if user.status == "banned":
        raise BizError(*ERR["USER_BANNED"])

    tokens = issue_tokens(user.id)
    logger.info("User login: %s (%s)", user.username or user.phone, user.id, user_id=user.id)
    return ok(TokenResponse(
        user_id=user.id, nickname=user.nickname, **tokens,
    ))


@app.post("/api/auth/refresh", response_model=ApiResponse[TokenResponse])
async def refresh(req: RefreshTokenRequest, db: Session = Depends(get_db)):
    """使用 refresh_token 换取新的 access_token"""
    payload = decode_token(req.refresh_token, expected_type=TokenType.REFRESH)
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user or user.status != "active":
        raise BizError(*ERR["AUTH_EXPIRED"])
    # P0-6: 签发过的 refresh token 在改密/挂失后立即失效（黑名单）
    valid_since = getattr(user, "token_valid_since", None) or 0.0
    iat = payload.get("iat_ts")
    if isinstance(iat, int) and valid_since > 0 and iat < int(valid_since):
        raise BizError(*ERR["AUTH_EXPIRED"])
    tokens = issue_tokens(user.id)
    return ok(TokenResponse(
        user_id=user.id, nickname=user.nickname, **tokens,
    ))


@app.post("/api/auth/password")
async def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.password_hash or not verify_password(req.old_password, current_user.password_hash):
        raise BizError(ERR["AUTH_INVALID"][0], "原密码错误")
    current_user.password_hash = hash_password(req.new_password)
    # P0-6: 改密后立即把 user.token_valid_since 推进到当前时间，旧 access/refresh 全部作废
    import time as _t
    current_user.token_valid_since = _t.time()
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise BizError(*ERR["DB_ERROR"])
    logger.info("Password changed; all older tokens revoked", user_id=current_user.id)
    return ok({"changed": True})


@app.patch("/api/auth/profile")
async def update_profile(
    req: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新个人资料（昵称/手机号/头像），仅更新传入字段"""
    updates = req.model_dump(exclude_unset=True, exclude_none=True)
    # 空串手机号 = 解绑（置 NULL），与注册逻辑一致
    if "phone" in updates and isinstance(updates["phone"], str) and not updates["phone"].strip():
        updates["phone"] = None
    if updates.get("phone"):
        dup = (
            db.query(User)
            .filter(User.phone == updates["phone"], User.id != current_user.id)
            .first()
        )
        if dup:
            raise BizError(*ERR["PHONE_DUPLICATE"])
    for field, value in updates.items():
        setattr(current_user, field, value)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise BizError(*ERR["DB_ERROR"])
    logger.info("Profile updated", user_id=current_user.id)
    return ok({
        "user_id": current_user.id,
        "username": current_user.username,
        "nickname": current_user.nickname,
        "phone": current_user.phone,
        "avatar_url": current_user.avatar_url,
    })


@app.get("/api/auth/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户资料（用于前端启动时恢复登录态）"""
    return ok({
        "user_id": current_user.id,
        "username": current_user.username,
        "phone": current_user.phone,
        "nickname": current_user.nickname,
        "avatar_url": current_user.avatar_url,
        "total_cook_count": current_user.total_cook_count,
        "total_takeout_count": current_user.total_takeout_count,
        "streak_days": current_user.streak_days,
        "quota": get_quota_info(current_user.id),
    })


# ============================================================
# Onboarding（需登录，归属由 current_user 保障）
# ============================================================
@app.post("/api/onboarding", response_model=ApiResponse[OnboardingResponse])
async def save_onboarding(
    req: OnboardingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # req.user_id 仅作兼容，实际以登录态为准
    user_id = current_user.id
    zodiac, chinese_zodiac = calc_zodiac(req.birth_date)

    prefs = (
        db.query(UserPreference)
        .filter(UserPreference.user_id == user_id)
        .first()
    )
    if not prefs:
        prefs = UserPreference(user_id=user_id)
        db.add(prefs)

    prefs.zodiac = zodiac
    prefs.chinese_zodiac = chinese_zodiac
    prefs.mbti = req.mbti
    prefs.taste_preference = req.taste_preference
    prefs.disliked_ingredients = req.disliked_ingredients
    prefs.cookware = req.cookware
    prefs.budget_level = req.budget_level
    prefs.cooking_skill = req.cooking_skill
    # v2.1 偏好扩展
    try:
        prefs.cuisines = req.cuisines or []
    except Exception:
        # 数据库列尚未迁移时的兼容
        pass
    # 设置页回显与自定义忌口持久化
    prefs.birth_date = req.birth_date
    try:
        prefs.custom_disliked = req.custom_disliked or {}
    except Exception:
        pass

    preference_service.init_weights(user_id, req.taste_preference, db)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise BizError(*ERR["DB_ERROR"])

    logger.info("Onboarding saved", user_id=user_id)
    return ok(OnboardingResponse(
        user_id=user_id,
        zodiac=zodiac,
        chinese_zodiac=chinese_zodiac,
        mbti=req.mbti,
        taste_preference=req.taste_preference,
        birth_date=req.birth_date,
        budget_level=req.budget_level,
        cooking_skill=req.cooking_skill,
        cuisines=req.cuisines or [],
        disliked_ingredients=req.disliked_ingredients or [],
        custom_disliked=req.custom_disliked or {},
        completed=True,
    ))


@app.get("/api/onboarding/meta", response_model=ApiResponse[OnboardingMetaResponse])
def onboarding_meta(current_user: User = Depends(get_current_user)):
    """前端下拉枚举所需的元信息，避免前后端重复维护硬编码"""
    from schemas import BUDGET_LEVELS, COOKING_SKILLS, MBTI_TYPES, CUISINE_TYPES
    return ok(OnboardingMetaResponse(
        budget_levels=list(BUDGET_LEVELS),
        cooking_skills=list(COOKING_SKILLS),
        mbti_types=list(MBTI_TYPES),
        cuisine_types=list(CUISINE_TYPES),
    ))


@app.get("/api/preferences/{user_id}")
def get_preferences(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(user_id, current_user)
    prefs = (
        db.query(UserPreference)
        .filter(UserPreference.user_id == user_id)
        .first()
    )
    if not prefs:
        return ok({"user_id": user_id, "onboarding_completed": False})
    # 读取时做旧值兼容（budget_level/skill 若为 v1 值则转 v2）
    cuisines_val = []
    try:
        cuisines_val = list(prefs.cuisines or []) if getattr(prefs, "cuisines", None) is not None else []
    except Exception:
        cuisines_val = []
    return ok({
        "user_id": user_id,
        "onboarding_completed": True,
        "zodiac": prefs.zodiac,
        "chinese_zodiac": prefs.chinese_zodiac,
        "mbti": prefs.mbti,
        "taste_preference": prefs.taste_preference,
        "taste_weights": prefs.taste_weights or {},
        "budget_level": _normalize_budget(prefs.budget_level or ""),
        "cooking_skill": _normalize_skill(prefs.cooking_skill or ""),
        "disliked_ingredients": prefs.disliked_ingredients or [],
        "cookware": prefs.cookware or [],
        "cuisines": cuisines_val,
        "birth_date": prefs.birth_date.isoformat() if getattr(prefs, "birth_date", None) else None,
        "custom_disliked": getattr(prefs, "custom_disliked", None) or {},
        "liked_dishes": prefs.liked_dishes or [],
    })


@app.get("/api/preferences/weights/{user_id}", response_model=ApiResponse[list[PreferenceWeightSchema]])
def get_preference_weights(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(user_id, current_user)
    return ok(preference_service.get_weights(user_id, db))


# ============================================================
# Ingredients (Cook Mode)
# ============================================================
@app.get("/api/ingredients/{user_id}")
def list_ingredients(
    user_id: str,
    status_filter: Optional[str] = Query(None, alias="status", description="available|used_up|expired"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(user_id, current_user)
    # P0-3 修复: 懒更新 — 每次查询前把当前用户过期的 available 食材置为 expired
    today = date.today()
    expired_n = (
        db.query(Ingredient)
        .filter(Ingredient.user_id == user_id)
        .filter(Ingredient.status == "available")
        .filter(Ingredient.expiry_date.is_not(None))
        .filter(Ingredient.expiry_date < today)
        .update(
            {Ingredient.status: "expired"},
            synchronize_session=False,
        )
    )
    if expired_n:
        try:
            db.commit()
            logger.info(
                "Lazy-expire: auto-marked %s ingredients as expired for user=%s",
                expired_n, user_id, user_id=user_id,
            )
        except Exception:
            db.rollback()

    q = db.query(Ingredient).filter(Ingredient.user_id == user_id)
    if status_filter:
        q = q.filter(Ingredient.status == status_filter)
    total = q.count()
    items = (
        q.order_by(Ingredient.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return paged([IngredientOut.model_validate(x).model_dump() for x in items],
                 page, page_size, total)


@app.post("/api/ingredients", response_model=ApiResponse[IngredientOut])
def create_ingredient(
    req: IngredientCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 强制归属为当前用户
    user_id = current_user.id
    _check_category(req.category)
    ing = Ingredient(
        user_id=user_id,
        name=req.name.strip()[:50],
        category=req.category,
        quantity=req.quantity,
        expiry_date=req.expiry_date,
        source=req.source,
        status="available",
    )
    db.add(ing)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise BizError(*ERR["DB_ERROR"])
    db.refresh(ing)
    logger.info("Ingredient added: %s", ing.name, user_id=user_id)
    return ok(IngredientOut.model_validate(ing))


@app.put("/api/ingredients/{ingredient_id}", response_model=ApiResponse[IngredientOut])
def update_ingredient(
    ingredient_id: str,
    req: IngredientUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ing = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ing:
        raise BizError(*ERR["INGREDIENT_NOT_FOUND"])
    require_owner(ing.user_id, current_user)
    if req.category is not None:
        _check_category(req.category)
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(ing, k, v)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise BizError(*ERR["DB_ERROR"])
    db.refresh(ing)
    return ok(IngredientOut.model_validate(ing))


@app.delete("/api/ingredients/{ingredient_id}")
def delete_ingredient(
    ingredient_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ing = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ing:
        raise BizError(*ERR["INGREDIENT_NOT_FOUND"])
    require_owner(ing.user_id, current_user)
    db.delete(ing)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise BizError(*ERR["DB_ERROR"])
    return ok({"deleted": True})


# ============================================================
# Recipe Recommendation (Cook Mode) — LLM 配额
# ============================================================
@app.post("/api/recipes/recommend", response_model=ApiResponse[RecipeResponse])
@limiter.limit("20/minute")
async def recommend_recipes(
    request: Request,
    req: RecipeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    await consume_quota(current_user.id, QuotaKind.RECIPE)
    request.state.current_user = current_user

    # 归属：强制 user_id
    prefs = (
        db.query(UserPreference)
        .filter(UserPreference.user_id == current_user.id)
        .first()
    )
    taste_weights = req.taste_weights
    if not taste_weights and prefs:
        taste_weights = preference_service.get_weights_dict(current_user.id, db)

    disliked = req.disliked_ingredients
    if not disliked and prefs:
        disliked = prefs.disliked_ingredients or []

    full_req = RecipeRequest(
        user_id=current_user.id,
        ingredient_names=req.ingredient_names,
        taste_weights=taste_weights,
        budget_level=prefs.budget_level if prefs else req.budget_level,
        cooking_skill=prefs.cooking_skill if prefs else req.cooking_skill,
        disliked_ingredients=disliked,
        exclude_recipes=req.exclude_recipes,
        regenerate_count=req.regenerate_count,
    )
    result = await recipe_service.recommend(full_req, db)
    return ok(result)


# ============================================================
# Shopping List (Cook Mode)
# ============================================================
@app.get("/api/shopping/{user_id}")
def list_shopping(
    user_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(user_id, current_user)
    q = (
        db.query(ShoppingItem)
        .filter(ShoppingItem.user_id == user_id)
        .order_by(ShoppingItem.checked, ShoppingItem.created_at.desc())
    )
    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return paged([ShoppingItemOut.model_validate(x).model_dump() for x in items],
                 page, page_size, total)


@app.post("/api/shopping", response_model=ApiResponse[ShoppingItemOut])
def create_shopping_item(
    req: ShoppingItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _check_category(req.category)
    item = ShoppingItem(
        user_id=current_user.id,
        name=req.name.strip()[:50],
        category=req.category,
        quantity=req.quantity,
        source_recipe=req.source_recipe,
    )
    db.add(item)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise BizError(*ERR["DB_ERROR"])
    db.refresh(item)
    return ok(ShoppingItemOut.model_validate(item))


@app.put("/api/shopping/{item_id}", response_model=ApiResponse[ShoppingItemOut])
def check_shopping_item(
    item_id: str,
    req: ShoppingItemCheck,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.query(ShoppingItem).filter(ShoppingItem.id == item_id).first()
    if not item:
        raise BizError(*ERR["SHOPPING_NOT_FOUND"])
    require_owner(item.user_id, current_user)
    item.checked = req.checked
    item.checked_at = datetime.now() if req.checked else None
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise BizError(*ERR["DB_ERROR"])
    db.refresh(item)
    return ok(ShoppingItemOut.model_validate(item))


@app.delete("/api/shopping/{item_id}", response_model=ApiResponse[dict])
def delete_shopping_item(
    item_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.query(ShoppingItem).filter(ShoppingItem.id == item_id).first()
    if not item:
        raise BizError(*ERR["SHOPPING_NOT_FOUND"])
    require_owner(item.user_id, current_user)
    try:
        db.delete(item)
        db.commit()
    except Exception:
        db.rollback()
        raise BizError(*ERR["DB_ERROR"])
    return ok({"deleted": True, "id": item_id})


# ============================================================
# Fortune (Order Mode)
# ============================================================
@app.get("/api/fortune/today/{user_id}", response_model=ApiResponse[FortuneResponse])
async def get_today_fortune(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(user_id, current_user)
    await consume_quota(current_user.id, QuotaKind.FORTUNE)
    return ok(await fortune_service.get_today_fortune(user_id, db))


# ============================================================
# Chat (Order Mode) — 5-round state machine
# ============================================================
@app.post("/api/chat/session", response_model=ApiResponse[ChatTurnResponse])
def create_chat_session(
    req: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 强制归属
    from schemas import ChatSessionCreate as _SC
    req2 = _SC(user_id=current_user.id, mood=req.mood)
    # P0-2 / P1-12 配额修复：仅在最终 LLM 推荐生成成功时才扣 CHAT 配额
    # （避免 session 创建时就扣、实际 LLM 失败导致用户白亏一次额度）
    # 此处不扣；扣额度位置移至 chat_service._generate_final_recommend 成功后。
    return ok(chat_service.create_session(req2, db))


@app.post("/api/chat/turn", response_model=ApiResponse[Union[ChatTurnResponse, ChatFinalRecommend]])
async def process_chat_turn(
    req: ChatTurnRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 归属校验：先查 session 是否属于当前用户
    session = db.query(ChatSession).filter(ChatSession.id == req.session_id).first()
    if not session:
        raise BizError(*ERR["SESSION_NOT_FOUND"])
    require_owner(session.user_id, current_user)
    result = await chat_service.process_turn(req, db)
    return ok(result)


# ============================================================
# Cook Record
# ============================================================
def _atomic_increment_counter(db: Session, user_id: str, field: str) -> None:
    """原子更新计数器，避免并发丢失"""
    stmt = update(User).where(User.id == user_id).values(
        **{field: getattr(User, field) + 1}
    ).execution_options(synchronize_session=False)
    db.execute(stmt)


@app.post("/api/diary/cook", response_model=ApiResponse[DiaryEntry])
def create_cook_record(
    req: CookRecordCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id
    try:
        # P0-4 修复: 允许回传 RecipeCache.id 做归因闭环
        recommend_id = None
        if req.ai_recommend_id:
            rc = (
                db.query(RecipeCache)
                .filter(RecipeCache.id == req.ai_recommend_id, RecipeCache.user_id == user_id)
                .first()
            )
            if rc:
                recommend_id = rc.id
        record = CookRecord(
            user_id=user_id,
            ai_recommend_id=recommend_id,
            dish_name=req.dish_name.strip()[:100],
            rating=req.rating,
            mood=req.mood,
            cooking_time=req.cooking_time,
            difficulty=req.difficulty,
            estimated_cost=req.estimated_cost,
            note=req.note,
            tags=req.tags,
        )
        db.add(record)
        _atomic_increment_counter(db, user_id, "total_cook_count")
        update_user_activity(user_id, db)

        pref_req = FeedbackRequest(
            user_id=user_id,
            dish_name=req.dish_name,
            rating=req.rating,
            type="cook",
        )
        preference_service.apply_feedback(pref_req, db)
        db.commit()
        db.refresh(record)
    except BizError:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error("create_cook_record failed: %s", exc, exc_info=True, user_id=user_id)
        raise BizError(*ERR["DB_ERROR"])

    return ok(DiaryEntry(
        id=record.id,
        date=record.created_at.strftime("%Y-%m-%d"),
        type="cook",
        title=record.dish_name,
        rating=record.rating or 2,
        mood=record.mood,
        cost=float(record.estimated_cost or 0),
    ))


# ============================================================
# Takeout Record
# ============================================================
@app.post("/api/diary/takeout", response_model=ApiResponse[DiaryEntry])
def create_takeout_record(
    req: TakeoutRecordCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id
    try:
        fortune_id = None
        fortune_summary = ""
        fortune_keywords = []

        fortune = (
            db.query(DailyFortune)
            .filter(
                DailyFortune.user_id == user_id,
                DailyFortune.date == date.today(),
            )
            .first()
        )
        if fortune:
            fortune_id = fortune.id
            fortune_summary = fortune.suggestion
            fortune_keywords = fortune.food_keywords or []

        session = None
        if req.session_id:
            session = (
                db.query(ChatSession).filter(ChatSession.id == req.session_id).first()
            )
            if session:
                require_owner(session.user_id, current_user)

        record = TakeoutRecord(
            user_id=user_id,
            fortune_id=fortune_id,
            mood=req.mood,
            fortune_summary=fortune_summary,
            fortune_keywords=fortune_keywords,
            final_choice=req.final_choice,
            choice_reason=req.choice_reason,
            conversation_rounds=req.conversation_rounds,
            satisfaction=req.satisfaction,
        )
        db.add(record)

        if session:
            session.takeout_id = record.id

        _atomic_increment_counter(db, user_id, "total_takeout_count")
        update_user_activity(user_id, db)

        satisfaction_map = {"好吃": 3, "一般": 2, "踩雷": 1}
        pref_req = FeedbackRequest(
            user_id=user_id,
            recipe_name=req.final_choice,
            rating=satisfaction_map.get(req.satisfaction, 2),
            type="order",
        )
        preference_service.apply_feedback(pref_req, db)
        db.commit()
        db.refresh(record)
    except BizError:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error("create_takeout_record failed: %s", exc, exc_info=True, user_id=user_id)
        raise BizError(*ERR["DB_ERROR"])

    return ok(DiaryEntry(
        id=record.id,
        date=record.created_at.strftime("%Y-%m-%d"),
        type="order",
        title=record.final_choice,
        rating=satisfaction_map.get(req.satisfaction, 2),
        mood=record.mood,
        cost=0.0,
    ))


# ============================================================
# Feedback
# ============================================================
@app.post("/api/feedback")
def submit_feedback(
    req: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 强制归属
    req2 = FeedbackRequest(
        user_id=current_user.id,
        recipe_name=req.recipe_name,
        dish_name=req.dish_name,
        rating=req.rating,
        type=req.type,
    )
    weights = preference_service.apply_feedback(req2, db)
    return ok({
        "updated": True,
        "weights": [w.model_dump() for w in weights],
        "formula": "newW = oldW × 0.7 + feedback × 0.3",
    })


# ============================================================
# Diary Stats / Heatmap / List
# ============================================================
@app.get("/api/diary/stats/{user_id}", response_model=ApiResponse[DiaryStats])
def get_diary_stats(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(user_id, current_user)
    month_start = date.today().replace(day=1)

    cook_count = (
        db.query(func.count(CookRecord.id))
        .filter(
            CookRecord.user_id == user_id,
            CookRecord.created_at >= month_start,
        )
        .scalar()
    ) or 0

    takeout_count = (
        db.query(func.count(TakeoutRecord.id))
        .filter(
            TakeoutRecord.user_id == user_id,
            TakeoutRecord.created_at >= month_start,
        )
        .scalar()
    ) or 0

    total_cook_cost = (
        db.query(func.coalesce(func.sum(CookRecord.estimated_cost), 0))
        .filter(
            CookRecord.user_id == user_id,
            CookRecord.created_at >= month_start,
        )
        .scalar()
    ) or 0

    avg_cook_rating = (
        db.query(func.coalesce(func.avg(CookRecord.rating), 0))
        .filter(
            CookRecord.user_id == user_id,
            CookRecord.created_at >= month_start,
        )
        .scalar()
    ) or 0

    avg_takeout_cost = 25.0
    saved_money = max(0, takeout_count * avg_takeout_cost - float(total_cook_cost))

    return ok(DiaryStats(
        cook_count=cook_count,
        takeout_count=takeout_count,
        total_cook_cost=float(total_cook_cost),
        total_takeout_cost=takeout_count * avg_takeout_cost,
        saved_money=round(saved_money, 2),
        avg_cook_rating=round(float(avg_cook_rating), 2),
    ))


@app.get("/api/diary/heatmap/{user_id}", response_model=ApiResponse[list[HeatmapDay]])
def get_heatmap(
    user_id: str,
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(user_id, current_user)
    today = date.today()
    y = year or today.year
    m = month or today.month

    if m == 12:
        next_month = date(y + 1, 1, 1)
    else:
        next_month = date(y, m + 1, 1)
    month_start = date(y, m, 1)

    cook_days = {}
    from sqlalchemy import func as sa_func
    cook_records = (
        db.query(
            sa_func.day(CookRecord.created_at).label("d"),
            CookRecord.dish_name,
            CookRecord.rating,
        )
        .filter(
            CookRecord.user_id == user_id,
            CookRecord.created_at >= month_start,
            CookRecord.created_at < next_month,
        )
        .order_by(CookRecord.created_at.asc())
        .all()
    )
    for cr in cook_records:
        d = int(cr.d)
        if d not in cook_days:
            cook_days[d] = {"title": cr.dish_name, "rating": cr.rating or 2}

    takeout_days = {}
    takeout_records = (
        db.query(
            sa_func.day(TakeoutRecord.created_at).label("d"),
            TakeoutRecord.final_choice,
        )
        .filter(
            TakeoutRecord.user_id == user_id,
            TakeoutRecord.created_at >= month_start,
            TakeoutRecord.created_at < next_month,
        )
        .order_by(TakeoutRecord.created_at.asc())
        .all()
    )
    for tr in takeout_records:
        d = int(tr.d)
        if d not in takeout_days:
            takeout_days[d] = {"title": tr.final_choice, "rating": 2}

    days_in_month = (next_month - month_start).days
    result = []
    for d in range(1, days_in_month + 1):
        has_cook = d in cook_days
        has_takeout = d in takeout_days
        if has_cook and has_takeout:
            dtype = "both"
            title = f"{cook_days[d]['title']}/{takeout_days[d]['title']}"
        elif has_cook:
            dtype = "cook"
            title = cook_days[d]["title"]
        elif has_takeout:
            dtype = "order"
            title = takeout_days[d]["title"]
        else:
            dtype = "empty"
            title = ""
        result.append(HeatmapDay(
            day=d,
            date=f"{y}-{m:02d}-{d:02d}",
            type=dtype,
            title=title,
        ))
    return ok(result)


@app.get("/api/diary/list/{user_id}")
def get_diary_list(
    user_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    filter_type: Optional[str] = Query(None, description="cook|order"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(user_id, current_user)
    satisfaction_map = {"好吃": 3, "一般": 2, "踩雷": 1}

    # 使用 SQL 分页：先查 cook 和 takeout 的 (id, created_at) 用于排序，再分页
    from sqlalchemy import union_all, literal_column, cast, String

    cook_q = (
        db.query(
            CookRecord.id.label("rid"),
            CookRecord.created_at.label("rdate"),
            literal_column("'cook'").label("rtype"),
        )
        .filter(CookRecord.user_id == user_id)
    )
    takeout_q = (
        db.query(
            TakeoutRecord.id.label("rid"),
            TakeoutRecord.created_at.label("rdate"),
            literal_column("'order'").label("rtype"),
        )
        .filter(TakeoutRecord.user_id == user_id)
    )

    if filter_type == "cook":
        union_q = cook_q
    elif filter_type == "order":
        union_q = takeout_q
    else:
        union_q = cook_q.union_all(takeout_q)

    # 先取分页后的 id 列表
    total = union_q.count()
    offset = (page - 1) * page_size
    page_rows = (
        union_q.order_by(literal_column("rdate").desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    results = []
    cook_ids = [r.rid for r in page_rows if r.rtype == "cook"]
    takeout_ids = [r.rid for r in page_rows if r.rtype == "order"]

    if cook_ids:
        cook_map = {
            cr.id: cr
            for cr in db.query(CookRecord).filter(CookRecord.id.in_(cook_ids)).all()
        }
        for r in page_rows:
            if r.rtype == "cook":
                cr = cook_map.get(r.rid)
                if cr:
                    results.append(DiaryEntry(
                        id=cr.id,
                        date=cr.created_at.strftime("%Y-%m-%d"),
                        type="cook",
                        title=cr.dish_name,
                        rating=cr.rating or 2,
                        mood=cr.mood,
                        cost=float(cr.estimated_cost or 0),
                    ))

    if takeout_ids:
        takeout_map = {
            tr.id: tr
            for tr in db.query(TakeoutRecord).filter(TakeoutRecord.id.in_(takeout_ids)).all()
        }
        for r in page_rows:
            if r.rtype == "order":
                tr = takeout_map.get(r.rid)
                if tr:
                    results.append(DiaryEntry(
                        id=tr.id,
                        date=tr.created_at.strftime("%Y-%m-%d"),
                        type="order",
                        title=tr.final_choice,
                        rating=satisfaction_map.get(tr.satisfaction, 2),
                        mood=tr.mood,
                        cost=0.0,
                    ))

    # 按 page_rows 的顺序排列（已是 desc）
    order_map = {r.rid: i for i, r in enumerate(page_rows)}
    results.sort(key=lambda x: order_map.get(x.id, 999))
    return paged([x.model_dump() for x in results], page, page_size, total)


# ============================================================
# User Profile
# ============================================================
def update_user_activity(user_id: str, db: Session):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return
    today = date.today()
    if user.last_active_at:
        last_date = user.last_active_at.date()
        if last_date == today:
            pass
        elif last_date == today - timedelta(days=1):
            user.streak_days += 1
        else:
            user.streak_days = 1
    else:
        user.streak_days = 1
    user.last_active_at = datetime.now()


@app.get("/api/user/{user_id}")
def get_user_profile(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(user_id, current_user)
    user = current_user
    return ok({
        "user_id": user.id,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
        "total_cook_count": user.total_cook_count,
        "total_takeout_count": user.total_takeout_count,
        "streak_days": user.streak_days,
        "last_active_at": user.last_active_at.strftime("%Y-%m-%d %H:%M") if user.last_active_at else None,
        "created_at": user.created_at.strftime("%Y-%m-%d"),
    })


# ============================================================
# Health check / Root（公开，可选登录）
# ============================================================
@app.get("/api/health")
def health_check():
    return ok({
        "status": "ok",
        "version": "2.1.0",
        "service": "FoodTime 食光 API",
        "env": settings.APP_ENV,
        "database": settings.DB_NAME,
        "debug": settings.DEBUG,
    })


@app.get("/")
def root():
    return ok({
        "service": "FoodTime 食光 API",
        "version": "2.1.0",
        "env": settings.APP_ENV,
        "database": settings.DB_NAME,
        "debug": settings.DEBUG,
        "docs": "/docs" if settings.DEBUG else None,
        "auth": {
            "register": "POST /api/auth/register",
            "login": "POST /api/auth/login",
            "refresh": "POST /api/auth/refresh",
            "me": "GET /api/auth/me  (Bearer token required)",
        },
        "endpoints": {
            "onboarding": "POST /api/onboarding",
            "preferences": "GET /api/preferences/{user_id}",
            "ingredients": "GET/POST/PUT/DELETE /api/ingredients  (分页)",
            "recipes": "POST /api/recipes/recommend  (LLM 配额: {}/day)".format(settings.LLM_RECIPES_QUOTA),
            "shopping": "GET/POST/PUT /api/shopping  (分页)",
            "fortune": "GET /api/fortune/today/{{user_id}}  (LLM 配额: {}/day)".format(settings.LLM_FORTUNE_QUOTA),
            "chat": "POST /api/chat/session & /api/chat/turn  (LLM 配额: {}/day)".format(settings.LLM_CHAT_QUOTA),
            "diary_stats": "GET /api/diary/stats/{user_id}",
            "diary_heatmap": "GET /api/diary/heatmap/{user_id}",
            "diary_list": "GET /api/diary/list/{user_id}  (分页)",
            "cook_record": "POST /api/diary/cook",
            "takeout_record": "POST /api/diary/takeout",
            "feedback": "POST /api/feedback",
        },
    })


# 向后兼容：原有的 X-App-Env / X-DB-Name 头（在全局中间件之后）
@app.middleware("http")
async def env_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-App-Env"] = settings.APP_ENV
    response.headers["X-DB-Name"] = settings.DB_NAME
    return response


# ===== 真实前端页面挂载（单页应用 SPA）=====
# 目录位置：项目根/frontend（即 backend 目录的兄弟目录）
# 访问入口：http://127.0.0.1:8000/app/   （刷新不 404，统一落到 index.html）
# 与 API(/api/*) / Swagger(/docs) 完全隔离，互不抢占
import os as _os
from starlette.responses import FileResponse, PlainTextResponse

_FRONTEND_DIR = _os.path.normpath(
    _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), _os.pardir, "frontend")
)
# 优先使用 Vite 构建产物 (dist/)；dev 未构建时回退 legacy/index.html
_FRONTEND_DIST = _os.path.join(_FRONTEND_DIR, "dist")
_FRONTEND_DIST_INDEX = _os.path.join(_FRONTEND_DIST, "index.html")
_LEGACY_INDEX = _os.path.join(_FRONTEND_DIR, "legacy", "index.html")
_serve_dir = _FRONTEND_DIST if _os.path.isfile(_FRONTEND_DIST_INDEX) else _FRONTEND_DIR
_serve_index = _FRONTEND_DIST_INDEX if _os.path.isfile(_FRONTEND_DIST_INDEX) else _LEGACY_INDEX
if _os.path.isdir(_FRONTEND_DIR) and _os.path.isfile(_serve_index):
    class _SPAApp:
        """
        极简可靠的 SPA 静态服务（比 StaticFiles(html=True) 更稳）：
          - 路径为空 -> index.html
          - 路径对应真实文件 -> FileResponse 直接返回
          - 否则 (SPA 路由, 例如 /app/cook, /app/diary/detail/123) -> index.html
          - 自动防 ../../../ 目录穿越
        """
        __slots__ = ("root", "index")
        def __init__(self, root: str, index: str):
            self.root = _os.path.abspath(root) + _os.sep
            self.index = index
        async def __call__(self, scope, receive, send):
            path = scope["path"].lstrip("/")
            if not path:
                return await self._file(self.index)(scope, receive, send)
            target = _os.path.abspath(_os.path.join(self.root[:-1], path))
            if not target.startswith(self.root):
                return await PlainTextResponse("Forbidden", status_code=403)(scope, receive, send)
            if _os.path.isfile(target):
                return await self._file(target)(scope, receive, send)
            # SPA Fallback: 任何不存在的子路径 → index.html（Vue router 接管）
            return await self._file(self.index)(scope, receive, send)
        @staticmethod
        def _file(p): return FileResponse(p)
    app.mount("/app", _SPAApp(_serve_dir, _serve_index), name="frontend_spa")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
    )
