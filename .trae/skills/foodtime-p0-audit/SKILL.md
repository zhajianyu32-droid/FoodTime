---
name: "foodtime-p0-audit"
description: "FoodTime 项目 P0/P1 缺陷审计+修复+验证闭环流程。Invoke when 要对 FoodTime 做安全/并发/数据一致性体检或修复 P0 缺陷。"
---

# FoodTime P0 缺陷审计 & 修复 SOP

本 skill 固化了 FoodTime（FastAPI + SQLAlchemy + MySQL + LLM 双 Provider 的个人「做饭推荐 / 外卖运势」应用）在 P0 级缺陷下的**审计要点、修复范式与回归校验规则**。当以下任一触发条件成立时调用：

- 用户说「修复 P0 / 修复安全漏洞 / 做一次代码体检 / 缺陷审计」；
- 准备对 FoodTime 后端做结构改动或上线前检查；
- 用户刚反馈「配额扣了但没出结果、账号被盗、食材明明过期却仍显示可用」等 P0 症状。

---

## 1. 审计总览（P0 缺陷清单 & 对应代码定位）

使用前先跑一轮 `pytest tests/ -v` 建立基线；失败先记录，再按此表格定位：

| # | 类别 | 典型症状 | 审计位置 | 校验规则（必须通过）|
|---|---|---|---|---|
| P0-1 | 密钥泄露 / 配置不当 | `.env` 中出现 `sk-xxx` 真实值、仓库无 `.gitignore`、`SECRET_KEY` 是仓库默认常量 | `backend/.env`, `backend/config.py`, 仓库根 `.gitignore` | 1. grep `.env` / `*.py` 无真实 `sk-` 前缀字符串；2. 根目录有 `.gitignore` 且包含 `.env .env.local *.pem __pycache__/ logs/ node_modules/`；3. `config.SECRET_KEY` 若命中已知弱值（见 `_KNOWN_INSECURE_SECRETS`）必须在启动时动态替换为 `secrets.token_hex(32)` 并打印 warning。 |
| P0-2 | 配额并发超卖 | 高并发下 used > limit，或 LLM 账单明显超预算 | `quota_limiter.consume_quota` 及调用方 `main.py` 的三处 `await consume_quota(...)` | 并发压测：`asyncio.gather(*[consume_quota(user, kind) for _ in range(N)])`，最终 used 必须严格等于 limit，超出应报错且失败不计 used。 |
| P0-3 | 食材状态不流转 | `expiry_date < today` 的食材依然 `status=available`，推荐菜谱匹配到过期食材 | `main.on_startup`, `main.list_ingredients`, `Ingredient.status/expiry_date` | 1. startup 时执行一次批量 UPDATE WHERE status='available' AND expiry_date<today；2. `GET /api/ingredients/{uid}` 在查之前对本 user 先执行一次懒更新；3. `used_up` 状态不得被懒更新覆盖。 |
| P0-4 | AI 归因缺失 | `ai_recommend_id` 全为空导致推荐点击率/反馈闭环不可追踪 | `RecipeItem.id`, `CookRecordCreate.ai_recommend_id`, `recipe_service._save_cache`, `create_cook_record` | 1. `POST /recipes/recommend` 返回的每条菜均带有 `id`（`RecipeCache.id`）；2. 用户携带 `ai_recommend_id` 写日记时，必须按 user 归属校验后写入 `CookRecord.ai_recommend_id`；3. `exclude_recipes` 非空时不得读写同 hash 缓存（防缓存污染）。 |
| P0-5 | main.py 超大 | 1000+ 行且 handler 内塞业务，新增功能容易回归 | `main.py` 长度、是否有 `routers/*.py` | 推荐阈值：`main.py <= 800 行`；否则拆分 `routers/auth_router / cook_router / order_router / diary_router / user_router` 并 `include_router`。 |
| P0-6 | JWT Refresh 无黑名单 | 改密后攻击者持旧 refresh 仍能换新 access → 账号接管 | `User.token_valid_since`, `security._enforce_token_valid_since`, `change_password`, `/api/auth/refresh` | 1. `User.token_valid_since FLOAT NOT NULL DEFAULT 0`；2. access / refresh 验证均校验 `iat >= token_valid_since`；3. `POST /api/auth/password` 成功后 `token_valid_since = time.time()`；4. 改密后旧 access 必须 401「当前登录态已因改密/挂失失效」，旧 refresh 返回 `AUTH_EXPIRED`。 |
| Extra | SQLAlchemy bool & BinaryExpression bug | `/api/auth/register` 抛 `TypeError: unsupported operand type(s) for &: 'bool' and 'BinaryExpression'` | `main.py` 中 `(bool_expr) & (col==x)` 的组合条件写法 | 禁止把 Python bool 直接用 `&` 或 `|` 跟 SQLA Column 表达式混算。必须用 `sqlalchemy.and_ / or_`，或先在 Python 层构建 filter list 再 `filter(or_(*filters))`。 |

