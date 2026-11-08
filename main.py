import sys
import curses
from core.battle_engine import BattleEngine
from core.map_engine import MapEngine
from adapters.json_repository import JsonFileRepository
from controller.game_controller import GameController


def run_tui(stdscr: "curses.window") -> None:
    from adapters.tui_view import TuiGameBoyView
    view = TuiGameBoyView(stdscr)
    controller = GameController(
        battleEngine=BattleEngine(),
        mapEngine=MapEngine(),
        view=view,
        repository=JsonFileRepository(),
    )
    controller.startGameLoop()


def run_gui() -> None:
    from adapters.gui_view import GuiGbaView
    view = GuiGbaView()
    controller = GameController(
        battleEngine=BattleEngine(),
        mapEngine=MapEngine(),
        view=view,
        repository=JsonFileRepository(),
    )
    controller.startGameLoop()


if __name__ == "__main__":
    if "--gui" in sys.argv:
        run_gui()
    else:
        # Na systemie Windows wymagana jest paczka: pip install windows-curses
        curses.wrapper(run_tui)