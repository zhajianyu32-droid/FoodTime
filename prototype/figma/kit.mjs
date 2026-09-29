// FoodTime 高保真原型生成器 —— 输出可直接拖入 Figma 的 SVG（图层可编辑）
// 用法: node build.mjs
import { writeFileSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";

const OUT = resolve("out");
mkdirSync(OUT, { recursive: true });

/* ========== 设计令牌（取自 frontend/src/assets/index.css :root） ========== */
const hsl = (h, s, l) => {
  s /= 100; l /= 100;
  const k = n => (n + h / 30) % 12;
  const a = s * Math.min(l, 1 - l);
  const f = n => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  const hex = c => c.toString(16).padStart(2, "0");
  return "#" + hex(Math.round(f(0) * 255)) + hex(Math.round(f(8) * 255)) + hex(Math.round(f(4) * 255));
};
export const T = {
  bg: hsl(60, 6, 95), fg: hsl(20, 14, 10), card: hsl(0, 0, 100),
  primary: hsl(24, 10, 20), primaryFg: hsl(60, 6, 95),
  secondary: hsl(60, 5, 88), secondaryFg: hsl(20, 14, 10),
  muted: hsl(60, 5, 88), mutedFg: hsl(25, 5, 40),
  accent: hsl(60, 5, 85), accentFg: hsl(20, 14, 10),
  destructive: hsl(0, 72, 51), destructiveFg: hsl(60, 6, 95),
  border: hsl(25, 6, 80), input: hsl(25, 6, 80), ring: hsl(24, 10, 20),
  radius: 8,
  // 页面里硬编码的语义色（Tailwind 调色板）
  green600: "#16a34a", green500: "#22c55e", yellow600: "#ca8a04",
  blue500: "#3b82f6", purple500: "#a855f7", red500: "#ef4444",
  redBg: "#fdecec", greenBg: "#eef7ee",
  onDarkDim: "#b9ada4", onDarkGreen: "#4ade80", onDarkRed: "#f87171",
};
export const FONT = "'PingFang SC','Microsoft YaHei','Noto Sans SC','Segoe UI',sans-serif";

/* ========== 文本宽度估算（用于对齐/换行/居中） ========== */
const isWide = ch => /[\u3000-\u303f\u4e00-\u9fff\uff00-\uffef\u{1f300}-\u{1faf6}\u{1f000}-\u{1f02f}\u{1f600}-\u{1f64f}\u{1f680}-\u{1f6ff}\u{1f900}-\u{1f9ff}]/u.test(ch);
export function measure(str, size, weight = 400) {
  let w = 0;
  for (const ch of String(str)) {
    if (isWide(ch)) w += size * 1.0;
    else if (ch === " ") w += size * 0.28;
    else if (ch === "i" || ch === "l" || ch === "." || ch === "," || ch === "|" || ch === "'" || ch === ":" || ch === ";") w += size * 0.28;
    else if (/[A-Z0-9]/.test(ch)) w += size * (weight >= 600 ? 0.66 : 0.6);
    else w += size * (weight >= 600 ? 0.56 : 0.52);
  }
  return Math.round(w * 100) / 100;
}
export function wrap(str, size, maxWidth, weight = 400) {
  const out = []; let line = "";
  for (const ch of String(str)) {
    if (measure(line + ch, size, weight) > maxWidth && line) { out.push(line); line = ch; }
    else line += ch;
  }
  if (line) out.push(line);
  return out;
}

/* ========== SVG 文档构建器（每个元素带 id -> 导入 Figma 后即为图层名） ========== */
const esc = t => String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

export class Doc {
  constructor(name, w, h) { this.name = name; this.w = w; this.h = h; this.body = []; this.ox = 0; this.oy = 0; }
  X(v) { return v + this.ox; }
  Y(v) { return v + this.oy; }
  push(s) { this.body.push(s); }
  rect(name, x, y, w, h, o = {}) {
    const a = [`x=${this.X(x)}`, `y=${this.Y(y)}`, `width=${w}`, `height=${h}`];
    a.push(`fill=${JSON.stringify(o.fill ?? "none")}`);
    if (o.stroke) { a.push(`stroke=${JSON.stringify(o.stroke)}`); a.push(`stroke-width=${o.sw ?? 1}`); }
    if (o.rx) a.push(`rx=${o.rx}`);
    if (o.opacity !== undefined) a.push(`opacity=${o.opacity}`);
    this.push(`<rect id=${JSON.stringify(esc(name))} ${a.join(" ")}/>`);
    return this;
  }
  line(name, x1, y1, x2, y2, stroke, sw = 1) {
    this.push(`<line id=${JSON.stringify(esc(name))} x1=${this.X(x1)} y1=${this.Y(y1)} x2=${this.X(x2)} y2=${this.Y(y2)} stroke=${JSON.stringify(stroke)} stroke-width=${sw}/>`);
    return this;
  }
  text(name, x, y, str, o = {}) {
    const size = o.size ?? 14, weight = o.weight ?? 400;
    const a = [`x=${this.X(x)}`, `y=${this.Y(y)}`, `font-family=${JSON.stringify(FONT)}`, `font-size=${size}`, `font-weight=${weight}`, `fill=${JSON.stringify(o.fill ?? T.fg)}`];
    if (o.anchor) a.push(`text-anchor=${JSON.stringify(o.anchor)}`);
    a.push(`xml:space=${JSON.stringify("preserve")}`);
    this.push(`<text id=${JSON.stringify(esc(name))} ${a.join(" ")}>${esc(str)}</text>`);
    return this;
  }
  // 多行文本，返回占用的总高度
  paragraph(name, x, y, str, size, maxWidth, o = {}) {
    const lines = wrap(str, size, maxWidth, o.weight);
    const lh = o.lineHeight ?? Math.round(size * 1.5);
    lines.forEach((ln, i) => this.text(name + (lines.length > 1 ? " " + (i + 1) : ""), x, y + i * lh, ln, { ...o, size }));
    return lines.length * lh;
  }
  group(name, x, y, fn) {
    this.push(`<g id=${JSON.stringify(esc(name))}>`);
    this.ox += x; this.oy += y;
    fn(this);
    this.ox -= x; this.oy -= y;
    this.push("</g>");
    return this;
  }
  toString() {
    return `<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="${this.w}" height="${this.h}" viewBox="0 0 ${this.w} ${this.h}" fill="none">\n<rect id="背景" width=${this.w} height=${this.h} fill=${JSON.stringify(T.bg)}/>\n${this.body.join("\n")}\n</svg>\n`;
  }
}

/* ========== 组件库 ========== */
export const SIDEBAR_W = 240, CONTENT_X = 328, CONTENT_W = 1024, PAD = 32;

export const NAV = [
  { group: "主菜单", items: [
    { key: "cook", icon: "🍳", label: "Cook Mode" },
    { key: "order", icon: "🛵", label: "Order Mode" },
    { key: "shopping", icon: "🛒", label: "购物单" },
    { key: "diary", icon: "📖", label: "美食日记" }] },
  { group: "管理", items: [{ key: "ingredients", icon: "🧊", label: "食材库" }] },
  { group: "系统", items: [
    { key: "settings", icon: "⚙️", label: "个人设置" },
    { key: "about", icon: "ℹ️", label: "关于" }] },
];

export function sidebar(d, active) {
  d.group("侧边导航", 0, 0, s => {
    s.rect("侧边栏底", 0, 0, SIDEBAR_W, 900, { fill: T.card });
    s.line("侧边栏右描边", SIDEBAR_W, 0, SIDEBAR_W, 900, T.border);
    s.text("产品名", 16, 40, "食光 FoodTime", { size: 18, weight: 700 });
    s.text("产品副标题", 16, 62, "独居青年吃饭决策助手", { size: 12, fill: T.mutedFg });
    s.line("分隔线", 16, 76, SIDEBAR_W - 16, 76, T.border);
    let y = 100;
    for (const g of NAV) {
      s.text("分组 " + g.group, 16, y + 12, g.group, { size: 12, fill: T.mutedFg, weight: 500 });
      y += 26;
      for (const it of g.items) {
        const on = it.key === active;
        if (on) s.rect("选中态 " + it.label, 12, y, SIDEBAR_W - 24, 36, { fill: T.primary, rx: 6 });
        s.text("导航项 " + it.label, 28, y + 23, it.icon + "  " + it.label, { size: 14, weight: on ? 500 : 400, fill: on ? T.primaryFg : T.mutedFg });
        y += 40;
      }
      y += 20;
    }
    s.line("底部描边", 16, 806, SIDEBAR_W - 16, 806, T.border);
    s.text("当前用户", 16, 836, "demo_pm", { size: 12, fill: T.mutedFg });
    badge(s, 190, 822, "dev", { variant: "secondary" });
    s.text("配额提示", 16, 858, "配额 0/100", { size: 12, fill: T.mutedFg });
    outlineButton(s, "退出按钮", 16, 866, SIDEBAR_W - 32, 28, "退出");
  });
}

export function pageHeader(d, title, subtitle, y = 48) {
  d.text("页面标题", CONTENT_X, y, title, { size: 24, weight: 700 });
  d.text("页面副标题", CONTENT_X, y + 24, subtitle, { size: 14, fill: T.mutedFg });
  return y + 48;
}

export function card(d, name, x, y, w, h) {
  d.rect(name, x, y, w, h, { fill: T.card, stroke: T.border, rx: T.radius });
  return { x, y, w, h, cx: x + 16, cy: y + 16 };
}

export function badge(d, x, y, label, o = {}) {
  const v = o.variant || "secondary";
  const size = 12, h = 22, pad = 8;
  const w = Math.round(measure(label, size, 400)) + pad * 2;
  const style = {
    secondary: { fill: T.secondary, ink: T.secondaryFg, stroke: null, rx: 6 },
    default: { fill: T.primary, ink: T.primaryFg, stroke: null, rx: 6 },
    outline: { fill: T.card, ink: T.fg, stroke: T.border, rx: 6 },
    destructive: { fill: T.destructive, ink: T.destructiveFg, stroke: null, rx: 6 },
    dot: { fill: T.destructive, ink: "#ffffff", stroke: null, rx: 999 },
  }[v];
  d.rect("徽章 " + label, x, y, w, h, { fill: style.fill, stroke: style.stroke || undefined, rx: Math.min(style.rx, h / 2) });
  d.text("徽章文字 " + label, x + w / 2, y + 15, label, { size, fill: style.ink, anchor: "middle" });
  return w;
}

export function chip(d, x, y, label, o = {}) {
  const sel = !!o.selected, size = 13, h = 28, pad = 10;
  const w = Math.round(measure(label, size, sel ? 500 : 400)) + pad * 2;
  d.rect((sel ? "已选标签 " : "未选标签 ") + label, x, y, w, h, {
    fill: sel ? T.primary : T.card, stroke: sel ? undefined : T.border, rx: 6,
  });
  d.text("标签文字 " + label, x + w / 2, y + 18, label, { size, weight: sel ? 500 : 400, fill: sel ? T.primaryFg : T.fg, anchor: "middle" });
  return w;
}

export function button(d, name, x, y, w, h, label, o = {}) {
  d.rect(name, x, y, w, h, { fill: T.primary, rx: 6 });
  d.text(name + " 文字", x + w / 2, y + h / 2 + 5, label, { size: o.size ?? 14, weight: 500, fill: T.primaryFg, anchor: "middle" });
  return w;
}
export function outlineButton(d, name, x, y, w, h, label, o = {}) {
  d.rect(name, x, y, w, h, { fill: T.card, stroke: T.border, rx: 6 });
  d.text(name + " 文字", x + w / 2, y + h / 2 + 5, label, { size: o.size ?? 14, weight: 500, fill: o.ink || T.fg, anchor: "middle" });
  return w;
}
export function ghostButton(d, name, x, y, w, h, label, o = {}) {
  d.text(name + " 文字", x, y + h / 2 + 5, label, { size: o.size ?? 14, weight: 500, fill: o.ink || T.mutedFg });
  return measure(label, o.size ?? 14, 500);
}

export function field(d, name, x, y, w, label, o = {}) {
  let yy = y;
  if (label) { d.text(name + " 标签", x, yy + 12, label, { size: 12, weight: 500, fill: T.fg }); yy += 22; }
  const h = o.h ?? 36;
  d.rect(name + " 输入框", x, yy, w, h, { fill: T.card, stroke: T.border, rx: 6 });
  const shown = o.value ?? o.placeholder ?? "";
  d.text(name + " 内容", x + 12, yy + 23, shown, { size: 14, fill: o.value === undefined ? T.mutedFg : T.fg });
  if (o.suffix) d.text(name + " 后缀", x + w - 12, yy + 23, o.suffix, { size: 14, fill: T.mutedFg, anchor: "end" });
  return yy + h;
}

export function tabs(d, name, x, y, w, items, o = {}) {
  const h = o.h ?? 40;
  d.rect(name, x, y, w, h, { fill: T.muted, rx: 8 });
  const each = (w - 8) / items.length;
  items.forEach((it, i) => {
    const tx = x + 4 + i * each, on = i === (o.active ?? 0);
    if (on) d.rect("选中页签 " + it, tx, y + 4, each - 4, h - 8, { fill: T.card, stroke: T.border, rx: 6 });
    d.text("页签 " + it, tx + (each - 4) / 2, y + h / 2 + 5, it, { size: 13, weight: on ? 500 : 400, fill: on ? T.fg : T.mutedFg, anchor: "middle" });
  });
  return y + h;
}

export function progress(d, x, y, w, pct) {
  d.rect("进度条底槽", x, y, w, 8, { fill: T.muted, rx: 4 });
  d.rect("进度条填充", x, y, Math.max(8, Math.round(w * pct / 100)), 8, { fill: T.primary, rx: 4 });
}

export function sectionTitle(d, x, y, text, o = {}) {
  d.text("小节标题 " + text, x, y, text, { size: o.size ?? 16, weight: o.weight ?? 600 });
  return y;
}