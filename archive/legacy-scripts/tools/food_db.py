#!/usr/bin/env python3
"""
Parser per food-db.md

Carica e gestisce il database nutrizionale master.
"""

import re
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"
FOOD_DB_FILE = KNOWLEDGE_DIR / "food-db.md"


class FoodDB:
    """Database alimenti con valori nutrizionali"""

    def __init__(self):
        self.foods = {}
        self._load()

    def _load(self):
        """Carica food-db.md"""
        with open(FOOD_DB_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Trova tabella (skip header e separator)
        in_table = False
        for line in lines:
            line = line.strip()

            # Skip header markdown
            if line.startswith('#'):
                continue

            # Skip separator line (----)
            if '---' in line and '|' in line:
                in_table = True
                continue

            # Parse riga tabella
            if in_table and line.startswith('|'):
                self._parse_food_row(line)

    def _parse_food_row(self, line):
        """Parse singola riga tabella"""
        # Split by |, strip spaces
        parts = [p.strip() for p in line.split('|')]

        # Remove empty first/last
        if parts[0] == '':
            parts = parts[1:]
        if parts[-1] == '':
            parts = parts[:-1]

        if len(parts) < 7:
            return

        name = parts[0]
        reference = parts[1]
        kcal = self._parse_float(parts[2])
        protein = self._parse_float(parts[3])
        cho = self._parse_float(parts[4])
        fat = self._parse_float(parts[5])
        fiber = self._parse_float(parts[6])

        # Estrai quantità di riferimento (es. "100 g" → 100)
        ref_amount = self._extract_reference_amount(reference)

        self.foods[name] = {
            'name': name,
            'reference': reference,
            'ref_amount': ref_amount,
            'kcal': kcal,
            'protein': protein,
            'cho': cho,
            'fat': fat,
            'fiber': fiber
        }

    def _parse_float(self, value):
        """Parse valore numerico (gestisce anche formati strani)"""
        # Rimuovi spazi
        value = value.strip()

        # Se vuoto, return 0
        if not value or value == '-':
            return 0.0

        try:
            return float(value)
        except ValueError:
            return 0.0

    def _extract_reference_amount(self, ref_str):
        """Estrae quantità di riferimento in grammi"""
        # Pattern: "100 g", "125 g", "170 g vasetto", "50 ml"
        match = re.search(r'(\d+)\s*(g|ml)', ref_str)
        if match:
            return int(match.group(1))
        return 100  # default

    def get(self, name):
        """Ottieni alimento per nome"""
        return self.foods.get(name)

    def search(self, query):
        """Cerca alimenti per nome (case-insensitive, partial match)"""
        query = query.lower()
        results = []

        for name, food in self.foods.items():
            if query in name.lower():
                results.append(food)

        return results

    def calculate_nutrients(self, name, amount_g):
        """Calcola nutrienti per quantità specifica (in grammi)"""
        food = self.get(name)
        if not food:
            return None

        # Scala in base a ref_amount
        ratio = amount_g / food['ref_amount']

        return {
            'name': name,
            'amount_g': amount_g,
            'kcal': round(food['kcal'] * ratio, 1),
            'protein': round(food['protein'] * ratio, 1),
            'cho': round(food['cho'] * ratio, 1),
            'fat': round(food['fat'] * ratio, 1),
            'fiber': round(food['fiber'] * ratio, 1)
        }

    def find_amount_for_target(self, name, target_kcal=None, target_protein=None, target_cho=None):
        """
        Trova quantità (in grammi) per raggiungere target specifico.
        Usa il primo target non-None tra kcal, protein, cho.
        """
        food = self.get(name)
        if not food:
            return None

        # Determina target e valore di riferimento
        if target_kcal is not None:
            ref_value = food['kcal']
            target_value = target_kcal
        elif target_protein is not None:
            ref_value = food['protein']
            target_value = target_protein
        elif target_cho is not None:
            ref_value = food['cho']
            target_value = target_cho
        else:
            return None

        if ref_value == 0:
            return None

        # Calcola quantità
        amount_g = (target_value / ref_value) * food['ref_amount']

        return round(amount_g, 0)

    def list_all(self):
        """Lista tutti gli alimenti"""
        return list(self.foods.keys())

    def count(self):
        """Conta alimenti nel DB"""
        return len(self.foods)


# Test rapido
if __name__ == '__main__':
    db = FoodDB()

    print(f"Food DB caricato: {db.count()} alimenti")
    print()

    # Test lookup
    pasta = db.get("Pasta secca (di semola)")
    if pasta:
        print(f"Pasta: {pasta['kcal']} kcal, {pasta['protein']}g P, {pasta['cho']}g CHO per {pasta['ref_amount']}g")
        print()

    # Test calcolo
    nutrients = db.calculate_nutrients("Pasta secca (di semola)", 80)
    if nutrients:
        print(f"80g Pasta: {nutrients['kcal']} kcal, {nutrients['protein']}g P, {nutrients['cho']}g CHO")
        print()

    # Test search
    results = db.search("pollo")
    print(f"Ricerca 'pollo': {len(results)} risultati")
    for r in results:
        print(f"  - {r['name']}")
