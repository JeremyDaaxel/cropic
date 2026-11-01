import os

from PIL import Image, ImageDraw

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "ui", "img", "logo.png")
ICO = os.path.join(BASE, "ui", "img", "cropic.ico")
SIZES = [16, 24, 32, 48, 64, 128, 256]
BG = (66, 66, 66, 255)


def render(size: int) -> Image.Image:
    logo = Image.open(SRC).convert("RGBA")

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    radius = max(2, round(size * 0.22))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius, fill=255)
    plate = Image.new("RGBA", (size, size), BG)
    canvas.paste(plate, (0, 0), mask)

    pad = max(1, round(size * 0.12))
    box = size - pad * 2
    scale = min(box / logo.width, box / logo.height)
    lw, lh = max(1, round(logo.width * scale)), max(1, round(logo.height * scale))
    logo = logo.resize((lw, lh), Image.LANCZOS)
    canvas.paste(logo, ((size - lw) // 2, (size - lh) // 2), logo)
    return canvas


def main():
    images = [render(s) for s in SIZES]
    images[-1].save(ICO, format="ICO", sizes=[(s, s) for s in SIZES])
    images[-1].save(os.path.join(BASE, "ui", "img", "logo-mark.png"))
    print("Icono escrito en", ICO)


if __name__ == "__main__":
    main()
