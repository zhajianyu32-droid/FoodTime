#!/usr/bin/env python3
"""
FoodTime — 云数据库一键初始化脚本
=================================
用途：把数据库结构与种子数据导入到任意云 MySQL（Railway / Aiven / 阿里云 RDS 等）。

背景（两个必须解决的问题）：
  1. 原始 SQL 脚本内硬编码了 `CREATE DATABASE meiweichuzuwu` 和 `USE meiweichuzuwu`，
     云平台分配的库名通常不同（Railway 默认 railway），直接执行会写到错误的库。
  2. **`06_schema_v2_final.sql` 是过时的老 schema** —— 它的 users 表只有 9 个字段，
     缺少 username / phone / password_hash / status / token_valid_since 等。
     本地库是靠 `backend/migrations/auto_migrate_mysql.py` 事后 ALTER 补齐的，
     而那个脚本硬编码了本地库名与密码，无法在云端使用。

本脚本的处理（关键改进）：
  1. **建表以 `backend/models.py` 为唯一真相源**，用 SQLAlchemy 直接生成 CREATE TABLE，
     彻底消除 schema 漂移；不再依赖过时的 06 脚本。
  2. 种子数据仍取 sql/ 下的 02 / 07 脚本，并剥离其中的库级语句与 DELIMITER 块。
  3. 全部在指定的目标库中执行。

用法：
  python sql/deploy_init_db.py "mysql://user:pass@host:port/dbname"
  # 或分离参数
  python sql/deploy_init_db.py --host HOST --port 3306 --user U --password P --db D

依赖：pymysql + sqlalchemy（后端 venv 已含）。
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

SQL_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SQL_DIR.parent / "backend"
MODELS_PATH = BACKEND_DIR / "models.py"

# 只导入种子数据；建表改由 models.py 生成
SEED_FILES = [
    "02_seed_data_mysql.sql",
    "07_seed_v2_data.sql",
]

# 剥离库级语句：这些必须由连接参数决定，不能让脚本自己切换
_STRIP_PATTERNS = [
    re.compile(r"^\s*CREATE\s+DATABASE\b[^;]*;", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*USE\s+[`\w]+;", re.IGNORECASE | re.MULTILINE),
]

# 种子数据里引用的视图在 models.py 中不存在，需要单独保留（06 脚本里的视图定义）
VIEW_SOURCE = SQL_DIR / "06_schema_v2_final.sql"


def load_models_base():
    """
    从 models.py 直接取出 Base.metadata，不触发 FastAPI / settings 的副作用。

    返回 (Base, error_message)。
    """
    if not MODELS_PATH.exists():
        return None, f"找不到 models.py: {MODELS_PATH}"
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    try:
        spec = importlib.util.spec_from_file_location("_ft_models", MODELS_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.Base, None
    except Exception as exc:  # noqa: BLE001
        return None, f"导入 models.py 失败: {exc}"


def extract_views(sql_text: str) -> list[str]:
    """
    从 06 脚本中提取 CREATE VIEW 语句（可重复执行版本）。

    视图不属于 SQLAlchemy 模型，但种子数据与统计接口会用到，必须保留。
    """
    stmts = split_statements(sql_text)
    views = []
    for s in stmts:
        if re.match(r"^\s*CREATE\s+(OR\s+REPLACE\s+)?VIEW\b", s, re.IGNORECASE):
            # 统一改成 CREATE OR REPLACE，保证可重复执行
            s = re.sub(
                r"^\s*CREATE\s+(OR\s+REPLACE\s+)?VIEW",
                "CREATE OR REPLACE VIEW",
                s, count=1, flags=re.IGNORECASE,
            )
            views.append(s)
    return views


def clean_sql(text: str) -> str:
    for pat in _STRIP_PATTERNS:
        text = pat.sub("-- [deploy] 已剥离库级语句\n", text)
    return text


def split_statements(sql: str) -> list[str]:
    """
    按分号切分语句，跳过注释行，并正确处理 DELIMITER 块。

    为什么需要特殊处理 DELIMITER：
      `DELIMITER //` 是 mysql 客户端的命令，不是 SQL 语句，驱动层无法执行。
      触发器/存储过程的函数体内部含分号，必须靠自定义分隔符才能整体提交。
      这里自行解析 DELIMITER 指令，把块内内容作为单条语句发给驱动。
    """
    stmts: list[str] = []
    delimiter = ";"
    buf: list[str] = []

    for raw_line in sql.splitlines():
        stripped = raw_line.strip()

        # 跳过注释行（注意：DELIMITER 行不能被当注释跳过）
        if stripped.startswith("--") or stripped.startswith("#"):
            continue

        # ---- DELIMITER 指令：切换分隔符，本身不发给服务器 ----
        m = re.match(r"^DELIMITER\s+(\S+)\s*$", stripped, re.IGNORECASE)
        if m:
            # 切换前先冲刷缓冲区
            pending = "\n".join(buf).strip()
            if pending:
                stmts.append(pending)
                buf = []
            delimiter = m.group(1)
            continue

        buf.append(raw_line)

        # 缓冲区是否以当前分隔符结尾？
        joined = "\n".join(buf).rstrip()
        if joined.endswith(delimiter):
            stmt = joined[: -len(delimiter)].strip()
            if stmt:
                stmts.append(stmt)
            buf = []

    # 收尾：文件末尾可能没有分隔符
    tail = "\n".join(buf).strip()
    if tail:
        stmts.append(tail)

    return stmts


def main() -> int:
    ap = argparse.ArgumentParser(description="FoodTime 云数据库初始化")
    ap.add_argument("dsn", nargs="?", help="mysql://user:pass@host:port/db")
    ap.add_argument("--host")
    ap.add_argument("--port", type=int, default=3306)
    ap.add_argument("--user")
    ap.add_argument("--password", default="")
    ap.add_argument("--db")
    ap.add_argument("--dry-run", action="store_true", help="只打印将执行的语句数，不连接数据库")
    args = ap.parse_args()

    if args.dsn:
        m = re.match(
            r"mysql://(?P<user>[^:]+):(?P<pwd>[^@]*)@(?P<host>[^:/]+):(?P<port>\d+)/(?P<db>\w+)",
            args.dsn,
        )
        if not m:
            print("❌ DSN 格式错误，应为 mysql://user:pass@host:port/db", file=sys.stderr)
            return 2
        conn_args = dict(
            host=m["host"], port=int(m["port"]),
            user=m["user"], password=m["pwd"], database=m["db"],
        )
    elif args.host and args.user and args.db:
        conn_args = dict(
            host=args.host, port=args.port,
            user=args.user, password=args.password, database=args.db,
        )
    else:
        ap.print_help()
        return 2

    # ---- 1. 建表：以 models.py 为唯一真相源 ----
    Base, err = load_models_base()
    if err:
        print(f"❌ {err}", file=sys.stderr)
        return 2

    from sqlalchemy import create_engine, inspect as sa_inspect, text as sa_text

    dsn = (
        f"mysql+pymysql://{conn_args['user']}:{conn_args['password']}"
        f"@{conn_args['host']}:{conn_args['port']}/{conn_args['database']}?charset=utf8mb4"
    )

    print(f"\n{'='*62}")
    print(f"目标库: {conn_args['database']} @ {conn_args['host']}:{conn_args['port']}")
    print(f"{'='*62}")

    tables = list(Base.metadata.sorted_tables)
    print(f"\n📐 建表（来源: backend/models.py，共 {len(tables)} 张表）")
    for t in tables:
        print(f"   - {t.name} ({len(t.columns)} 列)")

    # ---- 2. 种子数据 ----
    seed_stmts: list[tuple[str, str]] = []
    for fname in SEED_FILES:
        fpath = SQL_DIR / fname
        if not fpath.exists():
            print(f"⚠️  跳过不存在的文件: {fname}", file=sys.stderr)
            continue
        cleaned = clean_sql(fpath.read_text(encoding="utf-8"))
        stmts = split_statements(cleaned)
        print(f"📄 种子 {fname}: {len(stmts)} 条语句")
        for s in stmts:
            seed_stmts.append((fname, s))

    # ---- 3. 视图（models.py 不含视图，从 06 脚本提取）----
    views: list[str] = []
    if VIEW_SOURCE.exists():
        views = extract_views(clean_sql(VIEW_SOURCE.read_text(encoding="utf-8")))
        print(f"👁️  视图: {len(views)} 个（从 06 脚本提取）")

    if args.dry_run:
        print(f"\n✅ dry-run 完成：{len(tables)} 表 + {len(seed_stmts)} 条种子 + {len(views)} 视图")
        return 0

    # ---- 4. 执行 ----
    try:
        import pymysql  # noqa: F401
    except ImportError:
        print("❌ 缺少 pymysql，请先 pip install pymysql", file=sys.stderr)
        return 2

    engine = create_engine(dsn, pool_pre_ping=True)

    ok = 0
    fail = 0
    try:
        # 4a. 建表（按依赖顺序）
        print(f"\n{'─'*62}\n[1/4] 建表\n{'─'*62}")
        with engine.begin() as conn:
            Base.metadata.create_all(bind=conn)
        print(f"✅ {len(tables)} 张表创建完成")

        # 4b. 补齐数据库层默认值
        #      models.py 的 default=... 是 Python 层默认值，SQLAlchemy 不会把它翻译成
        #      DDL 的 DEFAULT。这导致 NOT NULL 且无默认值的列在「裸 SQL 插入」
        #     （种子数据 / 手工维护）时报 1364。
        #      应用运行时不受影响（ORM 在 Python 层填值），但种子数据必须补。
        #
        #      策略：直接遍历 Base.metadata，读取每个 Column 的 default，
        #            翻译成 DDL DEFAULT；再对 id / created_at 做通用兜底。
        print(f"\n{'─'*62}\n[2/4] 补齐数据库层默认值\n{'─'*62}")

        def _to_ddl_default(col) -> str | None:
            """把 SQLAlchemy Column 的 Python 默认值翻译成 DDL DEFAULT 片段。"""
            # 主键 id：统一 UUID()
            if col.primary_key:
                return "DEFAULT (UUID())"

            d = col.default
            if d is not None:
                arg = getattr(d, "arg", None)
                # callable（如 _uuid / _now / datetime.now）无法直接转 SQL，走通用规则
                if not callable(arg) and arg is not None:
                    if isinstance(arg, str):
                        return f"DEFAULT '{arg}'"
                    if isinstance(arg, bool):
                        return f"DEFAULT {1 if arg else 0}"
                    if isinstance(arg, (int, float)):
                        return f"DEFAULT {arg}"
                # 可调用 -> 交给下面的通用规则判断
                name = getattr(arg, "__name__", "")
                if name in ("_uuid", "uuid4", "uuid"):
                    return "DEFAULT (UUID())"
                if name in ("_now", "now", "utcnow"):
                    return (
                        "DEFAULT (NOW()) ON UPDATE CURRENT_TIMESTAMP"
                        if col.name.endswith("updated_at")
                        else "DEFAULT (NOW())"
                    )

            # 通用规则：按列名/类型推断
            cname = col.name
            ctype = str(col.type).upper()
            if cname == "id" or cname.endswith("_id"):
                if "VARCHAR" in ctype:
                    return "DEFAULT (UUID())"
            if cname.endswith("_at") and "DATETIME" in ctype:
                return (
                    "DEFAULT (NOW()) ON UPDATE CURRENT_TIMESTAMP"
                    if cname.endswith("updated_at")
                    else "DEFAULT (NOW())"
                )
            if "JSON" in ctype:
                return "DEFAULT (JSON_OBJECT())"
            if "VARCHAR" in ctype or "TEXT" in ctype:
                return "DEFAULT ''"
            if "INT" in ctype:
                return "DEFAULT 0"
            if "FLOAT" in ctype or "DOUBLE" in ctype or "DECIMAL" in ctype:
                return "DEFAULT 0"
            return None

        patched = 0
        skipped: list[str] = []
        with engine.begin() as conn:
            for table in Base.metadata.sorted_tables:
                # 从数据库读真实列信息（避免类型渲染差异）
                real_cols = {c["name"]: c for c in sa_inspect(engine).get_columns(table.name)}
                for col in table.columns:
                    real = real_cols.get(col.name)
                    if real is None:
                        continue
                    # 跳过可空列、已有默认值的列
                    if real.get("nullable", True) or real.get("default"):
                        continue
                    ddl = _to_ddl_default(col)
                    if not ddl:
                        skipped.append(f"{table.name}.{col.name}({col.type})")
                        continue
                    # 用数据库返回的真实类型（含长度）
                    type_sql = str(real["type"])
                    stmt = (
                        f"ALTER TABLE `{table.name}` MODIFY COLUMN `{col.name}` "
                        f"{type_sql} NOT NULL {ddl}"
                    )
                    try:
                        conn.execute(sa_text(stmt))
                        patched += 1
                    except Exception as exc:  # noqa: BLE001
                        skipped.append(f"{table.name}.{col.name} -> {exc}")
        print(f"✅ 补齐 {patched} 个默认值")
        if skipped:
            print(f"⚠️  跳过 {len(skipped)} 项（需人工确认）:")
            for s in skipped[:10]:
                print(f"     - {s}")

        # 4c. 视图
        if views:
            print(f"\n{'─'*62}\n[3/4] 创建视图\n{'─'*62}")
            for v in views:
                head = " ".join(v.split())[:70]
                try:
                    with engine.begin() as conn:
                        conn.execute(sa_text(v))
                    ok += 1
                    print(f"   ✅ {head}...")
                except Exception as exc:  # noqa: BLE001
                    fail += 1
                    print(f"   ⚠️  {head}... -> {exc}")

        # 4d. 种子数据
        print(f"\n{'─'*62}\n[4/4] 导入种子数据\n{'─'*62}")
        for i, (fname, stmt) in enumerate(seed_stmts, 1):
            head = " ".join(stmt.split())[:70]
            try:
                with engine.begin() as conn:
                    conn.execute(sa_text(stmt))
                ok += 1
            except Exception as exc:  # noqa: BLE001
                fail += 1
                print(f"   ⚠️  [{fname}] {head}... -> {exc}")

        print(f"\n{'='*62}")
        if fail == 0:
            print(f"✅ 初始化完成：{ok} 条语句执行成功，0 失败")
        else:
            print(f"⚠️  初始化完成：{ok} 成功，{fail} 失败（见上方 ⚠️ 明细）")
        print(f"{'='*62}")
        return 0 if fail == 0 else 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
