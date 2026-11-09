"""Testy logiki. Uruchomienie z głównego folderu: python -m unittest discover tests"""
import ast
import curses
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from adapters.json_repository import JsonRepository  # noqa: E402
from controller.game_controller import GameController  # noqa: E402
from adapters.sprites import fighter_sprite, load_sprite  # noqa: E402
from adapters.tui_view import MAX_COLOR_PAIRS, TuiView, ascii_cell  # noqa: E402
from core.battle_engine import BattleEngine  # noqa: E402
from core.damage_calculator import DamageCalculator  # noqa: E402
from core.entities import Battle, EventKind, GameState  # noqa: E402
from core.map_engine import MapEngine  # noqa: E402
from ports.interfaces import Command, IGameView, Menu, MenuItem, QuitGame  # noqa: E402


class ScriptedView(IGameView):
    """Atrapa widoku: dowód, że cała gra działa wyłącznie przez port."""

    def __init__(self, picks=(), commands=()):
        self.picks, self.commands = list(picks), list(commands)
        self.said, self.events = [], []

    def apply_settings(self, settings): pass
    def show_title(self): pass
    def show_world(self, world, team): pass
    def move_player(self, x, y): pass
    def show_battle(self, battle, portrait): pass
    def play(self, event): self.events.append(event)
    def say(self, text, wait=True): self.said.append(text)

    def choose(self, menu):
        if not self.picks:
            raise QuitGame
        return self.picks.pop(0)

    def read_command(self):
        if not self.commands:
            raise QuitGame
        return self.commands.pop(0)


class AutoPlayView(ScriptedView):
    """Zawsze wybiera pierwszą dostępną opcję, więc potrafi rozegrać całą walkę."""

    def choose(self, menu):
        return next(index for index, item in enumerate(menu.items) if item.enabled)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = JsonRepository(save_path=Path(self.tmp.name) / "save.json")
        self.content = self.repo.load_content()

    def battle(self, randomness=0.0):
        team = [self.content.make_creature("meganium", 50)]
        rivals = [self.content.make_creature("typhlosion", 50)]
        return Battle(team, rivals, {"hyper_potion": 1}, randomness)

    def duel(self, player, enemy, level=80, seed=1):
        """Walka jeden na jednego, od razu po wysłaniu Pokémonów."""
        battle = Battle([self.content.make_creature(player, level)], [self.content.make_creature(enemy, level)], {}, 0.0)
        engine = BattleEngine(rng=random.Random(seed))
        list(engine.start(battle))
        return battle, engine

    def world(self, area="foot", x=8, y=12):
        return MapEngine(self.content.areas, GameState(area=area, x=x, y=y))


class DamageTests(Base):
    def test_type_chart_changes_damage(self):
        grass, fire = self.content.make_creature("meganium", 50), self.content.make_creature("typhlosion", 50)
        calculator, move = DamageCalculator(), self.content.moves["flamethrower"]
        self.assertEqual(calculator.multiplier("fire", grass), 2.0)
        self.assertEqual(calculator.multiplier("grass", fire), 0.5)
        self.assertGreater(calculator.damage(fire, grass, move), calculator.damage(fire, fire, move))

    def test_two_types_multiply(self):
        charizard = self.content.make_creature("charizard", 50)
        calculator = DamageCalculator()
        self.assertEqual(calculator.multiplier("rock", charizard), 4.0)
        self.assertEqual(calculator.multiplier("ground", charizard), 0.0)

    def test_special_move_uses_special_stats(self):
        espeon = self.content.make_creature("espeon", 50)
        snorlax = self.content.make_creature("snorlax", 50)
        calculator = DamageCalculator()
        self.assertGreater(calculator.damage(espeon, snorlax, self.content.moves["psychic"]),
                           calculator.damage(espeon, snorlax, self.content.moves["swift"]))

    def test_burn_halves_physical_attack(self):
        attacker, target = self.content.make_creature("heracross", 50), self.content.make_creature("snorlax", 50)
        move, calculator = self.content.moves["megahorn"], DamageCalculator()
        healthy = calculator.damage(attacker, target, move)
        attacker.status = "burn"
        self.assertLess(calculator.damage(attacker, target, move), healthy)

    def test_critical_hit_is_stronger(self):
        a, b = self.content.make_creature("tyranitar", 50), self.content.make_creature("espeon", 50)
        move, calculator = self.content.moves["stone-edge"], DamageCalculator()
        self.assertGreater(calculator.damage(a, b, move, critical=True), calculator.damage(a, b, move))


