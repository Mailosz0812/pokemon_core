"""Świat gry: chodzenie po mapie, obiekty i wyszukiwanie trasy."""
from collections import deque

DIRECTIONS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
WALKABLE = set(",.:*-")  # trawa, ścieżka, jaskinia, śnieg, lód


class MapEngine:
    def __init__(self, areas, state):
        self.areas, self.state = areas, state

    area = property(lambda self: self.areas[self.state.area])
    position = property(lambda self: (self.state.x, self.state.y))

    def tile_at(self, x, y):
        return self.area.floor if (x, y) in self.area.objects else self.area.rows[y][x]

    def object_at(self, x, y):
        found = self.area.objects.get((x, y))
        return None if found and found.key in self.state.collected else found

    def move(self, direction):
        """Krok gracza. Wejście w obiekt nie przesuwa gracza, tylko zwraca ten obiekt."""
        dx, dy = DIRECTIONS[direction]
        x, y = self.state.x + dx, self.state.y + dy
        found = self.object_at(x, y)
        if found is None and self.tile_at(x, y) in WALKABLE:
            self.state.x, self.state.y = x, y
        return found

    def enter(self, area, x, y):
        self.state.area, self.state.x, self.state.y = area, x, y

    def collect(self, found):
        self.state.collected.add(found.key)

    def path_to(self, x, y):
        """Najkrótsza trasa do pola (BFS). Do obiektu można tylko dojść i w niego wejść."""
        start, goal = self.position, (x, y)
        came_from = {start: None}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            if current == goal:
                return self._rebuild_route(came_from, goal)
            for direction, (dx, dy) in DIRECTIONS.items():
                step = current[0] + dx, current[1] + dy
                free = step == goal or (self.tile_at(*step) in WALKABLE and self.object_at(*step) is None)
                if step not in came_from and free:
                    came_from[step] = current, direction
                    queue.append(step)
        return []

    @staticmethod
    def _rebuild_route(came_from, goal):
        route, current = [], goal
        while came_from[current]:
            current, direction = came_from[current]
            route.append(direction)
        return route[::-1]
