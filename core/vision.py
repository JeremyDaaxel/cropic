import os

import cv2
import numpy as np

_CASCADE_DIR = cv2.data.haarcascades
_cache = {}

from . import paths

_YUNET_PATH = paths.res("models", "face_detection_yunet_2023mar.onnx")
_yunet = None
_yunet_tried = False


def _get_yunet():
    global _yunet, _yunet_tried
    if not _yunet_tried:
        _yunet_tried = True
        try:
            if os.path.exists(_YUNET_PATH):
                _yunet = cv2.FaceDetectorYN.create(_YUNET_PATH, "", (320, 320),
                                                   score_threshold=0.6, nms_threshold=0.3)
        except Exception:
            _yunet = None
    return _yunet


def _detect_yunet(bgr):
    det = _get_yunet()
    if det is None:
        return None
    h, w = bgr.shape[:2]
    scale = min(1.0, 640.0 / max(h, w))
    img = cv2.resize(bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else bgr
    det.setInputSize((img.shape[1], img.shape[0]))
    ok, faces = det.detect(img)
    if not ok or faces is None:
        return []
    inv = 1.0 / scale
    out = []
    for f in faces:
        x, y, fw, fh = [float(v) * inv for v in f[:4]]
        pts = [(float(f[4 + 2 * i]) * inv, float(f[5 + 2 * i]) * inv) for i in range(5)]
        out.append({"box": (int(x), int(y), int(fw), int(fh)), "score": float(f[-1]),
                    "landmarks": pts})
    return out


def _cascade(name: str):
    if name not in _cache:
        path = os.path.join(_CASCADE_DIR, name)
        _cache[name] = cv2.CascadeClassifier(path) if os.path.exists(path) else None
    return _cache[name]


def _nms(boxes, thr=0.35):
    if not boxes:
        return []
    boxes = sorted(boxes, key=lambda b: b[2] * b[3], reverse=True)
    keep = []
    for b in boxes:
        bx, by, bw, bh = b
        dup = False
        for k in keep:
            kx, ky, kw, kh = k
            ix = max(0, min(bx + bw, kx + kw) - max(bx, kx))
            iy = max(0, min(by + bh, ky + kh) - max(by, ky))
            inter = ix * iy
            if inter and inter / float(bw * bh + kw * kh - inter) > thr:
                dup = True
                break
        if not dup:
            keep.append(b)
    return keep


def detect_faces(bgr: np.ndarray) -> list:

    faces = _detect_yunet(bgr)
    if faces:
        return sorted(faces, key=lambda f: -f["box"][2] * f["box"][3])
    if faces == []:
        return []
    return [{"box": b, "score": 0.5, "landmarks": None} for b in _detect_haar(bgr)]


def _detect_haar(bgr: np.ndarray) -> list:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    h, w = gray.shape
    scale = 1.0
    if max(h, w) > 900:
        scale = 900.0 / max(h, w)
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

    minsz = max(24, int(min(gray.shape) * 0.07))
    found = []
    for name, flip in (("haarcascade_frontalface_default.xml", False),
                       ("haarcascade_frontalface_alt2.xml", False),
                       ("haarcascade_profileface.xml", False),
                       ("haarcascade_profileface.xml", True)):
        cc = _cascade(name)
        if cc is None or cc.empty():
            continue
        img = cv2.flip(gray, 1) if flip else gray
        for (x, y, fw, fh) in cc.detectMultiScale(img, 1.08, 5, minSize=(minsz, minsz)):
            if flip:
                x = img.shape[1] - x - fw
            found.append((x, y, fw, fh))

    faces = _nms(found)
    inv = 1.0 / scale
    faces = [(int(x * inv), int(y * inv), int(fw * inv), int(fh * inv)) for x, y, fw, fh in faces]
    return sorted(faces, key=lambda b: b[2] * b[3], reverse=True)


def _box_of(face):
    return face["box"] if isinstance(face, dict) else face


def head_box(face) -> tuple:
    x, y, w, h = _box_of(face)
    hw = w * 1.30
    hh = h * 1.45
    hx = x + w / 2 - hw / 2
    hy = y - h * 0.30
    return hx, hy, hw, hh


def eye_line(face) -> float:
    if isinstance(face, dict) and face.get("landmarks"):
        (rx, ry), (lx, ly) = face["landmarks"][0], face["landmarks"][1]
        return (ry + ly) / 2.0
    x, y, w, h = _box_of(face)
    return y + h * 0.42


def face_center_x(face) -> float:
    if isinstance(face, dict) and face.get("landmarks"):
        nose_x = face["landmarks"][2][0]
        x, y, w, h = face["box"]
        return 0.5 * nose_x + 0.5 * (x + w / 2)
    x, y, w, h = _box_of(face)
    return x + w / 2


def gaze_direction(face) -> int:
    if not (isinstance(face, dict) and face.get("landmarks")):
        return 0
    x, y, w, h = face["box"]
    nose = face["landmarks"][2][0]
    rel = (nose - (x + w / 2)) / (w + 1e-6)
    if rel > 0.09:
        return 1
    if rel < -0.09:
        return -1
    return 0


def saliency_map(bgr: np.ndarray, size: int = 128) -> np.ndarray:

    small = cv2.resize(bgr, (size, size), interpolation=cv2.INTER_AREA)
    lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB).astype(np.float32)

    gray = lab[:, :, 0]
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    detail = cv2.GaussianBlur(np.abs(gx) + np.abs(gy), (0, 0), 3)

    mean = lab.reshape(-1, 3).mean(0)
    rarity = np.linalg.norm(lab - mean, axis=2)
    rarity = cv2.GaussianBlur(rarity, (0, 0), 3)

    sharp = np.abs(gray - cv2.GaussianBlur(gray, (0, 0), 2))
    sharp = cv2.GaussianBlur(sharp, (0, 0), 4)

    def norm(a):
        a = a - a.min()
        return a / (a.max() + 1e-6)

    sal = 0.45 * norm(detail) + 0.30 * norm(rarity) + 0.25 * norm(sharp)
    return norm(sal)
