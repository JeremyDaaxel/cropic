import datetime
import os

from PIL import ExifTags, Image, ImageCms

Image.MAX_IMAGE_PIXELS = None

_TAGS = ExifTags.TAGS
_GPS = ExifTags.GPSTAGS

_ENUMS = {
    "Orientation": {1: "normal", 2: "espejo horizontal", 3: "girada 180",
                    4: "espejo vertical", 5: "espejo + 90 antihorario",
                    6: "girada 90 horario", 7: "espejo + 90 horario",
                    8: "girada 90 antihorario"},
    "ResolutionUnit": {1: "sin unidad", 2: "pulgadas", 3: "centimetros"},
    "ColorSpace": {1: "sRGB", 65535: "sin calibrar"},
    "ExposureProgram": {0: "sin definir", 1: "manual", 2: "automatico",
                        3: "prioridad a la apertura", 4: "prioridad a la velocidad",
                        5: "creativo", 6: "accion", 7: "retrato", 8: "paisaje"},
    "MeteringMode": {0: "desconocido", 1: "media", 2: "media ponderada al centro",
                     3: "puntual", 4: "multipuntual", 5: "matricial", 6: "parcial"},
    "Flash": {0: "no disparo", 1: "disparo", 5: "disparo, sin retorno",
              7: "disparo, con retorno", 9: "forzado", 16: "apagado", 24: "automatico",
              25: "automatico, disparo"},
    "WhiteBalance": {0: "automatico", 1: "manual"},
    "SceneCaptureType": {0: "estandar", 1: "paisaje", 2: "retrato", 3: "nocturna"},
}


def _human(value, max_len=220):
    if isinstance(value, bytes):
        txt = value.decode("utf-8", "replace").strip("\x00").strip()
        return txt if txt else f"<{len(value)} bytes>"
    if isinstance(value, tuple) and len(value) == 2 and all(isinstance(v, int) for v in value):
        return f"{value[0]}/{value[1]}"
    txt = str(value)
    return txt if len(txt) <= max_len else txt[:max_len] + "..."


def _grados(coord, ref):
    try:
        d, m, s = [float(x) for x in coord]
    except (TypeError, ValueError):
        return None
    dec = d + m / 60 + s / 3600
    if str(ref).upper() in ("S", "W"):
        dec = -dec
    return dec, f"{int(d)}° {int(m)}' {s:.2f}\" {ref}"


def _seccion(titulo, filas):
    return {"titulo": titulo, "filas": [[k, v] for k, v in filas if v not in (None, "")]}


def _tamano(n):
    for unidad in ("B", "KB", "MB", "GB"):
        if n < 1024 or unidad == "GB":
            return f"{n:.0f} {unidad}" if unidad == "B" else f"{n:.1f} {unidad}"
        n /= 1024.0


def read_all(path):

    try:
        return _read_all(path)
    except Exception as exc:
        return [{"titulo": "Error al leer los datos",
                 "filas": [["Motivo", f"{type(exc).__name__}: {exc}"]]}]


