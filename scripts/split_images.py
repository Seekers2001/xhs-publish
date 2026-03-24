# -*- coding: utf-8 -*-
"""
小红书图片拆分脚本

功能：将章节截图或长图按小红书发布规格拆分为多条笔记。
- 支持目录批量拆分（章节截图）
- 支持单张长图按固定高度切割
- 自动分组（每组 ≤9 张）
- 输出 split_summary.json 记录分组元数据

依赖：Pillow（pip install Pillow）

使用方式：
    # 拆分章节图片目录（自动分组）
    python split_images.py --src xhs-output/images --out xhs-output/xhs-posts

    # 拆分单张长图
    python split_images.py --src full-content.png --out xhs-output/xhs-posts --long-image

    # 手动指定分组（页码从 1 开始）
    python split_images.py --src xhs-output/images --out xhs-output/xhs-posts --groups "1-5,6-10,11-16"
"""

import argparse
import json
import logging
import os
import shutil
import sys
from pathlib import Path

# 小红书单条笔记最大图片数
MAX_PER_POST = 9
# 默认输出宽度（小红书推荐）
DEFAULT_WIDTH = 1080
# 默认单页高度（约 9:17 比例，长图滚动友好）
DEFAULT_PAGE_HEIGHT = 2016
# 单张图片大小警告阈值（20MB，小红书上传限制）
FILE_SIZE_WARN_MB = 20

# 支持的比例预设（宽:高），输出高度 = 宽度 * 高/宽
ASPECT_RATIO_PRESETS = {
    "3:4":  (3, 4),   # 竖图，小红书最常用
    "9:16": (9, 16),  # 手机全屏竖图
    "1:1":  (1, 1),   # 方图
    "4:3":  (4, 3),   # 横图
}
DEFAULT_ASPECT_RATIO = "3:4"

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def check_pillow():
    """检查 Pillow 是否已安装，未安装则提示并退出"""
    try:
        from PIL import Image  # noqa: F401
        return True
    except ImportError:
        logger.error("Pillow 未安装，请执行: pip install Pillow")
        sys.exit(1)


def get_image_files(src_dir: str) -> list[str]:
    """
    获取目录下所有 PNG/JPG 图片文件，按文件名排序

    Args:
        src_dir: 图片目录路径

    Returns:
        排序后的图片文件名列表

    Raises:
        FileNotFoundError: 目录不存在
        ValueError: 目录下没有图片文件
    """
    src_path = Path(src_dir)
    if not src_path.exists():
        raise FileNotFoundError(f"目录不存在: {src_dir}")
    if not src_path.is_dir():
        raise ValueError(f"不是目录: {src_dir}")

    # 支持的图片格式
    extensions = {".png", ".jpg", ".jpeg", ".webp"}
    files = sorted(
        f.name for f in src_path.iterdir()
        if f.is_file() and f.suffix.lower() in extensions
    )

    if not files:
        raise ValueError(f"目录下没有图片文件: {src_dir}")

    return files


def auto_group(file_count: int, max_per_post: int = MAX_PER_POST) -> dict[str, list[int]]:
    """
    根据图片数量自动均匀分组

    分组策略：
    - 尽量均匀分配，每组不超过 max_per_post 张
    - 优先让每组数量接近，而不是前面塞满后面剩余

    Args:
        file_count: 总图片数量
        max_per_post: 每条笔记最大图片数，默认 9

    Returns:
        分组字典，如 {"post-01": [0,1,2,3,4], "post-02": [5,6,7,8,9]}

    示例：
        >>> auto_group(16, 9)
        {"post-01": [0..7], "post-02": [8..15]}  # 8+8
        >>> auto_group(10, 9)
        {"post-01": [0..4], "post-02": [5..9]}   # 5+5
    """
    if file_count <= 0:
        raise ValueError(f"图片数量必须大于 0，当前: {file_count}")

    if file_count <= max_per_post:
        # 单条笔记就够了
        return {"post-01": list(range(file_count))}

    # 计算需要几条笔记
    import math
    num_posts = math.ceil(file_count / max_per_post)

    # 均匀分配：每组基础数量 + 余数分配给前几组
    base_size = file_count // num_posts
    remainder = file_count % num_posts

    groups = {}
    idx = 0
    for i in range(num_posts):
        # 前 remainder 组多分配 1 张
        group_size = base_size + (1 if i < remainder else 0)
        group_indices = list(range(idx, idx + group_size))
        group_name = f"post-{i + 1:02d}"
        groups[group_name] = group_indices
        idx += group_size

    return groups


