from dataclasses import dataclass


@dataclass(frozen=True)
class Preset:
    key: str
    label: str
    group: str
    ratio: float
    mm: tuple | None = None
    framing: str = "libre"
    hint: str = ""

    @property
    def is_doc(self) -> bool:
        return self.framing == "documento"

    def pixels(self, dpi: int = 300) -> tuple:
        if self.mm:
            w = round(self.mm[0] / 25.4 * dpi)
            h = round(self.mm[1] / 25.4 * dpi)
            return w, h
        return None


PRESETS = [
    Preset("ig_square", "Cuadrado 1:1", "Instagram", 1 / 1, hint="Feed clasico y foto de perfil"),
    Preset("ig_portrait", "Vertical 4:5", "Instagram", 4 / 5, hint="El que mas pantalla ocupa en el feed"),
    Preset("ig_story", "Story / Reel 9:16", "Instagram", 9 / 16, hint="Pantalla completa"),
    Preset("ig_land", "Horizontal 1.91:1", "Instagram", 1.91 / 1, hint="Apaisado maximo del feed"),
    Preset("ig_grid", "Vertical 3:4", "Instagram", 3 / 4, hint="El vertical del feed nuevo y de la cuadricula"),

    Preset("doc_3x4", "Carnet 3x4 cm", "Documento", 30 / 40, mm=(30, 40), framing="documento",
           hint="Latinoamerica: DNI, carnets, tramites"),
    Preset("doc_35x45", "Pasaporte 3.5x4.5 cm", "Documento", 35 / 45, mm=(35, 45), framing="documento",
           hint="Estandar ICAO / visa europea"),
    Preset("doc_2x2in", "EEUU 2x2 in", "Documento", 1 / 1, mm=(50.8, 50.8), framing="documento",
           hint="Visa y pasaporte de EEUU"),
    Preset("doc_4x4", "Carnet 4x4 cm", "Documento", 1 / 1, mm=(40, 40), framing="documento",
           hint="Fichas y credenciales"),
    Preset("doc_5x5", "Carnet 5x5 cm", "Documento", 1 / 1, mm=(50, 50), framing="documento", hint="Titulos y diplomas"),

    Preset("free_16_9", "Panoramica 16:9", "Otros", 16 / 9, hint="Miniatura de video / portada"),
    Preset("free_3_2", "Foto 3:2", "Otros", 3 / 2, hint="Proporcion de camara reflex"),
]

BY_KEY = {p.key: p for p in PRESETS}

SHEETS = {
    "10x15": (152.4, 101.6, "Hoja 10x15 cm (horizontal)"),
    "13x18": (177.8, 127.0, "Hoja 13x18 cm (horizontal)"),
    "a4": (210.0, 297.0, "Hoja A4 (vertical)"),
}
