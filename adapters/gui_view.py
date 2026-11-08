import tkinter as tk
from typing import List, Dict, Any
from ports.interfaces import IGameView
from core.entities import Player, Boss, BattleState, Move
from core.map_engine import MapEngine


class GuiGbaView(IGameView):
    SPRITE_COLORS = {
        "pikachu": "#FFD700",
        "charizard": "#FF5722",
        "lapras": "#00BCD4",
        "blastoise": "#2196F3",
    }

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Pokémon GBA Edition (GUI View)")
        self.root.geometry("680x520")
        self.root.configure(bg="#2b2b36")

        self.canvas = tk.Canvas(self.root, width=640, height=360, bg="#a8d8a0", highlightthickness=2)
        self.canvas.pack(pady=10)

        self.controls_frame = tk.Frame(self.root, bg="#2b2b36")
        self.controls_frame.pack(fill=tk.BOTH, expand=True, padx=20)

        self._input_var = tk.StringVar()
        self._move_index_var = tk.IntVar()
        self._mode = None  # "MAP" lub "BATTLE"
        self._map_ids: Dict[str, int] = {}
        self._battle_ids: Dict[str, int] = {}
        self._prev_hp: Dict[str, float] = {}

        self.root.bind("<Up>", lambda e: self._input_var.set("UP"))
        self.root.bind("<Down>", lambda e: self._input_var.set("DOWN"))
        self.root.bind("<Left>", lambda e: self._input_var.set("LEFT"))
        self.root.bind("<Right>", lambda e: self._input_var.set("RIGHT"))
        self.root.protocol("WM_DELETE_WINDOW", lambda: self._input_var.set("QUIT"))

    def renderMap(self, map_engine: MapEngine, player: Player) -> None:
        tile_w = 640 // map_engine.width
        tile_h = 360 // map_engine.height

        if self._mode != "MAP":
            self.canvas.delete("all")
            self._map_ids.clear()
            self._mode = "MAP"
            # Rysowanie statycznej siatki mapy tylko raz
            for y in range(map_engine.height):
                for x in range(map_engine.width):
                    color = "#3e6b48" if (x in (0, map_engine.width - 1) or y in (0, map_engine.height - 1)) else "#a8d8a0"
                    self.canvas.create_rectangle(
                        x * tile_w, y * tile_h, (x + 1) * tile_w, (y + 1) * tile_h,
                        fill=color, outline="#90c088"
                    )
            for idx, entity in enumerate(map_engine.entities):
                if isinstance(entity, Boss):
                    bx, by = entity.posX * tile_w, entity.posY * tile_h
                    cid = self.canvas.create_oval(bx + 4, by + 4, bx + tile_w - 4, by + tile_h - 4, fill="#e53935", width=2)
                    self._map_ids[f"boss_{idx}"] = cid

            px, py = player.posX * tile_w, player.posY * tile_h
            self._map_ids["player"] = self.canvas.create_oval(
                px + 4, py + 4, px + tile_w - 4, py + tile_h - 4, fill="#1e88e5", outline="white", width=2
            )

        # Diff Update: przesuwamy wyłącznie obiekt gracza zamiast przerysowywać całą mapę
        px, py = player.posX * tile_w, player.posY * tile_h
        self.canvas.coords(self._map_ids["player"], px + 4, py + 4, px + tile_w - 4, py + tile_h - 4)

        for idx, entity in enumerate(map_engine.entities):
            if isinstance(entity, Boss) and entity.defeated:
                self.canvas.itemconfigure(self._map_ids[f"boss_{idx}"], fill="#757575")

        self.root.update()

    def renderBattleDiff(self, state: BattleState) -> None:
        p_poke = state.activePlayerPokemon
        e_poke = state.activeEnemy

        if self._mode != "BATTLE":
            self.canvas.delete("all")
            self._battle_ids.clear()
            self._mode = "BATTLE"
            self.canvas.configure(bg="#e8f5e9")

            # Statyczne tło areny GBA
            self.canvas.create_oval(380, 110, 600, 170, fill="#a5d6a7", outline="#81c784", width=3)
            self.canvas.create_oval(40, 230, 280, 300, fill="#a5d6a7", outline="#81c784", width=3)

            # Dynamiczne elementy cachowane po ID
            self._battle_ids["e_sprite"] = self.canvas.create_oval(440, 40, 540, 140, fill="#ccc", width=3)
            self._battle_ids["p_sprite"] = self.canvas.create_oval(100, 160, 210, 270, fill="#ccc", width=3)

            self._battle_ids["e_text"] = self.canvas.create_text(40, 30, anchor="nw", font=("Consolas", 13, "bold"))
            self.canvas.create_rectangle(40, 55, 240, 72, fill="#cfd8dc", outline="#37474f")
            self._battle_ids["e_hp_bar"] = self.canvas.create_rectangle(40, 55, 240, 72, fill="#4caf50")

            self._battle_ids["p_text"] = self.canvas.create_text(350, 190, anchor="nw", font=("Consolas", 13, "bold"))
            self.canvas.create_rectangle(350, 215, 550, 232, fill="#cfd8dc", outline="#37474f")
            self._battle_ids["p_hp_bar"] = self.canvas.create_rectangle(350, 215, 550, 232, fill="#4caf50")

            self.canvas.create_rectangle(10, 280, 630, 355, fill="#263238", outline="#cfd8dc", width=3)
            self._battle_ids["log_text"] = self.canvas.create_text(
                25, 290, anchor="nw", fill="white", font=("Consolas", 11)
            )
            self._prev_hp = {"enemy": e_poke.hpMax, "player": p_poke.hpMax}

        # Odświeżanie wyłącznie zmienionych właściwości i płynna animacja paska HP
        self.canvas.itemconfigure(self._battle_ids["e_sprite"], fill=self.SPRITE_COLORS.get(e_poke.spriteId, "#ff8a65"))
        self.canvas.itemconfigure(self._battle_ids["p_sprite"], fill=self.SPRITE_COLORS.get(p_poke.spriteId, "#ffd54f"))

        self.canvas.itemconfigure(self._battle_ids["e_text"], text=f"{e_poke.name} Lv.{e_poke.level} ({e_poke.hpNow}/{e_poke.hpMax})")
        self.canvas.itemconfigure(self._battle_ids["p_text"], text=f"{p_poke.name} Lv.{p_poke.level} ({p_poke.hpNow}/{p_poke.hpMax})")

        self._animate_hp_bar(self._battle_ids["e_hp_bar"], 40, 55, 72, self._prev_hp.get("enemy", e_poke.hpNow), e_poke.hpNow, e_poke.hpMax)
        self._animate_hp_bar(self._battle_ids["p_hp_bar"], 350, 215, 232, self._prev_hp.get("player", p_poke.hpNow), p_poke.hpNow, p_poke.hpMax)
        self._prev_hp["enemy"] = e_poke.hpNow
        self._prev_hp["player"] = p_poke.hpNow

        self.canvas.itemconfigure(self._battle_ids["log_text"], text="\n".join(state.battleLog[-3:]))
        self.root.update()

    def _animate_hp_bar(self, rect_id: int, x0: int, y0: int, y1: int, start_hp: float, end_hp: float, max_hp: float) -> None:
        steps = 10
        for step in range(1, steps + 1):
            curr = start_hp + (end_hp - start_hp) * (step / steps)
            ratio = max(0.0, curr / max(1.0, max_hp))
            color = "#4caf50" if ratio > 0.5 else ("#ffb300" if ratio > 0.2 else "#e53935")
            self.canvas.coords(rect_id, x0, y0, x0 + int(200 * ratio), y1)
            self.canvas.itemconfigure(rect_id, fill=color)
            self.root.update()
            self.root.after(15)

    def showDialog(self, text: str) -> None:
        for w in self.controls_frame.winfo_children():
            w.destroy()
        lbl = tk.Label(self.controls_frame, text=text, fg="white", bg="#2b2b36", font=("Consolas", 12, "bold"), wraplength=600)
        lbl.pack(pady=10)
        cont_var = tk.BooleanVar()
        btn = tk.Button(self.controls_frame, text="Kontynuuj (Enter / Klik)", command=lambda: cont_var.set(True), bg="#4caf50", fg="white", font=("Consolas", 11, "bold"))
        btn.pack()
        self.root.bind("<Return>", lambda e: cont_var.set(True))
        self.root.wait_variable(cont_var)
        self.root.unbind("<Return>")

    def getMapInput(self) -> str:
        for w in self.controls_frame.winfo_children():
            w.destroy()
        info = tk.Label(self.controls_frame, text="Sterowanie: Strzałki na klawiaturze lub przyciski myszką", fg="#b0bec5", bg="#2b2b36")
        info.pack(pady=4)
        btn_frame = tk.Frame(self.controls_frame, bg="#2b2b36")
        btn_frame.pack()
        for label, cmd in [("⬆ Góra", "UP"), ("⬇ Dół", "DOWN"), ("⬅ Lewo", "LEFT"), ("➡ Prawo", "RIGHT"), ("Wyjdź", "QUIT")]:
            tk.Button(btn_frame, text=label, width=10, command=lambda c=cmd: self._input_var.set(c)).pack(side=tk.LEFT, padx=4)

        self.root.wait_variable(self._input_var)
        return self._input_var.get()

    def getBattleMoveSelection(self, moves: List[Move]) -> Move:
        for w in self.controls_frame.winfo_children():
            w.destroy()
        grid = tk.Frame(self.controls_frame, bg="#2b2b36")
        grid.pack(pady=5)
        for idx, m in enumerate(moves):
            btn = tk.Button(
                grid,
                text=f"{m.moveName} ({m.type.value.upper()} | Moc: {int(m.basePower)})",
                width=32,
                height=2,
                bg="#37474f",
                fg="white",
                font=("Consolas", 10, "bold"),
                command=lambda i=idx: self._move_index_var.set(i),
            )
            btn.grid(row=idx // 2, column=idx % 2, padx=6, pady=4)

        self.root.wait_variable(self._move_index_var)
        return moves[self._move_index_var.get()]