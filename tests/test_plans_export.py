#!/usr/bin/env python3
"""
Test suite for plans export (Phase 2)

Tests:
- Parser piano_base
- Ingredient mapping
- Swap calculator
- Option generator
- Category plan generator
- Markdown exporter
- CLI /plan all
"""

import unittest
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.legacy.planner.piano_base_parser import parse_piano_base
from scripts.ingredient_mapper import map_ingredient_to_food_id, get_ingredient_category
from scripts.swap_calculator import SwapCalculator
from scripts.legacy.planner.option_generator import OptionGenerator
from scripts.legacy.planner.category_plan_generator import CategoryPlanGenerator
from scripts.legacy.planner.markdown_exporter import MarkdownExporter


class TestPlansExport(unittest.TestCase):
    """Test plans export system"""

    @classmethod
    def setUpClass(cls):
        cls.data_dir = Path('data')
        cls.piano_base_path = Path('sources/piano_base_ottimizzato.md')

    def test_01_parser(self):
        """Test piano_base parser"""
        piano_base = parse_piano_base(self.piano_base_path)

        self.assertIn('COLAZIONE', piano_base)
        self.assertIn('PRANZO', piano_base)
        self.assertIn('CENA', piano_base)

        # Check colazione has options
        colazione = piano_base['COLAZIONE']
        self.assertGreater(len(colazione['options']), 0)
        self.assertEqual(colazione['options'][0]['id'], 1)

    def test_02_ingredient_mapping(self):
        """Test ingredient mapping"""
        # Test basic mappings
        self.assertEqual(map_ingredient_to_food_id('Caffè'), 'caffe_espresso')
        self.assertEqual(map_ingredient_to_food_id('Pasta'), 'pasta_di_semola')
        self.assertEqual(map_ingredient_to_food_id('Pollo alla piastra'), 'pollo_petto_cotto_in_padella')

        # Test categories
        self.assertEqual(get_ingredient_category('pasta_di_semola'), 'CHO_base')
        self.assertEqual(get_ingredient_category('pollo_petto_cotto_in_padella'), 'protein')
        self.assertEqual(get_ingredient_category('mandorle'), 'fat')

    def test_03_swap_calculator(self):
        """Test swap calculator"""
        calc = SwapCalculator(self.data_dir / 'FOOD_DB.json')

        # Iso-proteico
        result = calc.calculate_swap('pollo_petto_cotto_in_padella', 180, 'tacchino_fesa_cotta_al_forno', 'protein')
        self.assertEqual(result['swap_method'], 'iso-protein')
        self.assertGreater(result['alt_qty_g'], 0)

        # Iso-grassi
        result = calc.calculate_swap('mandorle', 15, 'noci', 'fat')
        self.assertEqual(result['swap_method'], 'iso-fat')
        # Il valore puo' cambiare quando cambiano i nutrienti sorgente del FOOD_DB.
        self.assertGreater(result['alt_qty_g'], 0)

    def test_04_option_generator(self):
        """Test option generator"""
        piano_base = parse_piano_base(self.piano_base_path)
        colazione = piano_base['COLAZIONE']
        option1 = colazione['options'][0]

        generator = OptionGenerator(self.data_dir)

        meal_target = {'kcal': 484, 'P': 30.8, 'CHO': 55.0, 'F': 12.6}
        variants = generator.generate_option(option1, meal_target, 'meal')

        # Il numero varianti puo' cambiare con fallback/ingredienti disponibili nel FOOD_DB corrente.
        self.assertGreaterEqual(len(variants), 1)
        self.assertIn('variant', variants[0])
        self.assertIn('items', variants[0])
        self.assertIn('totals', variants[0])

    def test_05_category_plan_generator(self):
        """Test category plan generator"""
        generator = CategoryPlanGenerator(self.data_dir, self.piano_base_path)

        plan = generator.generate_category_plan('rest')

        self.assertEqual(plan['category_id'], 'rest')
        self.assertIn('meals', plan)
        self.assertIn('COLAZIONE', plan['meals'])
        self.assertGreater(len(plan['meals']['COLAZIONE']['options']), 0)

    def test_06_markdown_exporter(self):
        """Test markdown exporter"""
        # Generate plan
        generator = CategoryPlanGenerator(self.data_dir, self.piano_base_path)
        plan = generator.generate_category_plan('rest')

        # Export
        exporter = MarkdownExporter()
        output_path = Path('plans/nutrition/test_rest.md')

        exporter.export_plan(plan, output_path)

        # Verify file exists
        self.assertTrue(output_path.exists())

        # Verify content
        content = output_path.read_text()
        self.assertIn('<!-- META', content)
        self.assertIn('categoria: rest', content)
        self.assertIn('# Piano Nutrizionale: REST', content)

        # Cleanup
        output_path.unlink()

    def test_07_all_categories(self):
        """Test all 8 categories can be generated"""
        categories = ['rest', 'forza', 'easy_run', 'qualita', 'tempo', 'lungo', 'pizza_day', 'domenica']

        generator = CategoryPlanGenerator(self.data_dir, self.piano_base_path)

        for cat_id in categories:
            with self.subTest(category=cat_id):
                plan = generator.generate_category_plan(cat_id)
                self.assertEqual(plan['category_id'], cat_id)
                self.assertIn('meals', plan)


if __name__ == '__main__':
    unittest.main()
