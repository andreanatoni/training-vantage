#!/usr/bin/env python3
"""
piano_base_parser.py - Parser per piano_base_ottimizzato.md

Estrae struttura:
- Pasti (COLAZIONE, SPUNTINO_AM, PRANZO, SPUNTINO_PM, CENA)
- Opzioni per pasto (Opzione 1, Opzione 2, etc.)
- Ingredienti con alternative OR
- Note "Quando usarla"
"""

import re
from pathlib import Path
from typing import Dict, List, Any


class PianoBaseParser:
    """Parser per piano_base_ottimizzato.md"""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.content = self._read_file()
        self.meals = {}

    def _read_file(self) -> str:
        """Legge file piano_base"""
        with open(self.file_path, 'r', encoding='utf-8') as f:
            return f.read()

    def parse(self) -> Dict[str, Any]:
        """
        Parse completo del piano base

        Returns:
            dict con struttura:
            {
                'COLAZIONE': {
                    'timing': '07:30-08:30',
                    'options': [
                        {
                            'id': 1,
                            'title': 'Dolce classica con fette biscottate',
                            'ingredients': [
                                {'name': 'Caffè', 'category': 'Bevanda', 'alternatives': []},
                                {'name': 'Fette biscottate', 'category': 'CHO', 'alternatives': []},
                                ...
                            ],
                            'when': 'Colazione veloce...',
                            'notes': []
                        },
                        ...
                    ]
                },
                ...
            }
        """
        # Split contenuto in sezioni per pasto
        meal_sections = self._split_into_meals()

        for meal_name, section_text in meal_sections.items():
            self.meals[meal_name] = self._parse_meal_section(meal_name, section_text)

        return self.meals

    def _split_into_meals(self) -> Dict[str, str]:
        """Split contenuto in sezioni per pasto"""
        sections = {}

        # Pattern per identificare inizio pasto (# con emoji + nome)
        meal_pattern = r'^# [^\n]+ (COLAZIONE|SPUNTINO MATTINA|PRANZO|SPUNTINO POMERIGGIO|SPUNTINO SERA|CENA) - Piano Base Validato'

        # Normalizza nomi pasti
        meal_name_map = {
            'COLAZIONE': 'COLAZIONE',
            'SPUNTINO MATTINA': 'SPUNTINO_AM',
            'PRANZO': 'PRANZO',
            'SPUNTINO POMERIGGIO': 'SPUNTINO_PM',
            'SPUNTINO SERA': 'SPUNTINO_SERA',
            'CENA': 'CENA'
        }

        # Find all meal headers
        lines = self.content.split('\n')
        meal_starts = []

        for i, line in enumerate(lines):
            match = re.search(meal_pattern, line)
            if match:
                meal_name_raw = match.group(1)
                meal_name = meal_name_map.get(meal_name_raw, meal_name_raw)
                meal_starts.append((i, meal_name))

        # Extract sections between headers
        for idx, (start_line, meal_name) in enumerate(meal_starts):
            # End is either next meal or end of file
            end_line = meal_starts[idx + 1][0] if idx + 1 < len(meal_starts) else len(lines)
            section_lines = lines[start_line:end_line]
            sections[meal_name] = '\n'.join(section_lines)

        return sections

    def _parse_meal_section(self, meal_name: str, section_text: str) -> Dict[str, Any]:
        """Parse singola sezione pasto"""

        # Extract timing
        timing_match = re.search(r'\*\*Timing\*\*:\s*(.+?)(?:\n|$)', section_text)
        timing = timing_match.group(1) if timing_match else ''

        # Extract options
        options = self._extract_options(section_text)

        return {
            'timing': timing,
            'options': options
        }

    def _extract_options(self, section_text: str) -> List[Dict[str, Any]]:
        """Estrae tutte le opzioni da una sezione pasto"""
        options = []

        # Pattern per opzioni: ### Opzione N - Titolo
        option_pattern = r'### Opzione (\d+) - (.+?)\n'

        # Find all option headers
        option_matches = list(re.finditer(option_pattern, section_text))

        for idx, match in enumerate(option_matches):
            option_num = int(match.group(1))
            option_title = match.group(2).strip()

            # Extract text for this option (until next option or end)
            start_pos = match.end()
            end_pos = option_matches[idx + 1].start() if idx + 1 < len(option_matches) else len(section_text)
            option_text = section_text[start_pos:end_pos]

            # Parse option details
            option_data = self._parse_option(option_num, option_title, option_text)
            options.append(option_data)

        return options

    def _parse_option(self, option_num: int, title: str, option_text: str) -> Dict[str, Any]:
        """Parse dettagli di una singola opzione"""

        # Extract ingredients
        ingredients = self._extract_ingredients(option_text)

        # Extract "Quando usarla"
        when_match = re.search(r'\*\*Quando usarla\*\*:\s*(.+?)(?:\n\n|---|\Z)', option_text, re.DOTALL)
        when = when_match.group(1).strip() if when_match else ''

        # Extract notes (if any)
        notes = self._extract_notes(option_text)

        return {
            'id': option_num,
            'title': title,
            'ingredients': ingredients,
            'when': when,
            'notes': notes
        }

    def _extract_ingredients(self, option_text: str) -> List[Dict[str, Any]]:
        """Estrae ingredienti da testo opzione"""
        ingredients = []

        # Find "**Ingredienti:**" section
        ingredients_match = re.search(r'\*\*Ingredienti:\*\*\n((?:- .+\n?)+)', option_text)

        if not ingredients_match:
            return ingredients

        ingredients_text = ingredients_match.group(1)

        # Parse each ingredient line
        for line in ingredients_text.split('\n'):
            line = line.strip()
            if not line.startswith('-'):
                continue

            # Remove leading "- "
            line = line[2:].strip()

            # Pattern: "Categoria: Alimento OR Alternativa OR Alternativa2"
            # Or just: "Alimento OR Alternativa"

            # Try to extract category (if present)
            category_match = re.match(r'^(.+?):\s*(.+)$', line)

            if category_match:
                category = category_match.group(1).strip()
                items_text = category_match.group(2).strip()
            else:
                category = ''
                items_text = line

            # Split by OR to get alternatives
            items = [item.strip() for item in re.split(r'\s+OR\s+', items_text)]

            # First item is main, rest are alternatives
            main_item = items[0] if items else ''
            alternatives = items[1:] if len(items) > 1 else []

            ingredients.append({
                'category': category,
                'name': main_item,
                'alternatives': alternatives
            })

        return ingredients

    def _extract_notes(self, option_text: str) -> List[str]:
        """Estrae note speciali (es: Note gestione tonno, Note preparazione)"""
        notes = []

        # Pattern per note: **Note xxx**:
        note_pattern = r'\*\*Note (.+?)\*\*:\n((?:- .+\n?)+)'

        for match in re.finditer(note_pattern, option_text):
            note_type = match.group(1)
            note_content = match.group(2).strip()
            notes.append({
                'type': note_type,
                'content': note_content
            })

        return notes


def parse_piano_base(file_path: Path) -> Dict[str, Any]:
    """
    Helper function per parsing piano base

    Args:
        file_path: Path to piano_base_ottimizzato.md

    Returns:
        Parsed structure
    """
    parser = PianoBaseParser(file_path)
    return parser.parse()


if __name__ == '__main__':
    # Test parser
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python3 piano_base_parser.py <path_to_piano_base.md>")
        sys.exit(1)

    file_path = Path(sys.argv[1])

    if not file_path.exists():
        print(f"File not found: {file_path}")
        sys.exit(1)

    result = parse_piano_base(file_path)

    # Print summary
    print("=" * 80)
    print("PIANO BASE PARSER - Summary")
    print("=" * 80)

    for meal_name, meal_data in result.items():
        print(f"\n{meal_name}")
        print(f"  Timing: {meal_data['timing']}")
        print(f"  Options: {len(meal_data['options'])}")

        for opt in meal_data['options']:
            print(f"    {opt['id']}. {opt['title']}")
            print(f"       Ingredients: {len(opt['ingredients'])}")

    # Optional: full JSON output
    if '--json' in sys.argv:
        print("\n" + "=" * 80)
        print("Full JSON:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
