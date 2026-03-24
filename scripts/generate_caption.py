# -*- coding: utf-8 -*-
"""
小红书笔记标题正文生成脚本

功能：根据分组信息和原始 MD 内容，为每条笔记生成标题+正文模板。
- 支持三种文案风格：干货型、种草型、故事型
- 自动生成系列引导文案（第 X 篇/共 N 篇）
- 自动提取关键词生成话题标签建议
- 输出 caption.md 到每条笔记目录

依赖：无额外依赖（仅标准库）

使用方式：
    # 生成干货型文案
    python generate_caption.py --posts xhs-output/xhs-posts --source article.md --style 干货型

    # 生成种草型文案
    python generate_caption.py --posts xhs-output/xhs-posts --source article.md --style 种草型

    # 生成故事型文案
    python generate_caption.py --posts xhs-output/xhs-posts --source article.md --style 故事型
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# 支持的文案风格
VALID_STYLES = {"干货型", "种草型", "故事型"}


def extract_headings(md_content: str) -> list[str]:
    """
    从 Markdown 内容中提取所有标题

    Args:
        md_content: Markdown 原始文本

    Returns:
        标题文本列表（去掉 # 标记）
    """
    headings = []
    for line in md_content.splitlines():
        line = line.strip()
        # 匹配 # 开头的标题行
        match = re.match(r"^#{1,4}\s+(.+)$", line)
        if match:
            headings.append(match.group(1).strip())
    return headings


def extract_keywords(md_content: str, max_keywords: int = 10) -> list[str]:
    """
    从 Markdown 内容中提取关键词候选

    简单策略：提取加粗文本、标题文本中的名词性短语作为关键词候选。
    实际使用时 Claude 会基于内容理解生成更好的关键词。

    Args:
        md_content: Markdown 原始文本
        max_keywords: 最大关键词数量

    Returns:
        关键词列表
    """
    keywords = set()

    # 提取加粗文本 **xxx**
    bold_pattern = re.compile(r"\*\*(.+?)\*\*")
    for match in bold_pattern.finditer(md_content):
        text = match.group(1).strip()
        if 2 <= len(text) <= 15:
            keywords.add(text)

    # 提取标题文本
    for heading in extract_headings(md_content):
        if 2 <= len(heading) <= 15:
            keywords.add(heading)

    return list(keywords)[:max_keywords]


def load_split_summary(posts_dir: str) -> dict | None:
    """
    加载 split_summary.json（如果存在）

    Args:
        posts_dir: 笔记目录（xhs-posts）

    Returns:
        摘要字典，或 None
    """
    # split_summary.json 在 posts_dir 的上级目录
    summary_path = Path(posts_dir).parent / "split_summary.json"
    if summary_path.exists():
        with open(summary_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def get_post_dirs(posts_dir: str) -> list[Path]:
    """
    获取所有笔记子目录，按名称排序

    Args:
        posts_dir: 笔记根目录

    Returns:
        排序后的 Path 列表
    """
    posts_path = Path(posts_dir)
    if not posts_path.exists():
        raise FileNotFoundError(f"笔记目录不存在: {posts_dir}")

    dirs = sorted(
        d for d in posts_path.iterdir()
        if d.is_dir() and d.name.startswith("post-")
    )

    if not dirs:
        raise ValueError(f"没有找到 post-XX 子目录: {posts_dir}")

    return dirs


def generate_caption_template(
    post_index: int,
    total_posts: int,
    style: str,
    headings: list[str],
    keywords: list[str],
    source_title: str = "",
) -> str:
    """
    生成单条笔记的标题正文模板

    模板中使用 {{占位符}} 标记需要 Claude 填充的内容。
    脚本生成框架，Claude 在实际执行时填充具体文案。

    Args:
        post_index: 当前笔记序号（从 1 开始）
        total_posts: 总笔记数
        style: 文案风格
        headings: 原文标题列表
        keywords: 提取的关键词
        source_title: 原文标题

    Returns:
        caption.md 的内容文本
    """
    # 系列引导文案
    if total_posts > 1:
        series_text = f"第 {post_index} 篇 / 共 {total_posts} 篇"
        series_guide = (
            f"系列合集请看主页 | {series_text}"
        )
        if post_index < total_posts:
            series_guide += " | 下一篇见评论区置顶"
    else:
        series_text = ""
        series_guide = ""

    # 关键词标签建议
    tag_suggestions = " ".join(f"#{kw}" for kw in keywords[:8])

    # 根据风格生成不同模板
    if style == "干货型":
        template = _template_ganguo(
            post_index, total_posts, series_text, series_guide,
            tag_suggestions, headings, source_title,
        )
    elif style == "种草型":
        template = _template_zhongcao(
            post_index, total_posts, series_text, series_guide,
            tag_suggestions, headings, source_title,
        )
    elif style == "故事型":
        template = _template_gushi(
            post_index, total_posts, series_text, series_guide,
            tag_suggestions, headings, source_title,
        )
    else:
        # 默认干货型
        template = _template_ganguo(
            post_index, total_posts, series_text, series_guide,
            tag_suggestions, headings, source_title,
        )

    return template


def _template_ganguo(
    post_index, total_posts, series_text, series_guide,
    tag_suggestions, headings, source_title,
):
    """干货型文案模板：直接列要点，适合教程/知识分享"""
    heading_list = "\n".join(f"  - {h}" for h in headings[:5]) if headings else "  - （根据本篇内容填写要点）"

    return f"""# 笔记 {post_index} 文案方案