def _read_all(path):
    secciones = []

    try:
        st = os.stat(path)
        fecha = lambda t: datetime.datetime.fromtimestamp(t).strftime("%d/%m/%Y %H:%M:%S")
        secciones.append(_seccion("Archivo", [
            ("Nombre", os.path.basename(path)),
            ("Carpeta", os.path.dirname(path)),
            ("Tamano", f"{_tamano(st.st_size)} ({st.st_size:,} bytes)".replace(",", " ")),
            ("Modificado", fecha(st.st_mtime)),
            ("Creado", fecha(st.st_ctime)),
        ]))
    except OSError:
        pass

    try:
        im = Image.open(path)
    except Exception as exc:
        secciones.append(_seccion("Error", [("No se pudo leer", str(exc))]))
        return secciones

    with im:
        w, h = im.size
        mp = w * h / 1e6
        filas = [
            ("Formato", f"{im.format} — {im.format_description}" if im.format else None),
            ("Dimensiones", f"{w} x {h} px  ({mp:.1f} megapixeles)"),
            ("Proporcion", _proporcion(w, h)),
            ("Modo de color", f"{im.mode} ({', '.join(im.getbands())})"),
            ("Animada", "si, %d fotogramas" % getattr(im, "n_frames", 1)
             if getattr(im, "n_frames", 1) > 1 else None),
        ]
        dpi = im.info.get("dpi")
        if dpi:
            try:
                dx, dy = float(dpi[0]), float(dpi[1])
                if dx > 0 and dy > 0:
                    filas.append(("Resolucion", f"{dx:g} x {dy:g} ppp  →  impresa "
                                                f"{w / dx * 25.4:.0f} x {h / dy * 25.4:.0f} mm"))
            except (TypeError, ValueError, ZeroDivisionError):
                filas.append(("Resolucion", _human(dpi)))
        secciones.append(_seccion("Imagen", filas))

        icc = im.info.get("icc_profile")
        filas = []
        if icc:
            try:
                import io
                prof = ImageCms.ImageCmsProfile(io.BytesIO(icc))
                filas += [
                    ("Perfil", ImageCms.getProfileDescription(prof).strip()),
                    ("Fabricante", ImageCms.getProfileManufacturer(prof).strip() or None),
                    ("Copyright", ImageCms.getProfileCopyright(prof).strip() or None),
                    ("Espacio de conexion", str(ImageCms.getProfileInfo(prof)).strip()[:120] or None),
                    ("Tamano del perfil", _tamano(len(icc))),
                ]
            except Exception:
                filas.append(("Perfil", f"presente, {_tamano(len(icc))} (ilegible)"))
        else:
            filas.append(("Perfil", "ninguno"))
        secciones.append(_seccion("Color", filas))

        try:
            exif = im.getexif()
        except Exception:
            exif = None

        if exif:
            base = [(_TAGS.get(k, f"Etiqueta {k}"), _valor(_TAGS.get(k, ""), v))
                    for k, v in exif.items()]
            secciones.append(_seccion("Camara y captura (EXIF)", sorted(base)))

            for ifd, titulo in ((ExifTags.IFD.Exif, "Detalles de la toma"),
                                (ExifTags.IFD.Interop, "Interoperabilidad")):
                try:
                    datos = exif.get_ifd(ifd)
                except Exception:
                    datos = None
                if datos:
                    filas = [(_TAGS.get(k, f"Etiqueta {k}"), _valor(_TAGS.get(k, ""), v))
                             for k, v in datos.items()]
                    secciones.append(_seccion(titulo, sorted(filas)))

            try:
                gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
            except Exception:
                gps = None
            if gps:
                filas = [(_GPS.get(k, f"Etiqueta {k}"), _human(v)) for k, v in gps.items()]
                lat = _grados(gps.get(2), gps.get(1, ""))
                lon = _grados(gps.get(4), gps.get(3, ""))
                if lat and lon:
                    filas.insert(0, ("Coordenadas", f"{lat[0]:.6f}, {lon[0]:.6f}"))
                    filas.insert(1, ("En grados", f"{lat[1]}  {lon[1]}"))
                secciones.append(_seccion("Ubicacion (GPS)", sorted(filas)))

        try:
            xmp = im.getxmp()
        except Exception:
            xmp = None
        if xmp:
            filas = []
            _aplanar(xmp, filas)
            if filas:
                secciones.append(_seccion("XMP", filas[:80]))

        saltar = {"icc_profile", "exif", "photoshop", "xmp", "dpi"}
        filas = [(k, _human(v)) for k, v in im.info.items() if k not in saltar]
        if filas:
            secciones.append(_seccion("Otros datos del formato", sorted(filas)))

    return [s for s in secciones if s["filas"]]


def _valor(nombre, v):
    tabla = _ENUMS.get(nombre)
    if tabla and isinstance(v, int):
        return f"{v} — {tabla.get(v, 'sin descripcion')}"
    if nombre == "ExposureTime" and v:
        try:
            return f"{float(v)} s" + (f"  (1/{round(1 / float(v))} s)" if 0 < float(v) < 1 else "")
        except (TypeError, ValueError, ZeroDivisionError):
            pass
    if nombre == "FNumber" and v:
        try:
            return f"f/{float(v):g}"
        except (TypeError, ValueError):
            pass
    if nombre in ("FocalLength", "FocalLengthIn35mmFilm") and v:
        try:
            return f"{float(v):g} mm"
        except (TypeError, ValueError):
            pass
    return _human(v)


def _aplanar(obj, filas, prefijo=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            _aplanar(v, filas, f"{prefijo}{k}." if not prefijo else f"{prefijo}{k}.")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            _aplanar(v, filas, f"{prefijo}{i}.")
    else:
        txt = _human(obj)
        if txt:
            filas.append((prefijo.rstrip("."), txt))


def _proporcion(w, h):
    from math import gcd
    g = gcd(w, h) or 1
    a, b = w // g, h // g
    if a > 40 or b > 40:
        return f"{w / h:.3f} : 1"
    return f"{a}:{b}  ({w / h:.3f} : 1)"