def parse_groups(groups_str: str, file_count: int) -> dict[str, list[int]]:
    """
    解析手动分组字符串

    格式："1-5,6-10,11-16"（页码从 1 开始）

    Args:
        groups_str: 分组字符串
        file_count: 总文件数（用于校验范围）

    Returns:
        分组字典（索引从 0 开始）

    Raises:
        ValueError: 格式错误或范围越界
    """
    groups = {}
    parts = groups_str.strip().split(",")

    for i, part in enumerate(parts):
        part = part.strip()
        if "-" not in part:
            raise ValueError(f"分组格式错误，应为 '起-止'，实际: '{part}'")

        try:
            start_str, end_str = part.split("-", 1)
            start = int(start_str.strip())
            end = int(end_str.strip())
        except ValueError:
            raise ValueError(f"分组数字解析失败: '{part}'")

        if start < 1 or end > file_count:
            raise ValueError(
                f"分组范围越界: {start}-{end}，有效范围: 1-{file_count}"
            )
        if start > end:
            raise ValueError(f"起始页不能大于结束页: {start}-{end}")

        group_size = end - start + 1
        if group_size > MAX_PER_POST:
            logger.warning(
                f"分组 {start}-{end} 包含 {group_size} 张图，"
                f"超过小红书单条上限 {MAX_PER_POST} 张"
            )

        # 页码从 1 开始 → 索引从 0 开始
        group_name = f"post-{i + 1:02d}"
        groups[group_name] = list(range(start - 1, end))

    return groups


def check_file_sizes(src_dir: str, files: list[str]):
    """
    检查图片文件大小，超过阈值时发出警告

    Args:
        src_dir: 图片目录
        files: 文件名列表
    """
    for f in files:
        filepath = Path(src_dir) / f
        size_mb = filepath.stat().st_size / (1024 * 1024)
        if size_mb > FILE_SIZE_WARN_MB:
            logger.warning(
                f"文件 {f} 大小 {size_mb:.1f}MB，超过小红书 {FILE_SIZE_WARN_MB}MB 上传限制，"
                "建议压缩后再上传"
            )


def get_target_height(width: int, aspect_ratio: str) -> int | None:
    """
    根据比例预设计算目标高度

    Args:
        width: 输出宽度
        aspect_ratio: 比例字符串，如 "3:4"，传 None 表示不裁剪（保持原比例）

    Returns:
        目标高度（像素），None 表示不裁剪
    """
    if aspect_ratio is None:
        return None
    if aspect_ratio not in ASPECT_RATIO_PRESETS:
        raise ValueError(
            f"不支持的比例: {aspect_ratio}，可选: {', '.join(ASPECT_RATIO_PRESETS.keys())}"
        )
    w_ratio, h_ratio = ASPECT_RATIO_PRESETS[aspect_ratio]
    return int(width * h_ratio / w_ratio)


def crop_to_ratio(img, width: int, target_height: int):
    """
    将图片裁剪/填充到目标比例

    策略：
    - 图片高度 > 目标高度：从顶部裁剪，保留顶部内容（适合竖向阅读）
    - 图片高度 < 目标高度：底部填充白色，保持内容完整
    - 图片高度 == 目标高度：直接返回

    Args:
        img: PIL Image 对象（已缩放到目标宽度）
        width: 目标宽度
        target_height: 目标高度

    Returns:
        裁剪/填充后的 PIL Image
    """
    from PIL import Image

    w, h = img.size

    if h == target_height:
        return img
    elif h > target_height:
        # 裁剪：从顶部取 target_height 高度
        return img.crop((0, 0, width, target_height))
    else:
        # 填充：底部补白
        new_img = Image.new("RGB", (width, target_height), (255, 255, 255))
        new_img.paste(img, (0, 0))
        return new_img


