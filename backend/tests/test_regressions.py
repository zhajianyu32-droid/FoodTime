"""
A+B 批次修复的回归守卫。

每条用例都锚定一次真实修复，退化时立刻失败：
  A1/A2  quota_limiter 的 slowapi 配置文件 + peek/refund 辅助函数
  A3     conftest 的 BACKEND_DIR（从仓库根跑 pytest 也能 import services）
  A4     pytest.ini 的 asyncio fixture loop scope
  A5     新业务码 3006（未完成会话超限）
  A6     docker-compose 挂载的 SQL 文件路径
  A7/A8  Dockerfile / compose / Start.txt 的 PYTHONUTF8
  A9     会被按 locale 解码的配置文件必须是纯 ASCII
  A10    前端读取菜谱缓存主键的字段名
  A12/A13 GBK 控制台日志降级、utcfromtimestamp 弃用
  B1     一餐三选一的缓存槽位（不再被 UNIQUE(prompt_hash) 压成 1 条）
  B2     schemas 的入参长度/条数/枚举上限与 DB 列宽一致
  B3     食材 location 落库 + 枚举校验 + 热力图在 SQLite 可用
  B4     点单配额预扣/失败回滚 + 未完成会话上限与僵尸自愈

运行:
  cd backend ; $env:PYTHONUTF8="1" ; python -m pytest -q
"""
from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os
import re
import sys
import warnings
from datetime import date, datetime, timedelta

import pytest

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(_TESTS_DIR)
ROOT = os.path.dirname(BACKEND)


# ============================================================
# 公共辅助
# ============================================================
def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def _db():
    """复用 database.py 的全局 engine（另建内存引擎会因 SingletonThreadPool
    每连接一个内存库而报 no such table）。"""
    from database import Base, SessionLocal, engine

    Base.metadata.create_all(bind=engine)
    return SessionLocal()


def _uid(name: str) -> str:
    """每个用例一个独立 user_id，避免配额/会话上限互相污染。"""
    return f"reg-{name}"


def _fake_user(uid: str):
    from models import User

    return User(id=uid, nickname="reg")


@pytest.fixture(autouse=True)
def _fresh_quota_locks():
    """配额模块级 asyncio.Lock 会绑死在第一个事件循环上；
    每个用例用 asyncio.run 起新循环，必须先丢弃旧锁，否则
    RuntimeError: ... is bound to a different event loop。"""
    import quota_limiter

    quota_limiter._lock_pool.clear()
    quota_limiter._lock_pool_guard = asyncio.Lock()
    yield


def _stub_llm(monkeypatch, payload=None, raises=None):
    """替换 llm_service.chat_completion 并记录调用次数（测试禁止真打上游）。"""
    from services.llm_service import llm_service

    calls: list[int] = []

    async def fake(messages, **kwargs):
        calls.append(1)
        if raises is not None:
            raise raises
        return payload

    monkeypatch.setattr(llm_service, "chat_completion", fake)
    return calls


_RECIPE_PAYLOAD = {
    "content": json.dumps({"recipes": [
        {"name": f"菜{i}", "difficulty": i, "cooking_time": f"{i}0min",
         "estimated_cost": f"{i}0", "reason": "r", "steps": ["下锅"],
         "matched_ingredients": [], "missing_ingredients": []}
        for i in (1, 2, 3)
    ]}, ensure_ascii=False),
    "model": "stub-model",
    "total_tokens": 7,
}

_TURN5_PAYLOAD = {
    "content": json.dumps(
        {"recommend": "川味牛肉面", "reason": "暖食", "alternatives": ["酸辣粉"]},
        ensure_ascii=False,
    ),
    "model": "stub-model",
    "total_tokens": 5,
}


def _play_to_round5(uid: str, db) -> tuple[str, str]:
    """建会话并答完前 4 轮（这 4 轮不碰 LLM），返回 (session_id, 第5轮答案)。"""
    from schemas import ChatSessionCreate, ChatTurnRequest
    from services.chat_service import chat_service

    resp = chat_service.create_session(ChatSessionCreate(user_id=uid, mood=""), db)
    sid = resp.session_id
    for _ in range(4):
        resp = asyncio.run(chat_service.process_turn(
            ChatTurnRequest(session_id=sid, answer=resp.options[0]), db))
    assert resp.current_round == 5, "前 4 轮答完应停在第 5 轮"
    return sid, resp.options[0]


