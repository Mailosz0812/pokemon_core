from dataclasses import dataclass, field
from enum import Enum
from typing import List


class PokemonType(Enum):
    GROUND = "ground"
    WATER = "water"
    FIRE = "fire"
    ELECTRIC = "electric"
    ICE = "ice"
    PSYCHIC = "psychic"
    GHOST = "ghost"


class AttackType(Enum):
    GROUND = "ground"
    WATER = "water"
    FIRE = "fire"
    ELECTRIC = "electric"
    ICE = "ice"
    PSYCHIC = "psychic"
    GHOST = "ghost"


class AttackCategory(Enum):
    PHYSICAL = "physical"
    SPECIAL = "special"
    STATUS = "status"


class AttackProfile(Enum):
    AGGRESSIVE = "aggresive"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Renderable:
    spriteId: str


@dataclass
class Statistics:
    attack: float
    defence: float
    spAttack: float
    spDefence: float
    speed: float


@dataclass
class Move:
    moveName: str
    basePower: float
    type: AttackType
    category: AttackCategory
    accuracy: float


@dataclass
class Pokemon(Renderable):
    name: str
    level: int
    hpNow: float
    hpMax: float
    type: PokemonType
    stats: Statistics
    moves: List[Move] = field(default_factory=list)

    @property
    def is_alive(self) -> bool:
        return self.hpNow > 0


@dataclass
class MapEntity(Renderable):
    posX: float = 0.0
    posY: float = 0.0


@dataclass
class Trainer(MapEntity):
    pokemons: List[Pokemon] = field(default_factory=list)

    def has_alive_pokemon(self) -> bool:
        return any(p.is_alive for p in self.pokemons)


@dataclass
class Player(Trainer):
    name: str = "Player"


@dataclass
class Boss(Trainer):
    name: str = "Boss"
    preBattleDialog: str = ""
    defeatDialog: str = ""
    attackProfile: AttackProfile = AttackProfile.AGGRESSIVE
    stats: Statistics = field(default_factory=lambda: Statistics(10, 10, 10, 10, 10))
    defeated: bool = False


@dataclass
class BattleState:
    player: Player
    enemy: Boss
    activePlayerPokemon: Pokemon = field(init=False)
    activeEnemy: Pokemon = field(init=False)
    turnCount: int = 1
    isFinished: bool = False
    battleLog: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.activePlayerPokemon = next(p for p in self.player.pokemons if p.is_alive)
        self.activeEnemy = next(p for p in self.enemy.pokemons if p.is_alive)