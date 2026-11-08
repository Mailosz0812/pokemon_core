import random
from typing import Optional
from core.entities import (
    BattleState, Player, Boss, Trainer, Pokemon, Move, AttackProfile, AttackCategory
)
from core.damage_calculator import DamageCalculator


class BattleEngine:
    def __init__(self, damageCalculator: Optional[DamageCalculator] = None):
        self.damageCalculator = damageCalculator or DamageCalculator()

    def startBattle(self, player: Player, boss: Boss) -> BattleState:
        state = BattleState(player=player, enemy=boss)
        state.battleLog.append(f"{boss.name} wyzywa Cię na pojedynek!")
        state.battleLog.append(
            f"{boss.name} wysyła {state.activeEnemy.name}! Ty wysyłasz {state.activePlayerPokemon.name}!"
        )
        return state

    def executeTurn(self, state: BattleState, playerMove: Move) -> None:
        if state.isFinished:
            return

        state.battleLog.clear()
        state.battleLog.append(f"--- Tura {state.turnCount} ---")

        boss_move = self.selectBossMove(state.enemy, state)

        player_first = state.activePlayerPokemon.stats.speed >= state.activeEnemy.stats.speed

        if player_first:
            self._perform_attack(state, state.activePlayerPokemon, state.activeEnemy, playerMove, is_player=True)
            if not state.isFinished and state.activeEnemy.is_alive:
                self._perform_attack(state, state.activeEnemy, state.activePlayerPokemon, boss_move, is_player=False)
        else:
            self._perform_attack(state, state.activeEnemy, state.activePlayerPokemon, boss_move, is_player=False)
            if not state.isFinished and state.activePlayerPokemon.is_alive:
                self._perform_attack(state, state.activePlayerPokemon, state.activeEnemy, playerMove, is_player=True)

        state.turnCount += 1

    def _perform_attack(
        self, state: BattleState, attacker: Pokemon, defender: Pokemon, move: Move, is_player: bool
    ) -> None:
        state.battleLog.append(f"{attacker.name} używa {move.moveName}!")

        if random.uniform(0, 100) > move.accuracy:
            state.battleLog.append(f"Atak {attacker.name} chybił!")
            return

        if move.category == AttackCategory.STATUS:
            attacker.stats.attack = round(attacker.stats.attack * 1.2, 1)
            state.battleLog.append(f"Atak {attacker.name} wzrósł!")
            return

        dmg = self.damageCalculator.calculateDamage(attacker, defender, move)
        if self.damageCalculator.isCriticalHit() and dmg > 0:
            dmg = round(dmg * 1.5, 1)
            state.battleLog.append("Trafienie krytyczne!")

        eff = self.damageCalculator.getTypeEffectiveness(move.type, defender.type)
        if eff > 1.0:
            state.battleLog.append("To jest super efektywne!")
        elif 0 < eff < 1.0:
            state.battleLog.append("To nie jest zbyt efektywne...")
        elif eff == 0.0:
            state.battleLog.append(f"Brak efektu na {defender.name}!")

        defender.hpNow = max(0.0, round(defender.hpNow - dmg, 1))
        state.battleLog.append(f"{defender.name} traci {dmg} HP!")

        if not defender.is_alive:
            state.battleLog.append(f"{defender.name} zemdlał!")
            self._handle_faint(state, is_player_fainted=not is_player)

    def _handle_faint(self, state: BattleState, is_player_fainted: bool) -> None:
        if is_player_fainted:
            next_poke = self.switchNextPokemon(state.player)
            if next_poke:
                state.activePlayerPokemon = next_poke
                state.battleLog.append(f"Wysyłasz do walki {next_poke.name}!")
            else:
                state.isFinished = True
                state.battleLog.append("Wszystkie Twoje Pokémony zemdlały! Przegrywasz walkę.")
        else:
            next_poke = self.switchNextPokemon(state.enemy)
            if next_poke:
                state.activeEnemy = next_poke
                state.battleLog.append(f"{state.enemy.name} wysyła {next_poke.name}!")
            else:
                state.isFinished = True
                state.enemy.defeated = True
                state.battleLog.append(f"Pokonałeś trenera {state.enemy.name}!")

    def selectBossMove(self, boss: Boss, state: BattleState) -> Move:
        moves = state.activeEnemy.moves
        if boss.attackProfile == AttackProfile.AGGRESSIVE:
            return max(
                moves,
                key=lambda m: self.damageCalculator.calculateDamage(
                    state.activeEnemy, state.activePlayerPokemon, m
                ),
            )
        elif boss.attackProfile == AttackProfile.MEDIUM:
            if random.random() < 0.5:
                return max(moves, key=lambda m: m.basePower)
            return random.choice(moves)
        else:
            return random.choice(moves)

    def switchNextPokemon(self, trainer: Trainer) -> Optional[Pokemon]:
        for poke in trainer.pokemons:
            if poke.is_alive:
                return poke
        return None