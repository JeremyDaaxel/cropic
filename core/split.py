import numpy as np

from . import vision

CUT_MODES = {
    "cara": ("Por la mitad de la cara", 0.50),
    "ojos": ("Por los ojos", 0.50),
    "borde": ("Por el borde de la cara", 0.05),
    "centro": ("Por el centro de la foto", None),
}


def cut_anchor(img, faces, mode="cara"):
    H, W = img.shape[:2]
    if mode == "centro" or not faces:
        return W / 2.0
    f = faces[0]
    x, y, fw, fh = vision._box_of(f)
    if mode == "ojos" and isinstance(f, dict) and f.get("landmarks"):
        (rx, _), (lx, _) = f["landmarks"][0], f["landmarks"][1]
        return (rx + lx) / 2.0
    frac = CUT_MODES.get(mode, CUT_MODES["cara"])[1]
    return x + fw * frac


MIN_ZOOM = 0.5


def split(img, ratio, pieces=2, faces=None, sal=None, mode="cara", zoom=None, vcenter=None):

    H, W = img.shape[:2]
    faces = vision.detect_faces(img) if faces is None else faces
    anchor = cut_anchor(img, faces, mode)

    pw_max = min(H / max(ratio, 1e-6), W / pieces) * ratio

    if zoom is None:
        pw = 0.0
        for k in range(1, max(2, pieces)):
            cand = min(anchor / k, (W - anchor) / (pieces - k)) if pieces > k else pw_max
            pw = max(pw, cand)
        pw = max(min(pw, pw_max), pw_max * MIN_ZOOM)
    else:
        pw = pw_max * max(MIN_ZOOM, min(1.0, zoom))

    h = pw / ratio
    if h > H:
        h = H
        pw = h * ratio
    total = pw * pieces

    best_x0, best_err = max(0.0, min(anchor - pw, W - total)), None
    for k in range(1, pieces) if pieces > 1 else [0.5]:
        x0 = anchor - k * pw
        x0c = max(0.0, min(x0, W - total))
        err = abs(x0c - x0)
        if best_err is None or err < best_err:
            best_x0, best_err = x0c, err

    if vcenter is None:
        if faces:
            eye = vision.eye_line(faces[0])
            cy = eye + h * 0.14
        elif sal is not None:
            rows = sal.mean(1)
            cy = (float(np.argmax(np.convolve(rows, np.ones(9) / 9, mode="same"))) / len(rows)) * H
        else:
            cy = H / 2
    else:
        cy = vcenter * H
    y0 = max(0.0, min(cy - h / 2, H - h))

    return _lay_out(best_x0, y0, pw, h, pieces, W, H)


def _lay_out(x0, y0, pw, h, pieces, W, H):

    pwi = max(1, int(round(pw)))
    hi = max(1, int(round(h)))
    if pwi * pieces > W:
        pwi = W // pieces
        hi = min(hi, H)
    x = int(round(max(0, min(x0, W - pwi * pieces))))
    y = int(round(max(0, min(y0, H - hi))))
    return [(x + i * pwi, y, x + (i + 1) * pwi, y + hi) for i in range(pieces)]


def boxes_from_band(band, pieces, size=None):

    x0, y0, x1, y1 = [float(v) for v in band]
    if size:
        W, H = float(size[0]), float(size[1])
        w, h = min(x1 - x0, W), min(y1 - y0, H)
        x0 = max(0.0, min(x0, W - w))
        y0 = max(0.0, min(y0, H - h))
        x1, y1 = x0 + w, y0 + h
    n = max(1, int(pieces))
    return _lay_out(x0, y0, (x1 - x0) / n, y1 - y0, n,
                    int(size[0]) if size else int(round(x1)),
                    int(size[1]) if size else int(round(y1)))


def cut_quality(img, boxes, faces):
    if len(boxes) < 2 or not faces:
        return 0, "sin cara detectada: el corte va por el centro"
    x, y, fw, fh = vision._box_of(faces[0])
    seam = boxes[0][2]
    if x < seam < x + fw:
        rel = (seam - x) / fw
        return int(100 - abs(rel - 0.5) * 120), f"la union parte la cara al {rel * 100:.0f}%"
    dist = min(abs(seam - x), abs(seam - (x + fw))) / max(fw, 1)
    return max(0, int(60 - dist * 60)), "la union pasa cerca de la cara, pero no por ella"
