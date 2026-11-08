from abc import ABC, abstractmethod
from typing import List
from core.entities import Player, Boss, BattleState, Move
from core.map_engine import MapEngine


class IGameView(ABC):
    @abstractmethod
    def renderMap(self, map_engine: MapEngine, player: Player) -> None:
        pass

    @abstractmethod
    def renderBattleDiff(self, state: BattleState) -> None:
        """Odświeża wyłącznie te elementy widoku walki, które uległy zmianie."""
        pass

    @abstractmethod
    def showDialog(self, text: str) -> None:
        pass

    @abstractmethod
    def getMapInput(self) -> str:
        """Zwraca komendę kierunkową: 'UP', 'DOWN', 'LEFT', 'RIGHT' lub 'QUIT'."""
        pass

    @abstractmethod
    def getBattleMoveSelection(self, moves: List[Move]) -> Move:
        """Pozwala wybrać ruch za pomocą strzałek/myszki."""
        pass


class IDataRepository(ABC):
    @abstractmethod
    def loadPlayer(self) -> Player:
        pass

    @abstractmethod
    def loadBosses(self) -> List[Boss]:
        pass

    @abstractmethod
    def saveGameState(self, player: Player) -> None:
        pass