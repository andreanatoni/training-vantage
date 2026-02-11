#!/usr/bin/env python3
"""
Generatore piani avanzato con grammature calcolate

Calcola grammature esatte per ogni ingrediente in base a target kcal pasto.
Approccio semplificato: quantifica la prima opzione di ogni pasto.
"""

from food_db import FoodDB
from piano_base import PianoBase


# Mapping ingredienti piano-base → food-db
INGREDIENT_MAPPING = {
    # Colazione
    'Caffè': 'Caffè espresso',
    'Fette biscottate': 'Fette biscottate',
    'Oro Saiwa': 'Oro Saiwa',
    'Pane integrale': 'Pane integrale',
    'Marmellata': 'Marmellata',
    'Plum cake': 'Plum cake (senza latte/burro)',
    'Ciambellone (senza latte/burro)': 'Plum cake (senza latte/burro)',
    'Yogurt magro 0.1%': 'Yogurt magro 0.1%',
    'Yogurt greco 0%': 'Yogurt greco 0%',
    'Mandorle': 'Mandorle',
    'Noci': 'Noci',
    'Nocciole': 'Nocciole',
    'Burro d\'arachidi': 'Burro d\'arachidi',
    'Fiocchi d\'avena': 'Fiocchi d\'avena',

    # Proteine
    'Prosciutto crudo': 'Prosciutto crudo',
    'Bresaola': 'Bresaola',
    'Fesa tacchino': 'Fesa tacchino (affettato)',
    'Formaggio spalmabile (Philadelphia Light)': 'Formaggio spalmabile light',

    # Crackers e pane
    'Crackers integrali': 'Crackers integrali',

    # Frutta
    'Mela': 'Mela',
    'Banana': 'Banana',
    'Pera': 'Pera',
    'Miele': 'Miele',

    # Pranzo/Cena
    'Pasta': 'Pasta secca (di semola)',
    'Pasta secca (di semola)': 'Pasta secca (di semola)',
    'Riso basmati': 'Riso basmati',
    'Tortellini vitello': 'Tortellini vitello',
    'Tonno in scatola': 'Tonno al naturale (drenato)',
    'Tonno al naturale': 'Tonno al naturale (drenato)',
    'Ragù di vitello magro': 'Ragù di vitello (40% vitello / 60% passata)',
    'Pollo alla piastra': 'Pollo petto (cotto in padella)',
    'Pollo': 'Pollo petto (cotto in padella)',
    'Tacchino': 'Tacchino, fesa (cotto al forno)',
    'Vitello': 'Vitello (filetto, cotto in padella)',
    'Manzo magro': 'Manzo magro (fesa, crudo)',
    'Salmone': 'Salmone',
    'Pesce spada': 'Pesce spada',
    'Merluzzo': 'Merluzzo (surgelato, cotto al forno)',
    'Tonno tagliata': 'Tonno tagliata (fresco)',
    'Uova': 'Uova intere (gallina)',
    'Uova strapazzate': 'Uova intere (gallina)',
    'Mozzarella di bufala': 'Mozzarella di bufala',
    'Parmigiano': 'Parmigiano Reggiano',
    'Parmigiano grattugiato': 'Parmigiano Reggiano',
    'Passata di pomodoro': 'Passata di pomodoro',
    'Passatina di pomodoro': 'Passata di pomodoro',
    'Piselli': 'Piselli (in scatola, scolati)',
    'Zucchine': 'Zucchine (crude)',
    'Carote': 'Carote (crude)',
    'Patate lesse': 'Patate (senza buccia, bollite)',
    'Patate': 'Patate (senza buccia, bollite)',
    'Patate al forno senza olio': 'Patate (senza buccia, bollite)',
    'Vellutata di zucchine e carote': 'Vellutata zucchine/carote',
    'Hummus di ceci': 'Hummus di ceci (solo ceci frullati)',
    'Hummus di fagioli': 'Hummus di fagioli (solo fagioli frullati)',
    'Olio EVO': 'Olio EVO',
    'Zenzero': 'Zenzero fresco',
    'Zenzero grattuggiato': 'Zenzero fresco'
}


class AdvancedPlanGenerator:
    """Genera piani con grammature calcolate"""

    def __init__(self):
        self.food_db = FoodDB()
        self.piano_base = PianoBase()

    def map_ingredient(self, ingredient_name):
        """Mappa ingrediente piano-base a food-db"""
        # Prova mapping diretto
        if ingredient_name in INGREDIENT_MAPPING:
            return INGREDIENT_MAPPING[ingredient_name]

        # Prova ricerca parziale nel food-db
        results = self.food_db.search(ingredient_name.lower())
        if results:
            return results[0]['name']

        return None

    def calculate_meal_portions(self, meal_name, target_kcal, option_index=0):
        """
        Calcola porzioni per un pasto.
        Approccio semplificato: distribuzione proporzionale kcal.
        """
        options = self.piano_base.get_meal_options(meal_name)

        if not options or option_index >= len(options):
            return None

        option = options[option_index]
        portions = []

        # Per ogni ingrediente, assegna una porzione base
        for ingredient_spec in option['ingredients']:
            if ingredient_spec['type'] == 'single':
                ing_name = ingredient_spec['name']

                # Mappa a food-db
                food_name = self.map_ingredient(ing_name)

                if food_name:
                    # Calcola porzione base (dividi kcal equamente per ora)
                    # Questo è semplificato - versione avanzata userebbe vincoli macro
                    portion_kcal = target_kcal / len(option['ingredients'])

                    # Trova grammatura
                    amount = self.food_db.find_amount_for_target(food_name, target_kcal=portion_kcal)

                    if amount:
                        nutrients = self.food_db.calculate_nutrients(food_name, amount)
                        portions.append({
                            'ingredient': ing_name,
                            'food_db_name': food_name,
                            'amount_g': amount,
                            'nutrients': nutrients
                        })

        return portions

    def generate_quantified_option(self, meal_name, target_kcal):
        """Genera opzione quantificata per pasto"""
        portions = self.calculate_meal_portions(meal_name, target_kcal)

        if not portions:
            return None

        # Calcola totali
        total_kcal = sum(p['nutrients']['kcal'] for p in portions)
        total_protein = sum(p['nutrients']['protein'] for p in portions)
        total_cho = sum(p['nutrients']['cho'] for p in portions)
        total_fat = sum(p['nutrients']['fat'] for p in portions)

        return {
            'portions': portions,
            'totals': {
                'kcal': round(total_kcal, 1),
                'protein': round(total_protein, 1),
                'cho': round(total_cho, 1),
                'fat': round(total_fat, 1)
            }
        }


# Test rapido
if __name__ == '__main__':
    gen = AdvancedPlanGenerator()

    print("Test calcolo porzioni COLAZIONE (450 kcal)\n")

    result = gen.generate_quantified_option('COLAZIONE', 450)

    if result:
        print("Ingredienti:")
        for p in result['portions']:
            print(f"  {p['ingredient']}: {p['amount_g']:.0f}g")
            print(f"    → {p['nutrients']['kcal']:.0f} kcal | P {p['nutrients']['protein']:.1f}g | CHO {p['nutrients']['cho']:.1f}g | F {p['nutrients']['fat']:.1f}g")

        print(f"\nTotale: {result['totals']['kcal']:.0f} kcal | P {result['totals']['protein']:.1f}g | CHO {result['totals']['cho']:.1f}g | F {result['totals']['fat']:.1f}g")
