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

/* ============================ 购物清单 ============================ */
export function screenShopping() {
  const d = new Doc("购物清单", W, H);
  sidebar(d, "shopping");
  let y = header(d, "🛒 购物清单", "勾选已购买的食材，一键移入冰箱");
  d.text("已购买计数", CONTENT_X, y + 30, "1", { size: 30, weight: 700 });
  d.text("已购买总数", CONTENT_X + 28, y + 30, "/ 6 已购买", { size: 14, fill: T.mutedFg });
  outlineButton(d, "清空已勾选按钮", CONTENT_X + CONTENT_W - 190, y + 6, 110, 32, "清空已勾选", { size: 13 });
  button(d, "全部移入冰箱按钮", CONTENT_X + CONTENT_W - 74, y + 6, 74, 32, "📥 移入", { size: 13 });
  y += 52;
  tabs(d, "购物筛选页签", CONTENT_X, y, CONTENT_W, ["全部 6", "待购买 5", "已勾选 1"], { active: 0, h: 40 });
  y += 52;
  field(d, "购物添加输入", CONTENT_X, y, 420, null, { placeholder: "输入食材名，回车添加…", h: 34 });
  field(d, "购物数量输入", CONTENT_X + 428, y, 100, null, { placeholder: "数量", h: 34 });
  button(d, "购物添加按钮", CONTENT_X + 536, y, 64, 34, "添加", { size: 13 });
  y += 46;
  card(d, "购物清单卡片", CONTENT_X, y, CONTENT_W, 332);
  const rows = [
    [1, "猪肉丝", "250g", "青椒肉丝", 1], [0, "青椒", "3 个", "青椒肉丝", 0],
    [0, "番茄", "4 个", "番茄炒蛋", 0], [0, "鸡蛋", "1 盒", "番茄炒蛋", 0],
    [0, "大米", "5kg", "米饭", 0], [0, "生姜", "1 块", "通用", 0],
  ];
  rows.forEach((r, i) => {
    const ry = y + 16 + i * 44;
    d.rect("购物行 " + (i + 1), CONTENT_X + 16, ry, CONTENT_W - 32, 38, { fill: i % 2 ? T.bg : T.card, rx: 6 });
    d.rect("购物勾选框 " + r[1], CONTENT_X + 28, ry + 10, 18, 18, { fill: r[4] ? T.primary : T.card, stroke: T.border, rx: 4 });
    if (r[4]) d.text("购物勾选号 " + r[1], CONTENT_X + 37, ry + 24, "✓", { size: 13, fill: T.primaryFg, anchor: "middle" });
    d.text("购物食材 " + r[1], CONTENT_X + 60, ry + 24, r[1], { size: 14, weight: 500, fill: r[4] ? T.mutedFg : T.fg });
    d.text("购物数量 " + r[1], CONTENT_X + 300, ry + 24, r[2], { size: 13, fill: T.mutedFg });
    d.text("购物来源 " + r[1], CONTENT_X + 460, ry + 24, "来自：" + r[3], { size: 12, fill: T.mutedFg });
    ghostButton(d, "购物删除按钮 " + r[1], CONTENT_X + CONTENT_W - 64, ry + 8, 40, 22, "删除", { size: 12, ink: T.destructive });
  });
  d.text("购物操作提示", CONTENT_X + 16, y + 308, "💡 勾选食材后点击「全部移入冰箱」可批量入库", { size: 12, fill: T.mutedFg });
  d.h = y + 332 + 32;
  return d;
}

