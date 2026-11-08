import random
from core.entities import Pokemon, Move, AttackType, PokemonType, AttackCategory


class DamageCalculator:
    TYPE_CHART = {
        (AttackType.WATER, PokemonType.FIRE): 2.0,
        (AttackType.WATER, PokemonType.GROUND): 2.0,
        (AttackType.FIRE, PokemonType.ICE): 2.0,
        (AttackType.FIRE, PokemonType.WATER): 0.5,
        (AttackType.ELECTRIC, PokemonType.WATER): 2.0,
        (AttackType.ELECTRIC, PokemonType.GROUND): 0.0,
        (AttackType.GROUND, PokemonType.ELECTRIC): 2.0,
        (AttackType.GROUND, PokemonType.FIRE): 2.0,
        (AttackType.ICE, PokemonType.GROUND): 2.0,
        (AttackType.ICE, PokemonType.FIRE): 0.5,
        (AttackType.PSYCHIC, PokemonType.GHOST): 0.5,
        (AttackType.GHOST, PokemonType.PSYCHIC): 2.0,
        (AttackType.GHOST, PokemonType.GHOST): 2.0,
    }

    def getTypeEffectiveness(self, moveType: AttackType, defType: PokemonType) -> float:
        return self.TYPE_CHART.get((moveType, defType), 1.0)

    def isCriticalHit(self) -> bool:
        return random.random() < 0.0625

    def calculateDamage(self, attacker: Pokemon, defender: Pokemon, move: Move) -> float:
        if move.category == AttackCategory.STATUS or move.basePower <= 0:
            return 0.0

        if move.category == AttackCategory.PHYSICAL:
            atk = attacker.stats.attack
            dfn = defender.stats.defence
        else:
            atk = attacker.stats.spAttack
            dfn = defender.stats.spDefence

        base_damage = (((2 * attacker.level / 5 + 2) * move.basePower * (atk / max(1.0, dfn))) / 50) + 2

        stab = 1.5 if move.type.value == attacker.type.value else 1.0
        effectiveness = self.getTypeEffectiveness(move.type, defender.type)
        random_factor = random.uniform(0.85, 1.0)

        return round(base_damage * stab * effectiveness * random_factor, 1)