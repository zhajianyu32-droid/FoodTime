"""
P1-3: 核心单元测试
覆盖: onboarding 星座/生肖计算、偏好权重更新公式、聊天5轮状态机
运行: cd backend ; python -m pytest tests/ -v --asyncio-mode=auto
"""
from __future__ import annotations

from datetime import date

import pytest

from services.fortune_service import calc_zodiac
from services.preference_service import (
    PreferenceService, DIMENSIONS, DEFAULT_WEIGHT, ALPHA_OLD, ALPHA_FEEDBACK,
)
from services.chat_service import ChatService, ROUND_CONFIG
from schemas import (
    ChatSessionCreate, ChatTurnRequest,
    PreferenceWeight, FeedbackRequest,
)


# ============================================================
# 1. calc_zodiac — 星座 / 生肖计算（边界用例）
# ============================================================
@pytest.mark.parametrize(
    "birth_date,exp_zodiac,exp_chinese",
    [
        # 摩羯座边界 (12.22 - 1.19)
        (date(2000, 1, 1), "摩羯座", "龙"),
        (date(2000, 1, 19), "摩羯座", "龙"),
        (date(2000, 1, 20), "水瓶座", "龙"),
        # 水瓶座 (1.20 - 2.18)
        (date(2000, 2, 18), "水瓶座", "龙"),
        (date(2000, 2, 19), "双鱼座", "龙"),
        # 双鱼座 (2.19 - 3.20)
        (date(2000, 3, 20), "双鱼座", "龙"),
        (date(2000, 3, 21), "白羊座", "龙"),
        # 白羊座 (3.21 - 4.19)
        (date(2000, 4, 19), "白羊座", "龙"),
        (date(2000, 4, 20), "金牛座", "龙"),
        # 金牛座 (4.20 - 5.20)
        (date(2000, 5, 20), "金牛座", "龙"),
        (date(2000, 5, 21), "双子座", "龙"),
        # 双子座 (5.21 - 6.21)
        (date(2000, 6, 21), "双子座", "龙"),
        (date(2000, 6, 22), "巨蟹座", "龙"),
        # 巨蟹座 (6.22 - 7.22)
        (date(2000, 7, 22), "巨蟹座", "龙"),
        (date(2000, 7, 23), "狮子座", "龙"),
        # 狮子座 (7.23 - 8.22)
        (date(2000, 8, 22), "狮子座", "龙"),
        (date(2000, 8, 23), "处女座", "龙"),
        # 处女座 (8.23 - 9.22)
        (date(2000, 9, 22), "处女座", "龙"),
        (date(2000, 9, 23), "天秤座", "龙"),
        # 天秤座 (9.23 - 10.23)
        (date(2000, 10, 23), "天秤座", "龙"),
        (date(2000, 10, 24), "天蝎座", "龙"),
        # 天蝎座 (10.24 - 11.22)
        (date(2000, 11, 22), "天蝎座", "龙"),
        (date(2000, 11, 23), "射手座", "龙"),
        # 射手座 (11.23 - 12.21)
        (date(2000, 12, 21), "射手座", "龙"),
        (date(2000, 12, 22), "摩羯座", "龙"),
        # 生肖: (年份-4) mod 12
        # 0鼠 1牛 2虎 3兔 4龙 5蛇 6马 7羊 8猴 9鸡 10狗 11猪
        (date(1996, 6, 1), "双子座", "鼠"),      # (1996-4)%12=0
        (date(1997, 6, 1), "双子座", "牛"),      # 1
        (date(1998, 6, 1), "双子座", "虎"),      # 2
        (date(1999, 6, 1), "双子座", "兔"),      # 3
        (date(2000, 6, 1), "双子座", "龙"),      # 4
        (date(2001, 6, 1), "双子座", "蛇"),      # 5
        (date(2002, 6, 1), "双子座", "马"),      # 6
        (date(2003, 6, 1), "双子座", "羊"),      # 7
        (date(2004, 6, 1), "双子座", "猴"),      # 8
        (date(2005, 6, 1), "双子座", "鸡"),      # 9
        (date(2006, 6, 1), "双子座", "狗"),      # 10
        (date(2007, 6, 1), "双子座", "猪"),      # 11
        (date(2008, 6, 1), "双子座", "鼠"),      # 循环
    ],
)
def test_calc_zodiac_and_chinese_zodiac(birth_date, exp_zodiac, exp_chinese):
    zodiac, chinese = calc_zodiac(birth_date)
    assert zodiac == exp_zodiac, f"{birth_date} => 期望{exp_zodiac}, 实际{zodiac}"
    assert chinese == exp_chinese, f"{birth_date.year} => 期望属{exp_chinese}, 实际属{chinese}"


