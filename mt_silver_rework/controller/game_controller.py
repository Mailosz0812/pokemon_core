"""Kontroler: scenariusz gry czytany od góry do dołu.

Rozmawia z widokiem tylko przez port IGameView, więc nie wie, czy gra działa w terminalu, czy w oknie.
"""
from core.battle_engine import LAST_RESORT
from core.entities import STATUS_NAMES, TYPE_NAMES, Battle, GameState
from core.map_engine import MapEngine
from ports.interfaces import Click, Command, Menu, MenuItem, QuitGame

WALK = {Command.UP: "up", Command.DOWN: "down", Command.LEFT: "left", Command.RIGHT: "right"}
DIFFICULTY = {"easy": (-8, 0.6), "normal": (0, 0.3), "hard": (0, 0.0)}  # Zmiana poziomu Reda i losowość ataków.
SETTINGS = {
    "text_speed": ("Szybkość tekstu", {"slow": "wolna", "normal": "normalna", "fast": "szybka"}),
    "difficulty": ("Poziom trudności", {"easy": "łatwy", "normal": "normalny", "hard": "trudny"}),
    "animations": ("Animacje", {"on": "włączone", "off": "wyłączone"}),
    "theme": ("Motyw kolorów", {"snow": "śnieg", "night": "noc"}),
    "graphics": ("Grafika w terminalu", {"ascii": "ASCII", "blocks": "półbloki"}),
}
HELP = ["Strzałki: chodzenie i wybór w menu",
        "Enter lub spacja: zatwierdzenie, przyspieszenie tekstu",
        "Esc: menu albo powrót",
        "Wejdź w obiekt, żeby go użyć.",
        "W oknie działa też mysz: kliknij pole mapy albo opcję menu.",
        "Cel: przejdź przez jaskinię na szczyt i pokonaj Reda."]