# ============================================================
# A 组：P0 启动 / 编码
# ============================================================
def test_a01_import_main_succeeds():
    """P0-1 守门：import main 不再在导入期崩溃。"""
    assert hasattr(importlib.import_module("main"), "app")


def test_a02_startup_configs_are_pure_ascii():
    """A9/A2 守门：会被按 OS locale 解码的文件不能含非 ASCII 字节。

    uvicorn 的 --env-format、starlette 的 Config、limits 的 dotenv 读取
    都用 open() 不带 encoding，中文 Windows 上是 cp936(GBK)：
    UTF-8 中文注释会直接 UnicodeDecodeError，应用根本起不来。
    """
    targets = [
        os.path.join(BACKEND, ".env"),
        os.path.join(BACKEND, ".env.local"),
        os.path.join(BACKEND, ".env.example"),
        os.path.join(BACKEND, "ratelimit.env"),
    ]
    for path in targets:
        assert os.path.isfile(path), f"缺少配置文件: {path}"
        raw = open(path, "rb").read()
        bad = [i for i, b in enumerate(raw) if b > 0x7F]
        assert not bad, f"{os.path.basename(path)} 含 {len(bad)} 个非 ASCII 字节"

    # ASCII 化只动注释：键名必须还在，否则配置整体失效
    env = _read(os.path.join(BACKEND, ".env"))
    for key in ("APP_ENV", "DB_TYPE", "DB_HOST", "SECRET_KEY",
                "DEEPSEEK_API_KEY", "LLM_CHAT_QUOTA"):
        assert re.search(rf"^\s*{key}=", env, re.M), f".env 丢失键 {key}"


def test_a03_limiter_uses_dedicated_ascii_config():
    """A1/A2 守门：Limiter 指向 ratelimit.env，且该文件不改变任何限流行为。"""
    import quota_limiter
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    cfg = quota_limiter.SLOWAPI_CONFIG_FILE
    assert os.path.isabs(cfg)
    assert os.path.basename(cfg) == "ratelimit.env"
    assert os.path.isfile(cfg)
    active = [ln.strip() for ln in _read(cfg).splitlines()
              if ln.strip() and not ln.strip().startswith("#")]
    assert active == [], f"ratelimit.env 不该有生效配置（会改变限流行为）: {active}"

    # 构造本身不得抛异常 —— 这正是改前 import 阶段崩溃的位置
    Limiter(key_func=get_remote_address, config_filename=cfg)


def test_a04_console_logger_survives_gbk_stdout():
    """A12 守门：控制台格式化器不得产出当前 stdout 编码不了的字符。

    改前每条日志都触发 "--- Logging error --- UnicodeEncodeError"，
    把真正的错误信息整个淹掉。
    """
    import logging_config as lc

    assert isinstance(lc._CONSOLE_EMOJI_OK, bool)
    for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        assert level in lc._LEVEL_EMOJI_ASCII, f"缺少 {level} 的 ASCII 降级标记"

    fmt = lc.ConsoleFormatter()
    enc = getattr(sys.stdout, "encoding", None) or "ascii"
    for level in (logging.DEBUG, logging.INFO, logging.WARNING,
                  logging.ERROR, logging.CRITICAL):
        rec = logging.LogRecord(
            "foodtime.test", level, __file__, 1, "点单会话已过期 ✖", (), None
        )
        line = fmt.format(rec)
        line.encode(enc)  # 抛 UnicodeEncodeError 即为退化
        assert line, "日志行不能为空"


