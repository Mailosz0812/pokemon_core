"""Wzór na obrażenia i tabela typów."""

# Typ ataku: (przeciw czemu jest silny, przeciw czemu jest słaby, na co nie działa).
CHART = {
    "normal": (set(), {"rock", "steel"}, {"ghost"}),
    "fighting": ({"dark", "ice", "normal", "rock", "steel"}, {"bug", "flying", "poison", "psychic"}, {"ghost"}),
    "flying": ({"bug", "fighting", "grass"}, {"electric", "rock", "steel"}, set()),
    "poison": ({"grass"}, {"ghost", "ground", "poison", "rock"}, {"steel"}),
    "ground": ({"electric", "fire", "poison", "rock", "steel"}, {"bug", "grass"}, {"flying"}),
    "rock": ({"bug", "fire", "flying", "ice"}, {"fighting", "ground", "steel"}, set()),
    "bug": ({"dark", "grass", "psychic"}, {"fighting", "fire", "flying", "ghost", "poison", "steel"}, set()),
    "ghost": ({"ghost", "psychic"}, {"dark"}, {"normal"}),
    "steel": ({"ice", "rock"}, {"electric", "fire", "steel", "water"}, set()),
    "fire": ({"bug", "grass", "ice", "steel"}, {"dragon", "fire", "rock", "water"}, set()),
    "water": ({"fire", "ground", "rock"}, {"dragon", "grass", "water"}, set()),
    "grass": ({"ground", "rock", "water"}, {"bug", "dragon", "fire", "flying", "grass", "poison", "steel"}, set()),
    "electric": ({"flying", "water"}, {"dragon", "electric", "grass"}, {"ground"}),
    "psychic": ({"fighting", "poison"}, {"psychic", "steel"}, {"dark"}),
    "ice": ({"dragon", "flying", "grass", "ground"}, {"fire", "ice", "steel", "water"}, set()),
    "dragon": ({"dragon"}, {"steel"}, set()),
    "dark": ({"ghost", "psychic"}, {"dark", "fighting"}, set()),
}
CRITICAL_BONUS = 2
SAME_TYPE_BONUS = 1.5


class DamageCalculator:
    def multiplier(self, move_type, defender):
        strong, weak, immune = CHART[move_type]
        result = 1.0
        for defender_type in defender.species.types:
            result *= 0 if defender_type in immune else 2 if defender_type in strong else 0.5 if defender_type in weak else 1
        return result

    def damage(self, attacker, defender, move, roll=1.0, critical=False):
        """Uproszczony wzór z 4. generacji, bez zmian statystyk i zdolności."""
        if move.category == "physical":
            attack, defense = attacker.attack // 2 if attacker.status == "burn" else attacker.attack, defender.defense
        else:
            attack, defense = attacker.sp_attack, defender.sp_defense
        value = ((2 * attacker.level // 5 + 2) * move.power * attack // defense) // 50 + 2
        if critical:
            value *= CRITICAL_BONUS
        if move.type in attacker.species.types:
            value = int(value * SAME_TYPE_BONUS)
        return max(1, int(value * self.multiplier(move.type, defender) * roll))