/* ============================ 美食日记 ============================ */
export function screenDiary() {
  const d = new Doc("美食日记", W, H);
  sidebar(d, "diary");
  let y = header(d, "📖 美食日记", "记录每一餐，看见你的饮食偏好与节奏");
  const gap = 16, tw = Math.round((CONTENT_W - gap * 3) / 4);
  [["做饭", "12", T.fg], ["外卖", "8", T.fg], ["连续", "5天", T.fg], ["累计", "20", T.fg]].forEach((s, i) => {
    const x = CONTENT_X + i * (tw + gap);
    card(d, "日记统计卡片 " + s[0], x, y, tw, 88);
    d.text("统计名 " + s[0], x + 16, y + 30, s[0], { size: 12, fill: T.mutedFg });
    d.text("统计值 " + s[0], x + 16, y + 64, s[1], { size: 22, weight: 700, fill: s[2] });
  });
  y += 104;
  const lw = 600;
  card(d, "日记列表卡片", CONTENT_X, y, lw, 452);
  d.text("列表标题", LX, y + 30, "日记列表", { size: 15, weight: 600 });
  d.text("列表计数", LX + 74, y + 30, "共 20 条记录", { size: 11, fill: T.mutedFg });
  tabs(d, "日记筛选页签", LX, y + 44, lw - 48, ["全部", "做饭", "外卖"], { active: 0, h: 34 });
  const cols = [LX + 8, LX + 96, LX + 152, LX + 300];
  ["日期", "类型", "名称", "详情"].forEach((h, i) => d.text("表头 " + h, cols[i], y + 108, h, { size: 12, weight: 500, fill: T.mutedFg }));
  d.line("表头描边", LX, y + 116, LX + lw - 48, y + 116, T.border);
  const rows = [
    ["2026-09-29", "做饭", "青椒肉丝", "心情：还行 · 花费：¥12 · 评分：4"],
    ["2026-09-28", "外卖", "麻辣香锅", "心情：爽 · 花费：¥32 · 评分：5"],
    ["2026-09-27", "做饭", "番茄炒蛋", "花费：¥6 · 评分：4"],
    ["2026-09-26", "外卖", "黄焖鸡米饭", "心情：一般 · 花费：¥22"],
    ["2026-09-25", "做饭", "蛋炒饭", "花费：¥4 · 评分：3"],
    ["2026-09-24", "外卖", "螺蛳粉", "心情：上头 · 花费：¥18 · 评分：5"],
    ["2026-09-23", "做饭", "豆腐青菜汤", "花费：¥5 · 评分：4"],
  ];
  rows.forEach((r, i) => {
    const ry = y + 124 + i * 34;
    d.rect("日记行 " + (i + 1), LX, ry, lw - 48, 30, { fill: i % 2 ? T.bg : T.card, rx: 4 });
    r.forEach((c, k) => d.text("日记列" + (k + 1) + " " + i, cols[k], ry + 20, c, { size: 12, weight: k === 2 ? 500 : 400, fill: k === 3 ? T.mutedFg : T.fg }));
  });
  const hx = CONTENT_X + lw + gap, hw = CONTENT_W - lw - gap;
  card(d, "饮食热力图卡片", hx, y, hw, 262);
  d.text("热力图标题", hx + 24, y + 30, "饮食热力图", { size: 15, weight: 600 });
  d.text("热力图说明", hx + 24, y + 50, "2026 年 9 月 · 本月 22 天有记录", { size: 11, fill: T.mutedFg });
  const cell = 26, ox = hx + 24, oy = y + 70;
  for (let r = 0; r < 5; r++) for (let c = 0; c < 7; c++) {
    const n = r * 7 + c + 1; if (n > 30) continue;
    const col = n > 29 ? null : (n % 9 === 0 ? T.purple500 : (n % 3 === 0 ? T.blue500 : (n % 2 === 0 ? T.green500 : null)));
    d.rect("热力格 " + n, ox + c * (cell + 4), oy + r * (cell + 4), cell, cell, { fill: col || T.muted, rx: 4 });
    if (n <= 30) d.text("热力日 " + n, ox + c * (cell + 4) + 5, oy + r * (cell + 4) + 17, String(n), { size: 10, fill: col ? "#ffffff" : T.mutedFg });
  }
  [["做饭", T.green500], ["外卖", T.blue500], ["都有", T.purple500]].forEach((l, i) => {
    const lx = ox + i * 92, ly = oy + 5 * (cell + 4) + 12;
    d.rect("图例色块 " + l[0], lx, ly, 10, 10, { fill: l[1], rx: 2 });
    d.text("图例文字 " + l[0], lx + 16, ly + 10, l[0], { size: 12, fill: T.mutedFg });
  });
  card(d, "偏好权重卡片", hx, y + 274, hw, 178);
  d.text("权重标题", hx + 24, y + 302, "偏好权重", { size: 14, weight: 600 });
  [["辣", 82], ["清淡", 46], ["川菜", 70], ["粤菜", 38]].forEach((p, i) => {
    const py = y + 322 + i * 32;
    d.text("权重名 " + p[0], hx + 24, py + 8, p[0], { size: 12, fill: T.mutedFg });
    progress(d, hx + 76, py, hw - 130, p[1]);
    d.text("权重值 " + p[0], hx + hw - 44, py + 8, p[1] + "%", { size: 12, anchor: "end" });
  });
  d.h = y + 452 + 32;
  return d;
}

