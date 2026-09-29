import { T, Doc, CONTENT_X, CONTENT_W, card, badge, chip, button, outlineButton, ghostButton, field, tabs, progress, sidebar, measure } from "./kit.mjs";
import { W, chipRow } from "./screens-a.mjs";
const H = 900, LX = CONTENT_X + 24;

function header(d, title, sub, badges) {
  d.text("页面标题", CONTENT_X, 48, title, { size: 24, weight: 700 });
  d.text("页面副标题", CONTENT_X, 72, sub, { size: 14, fill: T.mutedFg });
  let bx = CONTENT_X + CONTENT_W;
  (badges || []).reverse().forEach(b => { const w = measure(b.t, 12) + 16; bx -= w + 8; badge(d, bx, 30, b.t, { variant: b.v }); });
  return 96;
}

/* ============================ Cook Mode ============================ */
export function screenCook() {
  const d = new Doc("Cook Mode", W, H);
  sidebar(d, "cook");
  let y = header(d, "🍳 Cook Mode", "拖拽食材到冰箱或做菜区，AI 智能推荐菜谱", [{ t: "临期 2", v: "default" }, { t: "已过期 3", v: "destructive" }]);
  const gap = 16, cw = Math.round((CONTENT_W - gap * 2) / 3), ch = 320;
  // 待选池
  card(d, "待选池卡片", CONTENT_X, y, cw, ch);
  d.text("待选池标题", LX, y + 30, "🧺 待选池", { size: 15, weight: 600 });
  badge(d, LX + 86, y + 16, "8 项", { variant: "secondary" });
  outlineButton(d, "添加食材按钮", CONTENT_X + cw - 96, y + 14, 80, 28, "+ 添加食材", { size: 12 });
  field(d, "待选池快填", LX, y + 52, cw - 48 - 56, null, { placeholder: "输入食材名，回车快速添加", h: 32 });
  button(d, "待选池添加按钮", LX + cw - 48 - 56 + 8, y + 52, 48, 32, "添加", { size: 12 });
  const pool = [["番茄", "剩 2 天"], ["鸡蛋", ""], ["青椒", ""], ["土豆", "剩 1 天"], ["米饭", ""], ["鸡胸肉", ""]];
  pool.forEach((p, i) => {
    const ry = y + 100 + i * 34;
    d.rect("待选项 " + p[0], LX, ry, cw - 48, 28, { fill: T.secondary, rx: 6 });
    d.text("待选项名 " + p[0], LX + 10, ry + 18, p[0], { size: 13 });
    if (p[1]) d.text("待选项提醒 " + p[0], LX + cw - 58, ry + 18, p[1], { size: 11, fill: T.yellow600, anchor: "end" });
  });
  // 冰箱
  const bx = CONTENT_X + cw + gap;
  card(d, "冰箱卡片", bx, y, cw, ch);
  d.text("冰箱标题", bx + 24, y + 30, "🧊 冰箱", { size: 15, weight: 600 });
  badge(d, bx + 84, y + 16, "6 项", { variant: "secondary" });
  [["❄️ 冷冻层", ["鸡胸肉", "虾仁"]], ["🥬 冷藏层", ["牛奶", "豆腐"]]].forEach(([t, items], k) => {
    const zy = y + 52 + k * 118;
    d.rect("层容器 " + t, bx + 24, zy, cw - 48, 106, { fill: T.bg, stroke: T.border, rx: 6 });
    d.text("层名称 " + t, bx + 36, zy + 22, t, { size: 12, weight: 500, fill: T.mutedFg });
    items.forEach((n, i) => {
      const ix = bx + 36 + i * 96;
      d.rect("冰箱食材 " + n, ix, zy + 34, 88, 28, { fill: T.card, stroke: T.border, rx: 6 });
      d.text("冰箱食材名 " + n, ix + 10, zy + 52, n, { size: 12 });
    });
  });
  d.text("冰箱拖拽提示", bx + 24, y + ch - 16, "↔ 拖拽食材在冷冻层和冷藏层之间移动", { size: 11, fill: T.mutedFg });
  // 做菜区
  const kx = CONTENT_X + (cw + gap) * 2;
  card(d, "做菜区卡片", kx, y, cw, ch);
  d.text("做菜区标题", kx + 24, y + 30, "🍳 做菜区", { size: 15, weight: 600 });
  d.text("做菜区说明", kx + 24, y + 50, "拖入食材后点击生成菜谱", { size: 11, fill: T.mutedFg });
  badge(d, kx + cw - 68, y + 16, "3 项", { variant: "default" });
  ["番茄", "鸡蛋", "青椒"].forEach((n, i) => chip(d, kx + 24 + i * 74, y + 66, n, { selected: true }));
  button(d, "生成菜谱按钮", kx + 24, y + 108, cw - 48, 36, "✨ 生成 AI 菜谱");
  const recipes = [["青椒肉丝", "15min · ¥8 · 简单"], ["番茄炒蛋", "10min · ¥5 · 简单"]];
  recipes.forEach((r, i) => {
    const ry = y + 158 + i * 78;
    d.rect("菜谱卡片 " + r[0], kx + 24, ry, cw - 48, 72, { fill: T.bg, stroke: T.border, rx: 6 });
    d.text("菜谱名 " + r[0], kx + 36, ry + 22, r[0], { size: 13, weight: 600 });
    d.text("菜谱元信息 " + r[0], kx + 36, ry + 40, r[1], { size: 11, fill: T.mutedFg });
    ghostButton(d, "菜谱详情按钮 " + r[0], kx + 36, ry + 46, 44, 22, "详情", { size: 12 });
    button(d, "记录做饭按钮 " + r[0], kx + cw - 108, ry + 46, 72, 22, "记录做饭", { size: 11 });
  });
  d.h = y + ch + 32;
  return d;
}