def split_for_xhs(
    src_dir: str,
    out_dir: str,
    groups: dict[str, list[int]] | None = None,
    width: int = DEFAULT_WIDTH,
    max_per_post: int = MAX_PER_POST,
    aspect_ratio: str | None = DEFAULT_ASPECT_RATIO,
) -> dict:
    """
    将章节图片按分组缩放输出，支持比例裁剪

    Args:
        src_dir: 章节图片目录（含编号 PNG）
        out_dir: 输出根目录
        groups: 分组字典，如 {"post-01": [0,1,2], "post-02": [3,4,5]}
                传 None 时自动分组
        width: 输出宽度，默认 1080px
        max_per_post: 每条笔记最大图片数，默认 9
        aspect_ratio: 输出比例，如 "3:4"/"9:16"/"1:1"/"4:3"，None 表示保持原比例

    Returns:
        分组摘要字典（同时保存为 split_summary.json）
    """
    from PIL import Image

    files = get_image_files(src_dir)
    logger.info(f"找到 {len(files)} 张图片，来源: {src_dir}")

    # 计算目标高度
    target_height = get_target_height(width, aspect_ratio)
    if target_height:
        logger.info(f"输出比例: {aspect_ratio}，目标尺寸: {width}x{target_height}")
    else:
        logger.info(f"输出宽度: {width}px，保持原比例")

    # 检查文件大小
    check_file_sizes(src_dir, files)

    # 如果没有指定分组，自动分组
    if groups is None:
        groups = auto_group(len(files), max_per_post)
        logger.info(f"自动分组: {len(groups)} 条笔记")

    # 清理输出目录
    out_path = Path(out_dir)
    if out_path.exists():
        shutil.rmtree(out_path)

    # 记录分组摘要
    summary = {
        "total_images": len(files),
        "total_posts": len(groups),
        "output_width": width,
        "aspect_ratio": aspect_ratio or "原比例",
        "posts": [],
    }

    for post_name, indices in groups.items():
        post_dir = out_path / post_name
        post_dir.mkdir(parents=True, exist_ok=True)

        post_info = {
            "name": post_name,
            "images": len(indices),
            "pages": f"{indices[0] + 1}-{indices[-1] + 1}",
            "files": [],
        }

        for i, idx in enumerate(indices, 1):
            if idx >= len(files):
                logger.warning(f"索引 {idx} 超出文件范围（共 {len(files)} 个文件），跳过")
                continue

            src_file = Path(src_dir) / files[idx]
            img = Image.open(src_file).convert("RGB")
            w, h = img.size

            # 先按目标宽度等比缩放
            new_h = int(h * width / w)
            img_resized = img.resize((width, new_h), Image.LANCZOS)

            # 再按比例裁剪/填充
            if target_height:
                img_resized = crop_to_ratio(img_resized, width, target_height)
                final_size = f"{width}x{target_height}"
            else:
                final_size = f"{width}x{new_h}"

            out_file = post_dir / f"{i:02d}.png"
            img_resized.save(str(out_file), "PNG", optimize=True)
            post_info["files"].append(str(out_file.name))

            logger.debug(f"  {files[idx]} → {out_file} ({final_size})")

        summary["posts"].append(post_info)
        logger.info(
            f"  {post_name}: {len(indices)} 张图 (页 {post_info['pages']})"
        )

    # 保存分组摘要到输出目录的上级
    summary_path = out_path.parent / "split_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    logger.info(f"分组摘要已保存: {summary_path}")

    return summary