class GameController:
    def __init__(self, view, repository, engine):
        self.view, self.repository, self.engine = view, repository, engine
        self.content = repository.load_content()
        self.state = repository.load_game(self.content) or GameState()
        self.world = MapEngine(self.content.areas, self.state)
        self.in_world = self.in_battle = False

    def run(self):
        try:
            self.view.apply_settings(self.state.settings)
            self._title()
        except (QuitGame, KeyboardInterrupt):
            self._save()

    def _save(self):
        """Walki nie zapisujemy: po wyjściu wraca się do stanu sprzed niej."""
        if not self.in_battle:
            self.repository.save_game(self.state)

    def _quit(self):
        raise QuitGame

    # --- menu ---

    def _open(self, menu):
        """Pokazuje menu i wykonuje akcję wybranej opcji. Zwraca False po wycofaniu się."""
        index = self.view.choose(menu)
        if index is not None and menu.items[index].action:
            menu.items[index].action()
        return index is not None

    def _confirm(self, question, warning):
        return self.view.choose(Menu(question, [MenuItem("Tak"), MenuItem("Nie")], lines=[warning])) == 0

    def _info(self, title, lines):
        self.view.choose(Menu(title, [MenuItem("Wróć")], lines=lines))

    def _title(self):
        while True:
            self.view.show_title()
            items = [MenuItem("Kontynuuj", self._explore)] if self.state.team else []
            items += [MenuItem("Nowa gra", self._new_game), MenuItem("Ustawienia", self._settings),
                      MenuItem("Statystyki", self._stats), MenuItem("Sterowanie", self._help),
                      MenuItem("Wyjście", self._quit)]
            self._open(Menu("", items, place="title", can_cancel=False))

    def _new_game(self):
        if self.state.team and not self._confirm("Rozpocząć nową grę?", "Obecny zapis zostanie zastąpiony."):
            return
        starters = [self.content.make_creature(*entry) for entry in self.content.starters]
        items = [MenuItem(f"{creature.name} (Lv{creature.level})", detail=self._describe(creature),
                          sprite=creature.species.id) for creature in starters]
        index = self.view.choose(Menu("Wybierz startera", items))
        if index is None:
            return
        team = [starters[index], *(self.content.make_creature(*entry) for entry in self.content.companions)]
        area, x, y = self.content.start
        self.state = GameState(team=team, bag=dict(self.content.start_bag), area=area, x=x, y=y,
                               settings=self.state.settings)
        self.world = MapEngine(self.content.areas, self.state)
        self._save()
        self._explore()

    def _settings(self):
        def item(name):
            label, values = SETTINGS[name]
            return MenuItem(f"{label}: {values[self.state.settings[name]]}", lambda: self._cycle(name),
                            "Enter zmienia wartość.")
        cursor = 0
        while True:
            menu = Menu("Ustawienia", [item(name) for name in SETTINGS], cursor=cursor)
            if not self._open(menu):
                return
            cursor = menu.cursor

    def _cycle(self, name):
        values = list(SETTINGS[name][1])
        self.state.settings[name] = values[(values.index(self.state.settings[name]) + 1) % len(values)]
        self.view.apply_settings(self.state.settings)
        self._save()

    def _stats(self):
        stats = self.state.stats
        best = stats["best_turns"] or "jeszcze nie ma"
        self._info("Statystyki", [f"Wygrane z Redem: {stats['wins']}", f"Porażki: {stats['losses']}",
                                  f"Najmniej tur w wygranej: {best}", f"Przebyte kroki: {stats['steps']}"])

    def _help(self):
        self._info("Sterowanie", HELP)

    # --- mapa ---

    def _explore(self):
        self.view.show_world(self.world, self.state.team)
        self.in_world = True
        while self.in_world:
            command = self.view.read_command()
            if command is Command.CANCEL:
                self._pause()
            elif isinstance(command, Click):
                for direction in self.world.path_to(command.x, command.y):
                    self._step(direction)
            elif command in WALK:
                self._step(WALK[command])

    def _step(self, direction):
        before = self.world.position
        found = self.world.move(direction)
        if found:
            self._interact(found)
        elif self.world.position != before:
            self.state.stats["steps"] += 1
            self.view.move_player(*self.world.position)

    def _interact(self, found):
        if found.kind in ("sign", "npc"):
            self.view.say(found.text)
        elif found.kind == "heal":
            for creature in self.state.team:
                creature.restore()
            self._refresh_world("Pokécentrum: drużyna wyleczona!")
        elif found.kind == "item":
            self.state.bag[found.item] += 1
            self.world.collect(found)
            self._refresh_world(f"Znajdujesz: {self.content.items[found.item].name}!")
        elif found.kind == "exit":
            self.world.enter(found.target, *found.spawn)
            self._save()
            self.view.show_world(self.world, self.state.team)
        elif found.kind == "boss":
            self._fight_boss(found)

    def _refresh_world(self, text):
        self._save()
        self.view.show_world(self.world, self.state.team)
        self.view.say(text)

    def _pause(self):
        while self.in_world:
            items = [MenuItem("Drużyna", self._team), MenuItem("Plecak", self._bag),
                     MenuItem("Statystyki", self._stats), MenuItem("Ustawienia", self._settings),
                     MenuItem("Sterowanie", self._help), MenuItem("Zapisz grę", self._save_from_menu),
                     MenuItem("Menu główne", self._leave_world)]
            if not self._open(Menu("Menu", items)):
                return

    def _save_from_menu(self):
        self._save()
        self.view.say("Gra zapisana.")

    def _leave_world(self):
        self._save()
        self.in_world = False

    def _team(self):
        index = self.view.choose(Menu("Drużyna (Enter: wyślij jako pierwszego)", self._team_items(self.state.team)))
        if index is not None:
            self.state.team.insert(0, self.state.team.pop(index))
            self.view.show_world(self.world, self.state.team)

    def _bag(self):
        item = self._choose_item()
        target = item and self._choose_target(item)
        if target is None:
            return
        self.state.bag[item.id] -= 1
        self._refresh_world(self.state.team[target].use(item))

    # --- wspólne opisy i wybory ---

    @staticmethod
    def _describe(creature):
        moves = ", ".join(f"{move.name} {creature.pp[move.id]}/{move.pp}" for move in creature.moves)
        types = ", ".join(TYPE_NAMES[name] for name in creature.species.types)
        return f"Typ: {types}. Ataki: {moves}"

    def _team_items(self, team, is_enabled=lambda creature: True):
        def label(creature):
            status = "KO" if creature.fainted else STATUS_NAMES[creature.status]
            return f"{creature.name} Lv{creature.level}  HP {creature.hp}/{creature.max_hp} {status}".rstrip()
        return [MenuItem(label(creature), detail=self._describe(creature), enabled=is_enabled(creature),
                         sprite=creature.species.id) for creature in team]

    def _choose_item(self):
        ids = list(self.state.bag)
        items = [MenuItem(f"{self.content.items[key].name} x{self.state.bag[key]}",
                          detail=self.content.items[key].description, enabled=self.state.bag[key] > 0) for key in ids]
        index = self.view.choose(Menu("Plecak", items))
        return None if index is None else self.content.items[ids[index]]

    def _choose_target(self, item):
        return self.view.choose(Menu(f"Użyj: {item.name}", self._team_items(self.state.team, lambda c: c.can_use(item))))

    # --- walka ---

    def _fight_boss(self, found):
        if all(creature.fainted for creature in self.state.team):
            self.view.say("Twoje Pokémony nie mogą walczyć. Wróć do Pokécentrum.")
            return
        self._save()
        self.view.say(found.text)
        level_change, randomness = DIFFICULTY[self.state.settings["difficulty"]]
        rivals = [self.content.make_creature(key, level + level_change) for key, level in self.content.boss_team]
        battle = Battle(self.state.team, rivals, self.state.bag, randomness)
        self.in_battle = True
        self.view.show_battle(battle, "red")
        self._play(self.engine.start(battle))
        while not battle.outcome:
            if battle.must_switch:
                self._play(self.engine.forced_switch(battle, self._choose_fighter(battle, forced=True)))
                continue
            if battle.player.recharging:
                self._play(self.engine.take_turn(battle, ("move", None)))
                continue
            action = self._ask_action(battle)
            if action:
                self._play(self.engine.take_turn(battle, action))
        self._finish_battle(battle)

    def _play(self, events):
        for event in events:
            self.view.play(event)

    def _ask_action(self, battle):
        self.view.say(f"Co zrobi {battle.player.name}?", wait=False)
        labels = ("WALKA", "POKÉMON", "PLECAK", "PODDAJ SIĘ")
        handlers = (self._pick_move, self._pick_switch, self._pick_item, self._surrender)
        while not battle.outcome:
            menu = Menu("", [MenuItem(label) for label in labels], columns=2, place="battle", can_cancel=False)
            action = handlers[self.view.choose(menu)](battle)
            if action:
                return action
        return None

    def _pick_move(self, battle):
        creature = battle.player
        if not creature.usable_moves:
            return "move", LAST_RESORT
        items = [MenuItem(move.name, detail=f"{TYPE_NAMES[move.type]} | moc {move.power or '-'} | PP {creature.pp[move.id]}/{move.pp}",
                          enabled=creature.pp[move.id] > 0) for move in creature.moves]
        index = self.view.choose(Menu("", items, columns=2, place="battle"))
        return None if index is None else ("move", creature.moves[index])

    def _choose_fighter(self, battle, forced):
        items = self._team_items(battle.player_team, lambda c: not c.fainted and c is not battle.player)
        cursor = next((index for index, item in enumerate(items) if item.enabled), 0)
        return self.view.choose(Menu("Kogo wysłać?", items, can_cancel=not forced, cursor=cursor))

    def _pick_switch(self, battle):
        index = self._choose_fighter(battle, forced=False)
        return None if index is None else ("switch", index)

    def _pick_item(self, battle):
        item = self._choose_item()
        target = item and self._choose_target(item)
        return None if target is None else ("item", item, target)

    def _surrender(self, battle):
        if self._confirm("Poddać się?", "Walka zakończy się porażką."):
            self.engine.surrender(battle)

    def _finish_battle(self, battle):
        self.in_battle = False
        stats = self.state.stats
        if battle.outcome == "win":
            stats["wins"] += 1
            stats["best_turns"] = min(stats["best_turns"] or battle.turns, battle.turns)
            title, lines = "Zwycięstwo!", [f"Red pokonany w {battle.turns} tur.", "Red kiwa głową i dalej milczy."]
        else:
            stats["losses"] += 1
            for creature in self.state.team:
                creature.restore()
            self.world.enter(*self.content.start)
            title, lines = "Porażka", ["Drużyna wraca wyleczona do Pokécentrum.", "Przedmioty użyte w walce nie wracają."]
        self._save()
        self.view.choose(Menu(title, [MenuItem("Dalej")], lines=lines, can_cancel=False))
        self.view.show_world(self.world, self.state.team)
