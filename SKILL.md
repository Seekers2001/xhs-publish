---
name: xhs-publish
description: >
  小红书发布全流程编排：用户导出长图 → 按比例拆分 → 生成标题正文。
  当用户提到"发小红书"、"小红书发布"、"XHS发布"、"markdown转小红书笔记"、"文章拆分发小红书"、
  "帮我把这篇文章发到小红书"时使用。即使用户只说"发到小红书"而没有明确提到工作流，也应触发此技能。
compatibility:
  requires: []
  optional:
    - xhs-markdown
    - baoyu-xhs-images
---

# 小红书发布全流程 Skill

将一篇 Markdown 文章从排版到最终拆分为小红书可发布的多条笔记，完整工作流。

## 目的

解决"写完文章到发小红书"之间的完整链路：
1. **用户自行用 Obsidian 或其他工具导出长图**，将长图路径告知 Claude
2. 将长图按指定比例拆分为多条笔记（每条不超过 9 张）
3. 为每条笔记生成标题和正文

**核心理念**：长图由用户自己导出（保证排版正确），Claude 负责拆分和文案。

## 使用方式

```bash
# 标准流程（从长图开始）
/xhs-publish path/to/image.png --split-only

# 拆分时指定比例（默认 3:4）
/xhs-publish path/to/image.png --split-only --aspect-ratio 9:16
/xhs-publish path/to/image.png --split-only --aspect-ratio 3:4
/xhs-publish path/to/image.png --split-only --aspect-ratio 1:1

# 拆分时手动指定分组
/xhs-publish path/to/image.png --split-only --groups "1-6,7-12"

# 指定文案风格
/xhs-publish path/to/article.md --caption-style 种草型
```

## 选项

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--step <N>` | 从第 N 步开始（2/3/4） | 2 |
| `--split-only` | 跳过排版，直接从已有长图拆分 | 否 |
| `--aspect-ratio <比例>` | 拆分比例：`3:4` / `9:16` / `1:1` / `4:3` | 3:4 |
| `--groups "<范围>"` | 手动指定笔记分组，如 `"1-6,7-12"` | 自动分组 |
| `--width <px>` | 输出图片宽度 | 1080 |
| `--page-height <px>` | 长图切分的单页参考高度 | 1440（3:4）/ 1920（9:16） |
| `--caption-style <风格>` | 文案风格：`干货型` / `种草型` / `故事型` | 干货型 |
| `--font-scale <预设/数字>` | 字号缩放：`small`(原始) / `medium` / `large`(默认) / `xlarge` / 自定义数字如 `1.3` | large |

---

## ⚠️ 已知问题与解决方案（实战经验）

### 1. MD 标题必须以 `#` 开头，否则封面不生效

**现象**：标题显示为小字段落，与下方配图无区分，层次感消失。

**原因**：`md_to_longimage.js` 的封面检测依赖 `# ` 前缀，没有 `#` 的标题行被当作普通段落处理。

**修复**：确保 MD 文件第一行格式为：
```markdown
# 主标题｜tagline
```
不要写成：
```markdown
主标题｜tagline        ← 错误，无封面效果
 主标题｜tagline       ← 错误，前面有空格也不行
```

### 2. Windows 上 `python` 命令失效（exit code 49）

**现象**：运行 `python split_images.py` 返回 exit code 49，无任何输出。

**原因**：`C:\Users\JXLFM\AppData\Local\Microsoft\WindowsApps\python.exe` 是 Windows Store 占位程序，不是真正的 Python，会打开应用商店并返回 49。

**修复**：使用完整路径调用真实 Python：
```bash
PYTHON="/c/Users/JXLFM/AppData/Local/Programs/Python/Python312/python.exe"
"$PYTHON" split_images.py ...
```

### 3. 默认背景色已改为纯白

`md_to_longimage.js` 的默认背景色已从暖奶油 `#F5F0E8` 改为纯白 `#ffffff`。
如需恢复暖奶油色，运行时加 `--bg "#F5F0E8"` 参数。

---

## 工作流概览

