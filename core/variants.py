from dataclasses import dataclass, field

import cv2
import numpy as np

from . import vision


@dataclass
class Variant:
    name: str
    box: tuple
    score: float = 0.0
    note: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def size(self):
        x0, y0, x1, y1 = self.box
        return x1 - x0, y1 - y0


def _fit(img_w, img_h, cx, cy, height, ratio):
    h = min(height, img_h)
    w = h * ratio
    if w > img_w:
        w = img_w
        h = w / ratio
    x0 = cx - w / 2
    y0 = cy - h / 2
    x0 = max(0, min(x0, img_w - w))
    y0 = max(0, min(y0, img_h - h))
    return (int(round(x0)), int(round(y0)), int(round(x0 + w)), int(round(y0 + h)))


def _place_eyes(img_w, img_h, face_cx, eye_y, height, ratio, eye_frac):
    h = min(height, img_h)
    w = h * ratio
    if w > img_w:
        w = img_w
        h = w / ratio
    y0 = eye_y - h * eye_frac
    x0 = face_cx - w / 2
    x0 = max(0, min(x0, img_w - w))
    y0 = max(0, min(y0, img_h - h))
    return (int(round(x0)), int(round(y0)), int(round(x0 + w)), int(round(y0 + h)))


def _iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    if not inter:
        return 0.0
    aa = (a[2] - a[0]) * (a[3] - a[1])
    bb = (b[2] - b[0]) * (b[3] - b[1])
    return inter / float(aa + bb - inter)


def score_box(box, img, sal, faces, ratio):
    H, W = img.shape[:2]
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    if bw < 8 or bh < 8:
        return 0.0

    sh, sw = sal.shape
    sx0, sy0 = int(x0 / W * sw), int(y0 / H * sh)
    sx1, sy1 = max(sx0 + 1, int(x1 / W * sw)), max(sy0 + 1, int(y1 / H * sh))
    captured = sal[sy0:sy1, sx0:sx1].sum() / (sal.sum() + 1e-6)
    density = sal[sy0:sy1, sx0:sx1].mean() / (sal.mean() + 1e-6)

    s = 45 * captured + 25 * min(density, 1.6) / 1.6

    if faces:
        fx, fy, fw, fh = vision._box_of(faces[0])
        fbox = (fx, fy, fx + fw, fy + fh)
        cover_x = max(0, min(fbox[2], x1) - max(fbox[0], x0)) / float(fw)
        cover_y = max(0, min(fbox[3], y1) - max(fbox[1], y0)) / float(fh)
        cover = max(0.0, cover_x) * max(0.0, cover_y)
        if cover < 0.999:
            s -= 45 * (1 - cover)
        else:
            s += 15
            hx, hy, hw_, hh_ = vision.head_box(faces[0])
            headroom = (hy - y0) / float(bh)
            s += 8 * max(0.0, 1 - abs(headroom - 0.10) / 0.25)
            eye_rel = (vision.eye_line(faces[0]) - y0) / float(bh)
            s += 7 * max(0.0, 1 - abs(eye_rel - 0.36) / 0.30)

        for other in faces[1:]:
            ox, oy, ow, oh = vision._box_of(other)
            ix = max(0, min(ox + ow, x1) - max(ox, x0)) / float(ow)
            iy = max(0, min(oy + oh, y1) - max(oy, y0)) / float(oh)
            visible = max(0.0, ix) * max(0.0, iy)
            if 0.12 < visible < 0.95:
                s -= 14 * (1 - visible)

    used = (bw * bh) / float(W * H)
    s += 5 * min(used, 0.8) / 0.8
    if min(bw, bh) < 300:
        s -= 10
    return float(max(0.0, min(100.0, s)))


