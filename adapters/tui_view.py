import curses
from typing import List, Dict, Any
from ports.interfaces import IGameView
from core.entities import Player, Boss, BattleState, Move
from core.map_engine import MapEngine


class TuiGameBoyView(IGameView):
    ASCII_SPRITES: Dict[str, List[str]] = {
        "pikachu": [
            r" (\__/) ",
            r" (o^.^) ",
            r" z(_('')('')",
        ],
        "charizard": [
            r"  /\_/\  ",
            r" ( >🔥< ) ",
            r"  /| |\  ",
        ],
        "lapras": [
            r"   _~_   ",
            r" ~(o.o)~ ",
            r"  /___\  ",
        ],
        "blastoise": [
            r"  [===]  ",
            r" ( o_o ) ",
            r" /|___|\ ",
        ],
    }

    def __init__(self, stdscr: "curses.window"):
        self.stdscr = stdscr
        curses.curs_set(0)
        self.stdscr.keypad(True)
        curses.start_color()
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)   # Styl Game Boy (zielony)
        curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # Boss / UI
        curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_BLACK)    # Gracz

        # Cache stanu do inteligentnego odświeżania różnicowego (Diff Rendering)
        self._last_player_pos = None
        self._battle_initialized = False
        self._prev_battle_snapshot: Dict[str, Any] = {}

    def renderMap(self, map_engine: MapEngine, player: Player) -> None:
        self._battle_initialized = False
        # Jeśli mapa nie była jeszcze rysowana, narysuj obramowanie raz
        if self._last_player_pos is None:
            self.stdscr.erase()
            self.stdscr.addstr(0, 2, "=== POKEMON GAME BOY TUI (Strzalki: Ruch | Q: Wyjscie) ===", curses.color_pair(1) | curses.A_BOLD)
            for y in range(map_engine.height):
                for x in range(map_engine.width):
                    if x in (0, map_engine.width - 1) or y in (0, map_engine.height - 1):
                        self.stdscr.addstr(y + 2, x * 2 + 2, "##", curses.color_pair(1))
                    else:
                        self.stdscr.addstr(y + 2, x * 2 + 2, " .")

        # Wymaż wyłącznie starą pozycję gracza (Diff update)
        if self._last_player_pos:
            old_x, old_y = self._last_player_pos
            self.stdscr.addstr(int(old_y) + 2, int(old_x) * 2 + 2, " .")

        # Narysuj Bossów
        for entity in map_engine.entities:
            if isinstance(entity, Boss):
                symbol = "B!" if not entity.defeated else "xx"
                self.stdscr.addstr(int(entity.posY) + 2, int(entity.posX) * 2 + 2, symbol, curses.color_pair(2) | curses.A_BOLD)

        # Narysuj nową pozycję gracza
        self.stdscr.addstr(int(player.posY) + 2, int(player.posX) * 2 + 2, "@@", curses.color_pair(3) | curses.A_BOLD)
        self._last_player_pos = (player.posX, player.posY)
        self.stdscr.refresh()

    def _hp_bar(self, hp_now: float, hp_max: float, width: int = 16) -> str:
        filled = int((hp_now / max(1.0, hp_max)) * width)
        return "[" + "#" * filled + "-" * (width - filled) + f"] {hp_now}/{hp_max}"

    def renderBattleDiff(self, state: BattleState) -> None:
        self._last_player_pos = None
        if not self._battle_initialized:
            self.stdscr.erase()
            self.stdscr.addstr(0, 2, "================ EKRAN WALKI GAME BOY ================", curses.color_pair(1) | curses.A_BOLD)
            self._battle_initialized = True
            self._prev_battle_snapshot.clear()

        p_poke = state.activePlayerPokemon
        e_poke = state.activeEnemy

        # 1. Odśwież sekcję Przeciwnika tylko jeśli zmieniło się jego HP lub aktywny Pokemon
        enemy_key = (e_poke.name, e_poke.hpNow)
        if self._prev_battle_snapshot.get("enemy") != enemy_key:
            self.stdscr.move(2, 2)
            self.stdscr.clrtoeol()
            self.stdscr.addstr(2, 2, f"Przeciwnik: {e_poke.name} (Lv.{e_poke.level}) HP: {self._hp_bar(e_poke.hpNow, e_poke.hpMax)}", curses.color_pair(2))
            for idx, line in enumerate(self.ASCII_SPRITES.get(e_poke.spriteId, ["[SPRITE]"])):
                self.stdscr.move(3 + idx, 35)
                self.stdscr.clrtoeol()
                self.stdscr.addstr(3 + idx, 35, line, curses.color_pair(2))
            self._prev_battle_snapshot["enemy"] = enemy_key

        # 2. Odśwież sekcję Gracza tylko jeśli zmieniło się jego HP lub aktywny Pokemon
        player_key = (p_poke.name, p_poke.hpNow)
        if self._prev_battle_snapshot.get("player") != player_key:
            for idx, line in enumerate(self.ASCII_SPRITES.get(p_poke.spriteId, ["[SPRITE]"])):
                self.stdscr.move(7 + idx, 4)
                self.stdscr.clrtoeol()
                self.stdscr.addstr(7 + idx, 4, line, curses.color_pair(3))
            self.stdscr.move(10, 2)
            self.stdscr.clrtoeol()
            self.stdscr.addstr(10, 2, f"Twoj Pokemon: {p_poke.name} (Lv.{p_poke.level}) HP: {self._hp_bar(p_poke.hpNow, p_poke.hpMax)}", curses.color_pair(3))
            self._prev_battle_snapshot["player"] = player_key

        # 3. Odśwież logi walki
        for i in range(5):
            self.stdscr.move(12 + i, 2)
            self.stdscr.clrtoeol()
        for idx, log_line in enumerate(state.battleLog[-5:]):
            self.stdscr.addstr(12 + idx, 2, f"> {log_line}")

        self.stdscr.refresh()
        if state.battleLog:
            self.stdscr.addstr(18, 2, "[Nacisnij dowolny klawisz, aby kontynuowac...]", curses.A_DIM)
            self.stdscr.getch()
            self.stdscr.move(18, 2)
            self.stdscr.clrtoeol()

    def showDialog(self, text: str) -> None:
        self.stdscr.move(20, 2)
        self.stdscr.clrtoeol()
        self.stdscr.addstr(20, 2, f"DIALOG: {text} [Nacisnij klawisz]", curses.color_pair(2) | curses.A_BOLD)
        self.stdscr.refresh()
        self.stdscr.getch()
        self.stdscr.move(20, 2)
        self.stdscr.clrtoeol()

    def getMapInput(self) -> str:
        key = self.stdscr.getch()
        mapping = {
            curses.KEY_UP: "UP",
            curses.KEY_DOWN: "DOWN",
            curses.KEY_LEFT: "LEFT",
            curses.KEY_RIGHT: "RIGHT",
            ord("q"): "QUIT",
            ord("Q"): "QUIT",
        }
        return mapping.get(key, "")

    def getBattleMoveSelection(self, moves: List[Move]) -> Move:
        selected = 0
        while True:
            self.stdscr.addstr(18, 2, "Wybierz atak (Strzalki Gora/Dol + ENTER):", curses.color_pair(1) | curses.A_BOLD)
            for idx, m in enumerate(moves):
                prefix = "-> " if idx == selected else "   "
                attr = curses.A_REVERSE if idx == selected else curses.A_NORMAL
                self.stdscr.move(19 + idx, 4)
                self.stdscr.clrtoeol()
                self.stdscr.addstr(
                    19 + idx, 4,
                    f"{prefix}{m.moveName} (Moc:{int(m.basePower)} | Typ:{m.type.value} | Kat:{m.category.value})",
                    attr,
                )
            self.stdscr.refresh()

            key = self.stdscr.getch()
            if key == curses.KEY_UP:
                selected = (selected - 1) % len(moves)
            elif key == curses.KEY_DOWN:
                selected = (selected + 1) % len(moves)
            elif key in (curses.KEY_ENTER, 10, 13):
                for idx in range(len(moves) + 1):
                    self.stdscr.move(18 + idx, 2)
                    self.stdscr.clrtoeol()
                return moves[selected]