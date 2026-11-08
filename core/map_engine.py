from typing import List, Optional
from core.entities import MapEntity, Player, Boss


class MapEngine:
    def __init__(self, width: int = 20, height: int = 12, entities: Optional[List[MapEntity]] = None):
        self.width = width
        self.height = height
        self.entities: List[MapEntity] = entities or []

    def isWalkable(self, x: float, y: float) -> bool:
        if x < 1 or x >= self.width - 1 or y < 1 or y >= self.height - 1:
            return False
        for entity in self.entities:
            if isinstance(entity, Boss) and entity.posX == x and entity.posY == y:
                return False
        return True

    def movePlayer(self, player: Player, dx: int, dy: int) -> bool:
        new_x = player.posX + dx
        new_y = player.posY + dy
        if self.isWalkable(new_x, new_y):
            player.posX = new_x
            player.posY = new_y
            return True
        return False

    def checkBossInteraction(self, player: Player) -> Optional[Boss]:
        # Sprawdza, czy gracz stoi na polu bezpośrednio sąsiadującym z niepokonanym Bossem
        for entity in self.entities:
            if isinstance(entity, Boss) and not entity.defeated:
                dist = abs(player.posX - entity.posX) + abs(player.posY - entity.posY)
                if dist <= 1.0:
                    return entity
        return None