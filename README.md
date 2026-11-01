# Cropic

App de escritorio para recortar fotos para Instagram. Quita la interfaz de las capturas de pantalla, detecta la cara y propone encuadres. También parte una foto en carrusel y prepara fotos de carnet listas para imprimir.

## Qué hace

- Recorta automáticamente las capturas de Instagram: barra de estado, cabecera, botones y comentarios.
- Detecta los rostros y propone varios encuadres, cada uno con su puntuación.
- Parte una foto en un carrusel de 2, 3 o 4 piezas con la unión sobre la cara.
- Formatos de Instagram (1:1, 4:5, 9:16, 1.91:1 y 3:4), de documento (carnet 3×4, pasaporte 3,5×4,5, EE. UU. 2×2 in, 4×4 y 5×5) y planchas de impresión de 10×15, 13×18 y A4.
- El recorte se puede mover y redimensionar a mano.
- Vista previa dentro del marco de Instagram.
- Doble clic en una foto para ver todos sus metadatos: EXIF, GPS, XMP y perfil de color.
- Exporta en JPG, PNG, WebP y TIFF, en sRGB y con los dpi correctos, sin ampliar la imagen.

## Uso

Necesita Windows 10 u 11 con WebView2 y Python 3.10 o superior.

```
pip install -r requirements.txt
python app.py
```

`python server.py` abre la misma interfaz en el navegador, en http://127.0.0.1:8770.

### Atajos

| Tecla | Acción |
|---|---|
| ↑ / ↓ | foto anterior / siguiente |
| ← / → | variación anterior / siguiente |
| Mayús + ← / → | mover el carrusel en la vista previa |
| Enter | exportar |

## Ejecutable

```
pip install pyinstaller
python build_exe.py
```

Genera `dist/Cropic.exe`, un solo archivo que funciona sin instalar Python.

## Créditos

- Detección de rostros: [YuNet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet), de OpenCV Zoo, con licencia MIT.
- Tipografía: Pencil (ver `ui/fonts/Pencil-README.txt`).
