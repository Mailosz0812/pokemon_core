import json
import os
from typing import List
from ports.interfaces import IDataRepository
from core.entities import (
    Player, Boss, Pokemon, Move, Statistics,
    PokemonType, AttackType, AttackCategory, AttackProfile
)


class JsonFileRepository(IDataRepository):
    def __init__(self, filePath: str = "game_data.json"):
        self.filePath = filePath
        if not os.path.exists(self.filePath):
            self._create_default_data()

    def _create_default_data(self) -> None:
        default_data = {
            "player": {
                "name": "Ash",
                "spriteId": "player_gb",
                "posX": 3,
                "posY": 6,
                "pokemons": [
                    {
                        "name": "Pikachu",
                        "spriteId": "pikachu",
                        "level": 80,
                        "hpNow": 190.0,
                        "hpMax": 190.0,
                        "type": "electric",
                        "stats": {"attack": 130, "defence": 95, "spAttack": 145, "spDefence": 110, "speed": 180},
                        "moves": [
                            {"moveName": "Thunderbolt", "basePower": 90, "type": "electric", "category": "special", "accuracy": 100},
                            {"moveName": "Quick Attack", "basePower": 40, "type": "electric", "category": "physical", "accuracy": 100},
                            {"moveName": "Surf", "basePower": 90, "type": "water", "category": "special", "accuracy": 100},
                            {"moveName": "Agility", "basePower": 0, "type": "psychic", "category": "status", "accuracy": 100}
                        ]
                    },
                    {
                        "name": "Charizard",
                        "spriteId": "charizard",
                        "level": 82,
                        "hpNow": 250.0,
                        "hpMax": 250.0,
                        "type": "fire",
                        "stats": {"attack": 155, "defence": 140, "spAttack": 185, "spDefence": 150, "speed": 165},
                        "moves": [
                            {"moveName": "Flamethrower", "basePower": 90, "type": "fire", "category": "special", "accuracy": 100},
                            {"moveName": "Earthquake", "basePower": 100, "type": "ground", "category": "physical", "accuracy": 100},
                            {"moveName": "Fire Blast", "basePower": 110, "type": "fire", "category": "special", "accuracy": 85}
                        ]
                    }
                ]
            },
            "bosses": [
                {
                    "name": "Elite Four Lorelei",
                    "spriteId": "boss_lorelei",
                    "posX": 10,
                    "posY": 4,
                    "preBattleDialog": "Lorelei: Nikt nie przetrwa starcia z moimi lodowymi Pokemonami!",
                    "defeatDialog": "Lorelei: Niesamowite... Roztopiłeś moją obronę!",
                    "attackProfile": "medium",
                    "pokemons": [
                        {
                            "name": "Lapras",
                            "spriteId": "lapras",
                            "level": 78,
                            "hpNow": 280.0,
                            "hpMax": 280.0,
                            "type": "ice",
                            "stats": {"attack": 140, "defence": 145, "spAttack": 155, "spDefence": 165, "speed": 115},
                            "moves": [
                                {"moveName": "Ice Beam", "basePower": 90, "type": "ice", "category": "special", "accuracy": 100},
                                {"moveName": "Hydro Pump", "basePower": 110, "type": "water", "category": "special", "accuracy": 80}
                            ]
                        }
                    ]
                },
                {
                    "name": "Champion Red",
                    "spriteId": "boss_red",
                    "posX": 16,
                    "posY": 6,
                    "preBattleDialog": "Red: ... ... ... !",
                    "defeatDialog": "Red: ... ... ...",
                    "attackProfile": "aggresive",
                    "pokemons": [
                        {
                            "name": "Blastoise",
                            "spriteId": "blastoise",
                            "level": 84,
                            "hpNow": 265.0,
                            "hpMax": 265.0,
                            "type": "water",
                            "stats": {"attack": 150, "defence": 180, "spAttack": 160, "spDefence": 185, "speed": 140},
                            "moves": [
                                {"moveName": "Hydro Cannon", "basePower": 110, "type": "water", "category": "special", "accuracy": 90},
                                {"moveName": "Ice Beam", "basePower": 90, "type": "ice", "category": "special", "accuracy": 100},
                                {"moveName": "Earthquake", "basePower": 100, "type": "ground", "category": "physical", "accuracy": 100}
                            ]
                        }
                    ]
                }
            ]
        }
        with open(self.filePath, "w", encoding="utf-8") as f:
            json.dump(default_data, f, indent=2, ensure_ascii=False)

    def _parse_pokemon(self, data: dict) -> Pokemon:
        moves = [
            Move(
                moveName=m["moveName"],
                basePower=float(m["basePower"]),
                type=AttackType(m["type"]),
                category=AttackCategory(m["category"]),
                accuracy=float(m["accuracy"]),
            )
            for m in data["moves"]
        ]
        st = data["stats"]
        return Pokemon(
            spriteId=data["spriteId"],
            name=data["name"],
            level=int(data["level"]),
            hpNow=float(data["hpNow"]),
            hpMax=float(data["hpMax"]),
            type=PokemonType(data["type"]),
            stats=Statistics(
                attack=float(st["attack"]),
                defence=float(st["defence"]),
                spAttack=float(st["spAttack"]),
                spDefence=float(st["spDefence"]),
                speed=float(st["speed"]),
            ),
            moves=moves,
        )

    def loadPlayer(self) -> Player:
        with open(self.filePath, "r", encoding="utf-8") as f:
            raw = json.load(f)["player"]
        return Player(
            spriteId=raw["spriteId"],
            posX=float(raw["posX"]),
            posY=float(raw["posY"]),
            name=raw["name"],
            pokemons=[self._parse_pokemon(p) for p in raw["pokemons"]],
        )

    def loadBosses(self) -> List[Boss]:
        with open(self.filePath, "r", encoding="utf-8") as f:
            raw_bosses = json.load(f)["bosses"]
        bosses = []
        for b in raw_bosses:
            bosses.append(
                Boss(
                    spriteId=b["spriteId"],
                    posX=float(b["posX"]),
                    posY=float(b["posY"]),
                    name=b["name"],
                    preBattleDialog=b["preBattleDialog"],
                    defeatDialog=b["defeatDialog"],
                    attackProfile=AttackProfile(b["attackProfile"]),
                    pokemons=[self._parse_pokemon(p) for p in b["pokemons"]],
                )
            )
        return bosses

    def saveGameState(self, player: Player) -> None:
        with open(self.filePath, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["player"]["posX"] = player.posX
        data["player"]["posY"] = player.posY
        with open(self.filePath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)