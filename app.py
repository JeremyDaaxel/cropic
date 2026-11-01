import base64
import json
import os
import sys
import threading
import traceback

import cv2
import numpy as np
import webview

from core import color, export, meta, paths, presets, split, ui_strip, variants, vision
from core.imageio import SUPPORTED, imread, read_meta

BASE = paths.res_dir()
UI = paths.res("ui", "index.html")
ICON = paths.res("ui", "img", "cropic.ico")
_PICTURES = os.path.join(os.path.expanduser("~"), "Pictures")
DEFAULT_OUT = os.path.join(_PICTURES, "Cropic")
_OLD_OUT = os.path.join(_PICTURES, "CropIG")
if not os.path.isdir(DEFAULT_OUT) and os.path.isdir(_OLD_OUT):
    DEFAULT_OUT = _OLD_OUT
_APPDATA = os.environ.get("APPDATA") or os.path.expanduser("~")
PREFS = (os.environ.get("CROPIC_PREFS")
         or os.path.join(_APPDATA, "Cropic", "prefs.json"))
PREF_KEYS = {"preset", "fmt", "sound", "dark", "outDir", "pieces", "cutMode", "dpi", "sheet"}


def _b64(img, quality=82, max_side=1400):
    h, w = img.shape[:2]
    if max(h, w) > max_side:
        s = max_side / float(max(h, w))
        img = cv2.resize(img, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(buf).decode("ascii")


class Item:

    def __init__(self, path, img, meta=None):
        self.path = path
        self.name = os.path.basename(path)
        meta = meta or {"icc": None, "dpi": None}
        img, self.src_profile, self.converted = color.to_srgb(img, meta.get("icc"))
        self.src_dpi = meta.get("dpi")
        self.original = img
        det = ui_strip.detect_photo_region(img)
        self.box = list(det["box"])
        self.auto_box = list(det["box"])
        self.confidence = det["confidence"]
        self.is_screenshot = det["is_screenshot"]
        self._refresh()

    def _refresh(self):
        self.photo = ui_strip.crop(self.original, self.box)
        self.faces = vision.detect_faces(self.photo) if self.photo.size else []
        self.sal = vision.saliency_map(self.photo) if self.photo.size else None

    def set_box(self, box):
        h, w = self.original.shape[:2]
        x0, y0, x1, y1 = [int(v) for v in box]
        x0, x1 = max(0, min(x0, w - 2)), max(2, min(x1, w))
        y0, y1 = max(0, min(y0, h - 2)), max(2, min(y1, h))
        if x1 - x0 < 16 or y1 - y0 < 16:
            return False
        self.box = [x0, y0, x1, y1]
        self._refresh()
        return True

    def info(self, item_id):
        h, w = self.original.shape[:2]
        ph, pw = self.photo.shape[:2]
        return {
            "id": item_id,
            "name": self.name,
            "path": self.path,
            "size": [w, h],
            "photoSize": [pw, ph],
            "box": self.box,
            "autoBox": self.auto_box,
            "confidence": round(self.confidence, 2),
            "isScreenshot": self.is_screenshot,
            "faces": [{"box": list(f["box"]), "score": round(f["score"], 2)} for f in self.faces],
            "profile": self.src_profile,
            "converted": self.converted,
            "thumb": _b64(self.photo, 70, 320),
            "preview": _b64(self.photo, 84, 1100),
        }


class Api:
    def __init__(self):
        self.items = {}
        self.counter = 0
        self.lock = threading.Lock()
        self.prefs = self._read_prefs()
        self.out_dir = self.prefs.get("outDir") or DEFAULT_OUT

    @staticmethod
    def _read_prefs():
        viejo = os.path.join(_APPDATA, "CropIG", "prefs.json")
        if not os.path.exists(PREFS) and os.path.exists(viejo):
            try:
                os.makedirs(os.path.dirname(PREFS), exist_ok=True)
                with open(viejo, encoding="utf-8") as src, open(PREFS, "w", encoding="utf-8") as dst:
                    dst.write(src.read())
            except OSError:
                pass
        try:
            with open(PREFS, encoding="utf-8") as fh:
                data = json.load(fh)
            return {k: v for k, v in data.items() if k in PREF_KEYS}
        except (OSError, ValueError):
            return {}

    def presets(self):
        return [{"key": p.key, "label": p.label, "group": p.group, "ratio": round(p.ratio, 4),
                 "hint": p.hint, "isDoc": p.is_doc,
                 "mm": list(p.mm) if p.mm else None} for p in presets.PRESETS]

    def sheets(self):
        return [{"key": k, "label": v[2]} for k, v in presets.SHEETS.items()]

    def settings(self):
        return {"outDir": self.out_dir, "prefs": self.prefs}

    def load_prefs(self):
        return self.prefs

    def save_prefs(self, prefs):
        if not isinstance(prefs, dict):
            return False
        self.prefs.update({k: v for k, v in prefs.items() if k in PREF_KEYS})
        if "outDir" in self.prefs:
            self.out_dir = self.prefs["outDir"] or self.out_dir
        try:
            os.makedirs(os.path.dirname(PREFS), exist_ok=True)
            with open(PREFS, "w", encoding="utf-8") as fh:
                json.dump(self.prefs, fh, indent=1, ensure_ascii=False)
            return True
        except OSError:
            traceback.print_exc()
            return False

    def pick_files(self):
        types = ("Imagenes (*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.tif;*.tiff)", "Todos (*.*)")
        result = webview.windows[0].create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=True, file_types=types)
        return list(result or [])

    def pick_folder(self):
        result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
        if not result:
            return []
        folder = result[0]
        return [os.path.join(folder, f) for f in sorted(os.listdir(folder))
                if f.lower().endswith(SUPPORTED)]

    def choose_out_dir(self):
        result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
        if result:
            self.out_dir = result[0]
            self.save_prefs({"outDir": self.out_dir})
        return self.out_dir

    def expand(self, pattern):
        import glob
        if os.path.isdir(pattern):
            return [os.path.join(pattern, f) for f in sorted(os.listdir(pattern))
                    if f.lower().endswith(SUPPORTED)]
        return sorted(p for p in glob.glob(pattern) if p.lower().endswith(SUPPORTED))

    def add_paths(self, paths):
        added, errors = [], []
        for path in paths:
            try:
                if not os.path.isfile(path):
                    errors.append({"path": path, "error": "no existe"})
                    continue
                img = imread(path)
                if img is None:
                    errors.append({"path": path, "error": "formato no soportado"})
                    continue
                with self.lock:
                    self.counter += 1
                    key = f"img{self.counter}"
                    item = Item(path, img, read_meta(path))
                    self.items[key] = item
                added.append(item.info(key))
            except Exception as exc:
                traceback.print_exc()
                errors.append({"path": path, "error": str(exc)})
        return {"items": added, "errors": errors}

    def metadata(self, item_id):
        item = self.items.get(item_id)
        if not item:
            return {"nombre": "", "secciones": []}
        try:
            secciones = meta.read_all(item.path)
        except Exception as exc:
            traceback.print_exc()
            secciones = [{"titulo": "Error al leer el archivo",
                          "filas": [["Motivo", f"{type(exc).__name__}: {exc}"]]}]

        h, w = item.original.shape[:2]
        ph, pw = item.photo.shape[:2]
        detectado = [
            ("Es una captura", "si" if item.is_screenshot else None),
            ("Confianza del recorte", f"{item.confidence * 100:.0f}%" if item.is_screenshot else None),
            ("Interfaz recortada", f"{w}x{h} → {pw}x{ph} px" if item.is_screenshot else None),
            ("Region de la foto", "x %d-%d, y %d-%d" % (item.box[0], item.box[2],
                                                        item.box[1], item.box[3])),
            ("Rostros", str(len(item.faces)) if item.faces else "ninguno"),
        ]
        for i, f in enumerate(item.faces, 1):
            x, y, fw, fh = f["box"]
            detectado.append((f"  Rostro {i}",
                              f"{fw}x{fh} px en ({x}, {y}) · certeza {f['score'] * 100:.0f}%"))
        if item.converted:
            detectado.append(("Conversion de color", f"{item.src_profile} → sRGB"))
        secciones.append({"titulo": "Lo que ha detectado Cropic",
                          "filas": [[k, v] for k, v in detectado if v]})
        return {"nombre": item.name, "secciones": [s for s in secciones if s["filas"]]}

    def remove(self, item_id):
        self.items.pop(item_id, None)
        return True

    def clear(self):
        self.items.clear()
        return True

    def set_box(self, item_id, box):
        item = self.items.get(item_id)
        if not item or not item.set_box(box):
            return None
        return item.info(item_id)

    def reset_box(self, item_id):
        item = self.items.get(item_id)
        if not item:
            return None
        item.set_box(item.auto_box)
        return item.info(item_id)

    def use_full(self, item_id):
        item = self.items.get(item_id)
        if not item:
            return None
        h, w = item.original.shape[:2]
        item.set_box([0, 0, w, h])
        return item.info(item_id)

    def variants(self, item_id, preset_key):
        item = self.items.get(item_id)
        preset = presets.BY_KEY.get(preset_key)
        if not item or preset is None:
            return []
        vs = variants.generate(item.photo, preset, item.faces, item.sal)
        out = []
        for i, v in enumerate(vs):
            crop = item.photo[v.box[1]:v.box[3], v.box[0]:v.box[2]]
            out.append({"index": i, "name": v.name, "note": v.note, "box": list(v.box),
                        "score": round(v.score), "size": list(v.size),
                        "thumb": _b64(crop, 78, 520)})
        return out

    def cut_modes(self):
        return [{"key": k, "label": v[0]} for k, v in split.CUT_MODES.items()]

    def split_preview(self, item_id, preset_key, pieces=2, mode="cara", zoom=None,
                      vcenter=None):

        item = self.items.get(item_id)
        preset = presets.BY_KEY.get(preset_key)
        if not item or preset is None:
            return {"pieces": [], "error": "seleccion invalida"}
        boxes = split.split(item.photo, preset.ratio, int(pieces), item.faces, item.sal,
                            mode=mode, zoom=zoom, vcenter=vcenter)
        score, why = split.cut_quality(item.photo, boxes, item.faces)
        out = []
        for i, (x0, y0, x1, y1) in enumerate(boxes):
            crop = item.photo[y0:y1, x0:x1]
            out.append({"index": i, "box": [x0, y0, x1, y1], "size": [x1 - x0, y1 - y0],
                        "thumb": _b64(crop, 78, 460)})
        return {"pieces": out, "score": score, "why": why,
                "seam": boxes[0][2] if len(boxes) > 1 else None}

    def split_custom(self, item_id, preset_key, pieces, band):
        item = self.items.get(item_id)
        preset = presets.BY_KEY.get(preset_key)
        if not item or preset is None:
            return {"pieces": [], "error": "seleccion invalida"}
        h, w = item.photo.shape[:2]
        boxes = split.boxes_from_band(band, int(pieces), (w, h))
        score, why = split.cut_quality(item.photo, boxes, item.faces)
        out = []
        for i, (x0, y0, x1, y1) in enumerate(boxes):
            crop = item.photo[max(0, y0):y1, max(0, x0):x1]
            if crop.size == 0:
                return {"pieces": [], "error": "banda fuera de la foto"}
            out.append({"index": i, "box": [x0, y0, x1, y1], "size": [x1 - x0, y1 - y0],
                        "thumb": _b64(crop, 78, 460)})
        return {"pieces": out, "score": score, "why": why,
                "seam": boxes[0][2] if len(boxes) > 1 else None}

    def export_split(self, item_id, preset_key, boxes, fmt="jpg", long_side=2000, quality=95):
        item = self.items.get(item_id)
        preset = presets.BY_KEY.get(preset_key)
        if not item or preset is None:
            return {"ok": False, "error": "seleccion invalida"}
        stem = os.path.splitext(item.name)[0]
        paths = []
        try:
            first = export.render(item.photo, boxes[0], preset, long_side=long_side)
            size = (first.shape[1], first.shape[0])
            for i, box in enumerate(boxes, 1):
                img = export.render(item.photo, box, preset, long_side=long_side, size=size)
                path = self._unique(f"{stem}_carrusel_{i}de{len(boxes)}.{fmt}")
                export.save(img, path, quality)
                paths.append(path)
            return {"ok": True, "paths": paths, "dir": self.out_dir}
        except Exception as exc:
            traceback.print_exc()
            return {"ok": False, "error": str(exc), "paths": paths}

    def original_preview(self, item_id):
        item = self.items.get(item_id)
        return _b64(item.original, 82, 1100) if item else ""

    def preview_box(self, item_id, box, preset_key=None):
        item = self.items.get(item_id)
        if not item:
            return {}
        x0, y0, x1, y1 = [int(v) for v in box]
        x0, y0 = max(0, x0), max(0, y0)
        crop = item.photo[y0:y1, x0:x1]
        if crop.size == 0:
            return {}
        out = {"thumb": _b64(crop, 78, 520), "size": [x1 - x0, y1 - y0]}
        preset = presets.BY_KEY.get(preset_key)
        if preset is not None:
            out["score"] = round(variants.score_box((x0, y0, x1, y1), item.photo, item.sal,
                                                    item.faces, preset.ratio))
        return out

    def export(self, item_id, preset_key, box, fmt="jpg", dpi=300, long_side=2000, quality=95):
        item = self.items.get(item_id)
        preset = presets.BY_KEY.get(preset_key)
        if not item or preset is None:
            return {"ok": False, "error": "seleccion invalida"}
        try:
            img = export.render(item.photo, box, preset, dpi=dpi, long_side=long_side)
            stem = os.path.splitext(item.name)[0]
            path = self._unique(f"{stem}_{preset.key}.{fmt}")
            export.save(img, path, quality, dpi=dpi if preset.mm else None)
            stretch = export.upscale_factor(item.photo, box, preset, dpi)
            return {"ok": True, "path": path, "size": [img.shape[1], img.shape[0]],
                    "stretch": round(stretch, 2)}
        except Exception as exc:
            traceback.print_exc()
            return {"ok": False, "error": str(exc)}

    def export_batch(self, jobs, fmt="jpg", dpi=300, long_side=2000, quality=95):
        done, failed = [], []
        for job in jobs:
            r = self.export(job["itemId"], job["presetKey"], job["box"], fmt, dpi, long_side, quality)
            (done if r.get("ok") else failed).append(r)
        return {"ok": len(done), "failed": failed, "dir": self.out_dir}

    def export_sheet(self, item_id, preset_key, box, sheet="10x15", dpi=300, count=None,
                     guides=True, fmt="jpg"):
        item = self.items.get(item_id)
        preset = presets.BY_KEY.get(preset_key)
        if not item or preset is None or preset.mm is None:
            return {"ok": False, "error": "la plancha solo aplica a formatos de documento"}
        try:
            photo = export.render(item.photo, box, preset, dpi=dpi)
            sheet_img, meta = export.contact_sheet(photo, preset, sheet, dpi, guides=guides,
                                                   count=count)
            stem = os.path.splitext(item.name)[0]
            path = self._unique(f"{stem}_plancha_{preset.key}_{sheet}.{fmt}")
            export.save(sheet_img, path, 96, dpi=dpi)
            return {"ok": True, "path": path, "meta": meta, "preview": _b64(sheet_img, 80, 900)}
        except Exception as exc:
            traceback.print_exc()
            return {"ok": False, "error": str(exc)}

    def open_out_dir(self):
        os.makedirs(self.out_dir, exist_ok=True)
        os.startfile(self.out_dir) if os.name == "nt" else None
        return self.out_dir

    def _unique(self, filename):
        os.makedirs(self.out_dir, exist_ok=True)
        path = os.path.join(self.out_dir, filename)
        stem, ext = os.path.splitext(path)
        n = 2
        while os.path.exists(path):
            path = f"{stem}_{n}{ext}"
            n += 1
        return path


