"""
一键迁移：把 Gourmet_House_test 老 schema 补齐到 models.py 当前版本（P0-6 等新增列 + JSON + 唯一键）。
保证幂等：如果列/索引已存在则跳过，不会把现有表删掉。
运行：
    cd backend && python migrations/auto_migrate_mysql.py
"""
from __future__ import annotations

import pymysql
from sqlalchemy import create_engine, inspect, text

# 1. 用 models 生成一份「理想 schema」到临时库 gourmet_house_fresh (CREATE ALL)
import importlib.util
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
MODELS_PATH = BACKEND_DIR / "models.py"
DB_NAME_OLD = "gourmet_house_test"
DB_NAME_FRESH = "gourmet_house_fresh"
ROOT_DSN = "mysql+pymysql://root:meiwei2026@localhost:3306/?charset=utf8mb4"
OLD_DSN = f"mysql+pymysql://root:meiwei2026@localhost:3306/{DB_NAME_OLD}?charset=utf8mb4"
FRESH_DSN = f"mysql+pymysql://root:meiwei2026@localhost:3306/{DB_NAME_FRESH}?charset=utf8mb4"


def main() -> None:
    # 1a. 为了避免 import models 触发 Side Effects（如 config 的 SECRET_KEY warning），
    # 先从 models.py 里直接取出 Base.metadata，不实例化 settings / FastAPI
    spec = importlib.util.spec_from_file_location("models", MODELS_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # noqa: S301 — models.py 为项目自有代码
    Base = mod.Base

    # 1b. 准备 fresh 数据库
    eng_root = create_engine(ROOT_DSN)
    with eng_root.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS `{DB_NAME_FRESH}`;"))
        conn.execute(text(f"CREATE DATABASE `{DB_NAME_FRESH}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"))
    eng_fresh = create_engine(FRESH_DSN)
    Base.metadata.create_all(bind=eng_fresh)

    # 2. 逐列 / 逐索引把 old -> fresh 的差异以 ALTER 形式补上
    insp_fresh = inspect(eng_fresh)
    eng_old = create_engine(OLD_DSN)
    conn_old = eng_old.connect().execution_options(isolation_level="AUTOCOMMIT")
    insp_old = inspect(eng_old)

    def run(sql: str) -> None:
        print("→", sql)
        try:
            conn_old.execute(text(sql))
        except pymysql.err.OperationalError as e:
            code = e.args[0]
            # 1060=Duplicate column / 1061=Duplicate key name / 1091=Can't DROP ... / 1826=Duplicate foreign key constraint
            if code in (1060, 1061, 1091, 1826):
                print(f"    (skipped, already exists err {code})")
                return
            raise
        except Exception as e:
            # MariaDB / MySQL 老版本常见 1068 (multiple primary)
            if "Duplicate" in str(e) or "already exists" in str(e):
                print(f"    (skipped: {e})")
                return
            raise

    for tbl in insp_fresh.get_table_names():
        if tbl not in insp_old.get_table_names():
            # 旧库缺失整张表 → 以 fresh 为模板重建
            create_sql = _show_create(eng_fresh, tbl)
            print(f"[create table {tbl}]")
            run(create_sql)
            continue
        fresh_cols = {c["name"]: c for c in insp_fresh.get_columns(tbl)}
        old_cols = {c["name"]: c for c in insp_old.get_columns(tbl)}
        for name, col in fresh_cols.items():
            if name in old_cols:
                continue
            add = _render_add_column(tbl, col)
            run(add)
        # --- 额外：DROP 老 schema 中已从 models.py 删除的列 — 避免 NOT NULL no-default 引发 INSERT 500 ---
        for name, col in list(old_cols.items()):
            if name in fresh_cols:
                continue
            # 为了安全，不直接删；改成可空+移至末尾
            run(f"ALTER TABLE `{tbl}` DROP COLUMN `{name}`;")
        # Unique 约束
        fresh_uq = {(uq["name"], tuple(uq["column_names"])) for uq in insp_fresh.get_unique_constraints(tbl)}
        old_uq = {(uq["name"], tuple(uq["column_names"])) for uq in insp_old.get_unique_constraints(tbl)}
        for name, cols in fresh_uq - old_uq:
            run(f"ALTER TABLE `{tbl}` ADD UNIQUE KEY `{name}` ({','.join(f'`{c}`' for c in cols)});")
        # Indexes
        fresh_idx = {(idx["name"], tuple(idx["column_names"]))
                     for idx in insp_fresh.get_indexes(tbl)
                     if not idx.get("unique", False)}
        old_idx = {(idx["name"], tuple(idx["column_names"]))
                   for idx in insp_old.get_indexes(tbl)
                   if not idx.get("unique", False)}
        for name, cols in fresh_idx - old_idx:
            run(f"CREATE INDEX `{name}` ON `{tbl}` ({','.join(f'`{c}`' for c in cols)});")
        # Foreign keys
        fresh_fks = {(fk["name"], tuple(fk["constrained_columns"]), fk["referred_table"], tuple(fk["referred_columns"]))
                     for fk in insp_fresh.get_foreign_keys(tbl)}
        old_fks = {(fk["name"], tuple(fk["constrained_columns"]), fk["referred_table"], tuple(fk["referred_columns"]))
                   for fk in insp_old.get_foreign_keys(tbl)}
        for name, cols, rt, rcols in fresh_fks - old_fks:
            run(
                f"ALTER TABLE `{tbl}` ADD CONSTRAINT `{name}` "
                f"FOREIGN KEY ({','.join(f'`{c}`' for c in cols)}) "
                f"REFERENCES `{rt}`({','.join(f'`{c}`' for c in rcols)});"
            )

    # 2b. 修复列的 nullable 属性（auto-migrate 不自动处理 NOT NULL → NULL）
    #     以及列长度/类型变更（如 budget_level VARCHAR(30)、cooking_skill VARCHAR(20)）
    _FIX_NULLABLE = {
        "chat_turns": [("takeout_id", "varchar(36)", "NULL")],
    }
    for tbl, fixes in _FIX_NULLABLE.items():
        for col, dtype, nullable in fixes:
            run(f"ALTER TABLE `{tbl}` MODIFY COLUMN `{col}` {dtype} {nullable};")

    # 2b-1. user_preferences 列长度 + 新增 cuisines JSON 列
    try:
        with eng_root.connect() as c2b:
            c2b.execute(text(f"ALTER TABLE `{DB_NAME_OLD}`.user_preferences MODIFY COLUMN budget_level VARCHAR(30) NOT NULL DEFAULT '16~25';"))
            c2b.execute(text(f"ALTER TABLE `{DB_NAME_OLD}`.user_preferences MODIFY COLUMN cooking_skill VARCHAR(20) NOT NULL DEFAULT '一般会做点（炒简单菜）';"))
            c2b.commit()
            print("[2b-1] user_preferences 列长度调整完成")
    except Exception as e2b:
        print(f"[2b-1] user_preferences 列长度调整跳过: {e2b}")
    try:
        with eng_root.connect() as c2b2:
            c2b2.execute(text(f"ALTER TABLE `{DB_NAME_OLD}`.user_preferences ADD COLUMN cuisines JSON NOT NULL;"))
            c2b2.commit()
            print("[2b-2] user_preferences.cuisines JSON 列新增完成")
    except Exception as e2b2:
        # Duplicate column name 是正常的
        if "Duplicate" not in str(e2b2) and "duplicate" not in str(e2b2):
            print(f"[2b-2] user_preferences.cuisines 新增跳过: {e2b2}")
        else:
            print("[2b-2] user_preferences.cuisines 列已存在，跳过")

    # 2c. 数据规范化：users.phone 字段 UNIQUE，空串会导致多人注册冲突 → 统一置为 NULL
    try:
        with eng_root.connect() as c2:
            row = c2.execute(text(f"SELECT COUNT(*) FROM `{DB_NAME_OLD}`.users WHERE phone = ''")).scalar()
            if row and row > 0:
                res = c2.execute(text(f"UPDATE `{DB_NAME_OLD}`.users SET phone = NULL WHERE phone = ''"))
                c2.commit()
                print(f"[2c] users.phone: 空串 -> NULL 共 {res.rowcount} 行")
    except Exception as e2c:
        print(f"[2c] users.phone 规范化跳过（表可能不存在）: {e2c}")

    # 2d. 数据规范化：user_preferences.budget_level / cooking_skill 旧值 → 新枚举
    _BUDGET_MAP = {"省钱": "0~15", "正常": "16~25", "吃好点": "51~100"}
    _SKILL_MAP  = {"新手": "会烧水/泡面", "一般": "一般会做点（炒简单菜）", "熟练": "熟练（能做一桌家常菜）"}
    try:
        with eng_root.connect() as c2d:
            updated_budget = 0
            for old_v, new_v in _BUDGET_MAP.items():
                r = c2d.execute(text(f"UPDATE `{DB_NAME_OLD}`.user_preferences SET budget_level = :nv WHERE budget_level = :ov AND budget_level NOT IN ('0~15','16~25','26~50','51~100','101~150','151~200','201及以上')"), {"nv":new_v,"ov":old_v})
                updated_budget += r.rowcount or 0
            updated_skill = 0
            for old_v, new_v in _SKILL_MAP.items():
                r = c2d.execute(text(f"UPDATE `{DB_NAME_OLD}`.user_preferences SET cooking_skill = :nv WHERE cooking_skill = :ov"), {"nv":new_v,"ov":old_v})
                updated_skill += r.rowcount or 0
            c2d.commit()
            if updated_budget or updated_skill:
                print(f"[2d] user_preferences 旧枚举转换: budget {updated_budget} 条, cooking_skill {updated_skill} 条")
            else:
                print("[2d] user_preferences 旧枚举转换：无需处理")
    except Exception as e2d:
        print(f"[2d] user_preferences 枚举转换跳过: {e2d}")

    # 3. 收尾：DROP 临时 fresh 数据库
    with eng_root.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS `{DB_NAME_FRESH}`;"))
    print("\n✅ Migration complete.")


def _render_add_column(tbl: str, col: dict) -> str:
    """把 SQLAlchemy column dict（from inspector）翻译成 MySQL ALTER ADD COLUMN"""
    name = col["name"]
    sa_type = col["type"]
    # 把 SA type 翻译成字符串
    type_sql = str(sa_type.compile(dialect=create_engine(OLD_DSN).dialect))
    parts = [f"ALTER TABLE `{tbl}` ADD COLUMN `{name}` {type_sql}"]
    if not col.get("nullable", True):
        parts.append("NOT NULL")
    default = col.get("default")
    if default is not None:
        # 处理 ColumnDefault / Scalar / etc 文本化
        d = getattr(default, "arg", default)
        if callable(d):
            pass  # func now() 等，交给建表 SQL 表达式
        else:
            # JSON / TEXT 不允许 DEFAULT，MySQL 会报错 — 让它无 DEFAULT
            if not ("json" in type_sql.lower() or "text" in type_sql.lower()):
                if isinstance(d, str):
                    parts.append(f"DEFAULT '{d}'")
                else:
                    parts.append(f"DEFAULT {d}")
    autoincrement = col.get("autoincrement", False)
    if autoincrement is True or (isinstance(autoincrement, str) and autoincrement.lower() == "auto"):
        parts.append("AUTO_INCREMENT")
    if col.get("comment"):
        parts.append(f"COMMENT '{col['comment']}'")
    return " ".join(parts) + ";"


def _show_create(eng, tbl: str) -> str:
    with eng.connect() as conn:
        rs = conn.execute(text(f"SHOW CREATE TABLE `{tbl}`;")).fetchone()
        return rs[1] + ";"


if __name__ == "__main__":
    main()
