"""Encje gry: czyste dane i proste reguły. Nic o ekranie ani o plikach."""
from dataclasses import dataclass, field
from enum import Enum, auto

STATUS_NAMES = {"paralysis": "PAR", "sleep": "SEN", "freeze": "LÓD", "burn": "OPA", "poison": "TRU", "": ""}
TYPE_NAMES = {
    "normal": "normalny", "fire": "ogień", "water": "woda", "electric": "elektryczny",
    "grass": "trawa", "ice": "lód", "fighting": "walka", "poison": "trucizna",
    "ground": "ziemia", "flying": "latający", "psychic": "psychiczny", "bug": "robak",
    "rock": "skała", "ghost": "duch", "dragon": "smok", "dark": "mrok", "steel": "stal",
}
PERFECT_IV = 31
DEFAULT_SETTINGS = {"text_speed": "normal", "difficulty": "normal", "animations": "on",
                    "theme": "snow", "graphics": "ascii"}


class EventKind(Enum):
    TEXT = auto()
    SEND_OUT = auto()
    ATTACK = auto()
    HIT = auto()
    HP = auto()
    STATUS = auto()
    FAINT = auto()


@dataclass(frozen=True)
class Event:
    """Coś, co wydarzyło się w walce. Każdy widok pokazuje to po swojemu."""
    kind: EventKind
    side: str = ""
    text: str = ""


@dataclass(frozen=True)
class Move:
    id: str
    name: str
    type: str
    category: str  # physical, special albo status
    power: int
    accuracy: int | None  # None oznacza, że atak zawsze trafia.
    pp: int
    priority: int = 0
    drain: int = 0  # Procent zadanych obrażeń: dodatni leczy, ujemny to odrzut.
    status: str = ""
    status_chance: int = 0


@dataclass(frozen=True)
class Species:
    id: str
    name: str
    types: tuple
    hp: int
    attack: int
    defense: int
    sp_attack: int
    sp_defense: int
    speed: int
    moves: tuple


@dataclass(frozen=True)
class Item:
    id: str
    name: str
    description: str
    heal: int = 0
    cures: bool = False
    revive: bool = False
    pp: int = 0


@dataclass
class Creature:
    species: Species
    level: int
    moves: list
    hp: int = None
    pp: dict = field(default_factory=dict)
    status: str = ""
    sleep_turns: int = 0
    recharging: bool = False

    def __post_init__(self):
        if self.hp is None:
            self.hp = self.max_hp
        self.pp = self.pp or {move.id: move.pp for move in self.moves}

    def _stat(self, base):
        return (2 * base + PERFECT_IV) * self.level // 100 + 5

    name = property(lambda self: self.species.name)
    max_hp = property(lambda self: (2 * self.species.hp + PERFECT_IV) * self.level // 100 + self.level + 10)
    attack = property(lambda self: self._stat(self.species.attack))
    defense = property(lambda self: self._stat(self.species.defense))
    sp_attack = property(lambda self: self._stat(self.species.sp_attack))
    sp_defense = property(lambda self: self._stat(self.species.sp_defense))
    speed = property(lambda self: self._stat(self.species.speed) // (4 if self.status == "paralysis" else 1))
    fainted = property(lambda self: self.hp <= 0)
    usable_moves = property(lambda self: [move for move in self.moves if self.pp[move.id] > 0])

    def clear_status(self):
        self.status, self.sleep_turns = "", 0

    def restore(self):
        self.hp = self.max_hp
        self.clear_status()
        self.pp = {move.id: move.pp for move in self.moves}

    def can_use(self, item):
        if item.revive or self.fainted:
            return item.revive and self.fainted
        missing_pp = any(self.pp[move.id] < move.pp for move in self.moves)
        return bool(item.heal and self.hp < self.max_hp or item.cures and self.status or item.pp and missing_pp)

    def use(self, item):
        """Zużywa przedmiot i zwraca opis efektu."""
        if item.revive:
            self.hp = self.max_hp // 2
            return f"{self.name} wraca do walki!"
        hp_before = self.hp
        self.hp = min(self.max_hp, self.hp + item.heal)
        if item.cures:
            self.clear_status()
        if item.pp:
            self.pp = {move.id: min(move.pp, self.pp[move.id] + item.pp) for move in self.moves}
            return f"{self.name} odzyskuje PP."
        if self.hp > hp_before:
            return f"{self.name} odzyskuje {self.hp - hp_before} HP."
        return f"{self.name} czuje się lepiej."


@dataclass
class Battle:
    player_team: list
    enemy_team: list
    bag: dict
    ai_randomness: float
    active: dict = field(default_factory=dict)
    outcome: str = ""  # "", "win" albo "lose"
    must_switch: bool = False
    turns: int = 0

    player = property(lambda self: self.active["player"])
    enemy = property(lambda self: self.active["enemy"])


@dataclass(frozen=True)
class MapObject:
    kind: str  # sign, npc, item, heal, exit, boss
    key: str  # Stały identyfikator: dzięki niemu pamiętamy zebrane przedmioty.
    text: str = ""
    item: str = ""
    target: str = ""
    spawn: tuple = ()


@dataclass(frozen=True)
class Area:
    name: str
    floor: str
    rows: tuple
    objects: dict  # (x, y) -> MapObject


@dataclass(frozen=True)
class Content:
    """Niezmienna treść gry wczytana z folderu data."""
    species: dict
    moves: dict
    items: dict
    areas: dict
    starters: list
    companions: list
    boss_team: list
    start_bag: dict
    start: tuple  # obszar, x, y

    def make_creature(self, species_id, level):
        species = self.species[species_id]
        return Creature(species, level, [self.moves[move] for move in species.moves])


@dataclass
class GameState:
    """Wszystko, co trafia do pliku zapisu."""
    team: list = field(default_factory=list)
    bag: dict = field(default_factory=dict)
    area: str = ""
    x: int = 0
    y: int = 0
    collected: set = field(default_factory=set)
    settings: dict = field(default_factory=lambda: dict(DEFAULT_SETTINGS))
    stats: dict = field(default_factory=lambda: {"wins": 0, "losses": 0, "steps": 0, "best_turns": None})