/* ============================ Order Mode ============================ */
export function screenOrder() {
  const d = new Doc("Order Mode", W, H);
  sidebar(d, "order");
  let y = header(d, "🛵 Order Mode", "抽今日美食运势卡，和 AI 聊 5 轮，拿专属外卖推荐", [{ t: "对话 5/5", v: "secondary" }, { t: "运势 1/1", v: "secondary" }]);
  d.text("运势小节标题", CONTENT_X, y + 6, "今日美食运势", { size: 13, weight: 600, fill: T.mutedFg });
  d.text("对话小节标题", CONTENT_X + 440, y + 6, "AI 对话推荐", { size: 13, weight: 600, fill: T.mutedFg });
  const cy = y + 22, fh = 600;
  // 运势卡（已翻面）
  card(d, "运势卡", CONTENT_X, cy, 404, fh);
  d.rect("卡牌背面", CONTENT_X + 24, cy + 24, 356, 300, { fill: T.primary, rx: 12 });
  d.text("卡牌宜忌标签 宜", CONTENT_X + 44, cy + 66, "宜", { size: 13, weight: 700, fill: T.onDarkGreen });
  d.text("卡牌宜内容", CONTENT_X + 72, cy + 66, "吃辣的、热乎的、一人食小馆", { size: 13, fill: T.primaryFg });
  d.text("卡牌忌标签 忌", CONTENT_X + 44, cy + 96, "忌", { size: 13, weight: 700, fill: T.onDarkRed });
  d.text("卡牌忌内容", CONTENT_X + 72, cy + 96, "吃生冷、油腻、凑合", { size: 13, fill: T.primaryFg });
  d.text("卡牌星座属相", CONTENT_X + 44, cy + 130, "双子座 · 属猪", { size: 12, fill: T.primaryFg });
  d.rect("卡牌今日已抽角标", CONTENT_X + 268, cy + 36, 96, 24, { fill: T.destructive, rx: 12 });
  d.text("卡牌已抽文字", CONTENT_X + 316, cy + 52, "今日已抽", { size: 12, fill: "#ffffff", anchor: "middle" });
  [["幸运食物", "麻辣香锅"], ["幸运颜色", "橘红色"], ["幸运数字", "7"]].forEach((r, i) => {
    const ry = cy + 168 + i * 44;
    d.text("幸运项标签 " + r[0], CONTENT_X + 44, ry, r[0], { size: 12, fill: T.onDarkDim });
    d.text("幸运项值 " + r[0], CONTENT_X + 44, ry + 20, r[1], { size: 15, weight: 600, fill: T.primaryFg });
  });
  d.text("综合建议标签", CONTENT_X + 24, cy + 356, "综合建议", { size: 12, weight: 500, fill: T.mutedFg });
  d.paragraph("综合建议内容", CONTENT_X + 24, cy + 380, "下班后别亏待自己，一份热辣的麻辣香锅配米饭，能把一天的疲惫都赶走。预算控制在 26~50 元，避免油炸与生冷。", 13, 356);
  d.text("翻面提示", CONTENT_X + 202, cy + fh - 24, "点击翻回 ↺", { size: 12, fill: T.mutedFg, anchor: "middle" });
  // 对话区
  const ox = CONTENT_X + 420, ow = CONTENT_W - 420;
  card(d, "AI 对话卡片", ox, cy, ow, fh);
  badge(d, ox + ow - 92, cy + 18, "第 5/5 轮", { variant: "default" });
  const msgs = [
    ["AI", "今天想吃什么口味的？"], ["我", "辣的，别太贵"], ["AI", "一个人吃还是和朋友一起？"], ["我", "一个人"],
    ["AI", "更想做饭还是点外卖？"], ["我", "点外卖，懒得动"], ["AI", "附近有什么忌口吗？"], ["我", "不吃香菜"],
    ["AI", "收到，正在为你挑选……"], ["我", "快点，我饿了"],
  ];
  let my = cy + 56;
  msgs.forEach((m, i) => {
    const mine = m[0] === "我";
    const w = Math.round(measure(m[1], 13)) + 24;
    const x = mine ? ox + ow - 24 - w : ox + 24;
    d.rect((mine ? "用户气泡 " : "AI 气泡 ") + (i + 1), x, my, w, 30, { fill: mine ? T.primary : T.secondary, rx: 8 });
    d.text("气泡文字 " + (i + 1), x + 12, my + 19, m[1], { size: 13, fill: mine ? T.primaryFg : T.fg });
    my += 36;
  });
  d.rect("最终推荐卡", ox + 24, my + 6, ow - 48, 132, { fill: T.bg, stroke: T.border, rx: 8 });
  d.text("最终推荐名称", ox + 40, my + 34, "麻辣香锅（微辣）· 附近 3.1km", { size: 15, weight: 600 });
  d.text("最终推荐备选", ox + 40, my + 56, "备选：番茄牛腩饭 / 干锅花菜", { size: 12, fill: T.mutedFg });
  ["美团", "必应", "百度", "搜索外卖"].forEach((t, i) => outlineButton(d, "外卖平台按钮 " + t, ox + 40 + i * 82, my + 70, 74, 26, t, { size: 12 }));
  ghostButton(d, "好评按钮", ox + 40, my + 100, 60, 24, "👍 好吃", { size: 12, ink: T.green600 });
  ghostButton(d, "中评按钮", ox + 116, my + 100, 60, 24, "😐 一般", { size: 12 });
  ghostButton(d, "差评按钮", ox + 192, my + 100, 72, 24, "👎 不好吃", { size: 12, ink: T.red500 });
  ghostButton(d, "重置对话按钮", ox + ow - 72, my + 100, 48, 24, "重置", { size: 12 });
  d.h = cy + fh + 32;
  return d;
}