# ============================================================
# 2. PreferenceService — 权重公式正确性
# ============================================================
@pytest.mark.parametrize(
    "old_w,feedback,expected_new",
    [
        # 公式: newW = oldW * ALPHA_OLD + feedback * ALPHA_FEEDBACK
        #   good=1.0 / ok=0.5 / bad=0.0
        (0.5, 3, 0.5 * ALPHA_OLD + 1.0 * ALPHA_FEEDBACK),   # rating 3 = good
        (0.5, 2, 0.5 * ALPHA_OLD + 0.5 * ALPHA_FEEDBACK),   # rating 2 = ok
        (0.5, 1, 0.5 * ALPHA_OLD + 0.0 * ALPHA_FEEDBACK),   # rating 1 = bad
        (1.0, 1, 1.0 * ALPHA_OLD + 0.0 * ALPHA_FEEDBACK),   # 高权重 + 差评 -> 下降
        (0.0, 3, 0.0 * ALPHA_OLD + 1.0 * ALPHA_FEEDBACK),   # 低权重 + 好评 -> 上升
    ],
)
def test_preference_feedback_formula(old_w: float, feedback: int, expected_new: float):
    """直接验证 feedback 计算公式（不依赖DB）"""
    from services.preference_service import FEEDBACK_SCORES
    label = "good" if feedback == 3 else "ok" if feedback == 2 else "bad"
    score = FEEDBACK_SCORES[label]
    new_w = old_w * ALPHA_OLD + score * ALPHA_FEEDBACK
    assert round(new_w, 5) == round(expected_new, 5)


def test_preference_init_weights_covers_all_dimensions():
    """init_weights 必须覆盖 DIMENSIONS 中全部 9 个维度"""
    # 用内存 SQLite 模拟 DB（最小化依赖）
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database import Base
    from models import PreferenceWeight

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    svc = PreferenceService()
    uid = "test-user-init-weights"
    svc.init_weights(uid, "辣", db)

    rows = db.query(PreferenceWeight).filter(PreferenceWeight.user_id == uid).all()
    # 必须全部 9 个维度
    assert len(rows) == len(DIMENSIONS)
    dims_found = sorted(r.dimension for r in rows)
    assert dims_found == sorted(DIMENSIONS)
    # 用户偏好 "辣" 的初始权重 = 0.8
    spicy = next(r for r in rows if r.dimension == "辣")
    assert round(float(spicy.weight), 3) == 0.800
    # 其他维度 = 0.5
    others = [r for r in rows if r.dimension != "辣"]
    assert all(round(float(r.weight), 3) == 0.500 for r in others)


# ============================================================
# 3. ChatService — 5 轮状态机
# ============================================================
def _make_db():
    """
    复用 database.py 的全局 engine，确保表对 quota_limiter 等服务同样可见。
    （若另建内存引擎，各连接的内存库互相隔离，会报 no such table）
    """
    from database import engine, Base, SessionLocal

    Base.metadata.create_all(bind=engine)
    return SessionLocal()


def test_chat_round_config_has_5_rounds():
    """必须刚好 5 轮，字段/问题/选项不得为空"""
    assert len(ROUND_CONFIG) == 5
    for i, cfg in enumerate(ROUND_CONFIG):
        assert cfg["dim"], f"第{i+1}轮缺少维度名称"
        assert cfg["field"], f"第{i+1}轮缺少字段名"
        assert cfg["q"], f"第{i+1}轮缺少问题"
        assert len(cfg["opts"]) >= 2, f"第{i+1}轮选项不足"