---

## 2. 修复模板（按每个缺陷的落地代码片段）

### P0-1 密钥与配置
1. **吊销泄露的 key**：DeepSeek/DashScope 控制台手动吊销；本 skill 只负责**代码侧防御**。
2. 新建 `.gitignore`（项目根）：参考 FoodTime 当前已落地版本。
3. 新建 `backend/.env.local`（gitignore）承载真实密钥；把 `backend/.env` 改成模板 + 占位符。
4. `config.py`：
   - `Settings.Config.env_file = (".env.local", ".env")` 让本机优先覆盖。
   - 启动后 `settings.SECRET_KEY = _ensure_secret_key(settings.SECRET_KEY)`，命中占位值则：
     - production 环境 `warnings.warn` + 抛出可观测告警；
     - dev 环境临时 `secrets.token_hex(32)`（重启失效，提醒写进 `.env.local`）。

### P0-2 并发配额
```python
_lock_pool: dict[tuple[str, str], asyncio.Lock] = {}
_lock_pool_guard = asyncio.Lock()

async def _get_lock(user_id: str, kind: str) -> asyncio.Lock:
    async with _lock_pool_guard:
        k = (user_id, kind)
        if k not in _lock_pool:
            _lock_pool[k] = asyncio.Lock()
        return _lock_pool[k]

async def consume_quota(user_id: str, kind: str) -> int:
    lock = await _get_lock(user_id, kind)
    async with lock:
        limit = _QUOTA_LIMITS.get(kind, 9999)
        today = _today()
        _daily_usage[today][user_id][kind] += 1      # 先 +1
        used = _daily_usage[today][user_id][kind]
        if used > limit:
            _daily_usage[today][user_id][kind] = limit  # 失败回滚
            raise BizError(*ERR["QUOTA_EXCEEDED"])
        return limit - used
```
- 所有 async handler 调用点加 `await`（之前同步写法会直接吞掉）。
- **Chat 配额不要在 session 创建时扣**（P1-12 附带修复），移到 `chat_service._generate_final_recommend` 成功 commit 之后再扣。避免用户 session 创建成功但 LLM 失败仍扣一次。

### P0-3 过期食材流转
```python
# startup
@app.on_event("startup")
def on_startup():
    if settings.DEBUG: Base.metadata.create_all(bind=engine)
    try:
        with engine.connect() as c:
            n = c.execute(
                update(Ingredient)
                .where(Ingredient.status == "available")
                .where(Ingredient.expiry_date.is_not(None))
                .where(Ingredient.expiry_date < date.today())
                .values(status="expired")
            ).rowcount
            if n: c.commit()
    except Exception as exc: logger.warning("...: %s", exc)

# lazy update before list (per-user)
today = date.today()
expired_n = (
    db.query(Ingredient)
    .filter(Ingredient.user_id == uid, Ingredient.status == "available")
    .filter(Ingredient.expiry_date.is_not(None), Ingredient.expiry_date < today)
    .update({Ingredient.status: "expired"}, synchronize_session=False)
)
if expired_n: db.commit()
```

