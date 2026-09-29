import { writeFileSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { screenLogin, screenRegister, screenDashboard, screenAbout } from "./screens-a.mjs";
import { screenSettings } from "./screens-settings.mjs";
import { screenCook, screenOrder } from "./screens-b.mjs";
import { screenShopping, screenDiary, screenIngredients } from "./screens-c.mjs";

const OUT = resolve("out");
mkdirSync(OUT, { recursive: true });

const screens = [
  { file: "01-登录", desc: "未登录 · 账号密码进入", doc: screenLogin() },
  { file: "02-注册", desc: "未登录 · 创建账户（手机号选填）", doc: screenRegister() },
  { file: "03-仪表盘", desc: "登录后首页 · 配额 / 临期 / 快捷入口", doc: screenDashboard() },
  { file: "04-Cook-Mode", desc: "做饭 · 待选池 + 冰箱 + 做菜区 + AI 菜谱", doc: screenCook() },
  { file: "05-Order-Mode", desc: "点单 · 美食运势卡 + 5 轮 AI 对话 + 外卖推荐", doc: screenOrder() },
  { file: "06-购物清单", desc: "按菜谱缺料自动生成，勾选后移入冰箱", doc: screenShopping() },
  { file: "07-食材库", desc: "冰箱台账 · 临期/过期提醒 + 筛选", doc: screenIngredients() },
  { file: "08-美食日记", desc: "记录列表 + 饮食热力图 + 偏好权重", doc: screenDiary() },
  { file: "09-个人设置-改版", desc: "★ 修复 1080p 裁切后的版本，整页一屏可见", doc: screenSettings() },
  { file: "10-关于", desc: "项目信息 + 核心能力清单", doc: screenAbout() },
];

const rows = [];
for (const s of screens) {
  s.doc.h = Math.max(900, s.doc.h);   // 画布不低于一屏，避免侧边栏被裁
  const raw = s.doc.toString();
  const svg = raw.replace(/([A-Za-z:][A-Za-z0-9:_-]*)=([^\s""'>/]+)/g, '$1="$2"');
  writeFileSync(resolve(OUT, s.file + ".svg"), svg, "utf8");
  rows.push(s);
  console.log("✓", s.file + ".svg", s.doc.w + "x" + s.doc.h, "(" + (svg.length / 1024).toFixed(1) + " KB)");
}

const gallery = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>食光 FoodTime · 原型总览</title>
<style>
 body{margin:0;background:#ececeb;font-family:"PingFang SC","Microsoft YaHei",sans-serif;color:#241f1c}
 header{padding:28px 32px 12px} h1{margin:0;font-size:24px} p.sub{margin:8px 0 0;color:#6b6561;font-size:14px;line-height:1.7}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(560px,1fr));gap:24px;padding:20px 32px 60px}
 .cell{background:#fff;border:1px solid #d1cdc8;border-radius:10px;overflow:hidden}
 .cell h2{margin:0;padding:12px 16px 2px;font-size:15px}
 .cell p{margin:0;padding:0 16px 10px;font-size:12px;color:#6b6561}
 .shot{display:block;width:100%;height:auto;border-top:1px solid #eee;background:#f1f1f0}
 .star{border-color:#38302b;box-shadow:0 0 0 2px #38302b22}
</style></head><body>
<header><h1>食光 FoodTime · 全模块可编辑原型</h1>
<p class="sub">共 ${rows.length} 个页面 · 1440 宽 · 矢量 SVG。<br>
<b>导入 Figma：</b>打开 Figma 文件 → 直接把 out 文件夹里的 .svg 拖进画布（或菜单 File → 拖入），每个页面会自动变成<b>可编辑的图层、文字和形状</b>。<br>
提示：文字使用 PingFang SC / 微软雅黑，若 Figma 提示缺字体，替换为任意中文字体即可，版式不变。</p></header>
<div class="grid">
${rows.map(s => `<div class="cell${s.file.startsWith("09") ? " star" : ""}"><h2>${s.file.replace(/^\d+-/, "")}</h2><p>${s.desc} · ${s.doc.w}×${s.doc.h}</p><img class="shot" src="out/${encodeURIComponent(s.file)}.svg" alt="${s.file}"></div>`).join("\n")}
</div></body></html>`;
writeFileSync(resolve("原型总览.html"), gallery, "utf8");
console.log("\n原型总览.html 已生成");