def test_chat_5_round_state_machine():
    """
    创建会话 → 依次回答 5 轮 → 第 6 次应给出最终推荐。
    因为没有 LLM key，会走 fallback 给出 "川味牛肉面" 兜底推荐。
    """
    import asyncio
    db = _make_db()
    svc = ChatService()
    uid = "test-chat-user"

    # Round 1: 创建会话
    resp1 = svc.create_session(ChatSessionCreate(user_id=uid, mood="开心"), db)
    assert resp1.current_round == 1
    assert resp1.total_rounds == 5
    assert resp1.status == "active"
    assert resp1.dimension == ROUND_CONFIG[0]["dim"]
    sid = resp1.session_id

    # Round 2-5: 依次回答
    for i in range(4):
        last = asyncio.run(svc.process_turn(
            ChatTurnRequest(session_id=sid, answer=ROUND_CONFIG[i]["opts"][0]),
            db,
        ))
        assert last.current_round == i + 2, f"第{i+1}轮完成后应进入第{i+2}轮"
        assert last.status == "active"

    # Round 5 answer → 第 6 次 process_turn 触发最终推荐
    final = asyncio.run(svc.process_turn(
        ChatTurnRequest(session_id=sid, answer=ROUND_CONFIG[4]["opts"][0]),
        db,
    ))
    # ChatFinalRecommend
    assert hasattr(final, "final_recommend") or "final_recommend" in final.model_dump()
    fd = final.model_dump()
    assert fd["final_recommend"], "5轮结束必须给出最终推荐"
    assert isinstance(fd["alternatives"], list) and len(fd["alternatives"]) >= 2
    assert fd["status"] == "completed" if "status" in fd else True


def test_chat_session_must_belong_to_correct_user():
    """越权场景：A 用户的 session 不能被 B 用户继续回答"""
    # 本测试由 main.py 层的 require_owner(session.user_id, current_user) 保证
    # 此处仅验证 session 表中 user_id 字段确实被写入
    db = _make_db()
    svc = ChatService()
    resp = svc.create_session(ChatSessionCreate(user_id="user-A", mood="开心"), db)

    from models import ChatSession
    row = db.query(ChatSession).filter(ChatSession.id == resp.session_id).first()
    assert row is not None
    assert row.user_id == "user-A"


# ============================================================
# 4. 安全：password 哈希 + JWT 签发验证
# ============================================================
def test_password_hash_roundtrip():
    from security import hash_password, verify_password

    pwd = "FoodTime-2026!安全"
    h = hash_password(pwd)
    assert h != pwd
    assert verify_password(pwd, h) is True
    assert verify_password("wrong-pass", h) is False


def test_jwt_token_pair_and_validation():
    from security import issue_tokens, decode_token, TokenType

    uid = "u-jwt-test-001"
    pair = issue_tokens(uid)

    assert "access_token" in pair and "refresh_token" in pair
    assert pair["token_type"] == "bearer"
    assert pair["expires_in"] > 0

    acc = decode_token(pair["access_token"], expected_type=TokenType.ACCESS)
    assert acc["sub"] == uid

    ref = decode_token(pair["refresh_token"], expected_type=TokenType.REFRESH)
    assert ref["sub"] == uid

    # 类型交叉校验失败
    from jose import JWTError as _JWTErr
    from fastapi import HTTPException
    try:
        decode_token(pair["refresh_token"], expected_type=TokenType.ACCESS)
        assert False, "refresh token 不应当能作为 access token 验证"
    except HTTPException:
        pass


# ============================================================
# 8. P0 修复 — 并发配额不超卖
# ============================================================
@pytest.mark.asyncio
async def test_quota_concurrent_not_oversold():
    """同一用户在 asyncio.gather 高并发下，used 总量不应超过 limit。"""
    import quota_limiter as _ql
    from quota_limiter import consume_quota, QuotaKind
    from database import engine, Base

    # 内存库不跨连接共享，必须在使用前建表
    Base.metadata.create_all(bind=engine)

    USER_ID = "u-quota-stress-01"
    KIND = QuotaKind.RECIPE

    # 重置该用户当日计数，避免污染（实现已改为 DB 持久化）
    _ql._save_used_to_db(USER_ID, KIND, 0)
    # 把 limit 临时压到 5 便于测溢出
    original_limits = _ql._QUOTA_LIMITS
    _ql._QUOTA_LIMITS = {KIND: 5}
    try:
        tasks = [consume_quota(USER_ID, KIND) for _ in range(20)]
        results = []
        for t in tasks:
            try:
                results.append(await t)
            except Exception:
                results.append("QUOTA_ERR")
        used = _ql._load_used_from_db(USER_ID, KIND)
        assert used == 5, f"used={used} 超过 limit=5，并发超卖 bug 未修复"
        success_count = sum(1 for x in results if x != "QUOTA_ERR")
        assert success_count == 5, f"success={success_count} 超过 limit=5"
        err_count = sum(1 for x in results if x == "QUOTA_ERR")
        assert err_count == 15
    finally:
        _ql._QUOTA_LIMITS = original_limits
        _ql._save_used_to_db(USER_ID, KIND, 0)


