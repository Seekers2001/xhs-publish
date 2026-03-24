/**
 * md_to_longimage.js
 * 将 Markdown 文件渲染为长图 PNG（暖奶油背景 + 宝玉风格排版）
 *
 * 用法：
 *   node md_to_longimage.js --src <md文件路径> --out <输出png路径>
 *
 * 可选参数：
 *   --base-dir       图片基础目录（默认取 MD 文件所在目录）
 *   --width          渲染宽度，默认 1440
 *   --accent         色块颜色，默认 #E8705A（coral）
 *   --bg             背景色，默认 #EEF2F6（冷蓝灰白）
 *   --cover-img      强制指定封面图路径（不依赖 MD 内图片）
 *   --cover-title    强制指定封面主标题（不依赖 MD 内 # 标题）
 *   --cover-eyebrow  封面眉题（小标签，显示在主标题上方，coral 色）
 *
 * 封面层次结构（@dotey 风格）：
 *   [全宽配图]
 *   眉题（小字 coral，可选）
 *   主标题（超大黑体）｜ tagline（自动从 ｜ 拆分，coral 色）
 *   副标题（## 或 --cover-subtitle，可选）
 *
 * 封面自动检测规则：
 *   MD 开头若有 # 标题 + 图片（顺序不限，前 8 行内），自动渲染封面
 */

const { chromium } = require('C:/Users/JXLFM/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright-core');
const fs = require('fs');
const path = require('path');

// ── 命令行参数解析 ──────────────────────────────────────────
function parseArgs() {
  const args = process.argv.slice(2);
  const result = {};
  for (let i = 0; i < args.length; i++) {
    if (args[i].startsWith('--')) {
      result[args[i].slice(2)] = args[i + 1];
      i++;
    }
  }
  return result;
}

const opts = parseArgs();

if (!opts.src || !opts.out) {
  console.error('用法: node md_to_longimage.js --src <md文件路径> --out <输出png路径>');
  process.exit(1);
}

const MD_FILE     = path.resolve(opts.src);
const OUT_FILE    = path.resolve(opts.out);
const BASE_DIR    = opts['base-dir'] ? path.resolve(opts['base-dir']) : path.dirname(MD_FILE);
const PAGE_WIDTH  = parseInt(opts.width || '1440');
const PLAIN_MODE  = opts.plain !== undefined;   // --plain：极简白底导出，不做任何样式修改
const ACCENT      = opts.accent || '#E8705A';   // coral 主色（@dotey 宝玉风格）
const BG_COLOR    = opts.bg    || '#ffffff';    // 纯白背景（原色）

// 字号缩放：支持预设名称（small/medium/large/xlarge）或自定义数字
// small≈原始大小, medium=中等, large=当前默认, xlarge=更大
const FONT_SCALE_PRESETS = { small: 0.71, medium: 0.85, large: 1.0, xlarge: 1.2 };
const _scaleInput = opts['font-scale'] || 'large';
const FONT_SCALE = FONT_SCALE_PRESETS[_scaleInput] ?? parseFloat(_scaleInput);
// 辅助函数：按比例计算字号（四舍五入到整数）
const F = (px) => Math.round(px * FONT_SCALE);

// 五色循环系：coral/teal/golden/blue/purple
const ACCENT_PALETTE = ['#E8705A', '#5BBFAD', '#F2A65A', '#7BB8D4', '#C4A0C8'];

const md = fs.readFileSync(MD_FILE, 'utf-8');

// ── 图片路径 → base64 data URI ──────────────────────────────
function imgToBase64(src) {
  if (!src) return null;
  if (src.startsWith('http://') || src.startsWith('https://')) return src;
  const absPath = path.resolve(BASE_DIR, src);
  if (!fs.existsSync(absPath)) {
    console.warn(`  ⚠ 图片不存在: ${absPath}`);
    return null;
  }
  const ext = path.extname(absPath).slice(1).toLowerCase();
  const mime = ext === 'jpg' ? 'image/jpeg' : `image/${ext}`;
  const data = fs.readFileSync(absPath).toString('base64');
  console.log(`  ✓ 嵌入图片: ${path.basename(absPath)}`);
  return `data:${mime};base64,${data}`;
}

// ── 行内 Markdown 格式化（粗体、行内代码）──────────────────
function inlineFormat(text) {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>');
}