class BattleTests(Base):
    def test_turn_spends_pp_and_reports_in_order(self):
        battle, engine = self.battle(), BattleEngine(rng=random.Random(1))
        list(engine.start(battle))
        move = battle.player.moves[0]
        kinds = [event.kind for event in engine.take_turn(battle, ("move", move))]
        self.assertEqual(battle.player.pp[move.id], move.pp - 1)
        self.assertEqual(battle.turns, 1)
        self.assertIn(EventKind.ATTACK, kinds)

    def test_model_matches_screen_at_every_event(self):
        """Generator zatrzymuje się na każdym zdarzeniu, więc HP w zdarzeniu HIT jest już po ciosie."""
        battle, engine = self.battle(), BattleEngine(rng=random.Random(2))
        list(engine.start(battle))
        start_hp = battle.player.hp
        for event in engine.take_turn(battle, ("move", battle.player.moves[1])):
            if event.kind is EventKind.HIT and event.side == "player":
                self.assertLess(battle.player.hp, start_hp)
                break

    def test_battle_always_ends(self):
        for seed in range(30):
            battle, engine = self.battle(0.3), BattleEngine(rng=random.Random(seed))
            list(engine.start(battle))
            for _ in range(200):
                if battle.outcome:
                    break
                list(engine.take_turn(battle, ("move", (battle.player.usable_moves or battle.player.moves)[0])))
            self.assertIn(battle.outcome, ("win", "lose"))

    def test_item_uses_turn_and_heals(self):
        battle, engine = self.battle(), BattleEngine(rng=random.Random(3))
        list(engine.start(battle))
        item = self.content.items["hyper_potion"]
        battle.player.hp = 10
        self.assertTrue(battle.player.can_use(item))
        kinds = [event.kind for event in engine.take_turn(battle, ("item", item, 0))]
        self.assertEqual(battle.bag["hyper_potion"], 0)
        self.assertEqual(kinds.count(EventKind.ATTACK), 1)  # Atakuje tylko przeciwnik.

    def test_immune_target_takes_no_damage(self):
        battle, engine = self.duel("heracross", "charizard")
        hp_before = battle.enemy.hp
        events = list(engine._attack(battle, "player", self.content.moves["earthquake"]))
        self.assertEqual(battle.enemy.hp, hp_before)
        self.assertTrue(any("Nie działa" in event.text for event in events))

    def test_recoil_hurts_attacker(self):
        battle, engine = self.duel("ho-oh", "snorlax")
        hp_before = battle.player.hp
        list(engine._attack(battle, "player", self.content.moves["brave-bird"]))
        self.assertLess(battle.player.hp, hp_before)

    def test_recharge_skips_next_turn(self):
        battle, engine = self.duel("blastoise", "snorlax", seed=3)
        move = self.content.moves["hydro-cannon"]
        for _ in range(20):
            list(engine._attack(battle, "player", move))
            if battle.player.recharging:
                break
        self.assertTrue(battle.player.recharging)
        events = list(engine._attack(battle, "player", move))
        self.assertFalse(battle.player.recharging)
        self.assertTrue(any("odpocząć" in event.text for event in events))

    def test_sleep_blocks_until_waking_up(self):
        battle, engine = self.duel("espeon", "snorlax")
        battle.player.status, battle.player.sleep_turns = "sleep", 2
        move = self.content.moves["psychic"]
        self.assertFalse(any(e.kind is EventKind.ATTACK for e in engine._attack(battle, "player", move)))
        self.assertTrue(any(e.kind is EventKind.ATTACK for e in engine._attack(battle, "player", move)))
        self.assertEqual(battle.player.status, "")

    def test_paralysis_quarters_speed(self):
        creature = self.content.make_creature("pikachu", 80)
        speed = creature.speed
        creature.status = "paralysis"
        self.assertEqual(creature.speed, speed // 4)

    def test_priority_beats_speed(self):
        battle, engine = self.duel("snorlax", "pikachu")
        quick, slow = self.content.moves["quick-attack"], self.content.moves["crunch"]
        order = engine._attack_order(battle, ("move", quick), slow)
        self.assertEqual(order[0][0], "player")

    def test_hail_spares_ice_types(self):
        battle, engine = self.duel("lapras", "snorlax")
        lapras_hp, snorlax_hp = battle.player.hp, battle.enemy.hp
        list(engine._hail(battle))
        self.assertEqual(battle.player.hp, lapras_hp)
        self.assertLess(battle.enemy.hp, snorlax_hp)

    def test_full_restore_and_ether(self):
        creature = self.content.make_creature("espeon", 76)
        full_restore, ether = self.content.items["full_restore"], self.content.items["ether"]
        creature.hp, creature.status = 1, "burn"
        creature.use(full_restore)
        self.assertEqual((creature.hp, creature.status), (creature.max_hp, ""))
        self.assertFalse(creature.can_use(ether))
        move = creature.moves[0]
        creature.pp[move.id] = 1
        self.assertTrue(creature.can_use(ether))
        creature.use(ether)
        self.assertEqual(creature.pp[move.id], min(move.pp, 11))


class MapTests(Base):
    def test_rows_have_equal_width_and_objects_lead_somewhere(self):
        for area in self.content.areas.values():
            self.assertEqual({len(row) for row in area.rows}, {26})
            self.assertEqual(len(area.rows), 15)
            for found in area.objects.values():
                if found.kind == "exit":
                    self.assertIn(found.target, self.content.areas)

    def test_bumping_into_object_does_not_move_player(self):
        world = self.world(x=4, y=11)
        found = world.move("up")
        self.assertEqual(found.kind, "heal")
        self.assertEqual(world.position, (4, 11))

    def test_walls_block(self):
        world = self.world(x=1, y=5)
        self.assertIsNone(world.move("left"))
        self.assertEqual(world.position, (1, 5))

    def test_path_finding_reaches_object(self):
        world = self.world(x=8, y=12)
        route = world.path_to(4, 10)
        for direction in route[:-1]:
            self.assertIsNone(world.move(direction))
        self.assertEqual(world.move(route[-1]).kind, "heal")

    def test_every_exit_is_reachable(self):
        for area_id, area in self.content.areas.items():
            start = next(found.spawn for other in self.content.areas.values() for found in other.objects.values()
                         if found.kind == "exit" and found.target == area_id)
            world = self.world(area_id, *start)
            for (x, y), found in area.objects.items():
                self.assertTrue(world.path_to(x, y), f"{area_id}: {found.kind} {x},{y}")


class SaveTests(Base):
    def test_round_trip_keeps_progress(self):
        team = [self.content.make_creature("feraligatr", 50)]
        team[0].hp, team[0].status, team[0].sleep_turns = 42, "sleep", 2
        self.repo.save_game(GameState(team=team, bag={"hyper_potion": 2}, area="summit", x=3, y=4, collected={"foot:4:4"}))
        loaded = self.repo.load_game(self.content)
        self.assertEqual((loaded.team[0].hp, loaded.team[0].status, loaded.team[0].sleep_turns), (42, "sleep", 2))
        self.assertEqual((loaded.area, loaded.x, loaded.collected), ("summit", 3, {"foot:4:4"}))

    def test_broken_save_is_ignored(self):
        self.repo.save_path.write_text("{ to nie jest json", encoding="utf-8")
        self.assertIsNone(self.repo.load_game(self.content))


class ControllerTests(Base):
    def test_new_game_walk_and_quit_saves_progress(self):
        view = ScriptedView(picks=[0, 1], commands=[Command.LEFT, Command.LEFT])  # Nowa gra, Feraligatr.
        GameController(view, self.repo, BattleEngine(rng=random.Random(1))).run()
        saved = json.loads(self.repo.save_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["team"][0]["species"], "feraligatr")
        self.assertEqual(len(saved["team"]), 6)
        self.assertEqual((saved["x"], saved["y"]), (6, 12))
        self.assertEqual(saved["stats"]["steps"], 2)

    def test_quitting_mid_battle_keeps_pre_battle_save(self):
        view = ScriptedView(picks=[0, 0])  # WALKA, pierwszy ruch; koniec wyborów przerywa walkę.
        controller = GameController(view, self.repo, BattleEngine(rng=random.Random(1)))
        typhlosion = self.content.make_creature("typhlosion", 50)
        controller.state.team.append(typhlosion)
        full_hp = typhlosion.max_hp
        boss = next(found for found in self.content.areas["summit"].objects.values() if found.kind == "boss")
        with self.assertRaises(QuitGame):
            controller._fight_boss(boss)
        controller._save()
        saved = json.loads(self.repo.save_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["team"][0]["hp"], full_hp)
        self.assertEqual(saved["team"][0]["pp"]["flamethrower"], self.content.moves["flamethrower"].pp)


class FullFightTests(Base):
    def test_whole_fight_with_red_ends_on_a_result(self):
        for seed in range(5):
            controller = GameController(AutoPlayView(), self.repo, BattleEngine(rng=random.Random(seed)))
            content = self.content
            controller.state.team = [content.make_creature(*entry) for entry in [content.starters[seed % 3], *content.companions]]
            controller.state.bag = dict(content.start_bag)
            boss = next(found for found in content.areas["summit"].objects.values() if found.kind == "boss")
            stats = controller.state.stats
            before = stats["wins"] + stats["losses"]
            controller._fight_boss(boss)
            self.assertEqual(stats["wins"] + stats["losses"], before + 1)
            self.assertFalse(controller.in_battle)

    def test_switch_menu_starts_on_a_healthy_pokemon(self):
        menus = []

        class Recording(ScriptedView):
            def choose(self, menu):
                menus.append(menu)
                return menu.cursor

        controller = GameController(Recording(), self.repo, BattleEngine(rng=random.Random(1)))
        team = [self.content.make_creature("espeon", 50), self.content.make_creature("ampharos", 50)]
        team[0].hp = 0
        battle = Battle(team, [self.content.make_creature("pikachu", 50)], {}, 0.0, active={"player": team[0]})
        self.assertEqual(controller._choose_fighter(battle, forced=True), 1)


class ContentTests(Base):
    def test_red_has_his_heartgold_team(self):
        levels = {species: level for species, level in self.content.boss_team}
        self.assertEqual(levels, {"pikachu": 88, "lapras": 80, "snorlax": 82,
                                  "venusaur": 84, "charizard": 84, "blastoise": 84})

    def test_new_game_gives_a_team_of_six(self):
        self.assertEqual(len(self.content.starters), 3)
        self.assertEqual(len(self.content.companions), 5)

    def test_every_fighter_has_64x64_sprites(self):
        team = [*self.content.starters, *self.content.companions]
        sprites = ["red"]
        for species, level in self.content.boss_team:
            sprites.append(species)
        for species, level in team:
            creature = self.content.make_creature(species, level)
            sprites += [species, fighter_sprite(creature, "player")]
        for name in sprites:
            rows = load_sprite(name)
            self.assertEqual((len(rows), len(rows[0])), (64, 64), name)


class TerminalColorTests(unittest.TestCase):
    PAPER, YELLOW, BLACK = (238, 238, 238), (250, 220, 60), (20, 20, 20)

    def test_colored_cell_has_no_ascii_glyph(self):
        self.assertEqual(ascii_cell(self.YELLOW, self.YELLOW, self.PAPER), (" ", self.YELLOW, self.YELLOW))

    def test_dark_outline_wins_inside_a_cell(self):
        self.assertEqual(ascii_cell(self.YELLOW, self.BLACK, self.PAPER)[2], self.BLACK)

    def test_half_transparent_cell_keeps_a_glyph_on_paper(self):
        char, foreground, background = ascii_cell(None, self.YELLOW, self.PAPER)
        self.assertNotEqual(char, " ")
        self.assertEqual((foreground, background), (self.YELLOW, self.PAPER))

    def test_color_pairs_never_exceed_what_curses_can_store(self):
        view = TuiView.__new__(TuiView)
        view.pairs = {}
        with mock.patch.object(curses, "COLORS", 256, create=True), \
                mock.patch.object(curses, "init_pair") as init_pair, \
                mock.patch.object(curses, "color_pair", lambda number: number << 8):
            for red in range(0, 256, 8):
                for green in range(0, 256, 8):
                    view._attr((red, green, 0), (0, 0, red))
        self.assertLessEqual(max(call.args[0] for call in init_pair.call_args_list), MAX_COLOR_PAIRS)


class MenuTests(unittest.TestCase):
    def test_cursor_wraps_and_respects_columns(self):
        menu = Menu("", [MenuItem(str(i)) for i in range(4)], columns=2)
        menu.move_cursor(Command.RIGHT)
        self.assertEqual(menu.cursor, 1)
        menu.move_cursor(Command.DOWN)
        self.assertEqual(menu.cursor, 3)
        menu.move_cursor(Command.DOWN)
        self.assertEqual(menu.cursor, 1)

    def test_left_and_right_stay_in_the_same_row(self):
        menu = Menu("", [MenuItem(str(i)) for i in range(4)], columns=2, cursor=1)
        menu.move_cursor(Command.RIGHT)
        self.assertEqual(menu.cursor, 0)
        menu.move_cursor(Command.LEFT)
        self.assertEqual(menu.cursor, 1)
        menu.cursor = 2
        menu.move_cursor(Command.LEFT)
        self.assertEqual(menu.cursor, 3)

    def test_left_and_right_do_nothing_in_a_single_column(self):
        menu = Menu("", [MenuItem(str(i)) for i in range(3)], cursor=1)
        menu.move_cursor(Command.RIGHT)
        self.assertEqual(menu.cursor, 1)

    def test_odd_last_row_keeps_the_cursor_on_a_real_item(self):
        menu = Menu("", [MenuItem(str(i)) for i in range(3)], columns=2, cursor=2)
        menu.move_cursor(Command.RIGHT)
        self.assertEqual(menu.cursor, 2)


class ArchitectureTests(unittest.TestCase):
    def imports(self, path):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                yield from (alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                yield node.module

    def test_core_knows_nothing_about_the_outside(self):
        for path in (ROOT / "core").glob("*.py"):
            for name in self.imports(path):
                self.assertFalse(name.startswith(("adapters", "controller", "ports", "curses", "PySide6")), f"{path}: {name}")

    def test_controller_and_ports_do_not_import_adapters(self):
        for path in [*(ROOT / "controller").glob("*.py"), *(ROOT / "ports").glob("*.py")]:
            for name in self.imports(path):
                self.assertFalse(name.startswith(("adapters", "curses", "PySide6")), f"{path}: {name}")


if __name__ == "__main__":
    unittest.main()