### P0-4 AI 归因
- `schemas.RecipeItem` 加 `id: str = ""`。
- `recipe_service.recommend()` 中：
  - `prompt_hash_src = prompt + "::exclude=" + ",".join(sorted(exclude_recipes))`，防 exclude 污染；
  - 仅当 `exclude_recipes` 为空时读缓存；缓存加 24h TTL（`created_at.timestamp() > time.time() - 86400`）；
  - LLM 生成每条菜后，用 `db.flush()` 立刻取 `RecipeCache.id` 回填 `RecipeItem.id`。
- `CookRecordCreate.ai_recommend_id` 字段加上；写日记时：
  ```python
  recommend_id = None
  if req.ai_recommend_id:
      rc = db.query(RecipeCache).filter(
          RecipeCache.id == req.ai_recommend_id,
          RecipeCache.user_id == user_id,   # 归属，防串号注入
      ).first()
      if rc: recommend_id = rc.id
  record = CookRecord(..., ai_recommend_id=recommend_id)
  ```

### P0-6 Refresh 黑名单
1. 模型：`User.token_valid_since = Column(Float, nullable=False, default=0.0)`。
2. 签发：`_sign` 里加 `iat_ts: int(datetime.now(UTC).timestamp())`（不要只塞 datetime，改密后 `valid_since` 是 float 秒）。
3. 校验：`_resolve_user_id` 中 decode 完后再调 `_enforce_token_valid_since(user, payload)`；`iat_ts < user.token_valid_since` → 401。
4. refresh 端点也要做同样校验，否则旧 refresh 能换新 access。
5. `POST /api/auth/password` 成功后：
   ```python
   import time as _t
   current_user.token_valid_since = _t.time()
   db.commit()
   ```
6. 对 MySQL 老表（production 已有的线上库）：执行一条 `ALTER TABLE users ADD COLUMN token_valid_since FLOAT NOT NULL DEFAULT 0;` 就行（单列加列不需要 alembic 也能平滑）。

---

## 3. 回归验证清单（每条修复后必须跑完）

> 目标：「已有测试 + 新增 P0 专项测试 + 端到端 HTTP 烟测」全部绿。

### 3.1 已有测试
```
cd backend
python -m pytest tests/ -v --asyncio-mode=auto
```
必须 **49 original passed**（修完 P0 补丁后是 **52 passed**，因为 skill 要求再加 3 个专项回归测试）。

### 3.2 必须新增的 P0 专项回归测试
1. **并发配额不超卖**（`test_quota_concurrent_not_oversold`）：把临时 limit 压到 5，20 条并发 await；断言 used==5、success==5、error==15。
2. **token_valid_since 黑名单**（`test_token_valid_since_blacklist`）：先 issue_tokens → `valid_since = iat+1.0` → `_enforce_token_valid_since` 抛 401 且含「改密/挂失」字样；valid_since 回退后新发 token 放行。
3. **食材懒更新 SQL 原子性**（`test_ingredient_lazy_expire_logic_smoke`）：SQLite 内存库造 3 条 fixture（过期/未过期/used_up）→ 执行等价 UPDATE → 只有过期的 `available` 变成 `expired`，`used_up` 不变。

### 3.3 E2E HTTP 烟测（sqlite smoke 模式）
使用临时 sqlite：`DB_TYPE=sqlite DB_NAME=foodtime_p0_smoke APP_ENV=test uvicorn main:app --port 8001`。按顺序打：