```
Step 0: 生成主图        Step 1: 配图分析        Step 2: 导出长图        Step 3+4: 拆分 & 文案
────────────────       ────────────────       ─────────────────      ──────────────────────
baoyu-image-gen        baoyu-article-         md_to_longimage.js     split_images.py
生成封面主题插图         illustrator            渲染长图 PNG            按比例切分 → 自动分组
       │               生成章节配图                    │                      │
       ▼                      │                       ▼                 ▼（确认后自动继续）
存入 imgs/ 目录         插入 MD 对应位置          用户告知长图路径    caption.md 写入各 post-xx/
```

**Step 0 生成主图后，Step 1 配图分析可选；Step 2 生成长图；Step 3 确认分组后，Step 4 文案自动执行。**

---

## Step 0: 生成主图（封面插图）

### 目的

为文章生成一张与主题契合的封面插图（放在长图第一屏上方），风格参照 @dotey 宝玉插画：暖奶油底色、flat vector 卡通、coral/teal 配色。

### 执行内容

使用 `baoyu-image-gen`（dashscope / qwen-image-2.0-pro）生成封面插图：

```bash
npx -y bun C:/Users/JXLFM/.claude/skills/baoyu-image-gen/scripts/main.ts \
  --provider dashscope \
  --model qwen-image-2.0-pro \
  --size "1920*1080" \
  --image "文章目录/imgs/01-cover.png" \
  --prompt "flat vector cartoon illustration, warm cream background #F5F0E8, bold black outlines, no gradients, no text. [主题场景描述]. Color palette: coral #E8705A, teal #5BBFAD, golden #F2A65A. Small stars and dots as decorative elements."
```

**主题场景由文章内容自动推断**：

| 文章类型 | 场景建议 |
|---------|---------|
| 审计/会计 | 审计师 + AI界面 + 文件/底稿 图标 |
| 技术/AI | 机器人/代码 + 工具图标 |
| 教程/流程 | 卡通人物操作步骤 |
| 个人成长 | 人物 + 成长/里程碑元素 |

生成后存入文章目录 `imgs/` 文件夹，并在 MD 开头引用：
```markdown
<!-- eyebrow: 标签 -->
# 主标题｜tagline
![封面图描述](imgs/01-cover.png)
```

### 导出选项

- **宝玉风格**（默认，XHS 发布用）：`node md_to_longimage.js --src article.md --out output.png`
- **极简白底**（内容预览用，不做任何样式修改）：`node md_to_longimage.js --src article.md --out output.png --plain`

### 用户确认点
- 生成的主图是否符合预期（可重新描述场景重新生成）
- 确认后进入 Step 1

---

## Step 1: 配图分析（默认询问，原 Step 0）

### 触发条件

启动 `/xhs-publish` 时，**无论用户是否提及配图，Claude 必须主动询问**：

> 是否需要根据文章内容自动生成配图？（对比/流程/数据型内容效果最好）

用户说「需要」「加图」「图文并茂」或不确定时执行；说「不需要」「跳过」或传入 `--no-illustrate` 时跳过直接进 Step 1。

### 执行内容

调用 `baoyu-article-illustrator`，**风格由文章内容自动推断**，不固定风格：

1. **内容分析**：读取 MD 文章，判断内容类型（技术/教程/叙事/数据/观点等）
2. **自动推荐 preset**：根据内容信号匹配最合适的 type + style 组合

| 文章类型 | 自动推荐 preset | 示例 |
|---------|---------------|------|
| 技术/AI/系统 | `tech-explainer`（infographic + blueprint） | 框架对比、系统架构 |
| 教程/流程 | `tutorial`（flowchart + vector-illustration） | 操作步骤、方法论 |
| 数据/对比 | `versus`（comparison + vector-illustration） | 工具对比、方案选型 |
| 个人/成长 | `storytelling`（scene + warm） | 经验分享、复盘 |
| 观点/评论 | `opinion-piece`（scene + screen-print） | 行业洞察、观点文 |
| 知识/概念 | `knowledge-base`（infographic + vector-illustration） | 概念解析、干货整理 |

3. **向用户展示推荐方案**（1 次 AskUserQuestion）：
   - 推荐的 preset + 预期效果说明
   - 每个章节建议配图的位置
   - 预计生成图片数量
