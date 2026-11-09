"""Widok tekstowy (curses).

Sprite'y 64x64 rysujemy bez skalowania: jedno pole terminala to dwa piksele w pionie.
Każda metoda odświeża tylko swój fragment ekranu.
"""
import curses
import math
import random
import sys
import textwrap
from functools import lru_cache

from adapters.sprites import fighter_sprite, load_sprite
from adapters.theme import THEMES, hp_color
from core.entities import STATUS_NAMES, EventKind
from ports.interfaces import Command, IGameView, QuitGame

WIDTH, HEIGHT = 132, 44
SPRITE_WIDTH, SPRITE_HEIGHT = 64, 32
SLOTS = {"enemy": (68, 1), "player": (1, 5)}
CLEAR_SPANS = {"enemy": (66, 66), "player": (0, 67)}  # Sprite przy ataku przesuwa się o 2 kolumny.
HP_SLOTS = {"enemy": (4, 1), "player": (72, 33)}
BAR_WIDTH = 30
BATTLE_MESSAGE = (0, 37, 84, 6)
BATTLE_MENU = (84, 37, 48, 6)
WORLD_MESSAGE = (0, 35, 132, 7)
MAP_LEFT, MAP_TOP, TILE_WIDTH, TILE_HEIGHT = 1, 3, 4, 2
PANEL_LEFT = 108
LOGO_TOP, LOGO_BOTTOM, TITLE_MENU_TOP = 2, 12, 15
SNOW_MS = 110
MAX_COLOR_PAIRS = 255  # curses.color_pair trzyma numer pary na 8 bitach; wyższe numery psują kolory.
TEXT_SPEEDS = {"slow": (40, 1200), "normal": (20, 800), "fast": (6, 350)}  # ms na znak, ms na komunikat

KEYS = {curses.KEY_UP: Command.UP, curses.KEY_DOWN: Command.DOWN, curses.KEY_LEFT: Command.LEFT,
        curses.KEY_RIGHT: Command.RIGHT, 10: Command.CONFIRM, 13: Command.CONFIRM,
        curses.KEY_ENTER: Command.CONFIRM, ord(" "): Command.CONFIRM, 27: Command.CANCEL}

# Kafelek mapy: dwa wiersze znaków, kolor znaku, kolor tła.
TILES = {
    "#": (("####", "####"), (70, 75, 85), (150, 155, 165)),
    "^": ((" /\\ ", "/__\\"), (60, 60, 70), (190, 195, 205)),
    "T": ((" /\\ ", "/||\\"), (10, 80, 40), (170, 220, 170)),
    "~": (("~ ~ ", " ~ ~"), (20, 80, 200), (170, 210, 250)),
    "B": (("[][]", "[][]"), (150, 40, 40), (240, 190, 190)),
    ",": ((" ., ", ",  ."), (70, 150, 80), (205, 240, 200)),
    ".": (("    ", " .  "), (140, 110, 70), (235, 220, 180)),
    ":": ((": . ", " . :"), (130, 100, 70), (215, 195, 165)),
    "*": ((" .  ", "   ."), (150, 180, 220), (250, 252, 255)),
    "-": (("  / ", " /  "), (120, 170, 220), (214, 236, 251)),
}
OBJECTS = {
    "sign": (("[==]", " || "), (90, 60, 20)), "npc": ((" oo ", "/||\\"), (40, 40, 140)),
    "item": (("(**)", "(__)"), (200, 30, 30)), "heal": (("/++\\", "|++|"), (200, 30, 30)),
    "boss": ((" R! ", "/||\\"), (200, 0, 0)), "exit": (("/~~\\", "|  |"), (0, 0, 0)),
}
HERO = ((" @@ ", "/||\\"), (20, 90, 180))

LEVELS = (0, 95, 135, 175, 215, 255)
XTERM_COLORS = [(r, g, b) for r in LEVELS for g in LEVELS for b in LEVELS] + [(8 + i * 10,) * 3 for i in range(24)]


def rgb(hex_color):
    return tuple(bytes.fromhex(hex_color[1:]))


def luminance(color):
    return 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]


def tone(color):
    if color is None:
        return 0
    value = luminance(color)
    return 0 if value > 200 else 1 if value > 140 else 2 if value > 80 else 3


