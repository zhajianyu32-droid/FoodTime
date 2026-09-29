"""
conftest.py: 确保 tests/ 中 import backend 顶层模块（config/models/services/...）能找到。
运行时请在 backend/ 目录下执行 pytest。
"""
import os
import sys

# 注意：conftest.py 位于 backend/tests/ 下，所以 backend/ 需要再往上取一层。
# 早先这里写的是 dirname(__file__)，插进 sys.path 的是 backend/tests，
# 于是从仓库根目录跑 `pytest backend/tests` 时报 No module named 'services'；
# 而在 backend/ 下跑又因为 pytest 会把 rootdir 加进路径而"碰巧"能用，两个 bug 互相掩护。
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(_TESTS_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# 测试强制使用 SQLite 内存库，避免污染真实数据库
os.environ.setdefault("DB_TYPE", "sqlite")
os.environ.setdefault("DB_NAME", ":memory:")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("SECRET_KEY", "foodtime-test-key-for-jwt-signing-only")
