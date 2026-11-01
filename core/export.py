import os

import cv2
import numpy as np
from PIL import Image

from . import color
from .presets import SHEETS


def render(img, box, preset, dpi=300, long_side=2000, allow_upscale=None, size=None):

    x0, y0, x1, y1 = [int(v) for v in box]
    crop = img[y0:y1, x0:x1]
    if crop.size == 0:
        return crop

    if size is not None:
        if (crop.shape[1], crop.shape[0]) == tuple(size):
            return crop
        interp = cv2.INTER_AREA if size[0] < crop.shape[1] else cv2.INTER_CUBIC
        return cv2.resize(crop, tuple(size), interpolation=interp)

    if allow_upscale is None:
        allow_upscale = preset.mm is not None

    target = preset.pixels(dpi)
    if target is None:
        w = long_side if preset.ratio >= 1 else round(long_side * preset.ratio)
        h = round(w / preset.ratio)
        target = (w, h)
        if not allow_upscale and target[0] > crop.shape[1]:
            target = (crop.shape[1], max(1, round(crop.shape[1] / preset.ratio)))

    if target == (crop.shape[1], crop.shape[0]):
        return crop
    interp = cv2.INTER_AREA if target[0] < crop.shape[1] else cv2.INTER_CUBIC
    return cv2.resize(crop, target, interpolation=interp)


def upscale_factor(img, box, preset, dpi=300):
    target = preset.pixels(dpi)
    if target is None:
        return 1.0
    w = max(1, int(box[2]) - int(box[0]))
    return max(1.0, target[0] / float(w))


def save(img, path, quality=95, dpi=None):
    ext = os.path.splitext(path)[1].lower() or ".jpg"
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    opts = {"icc_profile": color.srgb_bytes(), "dpi": (int(dpi or 72), int(dpi or 72))}

    if ext in (".jpg", ".jpeg"):
        opts.update(quality=int(quality), subsampling=0, optimize=True, progressive=True)
    elif ext == ".png":
        opts.update(compress_level=6)
    elif ext == ".webp":
        opts.update(quality=int(quality), method=5)
    elif ext in (".tif", ".tiff"):
        opts.update(compression="tiff_lzw")

    pil.save(path, **opts)
    return path


def contact_sheet(photo, preset, sheet="10x15", dpi=300, gap_mm=2.0, margin_mm=4.0,
                  guides=True, count=None):
    if preset.mm is None:
        raise ValueError("La plancha solo aplica a formatos de documento")
    sw_mm, sh_mm, _ = SHEETS[sheet]
    px = lambda mm: int(round(mm / 25.4 * dpi))

    W, H = px(sw_mm), px(sh_mm)
    pw, ph = px(preset.mm[0]), px(preset.mm[1])
    gap, margin = px(gap_mm), px(margin_mm)

    cols = max(1, (W - 2 * margin + gap) // (pw + gap))
    rows = max(1, (H - 2 * margin + gap) // (ph + gap))
    total = int(cols * rows) if count is None else min(int(count), int(cols * rows))

    sheet_img = np.full((H, W, 3), 255, np.uint8)
    cell = cv2.resize(photo, (pw, ph), interpolation=cv2.INTER_AREA
                      if pw < photo.shape[1] else cv2.INTER_CUBIC)

    grid_w = cols * pw + (cols - 1) * gap
    grid_h = rows * ph + (rows - 1) * gap
    ox = (W - grid_w) // 2
    oy = (H - grid_h) // 2

    placed = 0
    for r in range(int(rows)):
        for c in range(int(cols)):
            if placed >= total:
                break
            x = ox + c * (pw + gap)
            y = oy + r * (ph + gap)
            sheet_img[y:y + ph, x:x + pw] = cell
            if guides:
                cv2.rectangle(sheet_img, (x - 1, y - 1), (x + pw, y + ph), (190, 190, 190), 1)
            placed += 1

    return sheet_img, {"cols": int(cols), "rows": int(rows), "count": placed,
                       "size_px": (W, H), "dpi": dpi}