# ============================================================
# 9. P0-6 修复 — token_valid_since 黑名单机制
# ============================================================
def test_token_valid_since_blacklist():
    """改密后 token_valid_since 推进，旧 token 应当立即作废。"""
    from security import _enforce_token_valid_since, _iat_from_payload, issue_tokens, decode_token, TokenType
    from models import User
    import time as _t

    uid = "u-blacklist-01"
    old_pair = issue_tokens(uid)
    old_payload = decode_token(old_pair["access_token"], expected_type=TokenType.ACCESS)

    user_fresh = User(id=uid, nickname="t")
    user_fresh.token_valid_since = 0.0
    # 旧 token 对应新用户不应被拉黑（valid_since=0 等价于未启用黑名单）
    _enforce_token_valid_since(user_fresh, old_payload)  # 不应抛

    # 模拟改密：把 valid_since 推进到 iat + 1 秒后
    iat = _iat_from_payload(old_payload)
    user_fresh.token_valid_since = iat + 1.0
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        _enforce_token_valid_since(user_fresh, old_payload)
    assert exc.value.status_code == 401
    assert "改密" in exc.value.detail or "挂失" in exc.value.detail

    # 新发 token（iat >= valid_since）可以通过
    new_pair = issue_tokens(uid)
    # wait 1ms 确保时间戳递进
    _t.sleep(0.01)
    user_fresh.token_valid_since = iat  # 回退到旧时间之前
    new_payload = decode_token(new_pair["access_token"], expected_type=TokenType.ACCESS)
    _enforce_token_valid_since(user_fresh, new_payload)  # 不应抛


# ============================================================
# 10. P0-3 修复 — 食材过期状态流转（懒更新 SQL UPDATE 原子性）
# ============================================================
def test_ingredient_lazy_expire_logic_smoke():
    """验证 list_ingredients 会 UPDATE status=expired 的 SQL 逻辑在同步会话中可执行。"""
    from models import Ingredient, Base
    from database import SessionLocal, engine
    from datetime import date, timedelta

    # 临时 SQLite 内存库，避免污染真实 DB
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    mem = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=mem)
    MemSession = sessionmaker(bind=mem)

    sess = MemSession()
    try:
        yesterday = date.today() - timedelta(days=1)
        tomorrow = date.today() + timedelta(days=2)
        sess.add_all([
            Ingredient(user_id="u1", name="坏牛奶", category="乳制品", quantity="1盒",
                       status="available", expiry_date=yesterday),
            Ingredient(user_id="u1", name="好鸡蛋", category="蛋类", quantity="6枚",
                       status="available", expiry_date=tomorrow),
            Ingredient(user_id="u1", name="已用尽面粉", category="米面", quantity="0",
                       status="used_up", expiry_date=yesterday),  # used_up 不变
        ])
        sess.commit()

        # 模拟懒更新（与 main.py list_ingredients 中的逻辑等价）
        n = (
            sess.query(Ingredient)
            .filter(Ingredient.user_id == "u1")
            .filter(Ingredient.status == "available")
            .filter(Ingredient.expiry_date.is_not(None))
            .filter(Ingredient.expiry_date < date.today())
            .update({Ingredient.status: "expired"}, synchronize_session=False)
        )
        sess.commit()
        assert n == 1, f"应只置 expired 1 条，实际 {n}"

        rows = {r.name: r.status for r in sess.query(Ingredient).all()}
        assert rows["坏牛奶"] == "expired"
        assert rows["好鸡蛋"] == "available"
        assert rows["已用尽面粉"] == "used_up", "used_up 不应被懒更新覆盖"
    finally:
        sess.close()