def test_a05_json_formatter_uses_aware_utc():
    """A13 守门：ts 仍是 Z 结尾的 UTC，且不再调用被弃用的 utcfromtimestamp。"""
    import logging_config as lc

    rec = logging.LogRecord("foodtime.test", logging.INFO, __file__, 1, "ok", (), None)
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        payload = json.loads(lc.JsonFormatter().format(rec))

    assert payload["ts"].endswith("Z"), payload["ts"]
    assert "+00:00" not in payload["ts"]
    assert payload["level"] == "INFO"
    assert payload["msg"] == "ok"
    src = _read(os.path.join(BACKEND, "logging_config.py"))
    assert "datetime.fromtimestamp(" in src
    # 唯一允许出现 utcfromtimestamp 的地方是解释性注释
    code = "\n".join(ln for ln in src.splitlines() if not ln.strip().startswith("#"))
    assert "utcfromtimestamp" not in code


def test_a06_pytest_ini_declares_fixture_loop_scope():
    """A4 守门：pytest.ini 声明 loop scope，asyncio 的默认 loop 告警不该回来。"""
    ini = _read(os.path.join(BACKEND, "pytest.ini"))
    assert "asyncio_default_fixture_loop_scope" in ini
    assert "asyncio_mode = auto" in ini


def test_a07_conftest_backend_dir_points_to_backend():
    """A3 守门：conftest 注入 sys.path 的是 backend/，不是 backend/tests/。"""
    import conftest

    assert conftest.BACKEND_DIR == BACKEND
    assert os.path.basename(conftest.BACKEND_DIR) == "backend"
    assert os.path.isfile(os.path.join(conftest.BACKEND_DIR, "config.py"))
    assert conftest.BACKEND_DIR in sys.path
    # 从仓库根跑 pytest 时也要能 import services（改前是 No module named 'services'）
    importlib.import_module("services.recipe_service")


def test_a08_quota_log_reports_used_and_limit():
    """A1 守门：超限日志的两个占位符不能填同一个值（排障时会误导成 limit 配错）。"""
    src = _read(os.path.join(BACKEND, "quota_limiter.py"))
    assert "used=%s limit=%s" in src
    assert "limit=%s limit=%s" not in src


def test_a09_new_biz_code_3006_is_registered():
    """A5 守门：会话上限错误码存在且不与既有码撞号。"""
    from errors import ERR

    code, msg = ERR["CHAT_TOO_MANY_SESSIONS"]
    assert code == 3006
    assert msg
    codes = [v[0] for v in ERR.values()]
    dup = {c for c in codes if codes.count(c) > 1}
    assert dup <= {2006}, f"业务码撞号: {sorted(dup)}"


def test_a10_compose_sql_mounts_exist():
    """A6 守门：compose 挂载的 SQL 必须真实存在，否则 mysql 容器初始化即失败。"""
    compose = _read(os.path.join(ROOT, "docker-compose.yml"))
    mounts = re.findall(r"-\s*\./(sql/[^:\s]+):", compose)
    assert mounts, "没解析到 SQL 挂载项，检查 compose 格式"
    for rel in mounts:
        host = os.path.join(ROOT, rel.replace("/", os.sep))
        assert os.path.isfile(host), f"compose 挂载源不存在: ./{rel}"


def test_a11_pythonutf8_declared_on_every_startup_path():
    """A7/A8 守门：三条启动路径都要显式声明 UTF-8。

    只能用环境变量：uvicorn --reload 会另起子进程，-X utf8 不会被继承。
    """
    assert "PYTHONUTF8=1" in _read(os.path.join(BACKEND, "Dockerfile"))
    assert 'PYTHONUTF8: "1"' in _read(os.path.join(ROOT, "docker-compose.yml"))

    start = _read(os.path.join(ROOT, "Start.txt"))
    assert re.search(r"(?m)^\s*(\$env:PYTHONUTF8|set PYTHONUTF8)", start), \
        "Start.txt 必须给出 PowerShell 与 cmd 两种环境变量写法"
    uvicorn_lines = [ln for ln in start.splitlines() if "uvicorn" in ln]
    assert uvicorn_lines, "Start.txt 丢了后端启动命令"
    for ln in uvicorn_lines:
        assert "-X utf8" not in ln, f"--reload 子进程不继承 -X utf8: {ln}"


