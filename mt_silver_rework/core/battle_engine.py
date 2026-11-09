"""Przebieg walki.

Metody są generatorami: każdy `yield` oddaje zdarzenie do pokazania, a model jest wtedy
dokładnie w takim stanie, jaki gracz widzi na ekranie. Silnik nie zna żadnego widoku.
"""
import random

from core.damage_calculator import DamageCalculator
from core.entities import Event, EventKind, Move

LAST_RESORT = Move("struggle", "Struggle", "normal", "physical", 50, None, 1)
OTHER_SIDE = {"player": "enemy", "enemy": "player"}
RECHARGE_MOVES = {"hydro-cannon", "blast-burn", "frenzy-plant", "giga-impact"}
ALWAYS_HITS_IN_HAIL = "blizzard"  # Na szczycie cały czas pada grad.
STATUS_IMMUNE_TYPES = {"burn": {"fire"}, "freeze": {"ice"}, "poison": {"poison", "steel"}}
HAIL_IMMUNE_TYPES = {"ice", "rock", "ground", "steel"}
STATUS_INFLICTED = {
    "paralysis": "{} ma paraliż!",
    "sleep": "{} zasypia!",
    "freeze": "{} zamarza!",
    "burn": "{} ma oparzenia!",
    "poison": "{} jest zatruty!",
}


def say(text):
    return Event(EventKind.TEXT, text=text)


def first_alive(team):
    return next((creature for creature in team if not creature.fainted), None)


