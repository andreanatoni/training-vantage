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
    "Pasta": "pasta_di_semola",
    "Pasta secca": "pasta_di_semola",
    "Riso basmati": "riso_basmati_crudo",
    "Riso": "riso_basmati_crudo",
    "Patate lesse": "patate_bollite_senza_buccia",
    "Patate al forno senza olio": "patate_bollite_senza_buccia",
    "Patate": "patate_bollite_senza_buccia",
    "Tortellini vitello": "tortellini_freschi",
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
    "Tacchino": "tacchino_fesa_cotta_al_forno",
    "Vitello": "vitello_filetto_cotto_in_padella",
    "Manzo magro": "bovino_adulto_o_vitellone_fesa_crudo",
    "Manzo": "bovino_adulto_o_vitellone_fesa_crudo",
    "Prosciutto crudo": "prosciutto_crudo",
    "Bresaola": "bresaola",
    "Fesa tacchino": "fesa_di_tacchino_arrosto",

    # Proteine Animali - Pesce
    "Salmone": "salmone",
    "Pesce spada": "pesce_spada",
    "Merluzzo": "merluzzo_o_nasello_surgelato_cotto_in_forno",
    "Tonno tagliata": "tonno_pinne_gialle",
    "Tonno in scatola": "tonno_al_naturale",
    "Tonno in scatola (al naturale)": "tonno_al_naturale",
    "Tonno al naturale": "tonno_al_naturale",
    "Tonno sott'olio": "tonno_sott_olio_sgocciolato",
    "Tonno in scatola (sott'olio)": "tonno_sott_olio_sgocciolato",
    "Tonno sott'olio sgocciolato": "tonno_sott_olio_sgocciolato",

    # Proteine - Uova e Latticini
    "Uova": "uova_di_gallina_intero",
    "Uova strapazzate": "uova_di_gallina_intero",
    "Yogurt magro 0.1%": "yogurt_bianco_scremato",
    "Yogurt greco 0%": "yogurt_greco_0_lipidi",
    "Formaggio spalmabile (Philadelphia Light o simili)": "formaggio_cremoso_spalmabile_light",
    "Formaggio spalmabile": "formaggio_cremoso_spalmabile_light",
    "Parmigiano": "parmigiano_reggiano_dop",
    "Parmigiano grattugiato": "parmigiano_reggiano_dop",
    "Parmigiano reggiano": "parmigiano_reggiano_dop",
    "Grana padano": "grana_padano",
    "Grana Padano": "grana_padano",
    "Mozzarella di bufala": "mozzarella_di_bufala",

    # Proteine Vegetali
    "Hummus di ceci": "hummus_di_ceci_solo_ceci_frullati",
    "Hummus di fagioli": "hummus_di_fagioli_solo_fagioli_frullati",

    # Grassi
    "Olio EVO": "olio_di_oliva_extra_vergine",
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
    "pasta_di_semola": "CHO_base",
    "riso_basmati_crudo": "CHO_base",
    "patate_bollite_senza_buccia": "CHO_base",
    "pane_integrale": "CHO_base",
    "pane_bianco": "CHO_base",
    "fette_biscottate": "CHO_base",

    # Proteine (swap iso-proteico)
    "pollo_petto_cotto_in_padella": "protein",
    "tacchino_fesa_cotta_al_forno": "protein",
    "vitello_filetto_cotto_in_padella": "protein",
    "bovino_adulto_o_vitellone_fesa_crudo": "protein",
    "salmone": "protein",
    "pesce_spada": "protein",
    "merluzzo_o_nasello_surgelato_cotto_in_forno": "protein",
    "tonno_al_naturale": "protein",
    "tonno_sott_olio_sgocciolato": "protein",
    "tonno_pinne_gialle": "protein",
    "prosciutto_crudo": "protein",
    "bresaola": "protein",
    "fesa_di_tacchino_arrosto": "protein",
    "uova_di_gallina_intero": "protein",
    "yogurt_bianco_scremato": "protein",
    "yogurt_greco_0_lipidi": "protein",
    "parmigiano_reggiano_dop": "protein",
    "grana_padano": "protein",
    "mozzarella_di_bufala": "protein",
    "hummus_di_ceci_solo_ceci_frullati": "protein",
    "hummus_di_fagioli_solo_fagioli_frullati": "protein",

    # Grassi (swap iso-grassi)
    "mandorle": "fat",
    "noci": "fat",
    "nocciole": "fat",
    "burro_d_arachidi": "fat",
    "olio_di_oliva_extra_vergine": "fat",

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
