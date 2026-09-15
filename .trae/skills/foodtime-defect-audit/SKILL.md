---
name: "foodtime-defect-audit"
description: "FastAPI + Vue3 单体应用的系统级缺陷审计与修复指南。Invoke when 需要审计 FastAPI+SQLAlchemy+Vue 项目的安全/并发/数据一致性缺陷，或修复类似技术栈的 P0/P1/P2 级问题。"
---

# FoodTime 缺陷审计与修复经验

本 Skill 沉淀了 FastAPI + SQLAlchemy + MySQL + Vue3 单文件前端架构的系统级缺陷审计方法论、典型缺陷模式与修复规范。

## 适用场景

- 审计 FastAPI 后端的安全/授权/输入校验/异常处理
- 审计 Vue3 单文件前端的路由守卫/XSS/API 调用
- 审计 SQLAlchemy 模型的索引/约束/分页性能
- 修复密钥泄露、并发超卖、堆栈泄露、CRUD 缺失等典型缺陷

---

## 一、审计方法论（五维度并行）

### 1. 后端 API 审计清单

| 检查项 | 方法 | 常见缺陷 |
|--------|------|---------|
| 认证/授权 | 确认每个私域路由都有 `get_current_user` + `require_owner` | 遗漏 require_owner 导致水平越权 |
| 输入校验 | 检查 Pydantic schema 的 Field 约束、page_size 上限 | page_size 无上限导致 OOM |
| 异常处理 | 检查 errors.py 的 exception_handler 是否泄露堆栈 | DEBUG=true 时返回 traceback |
| CRUD 完整性 | 逐个核对前端调用的 HTTP method 是否后端都有实现 | DELETE 接口缺失，前端 catch 吞错 |
| SQL 注入 | 全量使用 ORM，禁查 `text()` 拼接用户输入 | 无（ORM 项目通常安全） |

### 2. 前端审计清单

| 检查项 | 方法 | 常见缺陷 |
|--------|------|---------|
| 路由守卫 | 确认私域路由无 token 时跳 login，登录后回跳 intent | 守卫绕过或回跳丢失 |
| XSS | 搜索 `v-html`、`innerHTML`、`document.write` | innerHTML 拼接未转义 |
| API 重放 | 检查 401 refresh 后重放是否传 raw/token 参数 | 重放丢失 body 或 raw 参数 |
| 错误吞没 | 搜索 `catch(_){}` 或空 catch 块 | 删除/更新失败被静默吞掉 |
| localStorage | 检查 token 存储 key 命名一致性 | 存入 key 与读取 key 不匹配 |

### 3. 数据库审计清单

| 检查项 | 方法 | 常见缺陷 |
|--------|------|---------|
| 索引 | 检查所有 `user_id` 外键字段是否有 Index | 全表扫描慢查询 |
| 唯一约束 | 检查缓存表 prompt_hash、每日运势 (user_id, date) | 重复插入导致数据膨胀 |
| 时区 | 检查 `_now()` 是否带时区，与 JWT 的 UTC 时间是否混用 | naive vs aware datetime 比较偏差 |
| onupdate | 检查 updated_at 字段是否有 `onupdate=_now` | UPDATE 时 updated_at 不刷新 |
| 内存分页 | 检查是否有 `.all()` 后 Python 切片分页 | 数据量大时 OOM |

### 4. 安全审计清单

| 检查项 | 方法 | 常见缺陷 |
|--------|------|---------|
| 密钥管理 | 确认 SECRET_KEY 不在 .env 中明文，使用 .env.local | .env 提交到 git 导致密钥泄露 |
| CORS | 检查 CORS_ORIGINS 是否含 `null` | null origin 可被恶意页面伪造 |
| 限流 | 确认 slowapi 在所有环境启用 | DEBUG 下禁用导致暴力枚举 |
| 配额持久化 | 确认配额计数不只在内存 | 重启清零可被绕过 |

### 5. 并发审计清单

| 检查项 | 方法 | 常见缺陷 |
|--------|------|---------|
| 配额超卖 | 检查 consume_quota 是否有 per-(user,kind) Lock | check-then-act 竞态 |
| 死锁 | 检查 sync 函数是否在 async 上下文用 `run_coroutine_threadsafe` | 同事件循环内死锁 |
| 锁池膨胀 | 检查锁池是否有上限清理机制 | 长期运行 OOM |

---

## 二、典型缺陷修复模式

### P0-1: 敏感配置泄露