def split_long_image(
    src_path: str,
    out_dir: str,
    width: int = DEFAULT_WIDTH,
    page_height: int = DEFAULT_PAGE_HEIGHT,
    max_per_post: int = MAX_PER_POST,
    aspect_ratio: str | None = DEFAULT_ASPECT_RATIO,
) -> dict:
    """
    将单张长图按固定高度拆分，再按笔记分组输出

    步骤：
    1. 缩放到目标宽度
    2. 按 page_height 等分切割
    3. 自动分组（每组 ≤ max_per_post）
    4. 按比例裁剪/填充后输出

    Args:
        src_path: 长图路径
        out_dir: 输出根目录
        width: 输出宽度，默认 1080
        page_height: 每页高度，默认 2016
        max_per_post: 每条笔记最大图片数，默认 9
        aspect_ratio: 输出比例，如 "3:4"/"9:16"/"1:1"/"4:3"，None 表示保持原比例

    Returns:
        分组摘要字典
    """
    from PIL import Image

    src = Path(src_path)
    if not src.exists():
        raise FileNotFoundError(f"文件不存在: {src_path}")
    if not src.is_file():
        raise ValueError(f"不是文件: {src_path}")

    img = Image.open(src_path)
    w, h = img.size
    logger.info(f"原始尺寸: {w}x{h}")

    # 先缩放到目标宽度
    scale = width / w
    new_h = int(h * scale)
    img = img.resize((width, new_h), Image.LANCZOS)
    logger.info(f"缩放后尺寸: {width}x{new_h}")

    # 创建临时目录存放切割后的页面
    import tempfile
    temp_dir = Path(tempfile.mkdtemp(prefix="xhs-split-"))

    try:
        # 按固定高度切割
        pages = []
        y = 0
        page_num = 1
        while y < new_h:
            bottom = min(y + page_height, new_h)
            # 跳过高度不足 page_height 的 10% 的尾部碎片
            remaining = new_h - y
            if remaining < page_height * 0.1 and page_num > 1:
                # 把尾部碎片合并到上一页
                logger.info(f"尾部碎片 {remaining}px 合并到上一页")
                # 重新裁剪上一页，扩展到底部
                prev_page_path = pages[-1]
                prev_page = img.crop((0, y - page_height, width, new_h))
                prev_page.save(str(prev_page_path), "PNG", optimize=True)
                break

            page = img.crop((0, y, width, bottom))
            page_path = temp_dir / f"page-{page_num:02d}.png"
            page.save(str(page_path), "PNG", optimize=True)
            pages.append(page_path)
            y = bottom
            page_num += 1

        logger.info(f"切割为 {len(pages)} 页")

        # 用切割后的临时目录作为输入，调用分组逻辑（传入比例参数）
        summary = split_for_xhs(
            src_dir=str(temp_dir),
            out_dir=out_dir,
            groups=None,
            width=width,
            max_per_post=max_per_post,
            aspect_ratio=aspect_ratio,
        )
        return summary

    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir, ignore_errors=True)


def generate_summary(out_dir: str) -> dict:
    """
    为已存在的分组目录生成摘要信息

    用于：手动整理好分组后，生成 split_summary.json

    Args:
        out_dir: 包含 post-XX 子目录的根目录

    Returns:
        摘要字典
    """
    out_path = Path(out_dir)
    if not out_path.exists():
        raise FileNotFoundError(f"目录不存在: {out_dir}")

    posts = sorted(
        d.name for d in out_path.iterdir()
        if d.is_dir() and d.name.startswith("post-")
    )

    summary = {
        "total_images": 0,
        "total_posts": len(posts),
        "posts": [],
    }

    for post_name in posts:
        post_dir = out_path / post_name
        images = sorted(
            f.name for f in post_dir.iterdir()
            if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        )
        post_info = {
            "name": post_name,
            "images": len(images),
            "files": images,
        }
        summary["posts"].append(post_info)
        summary["total_images"] += len(images)

    # 保存摘要
    summary_path = out_path.parent / "split_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    logger.info(f"摘要已生成: {summary_path}")

    return summary


def validate_args(args: argparse.Namespace):
    """
    校验命令行参数

    Args:
        args: 解析后的参数对象

    Raises:
        ValueError: 参数不合法
    """
    if args.width <= 0:
        raise ValueError(f"宽度必须大于 0: {args.width}")
    if args.page_height <= 0:
        raise ValueError(f"页高必须大于 0: {args.page_height}")
    if args.max_per_post <= 0 or args.max_per_post > 9:
        raise ValueError(f"每条最大图片数应为 1-9: {args.max_per_post}")


