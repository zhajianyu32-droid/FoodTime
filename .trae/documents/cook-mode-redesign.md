# Cook Mode 重构方案

## Context

当前 CookView 采用"左侧食材篮 + 右侧菜谱列表"的简单点击交互。用户希望升级为更直观的拖拽式交互：上方待选池 + 下方 2D 可交互冰箱 + 做菜区，让做饭流程更具沉浸感。

## 布局设计

```
┌──────────────────────────────────────────────────────┐
│  Header: Cook Mode                                   │
├──────────────────────────────────────────────────────┤
│  待选池 (Candidate Pool)                              │
│  [输入框] [+ 添加]                                    │
│  [tag1] [tag2] [tag3] ...  ← 可拖拽                  │
├────────────────────┬─────────────────────────────────┤
│  2D 冰箱            │  做菜区                          │
│  ┌────────────────┐│  ┌─────────────────────────────┐│
│  │ ❄️ 冷冻层       ││  │ 拖入食材到此区域              ││
│  │ [tag] [tag]    ││  │ [tag1] [tag2]               ││
│  ├────────────────┤│  │                             ││
│  │ 🥬 冷藏层       ││  │ [🤖 生成菜谱]                ││
│  │ [tag] [tag]    ││  │                             ││
│  └────────────────┘│  │ ── 菜谱结果 ──              ││
│                    │  │ [菜谱卡片1] [菜谱卡片2]      ││
│                    │  └─────────────────────────────┘│
└────────────────────┴─────────────────────────────────┘
```

## 技术方案

### 1. 拖拽实现：原生 HTML5 DnD
- 无需安装额外库（项目未安装 vuedraggable/sortablejs）
- 使用 `draggable="true"` + `@dragstart` + `@dragover.prevent` + `@drop` 事件
- 通过 `dataTransfer` 传递食材 ID，通过 reactive 变量记录拖拽源 zone

### 2. Zone 状态管理（前端本地）
后端 Ingredient 模型无 location 字段，zone 分配仅在前端管理：
- `zoneMap = reactive({})` — Map<ingredientId, 'pool'|'freezer'|'fridge'|'cooking'>
- `dragSource = ref(null)` — 当前拖拽源的 zone 名
- `dragIngId = ref(null)` — 当前拖拽的食材 ID
- 基于 zoneMap 用 computed 派生各 zone 的食材列表

### 3. 数据流
- `loadIngredients()` 加载后 → 所有食材默认分配到 `pool`（待选池）
- 用户在输入框添加新食材 → `addIngredient()` 后也进入 `pool`
- 拖拽到 `freezer` / `fridge` / `cooking` → 更新 zoneMap
- 点击"生成菜谱" → 取 `cooking` zone 的食材名列表 → 调用 `recommendRecipes()`
- 菜谱结果仍使用现有 Dialog 展示详情

### 4. 2D 冰箱视觉
CSS 实现，不使用图片：
- 外框：圆角边框 + 阴影，模拟冰箱外壳
- 分隔线：中间横线分隔上下两层
- 冷冻层（上）：浅蓝背景 `bg-blue-50`，标题带 ❄️ 图标
- 冷藏层（下）：浅绿背景 `bg-green-50`，标题带 🥬 图标
- 拖拽悬停时：虚线边框 + 高亮背景 `ring-2 ring-primary`

### 5. 食材标签样式
- 可拖拽的 chip/tag 组件
- 显示名称 + 数量
- 临期食材显示黄色警告
- 过期食材显示红色 + 不可拖入做菜区

## 修改文件

| 文件 | 修改内容 |
|------|---------|
| `frontend/src/views/CookView.vue` | 完全重写 template + script，实现新布局和拖拽逻辑 |
| `frontend/src/composables/useCook.js` | 修改 `recommendRecipes` 使用 cooking zone 食材；添加 zone 状态管理 |

## 验证方案

1. 访问 `http://localhost:5173/#/cook`，确认上下两段布局正确渲染
2. 在待选池输入食材名 → 点添加 → 标签出现在待选池
3. 拖拽标签到冰箱冷冻层 → 标签出现在冷冻层
4. 拖拽标签到冰箱冷藏层 → 标签出现在冷藏层
5. 拖拽标签到做菜区 → 标签出现在做菜区
6. 在做菜区点击"生成菜谱" → AI 返回菜谱列表
7. 点击菜谱卡片 → 弹出详情 Dialog
8. 检查浏览器控制台无错误