def test_a12_frontend_reads_recipe_item_id_not_cache_id():
    """A10 守门：后端 RecipeItem 的主键叫 id，前端不能再读 cache_id。"""
    use_cook = os.path.join(ROOT, "frontend", "src", "composables", "useCook.js")
    cook_view = os.path.join(ROOT, "frontend", "src", "views", "CookView.vue")
    assert "cache_id" not in _read(use_cook)
    assert "cache_id" not in _read(cook_view)
    assert "ai_recommend_id: r.id" in _read(use_cook)
    assert ":key=\"r.id" in _read(cook_view)

    from schemas import RecipeItem

    assert "id" in RecipeItem.model_fields
    assert "cache_id" not in RecipeItem.model_fields


def test_a13_quota_helpers_exist_and_peek_is_readonly():
    """A1 守门：peek/refund 是 B4 的前提；peek 只读，不能顺手扣费。"""
    import inspect as _inspect

    import quota_limiter

    assert callable(quota_limiter.peek_quota)
    assert _inspect.iscoroutinefunction(quota_limiter.refund_quota)

    uid = _uid("peek")
    kind = quota_limiter.QuotaKind.CHAT
    limit = quota_limiter._QUOTA_LIMITS[kind]
    db = _db()
    try:
        assert quota_limiter.peek_quota(uid, kind) == limit
        assert quota_limiter._load_used_from_db(uid, kind) == 0, "peek 不应写库"
        quota_limiter._save_used_to_db(uid, kind, 2)
        assert quota_limiter.peek_quota(uid, kind) == limit - 2
    finally:
        db.close()

# ============================================================
# B 组：一餐三选一缓存槽位 / 入参上限与列宽 / 食材与热力图 / 点单配额
# ============================================================
def test_b01_recipe_cache_writes_three_distinct_slots(monkeypatch):
    """B1 守门：一次推荐出来的 3 条菜谱必须各自落库、各自可复用。

    退化点：recipe_cache.prompt_hash 上是全局 UNIQUE（不是 per-user）。
    三条菜谱若共用同一个 prompt_hash，_save_cache 的 existing 分支会让
    第 2、3 条直接复用第 1 条的行 —— 缓存里永远只有 1 条，
    "换一换/再做一次"拿不到多样性，前端三选一也退化成一条。
    """
    from schemas import RecipeRequest
    from services.recipe_service import RecipeService

    from models import RecipeCache

    calls = _stub_llm(monkeypatch, _RECIPE_PAYLOAD)
    db = _db()
    uid = _uid("recipe3")
    try:
        req = RecipeRequest(user_id=uid, ingredient_names=["鸡蛋", "番茄"])
        resp = asyncio.run(RecipeService().recommend(req, db))

        assert len(resp.recipes) == 3
        ids = [r.id for r in resp.recipes]
        assert all(ids), f"菜谱没拿到缓存主键: {ids}"
        assert len(set(ids)) == 3, f"三选一被压成同一行: {ids}"
        assert len(calls) == 1, "一次推荐应只打一次 LLM"

        rows = db.query(RecipeCache).filter(RecipeCache.user_id == uid).all()
        assert len(rows) == 3, f"缓存落库条数 {len(rows)} != 3"
        hashes = [r.prompt_hash for r in rows]
        assert len(set(hashes)) == 3, f"槽位缓存键重复: {hashes}"
        assert all(len(h) == 64 for h in hashes), "槽位键应是 64 位 sha256"
        # 对外契约不变：返回给客户端的仍是 base_hash（16 位 md5），不是槽位键
        assert resp.prompt_hash and resp.prompt_hash not in hashes

        # 第二次同样入参：必须命中 3 条缓存，且一条 LLM 都不打
        resp2 = asyncio.run(RecipeService().recommend(req, db))
        assert sorted(r.id for r in resp2.recipes) == sorted(ids)
        assert len(calls) == 1, "命中缓存后不应再打 LLM"
    finally:
        db.close()