def main():
    """
    脚本入口：解析命令行参数，执行拆分

    支持两种模式：
    1. 目录模式（默认）：--src 指向图片目录，按分组输出
    2. 长图模式（--long-image）：--src 指向单张长图，按页高切割后分组
    """
    parser = argparse.ArgumentParser(
        description="小红书图片拆分脚本：将章节截图或长图拆分为多条笔记",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 自动分组拆分目录
  python split_images.py --src xhs-output/images --out xhs-output/xhs-posts

  # 拆分单张长图
  python split_images.py --src full-content.png --out xhs-output/xhs-posts --long-image

  # 手动指定分组（页码从 1 开始）
  python split_images.py --src xhs-output/images --out xhs-output/xhs-posts --groups "1-5,6-10,11-16"

  # 生成已有目录的摘要
  python split_images.py --summary xhs-output/xhs-posts
        """,
    )

    parser.add_argument(
        "--src", type=str, help="输入源：图片目录路径 或 单张长图路径"
    )
    parser.add_argument(
        "--out", type=str, default="xhs-posts", help="输出目录（默认: xhs-posts）"
    )
    parser.add_argument(
        "--long-image", action="store_true", help="长图模式：将单张长图按页高切割"
    )
    parser.add_argument(
        "--groups", type=str, default=None,
        help='手动指定分组，格式: "1-5,6-10,11-16"（页码从 1 开始）'
    )
    parser.add_argument(
        "--width", type=int, default=DEFAULT_WIDTH,
        help=f"输出宽度（默认: {DEFAULT_WIDTH}px）"
    )
    parser.add_argument(
        "--page-height", type=int, default=DEFAULT_PAGE_HEIGHT,
        help=f"长图模式每页高度（默认: {DEFAULT_PAGE_HEIGHT}px）"
    )
    parser.add_argument(
        "--max-per-post", type=int, default=MAX_PER_POST,
        help=f"每条笔记最大图片数（默认: {MAX_PER_POST}）"
    )
    parser.add_argument(
        "--aspect-ratio", type=str, default=DEFAULT_ASPECT_RATIO,
        choices=list(ASPECT_RATIO_PRESETS.keys()) + ["none"],
        help=(
            f"输出图片比例（默认: {DEFAULT_ASPECT_RATIO}）\n"
            "  3:4  竖图，小红书最常用\n"
            "  9:16 手机全屏竖图\n"
            "  1:1  方图\n"
            "  4:3  横图\n"
            "  none 保持原比例，不裁剪"
        )
    )
    parser.add_argument(
        "--summary", type=str, default=None,
        help="为已有分组目录生成摘要（不执行拆分）"
    )
    parser.add_argument(
        "--debug", action="store_true", help="开启调试日志"
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # 模式 1：只生成摘要
    if args.summary:
        summary = generate_summary(args.summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    # 参数校验
    if not args.src:
        parser.error("必须提供 --src 参数（图片目录或长图路径）")

    validate_args(args)
    check_pillow()

    # 处理比例参数：none 表示不裁剪
    aspect_ratio = None if args.aspect_ratio == "none" else args.aspect_ratio
    if aspect_ratio:
        logger.info(f"输出比例: {aspect_ratio}")
    else:
        logger.info("输出比例: 保持原比例")

    try:
        if args.long_image:
            # 模式 2：长图拆分
            logger.info(f"长图模式: {args.src}")
            summary = split_long_image(
                src_path=args.src,
                out_dir=args.out,
                width=args.width,
                page_height=args.page_height,
                max_per_post=args.max_per_post,
                aspect_ratio=aspect_ratio,
            )
        else:
            # 模式 3：目录拆分
            logger.info(f"目录模式: {args.src}")

            # 解析手动分组
            groups = None
            if args.groups:
                files = get_image_files(args.src)
                groups = parse_groups(args.groups, len(files))
                logger.info(f"手动分组: {len(groups)} 条笔记")

            summary = split_for_xhs(
                src_dir=args.src,
                out_dir=args.out,
                groups=groups,
                width=args.width,
                max_per_post=args.max_per_post,
                aspect_ratio=aspect_ratio,
            )

        # 打印摘要
        print("\n拆分完成！")
        print(f"总图片数: {summary['total_images']}")
        print(f"笔记数: {summary['total_posts']}")
        for post in summary["posts"]:
            pages_info = post.get("pages", "N/A")
            print(f"  {post['name']}: {post['images']} 张图 (页 {pages_info})")
        print(f"\n输出目录: {args.out}")

    except FileNotFoundError as e:
        logger.error(f"文件未找到: {e}")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"参数错误: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"拆分失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
