"""Mt. Silver: walka z Redem. Uruchomienie: python main.py (terminal) albo python main.py --gui (okno)."""
import curses
import locale
import sys

from adapters.json_repository import JsonRepository
from controller.game_controller import GameController
from core.battle_engine import BattleEngine


def start(view) -> None:
    GameController(view=view, repository=JsonRepository(), engine=BattleEngine()).run()


def run_tui(stdscr: "curses.window") -> None:
    from adapters.tui_view import TuiView
    start(TuiView(stdscr))


def run_gui() -> None:
    from adapters.gui_view import GuiView
    start(GuiView())


if __name__ == "__main__":
    if "--gui" in sys.argv:
        run_gui()
    else:
        locale.setlocale(locale.LC_ALL, "")
        curses.set_escdelay(25)  # Bez tego Esc reaguje z sekundowym opóźnieniem.
        curses.wrapper(run_tui)
