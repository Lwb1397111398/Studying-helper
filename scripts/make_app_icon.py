"""把 学习助手的图标.png 转成 packaging/app.ico（多尺寸）与预览图。

用法（仓库根目录）：
    python scripts/make_app_icon.py [源图片路径]

源图是白底 + 圆角方形贴纸画面。脚本会：
1. 自动裁掉外围白边，只保留圆角方形画面；
2. 按圆角遮罩把四角设为透明，避免任务栏出现白色直角块；
3. 大尺寸用完整画面，小尺寸（≤32px）改用中心指南针特写，否则会糊成一片纸色；
4. 输出 16/24/32/48/64/128/256 多尺寸 .ico 与 256px 预览 png。
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = ROOT / "学习助手的图标.png"
OUT_ICO = ROOT / "packaging" / "app.ico"
OUT_PREVIEW = ROOT / "packaging" / "app_preview.png"
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]
# 白边判定阈值：像素三通道都 >= 该值视为背景白
WHITE_THRESHOLD = 248
# 圆角半径占边长比例，贴近源图的圆角方形
CORNER_RATIO = 0.21
# ≤ 该尺寸时用中心特写而不是全图
DETAIL_MAX_SIZE = 32
# 特写窗口边长占画面比例
DETAIL_CROP_RATIO = 0.46


def find_art_box(img: Image.Image) -> tuple[int, int, int, int]:
    """找到非白背景的画面外框。"""
    gray = img.convert("L")
    # 低于阈值的像素置 255，其余 0，再用 getbbox 求外框
    mask = gray.point(lambda v: 255 if v < WHITE_THRESHOLD else 0)
    box = mask.getbbox()
    if box is None:
        return (0, 0, img.width, img.height)
    return box


def to_square(box: tuple[int, int, int, int], w: int, h: int) -> tuple[int, int, int, int]:
    """把外框扩成正方形并夹在原图范围内。"""
    left, top, right, bottom = box
    cx = (left + right) / 2
    cy = (top + bottom) / 2
    side = max(right - left, bottom - top)
    side = min(side, w, h)
    half = side / 2
    left = int(round(cx - half))
    top = int(round(cy - half))
    left = max(0, min(left, w - side))
    top = max(0, min(top, h - side))
    return (left, top, int(left + side), int(top + side))


def rounded_mask(size: int, radius_ratio: float = CORNER_RATIO) -> Image.Image:
    """生成抗锯齿圆角遮罩。"""
    scale = 4
    big = size * scale
    mask = Image.new("L", (big, big), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle(
        (0, 0, big - 1, big - 1),
        radius=int(big * radius_ratio),
        fill=255,
    )
    mask = mask.resize((size, size), Image.LANCZOS)
    return mask.filter(ImageFilter.GaussianBlur(0.3))


def find_focus_center(art: Image.Image) -> tuple[float, float]:
    """找画面中央的橙色主体（指南针气泡）中心，用作小尺寸特写焦点。

    在 128px 缩略图上检测，只看中央区域，避开四角的橙色贴纸。
    找不到时退回几何中心。
    """
    thumb = art.convert("RGB").resize((128, 128), Image.BILINEAR)
    px = thumb.load()
    lo, hi = int(128 * 0.22), int(128 * 0.78)
    xs, ys = [], []
    for y in range(lo, hi):
        for x in range(lo, hi):
            r, g, b = px[x, y]
            if r > 200 and 90 < g < 160 and b < 130:
                xs.append(x)
                ys.append(y)
    if not xs:
        return (0.5, 0.5)
    cx = (min(xs) + max(xs)) / 2 / 128
    cy = (min(ys) + max(ys)) / 2 / 128
    return (cx, cy)


def detail_crop(art: Image.Image, focus: tuple[float, float]) -> Image.Image:
    """围绕焦点裁一个正方形特写窗口，供小尺寸使用。"""
    side = int(min(art.width, art.height) * DETAIL_CROP_RATIO)
    cx = int(art.width * focus[0])
    cy = int(art.height * focus[1])
    left = max(0, min(cx - side // 2, art.width - side))
    top = max(0, min(cy - side // 2, art.height - side))
    return art.crop((left, top, left + side, top + side))


def build(src_path: Path) -> None:
    src = Image.open(src_path).convert("RGB")
    box = to_square(find_art_box(src), src.width, src.height)
    art = src.crop(box)

    # 大尺寸母版：完整画面；小尺寸母版：中心指南针特写
    master = art.resize((1024, 1024), Image.LANCZOS).convert("RGBA")
    focus = find_focus_center(art)
    detail = detail_crop(art, focus).resize((512, 512), Image.LANCZOS).convert("RGBA")

    frames = []
    for size in ICO_SIZES:
        base = detail if size <= DETAIL_MAX_SIZE else master
        frame = base.resize((size, size), Image.LANCZOS)
        frame.putalpha(rounded_mask(size))
        frames.append(frame)

    preview = master.copy()
    preview.putalpha(rounded_mask(1024))
    preview = preview.resize((256, 256), Image.LANCZOS)
    preview.putalpha(rounded_mask(256))

    OUT_ICO.parent.mkdir(parents=True, exist_ok=True)
    # ICO 容器由最大帧携带完整 sizes 列表；Pillow 会为每个尺寸重采样，
    # 因此手动逐帧写入以保留小尺寸特写。
    frames[-1].save(
        OUT_ICO,
        format="ICO",
        sizes=[(s, s) for s in ICO_SIZES],
        append_images=frames[:-1],
    )
    preview.save(OUT_PREVIEW, format="PNG")

    print(f"源图: {src_path} {src.size}")
    print(f"裁剪区域: {box}")
    print(f"小尺寸特写焦点: {focus[0]:.3f}, {focus[1]:.3f}")
    print(f"已生成: {OUT_ICO} (尺寸 {ICO_SIZES}，≤{DETAIL_MAX_SIZE}px 用特写)")
    print(f"预览图: {OUT_PREVIEW}")


if __name__ == "__main__":
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SRC
    if not source.is_file():
        raise SystemExit(f"找不到源图片: {source}")
    build(source)