class BattleEngine:
    def __init__(self, calculator=None, rng=None):
        self.calculator = calculator or DamageCalculator()
        self.rng = rng or random.Random()

    def start(self, battle):
        yield from self._send_out(battle, "enemy", first_alive(battle.enemy_team))
        yield from self._send_out(battle, "player", first_alive(battle.player_team))

    def take_turn(self, battle, action):
        """action: ("move", ruch lub None), ("switch", indeks) albo ("item", przedmiot, indeks)."""
        battle.turns += 1
        enemy_move = self._enemy_move(battle)
        if action[0] == "switch":
            yield from self._send_out(battle, "player", battle.player_team[action[1]])
        elif action[0] == "item":
            yield from self._use_item(battle, action[1], action[2])
        for side, move in self._attack_order(battle, action, enemy_move):
            yield from self._attack(battle, side, move)
        yield from self._end_turn(battle)

    def forced_switch(self, battle, index):
        battle.must_switch = False
        yield from self._send_out(battle, "player", battle.player_team[index])

    def surrender(self, battle):
        battle.outcome = "lose"

    # --- kolejność i decyzje Reda ---

    def _attack_order(self, battle, action, enemy_move):
        if action[0] != "move":
            return [("enemy", enemy_move)]
        player_move = action[1] or self._fallback_move(battle.player)

        def sort_key(entry):
            side, move = entry
            return move.priority, battle.active[side].speed, self.rng.random()

        return sorted([("player", player_move), ("enemy", enemy_move)], key=sort_key, reverse=True)

    @staticmethod
    def _fallback_move(creature):
        return creature.usable_moves[0] if creature.usable_moves else LAST_RESORT

    def _enemy_move(self, battle):
        usable = battle.enemy.usable_moves or [LAST_RESORT]
        if self.rng.random() < battle.ai_randomness:
            return self.rng.choice(usable)
        return max(usable, key=lambda move: self._move_score(battle, move))

    def _move_score(self, battle, move):
        if not move.power:
            return 70 if not battle.player.status else 0
        score = move.power * self.calculator.multiplier(move.type, battle.player)
        if move.type in battle.enemy.species.types:
            score *= 1.5
        score *= (move.accuracy or 100) / 100
        return score * 0.7 if move.id in RECHARGE_MOVES else score

    # --- pojedyncze akcje ---

    def _send_out(self, battle, side, creature):
        battle.active[side] = creature
        creature.recharging = False
        yield say(f"Naprzód, {creature.name}!" if side == "player" else f"Red wysyła: {creature.name}!")
        yield Event(EventKind.SEND_OUT, side)

    def _use_item(self, battle, item, index):
        battle.bag[item.id] -= 1
        creature = battle.player_team[index]
        text = creature.use(item)
        yield say(f"Używasz: {item.name}. {text}")
        if creature is battle.player:
            yield Event(EventKind.HP, "player")
            yield Event(EventKind.STATUS, "player")

    def _attack(self, battle, side, move):
        target_side = OTHER_SIDE[side]
        attacker, target = battle.active[side], battle.active[target_side]
        if attacker.fainted or target.fainted:
            return
        if attacker.recharging:
            attacker.recharging = False
            yield say(f"{attacker.name} musi odpocząć!")
            return
        blocked = yield from self._blocked_by_status(attacker, side)
        if blocked:
            return

        if attacker.pp.get(move.id, 0) > 0:
            attacker.pp[move.id] -= 1
        else:
            move = LAST_RESORT
        yield say(f"{attacker.name} używa: {move.name}!")
        yield Event(EventKind.ATTACK, side)

        if not self._hits(move):
            yield say("Pudło!")
            return
        if self.calculator.multiplier(move.type, target) == 0:
            yield say(f"Nie działa na: {target.name}...")
            return
        if move.power:
            yield from self._deal_damage(attacker, side, target, target_side, move)
            attacker.recharging = move.id in RECHARGE_MOVES
        yield from self._try_inflict(target, target_side, move)

    def _hits(self, move):
        if move.accuracy is None or move.id == ALWAYS_HITS_IN_HAIL:
            return True
        return self.rng.randint(1, 100) <= move.accuracy

    def _blocked_by_status(self, attacker, side):
        """Zwraca True, gdy status nie pozwala wykonać ruchu."""
        if attacker.status == "sleep":
            attacker.sleep_turns -= 1
            if attacker.sleep_turns > 0:
                yield say(f"{attacker.name} śpi.")
                return True
            attacker.clear_status()
            yield Event(EventKind.STATUS, side)
            yield say(f"{attacker.name} budzi się!")
        elif attacker.status == "freeze":
            if self.rng.randint(1, 5) > 1:
                yield say(f"{attacker.name} jest zamrożony!")
                return True
            attacker.clear_status()
            yield Event(EventKind.STATUS, side)
            yield say(f"{attacker.name} odmarza!")
        elif attacker.status == "paralysis" and self.rng.randint(1, 4) == 1:
            yield say(f"Paraliż! {attacker.name} nie może się ruszyć!")
            return True
        return False

    def _deal_damage(self, attacker, side, target, target_side, move):
        critical = self.rng.randint(1, 16) == 1
        roll = self.rng.randint(85, 100) / 100
        amount = min(target.hp, self.calculator.damage(attacker, target, move, roll, critical))
        target.hp -= amount
        yield Event(EventKind.HIT, target_side)
        yield Event(EventKind.HP, target_side)
        multiplier = self.calculator.multiplier(move.type, target)
        if critical:
            yield say("Trafienie krytyczne!")
        if multiplier > 1:
            yield say("To super skuteczne!")
        elif multiplier < 1:
            yield say("To mało skuteczne...")
        yield from self._report_faint(target, target_side)
        if move.drain < 0:
            attacker.hp = max(0, attacker.hp - max(1, amount * -move.drain // 100))
            yield Event(EventKind.HP, side)
            yield say(f"{attacker.name} obrywa odrzutem!")
            yield from self._report_faint(attacker, side)
        elif move.drain > 0 and not attacker.fainted:
            attacker.hp = min(attacker.max_hp, attacker.hp + max(1, amount * move.drain // 100))
            yield Event(EventKind.HP, side)
            yield say(f"{attacker.name} wysysa energię!")

    def _try_inflict(self, target, target_side, move):
        if not move.status or target.fainted:
            return
        if target.status:
            if not move.power:
                yield say("Nie ma efektu...")
            return
        if set(target.species.types) & STATUS_IMMUNE_TYPES.get(move.status, set()):
            return
        if self.rng.randint(1, 100) > move.status_chance:
            return
        target.status = move.status
        if move.status == "sleep":
            target.sleep_turns = self.rng.randint(2, 4)
        yield Event(EventKind.STATUS, target_side)
        yield say(STATUS_INFLICTED[move.status].format(target.name))

    def _report_faint(self, creature, side):
        if creature.fainted:
            yield Event(EventKind.FAINT, side)
            yield say(f"{creature.name} mdleje!")

    # --- koniec tury ---

    def _end_turn(self, battle):
        for side in ("player", "enemy"):
            creature = battle.active[side]
            if creature.status in ("burn", "poison") and not creature.fainted:
                creature.hp = max(0, creature.hp - max(1, creature.max_hp // 8))
                yield Event(EventKind.HP, side)
                yield say(f"{creature.name}: boli {'oparzenie' if creature.status == 'burn' else 'trucizna'}!")
                yield from self._report_faint(creature, side)
        yield from self._hail(battle)

        if first_alive(battle.player_team) is None:
            battle.outcome = "lose"
        elif first_alive(battle.enemy_team) is None:
            battle.outcome = "win"
        else:
            if battle.enemy.fainted:
                yield from self._send_out(battle, "enemy", first_alive(battle.enemy_team))
            battle.must_switch = battle.player.fainted

    def _hail(self, battle):
        hurt = [side for side, creature in battle.active.items()
                if not creature.fainted and not set(creature.species.types) & HAIL_IMMUNE_TYPES]
        for side in hurt:
            creature = battle.active[side]
            creature.hp = max(0, creature.hp - max(1, creature.max_hp // 16))
            yield Event(EventKind.HP, side)
        if hurt:
            yield say("Grad rani Pokémony!")
        for side in hurt:
            yield from self._report_faint(battle.active[side], side)