**模式**: `.env` 中明文存储 DB_PASSWORD / SECRET_KEY / API_KEY
**修复**:
1. 创建 `.env.local`（已被 .gitignore 排除），将真实密钥移入
2. `.env` 中对应值留空或用占位符
3. `config.py` 中 `env_file=(".env", ".env.local")`，后者覆盖前者
4. 生成 SECRET_KEY: `python -c "import secrets; print(secrets.token_hex(32))"`
5. 检查 git 历史: `git log --oneline -- .env`，若有记录需 `git filter-branch`

**校验规则**:
- [ ] `.env` 中不含真实密码/密钥
- [ ] `.env.local` 已在 `.gitignore` 中
- [ ] SECRET_KEY 长度 ≥ 64 hex chars
- [ ] `config.py` 的 env_file 顺序为 `.env` → `.env.local`

### P0-2: CRUD 接口缺失

**模式**: 前端调用 `DELETE /api/resource/{id}` 但后端只有 GET/POST/PUT
**修复**:
1. 后端补全缺失的 DELETE 路由
2. 路由内先查资源是否存在 → 404
3. 再调 `require_owner(resource.user_id, current_user)` 防越权
4. `db.delete()` + `db.commit()` + rollback 保护
5. 前端移除 `catch(_){}` 吞错，改为 `catch(e) { showToast(e.message,'error') }`

**校验规则**:
- [ ] 后端每个资源都有完整的 CRUD（或明确文档标注哪些不支持）
- [ ] 前端无 `catch(_){}` 空吞错误
- [ ] DELETE 路由有 require_owner 鉴权

### P0-3: 堆栈信息泄露

**模式**: `errors.py` 在 `DEBUG=True` 时返回 `traceback.format_exc()` 给前端
**修复**:
1. 移除 middleware 中的 `payload["data"] = {"type": ..., "detail": str(exc)}`
2. 移除 catch_all 中的 `payload["data"] = {"trace": traceback.format_exc()}`
3. 无论 DEBUG 与否，始终返回通用 "服务繁忙，请稍后再试"
4. 堆栈仅写入服务端日志（`logger.exception()`）

**校验规则**:
- [ ] 500 响应 body 不含 `trace`、`Traceback`、`detail`、SQL 语句
- [ ] 服务端日志中保留完整堆栈

### P1-1: 内存分页 → SQL 分页

**模式**: `.all()` 加载全量记录后 Python 切片
**修复**:
1. 用 `union_all` 合并 cook + takeout 查询
2. `.count()` 获取总数
3. `.offset((page-1)*page_size).limit(page_size)` SQL 分页
4. 再按分页后的 ID 批量 `IN` 查询完整记录
5. 按 page_rows 顺序排列结果

**校验规则**:
- [ ] 无 `.all()` 后 Python 切片分页
- [ ] 分页接口返回 `page.total` 准确
- [ ] `page_size` 参数有 `le=100` 上限

### P1-2: 热力图内存聚合 → SQL 轻量查询

**模式**: `.all()` 加载整月记录后 Python 聚合
**修复**:
1. 改为 `db.query(func.day(CreatedAt).label("d"), dish_name, rating)` 只取必要列
2. `.order_by(created_at.asc())` 确保首条记录优先
3. Python 端只需遍历轻量结果集做去重

**校验规则**:
- [ ] 聚合查询不加载完整 ORM 对象
- [ ] 只 SELECT 业务需要的列

### P1-3: 数据库索引缺失

**模式**: 所有 `user_id` 外键字段无显式 Index
**修复**:
```python
class Ingredient(Base):
    __tablename__ = "ingredients"
    __table_args__ = (
        Index("ix_ingredients_user_id", "user_id"),
        Index("ix_ingredients_user_status", "user_id", "status"),
    )
```
对以下表添加索引:
- `ingredients(user_id, status)` — 按用户+状态筛选
- `cook_records(user_id, created_at)` — 按用户+时间查日记
- `takeout_records(user_id, created_at)` — 同上
- `shopping_items(user_id)` — 购物单列表
- `chat_sessions(user_id)` — 对话历史
- `recipe_cache(user_id)` + `UniqueConstraint(prompt_hash)` — 缓存命中
- `daily_fortunes(user_id, date)` UniqueConstraint — 每日运势唯一

**校验规则**:
- [ ] 所有 `user_id` 外键字段有索引
- [ ] 缓存表 prompt_hash 有唯一约束
- [ ] 迁移脚本执行无报错

