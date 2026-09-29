import { T, Doc, CONTENT_X, CONTENT_W, pageHeader, card, badge, chip, button, outlineButton, ghostButton, field, tabs, progress, sectionTitle, sidebar, measure } from "./kit.mjs";

export const W = 1440, H = 900;

/** 自动换行的标签组，返回下一个 y */
export function chipRow(d, x, y, maxWidth, items, selected, o = {}) {
  const gap = o.gap ?? 8, lineH = o.lineH ?? 32;
  let cx = x, cy = y;
  items.forEach((label, i) => {
    const w = Math.round(measure(label, 13, selected.has(label) ? 500 : 400)) + 20;
    if (cx > x && cx + w > x + maxWidth) { cx = x; cy += lineH; }
    chip(d, cx, cy, label, { selected: selected.has(label) });
    cx += w + gap;
  });
  return { y: cy + lineH, x: cx };
}

/* ============================ 登录 ============================ */
export function screenLogin() {
  const d = new Doc("登录", W, H);
  d.rect("登录卡片", (W - 420) / 2, 190, 420, 348, { fill: T.card, stroke: T.border, rx: 8 });
  const x = (W - 420) / 2 + 24, iw = 420 - 48;
  d.text("标题", x, 236, "登录", { size: 24, weight: 700 });
  d.text("副标题", x, 262, "登录食光 FoodTime，开启你的美食决策之旅", { size: 14, fill: T.mutedFg });
  field(d, "用户名", x, 288, iw, "用户名", { placeholder: "3-50位中英数字下划线" });
  field(d, "密码", x, 356, iw, "密码", { placeholder: "至少 6 位" });
  button(d, "登录按钮", x, 428, iw, 40, "登录");
  d.text("注册引导", x, 500, "还没有账户？", { size: 14, fill: T.mutedFg });
  d.text("注册链接", x + measure("还没有账户？", 14), 500, "立即注册", { size: 14, weight: 500, fill: T.primary });
  return d;
}

/* ============================ 注册 ============================ */
export function screenRegister() {
  const d = new Doc("注册", W, H);
  d.rect("注册卡片", (W - 420) / 2, 140, 420, 410, { fill: T.card, stroke: T.border, rx: 8 });
  const x = (W - 420) / 2 + 24, iw = 420 - 48;
  d.text("标题", x, 186, "注册", { size: 24, weight: 700 });
  d.text("副标题", x, 212, "创建账户，开始记录你的每一餐", { size: 14, fill: T.mutedFg });
  field(d, "用户名", x, 238, iw, "用户名", { placeholder: "3-50位中英数字下划线" });
  field(d, "手机号", x, 306, iw, "手机号（选填）", { placeholder: "可留空" });
  field(d, "密码", x, 374, iw, "密码", { placeholder: "至少 6 位" });
  button(d, "注册按钮", x, 446, iw, 40, "注册");
  d.text("登录引导", x, 518, "已有账户？", { size: 14, fill: T.mutedFg });
  d.text("登录链接", x + measure("已有账户？", 14), 518, "返回登录", { size: 14, weight: 500, fill: T.primary });
  return d;
}