4. **用户确认后**：批量生成配图，存入 `imgs/` 子目录
5. **自动插入 MD**：在对应段落后插入 `![](imgs/NN-type-slug.png)`
6. 完成后进入 Step 1（`md_to_longimage.js` 会自动将嵌入图片渲染进长图）

### 参数固化（无需每次询问）

| 参数 | 值 | 说明 |
|------|----|------|
| `--style` | **自动从文章推断** | 不固定，由内容信号决定 |
| `--density` | `per-section` | 每个主要章节一张 |
| `--lang` | `zh` | 中文标签 |
| provider | `dashscope` | 阿里云通义万象 |
| aspect | `16:9` | 横版，适配长图嵌入 |
| quality | `2k` | 2048×1152 |

### 用户确认点
- 推荐的风格方案是否合适（可要求换 preset）
- 配图位置列表（可删减某些位置）
- 确认后批量生成，**不再逐张确认**

---

## Step 2: 导出长图（两种方式）

### ⚠️ 封面格式（强制规范，每篇文章必须）

**所有文章长图的第一屏必须是"上图下文"封面**，参考 @dotey 宝玉风格，四层视觉层次：

```
┌─────────────────────────────────────┐
│                                     │
│         【全宽配图 · 宽幅横图】       │
│                                     │
├─────────────────────────────────────┤
│                                     │
│ ━━ 眉题标签          ← coral 小字    │
│                                     │
│ 主标题文字            ← 96px 极粗黑  │
│                                     │
│ tagline（｜后自动拆） ← 54px coral  │
│                                     │
│ 副标题（可选）        ← 36px 灰色   │
│                                     │
└─────────────────────────────────────┘
```

**层次说明**：
| 层次 | 来源 | 字号/颜色 |
|------|------|----------|
| 眉题 | `<!-- eyebrow: 文字 -->` | 30px coral，左侧色条 |
| 主标题 | `# 标题｜tagline` 的 `｜` 前部分 | 96px 极粗黑体 `#111` |
| tagline | `# 标题｜tagline` 的 `｜` 后部分（自动拆） | 54px coral |
| 副标题 | `## 副标题`（可选） | 36px 灰色 |

**标准 MD 文件写法（脚本全自动识别，无需命令行参数）**：

```markdown
<!-- eyebrow: 审计季干货 -->
# 主标题｜tagline

![](imgs/封面配图.png)

## 副标题（可选）

<!-- PAGE BREAK -->

正文内容...
```

> `｜` 为全角竖线，自动将标题拆为主题（黑体）+ tagline（coral色）两部分，无需额外参数。

### 封面配图生成（使用 baoyu-cover-image）

**封面图必须在运行 `md_to_longimage.js` 之前准备好**。使用 `baoyu-cover-image` skill 生成：

```bash
# 根据文章标题和主题自动生成封面图
/baoyu-cover-image --title "审计人用AI的回答复核意见" --style warm
```

生成后将封面图放入 `imgs/` 目录，MD 文件中引用即可：
```markdown
![审计人用AI的6大场景全景图](imgs/01-cover.png)
```

**封面图风格建议**（与文章内容匹配）：

| 文章类型 | 推荐风格参数 |
|---------|------------|
| 审计/专业知识 | `--style minimal` 或 `--style warm` |
| 教程/干货 | `--style bold` |
| 个人/成长 | `--style warm` |

---

**最简运行命令（MD 内已包含所有封面信息）**：

```bash
node C:/Users/JXLFM/.claude/skills/xhs-publish/scripts/md_to_longimage.js \
  --src "F:/path/to/article.md" \
  --out "F:/path/to/output.png"
```

**备用参数（MD 内没有封面信息时使用）**：

```bash
node C:/Users/JXLFM/.claude/skills/xhs-publish/scripts/md_to_longimage.js \
  --src "article.md" \
  --out "output.png" \
  --cover-title "主标题｜tagline" \
  --cover-img "imgs/封面图.png" \
  --cover-eyebrow "眉题标签"
```

---

### 方式 A：脚本自动渲染（推荐）

使用内置脚本 `scripts/md_to_longimage.js` 将 MD 渲染为长图：