def _apply_window_icon(title="Cropic"):

    if os.name != "nt" or not os.path.exists(ICON):
        return
    try:
        import ctypes
        from ctypes import wintypes

        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        user32.FindWindowW.restype = wintypes.HWND
        hwnd = user32.FindWindowW(None, title)
        if not hwnd:
            return
        IMAGE_ICON, LR_LOADFROMFILE, LR_DEFAULTSIZE = 1, 0x10, 0x40
        WM_SETICON, ICON_SMALL, ICON_BIG = 0x80, 0, 1
        for which, size in ((ICON_SMALL, 16), (ICON_BIG, 32)):
            handle = user32.LoadImageW(None, ICON, IMAGE_ICON, size, size,
                                       LR_LOADFROMFILE | LR_DEFAULTSIZE)
            if handle:
                user32.SendMessageW(hwnd, WM_SETICON, which, handle)
        del kernel32
    except Exception:
        traceback.print_exc()


def main():
    api = Api()
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Axel.Cropic")
        except Exception:
            pass
    window = webview.create_window(
        "Cropic", UI, js_api=api, width=1280, height=820, min_size=(980, 640),
        background_color="#FFF8E0", text_select=False,
    )
    window.events.shown += lambda: _apply_window_icon("Cropic")
    webview.start(debug="--debug" in sys.argv)
    return window


if __name__ == "__main__":
    main()