# (schemas 模型, 字段, ORM 模型, 列名)：入参上限不得超过列宽
_SCHEMA_VS_DB_PAIRS = [
    ("IngredientCreate", "name", "Ingredient", "name"),
    ("IngredientCreate", "category", "Ingredient", "category"),
    ("IngredientCreate", "quantity", "Ingredient", "quantity"),
    ("IngredientCreate", "source", "Ingredient", "source"),
    ("IngredientCreate", "location", "Ingredient", "location"),
    ("IngredientUpdate", "name", "Ingredient", "name"),
    ("IngredientUpdate", "category", "Ingredient", "category"),
    ("IngredientUpdate", "quantity", "Ingredient", "quantity"),
    ("IngredientUpdate", "status", "Ingredient", "status"),
    ("IngredientUpdate", "location", "Ingredient", "location"),
    ("CookRecordCreate", "dish_name", "CookRecord", "dish_name"),
    ("CookRecordCreate", "mood", "CookRecord", "mood"),
    ("CookRecordCreate", "difficulty", "CookRecord", "difficulty"),
    ("CookRecordCreate", "note", "CookRecord", "note"),
    ("CookRecordCreate", "ai_recommend_id", "CookRecord", "ai_recommend_id"),
    ("TakeoutRecordCreate", "final_choice", "TakeoutRecord", "final_choice"),
    ("TakeoutRecordCreate", "mood", "TakeoutRecord", "mood"),
    ("TakeoutRecordCreate", "choice_reason", "TakeoutRecord", "choice_reason"),
    ("TakeoutRecordCreate", "satisfaction", "TakeoutRecord", "satisfaction"),
    ("ShoppingItemCreate", "name", "ShoppingItem", "name"),
    ("ShoppingItemCreate", "category", "ShoppingItem", "category"),
    ("ShoppingItemCreate", "quantity", "ShoppingItem", "quantity"),
    ("ShoppingItemCreate", "source_recipe", "ShoppingItem", "source_recipe"),
    # answer 同时写 chat_turns.content(varchar 500) 和
    # chat_sessions.*_choice(varchar 20)，取最窄的那一列做基准
    ("ChatTurnRequest", "answer", "ChatSession", "taste_choice"),
    ("ChatTurnRequest", "answer", "ChatSession", "budget_choice"),
    ("ChatTurnRequest", "answer", "ChatTurn", "content"),
    ("ChatTurnRequest", "session_id", "ChatSession", "id"),
]


def _pydantic_max_len(model, field):
    for meta in model.model_fields[field].metadata:
        length = getattr(meta, "max_length", None)
        if length is not None:
            return length
    return None


def test_b02_schema_max_len_matches_db_column():
    """B2 守门：入口长度上限必须 <= DB 列宽，且两边不能各自漂移。

    MySQL 端是 STRICT_TRANS_TABLES：超长不是静默截断而是 1406 报错，
    用户会看到一个莫名其妙的 500。所以约束必须在 pydantic 就拦住。
    """
    import schemas
    import models
    from pydantic import ValidationError

    for sm_name, sf, om_name, oc in _SCHEMA_VS_DB_PAIRS:
        model = getattr(schemas, sm_name)
        assert sf in model.model_fields, f"{sm_name} 已无字段 {sf}"
        want = _pydantic_max_len(model, sf)
        col = getattr(models, om_name).__table__.c[oc]
        got = col.type.length
        assert want is not None, f"{sm_name}.{sf} 丢了 max_length（B2 退化）"
        assert got, f"{om_name}.{oc} 不是定长列，请复核配对关系"
        assert want <= got, (
            f"{sm_name}.{sf} max_length={want} 超过 "
            f"{om_name}.{oc} varchar({got}) -> 1406/500"
        )

    # 槽位缓存键（64 位 sha256）必须放得进 prompt_hash 列
    assert models.RecipeCache.__table__.c.prompt_hash.type.length >= 64

    # 正例：合法边界值不报错，且 answer 会去空白
    assert schemas.IngredientCreate(user_id="u", name="面" * 50).name
    assert schemas.ChatTurnRequest(session_id="s", answer=" 辣 ").answer == "辣"

    # 反例：超长 / 超条数 / 枚举外取值，全部在入口就 ValidationError
    with pytest.raises(ValidationError):
        schemas.IngredientCreate(user_id="u", name="面" * 51)
    with pytest.raises(ValidationError):
        schemas.RecipeRequest(user_id="u", ingredient_names=["蛋"] * 51)
    with pytest.raises(ValidationError):
        schemas.RecipeRequest(user_id="u", ingredient_names=["蛋" * 51])
    with pytest.raises(ValidationError):
        schemas.RecipeRequest(user_id="u", exclude_recipes=["菜" * 101])
    with pytest.raises(ValidationError):
        schemas.TakeoutRecordCreate(user_id="u", final_choice="面", satisfaction="超好吃")
    with pytest.raises(ValidationError):
        schemas.ChatTurnRequest(session_id="s", answer="选" * 21)
    with pytest.raises(ValidationError):
        schemas.CookRecordCreate(user_id="u", dish_name="面", tags=["t"] * 11)