> 风格：干货型 | {series_text}

---

## 方案 A

### 标题
<!-- 标题要求：20-30字，包含核心关键词，带数字或结论 -->
{{{{根据本篇内容生成标题，参考格式：「数字+结论」型}}}}

### 正文
<!-- 正文要求：200-500字，信息密度高，要点清晰 -->

本篇要点涉及：
{heading_list}

{{{{根据以上要点生成正文，格式：}}}}
{{{{1. 开头一句话点明主题}}}}
{{{{2. 分点列出核心内容（3-5个要点）}}}}
{{{{3. 总结一句话}}}}

{series_guide}

{tag_suggestions}

---

## 方案 B

### 标题
<!-- 用「问题+答案」型 -->
{{{{生成另一个角度的标题}}}}

### 正文
{{{{用不同结构重写正文}}}}

{series_guide}

{tag_suggestions}

---

## 方案 C

### 标题
<!-- 用「场景+方法」型 -->
{{{{生成第三个标题}}}}

### 正文
{{{{用更口语化的方式重写}}}}

{series_guide}

{tag_suggestions}
"""


def _template_zhongcao(
    post_index, total_posts, series_text, series_guide,
    tag_suggestions, headings, source_title,
):
    """种草型文案模板：情感驱动，适合推荐/测评"""
    return f"""# 笔记 {post_index} 文案方案

> 风格：种草型 | {series_text}

---

## 方案 A

### 标题
<!-- 标题要求：20-30字，带情绪词+痛点，引发共鸣 -->
{{{{参考格式：「后悔没早知道」「真的绝了」「救命级」型}}}}

### 正文
<!-- 正文要求：200-500字，代入感强，痛点→解决方案→效果 -->

{{{{按以下结构生成：}}}}
{{{{1. 痛点共鸣（你是不是也遇到过...）}}}}
{{{{2. 发现过程（偶然/朋友推荐/研究后...）}}}}
{{{{3. 使用体验（具体效果，用数字说话）}}}}
{{{{4. 推荐理由（为什么值得看/学/用）}}}}

{series_guide}

{tag_suggestions}

---

## 方案 B

### 标题
{{{{用「对比反差」型：之前 vs 之后}}}}

### 正文
{{{{换一个痛点切入，重写正文}}}}

{series_guide}

{tag_suggestions}

---

## 方案 C

### 标题
{{{{用「紧迫感」型：还不知道就亏了}}}}

### 正文
{{{{用清单体重写：5个理由/3个步骤}}}}

{series_guide}

{tag_suggestions}
"""


def _template_gushi(
    post_index, total_posts, series_text, series_guide,
    tag_suggestions, headings, source_title,
):
    """故事型文案模板：叙事结构，适合经验分享"""
    return f"""# 笔记 {post_index} 文案方案

