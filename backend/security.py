"""
JWT 认证与权限模块 — P0-1 / P0-6 安全加固
提供: 密码哈希、JWT 签发/验证、Bearer Token 依赖、资源归属校验

P0-6 修复：Refresh token 黑名单（字段级）
    * User.token_valid_since = 最早接受的 iat 时间戳
    * 改密 / 强制退出 / 挂失时把 token_valid_since 更新到当前时间
    * 所有验证路径：iat >= token_valid_since 才放行；否则 401（旧 token 立即作废）
"""
from __future__ import annotations

import base64
import hashlib
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import User


# ---------------------------
# 密码哈希（原生 bcrypt）
# - bcrypt 密码最长 72 字节；先 sha256 预处理 → 32 字节 base64 → 44 字节
# - 彻底规避长密码截断，且保持 bcrypt 单向不可逆
# ---------------------------
_BCRYPT_ROUNDS = 12


def _prehash(raw: str) -> bytes:
    return base64.b64encode(hashlib.sha256(raw.encode("utf-8")).digest())


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(_prehash(raw), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash(raw), hashed.encode("utf-8"))
    except Exception:
        return False


# ---------------------------
# JWT
# ---------------------------
# 生产环境必须通过 SECRET_KEY 环境变量覆盖，此处是开发默认值
JWT_SECRET = getattr(settings, "SECRET_KEY", "foodtime-dev-insecure-change-me-please-2026")
JWT_ALG = "HS256"
ACCESS_TOKEN_TTL = timedelta(days=7)      # 访问令牌 7 天
REFRESH_TOKEN_TTL = timedelta(days=30)    # 刷新令牌 30 天


class TokenType:
    ACCESS = "access"
    REFRESH = "refresh"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _sign(payload: dict, ttl: timedelta) -> str:
    now = _utcnow()
    iat_stamp = now.replace(tzinfo=timezone.utc).timestamp()
    base = {
        "iat": now,
        "iat_ts": int(iat_stamp),        # 兼容字段：秒级时间戳（P0-6 黑名单比对用）
        "exp": now + ttl,
        "jti": uuid.uuid4().hex,
    }
    base.update(payload)
    return jwt.encode(base, JWT_SECRET, algorithm=JWT_ALG)


def issue_tokens(user_id: str) -> dict:
    access = _sign(
        {"sub": user_id, "type": TokenType.ACCESS},
        ACCESS_TOKEN_TTL,
    )
    refresh = _sign(
        {"sub": user_id, "type": TokenType.REFRESH},
        REFRESH_TOKEN_TTL,
    )
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": int(ACCESS_TOKEN_TTL.total_seconds()),
    }


def _iat_from_payload(payload: dict) -> float:
    """从 payload 解析 iat 的浮点秒数：兼容 datetime 和 int/float"""
    raw = payload.get("iat_ts") or payload.get("iat")
    if raw is None:
        return 0.0
    if isinstance(raw, datetime):
        return raw.replace(tzinfo=timezone.utc).timestamp()
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _enforce_token_valid_since(user: User, payload: dict) -> None:
    """P0-6 黑名单强制校验：iat >= token_valid_since 才放行"""
    valid_since = getattr(user, "token_valid_since", None) or 0.0
    if valid_since <= 0:
        return
    if _iat_from_payload(payload) < valid_since:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="当前登录态已因改密/挂失失效，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )


def decode_token(token: str, expected_type: Optional[str] = None) -> dict:
    """验证 JWT 并返回 payload，失败抛 HTTPException（不做 token_valid_since 校验，仅签名+类型）"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌签名",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if payload.get("exp", 0) < int(time.time()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if expected_type and payload.get("type") != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"令牌类型错误，期望 {expected_type}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌缺少用户主体",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


# ---------------------------
# FastAPI 依赖
# ---------------------------
_scheme = HTTPBearer(auto_error=False)


def _resolve_user_id(
    credentials: Optional[HTTPAuthorizationCredentials],
    db: Session,
) -> User:
    """无 token / token 无效 / 被 token_valid_since 拉黑 都会抛 401"""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials, expected_type=TokenType.ACCESS)
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已注销",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"账号已被 {user.status}，请联系管理员",
        )
    # P0-6: 黑名单（改密/挂失后立即失效旧 access token）
    _enforce_token_valid_since(user, payload)
    return user


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    获取当前已登录用户对象。
    作为所有需要登录接口的 Depends，天然拦截水平越权（资源按 user_id 归属）。
    """
    # 允许 query 参数携带 token（用于 WebSocket / 文件下载等场景）
    if not credentials:
        q_token = request.query_params.get("access_token")
        if q_token:
            credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=q_token)
    return _resolve_user_id(credentials, db)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """可选登录：未登录返回 None（如健康检查、公开信息）"""
    if not credentials:
        return None
    try:
        return _resolve_user_id(credentials, db)
    except HTTPException:
        return None


def require_owner(resource_user_id: str, current_user: User) -> None:
    """
    资源归属校验。确保当前用户只能操作自己的资源。
    所有按 user_id 查询的接口都必须调用。
    """
    if resource_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权操作其他用户的资源",
        )