def test_b03_ingredient_location_is_persisted():
    """B3-1：POST /api/ingredients 之前把 req.location 整个丢掉。

    退化表现：客户端指定"直接放冷冻/冷藏"静默失效，行永远落在默认值 pool，
    冰箱分区视图看不到刚入库的食材。同时守住"归属必须由 current_user 决定"。
    """
    import main
    from schemas import IngredientCreate

    from models import Ingredient

    uid = _uid("ing-loc")
    db = _db()
    try:
        resp = main.create_ingredient(
            IngredientCreate(
                user_id="someone-elses-id",  # body 里的 user_id 不可信
                name="五花肉",
                category="肉蛋",
                quantity="半斤",
                location="freezer",
            ),
            current_user=_fake_user(uid),
            db=db,
        )
        assert resp["code"] == 0
        data = resp["data"]
        assert data["location"] == "freezer", "location 又被丢掉了"
        assert data["user_id"] == uid, "归属必须来自 current_user，不能信 body"

        row = db.query(Ingredient).filter(Ingredient.id == data["id"]).one()
        assert row.location == "freezer", "响应写了但没落库"

        # 前端目前不传 location，默认行为保持不变
        default_resp = main.create_ingredient(
            IngredientCreate(user_id=uid, name="菠菜", category="蔬菜"),
            current_user=_fake_user(uid),
            db=db,
        )
        assert default_resp["data"]["location"] == "pool"
    finally:
        db.close()


def test_b03_ingredient_enum_and_blank_name_rejected():
    """B3-2：冰箱的分区/状态/分类必须是白名单枚举，且 PATCH 不能再写入空名。

    脏枚举会让前端按精确值做的分区筛选整块失效；空 name 则是无法显示的空白卡片，
    在 MySQL STRICT_TRANS_TABLES 下还可能直接 500。
    """
    from fastapi import HTTPException

    import main
    from errors import BizError
    from schemas import IngredientCreate, IngredientUpdate

    from models import Ingredient

    uid = _uid("ing-enum")
    db = _db()
    try:
        bad_creates = [
            IngredientCreate(user_id=uid, name="牛奶", category="乳制品", location="attic"),
            IngredientCreate(user_id=uid, name="牛奶", category="零食柜"),
            IngredientCreate(user_id=uid, name="   ", category="乳制品"),
        ]
        for req in bad_creates:
            with pytest.raises(BizError) as exc:
                main.create_ingredient(req, current_user=_fake_user(uid), db=db)
            assert exc.value.code == 1001, f"应报参数错误，实际 {exc.value.code}"
        assert db.query(Ingredient).filter(Ingredient.user_id == uid).count() == 0

        created = main.create_ingredient(
            IngredientCreate(user_id=uid, name="牛奶", category="乳制品"),
            current_user=_fake_user(uid),
            db=db,
        )["data"]
        iid = created["id"]

        for patch in (
            IngredientUpdate(name="  \t "),
            IngredientUpdate(status="发霉了"),
            IngredientUpdate(location="阳台"),
            IngredientUpdate(category="零食柜"),
        ):
            with pytest.raises(BizError) as exc:
                main.update_ingredient(iid, patch, current_user=_fake_user(uid), db=db)
            assert exc.value.code == 1001

        after = main.update_ingredient(
            iid, IngredientUpdate(status="used_up"), current_user=_fake_user(uid), db=db
        )["data"]
        assert after["status"] == "used_up"
        assert after["name"] == "牛奶", "exclude_unset 下只改 status，不能顺带改 name"

        with pytest.raises(HTTPException) as hx:
            main.update_ingredient(
                iid,
                IngredientUpdate(status="expired"),
                current_user=_fake_user(_uid("ing-enum-other")),
                db=db,
            )
        assert hx.value.status_code == 403
    finally:
        db.close()


