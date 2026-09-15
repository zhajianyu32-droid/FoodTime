"""
结构化 JSON 日志 + Trace ID 上下文（P1-1）
- 控制台：彩色人类可读
- 文件：app.log / errors.log，JSON Lines 格式，便于 ELK/Filebeat 采集
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
import threading
import uuid
from contextvars import ContextVar
from datetime import datetime
from typing import Optional

from config import settings

# ---- 全局 Trace ID ----
_TRACE_ID: ContextVar[str] = ContextVar("trace_id", default="")


def new_trace_id() -> str:
    tid = uuid.uuid4().hex[:16]
    _TRACE_ID.set(tid)
    return tid


def get_trace_id() -> str:
    return _TRACE_ID.get() or new_trace_id()


def set_trace_id(tid: str) -> None:
    _TRACE_ID.set(tid)


# ---- JSON 格式化 ----
_LEVEL_EMOJI = {
    "DEBUG": "·",
    "INFO": "ℹ",
    "WARNING": "⚠",
    "ERROR": "✖",
    "CRITICAL": "☠",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: PLR6301
        payload = {
            "ts": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "trace_id": get_trace_id(),
            "module": record.module,
            "line": record.lineno,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # 透传自定义字段
        for k in ("user_id", "endpoint", "latency_ms", "status_code", "llm_model", "tokens"):
            if hasattr(record, k):
                payload[k] = getattr(record, k)
        return json.dumps(payload, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: PLR6301
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        emoji = _LEVEL_EMOJI.get(record.levelname, "?")
        tid = get_trace_id()
        prefix = f"{ts} {emoji}{record.levelname:<7} [{tid[:8]}]"
        msg = f"{record.name}: {record.getMessage()}"
        line = f"{prefix} {msg}"
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


# ---- 初始化 ----
_init_lock = threading.Lock()
_initialized = False


def setup_logging() -> logging.Logger:
    global _initialized
    with _init_lock:
        if _initialized:
            return logging.getLogger("foodtime")
        _initialized = True

    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    # 清除默认 handler，避免重复
    for h in list(root.handlers):
        root.removeHandler(h)

    # 1. 控制台
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(ConsoleFormatter())
    root.addHandler(console)

    # 2. 文件（JSON Lines）
    log_dir = settings.LOG_DIR
    try:
        os.makedirs(log_dir, exist_ok=True)
    except OSError:
        log_dir = "."

    app_file = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "app.log"),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,
        encoding="utf-8",
    )
    app_file.setFormatter(JsonFormatter())
    root.addHandler(app_file)

    # 3. 错误单独归档
    err_file = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "errors.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    err_file.setLevel(logging.WARNING)
    err_file.setFormatter(JsonFormatter())
    root.addHandler(err_file)

    # 屏蔽第三方噪声
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.DEBUG else logging.WARNING
    )
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    logger = logging.getLogger("foodtime")
    logger.info(
        "Logging initialized: level=%s, dir=%s, env=%s",
        settings.LOG_LEVEL, log_dir, settings.APP_ENV,
    )
    return logger


# 便捷包装（带 extra 透传字段，同时兼容标准 logging 的 *args/%s 格式化 + exc_info/stack_info/stacklevel）
class ExtraLogger:
    _NATIVE_KWARGS = {"exc_info", "stack_info", "stacklevel"}

    def __init__(self, name: str = "foodtime"):
        self._lg = logging.getLogger(name)

    def _split_kwargs(self, kw: dict) -> tuple[dict, dict]:
        native: dict = {}
        extra_fields: dict = {}
        for k, v in kw.items():
            if k in self._NATIVE_KWARGS:
                native[k] = v
            else:
                extra_fields[k] = v
        if extra_fields:
            native["extra"] = extra_fields
        return native, extra_fields

    def debug(self, msg, *args, **kw):
        native, _ = self._split_kwargs(kw)
        self._lg.debug(msg, *args, **native)

    def info(self, msg, *args, **kw):
        native, _ = self._split_kwargs(kw)
        self._lg.info(msg, *args, **native)

    def warning(self, msg, *args, **kw):
        native, _ = self._split_kwargs(kw)
        self._lg.warning(msg, *args, **native)

    def error(self, msg, *args, **kw):
        native, _ = self._split_kwargs(kw)
        self._lg.error(msg, *args, **native)

    def critical(self, msg, *args, **kw):
        native, _ = self._split_kwargs(kw)
        self._lg.critical(msg, *args, **native)

    def exception(self, msg, *args, **kw):
        native, _ = self._split_kwargs(kw)
        self._lg.exception(msg, *args, **native)


def get_logger(name: str = "foodtime") -> ExtraLogger:
    setup_logging()
    return ExtraLogger(name)