> 风格：故事型 | {series_text}

---

## 方案 A

### 标题
<!-- 标题要求：20-30字，叙事感+悬念，让人想点进来看 -->
{{{{参考格式：「从XX到XX，我经历了...」「做了XX之后，我才发现...」型}}}}

### 正文
<!-- 正文要求：200-500字，叙事结构，有起承转合 -->

{{{{按以下结构生成：}}}}
{{{{1. 起：背景介绍（时间/场景/起因）}}}}
{{{{2. 承：过程描述（遇到了什么/做了什么）}}}}
{{{{3. 转：转折或发现（关键节点/顿悟时刻）}}}}
{{{{4. 合：收获总结（学到了什么/建议什么）}}}}

{series_guide}

{tag_suggestions}

---

## 方案 B

### 标题
{{{{用「自问自答」型：为什么我要...}}}}

### 正文
{{{{换一个叙事角度，如第三人称或倒叙}}}}

{series_guide}

{tag_suggestions}

---

## 方案 C

### 标题
{{{{用「感悟」型：XX教会了我什么}}}}

### 正文
{{{{用更感性的语言重写}}}}

{series_guide}

{tag_suggestions}
"""


def main():
    """
    脚本入口

    读取分组目录和原始 MD，为每条笔记生成 caption.md 模板。
    模板中的 {{占位符}} 部分由 Claude 在实际执行时填充。
    """
    parser = argparse.ArgumentParser(
        description="小红书笔记标题正文生成脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python generate_caption.py --posts xhs-output/xhs-posts --source article.md --style 干货型
  python generate_caption.py --posts xhs-output/xhs-posts --source article.md --style 种草型
  python generate_caption.py --posts xhs-output/xhs-posts --source article.md --style 故事型
        """,
    )

    parser.add_argument(
        "--posts", type=str, required=True,
        help="笔记目录路径（包含 post-XX 子目录）",
    )
    parser.add_argument(
        "--source", type=str, default=None,
        help="原始 Markdown 文件路径（用于提取标题和关键词）",
    )
    parser.add_argument(
        "--style", type=str, default="干货型",
        choices=list(VALID_STYLES),
        help="文案风格：干货型（默认）/ 种草型 / 故事型",
    )
    parser.add_argument(
        "--debug", action="store_true", help="开启调试日志",
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # 获取笔记目录
        post_dirs = get_post_dirs(args.posts)
        total_posts = len(post_dirs)
        logger.info(f"找到 {total_posts} 条笔记目录")

        # 读取原始 MD（如果提供）
        headings = []
        keywords = []
        source_title = ""
        if args.source:
            source_path = Path(args.source)
            if source_path.exists():
                md_content = source_path.read_text(encoding="utf-8")
                headings = extract_headings(md_content)
                keywords = extract_keywords(md_content)
                # 用第一个标题作为文章标题
                if headings:
                    source_title = headings[0]
                logger.info(f"从原文提取 {len(headings)} 个标题, {len(keywords)} 个关键词")
            else:
                logger.warning(f"原始文件不存在: {args.source}")

        # 加载分组摘要（如果存在）
        summary = load_split_summary(args.posts)
        if summary:
            logger.info(f"已加载分组摘要: {summary['total_posts']} 条笔记")

        # 为每条笔记生成 caption.md
        for i, post_dir in enumerate(post_dirs, 1):
            caption_content = generate_caption_template(
                post_index=i,
                total_posts=total_posts,
                style=args.style,
                headings=headings,
                keywords=keywords,
                source_title=source_title,
            )

            caption_path = post_dir / "caption.md"
            caption_path.write_text(caption_content, encoding="utf-8")
            logger.info(f"  {post_dir.name}/caption.md 已生成")

        print(f"\n文案模板生成完成！")
        print(f"  风格: {args.style}")
        print(f"  笔记数: {total_posts}")
        print(f"  每条笔记 3 套标题+正文方案")
        print(f"\n请让 Claude 根据模板中的 {{{{占位符}}}} 填充具体文案内容。")

    except FileNotFoundError as e:
        logger.error(f"文件未找到: {e}")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"参数错误: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"生成失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
