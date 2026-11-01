import io

import cv2
import numpy as np
from PIL import Image, ImageCms

_srgb = None
_srgb_bytes = None


def srgb_profile():
    global _srgb
    if _srgb is None:
        _srgb = ImageCms.createProfile("sRGB")
    return _srgb


def srgb_bytes() -> bytes:
    global _srgb_bytes
    if _srgb_bytes is None:
        _srgb_bytes = ImageCms.ImageCmsProfile(srgb_profile()).tobytes()
    return _srgb_bytes


def profile_name(icc: bytes) -> str:
    if not icc:
        return "sin perfil"
    try:
        p = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        return ImageCms.getProfileDescription(p).strip() or "perfil sin nombre"
    except Exception:
        return "perfil ilegible"


def _looks_like_srgb(name: str) -> bool:
    n = name.lower()
    return "srgb" in n or "iec61966" in n


def to_srgb(bgr: np.ndarray, icc: bytes):

    name = profile_name(icc)
    if not icc or _looks_like_srgb(name):
        return bgr, name, False
    try:
        rgb = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        src = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        out = ImageCms.profileToProfile(rgb, src, srgb_profile(), outputMode="RGB")
        return cv2.cvtColor(np.array(out), cv2.COLOR_RGB2BGR), name, True
    except Exception:
        return bgr, name + " (no se pudo convertir)", False