| # | 请求 | 期望 |
|---|---|---|
| 1 | `GET /` → SPA fallback 200 | body 包含 Vue 渲染锚点 `<div id="app">`（或字节数 ≥ 1KB） |
| 2 | `POST /api/auth/register` username 随机 | 返回 token，`code==0`；后续调用均用该 access 鉴权 |
| 3 | `GET /api/auth/me` | `data.user_id` == register 返回的 user_id，`quota.recipe.used==0` |
| 4 | `POST /api/recipes/recommend` 送西红柿+鸡蛋+大米 | 即使走 mock_fallback，`recipes[*].id` 非空（UUID），`prompt_hash` 非空 |
| 5 | `POST /api/diary/cook` 携带 `ai_recommend_id = recipes[0].id` | `code==0`，后端日志中不应出现外键违反；数据库查 cook_records.ai_recommend_id 非空 |
| 6 | `POST /api/auth/password` 成功 | `changed:true`，user.token_valid_since 被推到当前时间附近 |
| 7 | 步骤 3 再次用 **旧 access** 调用 `/api/auth/me` | **必须 401**，detail 含「改密/挂失失效」 |
| 8 | 用 **旧 refresh** 调 `/api/auth/refresh` | **必须拒绝**，返回 `AUTH_EXPIRED` 或同等 401/过期错误，不得换新 token |
| 9 | 并发 20 次请求 `POST /recipes/recommend` 后再 `GET /auth/me` | `quota.recipe.used <= LLM_RECIPES_QUOTA`，绝不超上限（验证锁）。 |

---

## 4. 验收门禁（必须全部满足才算 P0 修复完成）

- [ ] `pytest tests/ -v` 全绿；且至少包含本节 §3.2 的 3 个新测试。
- [ ] E2E 9 条烟测全通过（尤其步骤 7/8 的旧 token 拒绝、步骤 9 的配额不超上限）。
- [ ] grep `backend/.env` `backend/**/*.py` 不含任何真实 `sk-`、`DASHSCOPE_API_KEY` 明文。
- [ ] 仓库根有 `.gitignore`，且实际 `.env` / `.env.local` / `logs/` / `venv/` / `*.db` 在忽略列表。
- [ ] 生产启动 log 首屏不再出现「SECRET_KEY 使用了占位默认值」之外的风险提示；若有则开发者已手动在 `.env.local` 填入真 key。
- [ ] 改动至少回写一处 `# P0-x 修复:` 注释以便后来者快速定位。

---

## 5. 常见陷阱与避坑（来自真实修复记录）

1. **SQLAlchemy 条件组合陷阱**：`(col == x) | ((python_bool) & (col == y))` 会因 `bool & BinaryExpression` 报 TypeError。**统一用 `sqlalchemy.and_ / or_`**，Python 层先拼 filter list 再展开。
2. **慢路径 JWT iat 类型**：`python-jose` 默认给的 `iat` 是 naive datetime，而 `token_valid_since` 是 float 秒 → 直接比会错。**在签发时额外落一个 `iat_ts: int` 字段**，黑名单一律比对 `iat_ts`。
3. **RecipeCache 缓存污染**：换一换（exclude_recipes）写入的结果一定不能污染「同 prompt 不带 exclude」的正常推荐。要么 hash 带 exclude，要么 exclude 请求不读/不写缓存。
4. **session 创建即扣 CHAT 配额**：会导致「LLM 全挂走 mock」或「5 轮用户中途取消」都扣一次额度，用户投诉会炸。**挪到最终推荐 commit 成功后再扣**；失败不扣。
5. **Windows PowerShell CLI 复现 HTTP 请求时的编码噪音**：直接 `Invoke-RestMethod` 的 error stream 会带 CLIXML 前缀干扰诊断；拿真实响应体优先读 `Exception.Response.GetResponseStream()` 或写脚本用 python httpx 调用，减少被 shell 别名/转义污染。
6. **改 `User` 模型加列后的兼容性**：DEBUG=true 时 `Base.metadata.create_all(engine)` 对已有表不会自动加列（它是 CREATE IF NOT EXISTS，ALTER 不会做）。生产必须用 alembic 或手动跑 `ALTER TABLE users ADD COLUMN token_valid_since FLOAT NOT NULL DEFAULT 0;` 一次；个人 dev 删 sqlite 文件重来即可（skill 验收步骤 §3.3 使用临时 smoke db，天然 OK）。
