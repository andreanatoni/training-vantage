#!/usr/bin/env python3
"""
Demo Before/After: Volume Penalty Effect

Shows:
- BEFORE (volume_penalty_enabled=false): 600g zucchine solution
- AFTER (volume_penalty_enabled=true): <400g zucchine, uses fiber-dense alternatives
"""

import json
import sys
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.nutrition.plan_builder import PlanBuilder


def demo_before_volume_penalty():
    """Demo BEFORE: volume penalty disabled → 600g zucchine"""
    print("=" * 80)
    print("BEFORE: Volume Penalty DISABLED")
    print("=" * 80)

    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'

    # Temporarily disable volume penalty
    realism_path = data_dir / 'REALISM_RULES.json'
    with open(realism_path, 'r') as f:
        realism = json.load(f)

    original_enabled = realism['rules']['volume_penalty_enabled']
    realism['rules']['volume_penalty_enabled'] = False

    with open(realism_path, 'w') as f:
        json.dump(realism, f, indent=2, ensure_ascii=False)

    # Build with penalty disabled
    builder = PlanBuilder(data_dir)

    print("\n🎯 Target: kcal 400, P 20, CHO 60, F 10, Fibre 12 (high fiber)")
    print("📋 Allowed foods: zucchine, avena, mela, yogurt, mandorle\n")

    target = {
        'kcal': 400,
        'P': 20,
        'CHO': 60,
        'F': 10,
        'Fibre': 12
    }

    allowed_foods = [
        'zucchine_crude',
        'fiocchi_d_avena',
        'mela',
        'yogurt_greco_0_lipidi',
        'mandorle'
    ]

    result = builder.balancer.balance_meal(
        target=target,
        meal_context='meal',
        allowed_food_db_ids=allowed_foods
    )

    realistic = result['best_match_realistic']

    print("📊 Results (penalty DISABLED):")
    veg_total = 0
    for item in realistic['items']:
        if item['qty']['amount'] > 0:
            print(f"   - {item['name']}: {item['qty']['amount']}{item['qty']['unit']}")
            if builder.food_group_map.get(item['food_db_id']) == 'veg':
                veg_total += item['qty']['amount']

    print(f"\n   🥒 VEG TOTAL: {veg_total:.0f}g")
    print(f"   📊 Fibre achieved: {realistic['totals']['Fibre']:.1f}g")

    if veg_total > 400:
        print(f"   ⚠️  Volume molto alto (>400g)!")

    # Restore original setting
    realism['rules']['volume_penalty_enabled'] = original_enabled
    with open(realism_path, 'w') as f:
        json.dump(realism, f, indent=2, ensure_ascii=False)


def demo_after_volume_penalty():
    """Demo AFTER: volume penalty enabled → <400g zucchine, uses alternatives"""
    print("\n\n" + "=" * 80)
    print("AFTER: Volume Penalty ENABLED")
    print("=" * 80)

    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'
    builder = PlanBuilder(data_dir)

    print("\n🎯 Target: kcal 400, P 20, CHO 60, F 10, Fibre 12 (high fiber)")
    print("📋 Allowed foods: zucchine, avena, mela, yogurt, mandorle")
    print("✅ Volume penalty: ENABLED (soft constraint)\n")

    target = {
        'kcal': 400,
        'P': 20,
        'CHO': 60,
        'F': 10,
        'Fibre': 12
    }

    allowed_foods = [
        'zucchine_crude',
        'fiocchi_d_avena',
        'mela',
        'yogurt_greco_0_lipidi',
        'mandorle'
    ]

    result = builder.balancer.balance_meal(
        target=target,
        meal_context='meal',
        allowed_food_db_ids=allowed_foods
    )

    realistic = result['best_match_realistic']

    print("📊 Results (penalty ENABLED):")
    veg_total = 0
    fiber_dense = []

    for item in realistic['items']:
        if item['qty']['amount'] > 0:
            food_id = item['food_db_id']
            group = builder.food_group_map.get(food_id, 'unknown')

            symbol = ""
            if group == 'veg':
                veg_total += item['qty']['amount']
                symbol = "🥒"
            elif food_id in ['fiocchi_d_avena', 'mandorle', 'mela']:
                fiber_dense.append(item['name'])
                symbol = "🌾"

            print(f"   {symbol} {item['name']}: {item['qty']['amount']}{item['qty']['unit']}")

    print(f"\n   🥒 VEG TOTAL: {veg_total:.0f}g")
    print(f"   🌾 Fiber-dense used: {len(fiber_dense)}")
    print(f"   📊 Fibre achieved: {realistic['totals']['Fibre']:.1f}g")

    if veg_total < 400:
        print(f"   ✅ Volume realistico (<400g)!")


def main():
    """Run before/after demo"""
    print("\n")
    print("=" * 80)
    print("🎬 VOLUME PENALTY DEMO: BEFORE vs AFTER")
    print("=" * 80)
    print("\nShowing how volume penalty prefers fiber-dense alternatives")
    print("over excessive veg volume\n")

    demo_before_volume_penalty()
    demo_after_volume_penalty()

    print("\n\n" + "=" * 80)
    print("✅ DEMO COMPLETED")
    print("=" * 80)
    print("\nKey takeaway: Volume penalty (soft constraint) guides solver")
    print("to prefer fiber-dense alternatives (avena/fruit/nuts) over")
    print("excessive veg volume, while still allowing high veg when necessary.")
    print("=" * 80)


if __name__ == '__main__':
    main()
