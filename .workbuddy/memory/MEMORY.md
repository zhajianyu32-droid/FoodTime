# FoodTime 项目速查（架构知识库）

## 总览
"FoodTime 食光"——独居青年吃饭决策助手。三服务：MySQL 8(3306) / FastAPI 后端(8000) / Vue3+Vite 前端(5173)。启动方式见根目录 Start.txt（本地运行，非 docker；docker-compose.yml 为备用容器化方案，DB 名 meiweichuzuwu/密码 meiwei2026）。本地 .env 数据库名 Gourmet_House_test。

## 后端 backend/（FastAPI 单文件路由）
- 栈：FastAPI 0.115 + SQLAlchemy 2.0 **同步** + PyMySQL + Pydantic v2 + slowapi 限流 + python-jose JWT(HS256) + httpx/tenacity 调 LLM。
- 关键文件：main.py（全部 ~30 个 /api 路由，auth 146、recipes/recommend 511、diary/stats|heatmap|list、chat、fortune、shopping、ingredients）、config.py(BaseSettings，env/.env.local，SECRET_KEY 占位符检测)、database.py(连接池 pool_size=10)、errors.py(BizError+ERR 错误码 1xxx参数/2xxx认证/3xxx资源/4xxxLLM/5xxx内部)、quota_limiter.py(限流 IP 级 + 每日 LLM 配额持久化 QuotaUsage)、security.py(bcrypt+JWT access7d/refresh30d, HTTPBearer)。
- models.py 11 张表（User/UserPreference/Ingredient/CookRecord/TakeoutRecord/ChatTurn/DailyFortune/ShoppingItem/PreferenceWeight/RecipeCache/ChatSession/QuotaUsage），均 FK→users.id ondelete CASCADE。
- services/：llm_service(DeepSeek+DashScope 通义千问双 provider 故障转移+熔断+mock 兜底)、recipe_service(RecipeCache 24h)、chat_service(5 轮状态机)、fortune_service(每日缓存)、preference_service(权重公式 newW=old*0.7+score*0.3)。
- migrations/auto_migrate_mysql.py：无 Alembic，幂等 ALTER 迁移。tests/ 强制 sqlite 内存库。
- 统一响应 {code,message,data,trace_id}，成功 code=0；配额 recipe30/fortune2/chat10 每日。

## 前端 frontend/（Vue3 SPA）
- 栈：Vue 3.5 + Vite 6 + vue-router4(**hash 模式**) + Tailwind v4(CSS-first @theme) + shadcn-vue 风格组件(reka-ui 底层) + vue-sonner。**无 Pinia**，用 composable 模块级单例做 store。
- vite 代理 /api /docs /openapi.json → 127.0.0.1:8000；别名 @→src。
- 视图(全部需登录除 login/register)：/dashboard /cook(食材拖拽+菜谱推荐) /order(运势+对话) /diary(美食日记) /shopping /ingredients /settings /about。
- composables/：useApi(原生 fetch，token localStorage ft_at/ft_rt，401 自动 refresh 重放，解包 data.data??data)、useAuth/useDiary/useCook/useOrder/useShopping/useSettings/useQuota/useToast。
- 组件：src/components/ui/{button,input,card,badge,tabs,table,dialog,select,checkbox,progress,accordion,scroll-area,separator,textarea,sonner}；布局仅 AppLayout.vue(桌面 w-60 侧边栏 hidden md:flex / 移动顶栏)。
- 样式：stone 冷灰基底，--primary 24 10% 20%，token 类 bg-card/text-muted-foreground 等；响应式以 md:768px 分界。

## 修改惯例
- **【强制流程】任何代码修改任务动手前，必须先读取 agent/skills/grilling/SKILL.md 并执行 grilling 流程**：把修改目标拆成设计树，按轮次向用户提问（每轮列全当前可问的问题、编号、附推荐答案 ➡️），等用户答复后再进下一轮；事实自己去查（子代理/读代码），决策必须问用户；frontier 清空、用户确认共识后才动手改代码。这是用户 2026-09-12 明确要求的固定工作流，小改动也不例外（用户当次明确说"直接改"时可跳过）。
- 改后端接口：main.py 内对应行号区段 + schemas.py + 必要时 models.py（改表后跑 migrations/auto_migrate_mysql.py）。
- 改前端页面：对应 views/*.vue + 其 composable(useXxx.js)；API 调用走 useApi 的 api() 封装。
- agent/ 目录是 AI 助手 skills 文档（非运行代码）；Knowledge/ 是需求/开发指南/用户手册文档；sql/ 是建库与种子脚本。
