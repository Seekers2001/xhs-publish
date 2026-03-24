# xhs-publish — 小红书发布全流程 Claude Code Skill

将一篇 Markdown 文章从排版到拆分，一键完成小红书发布准备。

## 功能概览

核心理念：长图由用户自行导出（保证排版正确），Claude 负责拆分和生成文案。

工作流分四步：
- Step 0: 生成封面主图（baoyu-image-gen）
- Step 1: 文章配图，可选（baoyu-article-illustrator）
- Step 2: 导出长图（md_to_longimage.js 或手动导出）
- Step 3+4: 拆分 & 生成文案（split_images.py）

---

## 安装

### 第一步：安装依赖的 baoyu skills

本 skill 依赖 [JimLiu/baoyu-skills](https://github.com/JimLiu/baoyu-skills)，需要先安装：

```bash
git clone https://github.com/JimLiu/baoyu-skills.git /tmp/baoyu-skills
cp -r /tmp/baoyu-skills/skills/baoyu-image-gen ~/.claude/skills/
cp -r /tmp/baoyu-skills/skills/baoyu-article-illustrator ~/.claude/skills/
cp -r /tmp/baoyu-skills/skills/baoyu-cover-image ~/.claude/skills/
cp -r /tmp/baoyu-skills/skills/baoyu-xhs-images ~/.claude/skills/
```

### 第二步：安装 xhs-publish

```bash
git clone https://github.com/Seekers2001/xhs-publish.git /tmp/xhs-publish
cp -r /tmp/xhs-publish ~/.claude/skills/xhs-publish
```

### 第三步：安装运行环境依赖

```bash
# Node.js 长图渲染
npx playwright install chromium

# Python 图片拆分
pip install Pillow
```

### 第四步：配置 API Key

```bash
# 阿里云通义万象（推荐，国内访问稳定）
export DASHSCOPE_API_KEY="your_key_here"

# 或 OpenAI
export OPENAI_API_KEY="your_key_here"
```

---

## 使用方式

在 Claude Code 中直接说：

- "帮我把这篇文章发到小红书"
- "发小红书"
- "XHS 发布"

或使用命令：

```bash
# 从长图开始拆分（最常用）
/xhs-publish path/to/image.png --split-only

# 指定拆分比例
/xhs-publish path/to/image.png --split-only --aspect-ratio 9:16

# 指定文案风格
/xhs-publish path/to/article.md --caption-style 种草型
```

---

## 支持的拆分比例

| 比例 | 输出尺寸 | 适用场景 |
|------|---------|---------|
| 3:4（默认） | 1080×1440 | 小红书标准竖图 |
| 9:16 | 1080×1920 | 全屏竖图 |
| 1:1 | 1080×1080 | 方图 |
| 4:3 | 1080×810 | 横图 |

---

## 输出结构

```
桌面/
└── {文件名}-xhs/
    ├── post-01/
    │   ├── 01.png ~ NN.png
    │   └── caption.md    ← 2-3 套标题+正文，直接复制发布
    ├── post-02/
    └── split_summary.json
```

---

## 依赖关系

| 依赖 | 类型 | 用途 |
|------|------|------|
| [baoyu-image-gen](https://github.com/JimLiu/baoyu-skills) | 必须 | Step 0 封面图生成 |
| [baoyu-article-illustrator](https://github.com/JimLiu/baoyu-skills) | 必须 | Step 1 文章配图 |
| [baoyu-cover-image](https://github.com/JimLiu/baoyu-skills) | 必须 | Step 2 封面图 |
| [baoyu-xhs-images](https://github.com/JimLiu/baoyu-skills) | 可选 | XHS 风格图生成 |
| Node.js 18+ | 环境 | 长图渲染 |
| Playwright chromium | 环境 | 长图截图 |
| Python 3.10+ | 环境 | 图片拆分 |
| Pillow | Python 库 | 图片处理 |

---

## Windows 用户注意

`python` 命令可能指向应用商店占位程序，请使用完整路径：

```
C:\Users\{用户名}\AppData\Local\Programs\Python\Python312\python.exe
```

---

## License

MIT
