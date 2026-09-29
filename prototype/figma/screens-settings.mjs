import { T, Doc, CONTENT_X, CONTENT_W, sidebar, card, badge, chip, button, outlineButton, field, measure, FONT } from "./kit.mjs";
import { W, chipRow } from "./screens-a.mjs";

const LX = CONTENT_X + 24;

/* ============================ 个人设置（改版后 · 一屏完整可见） ============================ */
export function screenSettings() {
  const d = new Doc("个人设置-改版", W, H);
  sidebar(d, "settings");
  // 标题行（改版：说明文字与标题同行）
  const title = "⚙️ 个人设置";
  d.text("页面标题", CONTENT_X, 48, title, { size: 24, weight: 700 });
  d.text("页面副标题", CONTENT_X + measure(title, 24, 700) + 16, 48, "管理账户、密码与个人饮食偏好档案", { size: 14, fill: T.mutedFg });
  const top = 72;

  /* ---- 左：账户信息 ---- */
  const aw = 480, ah = 182;
  card(d, "账户信息卡片", CONTENT_X, top, aw, ah);
  d.text("账户信息标题", LX, top + 32, "账户信息", { size: 16, weight: 600 });
  d.text("账户信息说明", LX, top + 52, "你的账户基本资料", { size: 12, fill: T.mutedFg });
  outlineButton(d, "编辑资料按钮", CONTENT_X + aw - 176, top + 18, 80, 30, "编辑资料", { size: 13 });
  outlineButton(d, "退出登录按钮", CONTENT_X + aw - 90, top + 18, 78, 30, "退出登录", { size: 13 });
  const info = [["用户名", "demo_pm"], ["用户 ID", "64fd3f49-0def-...-ead85"], ["手机号", "未绑定"], ["注册时间", "-"]];
  info.forEach((r, i) => {
    const x = LX + (i % 2) * 232, y = top + 88 + Math.floor(i / 2) * 46;
    d.text("字段标签 " + r[0], x, y, r[0], { size: 12, fill: T.mutedFg });
    d.text("字段值 " + r[0], x, y + 20, r[1], { size: 13, weight: 500 });
  });

  /* ---- 右：修改密码 ---- */
  const pw = CONTENT_W - aw - 16, px = CONTENT_X + aw + 16;
  const ph = 292;
  card(d, "修改密码卡片", px, top, pw, ph);
  d.text("修改密码标题", px + 24, top + 32, "修改密码", { size: 16, weight: 600 });
  d.text("修改密码说明", px + 24, top + 52, "修改成功后，其他设备需要重新登录", { size: 12, fill: T.mutedFg });
  field(d, "原密码", px + 24, top + 68, pw - 48, "原密码", { placeholder: "请输入当前密码", h: 34 });
  field(d, "新密码", px + 24, top + 130, pw - 48, "新密码", { placeholder: "至少 6 位", h: 34 });
  field(d, "确认新密码", px + 24, top + 192, pw - 48, "确认新密码", { placeholder: "再次输入新密码", h: 34 });
  button(d, "提交修改密码按钮", px + pw - 24 - 92, top + 244, 92, 32, "修改密码", { size: 13 });

  /* ---- 偏好档案 ---- */
  const oy = top + Math.max(ah, ph) + 16;
  const oh = 486;
  card(d, "偏好档案卡片", CONTENT_X, oy, CONTENT_W, oh);
  d.text("偏好档案标题", LX, oy + 32, "偏好档案", { size: 16, weight: 600 });
  d.text("偏好档案说明", LX, oy + 52, "记录口味偏好、烹饪条件与忌口，让 AI 更懂你", { size: 12, fill: T.mutedFg });
  let bx = CONTENT_X + 560;
  [["已完善", "default"], ["双子座", "outline"], ["属猪", "outline"], ["INFP", "outline"], ["3 菜系", "outline"], ["忌口 3", "outline"]].forEach(([t, v]) => {
    bx += badge(d, bx, oy + 18, t, { variant: v }) + 8;
  });

  const fw = Math.round((CONTENT_W - 48 - 36) / 4);
  const f1 = oy + 70;
  field(d, "出生日期", LX, f1, fw, "出生日期", { value: "1995-06-15", h: 34, suffix: "📅" });
  field(d, "MBTI 性格类型", LX + (fw + 12), f1, fw, "MBTI 性格类型", { value: "INFP", h: 34, suffix: "▾" });
  field(d, "每餐预算", LX + (fw + 12) * 2, f1, fw, "每餐预算（元）", { value: "26~50 元", h: 34, suffix: "▾" });
  field(d, "烹饪水平", LX + (fw + 12) * 3, f1, fw, "烹饪水平", { value: "一般会做点（炒简单菜）", h: 34, suffix: "▾" });
  badge(d, LX + 62, f1 - 1, "双子座", { variant: "secondary" });
  badge(d, LX + 120, f1 - 1, "属猪", { variant: "secondary" });

  const f2 = f1 + 82;
  d.text("口味偏好标签", LX, f2, "口味偏好", { size: 12, weight: 500 });
  chipRow(d, LX, f2 + 10, 420, ["辣", "甜", "酸", "咸", "清淡", "油腻", "清爽", "都行"], new Set(["辣"]));
  const uw = CONTENT_W - 48 - 440 - 24;
  const ux = LX + 440 + 24;
  d.text("可用厨具标签", ux, f2, "可用厨具", { size: 12, weight: 500 });
  chipRow(d, ux, f2 + 10, uw, ["炒锅", "蒸锅", "电饭煲", "微波炉", "烤箱", "空气炸锅", "电煮锅", "高压锅", "平底锅", "汤锅"], new Set(["炒锅", "电饭煲", "空气炸锅"]));

  const f3 = f2 + 82;
  d.text("偏好菜系标签", LX, f3, "偏好菜系（可多选）", { size: 12, weight: 500 });
  outlineButton(d, "添加菜系按钮", CONTENT_X + CONTENT_W - 24 - 56, f3 - 22, 56, 32, "添加", { size: 13 });
  d.rect("自定义菜系输入框", CONTENT_X + CONTENT_W - 24 - 56 - 176, f3 - 22, 168, 32, { fill: T.card, stroke: T.border, rx: 6 });
  d.text("自定义菜系占位", CONTENT_X + CONTENT_W - 24 - 56 - 176 + 12, f3 - 1, "其他菜系，回车添加", { size: 13, fill: T.mutedFg });
  chipRow(d, LX, f3 + 10, CONTENT_W - 48, ["川菜", "粤菜", "鲁菜", "苏菜", "浙菜", "闽菜", "湘菜", "徽菜", "东北菜", "西北菜", "云南菜", "贵州菜", "新疆菜", "西藏菜", "北京菜", "上海菜", "广东早茶", "港式茶餐", "日式", "韩式", "东南亚", "意式", "法式", "美式", "墨西哥", "中东", "其他菜系"], new Set(["川菜", "粤菜", "湘菜"]));

  const f4 = f3 + 118;
  d.text("忌口食材标签", LX, f4, "忌口食材", { size: 12, weight: 500 });
  d.text("忌口操作提示", CONTENT_X + CONTENT_W - 24, f4, "点分类后选食材（红色为已忌口）；当前已忌口 3 项", { size: 12, fill: T.mutedFg, anchor: "end" });
  const cats = [["蔬菜", 1], ["肉蛋", 1], ["水产海鲜", 0], ["主食/谷物", 0], ["调料/辛香", 1], ["水果/坚果", 0], ["饮品/甜品", 0], ["其他", 1]];
  const catW = Math.round((CONTENT_W - 48 - 7 * 8) / 8);
  cats.forEach(([c, n], i) => {
    const x = LX + i * (catW + 8), on = c === "蔬菜";
    d.rect((on ? "已选忌口分类 " : "未选忌口分类 ") + c, x, f4 + 10, catW, 34, { fill: on ? T.primary : T.card, stroke: on ? undefined : T.border, rx: 6 });
    if (on) d.text("忌口分类文字 " + c, x + catW / 2, f4 + 31, c, { size: 13, weight: 500, fill: T.primaryFg, anchor: "middle" });
    else {
      const tw = measure(c, 13);
      d.text("忌口分类文字 " + c, x + catW / 2 - (n ? 6 : 0), f4 + 31, c, { size: 13, fill: T.fg, anchor: "middle" });
    }
    if (n) {
      d.rect("忌口计数角标 " + c, x + catW - 16, f4 + 2, 18, 18, { fill: T.destructive, rx: 9 });
      d.text("忌口计数文字 " + c, x + catW - 7, f4 + 15, String(n), { size: 11, fill: "#ffffff", anchor: "middle" });
    }
  });
  chipRow(d, LX, f4 + 54, CONTENT_W - 48, ["叶菜类 (1)", "根茎类", "瓜茄类", "菌菇类", "豆类类", "其他"], new Set(["叶菜类 (1)"]));

  button(d, "保存偏好按钮", CONTENT_X + CONTENT_W - 24 - 128, oy + oh - 42, 128, 34, "更新偏好档案", { size: 13 });
  d.h = oy + oh + 32;
  return d;
}

const H = 900;