def _salient_window(img, sal, ratio, height):
    H, W = img.shape[:2]
    h = min(height, H)
    w = min(h * ratio, W)
    h = w / ratio
    sh, sw = sal.shape
    integral = cv2.integral(sal.astype(np.float32))
    best, best_v = None, -1
    bw_s, bh_s = max(1, int(w / W * sw)), max(1, int(h / H * sh))
    for sy in range(0, sh - bh_s + 1, max(1, bh_s // 12)):
        for sx in range(0, sw - bw_s + 1, max(1, bw_s // 12)):
            v = (integral[sy + bh_s, sx + bw_s] - integral[sy, sx + bw_s]
                 - integral[sy + bh_s, sx] + integral[sy, sx])
            if v > best_v:
                best_v, best = v, (sx, sy)
    sx, sy = best
    cx = (sx + bw_s / 2) / sw * W
    cy = (sy + bh_s / 2) / sh * H
    return _fit(W, H, cx, cy, h, ratio)


def generate(img, preset, faces=None, sal=None, max_variants=6):
    H, W = img.shape[:2]
    ratio = preset.ratio
    faces = vision.detect_faces(img) if faces is None else faces
    sal = vision.saliency_map(img) if sal is None else sal

    out = []
    if preset.is_doc:
        out = _doc_variants(W, H, ratio, faces)
    else:
        out = _free_variants(img, sal, ratio, faces, W, H)

    uniq = []
    for v in out:
        if all(_iou(v.box, u.box) < 0.94 for u in uniq):
            uniq.append(v)

    for v in uniq:
        v.score = score_box(v.box, img, sal, faces, ratio)
    uniq.sort(key=lambda v: -v.score)
    good = [v for v in uniq if v.score >= 15]
    return (good or uniq[:1])[:max_variants]


def _free_variants(img, sal, ratio, faces, W, H):
    out = []
    full_h = min(H, W / ratio)
    if faces:
        f = faces[0]
        cx = vision.face_center_x(f)
        eye = vision.eye_line(f)
        _, _, _, head_h = vision.head_box(f)

        out.append(Variant("Primer plano", _place_eyes(W, H, cx, eye, head_h * 2.1, ratio, 0.40),
                           note="Cara grande, maximo impacto"))
        out.append(Variant("Retrato", _place_eyes(W, H, cx, eye, head_h * 3.3, ratio, 0.36),
                           note="Ojos en el tercio superior"))
        out.append(Variant("Medio cuerpo", _place_eyes(W, H, cx, eye, head_h * 5.2, ratio, 0.26),
                           note="Incluye torso y algo de escena"))
        out.append(Variant("Escena completa", _place_eyes(W, H, cx, eye, full_h, ratio, 0.30),
                           note="Aprovecha toda la foto"))

        gaze = vision.gaze_direction(f)
        if gaze == 0:
            gaze = 1 if cx < W / 2 else -1
        h3 = min(head_h * 4.0, H)
        w3 = min(h3 * ratio, W)
        out.append(Variant("Regla de tercios", _place_eyes(W, H, cx - w3 * 0.17 * gaze, eye, h3,
                                                           ratio, 0.34),
                           note="Deja aire hacia donde mira"))
    else:
        for k, (mult, name) in enumerate([(1.0, "Escena completa"), (0.72, "Acercamiento"),
                                          (0.5, "Detalle")]):
            out.append(Variant(name, _salient_window(img, sal, ratio, full_h * mult),
                               note="Centrado en la zona con mas detalle"))

    out.append(Variant("Zona de mas interes", _salient_window(img, sal, ratio, full_h * 0.8),
                       note="Elegido por el mapa de atencion"))
    out.append(Variant("Centrado", _fit(W, H, W / 2, H / 2, full_h, ratio),
                       note="Recorte central sin criterio, para comparar"))
    return out


def _doc_variants(W, H, ratio, faces):

    if not faces:
        full_h = min(H, W / ratio)
        return [Variant("Centrado (sin rostro detectado)", _fit(W, H, W / 2, H / 2, full_h, ratio),
                        note="No se detecto una cara: ajusta el encuadre a mano")]
    f = faces[0]
    cx = vision.face_center_x(f)
    eye = vision.eye_line(f)
    _, _, _, head_h = vision.head_box(f)

    out = []
    for head_frac, eye_frac, name, note in [
        (0.75, 0.42, "Norma carnet", "Cabeza al 75% del alto, ojos sobre la mitad"),
        (0.70, 0.44, "Un poco mas de aire", "Cabeza al 70%: valido y mas comodo"),
        (0.80, 0.40, "Cabeza grande", "Cabeza al 80%, limite superior de la norma"),
    ]:
        crop_h = head_h / head_frac
        out.append(Variant(name, _place_eyes(W, H, cx, eye, crop_h, ratio, eye_frac),
                           note=note, meta={"head_frac": head_frac}))
    return out