**排版风格**：暖奶油背景 · 左对齐 · `**粗体行**` 自动变为左侧色块标题 · 配图自动嵌入
**视觉基调**：@dotey 宝玉风格，背景暖奶油色 + coral/teal/golden 五色轮换色块

```bash
node C:/Users/JXLFM/.claude/skills/xhs-publish/scripts/md_to_longimage.js \
  --src "F:/path/to/article.md" \
  --out "F:/path/to/output.png"

# 可选覆盖参数：
#   --accent "#E8705A"   色块主色（默认 coral）
#   --bg     "#F5F0E8"   背景色（默认暖奶油）
#   --width  1440        渲染宽度
#   --cover-title "标题" 强制封面标题（MD 无 # 标题时使用）
#   --cover-img "图.png" 强制封面图（MD 无首图时使用）
```

**渲染规则**：
| Markdown 格式 | 渲染效果 |
|--------------|---------|
| `<!-- eyebrow: 文字 -->` | 封面眉题（coral 小标签，左侧色条） |
| `# 主标题｜tagline` + `![](图)` | **封面：上图下文，四层层次**（强制规范） |
| `## 副标题`（封面内） | 封面副标题（灰色细字） |
| `**单独一行粗体**` | 左侧色块 + 加粗节标题（五色轮换） |
| `## 标题` / `# 标题`（正文中） | 色块节标题 |
| `普通段落文字` | 左对齐正文，字号 34px |
| `**行内粗体**` | 加粗文字 |
| `- 列表项` | coral 圆点列表 |
| `` ```代码块``` `` | 圆角代码区 |
| `![alt](图片路径)` | 嵌入配图，圆角阴影 |

**注意**：需要 Node.js + Playwright（`npx playwright install chromium`）

---

### 方式 B：用户自行导出长图

用户使用自己熟悉的工具将 MD 导出为长图 PNG，保证排版完全正确。

**常用工具**：
- Obsidian → 安装 `obsidian-export-image` 插件 → 导出 PNG
- Typora → 文件 → 导出 → 图片
- 截图工具（Snipaste 等）长图截取

导出完成后，告知 Claude：
- **长图路径**（完整路径，如 `F:\2-Learn\...\article.png`）
- **拆分比例**（3:4 / 9:16 / 1:1 / 4:3，默认 3:4）

**Claude 收到路径和比例后，直接进入 Step 3。**

---

## Step 3: 拆分发布

### 目的
将用户提供的长图按指定比例拆分为多条笔记，每条不超过 9 张图。

### 支持比例

| 比例 | 输出尺寸 | 适用场景 |
|------|---------|---------|
| `3:4` | 1080x1440 | 小红书标准竖图（默认） |
| `9:16` | 1080x1920 | 全屏竖图，沉浸感强 |
| `1:1` | 1080x1080 | 方图，适合图文混排 |
| `4:3` | 1080x810 | 横图 |

### 执行内容

运行拆分脚本，**输出到桌面新建文件夹**（文件夹名取自长图文件名）：

```bash
# 输出目录自动设为：C:\Users\JXLFM\Desktop\{文件名}-xhs\
python C:/Users/JXLFM/.claude/skills/xhs-publish/scripts/split_images.py \
  --src "长图路径.png" \
  --out "C:/Users/JXLFM/Desktop/{文件名}-xhs" \
  --long-image \
  --aspect-ratio 3:4
```

**输出目录命名规则**：取长图文件名（去掉扩展名），加 `-xhs` 后缀，放在桌面。
例如：长图为 `做审计的你.png` → 输出到 `C:\Users\JXLFM\Desktop\做审计的你-xhs\`

**询问用户比例**：如果用户未指定，使用 AskUserQuestion 让用户选择 3:4 / 9:16 / 1:1 / 4:3。

### 分组策略

**自动分组（默认）**：脚本根据总张数均匀分配，每组不超过 9 张。

**手动分组**：通过 `--groups` 参数指定范围（页码从 1 开始）：
```bash
--groups "1-6,7-12"
```

### 输出结构
```
桌面/
└── {文件名}-xhs/               # 自动创建，名称取自长图文件名
    ├── post-01/
    │   ├── 01.png ~ NN.png     # 1080x目标高度
    │   └── caption.md          # Step 4 生成
    ├── post-02/
    │   └── ...
    └── split_summary.json      # 分组摘要
