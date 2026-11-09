"""Porty: kontrakty między logiką a światem zewnętrznym (ekranem i plikami)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Optional


class QuitGame(Exception):
    """Gracz zamknął okno albo terminal."""


class Command(Enum):
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()
    CONFIRM = auto()
    CANCEL = auto()


@dataclass(frozen=True)
class Click:
    """Kliknięcie pola mapy (tylko tryb graficzny)."""
    x: int
    y: int


@dataclass
class MenuItem:
    label: str
    action: Optional[Callable] = None
    detail: str = ""
    enabled: bool = True
    sprite: str = ""


@dataclass
class Menu:
    title: str
    items: list
    columns: int = 1
    place: str = "center"  # center, title albo battle
    can_cancel: bool = True
    lines: list = field(default_factory=list)
    cursor: int = 0

    @property
    def current(self):
        return self.items[self.cursor]

    def move_cursor(self, command):
        """Góra i dół zmieniają wiersz, a lewo i prawo poruszają się tylko w obrębie wiersza."""
        if command in (Command.UP, Command.DOWN):
            step = -self.columns if command is Command.UP else self.columns
            self.cursor = (self.cursor + step) % len(self.items)
        elif command in (Command.LEFT, Command.RIGHT):
            row_start = self.cursor - self.cursor % self.columns
            row_length = min(self.columns, len(self.items) - row_start)
            step = -1 if command is Command.LEFT else 1
            self.cursor = row_start + (self.cursor - row_start + step) % row_length


class IGameView(ABC):
    """Metody blokują: wracają dopiero, gdy animacja się skończy albo gracz odpowie."""

    @abstractmethod
    def apply_settings(self, settings): ...

    @abstractmethod
    def show_title(self): ...

    @abstractmethod
    def show_world(self, world, team): ...

    @abstractmethod
    def move_player(self, x, y):
        """Przesuwa tylko postać gracza; reszta mapy zostaje nietknięta."""

    @abstractmethod
    def show_battle(self, battle, portrait): ...

    @abstractmethod
    def play(self, event):
        """Pokazuje jedno zdarzenie walki."""

    @abstractmethod
    def say(self, text, wait=True): ...

    @abstractmethod
    def choose(self, menu):
        """Zwraca indeks wybranej opcji albo None, gdy gracz się wycofał."""

    @abstractmethod
    def read_command(self):
        """Zwraca Command albo Click."""


class IDataRepository(ABC):
    @abstractmethod
    def load_content(self): ...

    @abstractmethod
    def load_game(self, content):
        """Zwraca GameState albo None, gdy nie ma zapisu lub jest uszkodzony."""

    @abstractmethod
    def save_game(self, state): ...
