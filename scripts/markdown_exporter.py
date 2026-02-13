#!/usr/bin/env python3
"""
markdown_exporter.py - Export piano in formato markdown

Genera file .md leggibile con:
- META comment (categoria, ffm, bmr, etc.)
- Header piano
- Pasti con opzioni
- Totali giornalieri
"""

from typing import Dict, Any
from pathlib import Path
from datetime import datetime


class MarkdownExporter:
    """Exporter piano → markdown"""

    def export_plan(self, plan: Dict[str, Any], output_path: Path):
        """
        Esporta piano come .md

        Args:
            plan: Piano da category_plan_generator
            output_path: Path file .md di output
        """
        md_content = self._generate_markdown(plan)

        # Save to file
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

    def _generate_markdown(self, plan: Dict[str, Any]) -> str:
        """Generate markdown content"""
        lines = []

        # META comment
        lines.append(self._generate_meta_comment(plan))
        lines.append("")

        # Header
        lines.append(f"# Piano Nutrizionale: {plan['category_id'].upper()}")
        lines.append("")
        lines.append(f"**Categoria**: {plan['category_name']}")
        lines.append(f"**Target giornaliero**: {plan['target_daily']['kcal']:.0f} kcal | {plan['target_daily']['P']:.0f}g P | {plan['target_daily']['CHO']:.0f}g CHO | {plan['target_daily']['F']:.0f}g F")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Meals
        for meal_id, meal_data in plan['meals'].items():
            lines.append(self._generate_meal_section(meal_id, meal_data))
            lines.append("")

        # Daily totals summary
        lines.append(self._generate_daily_summary(plan))

        return '\n'.join(lines)

    def _generate_meta_comment(self, plan: Dict[str, Any]) -> str:
        """Generate META HTML comment"""
        today = datetime.now().strftime('%Y-%m-%d')

        meta_lines = [
            "<!-- META",
            f"categoria: {plan['category_id']}",
            f"generato: {today}",
            f"ffm: {plan['ffm']:.2f}",
            f"peso: {plan['peso']:.2f}",
            f"bmr: {plan['bmr']}",
            "-->"
        ]

        return '\n'.join(meta_lines)

    def _generate_meal_section(self, meal_id: str, meal_data: Dict[str, Any]) -> str:
        """Generate meal section with all options"""
        lines = []

        # Meal header
        lines.append(f"## {meal_id.replace('_', ' ')} - {meal_data['timing']}")
        lines.append("")

        target = meal_data['target']
        lines.append(f"**Target**: {target['kcal']:.0f} kcal | {target['P']:.1f}g P | {target['CHO']:.1f}g CHO | {target['F']:.1f}g F")
        lines.append("")

        # Options
        for idx, option in enumerate(meal_data['options'], 1):
            lines.append(self._generate_option(idx, option))
            lines.append("")
            if idx < len(meal_data['options']):
                lines.append("---")
                lines.append("")

        return '\n'.join(lines)

    def _generate_option(self, idx: int, option: Dict[str, Any]) -> str:
        """Generate single option"""
        lines = []

        # Option header
        variant_suffix = f" ({option['variant']})" if option['variant'] != 'main' else ""
        lines.append(f"### Opzione {idx}{variant_suffix} - {option['title']}")
        lines.append("")

        # Items
        for item in option['items']:
            # Main item
            item_line = f"- {item['name']}: {item['qty']:.1f}{item['unit']}"

            # Alternatives (OR)
            if item['alternatives']:
                alts = [f"{alt['name']} {alt['qty']:.1f}g" for alt in item['alternatives']]
                item_line += f" OR {' OR '.join(alts)}"

            lines.append(item_line)

        lines.append("")

        # Totals
        totals = option['totals']
        lines.append(f"**Totali**: {totals['kcal']:.0f} kcal | {totals['P']:.1f}g P | {totals['CHO']:.1f}g CHO | {totals['F']:.1f}g F | {totals['Fibre']:.1f}g Fibre")

        # Delta
        delta = option['delta']
        lines.append(f"**Delta**: kcal {delta['kcal_pct']:+.1f}% | P {delta['P_pct']:+.1f}% | CHO {delta['CHO_pct']:+.1f}% | F {delta['F_pct']:+.1f}%")
        lines.append("")

        # When
        if option['when']:
            lines.append(f"**Quando usarla**: {option['when']}")

        return '\n'.join(lines)

    def _generate_daily_summary(self, plan: Dict[str, Any]) -> str:
        """Generate daily summary table"""
        lines = []

        lines.append("---")
        lines.append("")
        lines.append("## TOTALI GIORNALIERI")
        lines.append("")

        target = plan['target_daily']

        lines.append("| Nutriente | Target |")
        lines.append("|-----------|--------|")
        lines.append(f"| Kcal | {target['kcal']:.0f} |")
        lines.append(f"| Proteine | {target['P']:.0f}g |")
        lines.append(f"| Carboidrati | {target['CHO']:.0f}g |")
        lines.append(f"| Grassi | {target['F']:.0f}g |")
        lines.append(f"| Fibre | {target['Fibre']:.0f}g |")

        return '\n'.join(lines)


if __name__ == '__main__':
    # Test exporter
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from scripts.category_plan_generator import CategoryPlanGenerator

    data_dir = Path('data')
    piano_base_path = Path('sources/piano_base_ottimizzato.md')

    # Generate plan
    gen = CategoryPlanGenerator(data_dir, piano_base_path)
    plan = gen.generate_category_plan('rest')

    # Export to markdown
    exporter = MarkdownExporter()
    output_path = Path('plans/nutrition/rest.md')

    exporter.export_plan(plan, output_path)

    print(f"✅ Plan exported to {output_path}")
    print(f"   File size: {output_path.stat().st_size} bytes")

    # Show preview
    print("\nPreview (first 30 lines):")
    print("=" * 80)
    with open(output_path, 'r') as f:
        for i, line in enumerate(f, 1):
            if i > 30:
                print("...")
                break
            print(line.rstrip())