def test_b03_heatmap_works_without_mysql_day_function():
    """B3-3：日历热力图不能在 SQL 里用 MySQL 专有的 DAY()。

    原实现 `func.day(created_at)` 在 SQLite（以及单测/本地 sqlite 模式）下
    直接 "no such function: day"，整个日记页 500。改成取回 created_at
    在 Python 侧取 .day 后，"当日首条胜出"与排序语义必须保持不变。
    """
    import main
    from fastapi import HTTPException

    from models import CookRecord, TakeoutRecord

    uid = _uid("heatmap")
    # 用固定的历史月份：today 无关，且 2 月天数确定（2001 非闰年 = 28 天）
    db = _db()
    try:
        db.add(CookRecord(user_id=uid, dish_name="番茄炒蛋",
                          created_at=datetime(2001, 2, 14, 8, 0)))
        db.add(TakeoutRecord(user_id=uid, final_choice="黄焖鸡",
                             created_at=datetime(2001, 2, 14, 9, 0)))
        db.add(CookRecord(user_id=uid, dish_name="牛肉面",
                          created_at=datetime(2001, 2, 1, 19, 30)))
        db.commit()

        resp = main.get_heatmap(uid, 2001, 2, current_user=_fake_user(uid), db=db)
        assert resp["code"] == 0
        items = [
            d if isinstance(d, dict) else d.model_dump() for d in resp["data"]
        ]
        by_day = {d["day"]: d for d in items}
        assert len(items) == 28, "2001-02 是平年，应返回 28 天"
        assert by_day[14]["type"] == "both"
        assert by_day[14]["title"] == "番茄炒蛋/黄焖鸡"
        assert by_day[1]["type"] == "cook"
        assert by_day[1]["title"] == "牛肉面"
        assert by_day[2]["type"] == "empty"

        with pytest.raises(HTTPException) as hx:
            main.get_heatmap(uid, 2001, 2, current_user=_fake_user(_uid("heatmap-x")), db=db)
        assert hx.value.status_code == 403
    finally:
        db.close()

def test_b04_llm_failure_refunds_the_prefunded_quota(monkeypatch):
    """B4-1：LLM 彻底失败时要归还"预扣"的那一次配额。

    扣费时机的两个退化方向都要守住：
      * 在 LLM 之后才 consume —— 配额耗尽的人照样每次真打上游（花钱 + 等超时）；
      * 预扣了但失败不退款 —— 上游抖动一次就白掉用户一格额度。
    """
    import quota_limiter
    from schemas import ChatTurnRequest
    from services.chat_service import chat_service

    db = _db()
    uid = _uid("refund")
    kind = quota_limiter.QuotaKind.CHAT
    try:
        sid, ans = _play_to_round5(uid, db)
        assert quota_limiter._load_used_from_db(uid, kind) == 0, "前 4 轮不该扣费"

        calls = _stub_llm(monkeypatch, raises=RuntimeError("upstream down"))
        with pytest.raises(RuntimeError):
            asyncio.run(chat_service.process_turn(
                ChatTurnRequest(session_id=sid, answer=ans), db))

        assert len(calls) == 1, "LLM 应被调用一次（然后失败）"
        assert quota_limiter._load_used_from_db(uid, kind) == 0, (
            "调用失败却把配额扣掉了：refund_quota 退化"
        )
    finally:
        db.close()


