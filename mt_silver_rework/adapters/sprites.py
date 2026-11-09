"""Sprite to plik tekstowy: paleta, pusta linia, siatka znaków. Oba widoki rysują go piksel w piksel."""
from functools import lru_cache
from pathlib import Path

SPRITE_DIR = Path(__file__).resolve().parent.parent / "assets" / "sprites"


@lru_cache(maxsize=None)
def load_sprite(name):
    """Zwraca wiersze pikseli (r, g, b); przezroczysty piksel to None."""
    palette, pixels = (SPRITE_DIR / f"{name}.txt").read_text(encoding="utf-8").split("\n\n")
    colors = {line[0]: tuple(bytes.fromhex(line[2:])) for line in palette.splitlines()}
    return [[colors.get(char) for char in row] for row in pixels.split()]


def sprite_bottom(name):
    """Wysokość sprite'a liczona do najniższego widocznego piksela."""
    return max(y for y, row in enumerate(load_sprite(name)) if any(row)) + 1


def fighter_sprite(creature, side):
    """Własnego Pokémona widać od tyłu, a rywala od przodu."""
    return f"{creature.species.id}_back" if side == "player" else creature.species.id
