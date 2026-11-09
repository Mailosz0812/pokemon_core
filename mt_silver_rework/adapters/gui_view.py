"""Widok graficzny (PySide6).

Każdy element to osobny widget, więc Qt odświeża tylko to, co faktycznie się zmieniło.
Metody blokują kontroler przez zagnieżdżoną pętlę zdarzeń, a okno przez cały czas reaguje.
"""
import math
import random
import sys
from functools import lru_cache

from PySide6.QtCore import QElapsedTimer, QEventLoop, QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QFont, QImage, QLinearGradient, QPainter, QPen, QPixmap, QPolygon, QRegion
from PySide6.QtWidgets import (QApplication, QFrame, QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QLabel,
                               QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from adapters.sprites import fighter_sprite, load_sprite, sprite_bottom
from adapters.theme import THEMES, hp_color
from core.entities import STATUS_NAMES, EventKind
from ports.interfaces import Click, Command, IGameView, QuitGame

FRAME_MS = 16
WALK_MS = 110
TILE_SCALE, TILE_SIZE = 2, 32  # Kafelek 16x16 powiększony dokładnie 2 razy.
SPRITE_SIZE = 64
ARENA_SCALES = {"enemy": 4, "player": 5}  # Nasz Pokémon jest bliżej, więc jest większy.
HIDDEN_BEHIND_PANEL = 30  # Tyle pikseli od dołu chowa się za panelem, jak w grach na Game Boya.
BOTTOM_HEIGHT, HINT_BAR_HEIGHT = 150, 40  # Stałe wysokości, żeby układ nie skakał między ekranami.
MENU_GUARD_MS = 150  # Enter wciśnięty przy przewijaniu tekstu nie może od razu wybrać opcji.
HOVER_MIN_TRAVEL = 8  # O tyle pikseli musi przesunąć się mysz, żeby przejąć wybór od klawiatury.
MAP_COLUMNS, MAP_ROWS = 26, 15
TEXT_SPEEDS = {"slow": (25, 1200), "normal": (50, 800), "fast": (150, 350)}  # znaki na sekundę, ms na komunikat
TILE_NAMES = {",": "grass", ".": "path", ":": "cave", "*": "snow", "-": "ice", "#": "rock",
              "^": "boulder", "T": "tree", "~": "water", "B": "wall"}
RIDGE_COLOR = "#7a8aa0"
RIDGE = ((0, 1), (0.14, 0.52), (0.28, 0.68), (0.5, 0.24), (0.68, 0.58), (0.84, 0.42), (1, 0.72), (1, 1))
SNOW_CAPS = (((0.5, 0.24), (0.585, 0.41), (0.54, 0.38), (0.5, 0.43), (0.455, 0.38), (0.41, 0.41)),
             ((0.14, 0.52), (0.19, 0.58), (0.14, 0.57), (0.09, 0.59)),
             ((0.84, 0.42), (0.895, 0.5), (0.84, 0.48), (0.78, 0.49)))
KEYS = {Qt.Key.Key_Up: Command.UP, Qt.Key.Key_Down: Command.DOWN, Qt.Key.Key_Left: Command.LEFT,
        Qt.Key.Key_Right: Command.RIGHT, Qt.Key.Key_Return: Command.CONFIRM, Qt.Key.Key_Enter: Command.CONFIRM,
        Qt.Key.Key_Space: Command.CONFIRM, Qt.Key.Key_Escape: Command.CANCEL}


@lru_cache(maxsize=None)
def sprite_image(name, scale):
    rows = load_sprite(name)
    image = QImage(len(rows[0]), len(rows), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    for y, row in enumerate(rows):
        for x, color in enumerate(row):
            if color:
                image.setPixelColor(x, y, QColor(*color))
    return image.scaled(image.width() * scale, image.height() * scale)  # Powiększenie bez wygładzania.


def sprite_pixmap(name, scale):
    return QPixmap.fromImage(sprite_image(name, scale))


def stylesheet(theme):
    return f"""
    QWidget {{ color: {theme['text']}; font-size: 15px; }}
    #root {{ background: {theme['window']}; }}
    #messageBox, #menuPanel {{ background: {theme['panel']}; border: 2px solid {theme['accent']}; border-radius: 10px; }}
    #messageBox {{ padding: 10px 14px; font-size: 18px; }}
    #areaName {{ color: {theme['accent']}; font-size: 20px; font-weight: bold; }}
    #menuTitle {{ color: {theme['accent']}; font-size: 19px; font-weight: bold; }}
    #detail, #hints {{ color: {theme['dim']}; }}
    QPushButton {{ background: {theme['panel']}; border: 1px solid {theme['dim']}; border-radius: 6px;
                   padding: 7px 12px; text-align: left; }}
    QPushButton[selected="true"] {{ background: {theme['accent']}; color: {theme['on_accent']};
                                    border-color: {theme['accent']}; font-weight: bold; }}
    QPushButton:disabled {{ color: {theme['dim']}; border-style: dashed; }}
    #small {{ padding: 4px 10px; text-align: center; color: {theme['accent']}; }}
    """


def draw_ridge(painter, width, height):
    """Pasmo gór ze śniegiem na szczytach, wspólne dla ekranu tytułowego i tła walki."""
    painter.setPen(Qt.PenStyle.NoPen)
    for color, points in ((RIDGE_COLOR, RIDGE), *(("#ffffff", cap) for cap in SNOW_CAPS)):
        painter.setBrush(QColor(color))
        painter.drawPolygon(QPolygon([QPoint(int(x * width), int(y * height)) for x, y in points]))


def draw_hp_bar(painter, rect, share):
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#3a3f4b"))
    painter.drawRoundedRect(rect, 4, 4)
    painter.setBrush(QColor(hp_color(share)))
    inner = rect.adjusted(2, 2, -2, -2)
    inner.setWidth(int(inner.width() * share))
    if share > 0:
        painter.drawRoundedRect(inner, 3, 3)


class TitlePage(QWidget):
    """Tło rysujemy raz; w każdej klatce odświeżamy tylko pola wokół płatków śniegu."""

    def __init__(self, view):
        super().__init__()
        self.view = view
        self.background = None
        self.flakes = [[random.random(), random.random(), random.uniform(0.04, 0.14)] for _ in range(70)]
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._advance)
        self.timer.start(FRAME_MS)

    def reload(self):
        self.background = None
        self.update()

    def resizeEvent(self, event):
        self.background = None

    def _flake_rect(self, flake):
        return QRect(int(flake[0] * self.width()) - 3, int(flake[1] * self.height()) - 3, 7, 7)

    def _advance(self):
        if not self.isVisible() or not self.view.animated:
            return
        region = QRegion()
        for flake in self.flakes:
            region += self._flake_rect(flake)
            flake[1] += flake[2] * FRAME_MS / 1000
            flake[0] += 0.01 * FRAME_MS / 1000 * math.sin(flake[1] * 12)
            if flake[1] > 1:
                flake[0], flake[1] = random.random(), 0
            region += self._flake_rect(flake)
        self.update(region)

    def _build_background(self):
        self.background = QPixmap(self.size())
        painter = QPainter(self.background)
        width, height, theme = self.width(), self.height(), self.view.theme
        gradient = QLinearGradient(0, 0, 0, height)
        gradient.setColorAt(0, QColor(theme["sky_top"]))
        gradient.setColorAt(1, QColor(theme["sky_bottom"]))
        painter.fillRect(self.rect(), gradient)
        draw_ridge(painter, width, height)
        font = QFont(self.font())
        font.setPixelSize(max(36, height // 11))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(theme["accent"]))
        painter.drawText(QRect(0, height // 22, width, height // 8), Qt.AlignmentFlag.AlignCenter, "MT. SILVER")
        font.setPixelSize(max(16, height // 30))
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor(theme["text"]))
        painter.drawText(QRect(0, height // 22 + height // 9, width, height // 16),
                         Qt.AlignmentFlag.AlignCenter, "Walka z Redem")
        painter.end()

    def paintEvent(self, event):
        if self.background is None:
            self._build_background()
        painter = QPainter(self)
        painter.drawPixmap(event.rect(), self.background, event.rect())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self.view.theme["snowflake"]))
        for flake in self.flakes:
            if self._flake_rect(flake).intersects(event.rect()):
                painter.drawEllipse(self._flake_rect(flake).adjusted(1, 1, -1, -1))


class MapView(QLabel):
    """Mapa jest gotowym obrazem, a gracz osobnym widgetem, więc krok odświeża tylko pola wokół niego."""

    def __init__(self, view):
        super().__init__()
        self.view = view
        self.setFixedSize(MAP_COLUMNS * TILE_SIZE, MAP_ROWS * TILE_SIZE)
        self.hero = QLabel(self)
        self.hero.setPixmap(sprite_pixmap("tile_hero", TILE_SCALE))
        self.hero.adjustSize()

    def show_area(self, world):
        canvas = QPixmap(self.size())
        painter = QPainter(canvas)
        for y, row in enumerate(world.area.rows):
            for x in range(len(row)):
                painter.drawImage(x * TILE_SIZE, y * TILE_SIZE,
                                  sprite_image(f"tile_{TILE_NAMES[world.tile_at(x, y)]}", TILE_SCALE))
                found = world.object_at(x, y)
                if found:
                    painter.drawImage(x * TILE_SIZE, y * TILE_SIZE, sprite_image(f"tile_{found.kind}", TILE_SCALE))
        painter.end()
        self.setPixmap(canvas)
        self.hero.move(world.position[0] * TILE_SIZE, world.position[1] * TILE_SIZE)

    def mousePressEvent(self, event):
        point = event.position().toPoint()
        self.view.on_input(Click(point.x() // TILE_SIZE, point.y() // TILE_SIZE))


class TeamPanel(QWidget):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.team = []
        self.setFixedWidth(190)

    def paintEvent(self, event):
        painter = QPainter(self)
        theme = self.view.theme
        painter.setPen(QColor(theme["accent"]))
        painter.drawText(8, 22, "DRUŻYNA")
        for index, creature in enumerate(self.team):
            y = 36 + index * 56
            painter.setPen(QColor(theme["text"]))
            painter.drawText(8, y + 14, creature.name)
            painter.setPen(QColor(theme["dim"]))
            painter.drawText(110, y + 14, f"{creature.hp}/{creature.max_hp}")
            draw_hp_bar(painter, QRect(8, y + 22, 170, 10), creature.hp / creature.max_hp)


class HpBox(QWidget):
    def __init__(self, parent, view, with_numbers):
        super().__init__(parent)
        self.view, self.with_numbers = view, with_numbers
        self.creature, self.hp = None, 0
        self.setFixedSize(300, 92 if with_numbers else 68)
        self.hide()

    def set_creature(self, creature):
        self.creature = creature
        self.setVisible(creature is not None)
        if creature:
            self.set_hp(creature.hp)

    def set_hp(self, hp):
        self.hp = hp
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme, creature = self.view.theme, self.creature
        painter.setPen(QPen(QColor(theme["accent"]), 2))
        painter.setBrush(QColor(theme["panel"]))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)
        font = QFont(self.font())
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(theme["text"]))
        painter.drawText(14, 24, creature.name)
        painter.drawText(self.width() - 72, 24, f"Lv{creature.level}")
        painter.setPen(QColor(hp_color(0)))
        painter.drawText(self.width() - 170, 24, STATUS_NAMES[creature.status])
        draw_hp_bar(painter, QRect(14, 36, self.width() - 28, 16), self.hp / creature.max_hp)
        if self.with_numbers:
            painter.setPen(QColor(theme["text"]))
            painter.drawText(QRect(14, 56, self.width() - 28, 26), Qt.AlignmentFlag.AlignRight,
                             f"{round(self.hp)}/{creature.max_hp}")


class Fighter(QLabel):
    """Sprite z własną przezroczystością, żeby dało się go płynnie animować."""

    def __init__(self, parent):
        super().__init__(parent)
        self.effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)
        self.base = QPoint()
        self.hide()

    def set_sprite(self, name, scale):
        self.setPixmap(sprite_pixmap(name, scale))
        self.adjustSize()
        self.show()

    def pose(self, dx=0, dy=0, opacity=1.0):
        self.move(self.base + QPoint(int(dx), int(dy)))
        self.effect.setOpacity(opacity)


class Arena(QWidget):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.background = None
        self.fighters = {"enemy": Fighter(self), "player": Fighter(self)}
        self.boxes = {"enemy": HpBox(self, view, False), "player": HpBox(self, view, True)}
        self.sprite_names = {"enemy": None, "player": None}

    def reset(self, portrait):
        for side in self.fighters:
            self.fighters[side].hide()
            self.boxes[side].set_creature(None)
            self.sprite_names[side] = None
        self.show_fighter("enemy", portrait)
        self.reload()

    def show_fighter(self, side, name):
        self.sprite_names[side] = name
        self.fighters[side].set_sprite(name, ARENA_SCALES[side])
        self._place(side)

    def _ground_y(self):
        return self.height() * 11 // 20

    def _place(self, side):
        """Rywal stoi na śniegu, a dół naszego Pokémona chowa się za panelem."""
        name = self.sprite_names[side]
        if name is None:
            return
        scale, fighter = ARENA_SCALES[side], self.fighters[side]
        bottom = sprite_bottom(name) * scale
        if side == "enemy":
            fighter.base = QPoint(self.width() - SPRITE_SIZE * scale - 70, self._ground_y() - bottom)
        else:
            fighter.base = QPoint(50, self.height() - bottom + HIDDEN_BEHIND_PANEL)
        fighter.pose()

    def reload(self):
        self.background = None
        self.update()

    def resizeEvent(self, event):
        self.background = None
        for side in self.fighters:
            self._place(side)
        self.boxes["enemy"].move(40, 26)
        self.boxes["player"].move(self.width() - 340, self.height() - 104)

    def mousePressEvent(self, event):
        self.view.advance()

    def _build_background(self):
        """Szczyt Mt. Silver: niebo, odległe góry, śnieżne pole i zaspy pod walczącymi."""
        self.background = QPixmap(self.size())
        painter = QPainter(self.background)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width, height, theme = self.width(), self.height(), self.view.theme
        horizon = height * 2 // 5
        sky = QLinearGradient(0, 0, 0, horizon)
        sky.setColorAt(0, QColor(theme["sky_top"]))
        sky.setColorAt(1, QColor(theme["sky_bottom"]))
        painter.fillRect(0, 0, width, horizon, sky)
        draw_ridge(painter, width, horizon + height // 10)

        snowfield = QLinearGradient(0, horizon, 0, height)
        snowfield.setColorAt(0, QColor(theme["shadow"]))
        snowfield.setColorAt(0.45, QColor(theme["ground"]))
        painter.fillRect(0, horizon, width, height - horizon, snowfield)

        enemy_center = width - SPRITE_SIZE * ARENA_SCALES["enemy"] // 2 - 70
        player_center = 50 + SPRITE_SIZE * ARENA_SCALES["player"] // 2
        self._draw_snowdrift(painter, enemy_center, self._ground_y(), 190, 44)
        self._draw_snowdrift(painter, player_center, height + 6, 330, 92)

        specks = random.Random(7)  # Stałe ziarno: śnieg za każdym razem leży tak samo.
        painter.setBrush(QColor(theme["snowflake"]))
        for _ in range(90):
            painter.drawEllipse(specks.randrange(width), specks.randrange(height), 3, 3)
        painter.end()

    def _draw_snowdrift(self, painter, center_x, center_y, radius_x, radius_y):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self.view.theme["shadow"]))
        painter.drawEllipse(QPoint(center_x, center_y + 8), radius_x, radius_y)
        painter.setBrush(QColor(self.view.theme["ground"]))
        painter.drawEllipse(QPoint(center_x, center_y), radius_x - 12, radius_y - 8)

    def paintEvent(self, event):
        if self.background is None:
            self._build_background()
        QPainter(self).drawPixmap(event.rect(), self.background, event.rect())


class MenuButton(QPushButton):
    def __init__(self, view, panel, index, item):
        super().__init__(item.label)
        self.panel, self.index = panel, index
        self.setEnabled(item.enabled)
        self.setMinimumHeight(36)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)
        self.clicked.connect(lambda: view.on_input(index))

    def mouseMoveEvent(self, event):
        self.panel.hover(self.index, event.globalPosition().toPoint())
        super().mouseMoveEvent(event)

    def set_selected(self, selected):
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)


class MenuPanel(QFrame):
    """Ten sam panel pokazuje każde menu gry."""

    def __init__(self, view):
        super().__init__()
        self.setObjectName("menuPanel")
        self.view = view
        self.menu, self.buttons, self.shown = None, [], 0
        self.pointer_anchor = QCursor.pos()
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(14, 12, 14, 12)
        self.content = QWidget()
        self.row.addWidget(self.content, 1)
        self.preview = QLabel()
        self.row.addWidget(self.preview)

    def _new_content(self):
        fresh = QWidget()
        self.row.replaceWidget(self.content, fresh)
        self.content.deleteLater()
        self.content = fresh
        return fresh

    def clear(self):
        """Pusty panel zostaje na miejscu, więc reszta interfejsu się nie przesuwa."""
        self.menu, self.buttons, self.shown = None, [], 0
        self._new_content()
        self.preview.hide()

    def show_menu(self, menu):
        """Buduje przyciski od nowa; dzieje się to tylko przy otwarciu menu."""
        self.menu, self.buttons, self.shown = menu, [], menu.cursor
        self.pointer_anchor = QCursor.pos()
        column = QVBoxLayout(self._new_content())
        column.setContentsMargins(0, 0, 0, 0)
        if menu.title:
            column.addWidget(QLabel(menu.title, objectName="menuTitle"))
        if menu.lines:
            column.addWidget(QLabel("\n".join(menu.lines), wordWrap=True))
        grid = QGridLayout()
        grid.setSpacing(6)
        for index, item in enumerate(menu.items):
            self.buttons.append(MenuButton(self.view, self, index, item))
            grid.addWidget(self.buttons[-1], index // menu.columns, index % menu.columns)
        column.addLayout(grid)
        self.detail = QLabel(objectName="detail", wordWrap=True)
        column.addWidget(self.detail)  # Najpierw do układu: widget bez rodzica pokazałby się jako osobne okno.
        self.detail.setVisible(any(item.detail for item in menu.items))
        if menu.can_cancel and menu.place != "battle":
            back = QPushButton("Wstecz (Esc)", objectName="small")
            back.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            back.clicked.connect(lambda: self.view.on_input(Command.CANCEL))
            column.addWidget(back)
        self.preview.setVisible(any(item.sprite for item in menu.items))
        self.buttons[menu.cursor].set_selected(True)
        self._show_selection()

    def hover(self, index, position):
        """Mysz przejmuje wybór dopiero po wyraźnym ruchu, więc drgnięcie nie cofa wyboru z klawiatury."""
        if not self.menu or (position - self.pointer_anchor).manhattanLength() < HOVER_MIN_TRAVEL:
            return
        self.pointer_anchor = position
        if self.menu.cursor != index:
            self.menu.cursor = index
            self.refresh_cursor()

    def move_cursor_by_key(self, command):
        self.menu.move_cursor(command)
        self.pointer_anchor = QCursor.pos()
        self.refresh_cursor()

    def refresh_cursor(self):
        """Zmiana wyboru przemalowuje tylko dwa przyciski i opis."""
        self.buttons[self.shown].set_selected(False)
        self.shown = self.menu.cursor
        self.buttons[self.shown].set_selected(True)
        self._show_selection()

    def _show_selection(self):
        self.detail.setText(self.menu.current.detail)
        if self.menu.current.sprite:
            self.preview.setPixmap(sprite_pixmap(self.menu.current.sprite, 3))


class Curtain(QWidget):
    """Biała warstwa do przejść między ekranami; nie przechwytuje myszy."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.alpha = 0
        self.hide()

    def set_alpha(self, alpha):
        self.alpha = int(alpha)
        self.update()

    def paintEvent(self, event):
        QPainter(self).fillRect(event.rect(), QColor(255, 255, 255, self.alpha))


class Window(QWidget):
    """Główne okno: przekazuje klawisze i zamknięcie do widoku."""

    def __init__(self, view):
        super().__init__(objectName="root")
        self.view = view
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setWindowTitle("Mt. Silver: walka z Redem")
        self.setMinimumSize(1040, 720)

    def keyPressEvent(self, event):
        command = KEYS.get(event.key())
        held_down = event.isAutoRepeat() and command in (Command.CONFIRM, Command.CANCEL)
        if command and not held_down:
            self.view.on_input(command)

    def closeEvent(self, event):
        self.view.on_close()

    def resizeEvent(self, event):
        self.view.overlay.setGeometry(self.rect())
        self.view.curtain.setGeometry(self.rect())


class GuiView(IGameView):
    def __init__(self):
        self.app = QApplication.instance() or QApplication(sys.argv[:1])
        self.app.setStyle("Fusion")
        self.loop, self.input, self.battle = None, None, None
        self.waiting = self.closed = self.skip = self.menu_open = False
        self.settings, self.theme = {}, THEMES["snow"]
        self.animated = True

        self.window = Window(self)
        self.title_page, self.map, self.team, self.arena = TitlePage(self), MapView(self), TeamPanel(self), Arena(self)
        self.area_name = QLabel(objectName="areaName", alignment=Qt.AlignmentFlag.AlignCenter)
        self.world_page = self._build_world_page()
        self.stack = QStackedWidget()
        for page in (self.title_page, self.world_page, self.arena):
            self.stack.addWidget(page)

        self.message = QLabel(objectName="messageBox", wordWrap=True,
                              alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.message.mousePressEvent = lambda event: self.advance()
        self.battle_menu = MenuPanel(self)
        self.battle_menu.setFixedWidth(430)
        self.battle_menu.hide()
        self.bottom = QWidget()
        self.bottom.setFixedHeight(BOTTOM_HEIGHT)
        bottom_row = QHBoxLayout(self.bottom)
        bottom_row.setContentsMargins(10, 8, 10, 2)
        bottom_row.addWidget(self.message, 1)
        bottom_row.addWidget(self.battle_menu)
        self.bottom.hide()

        self.hints = QLabel(objectName="hints")
        self.menu_button = QPushButton("Menu (Esc)", objectName="small")
        self.menu_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.menu_button.clicked.connect(lambda: self.on_input(Command.CANCEL))
        self.menu_button.hide()
        hint_bar = QWidget()
        hint_bar.setFixedHeight(HINT_BAR_HEIGHT)
        hint_row = QHBoxLayout(hint_bar)
        hint_row.setContentsMargins(12, 2, 10, 8)
        hint_row.addWidget(self.hints, 1)
        hint_row.addWidget(self.menu_button)
        root = QVBoxLayout(self.window)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self.stack, 1)
        root.addWidget(self.bottom)
        root.addWidget(hint_bar)

        self.overlay = QWidget(self.window, objectName="overlay")
        self.overlay.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.overlay_menu = MenuPanel(self)
        self.overlay_menu.setFixedWidth(620)
        self.overlay_layout = QVBoxLayout(self.overlay)
        self.overlay_layout.addStretch(1)
        self.overlay_layout.addWidget(self.overlay_menu, 0, Qt.AlignmentFlag.AlignHCenter)
        self.overlay_layout.addStretch(1)
        self.overlay.hide()
        self.curtain = Curtain(self.window)
        self.window.resize(1040, 720)
        self.window.show()

    def _build_world_page(self):
        page = QWidget()
        map_column = QVBoxLayout()
        map_column.addWidget(self.area_name)
        map_column.addWidget(self.map, 0, Qt.AlignmentFlag.AlignCenter)
        map_column.addStretch(1)
        row = QHBoxLayout(page)
        row.setContentsMargins(6, 6, 6, 0)
        row.addLayout(map_column, 1)
        row.addWidget(self.team)
        return page

    # --- blokowanie kontrolera ---

    def _spin(self, ms=None):
        """Oddaje sterowanie Qt do czasu sygnału; kontroler stoi, okno działa."""
        self.loop = QEventLoop()
        if ms is not None:
            QTimer.singleShot(ms, self.loop.quit)
        self.loop.exec()
        if self.closed:
            raise QuitGame

    def _read(self):
        """Czeka na klawisz albo kliknięcie."""
        self.waiting = True
        self._spin()
        self.waiting = False
        return self.input

    def _animate(self, ms, frame):
        """frame(t) dostaje postęp od 0 do 1; Enter przeskakuje do końca."""
        self.skip = False
        clock = QElapsedTimer()
        clock.start()
        while self.animated and not self.skip and clock.elapsed() < ms:
            frame(clock.elapsed() / ms)
            self._spin(FRAME_MS)
        frame(1.0)

    def on_input(self, value):
        self.skip = self.skip or value is Command.CONFIRM
        if self.waiting:
            self.input = value
            self.loop.quit()

    def advance(self):
        """Kliknięcie tła przewija tekst, ale nie może zatwierdzić opcji w otwartym menu."""
        if not self.menu_open:
            self.on_input(Command.CONFIRM)

    def on_close(self):
        self.closed = True
        if self.loop:
            self.loop.quit()

    # --- port IGameView ---

    def apply_settings(self, settings):
        self.settings, self.theme = settings, THEMES[settings["theme"]]
        self.animated = settings["animations"] == "on"
        self.chars_per_second, self.hold_ms = TEXT_SPEEDS[settings["text_speed"]]
        self.window.setStyleSheet(stylesheet(self.theme))
        self.title_page.reload()
        self.arena.reload()
        self.team.update()

    def _switch_page(self, page):
        self.bottom.setVisible(page is not self.title_page)
        self.battle_menu.setVisible(page is self.arena)
        self.menu_button.setVisible(page is self.world_page)
        if self.stack.currentWidget() is page:
            return
        self.stack.setCurrentWidget(page)
        self.curtain.show()
        self.curtain.raise_()
        self._animate(300, lambda t: self.curtain.set_alpha(255 * (1 - t)))
        self.curtain.hide()

    def show_title(self):
        self._switch_page(self.title_page)

    def show_world(self, world, team):
        self.map.show_area(world)
        self.team.team = team
        self.team.update()
        self.area_name.setText(world.area.name)
        self.message.clear()
        self._switch_page(self.world_page)

    def move_player(self, x, y):
        hero, start = self.map.hero, self.map.hero.pos()
        end = QPoint(x * TILE_SIZE, y * TILE_SIZE)
        self._animate(WALK_MS, lambda t: hero.move(start + (end - start) * t))

    def read_command(self):
        self.hints.setText("Strzałki lub klik: ruch | Wejdź w obiekt, żeby go użyć | Esc: menu")
        return self._read()

    def show_battle(self, battle, portrait):
        self.battle = battle
        self.message.clear()
        self.arena.reset(portrait)
        self._switch_page(self.arena)

    def _type(self, text):
        self._animate(len(text) * 1000 / self.chars_per_second,
                      lambda t: self.message.setText(text[:round(t * len(text))]))

    def say(self, text, wait=True):
        self._type(text)
        if wait:
            self.message.setText(text + "  ▼")
            self.hints.setText("Enter lub klik: dalej")
            while True:
                value = self._read()
                if value is Command.CONFIRM or isinstance(value, Click):
                    break
            self.message.clear()

    def play(self, event):
        if event.kind is EventKind.TEXT:
            self._type(event.text)
            self._animate(self.hold_ms, lambda t: None)
            return
        side = event.side
        fighter, box, creature = self.arena.fighters[side], self.arena.boxes[side], self.battle.active[side]
        direction = 1 if side == "player" else -1
        if event.kind is EventKind.SEND_OUT:
            box.set_creature(creature)
            self.arena.show_fighter(side, fighter_sprite(creature, side))
            self._animate(260, lambda t: fighter.pose(opacity=t))
        elif event.kind is EventKind.ATTACK:
            self._animate(260, lambda t: fighter.pose(dx=direction * 46 * math.sin(math.pi * t)))
        elif event.kind is EventKind.HIT:
            self._animate(380, lambda t: fighter.pose(dx=14 * math.sin(t * 6 * math.pi) * (1 - t),
                                                      opacity=0.35 + 0.65 * abs(math.cos(t * 3 * math.pi))))
        elif event.kind is EventKind.HP:
            start = box.hp
            self._animate(700, lambda t: box.set_hp(start + (creature.hp - start) * t))
        elif event.kind is EventKind.STATUS:
            box.update()
        elif event.kind is EventKind.FAINT:
            self._animate(420, lambda t: fighter.pose(dy=90 * t, opacity=1 - t))
            fighter.hide()
            box.set_creature(None)

    def choose(self, menu):
        in_battle_box = menu.place == "battle"
        panel = self.battle_menu if in_battle_box else self.overlay_menu
        panel.show_menu(menu)
        if not in_battle_box:
            shade = "transparent" if menu.place == "title" else "rgba(0, 0, 0, 90)"
            self.overlay.setStyleSheet(f"#overlay {{ background: {shade}; }}")
            self.overlay_layout.setStretch(0, 3 if menu.place == "title" else 1)  # Na tytule menu nie zasłania gór.
            self.overlay.show()
            self.overlay.raise_()
        self.hints.setText("Strzałki: wybór | Enter: zatwierdź" + (" | Esc: wstecz" if menu.can_cancel else ""))
        self.menu_open = True
        self._spin(MENU_GUARD_MS)
        result = self._run_menu(menu, panel)
        self.menu_open = False
        panel.clear() if in_battle_box else self.overlay.hide()
        self.hints.setText("Enter lub klik: dalej")
        return result

    def _run_menu(self, menu, panel):
        while True:
            value = self._read()
            if isinstance(value, int):  # Kliknięta opcja.
                menu.cursor = value
                return value
            if value is Command.CONFIRM and menu.current.enabled:
                return menu.cursor
            if value is Command.CANCEL and menu.can_cancel:
                return None
            if isinstance(value, Command):
                panel.move_cursor_by_key(value)
