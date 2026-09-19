#!/usr/bin/env python3
"""
FoodTime — 云数据库一键初始化脚本
=================================
用途：把 sql/ 下的建表与种子脚本，导入到任意云 MySQL（Railway / Aiven / 阿里云 RDS 等）。

背景：原始脚本内硬编码了 `CREATE DATABASE meiweichuzuwu` 和 `USE meiweichuzuwu`，
      云平台分配的库名通常不同（Railway 默认 railway），直接执行会写到错误的库。

本脚本的处理：
  1. 剥离所有 `CREATE DATABASE ...;` 与 `USE ...;` 语句；
  2. 按依赖顺序拼接 06（建表）→ 02（基础种子）→ 07（v2 增量种子）；
  3. 全部在指定的目标库中执行。

用法：
  python sql/deploy_init_db.py "mysql://user:pass@host:port/dbname"
  # 或分离参数
  python sql/deploy_init_db.py --host HOST --port 3306 --user U --password P --db D

依赖：pymysql（后端 venv 已含）。若未安装：pip install pymysql
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SQL_DIR = Path(__file__).resolve().parent

# 执行顺序：建表 → 基础数据 → v2 增量
FILES_IN_ORDER = [
    "06_schema_v2_final.sql",
    "02_seed_data_mysql.sql",
    "07_seed_v2_data.sql",
]

# 剥离库级语句：这些必须由连接参数决定，不能让脚本自己切换
_STRIP_PATTERNS = [
    re.compile(r"^\s*CREATE\s+DATABASE\b[^;]*;", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*USE\s+[`\w]+;", re.IGNORECASE | re.MULTILINE),
]


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

    # ---- 收集并清洗 SQL ----
    all_stmts: list[tuple[str, str]] = []
    for fname in FILES_IN_ORDER:
        fpath = SQL_DIR / fname
        if not fpath.exists():
            print(f"⚠️  跳过不存在的文件: {fname}", file=sys.stderr)
            continue
        raw = fpath.read_text(encoding="utf-8")
        cleaned = clean_sql(raw)
        stmts = split_statements(cleaned)
        print(f"📄 {fname}: {len(stmts)} 条语句")
        for s in stmts:
            all_stmts.append((fname, s))

    print(f"\n合计 {len(all_stmts)} 条语句，目标库: {conn_args['database']} @ {conn_args['host']}:{conn_args['port']}")

    if args.dry_run:
        print("✅ dry-run 完成，未连接数据库")
        return 0

    # ---- 执行 ----
    try:
        import pymysql
    except ImportError:
        print("❌ 缺少 pymysql，请先 pip install pymysql", file=sys.stderr)
        return 2

    conn = pymysql.connect(
        **conn_args,
        charset="utf8mb4",
        autocommit=False,
        # 大脚本可能很慢，放宽超时
        connect_timeout=30,
        read_timeout=300,
        write_timeout=300,
    )
    ok = 0
    try:
        with conn.cursor() as cur:
            for i, (fname, stmt) in enumerate(all_stmts, 1):
                try:
                    cur.execute(stmt)
                    ok += 1
                except Exception as exc:  # noqa: BLE001
                    snippet = " ".join(stmt.split())[:120]
                    print(f"\n❌ 第 {i} 条失败（来自 {fname}）: {exc}", file=sys.stderr)
                    print(f"   语句: {snippet}...", file=sys.stderr)
                    conn.rollback()
                    return 1
        conn.commit()
        print(f"\n✅ 初始化完成：{ok}/{len(all_stmts)} 条语句执行成功")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
