#!/usr/bin/env python3
"""
swap_calculator.py - Calcolo grammature alternative per swap

Implementa logica iso-proteico/iso-grassi/iso-CHO/iso-calorico per calcolare
grammature alternative quando si swappa un ingrediente.

Regole:
- Proteine (carne/pesce): iso-proteico (stesse proteine)
- Frutta secca: iso-grassi (stessi grassi)
- Verdure: iso-calorico
- Frutta: iso-CHO
- CHO base (pasta/riso): FISSO (nessun calcolo)
- Olio EVO: condizionale (se proteina swap cambia grassi)
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
import json


class SwapCalculator:
    """Calcola grammature alternative per swap"""

    def __init__(self, food_db_path: Path):
        self.food_db = self._load_food_db(food_db_path)
        self.food_index = {f['id']: f for f in self.food_db['foods']}

    def _load_food_db(self, path: Path) -> Dict:
        """Carica FOOD_DB.json"""
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_nutrients_per_100g(self, food_id: str) -> Dict[str, float]:
        """
        Ottiene nutrienti per 100g di un alimento

        Args:
            food_id: ID alimento

        Returns:
            dict con kcal, P, CHO, F, Fibre per 100g
        """
        if food_id not in self.food_index:
            raise ValueError(f"Food ID '{food_id}' not found in FOOD_DB")

        food = self.food_index[food_id]
        reference_amount = food['reference']['amount']
        nutrients_ref = food['nutrients_per_reference']

        # Convert to per 100g
        factor = 100.0 / reference_amount

        return {
            'kcal': nutrients_ref['kcal'] * factor,
            'P': nutrients_ref['P'] * factor,
            'CHO': nutrients_ref['CHO'] * factor,
            'F': nutrients_ref['F'] * factor,
            'Fibre': nutrients_ref['Fibre'] * factor
        }

    def calculate_iso_protein(self, base_food_id: str, base_qty_g: float, alt_food_id: str) -> float:
        """
        Calcola grammatura alternativa con stesse proteine (iso-proteico)

        Args:
            base_food_id: Alimento base
            base_qty_g: Grammatura base (g)
            alt_food_id: Alimento alternativo

        Returns:
            Grammatura alternativa (g) con stesse proteine
        """
        base_nutrients = self.get_nutrients_per_100g(base_food_id)
        alt_nutrients = self.get_nutrients_per_100g(alt_food_id)

        # Calcola proteine totali del base
        base_protein_g = base_nutrients['P'] * base_qty_g / 100.0

        # Calcola grammatura alternative per stesse proteine
        if alt_nutrients['P'] == 0:
            raise ValueError(f"Alternative food '{alt_food_id}' has 0 protein - cannot do iso-protein swap")

        alt_qty_g = (base_protein_g / alt_nutrients['P']) * 100.0

        return round(alt_qty_g, 1)

    def calculate_iso_fat(self, base_food_id: str, base_qty_g: float, alt_food_id: str) -> float:
        """
        Calcola grammatura alternativa con stessi grassi (iso-grassi)

        Args:
            base_food_id: Alimento base
            base_qty_g: Grammatura base (g)
            alt_food_id: Alimento alternativo

        Returns:
            Grammatura alternativa (g) con stessi grassi
        """
        base_nutrients = self.get_nutrients_per_100g(base_food_id)
        alt_nutrients = self.get_nutrients_per_100g(alt_food_id)

        # Calcola grassi totali del base
        base_fat_g = base_nutrients['F'] * base_qty_g / 100.0

        # Calcola grammatura alternative per stessi grassi
        if alt_nutrients['F'] == 0:
            raise ValueError(f"Alternative food '{alt_food_id}' has 0 fat - cannot do iso-fat swap")

        alt_qty_g = (base_fat_g / alt_nutrients['F']) * 100.0

        return round(alt_qty_g, 1)

    def calculate_iso_cho(self, base_food_id: str, base_qty_g: float, alt_food_id: str) -> float:
        """
        Calcola grammatura alternativa con stessi CHO (iso-CHO)

        Args:
            base_food_id: Alimento base
            base_qty_g: Grammatura base (g)
            alt_food_id: Alimento alternativo

        Returns:
            Grammatura alternativa (g) con stessi CHO
        """
        base_nutrients = self.get_nutrients_per_100g(base_food_id)
        alt_nutrients = self.get_nutrients_per_100g(alt_food_id)

        # Calcola CHO totali del base
        base_cho_g = base_nutrients['CHO'] * base_qty_g / 100.0

        # Calcola grammatura alternative per stessi CHO
        if alt_nutrients['CHO'] == 0:
            # Se alternative ha 0 CHO, non possiamo fare swap iso-CHO
            # Fallback su iso-kcal
            return self.calculate_iso_kcal(base_food_id, base_qty_g, alt_food_id)

        alt_qty_g = (base_cho_g / alt_nutrients['CHO']) * 100.0

        return round(alt_qty_g, 1)

    def calculate_iso_kcal(self, base_food_id: str, base_qty_g: float, alt_food_id: str) -> float:
        """
        Calcola grammatura alternativa con stesse kcal (iso-calorico)

        Args:
            base_food_id: Alimento base
            base_qty_g: Grammatura base (g)
            alt_food_id: Alimento alternativo

        Returns:
            Grammatura alternativa (g) con stesse kcal
        """
        base_nutrients = self.get_nutrients_per_100g(base_food_id)
        alt_nutrients = self.get_nutrients_per_100g(alt_food_id)

        # Calcola kcal totali del base
        base_kcal = base_nutrients['kcal'] * base_qty_g / 100.0

        # Calcola grammatura alternative per stesse kcal
        if alt_nutrients['kcal'] == 0:
            raise ValueError(f"Alternative food '{alt_food_id}' has 0 kcal - cannot do iso-kcal swap")

        alt_qty_g = (base_kcal / alt_nutrients['kcal']) * 100.0

        return round(alt_qty_g, 1)

    def calculate_swap(
        self,
        base_food_id: str,
        base_qty_g: float,
        alt_food_id: str,
        category: str
    ) -> Dict[str, Any]:
        """
        Calcola swap basato su categoria

        Args:
            base_food_id: Alimento base
            base_qty_g: Grammatura base (g)
            alt_food_id: Alimento alternativo
            category: Categoria (protein, fat, veg, fruit, CHO_base, other)

        Returns:
            dict con:
            {
                'alt_food_id': str,
                'alt_qty_g': float,
                'swap_method': str (iso-protein, iso-fat, iso-CHO, iso-kcal, fixed),
                'base_nutrients': dict,
                'alt_nutrients': dict
            }
        """
        # CHO base restano fissi (non calcolano swap)
        if category == 'CHO_base':
            return {
                'alt_food_id': alt_food_id,
                'alt_qty_g': base_qty_g,  # FIXED
                'swap_method': 'fixed',
                'base_nutrients': self.get_nutrients_per_100g(base_food_id),
                'alt_nutrients': self.get_nutrients_per_100g(alt_food_id)
            }

        # Determina metodo swap
        if category == 'protein':
            method = 'iso-protein'
            alt_qty_g = self.calculate_iso_protein(base_food_id, base_qty_g, alt_food_id)
        elif category == 'fat':
            method = 'iso-fat'
            alt_qty_g = self.calculate_iso_fat(base_food_id, base_qty_g, alt_food_id)
        elif category == 'fruit':
            method = 'iso-CHO'
            alt_qty_g = self.calculate_iso_cho(base_food_id, base_qty_g, alt_food_id)
        elif category == 'veg':
            method = 'iso-kcal'
            alt_qty_g = self.calculate_iso_kcal(base_food_id, base_qty_g, alt_food_id)
        else:
            # Default: iso-kcal
            method = 'iso-kcal'
            alt_qty_g = self.calculate_iso_kcal(base_food_id, base_qty_g, alt_food_id)

        return {
            'alt_food_id': alt_food_id,
            'alt_qty_g': alt_qty_g,
            'swap_method': method,
            'base_nutrients': self.get_nutrients_per_100g(base_food_id),
            'alt_nutrients': self.get_nutrients_per_100g(alt_food_id)
        }

    def calculate_conditional_oil(
        self,
        base_oil_qty_g: float,
        base_protein_food_id: str,
        alt_protein_food_id: str,
        protein_qty_g: float
    ) -> float:
        """
        Calcola olio EVO condizionale quando swap proteina cambia grassi

        Esempio:
        - Tonno naturale (0.5g F/100g) + Olio 12g = ~12g grassi totali
        - Tonno sott'olio (10.1g F/100g) + Olio X g = ~12g grassi totali
          → X = 12 - (10.1 * qty / 100)

        Args:
            base_oil_qty_g: Olio base (g)
            base_protein_food_id: Proteina base
            alt_protein_food_id: Proteina alternativa
            protein_qty_g: Grammatura proteina

        Returns:
            Olio alternativo (g) per compensare grassi
        """
        base_protein_nutrients = self.get_nutrients_per_100g(base_protein_food_id)
        alt_protein_nutrients = self.get_nutrients_per_100g(alt_protein_food_id)

        # Grassi da proteina base
        base_protein_fat = base_protein_nutrients['F'] * protein_qty_g / 100.0

        # Grassi da proteina alternativa
        alt_protein_fat = alt_protein_nutrients['F'] * protein_qty_g / 100.0

        # Grassi totali target (proteina base + olio base)
        target_total_fat = base_protein_fat + base_oil_qty_g

        # Olio necessario con proteina alternativa
        alt_oil_qty_g = target_total_fat - alt_protein_fat

        # Non può essere negativo
        if alt_oil_qty_g < 0:
            alt_oil_qty_g = 0

        return round(alt_oil_qty_g, 1)


if __name__ == '__main__':
    # Test swap calculator
    import sys
    from pathlib import Path

    db_path = Path('data/FOOD_DB.json')
    if not db_path.exists():
        print(f"FOOD_DB not found at {db_path}")
        sys.exit(1)

    calc = SwapCalculator(db_path)

    print("=" * 80)
    print("SWAP CALCULATOR - Test")
    print("=" * 80)

    # Test 1: Iso-proteico (Pollo → Tacchino)
    print("\n1. ISO-PROTEICO: Pollo 180g → Tacchino")
    result = calc.calculate_swap('pollo_petto_cotto_in_padella', 180, 'tacchino_fesa_cotto_al_forno', 'protein')
    print(f"   Pollo 180g ({result['base_nutrients']['P']:.1f}g P/100g) → Tacchino {result['alt_qty_g']}g ({result['alt_nutrients']['P']:.1f}g P/100g)")
    print(f"   Method: {result['swap_method']}")

    # Test 2: Iso-grassi (Mandorle → Noci)
    print("\n2. ISO-GRASSI: Mandorle 15g → Noci")
    result = calc.calculate_swap('mandorle', 15, 'noci', 'fat')
    print(f"   Mandorle 15g ({result['base_nutrients']['F']:.1f}g F/100g) → Noci {result['alt_qty_g']}g ({result['alt_nutrients']['F']:.1f}g F/100g)")
    print(f"   Method: {result['swap_method']}")

    # Test 3: Iso-CHO (Mela → Banana)
    print("\n3. ISO-CHO: Mela 130g → Banana")
    result = calc.calculate_swap('mela', 130, 'banana', 'fruit')
    print(f"   Mela 130g ({result['base_nutrients']['CHO']:.1f}g CHO/100g) → Banana {result['alt_qty_g']}g ({result['alt_nutrients']['CHO']:.1f}g CHO/100g)")
    print(f"   Method: {result['swap_method']}")

    # Test 4: Iso-kcal (Zucchine → Carote)
    print("\n4. ISO-KCAL: Zucchine 150g → Carote")
    result = calc.calculate_swap('zucchine_crude', 150, 'carote_crude', 'veg')
    print(f"   Zucchine 150g ({result['base_nutrients']['kcal']:.1f} kcal/100g) → Carote {result['alt_qty_g']}g ({result['alt_nutrients']['kcal']:.1f} kcal/100g)")
    print(f"   Method: {result['swap_method']}")

    # Test 5: Fixed (Pasta - CHO base)
    print("\n5. FIXED: Pasta 90g (CHO base non cambia)")
    result = calc.calculate_swap('pasta_secca_di_semola', 90, 'riso_basmati_crudo', 'CHO_base')
    print(f"   Pasta 90g → Riso {result['alt_qty_g']}g")
    print(f"   Method: {result['swap_method']}")

    # Test 6: Olio condizionale (Tonno naturale vs sott'olio)
    print("\n6. OLIO CONDIZIONALE: Tonno naturale + Olio 12g vs Tonno sott'olio")
    alt_oil = calc.calculate_conditional_oil(12, 'tonno_al_naturale_drenato', 'tonno_sott_olio_sgocciolato', 75)
    print(f"   Tonno naturale 75g + Olio 12g")
    print(f"   → Tonno sott'olio 75g + Olio {alt_oil}g")

    print("\n" + "=" * 80)
