import cv2
import numpy as np

BG_TOL = 20
CONTENT_FRAC = 0.55
GAP_FRAC = 0.035


def _background_color(gray: np.ndarray) -> float:
    h, w = gray.shape
    borders = np.concatenate([
        gray[:6, :].ravel(), gray[-6:, :].ravel(),
        gray[:, :6].ravel(), gray[:, -6:].ravel(),
    ])
    hist = np.bincount(borders, minlength=256)
    hist = np.convolve(hist, np.ones(9) / 9, mode="same")
    return float(np.argmax(hist))


def _largest_run(mask: np.ndarray, gap: int) -> tuple:
    if not mask.any():
        return 0, len(mask)
    m = mask.astype(np.uint8)
    if gap > 0:
        k = np.ones(gap * 2 + 1, np.uint8)
        m = (np.convolve(m, k, mode="same") > 0).astype(np.uint8)
        m = (np.convolve(m, k, mode="same") == k.sum()).astype(np.uint8)
    best = (0, 0)
    start = None
    for i, v in enumerate(np.append(m, 0)):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if i - start > best[1] - best[0]:
                best = (start, i)
            start = None
    return best if best[1] > best[0] else (0, len(mask))


def _trim_flat_edges(gray: np.ndarray, bg: float, box: tuple) -> tuple:
    x0, y0, x1, y1 = box
    sub = gray[y0:y1, x0:x1].astype(np.int16)
    if sub.size == 0:
        return box
    far = np.abs(sub - bg) > BG_TOL
    rows, cols = far.mean(1), far.mean(0)
    while y1 - y0 > 20 and rows[0] < 0.30:
        y0 += 1; rows = rows[1:]
    while y1 - y0 > 20 and rows[-1] < 0.30:
        y1 -= 1; rows = rows[:-1]
    while x1 - x0 > 20 and cols[0] < 0.30:
        x0 += 1; cols = cols[1:]
    while x1 - x0 > 20 and cols[-1] < 0.30:
        x1 -= 1; cols = cols[:-1]
    return x0, y0, x1, y1


CHROME_BG_FRAC = 0.65
CHROME_FLATNESS = 9.0
CHROME_EDGE_JUMP = 26.0


def _is_chrome(bg, band, edge) -> bool:
    if band.size == 0 or edge.size == 0:
        return False
    band_i = band.astype(np.int16)

    if (np.abs(band_i - bg) <= BG_TOL).mean() < CHROME_BG_FRAC:
        return False

    axis = 1 if band.shape[0] <= band.shape[1] else 0
    if float(np.median(band_i, axis=axis).std()) > CHROME_FLATNESS:
        return False

    if abs(float(np.median(band_i)) - float(np.median(edge.astype(np.int16)))) < CHROME_EDGE_JUMP:
        return False
    return True


def detect_photo_region(bgr: np.ndarray) -> dict:
    h, w = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    bg = _background_color(gray)

    far = (np.abs(gray.astype(np.int16) - bg) > BG_TOL)
    row_content = far.mean(1) > CONTENT_FRAC
    y0, y1 = _largest_run(row_content, int(h * GAP_FRAC))

    band = far[y0:y1]
    col_content = band.mean(0) > CONTENT_FRAC if band.size else np.ones(w, bool)
    x0, x1 = _largest_run(col_content, int(w * GAP_FRAC))

    box = _trim_flat_edges(gray, bg, (x0, y0, x1, y1))
    x0, y0, x1, y1 = box

    if y0 > 0 and not _is_chrome(bg, gray[:y0], gray[y0:y0 + 3]):
        y0 = 0
    if y1 < h and not _is_chrome(bg, gray[y1:], gray[y1 - 3:y1]):
        y1 = h
    if x0 > 0 and not _is_chrome(bg, gray[y0:y1, :x0], gray[y0:y1, x0:x0 + 3]):
        x0 = 0
    if x1 < w and not _is_chrome(bg, gray[y0:y1, x1:], gray[y0:y1, x1 - 3:x1]):
        x1 = w

    if (x0 + (w - x1)) > w * 0.12:
        sides = []
        if x0 > 0:
            sides.append(far[y0:y1, :x0].mean())
        if x1 < w:
            sides.append(far[y0:y1, x1:].mean())
        if sides and max(sides) > 0.03:
            x0, x1 = 0, w

    area_frac = ((x1 - x0) * (y1 - y0)) / float(w * h)
    is_screenshot = area_frac < 0.93 and (x1 - x0) > 60 and (y1 - y0) > 60
    if not is_screenshot:
        return {"box": (0, 0, w, h), "confidence": 0.0, "is_screenshot": False, "bg": bg}

    removed = []
    if y0 > 4:
        removed.append(far[:y0].mean())
    if y1 < h - 4:
        removed.append(far[y1:].mean())
    if x0 > 4:
        removed.append(far[y0:y1, :x0].mean())
    if x1 < w - 4:
        removed.append(far[y0:y1, x1:].mean())
    cleanliness = 1.0 - float(np.mean(removed)) if removed else 0.5
    inside = far[y0:y1, x0:x1].mean()
    conf = max(0.0, min(1.0, 0.5 * cleanliness + 0.5 * inside))

    return {"box": (x0, y0, x1, y1), "confidence": conf, "is_screenshot": True, "bg": bg}


def crop(bgr: np.ndarray, box: tuple) -> np.ndarray:
    x0, y0, x1, y1 = [int(v) for v in box]
    return bgr[y0:y1, x0:x1]
