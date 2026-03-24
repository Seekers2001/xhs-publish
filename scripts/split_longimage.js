/**
 * split_longimage.js
 * 将长图按 3:4（或其他比例）拆分为小红书图片，每组最多 9 张
 *
 * 依赖：Playwright（已通过 md_to_longimage.js 安装）
 *
 * 用法：
 *   node split_longimage.js --src <长图路径> --out <输出目录> --aspect-ratio 3:4
 */

const { chromium } = require('C:/Users/JXLFM/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright-core');
const fs = require('fs');
const path = require('path');

// 解析命令行参数
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
  console.error('用法: node split_longimage.js --src <长图路径> --out <输出目录> [--aspect-ratio 3:4]');
  process.exit(1);
}

const SRC = path.resolve(opts.src);
const OUT_DIR = path.resolve(opts.out);
const ASPECT = opts['aspect-ratio'] || '3:4';
const MAX_PER_POST = 9;

// 解析比例
const [wr, hr] = ASPECT.split(':').map(Number);
const OUT_WIDTH = 1080;
const PAGE_HEIGHT = Math.round(OUT_WIDTH * hr / wr);  // 3:4 → 1440

console.log(`长图路径: ${SRC}`);
console.log(`输出目录: ${OUT_DIR}`);
console.log(`输出比例: ${ASPECT}，每页高度: ${PAGE_HEIGHT}px`);

// 图片转 base64
const ext = path.extname(SRC).slice(1).toLowerCase();
const mime = ext === 'jpg' ? 'image/jpeg' : `image/${ext}`;
const imgData = fs.readFileSync(SRC).toString('base64');
const dataUrl = `data:${mime};base64,${imgData}`;

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({ deviceScaleFactor: 1 });
  const page = await context.newPage();

  // 先用一个临时页面获取图片原始尺寸
  await page.setViewportSize({ width: 100, height: 100 });
  await page.setContent(`<img id="img" src="${dataUrl}" style="position:absolute;top:0;left:0;">`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(300);

  const { naturalWidth, naturalHeight } = await page.evaluate(() => {
    const img = document.getElementById('img');
    return { naturalWidth: img.naturalWidth, naturalHeight: img.naturalHeight };
  });

  console.log(`原始尺寸: ${naturalWidth}x${naturalHeight}`);

  // 缩放后的高度
  const scale = OUT_WIDTH / naturalWidth;
  const scaledHeight = Math.round(naturalHeight * scale);
  console.log(`缩放后: ${OUT_WIDTH}x${scaledHeight}`);

  // 计算页数
  const totalPages = Math.ceil(scaledHeight / PAGE_HEIGHT);
  console.log(`切割为 ${totalPages} 页`);

  // 分组（每组最多 9 张）
  const totalPosts = Math.ceil(totalPages / MAX_PER_POST);
  const posts = [];
  for (let i = 0; i < totalPosts; i++) {
    const start = i * MAX_PER_POST;
    const end = Math.min(start + MAX_PER_POST, totalPages);
    posts.push({ start, end });
  }
  console.log(`分为 ${totalPosts} 条笔记`);

  // 准备渲染页面（用于截图每一页）
  await page.setViewportSize({ width: OUT_WIDTH, height: PAGE_HEIGHT });
  await page.setContent(`
    <html><head><style>
      * { margin: 0; padding: 0; box-sizing: border-box; }
      body { width: ${OUT_WIDTH}px; background: white; overflow: hidden; }
      img { width: ${OUT_WIDTH}px; height: ${scaledHeight}px; display: block; object-fit: fill; }
    </style></head>
    <body><img id="img" src="${dataUrl}"></body>
    </html>
  `, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(500);

  // 确保输出目录存在
  if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });

  // 截图每一页，写入对应的 post 目录
  for (let pi = 0; pi < posts.length; pi++) {
    const { start, end } = posts[pi];
    const postName = `post-${(pi + 1).toString().padStart(2, '0')}`;
    const postDir = path.join(OUT_DIR, postName);
    if (!fs.existsSync(postDir)) fs.mkdirSync(postDir, { recursive: true });

    console.log(`\n${postName}: 第 ${start + 1}-${end} 页`);

    for (let p = start; p < end; p++) {
      const y = p * PAGE_HEIGHT;
      const imgIdx = (p - start + 1).toString().padStart(2, '0');
      const outFile = path.join(postDir, `${imgIdx}.png`);

      // 滚动到对应位置截图
      await page.evaluate((scrollY) => window.scrollTo(0, scrollY), y);
      await page.waitForTimeout(100);

      await page.screenshot({
        path: outFile,
        clip: { x: 0, y: 0, width: OUT_WIDTH, height: PAGE_HEIGHT }
      });

      console.log(`  ✓ ${postName}/${imgIdx}.png`);
    }
  }

  await browser.close();

  // 输出摘要
  console.log('\n==============================');
  console.log('拆分完成！');
  console.log(`总页数: ${totalPages}`);
  console.log(`笔记数: ${totalPosts}`);
  for (let i = 0; i < posts.length; i++) {
    const { start, end } = posts[i];
    console.log(`  post-${(i + 1).toString().padStart(2, '0')}: ${end - start} 张图（第 ${start + 1}-${end} 页）`);
  }
  console.log(`\n输出目录: ${OUT_DIR}`);
})();
