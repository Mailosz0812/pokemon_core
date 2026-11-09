"""Odczyt treści gry z folderu data oraz zapis i odczyt postępu gracza."""
import json
from pathlib import Path

from core.entities import Area, Content, Creature, GameState, Item, MapObject, Move, Species
from ports.interfaces import IDataRepository

ROOT = Path(__file__).resolve().parent.parent


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_area(area_id, data):
    objects = {}
    for y, row in enumerate(data["rows"]):
        for x, char in enumerate(row):
            if char in data["objects"]:
                fields = dict(data["objects"][char])
                fields["spawn"] = tuple(fields.get("spawn", ()))
                objects[x, y] = MapObject(key=f"{area_id}:{x}:{y}", **fields)
    return Area(data["name"], data["floor"], tuple(data["rows"]), objects)


class JsonRepository(IDataRepository):
    def __init__(self, save_path=ROOT / "save.json", data_dir=ROOT / "data"):
        self.save_path, self.data_dir = Path(save_path), Path(data_dir)

    def load_content(self):
        moves = {key: Move(id=key, **value) for key, value in read_json(self.data_dir / "moves.json").items()}
        species = {key: Species(id=key, **{**value, "types": tuple(value["types"]), "moves": tuple(value["moves"])})
                   for key, value in read_json(self.data_dir / "creatures.json").items()}
        items = {key: Item(id=key, **value) for key, value in read_json(self.data_dir / "items.json").items()}
        areas = {key: build_area(key, value) for key, value in read_json(self.data_dir / "world.json").items()}
        setup = read_json(self.data_dir / "setup.json")
        return Content(species, moves, items, areas, setup["starters"], setup["companions"], setup["boss_team"],
                       setup["start_bag"], tuple(setup["start"]))

    def load_game(self, content):
        try:
            data = read_json(self.save_path)
            data["team"] = [self._restore(entry, content) for entry in data["team"]]
            data["collected"] = set(data["collected"])
            return GameState(**data)
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def save_game(self, state):
        data = {**vars(state), "team": [self._dump(creature) for creature in state.team],
                "collected": sorted(state.collected)}
        self.save_path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _dump(creature):
        return {"species": creature.species.id, "level": creature.level, "hp": creature.hp,
                "pp": creature.pp, "status": creature.status, "sleep_turns": creature.sleep_turns}

    @staticmethod
    def _restore(entry, content):
        species = content.species[entry["species"]]
        return Creature(species, entry["level"], [content.moves[move] for move in species.moves],
                        entry["hp"], entry["pp"], entry["status"], entry["sleep_turns"])
