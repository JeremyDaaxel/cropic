import cv2
import numpy as np
from PIL import Image

SUPPORTED = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff")


def imread(path):
    data = np.fromfile(path, dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def read_meta(path):
    try:
        with Image.open(path) as im:
            return {"icc": im.info.get("icc_profile"), "dpi": im.info.get("dpi")}
    except Exception:
        return {"icc": None, "dpi": None}