/* ============================ 仪表盘 ============================ */
export function screenDashboard() {
  const d = new Doc("仪表盘", W, H);
  sidebar(d, "dashboard");
  let y = pageHeader(d, "🏠 仪表盘", "欢迎回来，demo_pm");
  const gap = 16, cw = Math.round((CONTENT_W - gap * 2) / 3);
  const quotas = [
    { label: "菜谱推荐", val: "0 / 100", pct: 0 },
    { label: "美食运势", val: "0 / 100", pct: 0 },
    { label: "对话次数", val: "0 / 100", pct: 0 },
  ];
  quotas.forEach((q, i) => {
    const x = CONTENT_X + i * (cw + gap);
    card(d, "配额卡片 " + q.label, x, y, cw, 124);
    d.text("配额名称 " + q.label, x + 16, y + 34, q.label, { size: 12, fill: T.mutedFg });
    d.text("配额数值 " + q.label, x + 16, y + 64, q.val, { size: 24, weight: 700 });
    progress(d, x + 16, y + 82, cw - 32, q.pct);
    d.text("配额百分比 " + q.label, x + 16, y + 108, "已使用 " + q.pct + "%", { size: 12, fill: T.mutedFg });
  });
  y += 124 + gap;
  const hw = Math.round((CONTENT_W - gap) / 2);
  const stats = [
    { name: "🧊 食材库", a: ["3", "已过期", T.destructive], b: ["2", "即将过期", T.yellow600] },
    { name: "🛒 购物单", a: ["5", "待购买", T.fg], b: ["1", "已购买", T.green600] },
  ];
  stats.forEach((s, i) => {
    const x = CONTENT_X + i * (hw + gap);
    card(d, "统计卡片 " + s.name, x, y, hw, 128);
    d.text("统计标题 " + s.name, x + 16, y + 36, s.name, { size: 16, weight: 600 });
    [[s.a, 0], [s.b, 1]].forEach(([blk, k]) => {
      const bx = x + 16 + k * 96;
      d.text("统计数值 " + blk[1], bx, y + 84, blk[0], { size: 24, weight: 700, fill: blk[2] });
      d.text("统计名称 " + blk[1], bx, y + 106, blk[1], { size: 12, fill: T.mutedFg });
    });
  });
  y += 128 + gap;
  const navs = [
    { name: "🍳 Cook Mode", desc: "从冰箱食材出发，获取 AI 菜谱推荐" },
    { name: "🛵 Order Mode", desc: "抽取美食运势，与 AI 对话获取外卖推荐" },
  ];
  navs.forEach((n, i) => {
    const x = CONTENT_X + i * (hw + gap);
    card(d, "入口卡片 " + n.name, x, y, hw, 96);
    d.text("入口标题 " + n.name, x + 16, y + 38, n.name, { size: 16, weight: 600 });
    d.text("入口描述 " + n.name, x + 16, y + 62, n.desc, { size: 12, fill: T.mutedFg });
  });
  return d;
}

/* ============================ 关于 ============================ */
export function screenAbout() {
  const d = new Doc("关于", W, H);
  sidebar(d, "about");
  let y = pageHeader(d, "📖 关于", "了解 FoodTime 背后的故事与技术栈");
  card(d, "项目信息卡片", CONTENT_X, y, CONTENT_W, 268);
  d.text("项目名称大标题", CONTENT_X + 24, y + 42, "食光 FoodTime", { size: 24, weight: 700 });
  d.text("项目副标题", CONTENT_X + 24, y + 66, "独居青年吃饭决策助手", { size: 14, fill: T.mutedFg });
  const rows = [
    ["项目名称", "FoodTime · 食光"], ["版本", "v0.1.0"], ["后端", "FastAPI + SQLAlchemy"],
    ["前端", "Vue 3 + shadcn-vue"], ["运行环境", "Python 3.12 (dev)"], ["许可", "MIT"],
  ];
  rows.forEach((r, i) => {
    const col = i % 3, row = Math.floor(i / 3);
    const x = CONTENT_X + 24 + col * 328, yy = y + 104 + row * 62;
    d.text("信息标签 " + r[0], x, yy, r[0], { size: 12, fill: T.mutedFg });
    d.text("信息内容 " + r[0], x, yy + 22, r[1], { size: 14, weight: 500 });
  });
  d.text("技术栈小标题", CONTENT_X + 24, y + 226, "技术栈", { size: 12, weight: 500, fill: T.mutedFg });
  let tx = CONTENT_X + 24;
  ["FastAPI", "Vue 3", "SQLAlchemy", "Tailwind CSS", "shadcn-vue", "LLM"].forEach(t => { tx += badge(d, tx, y + 234, t, { variant: "outline" }) + 8; });
  y += 268 + 16;
  card(d, "核心能力卡片", CONTENT_X, y, CONTENT_W, 250);
  d.text("能力标题", CONTENT_X + 24, y + 38, "核心能力", { size: 18, weight: 600 });
  d.text("能力副标题", CONTENT_X + 24, y + 60, "FoodTime 提供的几大场景化能力", { size: 12, fill: T.mutedFg });
  const caps = [
    "🍳 Cook Mode：选冰箱食材 → AI 推荐菜谱，一键记录做饭或加入购物单补货",
    "🛒 购物清单：按推荐菜谱缺料自动生成，勾选已购即同步入库",
    "🥡 外卖决策：和 AI 对话几轮，让 LLM 推荐今天点什么外卖",
    "🥬 食材管理：冰箱食材统一登记，自动临期/过期提醒",
    "📖 美食日记：做饭/外卖记录沉淀，生成偏好权重与饮食热力图",
    "⚙️ 偏好档案：星座/属相/MBTI/口味/菜系/厨具/忌口三层树",
  ];
  caps.forEach((c, i) => d.text("能力 " + (i + 1), CONTENT_X + 24, y + 92 + i * 26, c, { size: 13 }));
  return d;
}