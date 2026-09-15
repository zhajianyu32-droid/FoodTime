"""
P0-2 全局异常处理 + 业务错误码
- 所有异常统一映射为 ApiResponse 格式，绝不泄露堆栈给前端
- 业务错误码约定：
    0        成功
    1xxx    参数 / 校验错误
    2xxx    认证 / 权限错误
    3xxx    资源不存在 / 状态错误
    4xxx    第三方 / LLM / 上游服务错误
    5xxx    服务端内部错误
"""
from __future__ import annotations

import time
import traceback
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from jose import JWTError
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError, DBAPIError, IntegrityError

from logging_config import get_logger, get_trace_id, new_trace_id
from schemas import ApiResponse

logger = get_logger("foodtime.errors")


# ---------------- 业务错误 ----------------
class BizError(Exception):
    """业务层抛此异常，code/message 会原样返回给前端"""
    def __init__(self, code: int, message: str, http_status: int = 200, data: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.data = data


# 常用错误码（可按需扩展）
ERR = {
    "PARAM_INVALID": (1001, "请求参数校验失败"),
    "USER_NOT_FOUND": (2001, "用户不存在"),
    "AUTH_REQUIRED": (2002, "请先登录"),
    "AUTH_INVALID": (2003, "用户名或密码错误"),
    "AUTH_EXPIRED": (2004, "登录已过期，请重新登录"),
    "AUTH_FORBIDDEN": (2005, "无权操作该资源"),
    "USER_DUPLICATE": (2006, "用户名或手机号已被注册"),
    "USERNAME_DUPLICATE": (2006, "用户名已被注册，请换一个"),
    "PHONE_DUPLICATE": (2006, "该手机号已被注册，可直接登录"),
    "USER_BANNED": (2007, "该账户已被封禁"),
    "PASSWORD_WEAK": (2008, "新密码强度不足"),
    "METHOD_NOT_ALLOWED": (1002, "请求方法不允许，请使用正确的 HTTP 方法"),
    "INGREDIENT_NOT_FOUND": (3001, "食材不存在"),
    "SHOPPING_NOT_FOUND": (3002, "购物项不存在"),
    "SESSION_NOT_FOUND": (3003, "对话会话不存在或已结束"),
    "QUOTA_EXCEEDED": (3004, "今日配额已用完，请明天再来"),
    "RATE_LIMIT": (3005, "请求过于频繁，喝口水休息一下吧"),
    "LLM_UNAVAILABLE": (4001, "AI 服务暂时不可用，请稍后再试"),
    "LLM_TIMEOUT": (4002, "AI 思考超时了，重试一下"),
    "DB_ERROR": (5001, "数据库服务异常"),
    "INTERNAL": (5000, "服务内部错误，请稍后重试"),
}


def _resp(code: int, message: str, data: Any = None, trace_id: str = "") -> dict:
    return ApiResponse(code=code, message=message, data=data, trace_id=trace_id or get_trace_id()).model_dump()


# ---------------- 统一注册到 FastAPI ----------------
def register_exception_handlers(app: FastAPI) -> None:
    @app.middleware("http")
    async def _trace_and_time(request: Request, call_next):
        # 1) Trace ID：优先接上游传入的，否则新建
        tid = request.headers.get("X-Trace-Id") or request.headers.get("X-Request-Id")
        if tid:
            from logging_config import set_trace_id
            set_trace_id(tid[:32])
        else:
            new_trace_id()

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            # 未被 handler 捕获的漏网之鱼
            latency_ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "Unhandled middleware exception: %s", exc,
                exc_info=True,
                endpoint=request.url.path, latency_ms=latency_ms,
                status_code=500,
            )
            payload = _resp(*ERR["INTERNAL"], trace_id=get_trace_id())
            payload["message"] = "服务繁忙，请稍后再试"
            return JSONResponse(status_code=500, content=payload)

        latency_ms = int((time.perf_counter() - start) * 1000)
        # 响应头带 Trace ID，便于前端联调
        response.headers["X-Trace-Id"] = get_trace_id()
        response.headers["X-Response-Time-Ms"] = str(latency_ms)
        # 访问日志（采样 WARNING 以上或慢请求）
        if response.status_code >= 400 or latency_ms > 1000:
            level = logger.warning if response.status_code < 500 else logger.error
            level(
                "Access %s %s -> %s (%sms)",
                request.method, request.url.path,
                response.status_code, latency_ms,
                endpoint=request.url.path, status_code=response.status_code,
                latency_ms=latency_ms,
            )
        else:
            logger.info(
                "Access %s %s -> %s (%sms)",
                request.method, request.url.path,
                response.status_code, latency_ms,
                endpoint=request.url.path, status_code=response.status_code,
                latency_ms=latency_ms,
            )
        return response

    # 业务错误
    @app.exception_handler(BizError)
    async def _biz(request: Request, exc: BizError):
        logger.warning(
            "BizError code=%s msg=%s path=%s",
            exc.code, exc.message, request.url.path,
            endpoint=request.url.path,
        )
        return JSONResponse(
            status_code=exc.http_status,
            content=_resp(exc.code, exc.message, data=exc.data),
        )

    # 422 参数校验错误（FastAPI/Pydantic）
    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        details = []
        for e in exc.errors():
            loc = ".".join(str(x) for x in e.get("loc", []))
            raw_msg = e.get("msg", "")
            # 去掉 pydantic 前缀："Value error, " / "String should have at least 6 characters" 之类保留用户友好部分
            clean_msg = raw_msg.replace("Value error, ", "").replace("Value error，", "")
            if clean_msg.startswith("Input should be"):
                # 例：Input should be less than or equal to 100 → 去掉前缀使其更友好
                pass
            details.append(f"[{loc}] {clean_msg}")
        msg = ERR["PARAM_INVALID"][1] + ": " + "; ".join(details[:3])
        logger.info(
            "Validation failed on %s: %s", request.url.path, details,
            endpoint=request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_resp(ERR["PARAM_INVALID"][0], msg, data={"errors": details}),
        )

    @app.exception_handler(ValidationError)
    async def _pydantic(request: Request, exc: ValidationError):
        details = []
        for e in exc.errors():
            raw_msg = e.get("msg", "")
            clean_msg = raw_msg.replace("Value error, ", "").replace("Value error，", "")
            details.append(f"{e.get('loc')}: {clean_msg}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_resp(ERR["PARAM_INVALID"][0], "; ".join(details[:3])),
        )

    # SQLAlchemy 异常（绝不暴露 SQL 语句）
    def _classify_sa_error(exc: SQLAlchemyError):
        """把数据库异常细化成业务友好的错误码和消息，返回 (code, msg, http_status)"""
        # MySQL 1062 = 唯一键冲突 (Duplicate entry)
        if isinstance(exc, IntegrityError):
            orig = getattr(exc, "orig", None)
            err_args = getattr(orig, "args", None) or ()
            err_code = None
            err_text = ""
            for a in err_args:
                if isinstance(a, int):
                    err_code = a
                elif isinstance(a, str):
                    err_text = a
            # 兼容 exc.args / (code, msg) 形式
            if err_code is None and isinstance(getattr(orig, "args", None), (list, tuple)) and len(orig.args) >= 2 and isinstance(orig.args[0], int):
                err_code = orig.args[0]; err_text = str(orig.args[1])
            if err_code == 1062 or (isinstance(err_text, str) and "Duplicate entry" in err_text):
                # 从错误信息推断字段："for key 'users.phone'" / "for key 'users.username'" / "for key 'phone'" / ...
                low = (err_text or "").lower()
                # 配额表/运势表/缓存表的唯一键冲突属于正常 upsert 竞争，不应暴露给用户
                if "quota_usage" in low or "uq_quota" in low:
                    return None, None, None  # 让调用方自己处理
                if "daily_fortunes" in low or "uq_daily_fortunes" in low:
                    return None, None, None
                if "recipe_cache" in low or "uq_recipe_cache" in low:
                    return None, None, None
                if ".username" in low or "'username" in low or low.endswith("username'"):
                    code, msg = ERR["USERNAME_DUPLICATE"]
                elif ".phone" in low or "'phone" in low or low.endswith("phone'"):
                    code, msg = ERR["PHONE_DUPLICATE"]
                else:
                    code, msg = ERR["USER_DUPLICATE"]
                return code, msg, 200  # 业务冲突用 200 避免前端显示 HTTP 错误
        # 其他数据库异常保持 5001 但仍由全局处理打日志
        return None, None, None

    @app.exception_handler(IntegrityError)
    async def _sa_integrity(request: Request, exc: IntegrityError):
        logger.error(
            "DB IntegrityError on %s: %s", request.url.path, exc,
            exc_info=True, endpoint=request.url.path,
        )
        code, msg, http_status = _classify_sa_error(exc)
        if code is not None:
            return JSONResponse(
                status_code=http_status,
                content=_resp(code, msg),
            )
        # 兜底分类失败
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_resp(*ERR["DB_ERROR"]),
        )

    @app.exception_handler(SQLAlchemyError)
    async def _sa(request: Request, exc: SQLAlchemyError):
        # IntegrityError 已被上面专门捕获，这里只处理其他 SQLAlchemy 异常
        if isinstance(exc, IntegrityError):
            return await _sa_integrity(request, exc)
        logger.error(
            "DB Error on %s: %s", request.url.path, exc,
            exc_info=True, endpoint=request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_resp(*ERR["DB_ERROR"]),
        )

    @app.exception_handler(JWTError)
    async def _jwt(request: Request, exc: JWTError):
        logger.info("JWT error on %s: %s", request.url.path, exc, endpoint=request.url.path)
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=_resp(*ERR["AUTH_INVALID"]),
        )

    # HTTPException（FastAPI 原生 + Starlette 路由层抛出的 405 等）
    from fastapi import HTTPException as FastHTTPException
    from starlette.exceptions import HTTPException as StarletteHTTPException

    async def _handle_http_exception(request: Request, exc):
        mapping = {
            401: ERR["AUTH_REQUIRED"],
            403: ERR["AUTH_FORBIDDEN"],
            404: (3000, exc.detail if isinstance(exc.detail, str) else "资源不存在"),
            405: ERR["METHOD_NOT_ALLOWED"],
            429: ERR["RATE_LIMIT"],
        }
        code, msg = mapping.get(exc.status_code, ERR["INTERNAL"])
        if isinstance(exc.detail, str) and exc.status_code not in (405, 429):  # 405/429 用统一友好文案
            msg = exc.detail
        logger.info(
            "HTTP %s on %s: %s", exc.status_code, request.url.path, msg,
            endpoint=request.url.path, status_code=exc.status_code,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_resp(code, msg, trace_id=get_trace_id()),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(FastHTTPException)
    async def _fastapi_http(request: Request, exc: FastHTTPException):
        return await _handle_http_exception(request, exc)

    @app.exception_handler(StarletteHTTPException)
    async def _starlette_http(request: Request, exc: StarletteHTTPException):
        # 路由层找不到匹配方法会抛 StarletteHTTPException (status=405)
        return await _handle_http_exception(request, exc)

    # 兜底
    @app.exception_handler(Exception)
    async def _catch_all(request: Request, exc: Exception):
        logger.exception(
            "Unhandled exception on %s: %s", request.url.path, exc,
            endpoint=request.url.path,
        )
        payload = _resp(*ERR["INTERNAL"])
        return JSONResponse(status_code=500, content=payload)


# 避免循环导入
from config import settings