```

示例：长图 `做审计的你.png` → 桌面生成 `做审计的你-xhs/post-01/` ...

### 用户确认点
- 拆分后的分组方案（每条笔记页码范围和张数）
- 如需调整，使用 `--groups` 重新运行

**用户确认分组后，立即执行文案生成，无需再次确认。**

---

## Step 4: 生成文案（随 Step 3 自动执行）

拆分完成后**立即**为每条笔记生成 `caption.md`，与图片放在同一目录，不需要用户单独触发。

### 执行内容

1. 读取分组信息（`split_summary.json`）
2. 读取原始 MD 内容（**如有**）作为文案依据；若仅有长图无 MD，则根据用户描述或图片内容推断主题
3. 按选定风格生成每条笔记的 2-3 套标题+正文方案
4. 自动添加系列引导（第 X 篇/共 N 篇）
5. 自动生成话题标签建议（5-8 个）
6. **写入 `post-xx/caption.md`，与图片同目录**

> 如果用户只提供了长图（无 MD），在 Step 3 执行前询问：文章主题/关键词是什么？用于生成更准确的文案。

### 文案风格

| 风格 | 适用场景 | 特点 |
|------|---------|------|
| **干货型**（默认） | 教程、知识分享、技术文 | 直接列要点，信息密度高 |
| **种草型** | 推荐、测评、好物分享 | 情感驱动，痛点共鸣 |
| **故事型** | 经验分享、复盘、成长记录 | 叙事结构，代入感强 |

### 标题要求
- 20-30 字（小红书推荐长度）
- 包含核心搜索关键词
- 带情绪钩子或痛点引导
- 适当使用数字和符号增加点击率

### 正文要求
- 200-500 字
- 内容概要 + 核心价值点
- 系列引导（第 X 篇/共 N 篇，上/下篇在评论区）
- 末尾 5-8 个话题标签

### 最终输出结构
```
桌面/
└── {文件名}-xhs/
    ├── post-01/
    │   ├── 01.png ~ NN.png
    │   └── caption.md    ← 2-3 套标题+正文，直接复制发布
    ├── post-02/
    │   ├── 01.png ~ NN.png
    │   └── caption.md
    └── split_summary.json
```

---

## 进度清单

```
XHS 发布全流程进度：
- [ ] Step 0: 生成主图（baoyu-image-gen，封面插图）
  - [ ] 分析文章主题，自动推断场景描述
  - [ ] 生成 1920×1080 封面插图，存入 imgs/ 目录
  - [ ] 在 MD 开头引用封面图（# 标题｜tagline + ![](imgs/...)）
- [ ] Step 1: 配图分析（可选，baoyu-article-illustrator）
  - [ ] 分析文章内容类型，自动推荐 preset（type + style）
  - [ ] 用户确认配图位置和风格方案
  - [ ] 批量生成配图，插入 MD 对应位置
- [ ] Step 2: 导出长图
  - [ ] 宝玉风格（默认）：node md_to_longimage.js --src article.md --out output.png
  - [ ] 极简白底（预览）：node md_to_longimage.js --src article.md --out output.png --plain
  - [ ] 告知 Claude 长图路径和拆分比例
- [ ] Step 3+4: 拆分 & 文案（合并执行）
  - [ ] 询问拆分比例（3:4/9:16/1:1/4:3）
  - [ ] 执行拆分，输出到桌面 {文件名}-xhs/
  - [ ] 紧接着为每条笔记生成 caption.md（无需再确认）
  - [ ] caption.md 与图片放在同一 post-xx/ 目录
