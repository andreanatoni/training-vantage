#!/usr/bin/env python3
"""
Porzioni standard validate per ogni opzione del piano base.

Queste sono grammature realistiche testate che rispettano i vincoli
del piano base e raggiungono i target kcal per categoria.
"""

# Porzioni standard per COLAZIONE (circa 450 kcal)
COLAZIONE_PORTIONS = {
    'Opzione 1 - Dolce classica con fette biscottate': {
        'Caffè espresso': 50,  # 1 tazzina
        'Fette biscottate': 40,  # ~155 kcal
        'Marmellata': 30,  # ~68 kcal
        'Yogurt magro 0.1%': 125,  # 52 kcal
        'Mandorle': 15  # ~94 kcal (compensazione yogurt magro)
        # Totale: ~369 kcal (scalabile)
    },
    'Opzione 2 - Dolce con pane e frutta secca': {
        'Pane integrale': 50,  # ~112 kcal
        'Marmellata': 30,  # ~68 kcal
        'Yogurt magro 0.1%': 125,  # ~52 kcal
        'Mandorle': 20  # ~126 kcal
        # Totale: ~358 kcal (scalabile)
    },
    'Opzione 3 - Salata completa': {
        'Pane integrale': 60,  # ~134 kcal
        'Prosciutto crudo': 40,  # ~90 kcal
        'Formaggio spalmabile light': 30,  # ~54 kcal
        'Caffè espresso': 50
        # Totale: ~278 kcal (scalabile)
    }
}

# Porzioni standard per PRANZO (circa 850 kcal)
PRANZO_PORTIONS = {
    'Opzione 1 - Pasta al tonno': {
        'Pasta secca (di semola)': 90,  # ~307 kcal
        'Tonno al naturale (drenato)': 80,  # ~82 kcal
        'Zucchine (crude)': 200,  # ~32 kcal
        'Olio EVO': 15,  # ~135 kcal
        'Mela': 150  # ~66 kcal
        # Totale: ~622 kcal (scalabile)
    },
    'Opzione 3 - Riso con proteine': {
        'Riso basmati': 80,  # ~294 kcal
        'Pollo petto (cotto in padella)': 150,  # ~150 kcal
        'Piselli (in scatola, scolati)': 80,  # ~62 kcal
        'Zucchine (crude)': 150,  # ~24 kcal
        'Olio EVO': 10,  # ~90 kcal
        'Mela': 150  # ~66 kcal
        # Totale: ~686 kcal (scalabile)
    }
}

# Porzioni standard per CENA (circa 650 kcal)
CENA_PORTIONS = {
    'Opzione 1 - Carne + patate/pane + verdure': {
        'Pollo petto (cotto in padella)': 180,  # ~180 kcal
        'Patate (senza buccia, bollite)': 200,  # ~148 kcal
        'Zucchine (crude)': 200,  # ~32 kcal
        'Olio EVO': 15  # ~135 kcal
        # Totale: ~495 kcal (scalabile)
    },
    'Opzione 2 - Pesce + patate/pane + verdure': {
        'Salmone': 150,  # ~278 kcal
        'Patate (senza buccia, bollite)': 180,  # ~133 kcal
        'Zucchine (crude)': 200,  # ~32 kcal
        'Olio EVO': 10  # ~90 kcal
        # Totale: ~533 kcal (scalabile)
    }
}


def scale_portions(portions, target_kcal, current_kcal):
    """Scala porzioni per raggiungere target kcal"""
    if current_kcal == 0:
        return portions

    ratio = target_kcal / current_kcal

    # Non scalare oltre limiti ragionevoli
    if ratio < 0.7 or ratio > 1.5:
        ratio = min(max(ratio, 0.8), 1.3)

    scaled = {}
    for ingredient, amount in portions.items():
        scaled[ingredient] = round(amount * ratio, 0)

    return scaled


def get_standard_portions(meal_name, option_name, target_kcal=None):
    """Ottieni porzioni standard per opzione"""

    # Mapping pasti
    portions_db = {
        'COLAZIONE': COLAZIONE_PORTIONS,
        'PRANZO': PRANZO_PORTIONS,
        'CENA': CENA_PORTIONS
    }

    if meal_name not in portions_db:
        return None

    portions = portions_db[meal_name].get(option_name)

    if not portions:
        return None

    # Se target_kcal specificato, scala
    if target_kcal:
        from food_db import FoodDB
        db = FoodDB()

        # Calcola kcal attuali
        current_kcal = 0
        for ingredient, amount in portions.items():
            nutrients = db.calculate_nutrients(ingredient, amount)
            if nutrients:
                current_kcal += nutrients['kcal']

        # Scala
        portions = scale_portions(portions, target_kcal, current_kcal)

    return portions


# Test
if __name__ == '__main__':
    from food_db import FoodDB

    db = FoodDB()

    print("Porzioni standard COLAZIONE Opzione 1 (target 450 kcal)\n")

    portions = get_standard_portions('COLAZIONE', 'Opzione 1 - Dolce classica con fette biscottate', target_kcal=450)

    if portions:
        total_kcal = 0
        total_p = 0
        total_cho = 0
        total_f = 0

        for ingredient, amount in portions.items():
            nutrients = db.calculate_nutrients(ingredient, amount)
            if nutrients:
                print(f"{ingredient}: {amount:.0f}g → {nutrients['kcal']:.0f} kcal | P {nutrients['protein']:.1f}g | CHO {nutrients['cho']:.1f}g | F {nutrients['fat']:.1f}g")
                total_kcal += nutrients['kcal']
                total_p += nutrients['protein']
                total_cho += nutrients['cho']
                total_f += nutrients['fat']

        print(f"\nTotale: {total_kcal:.0f} kcal | P {total_p:.1f}g | CHO {total_cho:.1f}g | F {total_f:.1f}g")