def ascii_cell(upper, lower, paper):
    """Pole sprite'a to pełny kolor; znak ASCII zostaje tylko tam, gdzie połowa pola jest przezroczysta."""
    if upper is None or lower is None:
        return '"' if lower is None else "_", upper or lower, paper
    darker = min(upper, lower, key=luminance)
    color = darker if tone(darker) == 3 else upper  # Ciemne kontury mają pierwszeństwo.
    return " ", color, color


def color_axes(color):
    """Jasność i dwie osie barwy. Porównywanie w tym układzie nie gubi odcienia, np. brązów."""
    r, g, b = color
    return luminance(color), r - g, (r + g) / 2 - b


@lru_cache(maxsize=None)
def to_xterm(color):
    """Numer najbliższego koloru w palecie 256 kolorów (pozycje od 16 to sześcian i szarości)."""
    target = color_axes(color)
    return 16 + min(range(len(XTERM_COLORS)), key=lambda i: math.dist(target, color_axes(XTERM_COLORS[i])))


class TuiView(IGameView):
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.scene = None
        self.menu = None
        self.text = ""
        self.pairs = {}
        self.top, self.left = 0, 0
        self.world = self.team = self.battle = self.hero = None
        self.fighters = {"enemy": None, "player": None}
        self.sprites = {"enemy": None, "player": None}
        self.shown_hp = {"enemy": 0, "player": 0}
        self.flakes = [[random.randrange(WIDTH), random.randrange(HEIGHT - 1)] for _ in range(45)]
        curses.curs_set(0)
        stdscr.keypad(True)
        rows, cols = stdscr.getmaxyx()
        if rows < HEIGHT or cols < WIDTH:  # Prośba do terminala o powiększenie okna; nie każdy ją spełni.
            sys.stdout.write(f"\x1b[8;{HEIGHT};{WIDTH}t")
            sys.stdout.flush()

    # --- podstawy rysowania ---

    def apply_settings(self, settings):
        self.settings = settings
        self.c = {name: rgb(value) for name, value in THEMES[settings["theme"]].items()}
        self.animated = settings["animations"] == "on"
        self.char_ms, self.hold_ms = TEXT_SPEEDS[settings["text_speed"]]
        self._repaint()

    def _attr(self, foreground, background):
        if curses.COLORS < 256:
            return curses.A_NORMAL
        key = to_xterm(foreground), to_xterm(background)
        if key not in self.pairs:
            if len(self.pairs) >= MAX_COLOR_PAIRS:
                return curses.A_NORMAL
            self.pairs[key] = len(self.pairs) + 1
            curses.init_pair(self.pairs[key], *key)
        return curses.color_pair(self.pairs[key])

    def _put(self, y, x, text, foreground=None, background=None, bold=False):
        attr = self._attr(foreground or self.c["text"], background or self.c["window"])
        try:
            self.stdscr.addstr(self.top + y, self.left + x, text, attr | (curses.A_BOLD if bold else 0))
        except curses.error:
            pass  # curses zgłasza błąd przy pisaniu w ostatnim polu ekranu, choć znak się pojawia.

    def _clear(self, x, y, width, height):
        for row in range(y, y + height):
            self._put(row, x, " " * width)

    def _box(self, x, y, width, height, color=None):
        color = color or self.c["dim"]
        self._put(y, x, "╭" + "─" * (width - 2) + "╮", color)
        for row in range(y + 1, y + height - 1):
            self._put(row, x, "│" + " " * (width - 2) + "│", color)
        self._put(y + height - 1, x, "╰" + "─" * (width - 2) + "╯", color)

    def _pixels(self, name, left, top):
        rows = load_sprite(name)
        paper = self.c["window"]
        blocks = self.settings["graphics"] == "blocks"
        for row in range(0, len(rows) - 1, 2):
            for column, (upper, lower) in enumerate(zip(rows[row], rows[row + 1])):
                if upper or lower:
                    char, foreground, background = (("▀", upper or paper, lower or paper) if blocks
                                                    else ascii_cell(upper, lower, paper))
                    self._put(top + row // 2, left + column, char, foreground, background)

    def _hint(self, text):
        self._put(HEIGHT - 1, 0, text.ljust(WIDTH - 1), self.c["dim"])

    # --- wejście i rozmiar okna ---

    def _key(self, timeout=-1):
        self.stdscr.timeout(timeout)
        key = self.stdscr.getch()
        if key == curses.KEY_RESIZE:
            self._repaint()
            return -1
        return key

    def _fit(self):
        """Sprite'y są rysowane 1:1, więc gra potrzebuje okna o stałym minimalnym rozmiarze."""
        while True:
            rows, cols = self.stdscr.getmaxyx()
            if rows >= HEIGHT and cols >= WIDTH:
                self.top, self.left = (rows - HEIGHT) // 2, (cols - WIDTH) // 2
                return
            self.stdscr.erase()
            self.stdscr.addnstr(0, 0, f"Powiększ okno do {WIDTH}x{HEIGHT} (teraz {cols}x{rows}). Q: wyjście", cols - 1)
            self.stdscr.refresh()
            self.stdscr.timeout(-1)
            if self.stdscr.getch() in (ord("q"), ord("Q"), 27):
                raise QuitGame

    def _repaint(self):
        """Pełne przerysowanie: tylko przy zmianie ekranu, motywu albo rozmiaru okna."""
        self.pairs.clear()  # Każdy ekran ma własną pulę par kolorów, bo jest ich tylko 255.
        self._fit()
        self.stdscr.bkgd(" ", self._attr(self.c["text"], self.c["window"]))
        self.stdscr.erase()
        if self.scene:
            {"title": self._draw_title, "world": self._draw_world, "battle": self._draw_battle}[self.scene]()
        if self.menu:
            self._draw_menu(self.menu)
        self.stdscr.refresh()

    def _hold(self, ms):
        """Czeka podaną liczbę milisekund; dowolny klawisz skraca czekanie."""
        self.stdscr.refresh()
        self._key(int(ms))

    # --- ekran tytułowy ---

    def show_title(self):
        self.scene = "title"
        self._repaint()

    def _draw_title(self):
        self._pixels("logo", (WIDTH - len(load_sprite("logo")[0])) // 2, LOGO_TOP)
        subtitle = "Walka z Redem"
        self._put(LOGO_BOTTOM - 1, (WIDTH - len(subtitle)) // 2, subtitle, bold=True)

    def _update_snow(self, menu):
        left, top, width, height = self._menu_box(menu)

        def draw(flake, char):
            x, y = flake
            hidden = LOGO_TOP <= y <= LOGO_BOTTOM or (left <= x < left + width and top <= y < top + height)
            if not hidden:
                self._put(y, x, char, self.c["dim"])

        for flake in self.flakes:
            draw(flake, " ")
            flake[1] += 1
            if flake[1] >= HEIGHT - 1:
                flake[:] = [random.randrange(WIDTH), 0]
            draw(flake, "*")
        self.stdscr.refresh()

    # --- mapa ---

    def show_world(self, world, team):
        self.world, self.team, self.text = world, team, ""
        self.hero = world.position
        self.scene = "world"
        self._repaint()

    def _draw_world(self):
        self._put(1, MAP_LEFT, self.world.area.name.center(TILE_WIDTH * 26), self.c["accent"], bold=True)
        for y, row in enumerate(self.world.area.rows):
            for x in range(len(row)):
                self._draw_tile(x, y)
        self._draw_hero()
        self._draw_team()
        self._draw_message()

    def _draw_glyphs(self, x, y, glyphs, foreground, background, bold=False):
        for row, text in enumerate(glyphs):
            self._put(MAP_TOP + y * TILE_HEIGHT + row, MAP_LEFT + x * TILE_WIDTH, text, foreground, background, bold)

    def _draw_tile(self, x, y):
        glyphs, foreground, background = TILES[self.world.tile_at(x, y)]
        found = self.world.object_at(x, y)
        if found:
            glyphs, foreground = OBJECTS[found.kind]
        self._draw_glyphs(x, y, glyphs, foreground, background, bold=found is not None)

    def _draw_hero(self):
        background = TILES[self.world.tile_at(*self.hero)][2]
        self._draw_glyphs(*self.hero, *HERO, background, bold=True)

    def move_player(self, x, y):
        """Krok gracza to tylko dwa kafelki: stary i nowy."""
        self._draw_tile(*self.hero)
        self.hero = x, y
        self._draw_hero()
        self.stdscr.refresh()

    def _draw_team(self):
        self._put(MAP_TOP, PANEL_LEFT, "DRUŻYNA", self.c["accent"], bold=True)
        for index, creature in enumerate(self.team):
            row = MAP_TOP + 2 + index * 3
            share = creature.hp / creature.max_hp
            filled = round(share * 12)
            self._put(row, PANEL_LEFT, f"{creature.name:<12} Lv{creature.level}", bold=True)
            self._put(row + 1, PANEL_LEFT, "=" * filled + "-" * (12 - filled), rgb(hp_color(share)))
            self._put(row + 1, PANEL_LEFT + 13, f"{creature.hp}/{creature.max_hp}", self.c["dim"])

    def read_command(self):
        self._hint("Strzałki: chodzenie (wejdź w obiekt, żeby go użyć) | Esc: menu")
        self.stdscr.refresh()
        while True:
            command = KEYS.get(self._key())
            if command:
                return command

    # --- walka ---

    def show_battle(self, battle, portrait):
        self.battle, self.text = battle, ""
        self.fighters = {"enemy": None, "player": None}
        self.sprites = {"enemy": portrait, "player": None}
        self.scene = "battle"
        if self.animated:
            for row in range(HEIGHT // 2 + 1):
                self._put(row, 0, "#" * WIDTH, self.c["accent"])
                self._put(HEIGHT - 1 - row, 0, "#" * WIDTH, self.c["accent"])
                self.stdscr.refresh()
                curses.napms(10)
        self._repaint()

    def _draw_battle(self):
        for side in ("enemy", "player"):
            self._draw_fighter(side)
            self._draw_hp(side)
        self._box(*BATTLE_MENU)
        self._draw_message()

    def _draw_fighter(self, side, shift=0, hidden=False):
        left, top = SLOTS[side]
        self._clear(CLEAR_SPANS[side][0], top, CLEAR_SPANS[side][1], SPRITE_HEIGHT)
        if self.sprites[side] and not hidden:
            self._pixels(self.sprites[side], left + shift, top)
        self.stdscr.refresh()

    def _draw_hp(self, side):
        x, y = HP_SLOTS[side]
        self._clear(x, y, BAR_WIDTH + 14, 3)
        creature = self.fighters[side]
        if creature:
            share = self.shown_hp[side] / creature.max_hp
            filled = max(1, round(share * BAR_WIDTH)) if self.shown_hp[side] > 0 else 0
            self._put(y, x, f"{creature.name}  Lv{creature.level}", bold=True)
            self._put(y, x + 26, STATUS_NAMES[creature.status], rgb(hp_color(0)), bold=True)
            self._put(y + 1, x, "HP [" + "=" * filled + "-" * (BAR_WIDTH - filled) + "]", rgb(hp_color(share)))
            if side == "player":
                self._put(y + 2, x + 4, f"{round(self.shown_hp[side])}/{creature.max_hp}")
        self.stdscr.refresh()

    def play(self, event):
        if event.kind is EventKind.TEXT:
            self._type(event.text)
            self._hold(self.hold_ms)
            return
        side = event.side
        creature = self.battle.active[side]
        if event.kind is EventKind.SEND_OUT:
            self.fighters[side], self.sprites[side], self.shown_hp[side] = creature, fighter_sprite(creature, side), creature.hp
            self._draw_fighter(side)
            self._draw_hp(side)
        elif event.kind is EventKind.ATTACK and self.animated:
            self._draw_fighter(side, shift=2 if side == "player" else -2)
            self._hold(90)
            self._draw_fighter(side)
        elif event.kind is EventKind.HIT and self.animated:
            for hidden in (True, False, True, False):
                self._draw_fighter(side, hidden=hidden)
                self._hold(60)
        elif event.kind is EventKind.HP:
            self._animate_hp(side, creature)
        elif event.kind is EventKind.STATUS:
            self._draw_hp(side)
        elif event.kind is EventKind.FAINT:
            self.fighters[side] = self.sprites[side] = None
            self._draw_fighter(side)
            self._draw_hp(side)

    def _animate_hp(self, side, creature):
        start, frames = self.shown_hp[side], 14 if self.animated else 1
        for frame in range(1, frames + 1):
            self.shown_hp[side] = start + (creature.hp - start) * frame / frames
            self._draw_hp(side)
            if self.animated:
                self._hold(30)

    # --- komunikaty ---

    def _message_box(self):
        return BATTLE_MESSAGE if self.scene == "battle" else WORLD_MESSAGE

    def _draw_message(self):
        x, y, width, height = self._message_box()
        self._box(x, y, width, height)
        for row, line in enumerate(textwrap.wrap(self.text, width - 4)[:height - 2]):
            self._put(y + 1 + row, x + 2, line)

    def _type(self, text):
        """Pisze tekst znak po znaku; Enter pokazuje od razu całość."""
        self.text = text
        x, y, width, height = self._message_box()
        self._box(x, y, width, height)
        instant = not self.animated
        for row, line in enumerate(textwrap.wrap(text, width - 4)[:height - 2]):
            for column, char in enumerate(line):
                self._put(y + 1 + row, x + 2 + column, char)
                if not instant:
                    self.stdscr.refresh()
                    instant = KEYS.get(self._key(self.char_ms)) is Command.CONFIRM
        self.stdscr.refresh()

    def say(self, text, wait=True):
        self._type(text)
        if wait:
            x, y, width, height = self._message_box()
            self._put(y + height - 2, x + width - 4, ">>", self.c["accent"], bold=True)
            self._hint("Enter: dalej")
            while KEYS.get(self._key()) is not Command.CONFIRM:
                pass
            self.text = ""
            self._draw_message()

    # --- menu ---

    def choose(self, menu):
        self.menu = menu
        self._draw_menu(menu)
        self._hint("Strzałki: wybór | Enter: zatwierdź" + (" | Esc: wstecz" if menu.can_cancel else ""))
        snow = menu.place == "title" and self.animated
        result = self._run_menu(menu, snow)
        self.menu = None
        if menu.place == "battle":
            self._box(*BATTLE_MENU)
        else:
            self._repaint()
        return result

    def _run_menu(self, menu, snow):
        while True:
            key = self._key(SNOW_MS if snow else -1)
            if key == -1 and snow:
                self._update_snow(menu)
            command = KEYS.get(key)
            if command is Command.CONFIRM and menu.current.enabled:
                return menu.cursor
            if command is Command.CANCEL and menu.can_cancel:
                return None
            if command:
                previous = menu.cursor
                menu.move_cursor(command)
                self._draw_item(menu, previous)  # Zmiana wyboru odświeża tylko dwie opcje i opis.
                self._draw_item(menu, menu.cursor)
                self._draw_details(menu)
                self.stdscr.refresh()

    def _menu_box(self, menu):
        """Wymiary okna menu: x, y, szerokość, wysokość."""
        if menu.place == "battle":
            return BATTLE_MENU
        has_sprite = any(item.sprite for item in menu.items)
        has_detail = any(item.detail for item in menu.items)
        width = 124 if has_sprite else 64
        height = 2 + bool(menu.title) + len(menu.lines) + bool(menu.lines) + len(menu.items) + (4 if has_detail else 0)
        if has_sprite:
            height = max(height, SPRITE_HEIGHT + 2)
        top = TITLE_MENU_TOP if menu.place == "title" else HEIGHT - height - 1 if has_sprite else (HEIGHT - height) // 2
        return (WIDTH - width) // 2, top, width, height

    def _item_position(self, menu, index):
        x, y, width, _ = self._menu_box(menu)
        if menu.place == "battle":
            return y + 1 + index // menu.columns, x + 2 + (index % menu.columns) * ((width - 4) // menu.columns)
        return y + 1 + bool(menu.title) + len(menu.lines) + bool(menu.lines) + index, x + 2

    def _draw_menu(self, menu):
        x, y, width, height = self._menu_box(menu)
        self._box(x, y, width, height, self.c["accent"])
        row = y + 1
        if menu.title:
            self._put(row, x + 2, menu.title, self.c["accent"], bold=True)
            row += 1
        for line in menu.lines:
            self._put(row, x + 2, line)
            row += 1
        for index in range(len(menu.items)):
            self._draw_item(menu, index)
        self._draw_details(menu)
        self.stdscr.refresh()

    def _draw_item(self, menu, index):
        item = menu.items[index]
        y, x = self._item_position(menu, index)
        selected = index == menu.cursor
        color = self.c["accent"] if selected else self.c["text"] if item.enabled else self.c["dim"]
        self._put(y, x, (">" if selected else " ") + item.label, color, bold=selected)

    def _draw_details(self, menu):
        x, y, width, height = self._menu_box(menu)
        has_sprite = any(item.sprite for item in menu.items)
        detail_width = width - 4 - (SPRITE_WIDTH + 2 if has_sprite else 0)
        if any(item.detail for item in menu.items):
            rows = 1 if menu.place == "battle" else 3
            wrapped = textwrap.wrap(menu.current.detail, detail_width)
            for row in range(rows):
                text = wrapped[row] if row < len(wrapped) else ""
                self._put(y + height - 1 - rows + row, x + 2, text.ljust(detail_width), self.c["dim"])
        if has_sprite:
            left = x + width - SPRITE_WIDTH - 2
            self._clear(left, y + 1, SPRITE_WIDTH, SPRITE_HEIGHT)
            self._pixels(menu.current.sprite, left, y + 1)