def test_b04_quota_exhausted_never_calls_llm(monkeypatch):
    """B4-2：额度为 0 时，进 LLM 之前就拒绝，一次上游都不能打。"""
    import quota_limiter
    from errors import BizError
    from schemas import ChatTurnRequest
    from services.chat_service import chat_service

    db = _db()
    uid = _uid("exhausted")
    kind = quota_limiter.QuotaKind.CHAT
    try:
        sid, ans = _play_to_round5(uid, db)
        quota_limiter._save_used_to_db(uid, kind, quota_limiter._QUOTA_LIMITS[kind])
        assert quota_limiter.peek_quota(uid, kind) == 0

        calls = _stub_llm(monkeypatch, _TURN5_PAYLOAD)
        with pytest.raises(BizError) as exc:
            asyncio.run(chat_service.process_turn(
                ChatTurnRequest(session_id=sid, answer=ans), db))
        assert exc.value.code == 3004
        assert len(calls) == 0, "配额耗尽还去打 LLM：consume_quota 又跑到调用之后了"
    finally:
        db.close()


def test_b04_active_session_cap_and_stale_self_heal():
    """B4-3：未完成点单会话有上限，但僵尸会话要先自愈再计数。

    只加硬上限会把"中途关掉页面"的用户永久锁死，所以 create_session 必须
    先把超过 STALE_CHAT_SESSION_MINUTES 的 active 置为 expired（并且先落库，
    即使随后因超限被拒，用户也不该继续背着僵尸会话），再统计数量。
    """
    from errors import BizError
    from models import ChatSession
    from schemas import ChatSessionCreate
    from services.chat_service import (
        MAX_ACTIVE_CHAT_SESSIONS,
        STALE_CHAT_SESSION_MINUTES,
        chat_service,
    )

    assert MAX_ACTIVE_CHAT_SESSIONS == 3
    db = _db()
    uid = _uid("sess-cap")
    try:
        sids = [
            chat_service.create_session(ChatSessionCreate(user_id=uid, mood=""), db)
            .session_id
            for _ in range(MAX_ACTIVE_CHAT_SESSIONS)
        ]
        with pytest.raises(BizError) as exc:
            chat_service.create_session(ChatSessionCreate(user_id=uid, mood=""), db)
        assert exc.value.code == 3006, "未完成会话超限应返回 3006"

        stale = db.query(ChatSession).filter(ChatSession.id == sids[0]).one()
        stale.created_at = datetime.now() - timedelta(
            minutes=STALE_CHAT_SESSION_MINUTES + 15
        )
        db.commit()

        again = chat_service.create_session(ChatSessionCreate(user_id=uid, mood=""), db)
        assert again.status == "active", "僵尸会话没有让位"
        db.expire_all()
        assert stale.status == "expired"
        assert stale.completed_at is not None
        active_cnt = (
            db.query(ChatSession)
            .filter(ChatSession.user_id == uid, ChatSession.status == "active")
            .count()
        )
        assert active_cnt == MAX_ACTIVE_CHAT_SESSIONS
    finally:
        db.close()


def test_b04_chat_route_guards_present():
    """B4-4：两个点单写接口必须有速率限制，建会话还要进门先查余额。

    之前 /api/chat/session 既没 limiter 也不看配额，脚本可以无限灌 session，
    也可以让用户答满 5 轮才被拒绝（双方时间都白费）。
    """
    src = _read(os.path.join(BACKEND, "main.py")).splitlines()

    def _guard(fn_name: str, expected_limit: str) -> None:
        prefixes = (f"def {fn_name}(", f"async def {fn_name}(")
        idx = next(
            (k for k, ln in enumerate(src) if ln.startswith(prefixes)), None
        )
        assert idx is not None, f"main.py 里找不到 {fn_name}"
        assert src[idx - 1].strip() == f'@limiter.limit("{expected_limit}")', (
            f"{fn_name} 上方的限流装饰器变成了 {src[idx - 1]!r}"
        )
        body = "\n".join(src[idx:idx + 25])
        if fn_name == "create_chat_session":
            assert "peek_quota(" in body, "建会话不再先查配额"
            assert "QUOTA_EXCEEDED" in body

    _guard("create_chat_session", "10/minute")
    _guard("process_chat_turn", "30/minute")