// ── 封面检测：扫描前 10 行，找 eyebrow注释 + H1 + 图片 ──────
function detectCover(lines) {
  let h1Text   = opts['cover-title'] || null;
  let h1Line   = h1Text ? -99 : -1;   // -99 表示由参数给出
  let imgSrc   = opts['cover-img']   || null;
  let imgLine  = imgSrc ? -99 : -1;
  let h2Text   = null;
  let eyebrow  = opts['cover-eyebrow'] || null;  // 眉题

  const scanLimit = Math.min(10, lines.length);
  for (let i = 0; i < scanLimit; i++) {
    const t = lines[i].trim();
    if (t === '') continue;

    // <!-- eyebrow: 审计季干货 --> 注释识别
    const eyebrowM = t.match(/^<!--\s*eyebrow:\s*(.+?)\s*-->$/);
    if (eyebrowM && !eyebrow) { eyebrow = eyebrowM[1]; continue; }

    // PAGE BREAK 注释跳过
    if (t === '<!-- PAGE BREAK -->') break;

    // # H1 标题
    const h1m = t.match(/^#\s+(.+)$/);
    if (h1m && h1Line === -1) { h1Text = h1m[1]; h1Line = i; continue; }

    // 图片
    const imgm = t.match(/^!\[([^\]]*)\]\(([^)]+)\)$/);
    if (imgm && imgLine === -1) { imgSrc = imgm[2]; imgLine = i; continue; }

    // ## 副标题（在 H1 之后才识别）
    const h2m = t.match(/^##\s+(.+)$/);
    if (h2m && h1Line !== -1 && !h2Text) { h2Text = h2m[1]; continue; }

    // 遇到其他内容（正文段落）就停止扫描
    if (!t.startsWith('<!--')) break;
  }

  // H1 + 图片都找到才视为封面
  const hasCover = (h1Text !== null) && (imgSrc !== null);
  const skipTo   = hasCover
    ? Math.max(h1Line === -99 ? 0 : h1Line, imgLine === -99 ? 0 : imgLine) + 1
    : 0;

  return { hasCover, h1Text, h2Text, imgSrc, eyebrow, skipTo };
}

