#!/usr/bin/env python3
"""
Parser per piano-base.md

Carica e gestisce il piano base validato con tutte le opzioni per pasto.
"""

import re
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"
PIANO_BASE_FILE = KNOWLEDGE_DIR / "piano-base.md"


class PianoBase:
    """Piano base con opzioni validate per ogni pasto"""

    def __init__(self):
        self.meals = {}  # { 'COLAZIONE': {...}, 'PRANZO': {...}, ... }
        self._load()

    def _load(self):
        """Carica piano-base.md"""
        with open(PIANO_BASE_FILE, 'r', encoding='utf-8') as f:
            content = f.read()

        # Split in sezioni per H2 (##)
        sections = re.split(r'\n## ', content)

        for section in sections:
            if not section.strip():
                continue

            lines = section.split('\n')
            section_title = lines[0].strip()

            # Solo pasti principali (escludi RULES, NOTE OPERATIVE, etc.)
            meal_names = [
                'COLAZIONE', 'SPUNTINO MATTINA', 'PRANZO',
                'SPUNTINO POMERIGGIO', 'SPUNTINO SERA', 'CENA'
            ]

            if section_title in meal_names:
                self._parse_meal(section_title, section)

    def _parse_meal(self, meal_name, section_text):
        """Parse sezione pasto"""
        meal_data = {
            'name': meal_name,
            'timing': None,
            'options': []
        }

        # Estrai timing (se presente)
        timing_match = re.search(r'\*\*Timing\*\*:\s*(.+)', section_text)
        if timing_match:
            meal_data['timing'] = timing_match.group(1).strip()

        # Split in opzioni (###)
        options = re.split(r'\n### ', section_text)

        for opt_text in options[1:]:  # Skip first (meal header)
            option = self._parse_option(opt_text)
            if option:
                meal_data['options'].append(option)

        self.meals[meal_name] = meal_data

    def _parse_option(self, option_text):
        """Parse singola opzione"""
        lines = option_text.split('\n')

        # Prima riga = titolo opzione
        title_line = lines[0].strip()

        # Estrai numero opzione e nome
        match = re.match(r'Opzione (\d+)\s*-\s*(.+)', title_line)
        if not match:
            return None

        option_num = int(match.group(1))
        option_name = match.group(2).strip()

        # Ingredienti (linee che iniziano con alimento o contengono OR/opzionale)
        ingredients = []
        quando = None
        note = None

        for line in lines[1:]:
            line = line.strip()

            # Skip righe vuote
            if not line:
                continue

            # Quando usarla
            if line.startswith('**Quando'):
                quando = self._extract_text_after_bold(line)
                continue

            # Note
            if line.startswith('**Note'):
                note = self._extract_text_after_bold(line)
                continue

            # SWAP
            if line.startswith('**SWAP'):
                # TODO: parse swap separatamente
                continue

            # Timing
            if line.startswith('**Timing'):
                # Timing specifico opzione
                continue

            # Ingredienti (lista comma-separated o con OR)
            if ',' in line or ' OR ' in line or line[0].isupper():
                # Parse ingredienti
                ingr_list = self._parse_ingredients_line(line)
                ingredients.extend(ingr_list)

        return {
            'number': option_num,
            'name': option_name,
            'ingredients': ingredients,
            'quando': quando,
            'note': note
        }

    def _parse_ingredients_line(self, line):
        """Parse riga ingredienti"""
        # Rimuovi bullets/dashes iniziali
        line = re.sub(r'^[-*•]\s*', '', line)

        # Split per virgola
        parts = [p.strip() for p in line.split(',')]

        ingredients = []

        for part in parts:
            # Check se ha OR (alternative)
            if ' OR ' in part:
                alternatives = [a.strip() for a in part.split(' OR ')]
                ingredients.append({
                    'type': 'alternatives',
                    'items': alternatives,
                    'optional': False
                })
            else:
                # Check se opzionale
                optional = '(opzionale' in part.lower()
                # Rimuovi "(opzionale)" dal nome
                clean_name = re.sub(r'\s*\(opzionale[^)]*\)', '', part, flags=re.IGNORECASE)

                ingredients.append({
                    'type': 'single',
                    'name': clean_name.strip(),
                    'optional': optional
                })

        return ingredients

    def _extract_text_after_bold(self, line):
        """Estrae testo dopo **Label**: """
        match = re.search(r'\*\*[^*]+\*\*:\s*(.+)', line)
        if match:
            return match.group(1).strip()
        return line

    def get_meal(self, meal_name):
        """Ottieni dati pasto"""
        return self.meals.get(meal_name)

    def get_meal_options(self, meal_name):
        """Ottieni opzioni per pasto"""
        meal = self.get_meal(meal_name)
        if meal:
            return meal['options']
        return []

    def list_meals(self):
        """Lista nomi pasti"""
        return list(self.meals.keys())

    def count_options(self, meal_name):
        """Conta opzioni per pasto"""
        meal = self.get_meal(meal_name)
        if meal:
            return len(meal['options'])
        return 0


# Test rapido
if __name__ == '__main__':
    piano = PianoBase()

    print("Piano Base caricato")
    print()

    for meal_name in piano.list_meals():
        count = piano.count_options(meal_name)
        print(f"{meal_name}: {count} opzioni")

    print()
    print("Esempio — COLAZIONE Opzione 1:")
    colazione = piano.get_meal('COLAZIONE')
    if colazione and colazione['options']:
        opt1 = colazione['options'][0]
        print(f"  Nome: {opt1['name']}")
        print(f"  Ingredienti:")
        for ing in opt1['ingredients']:
            if ing['type'] == 'single':
                opt_str = " (opzionale)" if ing['optional'] else ""
                print(f"    - {ing['name']}{opt_str}")
            elif ing['type'] == 'alternatives':
                print(f"    - {' OR '.join(ing['items'])}")
        print(f"  Quando: {opt1['quando']}")
