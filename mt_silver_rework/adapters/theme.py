"""Kolory wspólne dla obu widoków."""

THEMES = {
    "snow": {"window": "#e8f0f8", "panel": "#ffffff", "text": "#14204a", "dim": "#6b7890",
             "accent": "#1f5fb4", "on_accent": "#ffffff", "sky_top": "#8fbbe8", "sky_bottom": "#e8f2fb",
             "ground": "#f7fbff", "shadow": "#c4d6e8", "snowflake": "#ffffff"},
    "night": {"window": "#141b2e", "panel": "#1e2740", "text": "#e6ecf8", "dim": "#8b97b3",
              "accent": "#6ea8ff", "on_accent": "#0e1424", "sky_top": "#0d1530", "sky_bottom": "#2a3a66",
              "ground": "#394a70", "shadow": "#2a3755", "snowflake": "#cfe0ff"},
}


def hp_color(share):
    return "#35b45a" if share > 0.5 else "#e6b422" if share > 0.2 else "#d8352b"