// ── 主转换函数 ─────────────────────────────────────────────
function mdToHtml(text) {
  const lines = text.split('\n');
  const htmlParts = [];
  let accentIdx = 0; // 色块轮换索引

  // 封面检测
  const cover = detectCover(lines);
  let coverHtml = '';

  if (cover.hasCover) {
    const imgUrl = imgToBase64(cover.imgSrc);
    const imgHtml = imgUrl
      ? `<img src="${imgUrl}" class="cover-img" alt="">`
      : `<div class="cover-img-placeholder"></div>`;

    // 封面眉题：--cover-eyebrow 参数 或 MD 内 <!-- eyebrow: xxx --> 注释（可选）
    const eyebrow = opts['cover-eyebrow'] || cover.eyebrow || null;

    // 主标题层次拆分：若含 ｜ 分隔符，自动拆为主题 + tagline
    let mainTitle = cover.h1Text;
    let tagline = null;
    const pipeIdx = cover.h1Text.indexOf('｜');
    if (pipeIdx > 0) {
      mainTitle = cover.h1Text.slice(0, pipeIdx).trim();
      tagline   = cover.h1Text.slice(pipeIdx + 1).trim();
    }

    // 封面：上图下文（@dotey 风格）
    // 层次：眉题（小 coral）→ 主标题（超大黑体）→ tagline（大 coral）→ 副标题（灰）
    coverHtml = `
<div class="cover-card">
  <div class="cover-top">${imgHtml}</div>
  <div class="cover-bottom">
    ${eyebrow ? `<div class="cover-eyebrow">${eyebrow}</div>` : ''}
    <div class="cover-title-wrap">
      <div class="cover-title">${inlineFormat(mainTitle)}</div>
      ${tagline ? `<div class="cover-tagline">${inlineFormat(tagline)}</div>` : ''}
    </div>
    ${cover.h2Text ? `<div class="cover-subtitle">${inlineFormat(cover.h2Text)}</div>` : ''}
  </div>
</div>`;
  }

  // 处理正文（跳过已用于封面的行）
  let i = cover.hasCover ? cover.skipTo : 0;

  // 跳过封面后的空行
  while (i < lines.length && lines[i].trim() === '') i++;

  for (; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    // ── 标准图片 ![alt](src) ──
    const imgMatch = trimmed.match(/^!\[([^\]]*)\]\(([^)]+)\)$/);
    if (imgMatch) {
      const dataUrl = imgToBase64(imgMatch[2]);
      if (dataUrl) {
        htmlParts.push(`<img src="${dataUrl}" alt="${imgMatch[1]}" class="content-img">`);
      }
      continue;
    }

    // Obsidian 图片 ![[filename]] 跳过
    if (/^!\[\[/.test(trimmed)) continue;

    // ── H1 标题（未用作封面时） ──
    const h1m = trimmed.match(/^#\s+(.+)$/);
    if (h1m) {
      const color = ACCENT_PALETTE[accentIdx % ACCENT_PALETTE.length];
      accentIdx++;
      htmlParts.push(`<div class="h1-title" style="border-color:${color}">${inlineFormat(h1m[1])}</div>`);
      continue;
    }

    // ── H2 标题 ──
    const h2m = trimmed.match(/^##\s+(.+)$/);
    if (h2m) {
      const color = ACCENT_PALETTE[accentIdx % ACCENT_PALETTE.length];
      accentIdx++;
      htmlParts.push(`<div class="h2-title" style="border-color:${color}">${inlineFormat(h2m[1])}</div>`);
      continue;
    }

    // ── H3 标题 ──
    const h3m = trimmed.match(/^###\s+(.+)$/);
    if (h3m) {
      htmlParts.push(`<div class="h3-title">${inlineFormat(h3m[1])}</div>`);
      continue;
    }

    // ── **粗体单行** → 色块节标题（兼容旧格式） ──
    const boldOnly = trimmed.match(/^\*\*(.+)\*\*$/);
    if (boldOnly) {
      const color = ACCENT_PALETTE[accentIdx % ACCENT_PALETTE.length];
      accentIdx++;
      htmlParts.push(`<div class="section-title" style="border-color:${color}">${boldOnly[1]}</div>`);
      continue;
    }

    // ── 无序列表 ──
    const ulm = trimmed.match(/^[-*•]\s+(.+)$/);
    if (ulm) {
      htmlParts.push(`<div class="list-item"><span class="list-bullet">•</span><span>${inlineFormat(ulm[1])}</span></div>`);
      continue;
    }

    // ── 有序列表 ──
    const olm = trimmed.match(/^(\d+)[.)]\s+(.+)$/);
    if (olm) {
      htmlParts.push(`<div class="list-item"><span class="list-num">${olm[1]}.</span><span>${inlineFormat(olm[2])}</span></div>`);
      continue;
    }

    // ── 代码块（多行） ──
    if (trimmed.startsWith('```')) {
      const codeLines = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith('```')) {
        codeLines.push(lines[i].replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'));
        i++;
      }
      htmlParts.push(`<div class="code-block">${codeLines.join('\n')}</div>`);
      continue;
    }

    // ── 引用块 ──
    if (trimmed.startsWith('> ')) {
      htmlParts.push(`<div class="blockquote">${inlineFormat(trimmed.slice(2))}</div>`);
      continue;
    }

    // ── 分隔线 ──
    if (/^---+$/.test(trimmed) || /^\*\*\*+$/.test(trimmed)) {
      htmlParts.push(`<div class="hr"></div>`);
      continue;
    }

    // ── 空行 ──
    if (trimmed === '') {
      htmlParts.push('<div class="spacer"></div>');
      continue;
    }

    // ── 普通段落 ──
    htmlParts.push(`<div class="para">${inlineFormat(trimmed)}</div>`);
  }

  return { coverHtml, bodyHtml: htmlParts.join('\n') };
}

// ── 生成 HTML ──────────────────────────────────────────────
console.log('正在处理 Markdown...');
const { coverHtml, bodyHtml } = mdToHtml(md);

// 封面高度 = PAGE_WIDTH * 3/4（与 3:4 小红书比例匹配，方便截图）
const COVER_HEIGHT = Math.round(PAGE_WIDTH * 0.667);

// --plain 模式：极简白底样式，完全不改变 MD 内容，直接按 GitHub 风格渲染
const plainCss = `
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    width: ${PAGE_WIDTH}px;
    background: #ffffff;
    color: #24292e;
    font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
    font-size: 32px;
    line-height: 1.8;
    padding: 80px 100px;
  }
  h1 { font-size: 56px; font-weight: 700; margin: 40px 0 20px; border-bottom: 2px solid #e1e4e8; padding-bottom: 16px; }
  h2 { font-size: 38px; font-weight: 600; margin: 36px 0 14px; border-bottom: 1px solid #e1e4e8; padding-bottom: 8px; }
  h3 { font-size: 32px; font-weight: 600; margin: 24px 0 10px; }
  p  { margin: 16px 0; }
  strong { font-weight: 700; }
  em { font-style: italic; }
  ul, ol { margin: 16px 0 16px 48px; }
  li { margin: 8px 0; }
  blockquote { border-left: 6px solid #dfe2e5; padding: 8px 24px; color: #6a737d; margin: 20px 0; }
  code { background: #f6f8fa; border-radius: 6px; padding: 2px 8px; font-size: 26px; font-family: monospace; }
  pre  { background: #f6f8fa; border-radius: 8px; padding: 28px; overflow: auto; margin: 20px 0; }
  pre code { background: none; padding: 0; }
  hr { border: none; border-top: 2px solid #e1e4e8; margin: 32px 0; }
  img { max-width: 100%; border-radius: 8px; margin: 16px 0; display: block; }
  .cover-card { margin-bottom: 40px; }
  .cover-top img { width: 100%; border-radius: 8px; }
  .cover-bottom { padding: 28px 0; }
  .cover-eyebrow { color: #6a737d; font-size: 26px; margin-bottom: 14px; letter-spacing: 0.05em; }
  .cover-title { font-size: 80px; font-weight: 800; color: #111; line-height: 1.25; }
  .cover-tagline { font-size: 44px; color: #6a737d; margin-top: 12px; font-weight: 400; }
  .cover-subtitle { font-size: 30px; color: #6a737d; margin-top: 14px; }
  .body-wrap { padding: 0; }
`;

// plain 模式直接用极简 CSS，否则用完整宝玉风格 CSS
const html = PLAIN_MODE ? `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>${plainCss}</style>
</head>
<body>
${coverHtml}
<div class="body-wrap">
${bodyHtml}
</div>
</body>
</html>` : `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    width: ${PAGE_WIDTH}px;
    background: ${BG_COLOR};
    color: #2A2A2A;
    font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif;
    font-size: ${F(48)}px;
    line-height: 1.9;
    padding: 0;
  }

  /* ── 正文容器 ── */
  .body-wrap {
    padding: 80px 100px 100px;
  }

  /* ══════════════════════════════════════════
     封面卡片：上图下文（@dotey 宝玉风格）
     上：宽幅配图；下：超大黑体标题
     适合截图作小红书首页图
     ══════════════════════════════════════════ */
  .cover-card {
    display: flex;
    flex-direction: column;
    width: 100%;
    overflow: hidden;
    margin-bottom: 0;
    border-bottom: 6px solid rgba(0,0,0,0.06);
  }

  /* 封面上方：图片区域，全宽 */
  .cover-top {
    width: 100%;
    overflow: hidden;
  }
  .cover-img {
    width: 100%;
    display: block;
    object-fit: cover;
  }
  .cover-img-placeholder {
    width: 100%;
    height: 540px;
    background: #E8D5C4;
  }

  /* 封面下方：标题文字区域 */
  .cover-bottom {
    padding: 56px 100px 72px;
    background: ${BG_COLOR};
  }

  /* ── 层次1：眉题（最小，coral 色，小标签感） ── */
  .cover-eyebrow {
    font-size: ${F(42)}px;
    font-weight: 600;
    color: ${ACCENT};
    letter-spacing: 3px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .cover-eyebrow::before {
    content: '';
    display: inline-block;
    width: 40px;
    height: 4px;
    background: ${ACCENT};
    border-radius: 2px;
    flex-shrink: 0;
  }

  /* 主标题 + tagline 的容器 */
  .cover-title-wrap {
    margin-bottom: 0;
  }

  /* ── 层次2：主标题（最大，极粗黑体，纯黑） ── */
  .cover-title {
    font-size: ${F(110)}px;
    font-weight: 900;
    color: #111111;
    line-height: 1.2;
    letter-spacing: -2px;
    margin-bottom: 0;
    word-break: keep-all;
    overflow-wrap: break-word;
  }

  /* ── 层次3：tagline（｜后拆分，coral 色，稍小） ── */
  .cover-tagline {
    font-size: ${F(68)}px;
    font-weight: 700;
    color: ${ACCENT};
    line-height: 1.4;
    margin-top: 12px;
    letter-spacing: 0;
  }

  /* ── 层次4：副标题（最小，灰色，可选） ── */
  .cover-subtitle {
    font-size: ${F(48)}px;
    font-weight: 400;
    color: #888888;
    line-height: 1.6;
    margin-top: 28px;
    border-top: 2px solid rgba(0,0,0,0.08);
    padding-top: 24px;
  }

  /* ── 正文标题层级 ─────────────────── */

  /* H1：大色块左边线 */
  .h1-title {
    font-size: ${F(72)}px;
    font-weight: 800;
    color: #1A1A1A;
    border-left: 10px solid ${ACCENT};
    padding-left: 28px;
    margin: 72px 0 28px;
    line-height: 1.4;
  }
  .h1-title:first-child { margin-top: 0; }

  /* H2：中等色块左边线 */
  .h2-title {
    font-size: ${F(60)}px;
    font-weight: 700;
    color: #1A1A1A;
    border-left: 8px solid ${ACCENT};
    padding-left: 24px;
    margin: 60px 0 22px;
    line-height: 1.4;
  }

  /* H3：小标题，无色块 */
  .h3-title {
    font-size: ${F(52)}px;
    font-weight: 700;
    color: #333333;
    margin: 44px 0 16px;
    padding-left: 4px;
    line-height: 1.4;
  }

  /* **粗体单行** → 节标题（兼容旧格式，同 H2） */
  .section-title {
    font-size: ${F(60)}px;
    font-weight: 700;
    color: #1A1A1A;
    border-left: 8px solid ${ACCENT};
    padding-left: 24px;
    margin: 60px 0 22px;
    line-height: 1.4;
  }
  .section-title:first-child { margin-top: 0; }

  /* ── 正文段落 ── */
  .para {
    font-size: ${F(48)}px;
    color: #2A2A2A;
    margin-bottom: 20px;
    line-height: 1.9;
  }
  strong { font-weight: 700; color: #1A1A1A; }
  em { font-style: italic; color: #444; }
  code {
    background: rgba(0,0,0,0.07);
    border-radius: 6px;
    padding: 2px 10px;
    font-family: Consolas, "Courier New", monospace;
    font-size: ${F(42)}px;
    color: #C0392B;
  }

  /* ── 列表 ── */
  .list-item {
    display: flex;
    align-items: flex-start;
    font-size: ${F(48)}px;
    line-height: 1.9;
    margin-bottom: 12px;
    color: #2A2A2A;
  }
  .list-bullet {
    color: ${ACCENT};
    font-size: ${F(56)}px;
    line-height: 1.6;
    margin-right: 18px;
    flex-shrink: 0;
  }
  .list-num {
    color: ${ACCENT};
    font-weight: 700;
    font-size: ${F(48)}px;
    margin-right: 18px;
    min-width: 60px;
    flex-shrink: 0;
  }

  /* ── 引用块 ── */
  .blockquote {
    border-left: 6px solid #C4A0C8;
    background: rgba(196,160,200,0.12);
    padding: 20px 28px;
    font-size: ${F(44)}px;
    color: #555;
    border-radius: 0 12px 12px 0;
    margin: 20px 0;
    line-height: 1.8;
  }

  /* ── 代码块 ── */
  .code-block {
    background: rgba(0,0,0,0.06);
    border-radius: 14px;
    padding: 32px 36px;
    font-family: Consolas, "Courier New", monospace;
    font-size: ${F(40)}px;
    line-height: 1.75;
    white-space: pre-wrap;
    margin: 24px 0;
    color: #2A2A2A;
    border: 2px solid rgba(0,0,0,0.08);
  }

  /* ── 配图 ── */
  .content-img {
    width: 100%;
    display: block;
    margin: 44px 0;
    border-radius: 20px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.10);
  }

  /* ── 分隔线 ── */
  .hr {
    height: 3px;
    background: linear-gradient(90deg, ${ACCENT}66, transparent);
    border-radius: 2px;
    margin: 56px 0;
  }

  /* ── 间距 ── */
  .spacer { height: 14px; }
</style>
</head>
<body>
${coverHtml}
<div class="body-wrap">
${bodyHtml}
</div>
</body>
</html>`;

// ── Playwright 截图 ────────────────────────────────────────
(async () => {
  const outDir = path.dirname(OUT_FILE);
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch();
  const context = await browser.newContext({ deviceScaleFactor: 2 });
  const page = await context.newPage();

  await page.setViewportSize({ width: PAGE_WIDTH, height: 800 });
  await page.setContent(html, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(600);

  await page.screenshot({ path: OUT_FILE, fullPage: true });
  await browser.close();

  const stat = fs.statSync(OUT_FILE);
  const sizeStr = stat.size > 1024 * 1024
    ? `${(stat.size / 1024 / 1024).toFixed(1)} MB`
    : `${(stat.size / 1024).toFixed(0)} KB`;

  console.log(`\n✓ 长图已生成: ${OUT_FILE}`);
  console.log(`  页面宽度: ${PAGE_WIDTH}px（实际 2x 清晰度）`);
  console.log(`  封面区高: ${COVER_HEIGHT}px（上图下文，适合截图作首页图）`);
  console.log(`  文件大小: ${sizeStr}`);
})();
