# FoodTime 接入 shadcn-vue 迁移计划

## Context

当前前端是单 HTML 文件 + CDN Vue 3，无构建工具、无 package.json。用户要求接入 shadcn/ui 组件库（Vue 版即 shadcn-vue）。需搭建 Vite + Vue 3 + Tailwind v4 工程，初始化 shadcn-vue，迁移路由/认证/Dashboard 等核心链路。

**决策**：切换到 shadcn 默认风格（废弃像素风），主流程不变但可适当精简。

## 实施步骤

### 阶段 0：脚手架 + 基础设施

1. **备份旧前端**
   - `frontend/index.html` → `frontend/legacy/index.html`（作为迁移对照参考）

2. **初始化 Vite + Vue 项目**（在 `frontend/` 目录内）
   ```bash
   npm create vite@latest . -- --template vue
   ```
   - 安装依赖：`npm install`
   - 安装 Tailwind v4：`npm install tailwindcss @tailwindcss/vite`

3. **配置 `frontend/vite.config.js`**
   - Tailwind 插件
   - `@` → `./src` 路径别名
   - dev server `port: 5173`
   - proxy `/api`、`/docs`、`/openapi.json` → `http://127.0.0.1:8000`

4. **配置 `frontend/jsconfig.json`**
   - `baseUrl: "."`、`paths: { "@/*": ["./src/*"] }`

5. **初始化 shadcn-vue**
   ```bash
   npx shadcn-vue@latest init
   ```
   - TypeScript: No
   - Style: Vega
   - Base color: Stone
   - CSS file: `src/assets/index.css`
   - Components alias: `@/components`
   - Utils alias: `@/lib/utils`

6. **创建 `frontend/.env`**：`VITE_API_BASE=/api`
7. **创建 `frontend/.gitignore`**：`node_modules/ dist/ .vite/ *.local`

8. **修改 `backend/main.py`（约 L1215）**
   - `_FRONTEND_INDEX` 指向 `frontend/dist/index.html`
   - 若 `dist/` 不存在则回退 `frontend/legacy/index.html`（dev 未构建时仍可用旧页面）
   - `_SPAApp` 本身无需改动

9. **验证**：`npm run dev`（5173）+ 后端 8000 → `fetch('/api/health')` 返回 ok

### 阶段 1：骨架 + 登录注册

**新增文件**：
- `src/router/index.js` — `createWebHashHistory()` + 10 条路由 + Auth Guard（复刻旧 hash 路由）
- `src/composables/useApi.js` — 搬 `api()` + 401 refresh + 重放 + `data.message||detail||error` 三字段解析
- `src/composables/useAuth.js` — 搬 `TOK` + login/register/refresh/me/logout
- `src/composables/useToast.js` — 封装 sonner
- `src/App.vue` — `<RouterView/>` + `<Toaster/>`
- `src/main.js` — createApp + use(router) + import index.css
- `src/views/LoginView.vue` / `src/views/RegisterView.vue`

**shadcn 组件**：
```bash
npx shadcn-vue@latest add button input label card sonner
```

**迁移要点**：
- Hash 路由 `#/login` `#/register` 保持兼容
- Auth Guard：未登录访问私域路由 → 跳 `#/login` + 存 `sessionStorage.ft_redirect`
- `useApi.js` 保留 `data?.code` 解包逻辑 + `error` 字段兼容
- 错误展示用 `{{ }}` 文本插值（自动转义防 XSS）

**验证**：登录拿 token → `/api/auth/me` 通 → 跳 `#/dashboard`

### 阶段 2：Dashboard

**新增文件**：
- `src/composables/useQuota.js` — 复刻 `recipeQuotaPercent`/`fortuneQuotaPercent`/`chatQuotaPercent`
- `src/composables/useIngredients.js` — 复刻 `expiredCount`/`expiringCount`
- `src/composables/useShopping.js` — 复刻 `shoppingPendingCount`/`shoppingCheckedCount`
- `src/views/DashboardView.vue`

**shadcn 组件**：
```bash
npx shadcn-vue@latest add card progress badge
```

**迁移要点**：
- 用 `<Card>` 替换旧 `.card`
- 用 `<Progress>` 替换旧配额进度条
- 用 `<Badge>` 替换旧 `.badge-*`
- 适当精简：Dashboard 只保留配额卡片 + 食材/购物统计概览，不做完整旧版复刻

**验证**：登录后 `#/dashboard` 展示配额卡片 + 统计数据

### 后端改动文件

- `backend/main.py`（L1208-1245 `_SPAApp` 挂载路径改为 dist + legacy 回退）

### 新建文件总览

```
frontend/
├── legacy/index.html          # 原 2598 行备份
├── src/
│   ├── assets/index.css       # @import "tailwindcss" + shadcn 主题
│   ├── components/ui/         # shadcn-vue 生成
│   ├── composables/
│   │   ├── useApi.js
│   │   ├── useAuth.js
│   │   ├── useToast.js
│   │   ├── useQuota.js
│   │   ├── useIngredients.js
│   │   └── useShopping.js
│   ├── views/
│   │   ├── LoginView.vue
│   │   ├── RegisterView.vue
│   │   └── DashboardView.vue
│   ├── router/index.js
│   ├── lib/utils.js
│   ├── App.vue
│   └── main.js
├── components.json
├── index.html
├── package.json
├── vite.config.js
├── jsconfig.json
├── .env
└── .gitignore
```

## 验证方法

1. **dev 模式**：`cd frontend && npm run dev` → 访问 `http://localhost:5173/`
2. **后端联动**：后端 8000 运行中，Vite proxy `/api` 通畅
3. **登录链路**：注册新用户 → 登录 → 跳 Dashboard → 配额卡片展示
4. **旧页面兼容**：`http://127.0.0.1:8000/app/` 仍可访问旧版（legacy 回退）
5. **生产构建**：`npm run build` → `frontend/dist/` → 后端 `/app/` 加载新版