/* ============================ 食材库 ============================ */
export function screenIngredients() {
  const d = new Doc("食材库", W, H);
  sidebar(d, "ingredients");
  let y = header(d, "🧊 食材管理", "管理冰箱里的食材，及时处理临期与过期", [{ t: "临期 2", v: "default" }, { t: "已过期 3", v: "destructive" }]);
  const fw = Math.round((CONTENT_W - 48 - 4 * 12 - 96) / 5);
  card(d, "添加食材卡片", CONTENT_X, y, CONTENT_W, 150);
  d.text("添加食材标题", LX, y + 30, "添加食材", { size: 16, weight: 600 });
  const f = [["名称", "如：番茄"], ["分类", "选择分类 ▾"], ["数量", "如：2"], ["保质期（天）", "7（默认）"], ["过期日期（可选）", "年/月/日 📅"]];
  f.forEach((x, i) => field(d, "添加字段 " + x[0], LX + i * (fw + 12), y + 44, fw, x[0], { placeholder: x[1], h: 34 }));
  button(d, "提交添加按钮", CONTENT_X + CONTENT_W - 120, y + 66, 96, 34, "添加");
  y += 166;
  card(d, "食材清单卡片", CONTENT_X, y, CONTENT_W, 486);
  d.text("清单标题", LX, y + 30, "食材清单", { size: 16, weight: 600 });
  const cols = [LX + 8, LX + 180, LX + 320, LX + 430, LX + 560, LX + 690, CONTENT_X + CONTENT_W - 100];
  ["名称", "分类", "数量", "保质期", "过期日", "状态", "操作"].forEach((h, i) => d.text("食材表头 " + h, cols[i], y + 116, h, { size: 12, weight: 500, fill: T.mutedFg }));
  field(d, "状态筛选", CONTENT_X + CONTENT_W - 480, y + 44, 150, null, { value: "全部状态 ▾", h: 32 });
  field(d, "分类筛选", CONTENT_X + CONTENT_W - 320, y + 44, 150, null, { value: "全部分类 ▾", h: 32 });
  field(d, "名称搜索", CONTENT_X + CONTENT_W - 160, y + 44, 136, null, { placeholder: "按名称搜索", h: 32 });
  d.line("食材表头描边", LX, y + 124, LX + CONTENT_W - 48, y + 124, T.border);
  const rows = [
    ["鸡胸肉", "肉蛋类", "300g", "3 天", "09-30", "临期", T.yellow600],
    ["牛奶", "乳制品", "1 盒", "2 天", "09-29", "已过期", T.destructive],
    ["番茄", "蔬菜", "4 个", "4 天", "10-01", "临期", T.yellow600],
    ["鸡蛋", "肉蛋类", "10 枚", "12 天", "10-09", "可用", T.green600],
    ["青椒", "蔬菜", "3 个", "5 天", "10-02", "可用", T.green600],
    ["大米", "主食/谷物", "5kg", "180 天", "2027-03", "可用", T.green600],
    ["豆腐", "豆制品", "2 块", "1 天", "09-28", "已过期", T.destructive],
    ["生姜", "调料/辛香", "1 块", "20 天", "10-17", "可用", T.green600],
  ];
  rows.forEach((r, i) => {
    const ry = y + 132 + i * 40;
    d.rect("食材行 " + (i + 1), LX, ry, CONTENT_W - 48, 36, { fill: i % 2 ? T.bg : T.card, rx: 4 });
    r.slice(0, 6).forEach((c, k) => d.text("食材列" + (k + 1) + " " + r[0], cols[k], ry + 23, c, { size: 13, weight: k === 0 ? 500 : 400, fill: k === 5 ? r[6] : T.fg }));
    ghostButton(d, "编辑食材按钮 " + r[0], cols[6], ry + 6, 32, 24, "编辑", { size: 12 });
    ghostButton(d, "删除食材按钮 " + r[0], cols[6] + 38, ry + 6, 32, 24, "删除", { size: 12, ink: T.destructive });
  });
  d.h = y + 486 + 32;
  return d;
}