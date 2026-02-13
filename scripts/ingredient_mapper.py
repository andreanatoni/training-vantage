#!/usr/bin/env python3
"""
ingredient_mapper.py - Mapping nomi ingredienti piano_base → food_db_ids

Mappa nomi "naturali" dal piano_base_ottimizzato.md ai food_db_ids in FOOD_DB.json
"""

from typing import Dict, List, Optional
import re


# Mapping statico nomi → food_db_ids
INGREDIENT_MAPPING = {
    # Bevande
    "Caffè": "caffe_espresso",
    "Caffe'": "caffe_espresso",
    "Caffè espresso": "caffe_espresso",

    # CHO Base
    "Fette biscottate": "fette_biscottate",
    "Pane integrale": "pane_integrale",
    "Pane bianco": "pane_bianco",
    "Pasta": "pasta_secca_di_semola",
    "Pasta secca": "pasta_secca_di_semola",
    "Riso basmati": "riso_basmati_crudo",
    "Riso": "riso_basmati_crudo",
    "Patate lesse": "patate_senza_buccia_bollite",
    "Patate al forno senza olio": "patate_senza_buccia_bollite",
    "Patate": "patate_senza_buccia_bollite",
    "Tortellini vitello": "tortellini_vitello",
    "Crackers integrali": "crackers_integrali",
    "Oro Saiwa": "oro_saiwa",

    # Dolci/Zuccheri
    "Marmellata": "marmellata",
    "Miele": "miele",
    "Plum cake": "plum_cake_senza_latte_burro",
    "Plum cake (senza latte/burro)": "plum_cake_senza_latte_burro",
    "Ciambellone": "plum_cake_senza_latte_burro",  # Stesso ID, variante
    "Ciambellone (senza latte/burro)": "plum_cake_senza_latte_burro",

    # Proteine Animali - Carne
    "Pollo alla piastra": "pollo_petto_cotto_in_padella",
    "Pollo": "pollo_petto_cotto_in_padella",
    "Tacchino": "tacchino_fesa_cotto_al_forno",
    "Vitello": "vitello_filetto_cotto_in_padella",
    "Manzo magro": "manzo_magro_fesa_crudo",
    "Manzo": "manzo_magro_fesa_crudo",
    "Prosciutto crudo": "prosciutto_crudo",
    "Bresaola": "bresaola",
    "Fesa tacchino": "fesa_tacchino_affettato",

    # Proteine Animali - Pesce
    "Salmone": "salmone",
    "Pesce spada": "pesce_spada",
    "Merluzzo": "merluzzo_surgelato_cotto_al_forno",
    "Tonno tagliata": "tonno_tagliata_fresco",
    "Tonno in scatola": "tonno_al_naturale_drenato",
    "Tonno in scatola (al naturale)": "tonno_al_naturale_drenato",
    "Tonno al naturale": "tonno_al_naturale_drenato",
    "Tonno sott'olio": "tonno_sott_olio_sgocciolato",
    "Tonno in scatola (sott'olio)": "tonno_sott_olio_sgocciolato",
    "Tonno sott'olio sgocciolato": "tonno_sott_olio_sgocciolato",

    # Proteine - Uova e Latticini
    "Uova": "uova_intere_gallina",
    "Uova strapazzate": "uova_intere_gallina",
    "Yogurt magro 0.1%": "yogurt_magro_0_1",
    "Yogurt greco 0%": "yogurt_greco_0",
    "Formaggio spalmabile (Philadelphia Light o simili)": "formaggio_spalmabile_light",
    "Formaggio spalmabile": "formaggio_spalmabile_light",
    "Parmigiano": "parmigiano_reggiano",
    "Parmigiano grattugiato": "parmigiano_reggiano",
    "Parmigiano reggiano": "parmigiano_reggiano",
    "Grana padano": "grana_padano",
    "Grana Padano": "grana_padano",
    "Mozzarella di bufala": "mozzarella_di_bufala",

    # Proteine Vegetali
    "Hummus di ceci": "hummus_di_ceci_solo_ceci_frullati",
    "Hummus di fagioli": "hummus_di_fagioli_solo_fagioli_frullati",

    # Grassi
    "Olio EVO": "olio_evo",
    "Mandorle": "mandorle",
    "Noci": "noci",
    "Nocciole": "nocciole",
    "Burro d'arachidi": "burro_d_arachidi",
    "Fiocchi d'avena": "fiocchi_d_avena",

    # Verdure
    "Zucchine": "zucchine_crude",
    "Zucchine crude": "zucchine_crude",
    "Carote": "carote_crude",
    "Carote crude": "carote_crude",
    "Piselli": "piselli_in_scatola_scolati",
    "Passata di pomodoro": "passata_di_pomodoro",
    "Passatina di pomodoro": "passata_di_pomodoro",
    "Vellutata zucchine e carote": "vellutata_zucchine_carote",
    "Vellutata di zucchine e carote": "vellutata_zucchine_carote",
    "Minestrone": "minestrone",

    # Condimenti/Extra
    "Zenzero grattuggiato": "zenzero_fresco",
    "Zenzero": "zenzero_fresco",
    "Zenzero fresco": "zenzero_fresco",
    "Ragù di vitello magro": "ragù_di_vitello_40_vitello_60_passata",
    "Ragù di vitello": "ragù_di_vitello_40_vitello_60_passata",

    # Frutta
    "Mela": "mela",
    "Banana": "banana",
    "Pera": "pera",
    "Frutta": "mela",  # Default per "Frutta: A scelta"
    "A scelta": "mela",  # Default
}


