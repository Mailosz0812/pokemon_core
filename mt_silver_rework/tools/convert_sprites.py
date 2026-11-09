"""Jednorazowo zamienia sprite'y PNG z FireRed na pliki tekstowe 64x64 w assets/sprites.

Folder źródłowy ma podfoldery front, back i trainers (red.png). Sprite'y z FireRed mają 64x64,
więc przechodzą bez zmian; większe obrazy, np. sprite Reda, są zmniejszane.

Uruchomienie z głównego folderu projektu:
    .venv/bin/python tools/convert_sprites.py FOLDER_ZE_SPRITE_AMI
"""
import string
import sys
from collections import Counter
from pathlib import Path

from PySide6.QtGui import QImage

TARGET = 64
OUTPUT = Path(__file__).resolve().parent.parent / "assets" / "sprites"
OPAQUE_SHARE = 0.4
DARK_VOTE = 1.5


def luminance(color):
    return 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]


def read_pixels(path):
    image = QImage(str(path)).convertToFormat(QImage.Format.Format_ARGB32)
    rows = []
    for y in range(image.height()):
        row = []
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            row.append((color.red(), color.green(), color.blue()) if color.alpha() >= 128 else None)
        rows.append(row)
    return rows


def shrink(rows):
    """Każdy nowy piksel to wynik głosowania w bloku; ciemne kontury mają mocniejszy głos."""
    size = len(rows)
    result = []
    for y in range(TARGET):
        row = []
        for x in range(TARGET):
            block = [rows[sy][sx]
                     for sy in range(y * size // TARGET, (y + 1) * size // TARGET)
                     for sx in range(x * size // TARGET, (x + 1) * size // TARGET)]
            opaque = [pixel for pixel in block if pixel]
            if len(opaque) < OPAQUE_SHARE * len(block):
                row.append(None)
                continue
            votes = Counter(opaque)
            row.append(max(votes, key=lambda c: votes[c] * (DARK_VOTE if luminance(c) < 70 else 1)))
        result.append(row)
    return result


def write_sprite(name, rows):
    colors = sorted({pixel for row in rows for pixel in row if pixel})
    symbols = dict(zip(colors, string.ascii_letters))
    palette = [f"{symbol}={bytes(color).hex()}" for color, symbol in symbols.items()]
    grid = ["".join(symbols.get(pixel, ".") for pixel in row) for row in rows]
    (OUTPUT / f"{name}.txt").write_text("\n".join(palette) + "\n\n" + "\n".join(grid) + "\n", encoding="utf-8")


def main():
    source = Path(sys.argv[1])
    for path in sorted((source / "front").glob("*.png")):
        write_sprite(NUMBERS[int(path.stem)], shrink(read_pixels(path)))
    for path in sorted((source / "back").glob("*.png")):
        write_sprite(f"{NUMBERS[int(path.stem)]}_back", shrink(read_pixels(path)))
    write_sprite("red", shrink(read_pixels(source / "trainers" / "red.png")))


NUMBERS = {25: "pikachu", 131: "lapras", 143: "snorlax", 3: "venusaur", 6: "charizard", 9: "blastoise",
           157: "typhlosion", 160: "feraligatr", 154: "meganium", 181: "ampharos", 196: "espeon",
           214: "heracross", 248: "tyranitar", 250: "ho-oh"}

if __name__ == "__main__":
    main()
