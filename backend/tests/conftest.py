"""
conftest.py: 确保 tests/ 中 import backend 顶层模块（config/models/services/...）能找到。
运行时请在 backend/ 目录下执行 pytest。
"""
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# 测试强制使用 SQLite 内存库，避免污染真实数据库
os.environ.setdefault("DB_TYPE", "sqlite")
os.environ.setdefault("DB_NAME", ":memory:")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("SECRET_KEY", "foodtime-test-key-for-jwt-signing-only")