# Categorie macro per swap calculator
INGREDIENT_CATEGORIES = {
    # CHO Base (restano fissi)
    "pasta_secca_di_semola": "CHO_base",
    "riso_basmati_crudo": "CHO_base",
    "patate_senza_buccia_bollite": "CHO_base",
    "pane_integrale": "CHO_base",
    "pane_bianco": "CHO_base",
    "fette_biscottate": "CHO_base",

    # Proteine (swap iso-proteico)
    "pollo_petto_cotto_in_padella": "protein",
    "tacchino_fesa_cotto_al_forno": "protein",
    "vitello_filetto_cotto_in_padella": "protein",
    "manzo_magro_fesa_crudo": "protein",
    "salmone": "protein",
    "pesce_spada": "protein",
    "merluzzo_surgelato_cotto_al_forno": "protein",
    "tonno_al_naturale_drenato": "protein",
    "tonno_sott_olio_sgocciolato": "protein",
    "tonno_tagliata_fresco": "protein",
    "prosciutto_crudo": "protein",
    "bresaola": "protein",
    "fesa_tacchino_affettato": "protein",
    "uova_intere_gallina": "protein",
    "yogurt_magro_0_1": "protein",
    "yogurt_greco_0": "protein",
    "parmigiano_reggiano": "protein",
    "grana_padano": "protein",
    "mozzarella_di_bufala": "protein",
    "hummus_di_ceci_solo_ceci_frullati": "protein",
    "hummus_di_fagioli_solo_fagioli_frullati": "protein",

    # Grassi (swap iso-grassi)
    "mandorle": "fat",
    "noci": "fat",
    "nocciole": "fat",
    "burro_d_arachidi": "fat",
    "olio_evo": "fat",

    # Verdure (swap iso-calorico)
    "zucchine_crude": "veg",
    "carote_crude": "veg",
    "piselli_in_scatola_scolati": "veg",
    "passata_di_pomodoro": "veg",
    "vellutata_zucchine_carote": "veg",
    "minestrone": "veg",

    # Frutta (swap iso-CHO)
    "mela": "fruit",
    "banana": "fruit",
    "pera": "fruit",

    # Altri (nessuno swap o condizionale)
    "caffe_espresso": "beverage",
    "zenzero_fresco": "seasoning",
    "marmellata": "sweet",
    "miele": "sweet",
}


def map_ingredient_to_food_id(ingredient_name: str) -> Optional[str]:
    """
    Mappa nome ingrediente → food_db_id

    Args:
        ingredient_name: Nome ingrediente dal piano_base

    Returns:
        food_db_id se trovato, None altrimenti
    """
    import re

    # Normalizza nome (trim)
    name_normalized = ingredient_name.strip()

    # Remove parenthetical notes (es: "Mandorle (solo se...)" → "Mandorle")
    clean_name = re.sub(r'\s*\([^)]*\)', '', name_normalized).strip()

    # Exact match (original)
    if name_normalized in INGREDIENT_MAPPING:
        return INGREDIENT_MAPPING[name_normalized]

    # Exact match (cleaned)
    if clean_name in INGREDIENT_MAPPING:
        return INGREDIENT_MAPPING[clean_name]

    # Case-insensitive match (cleaned)
    for key, value in INGREDIENT_MAPPING.items():
        if key.lower() == clean_name.lower():
            return value

    # Partial match (es: "Yogurt" matches "Yogurt magro 0.1%")
    for key, value in INGREDIENT_MAPPING.items():
        if clean_name.lower() in key.lower():
            return value

    # Not found
    return None


def get_ingredient_category(food_db_id: str) -> str:
    """
    Ottiene categoria macro di un ingrediente per swap calculator

    Args:
        food_db_id: ID dal FOOD_DB

    Returns:
        Categoria: CHO_base, protein, fat, veg, fruit, beverage, seasoning, sweet, other
    """
    return INGREDIENT_CATEGORIES.get(food_db_id, "other")


# Missing foods in FOOD_DB (to be added if needed)
MISSING_FOODS = [
    # All required foods are now present
]


if __name__ == '__main__':
    # Test mapping
    test_ingredients = [
        "Caffè",
        "Pasta",
        "Pollo alla piastra",
        "Yogurt greco 0%",
        "Prosciutto crudo",
        "Tonno al naturale",
        "Zucchine",
        "Mela",
        "Mandorle",
        "UNKNOWN_FOOD"
    ]

    print("=" * 80)
    print("INGREDIENT MAPPER - Test")
    print("=" * 80)

    for ing in test_ingredients:
        food_id = map_ingredient_to_food_id(ing)
        if food_id:
            category = get_ingredient_category(food_id)
            print(f"{ing:40} → {food_id:40} [{category}]")
        else:
            print(f"{ing:40} → NOT FOUND")

    print("\n" + "=" * 80)
    print("Missing foods in FOOD_DB:")
    for missing in MISSING_FOODS:
        print(f"  ⚠️  {missing}")
