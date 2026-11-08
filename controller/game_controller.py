from core.battle_engine import BattleEngine
from core.map_engine import MapEngine
from core.entities import Boss
from ports.interfaces import IGameView, IDataRepository


class GameController:
    def __init__(
        self,
        battleEngine: BattleEngine,
        mapEngine: MapEngine,
        view: IGameView,
        repository: IDataRepository,
    ):
        self.battleEngine = battleEngine
        self.mapEngine = mapEngine
        self.view = view
        self.repository = repository
        self.player = self.repository.loadPlayer()
        self.bosses = self.repository.loadBosses()
        self.mapEngine.entities.extend(self.bosses)
        self.running = True

    def startGameLoop(self) -> None:
        self.view.renderMap(self.mapEngine, self.player)
        while self.running:
            self.updateMapExploration()

    def updateMapExploration(self) -> None:
        action = self.view.getMapInput()
        dx, dy = 0, 0
        if action == "UP":
            dy = -1
        elif action == "DOWN":
            dy = 1
        elif action == "LEFT":
            dx = -1
        elif action == "RIGHT":
            dx = 1
        elif action == "QUIT":
            self.repository.saveGameState(self.player)
            self.running = False
            return

        if dx != 0 or dy != 0:
            moved = self.mapEngine.movePlayer(self.player, dx, dy)
            if moved:
                self.view.renderMap(self.mapEngine, self.player)
                boss = self.mapEngine.checkBossInteraction(self.player)
                if boss and self.player.has_alive_pokemon():
                    self.runBattleLoop(boss)
                    self.view.renderMap(self.mapEngine, self.player)

    def runBattleLoop(self, boss: Boss) -> None:
        self.view.showDialog(boss.preBattleDialog)
        state = self.battleEngine.startBattle(self.player, boss)
        self.view.renderBattleDiff(state)

        while not state.isFinished:
            selected_move = self.view.getBattleMoveSelection(state.activePlayerPokemon.moves)
            self.battleEngine.executeTurn(state, selected_move)
            self.view.renderBattleDiff(state)

        if boss.defeated:
            self.view.showDialog(boss.defeatDialog)
        else:
            self.view.showDialog("Uciekasz do Pokemon Center, aby uleczyć drużynę...")
            for p in self.player.pokemons:
                p.hpNow = p.hpMax