### P1-4: 配额仅存内存 → DB 持久化

**模式**: `_daily_usage = defaultdict(...)` 存内存，重启清零
**修复**:
1. 新增 `QuotaUsage` 模型: `(user_id, date, kind, used)` + UniqueConstraint
2. `consume_quota` 先从 DB 加载 used → +1 → 判断超限 → 写回 DB
3. `consume_quota_sync` 直接 DB 读写，不再通过 `run_coroutine_threadsafe`
4. `cleanup_old_days` 改为 SQL DELETE 而非内存 dict pop

**校验规则**:
- [ ] 重启后配额计数不归零
- [ ] `consume_quota_sync` 不使用 `run_coroutine_threadsafe`
- [ ] QuotaUsage 表有 `(user_id, date, kind)` 唯一约束

### P1-5: slowapi 限流禁用

**模式**: `enabled=not settings.DEBUG`，DEBUG 下完全关闭
**修复**:
1. 改为 `enabled=True` 始终启用
2. 移除 `default_limits`（slowapi 版本兼容性问题）
3. 移除装饰器上的 `key_func=lambda req: ...`（部分版本调用参数不符）
4. 使用默认 `get_remote_address` 作为 key_func

**校验规则**:
- [ ] limiter `enabled=True`
- [ ] 无 `default_limits` 参数
- [ ] 装饰器上无自定义 `key_func` lambda
- [ ] 登录接口 10/min、注册 5/min 限流生效

### P1-6: 前端 API refresh 重放丢参数

**模式**: `api(path, { method, body, raw })` 重放时未传 raw/token
**修复**:
```javascript
// 修复前
return api(path, { method, body, raw });
// 修复后
return api(path, { method, body, raw, token: TOK.A });
```

**校验规则**:
- [ ] refresh 重放时传入 `raw` 和新 `token`
- [ ] body 参数在重放中正确传递

### P2-1: updated_at 不自动刷新

**模式**: `updated_at = Column(DateTime, default=_now)` 仅 INSERT 设值
**修复**:
```python
updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)
```

### P2-2: innerHTML XSS

**模式**: `box.innerHTML = '...' + msg + '...'` 未转义
**修复**:
```javascript
var safeMsg = String(msg || '').replace(/[<>&"']/g, function(c) {
  return {'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'}[c];
});
```

### P2-3: consume_quota_sync 死锁

**模式**: `asyncio.run_coroutine_threadsafe(consume_quota(...), loop).result()` 在同事件循环内阻塞
**修复**: 改为直接 DB 读写，完全不经过 asyncio 调度

---

## 三、修复后自测流程

### API 级自测（浏览器内执行）

```javascript
// 1. 登录获取 token
// 2. CRUD 全流程: Create → Delete → 确认删除
// 3. 分页接口: 检查 page.total
// 4. 聚合接口: 检查返回天数
// 5. 配额接口: 检查 /auth/me 包含 quota
// 6. 堆栈屏蔽: 请求不存在的 endpoint，检查无 trace
```

### 前端自测

1. 登录 → 自动跳转仪表盘
2. 8 个路由全部渲染 hasMain=true
3. 购物单添加 → 删除（确认对话框 → 确认 → 列表清空）
4. Auth Guard: 未登录跳 login、登录后回跳 intent
5. 404 视图: 非法 hash 展示 404 页面

### 数据库迁移自测

1. 运行 `auto_migrate_mysql.py` 确认无报错
2. 重复索引/约束的 "skipped" 消息是正常的（幂等设计）
3. 唯一约束添加前需先清理重复数据
4. 确认 `quota_usage` 表已创建

---

## 四、迁移脚本注意事项

1. **幂等设计**: 所有 ALTER/CREATE 语句需 try-except 跳过已存在的对象
2. **唯一约束前置**: 添加 UniqueConstraint 前必须先 DELETE 重复行
3. **索引命名**: 统一 `ix_{table}_{columns}` 命名，便于后续维护
4. **外键约束**: MySQL 的外键名全局唯一，重复添加需 skip

---

## 五、缺陷优先级判定标准

| 级别 | 判定标准 | SLA |
|------|---------|-----|
| P0 | 安全漏洞/数据丢失/核心功能不可用 | 立即修复 |
| P1 | 性能隐患/逻辑缺陷/功能不完整 | 尽快修复 |
| P2 | 代码质量/健壮性/规范问题 | 建议修复 |
