#!/usr/bin/env python3
"""
generation_logger.py - Logger per tracciare warning/errori durante generazione piani

Raccoglie tutti i warning e errori durante la generazione dei piani
e li salva in un report.md leggibile.
"""

from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path


class GenerationLogger:
    """Logger per tracciare warning/errori durante generazione piani"""

    def __init__(self):
        self.warnings = []
        self.errors = []
        self.info = []

    def warning(self, message: str, context: Dict[str, Any] = None):
        """Add warning"""
        self.warnings.append({
            'message': message,
            'context': context or {},
            'timestamp': datetime.now().isoformat()
        })

    def error(self, message: str, context: Dict[str, Any] = None):
        """Add error"""
        self.errors.append({
            'message': message,
            'context': context or {},
            'timestamp': datetime.now().isoformat()
        })

    def info(self, message: str, context: Dict[str, Any] = None):
        """Add info"""
        self.info.append({
            'message': message,
            'context': context or {},
            'timestamp': datetime.now().isoformat()
        })

    def has_issues(self) -> bool:
        """Check if there are any warnings or errors"""
        return len(self.warnings) > 0 or len(self.errors) > 0

    def generate_report(self, output_path: Path):
        """Generate markdown report"""
        lines = []

        # Header
        lines.append("# Plan Generation Report")
        lines.append("")
        lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # Summary
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- ✅ Info: {len(self.info)}")
        lines.append(f"- ⚠️  Warnings: {len(self.warnings)}")
        lines.append(f"- ❌ Errors: {len(self.errors)}")
        lines.append("")

        # Errors (if any)
        if self.errors:
            lines.append("---")
            lines.append("")
            lines.append("## ❌ Errors")
            lines.append("")

            # Group by context
            errors_by_category = {}
            for err in self.errors:
                category = err['context'].get('category', 'Unknown')
                meal = err['context'].get('meal', 'Unknown')
                option = err['context'].get('option', 'Unknown')

                key = f"{category} - {meal} - {option}"
                if key not in errors_by_category:
                    errors_by_category[key] = []
                errors_by_category[key].append(err['message'])

            for key, messages in errors_by_category.items():
                lines.append(f"### {key}")
                lines.append("")
                for msg in messages:
                    lines.append(f"- {msg}")
                lines.append("")

        # Warnings (if any)
        if self.warnings:
            lines.append("---")
            lines.append("")
            lines.append("## ⚠️  Warnings")
            lines.append("")

            # Group by type
            warnings_by_type = {}
            for warn in self.warnings:
                msg = warn['message']

                # Categorize warning type
                if 'not found in mapping' in msg:
                    warn_type = 'Ingredient Mapping'
                elif 'Failed to generate' in msg:
                    warn_type = 'Generation Failure'
                elif 'No distribution found' in msg:
                    warn_type = 'Missing Distribution'
                else:
                    warn_type = 'Other'

                if warn_type not in warnings_by_type:
                    warnings_by_type[warn_type] = []

                warnings_by_type[warn_type].append({
                    'message': msg,
                    'context': warn['context']
                })

            for warn_type, warns in warnings_by_type.items():
                lines.append(f"### {warn_type} ({len(warns)})")
                lines.append("")

                # For ingredient mapping, group by ingredient
                if warn_type == 'Ingredient Mapping':
                    ingredient_counts = {}
                    for w in warns:
                        # Extract ingredient name from message
                        msg = w['message']
                        if "'" in msg:
                            ing = msg.split("'")[1]
                            if ing not in ingredient_counts:
                                ingredient_counts[ing] = {
                                    'count': 0,
                                    'contexts': []
                                }
                            ingredient_counts[ing]['count'] += 1
                            ingredient_counts[ing]['contexts'].append(w['context'])

                    # Sort by count (most common first)
                    sorted_ingredients = sorted(ingredient_counts.items(), key=lambda x: x[1]['count'], reverse=True)

                    for ing, data in sorted_ingredients:
                        lines.append(f"- **{ing}** (skipped {data['count']} times)")

                        # Show contexts (max 3)
                        shown_contexts = set()
                        for ctx in data['contexts'][:3]:
                            category = ctx.get('category', '?')
                            meal = ctx.get('meal', '?')
                            shown_contexts.add(f"{category}/{meal}")

                        if shown_contexts:
                            lines.append(f"  - Found in: {', '.join(shown_contexts)}")

                        if data['count'] > 3:
                            lines.append(f"  - ... and {data['count'] - 3} more")

                else:
                    # For other warnings, just list them
                    for w in warns[:10]:  # Max 10
                        lines.append(f"- {w['message']}")
                        if w['context']:
                            ctx_str = ' | '.join(f"{k}={v}" for k, v in w['context'].items())
                            lines.append(f"  - Context: {ctx_str}")

                    if len(warns) > 10:
                        lines.append(f"- ... and {len(warns) - 10} more")

                lines.append("")

        # Info (if any)
        if self.info:
            lines.append("---")
            lines.append("")
            lines.append("## ℹ️  Info")
            lines.append("")
            for info in self.info:
                lines.append(f"- {info['message']}")
            lines.append("")

        # Save report
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))


# Global logger instance
_logger = None


def get_logger() -> GenerationLogger:
    """Get global logger instance"""
    global _logger
    if _logger is None:
        _logger = GenerationLogger()
    return _logger


def reset_logger():
    """Reset global logger"""
    global _logger
    _logger = GenerationLogger()


if __name__ == '__main__':
    # Test logger
    logger = GenerationLogger()

    logger.info("Starting plan generation", {'category': 'rest'})
    logger.warning("Ingredient 'Mandorle (solo se...)' not found in mapping", {
        'category': 'rest',
        'meal': 'COLAZIONE',
        'option': 'Opzione 5'
    })
    logger.warning("Ingredient 'Mandorle (solo se...)' not found in mapping", {
        'category': 'forza',
        'meal': 'COLAZIONE',
        'option': 'Opzione 5'
    })
    logger.warning("Ingredient 'Banana (opzionale)' not found in mapping", {
        'category': 'rest',
        'meal': 'SPUNTINO_AM',
        'option': 'Opzione 3'
    })
    logger.error("Failed to generate option", {
        'category': 'rest',
        'meal': 'PRANZO',
        'option': 'Opzione 1'
    })
    logger.info("Completed plan generation")

    # Generate report
    output_path = Path('plans/nutrition/test_report.md')
    logger.generate_report(output_path)

    print(f"✅ Report generated: {output_path}")
    print(f"   Warnings: {len(logger.warnings)}")
    print(f"   Errors: {len(logger.errors)}")

    # Show preview
    print("\nPreview:")
    print("=" * 80)
    with open(output_path, 'r') as f:
        for i, line in enumerate(f, 1):
            if i > 40:
                print("...")
                break
            print(line.rstrip())

    # Cleanup
    output_path.unlink()
