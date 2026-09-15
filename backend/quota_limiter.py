"""
P0-3 修复: 限流 + 用户配额（并发安全版）
- per-IP / per-user 全局速率限制（slowapi）
- 每用户每天 LLM 调用配额（菜谱推荐/运势/外卖对话），持久化到数据库
"""
from __future__ import annotations

import asyncio
from datetime import date
from typing import Callable, Awaitable

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from config import settings
from errors import BizError, ERR, _resp
from logging_config import get_logger
from models import User, QuotaUsage

logger = get_logger("foodtime.quota")


# ---------------- 1) slowapi 速率限制 ----------------
limiter = Limiter(
    key_func=get_remote_address,
    enabled=True,   # 始终启用，DEBUG 下也防止暴力枚举
    storage_uri="memory://",
)


def _custom_rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """将 slowapi 的 RateLimitExceeded 转为项目标准的 ApiResponse 格式。

    默认 slowapi handler 返回 {"error": "..."}（无 code 字段），
    前端 api() 解包逻辑会退化成 `msg = undefined || 'HTTP 429'`，
    用户看到的是无意义的 'HTTP 429'。
    """
    detail = str(exc.detail) if hasattr(exc, "detail") and exc.detail else ""
    # detail 示例："Rate limit exceeded: 5 per 1 minute"
    msg = ERR["RATE_LIMIT"][1]
    if detail:
        msg = f"{msg}（{detail}）"
    code, _ = ERR["RATE_LIMIT"]
    logger.warning(
        "Rate limit exceeded: path=%s detail=%s",
        request.url.path, detail,
        endpoint=request.url.path,
    )
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content=_resp(code, msg),
    )


def attach_limiter(app):
    """在 main.py 的 app 创建后调用"""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _custom_rate_limit_exceeded_handler)


def user_key_from_request(request) -> str:
    """slowapi 自定义 key：优先 user_id，否则 IP"""
    user = getattr(request.state, "current_user", None)
    if user and hasattr(user, "id"):
        return f"u:{user.id}"
    return f"ip:{get_remote_address(request)}"


# ---------------- 2) 每日 LLM 配额（并发安全 + DB 持久化）----------------
class QuotaKind:
    RECIPE = "recipe"
    FORTUNE = "fortune"
    CHAT = "chat"


_QUOTA_LIMITS = {
    QuotaKind.RECIPE: settings.LLM_RECIPES_QUOTA,
    QuotaKind.FORTUNE: settings.LLM_FORTUNE_QUOTA,
    QuotaKind.CHAT: settings.LLM_CHAT_QUOTA,
}

# 按 (user_id, kind) 粒度加锁；避免全局锁造成全用户串行
_lock_pool: dict[tuple[str, str], asyncio.Lock] = {}
_lock_pool_guard = asyncio.Lock()


async def _get_lock(user_id: str, kind: str) -> asyncio.Lock:
    async with _lock_pool_guard:
        key = (user_id, kind)
        lock = _lock_pool.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _lock_pool[key] = lock
        return lock


def _today() -> str:
    return date.today().isoformat()


def _get_db_session() -> Session:
    """获取短生命周期 DB session（不依赖 FastAPI 依赖注入）"""
    from database import SessionLocal
    return SessionLocal()


def _load_used_from_db(user_id: str, kind: str) -> int:
    """从数据库加载今日已用配额"""
    today = date.today()
    db = _get_db_session()
    try:
        row = db.query(QuotaUsage).filter(
            QuotaUsage.user_id == user_id,
            QuotaUsage.date == today,
            QuotaUsage.kind == kind,
        ).first()
        return row.used if row else 0
    finally:
        db.close()


def _save_used_to_db(user_id: str, kind: str, used: int) -> None:
    """将配额计数写入数据库（upsert）"""
    today = date.today()
    db = _get_db_session()
    try:
        row = db.query(QuotaUsage).filter(
            QuotaUsage.user_id == user_id,
            QuotaUsage.date == today,
            QuotaUsage.kind == kind,
        ).first()
        if row:
            row.used = used
        else:
            row = QuotaUsage(user_id=user_id, date=today, kind=kind, used=used)
            db.add(row)
        db.commit()
    except Exception:
        db.rollback()
        logger.error("Failed to persist quota: user=%s kind=%s used=%s", user_id, kind, used)
    finally:
        db.close()


async def consume_quota(user_id: str, kind: str) -> int:
    """
    消耗一次配额（异步并发安全 + DB 持久化），返回剩余次数。
    超配额抛 BizError(QUOTA_EXCEEDED)。
    """
    lock = await _get_lock(user_id, kind)
    async with lock:
        limit = _QUOTA_LIMITS.get(kind, 9999)
        # 从 DB 加载当前已用（重启后仍准确）
        used = _load_used_from_db(user_id, kind) + 1
        if used > limit:
            logger.warning(
                "Quota exceeded user=%s kind=%s used=%s limit=%s",
                user_id, kind, limit, limit,
            )
            raise BizError(*ERR["QUOTA_EXCEEDED"])
        _save_used_to_db(user_id, kind, used)
        remaining = limit - used
        return remaining


def consume_quota_sync(user_id: str, kind: str) -> int:
    """
    同步兼容入口：直接走 DB 读写（不再通过 asyncio 调度，避免事件循环死锁）。
    """
    limit = _QUOTA_LIMITS.get(kind, 9999)
    used = _load_used_from_db(user_id, kind) + 1
    if used > limit:
        raise BizError(*ERR["QUOTA_EXCEEDED"])
    _save_used_to_db(user_id, kind, used)
    return limit - used


def get_quota_info(user_id: str) -> dict:
    """返回用户今日配额使用情况（个人中心展示）"""
    result = {}
    for kind, limit in _QUOTA_LIMITS.items():
        used = _load_used_from_db(user_id, kind)
        result[kind] = {"limit": limit, "used": used, "remaining": max(0, limit - used)}
    return result


def cleanup_old_days(keep_days: int = 3) -> None:
    """定期清理超过 N 天的配额记录"""
    import datetime as dt
    cutoff = date.today() - dt.timedelta(days=keep_days)
    db = _get_db_session()
    try:
        deleted = db.query(QuotaUsage).filter(QuotaUsage.date < cutoff).delete()
        db.commit()
        if deleted:
            logger.info("Quota cleanup: removed %s old records", deleted)
    except Exception:
        db.rollback()
    finally:
        db.close()
    # 清洗锁池
    if len(_lock_pool) > 10_000:
        logger.info("Quota lock_pool size=%s > 10k, resetting.", len(_lock_pool))
        _lock_pool.clear()