```

---

## 错误恢复

| 步骤 | 常见错误 | 恢复方式 |
|------|---------|---------|
| Step 1 | 分页后内容丢失 | 检查备份文件（`*-backup-*.md`），恢复后重试 |
| Step 3 | Pillow 未安装 | `pip install Pillow` |
| Step 3 | 图片尺寸不标准 | 检查长图宽度，建议导出时设置宽度为 1080 的倍数 |
| Step 3 | 分组超过 9 张 | 使用 `--groups` 手动指定分组 |
| Step 4 | 文案风格不满意 | 使用 `--caption-style` 切换风格重新生成 |

### 从中断恢复

| 当前状态 | 恢复方式 |
|---------|---------|
| 已有长图 | `--split-only` 直接拆分 |
| 已有拆分好的图片 | `--step 4` 只生成文案 |

---

## 配图偏好（风格自动推断）

当文章需要生成配图时（调用 `baoyu-article-illustrator`），**以下参数固化，风格由文章内容自动推断**：

### 固化参数（无需询问）
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--style` | **由文章内容自动推断** | 技术文→blueprint/vector，叙事→warm，观点→screen-print 等 |
| `--lang` | `zh` | 中文界面和标签 |
| `--density` | `per-section` | 每个主要章节一张 |
| provider | `dashscope` | 阿里云通义万象 |
| aspect | `16:9` | 横版，适配文章内嵌 |
| quality | `2k` | 2048×1152 |

### 视觉规范（固化，参考 @dotey 宝玉风格）

**以下视觉参数固化不变，所有配图保持视觉一致性**：

| 参数 | 值 | 说明 |
|------|----|------|
| 背景色 | 暖奶油白 `#F5F0E8` | 所有图统一底色 |
| 主色调 | coral `#E8705A`、teal `#5BBFAD`、golden `#F2A65A`、blue `#7BB8D4`、purple `#C4A0C8` | 五色系循环使用 |
| 笔触风格 | flat vector，粗黑轮廓线，无渐变，无摄影元素 | 卡通插画感 |
| 人物/吉祥物 | 简化卡通剪影，圆润比例，禁止写实 | 可设置品牌吉祥物 |
| 装饰元素 | 齿轮、星光、圆点、对话框等小元素点缀 | 增加活泼感 |
| 文字 | 中文，粗体，高对比，与背景色块搭配 | 可读性优先 |
| 整体感 | 信息密度适中，构图有留白，视觉层次清晰 | 参考 @dotey 宝玉系列 |

### 布局类型自动推断（type 随内容变化）

视觉风格不变，**只有 type（布局结构）根据文章内容自动选择**：

| 文章类型信号 | 推荐 type | 示例画面 |
|------------|----------|---------|
| AI/技术/系统/代码 | `infographic` | 功能分区图、能力对比 |
| 教程/步骤/流程 | `flowchart` | 流程箭头图 |
| 数据/方案对比/vs | `comparison` | 左右分栏对比 |
| 个人/成长/经验 | `scene` | 人物场景叙事图 |
| 知识/概念/干货 | `infographic` | 核心概念拆解图 |
| 产品/生态/功能全景 | `framework` | 椭圆放射图、矩阵图 |
| 历史/进化/时间线 | `timeline` | 水平/垂直时间轴 |

**prompt 中需加入风格约束语**（每张图生成时自动附加）：
```
warm cream background #F5F0E8, flat vector cartoon style, bold black outlines,
coral #E8705A + teal #5BBFAD + golden #F2A65A + blue #7BB8D4 color palette,
simplified cartoon characters, no gradients, no photography, clean Chinese typography,
decorative elements: gears/stars/dots/speech bubbles, inspired by @dotey baoyu illustration style
```

### 触发规则
- **Step 0 流程触发**：启动时主动询问是否配图，确认后自动执行
- **对话中触发**：用户说「加配图」「生成插图」「图文并茂」时，执行 Step 0 流程
- 推荐 type 给用户确认，**视觉风格约束不需要确认，直接应用**

---

## 注意事项

1. **长图由用户导出**：不再使用自动截图，避免排版失真
2. **比例必须确认**：每次拆分前询问用户选择比例，不要假设
3. **分步确认**：每步单独调用，用户确认后再进下一步
4. **Python 环境**：拆分脚本需要 Pillow 库（`pip install Pillow`）
5. **输出路径**：默认输出到桌面 `{文件名}-xhs/` 文件夹
6. **文案参考**：详细的小红书文案写作指南见 `references/caption-guide.md`
