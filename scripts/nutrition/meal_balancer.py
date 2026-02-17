#!/usr/bin/env python3
"""
meal_balancer.py - Sistema di bilanciamento pasti con vincoli LARN + PERSONAL_LIMITS

=== SPEC OPERATIVA ===

INPUT ATTESO:
{
  "target": { "kcal": 450, "P": 25, "CHO": 60, "F": 12, "Fibre": 8 },
  "meal_context": "snack" | "meal",  # default: "meal"
  "allowed_food_db_ids": ["..."]     # opzionale
}

REGOLE QUANTITÀ (ordine di priorità):

1. Se PERSONAL_LIMITS.is_ingredient=true
   → qty libera, quantizzata a step_g, rispettando max_qty_g
     (e snack/meal max se context_dependent)

2. Altrimenti se mapping.larn_portion_id != null
   → qty = LARN.standard_qty * multiplier
   - best_match_realistic: multiplier rispetta PERSONAL_LIMITS
   - best_match_unconstrained: può violare, ma marca violations

3. Altrimenti se mapping.operational_portion_id != null
   → qty = OPERATIVE.standard_qty * multiplier
     (e cap/allowed_multipliers)

4. Altrimenti → alimento non usabile (warning)

DUE SOLUZIONI OBBLIGATORIE:

- best_match_unconstrained: ignora caps realistic, marca violations
- best_match_realistic: non può violare caps realistic/context

OUTPUT:
- items[] con qty, multiplier, macros, violations
- totals, delta, recommendation, notes (max 6, Problema→Causa→Soluzione)

EDGE CASES GESTITI:
1. Unità diverse (g vs mL): no conversione
2. Reference amount variabile in FOOD_DB
3. Quantizzazione step per ingredient
4. Context-dependent caps (snack vs meal)
5. Pareggio: se delta realistic ≤ +5% vs unconstrained → raccomanda realistic
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from copy import deepcopy


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class NutrientValues:
    """Valori nutrizionali"""
    kcal: float
    P: float
    CHO: float
    F: float
    Fibre: float

    def to_dict(self) -> Dict[str, float]:
        return {
            'kcal': round(self.kcal, 1),
            'P': round(self.P, 1),
            'CHO': round(self.CHO, 1),
            'F': round(self.F, 1),
            'Fibre': round(self.Fibre, 1)
        }


@dataclass
class FoodQuantity:
    """Quantità di un alimento"""
    amount: float
    unit: str  # "g" o "mL"

    def to_dict(self) -> Dict[str, Any]:
        return {'amount': round(self.amount, 1), 'unit': self.unit}


@dataclass
class FoodItem:
    """Item nel pasto"""
    food_db_id: str
    name: str
    larn_portion_id: Optional[str]
    operational_portion_id: Optional[str]
    multiplier: Optional[float]
    qty: FoodQuantity
    macros: NutrientValues
    violations: List[str] = field(default_factory=list)
    is_ingredient: bool = False

    def to_dict(self) -> Dict[str, Any]:
        result = {
            'food_db_id': self.food_db_id,
            'name': self.name,
            'qty': self.qty.to_dict(),
            'macros': self.macros.to_dict()
        }

        if self.larn_portion_id:
            result['larn_portion_id'] = self.larn_portion_id
        if self.operational_portion_id:
            result['operational_portion_id'] = self.operational_portion_id
        if self.multiplier is not None:
            result['multiplier'] = round(self.multiplier, 2)
        if self.violations:
            result['violations'] = self.violations
        if self.is_ingredient:
            result['is_ingredient'] = True

        return result


@dataclass
class MatchResult:
    """Risultato del matching"""
    items: List[FoodItem]
    totals: NutrientValues
    delta: Dict[str, float]

    def to_dict(self, comment: str) -> Dict[str, Any]:
        return {
            'comment': comment,
            'items': [item.to_dict() for item in self.items],
            'totals': self.totals.to_dict(),
            'delta': self.delta
        }


@dataclass
class BeamState:
    """Stato nel beam search"""
    items: List[FoodItem]
    totals: NutrientValues
    score: float  # Lower is better

    def copy(self) -> 'BeamState':
        """Deep copy dello stato"""
        return BeamState(
            items=self.items.copy(),
            totals=NutrientValues(
                kcal=self.totals.kcal,
                P=self.totals.P,
                CHO=self.totals.CHO,
                F=self.totals.F,
                Fibre=self.totals.Fibre
            ),
            score=self.score
        )


# ============================================================================
# DATA LOADERS
# ============================================================================

class MealBalancerData:
    """Carica dataset nutrizionali in strict mode da FOOD_CATALOG derivato."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir

        # Runtime source of truth: derived unified catalog
        self.food_catalog = self._load_json('FOOD_CATALOG.json')
        self.catalog_active = True
        if not self._is_catalog_usable():
            raise SystemExit(
                "[ERR] FOOD_CATALOG.json missing/incoerente per meal_balancer strict mode. "
                "Esegui: ./tv food build-catalog && ./tv food validate-data"
            )

        # Build indexes for fast lookup
        self._build_indexes()

    def _load_json(self, filename: str) -> Dict:
        """Load JSON file"""
        filepath = self.data_dir / filename
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            sys.exit(1)

    def _is_catalog_usable(self) -> bool:
        """Catalog is usable only if complete and structurally coherent."""
        if not self.food_catalog:
            return False
        foods = self.food_catalog.get('foods')
        stats = self.food_catalog.get('stats', {})
        meta = self.food_catalog.get('meta', {})
        if not isinstance(foods, list) or not foods:
            return False
        if not meta.get('derived'):
            return False
        if stats.get('missing_mapping_count', 1) != 0:
            return False
        if stats.get('invalid_larn_mapping_count', 1) != 0:
            return False
        return True

    def _build_indexes(self):
        """Build fast lookup indexes"""
        self.food_db_index = {}
        self.mapping_index = {}
        self.personal_limits_index = {}
        self.catalog_portion_by_food = {}
        self.larn_index = {}
        self.operative_index = {}

        for food in self.food_catalog.get('foods', []):
            food_id = food.get('id')
            if not food_id:
                continue

            self.food_db_index[food_id] = {
                'id': food_id,
                'name': food.get('name'),
                'reference': food.get('reference'),
                'nutrients_per_reference': food.get('nutrients_per_reference'),
            }

            portion = food.get('portion') or {}
            self.catalog_portion_by_food[food_id] = portion
            larn_id = portion.get('larn_portion_id')
            if larn_id and larn_id not in self.larn_index:
                self.larn_index[larn_id] = {
                    'id': larn_id,
                    'standard': portion.get('standard'),
                    'practical': portion.get('practical', []),
                    'group': portion.get('group'),
                    'item_label': portion.get('item_label'),
                    'source': portion.get('source'),
                }

            mapping = food.get('mapping') or {}
            self.mapping_index[food_id] = {
                'food_db_id': food_id,
                'larn_portion_id': larn_id,
                'larn_variant_id': None,
                'operational_portion_id': None,
                'review_status': mapping.get('review_status'),
                'mapping_confidence': mapping.get('mapping_confidence'),
                'mapping_source': mapping.get('mapping_source'),
                'last_reviewed_at': mapping.get('last_reviewed_at'),
                'note': mapping.get('note'),
            }

            personal_limit = food.get('personal_limits')
            if isinstance(personal_limit, dict):
                self.personal_limits_index[food_id] = personal_limit


# ============================================================================
# CORE LOGIC
# ============================================================================

class MealBalancer:
    """Core meal balancing logic"""

    # ========================================================================
    # CONFIGURABLE CONSTANTS (v1.0)
    # ========================================================================

    # Multipliers ammessi (default)
    DEFAULT_MULTIPLIERS = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 2, 2.5, 3]
    YOGURT_EXTRA_MULTIPLIERS = [0.8]  # Per 100g

    # Score weights (priorità: kcal > P > CHO > F > Fibre)
    SCORE_WEIGHTS = {
        'kcal': 5.0,
        'P': 4.0,
        'CHO': 3.0,
        'F': 2.0,
        'Fibre': 1.0
    }

    # Pruning thresholds
    PRUNING_KCAL_REALISTIC = 1.2  # realistic può arrivare a 1.2× target kcal
    PRUNING_KCAL_UNCONSTRAINED = 1.4  # unconstrained può arrivare a 1.4× target kcal

    # Beam search
    DEFAULT_BEAM_WIDTH = 300

    # Pareggio rule
    PAREGGIO_THRESHOLD_PCT = 5.0  # Se realistic aumenta errore <5% → raccomanda realistic

    # Snapping
    SNAP_TOLERANCE_PCT = 0.2  # 20% tolerance per snap a preferred_qty
    SNAP_STEP_REALISTIC = 5.0  # Step default per realistic (g)
    SNAP_STEP_UNCONSTRAINED = 2.5  # Step default per unconstrained (g)

    def __init__(self, data: MealBalancerData):
        self.data = data

    def calculate_macros(self, food_db_id: str, qty_amount: float) -> NutrientValues:
        """
        Calcola macro da FOOD_DB per una data quantità.

        EDGE CASE 2: Reference amount può essere variabile (100g, 125g, 170g)
        """
        food = self.data.food_db_index.get(food_db_id)
        if not food:
            raise ValueError(f"Food {food_db_id} not found in FOOD_DB")

        ref_amount = food['reference']['amount']
        nutrients_ref = food['nutrients_per_reference']

        # Factor = qty / reference_amount
        factor = qty_amount / ref_amount

        return NutrientValues(
            kcal=nutrients_ref['kcal'] * factor,
            P=nutrients_ref['P'] * factor,
            CHO=nutrients_ref['CHO'] * factor,
            F=nutrients_ref['F'] * factor,
            Fibre=nutrients_ref['Fibre'] * factor
        )

    def get_portion_info(self, food_db_id: str, meal_context: str = "meal") -> Dict[str, Any]:
        """
        Ottiene info porzioni per un alimento seguendo ordine priorità.

        Returns dict con:
        - mode: "ingredient" | "larn" | "operative" | "unmapped"
        - standard_qty: float (base portion)
        - unit: "g" | "mL"
        - multipliers: List[float] (ammessi)
        - max_qty: float (da PERSONAL_LIMITS o None)
        - step: float (per ingredient)
        - is_ingredient: bool
        """
        mapping_entry = self.data.mapping_index.get(food_db_id)
        personal_limit = self.data.personal_limits_index.get(food_db_id)

        result = {
            'mode': 'unmapped',
            'standard_qty': None,
            'unit': 'g',
            'multipliers': self.DEFAULT_MULTIPLIERS.copy(),
            'max_qty': None,
            'step': None,
            'is_ingredient': False,
            'violations_possible': []
        }

        # PRIORITÀ 1: is_ingredient in PERSONAL_LIMITS
        if personal_limit and personal_limit.get('is_ingredient'):
            result['mode'] = 'ingredient'
            result['is_ingredient'] = True
            result['step'] = personal_limit.get('step_g', 10)
            result['unit'] = 'g'  # Ingredient sempre in grammi

            # Max qty (context-dependent se necessario)
            if personal_limit.get('context_dependent'):
                if meal_context == 'snack':
                    result['max_qty'] = personal_limit.get('snack_max_qty_g')
                else:
                    result['max_qty'] = personal_limit.get('meal_max_qty_g')
            else:
                result['max_qty'] = personal_limit.get('max_qty_g')

            return result

        # PRIORITÀ 2: LARN portion (from FOOD_CATALOG derived view)
        if mapping_entry:
            larn_id = mapping_entry.get('larn_portion_id')
            portion = self.data.catalog_portion_by_food.get(food_db_id) or {}
            standard = portion.get('standard') or {}

            if larn_id and standard.get('qty') and standard.get('unit'):
                result['mode'] = 'larn'
                result['standard_qty'] = standard['qty']
                result['unit'] = standard['unit']

                # Yogurt: extra multiplier 0.8
                if 'yogurt' in food_db_id:
                    result['multipliers'].extend(self.YOGURT_EXTRA_MULTIPLIERS)
                    result['multipliers'].sort()

                # Max from PERSONAL_LIMITS
                if personal_limit:
                    if personal_limit.get('context_dependent'):
                        if meal_context == 'snack':
                            result['max_qty'] = personal_limit.get('snack_max_qty_g')
                        else:
                            result['max_qty'] = personal_limit.get('meal_max_qty_g')
                    else:
                        result['max_qty'] = personal_limit.get('max_qty_g')

                return result

            # PRIORITÀ 3: OPERATIVE portion
            operative_id = mapping_entry.get('operational_portion_id')
            if operative_id and operative_id in self.data.operative_index:
                operative = self.data.operative_index[operative_id]
                result['mode'] = 'operative'
                result['standard_qty'] = operative['standard']['qty']
                result['unit'] = operative['standard']['unit']

                # Multipliers specifici se presenti
                if 'allowed_multipliers' in operative:
                    result['multipliers'] = operative['allowed_multipliers']

                # Cap da OPERATIVE o PERSONAL_LIMITS
                if 'max_qty' in operative:
                    result['max_qty'] = operative['max_qty']['qty']
                elif personal_limit:
                    result['max_qty'] = personal_limit.get('max_qty_g')

                return result

        # Nessuna porzione trovata
        return result

    def quantize_to_step(self, qty: float, step: float) -> float:
        """
        EDGE CASE 3: Quantizza qty allo step più vicino.
        Es: qty=83, step=20 → 80
        """
        if step <= 0:
            return qty
        return round(qty / step) * step

    def snap_to_realistic_qty(self, food_db_id: str, qty: float, mode: str) -> float:
        """
        Snap qty a quantità realistiche/pratiche.

        PROBLEMA: Le quantità matematicamente ottimali (es. 156.2g yogurt, 12.5g marmellata)
        sono impratiche da pesare/misurare.

        SOLUZIONE:
        - realistic: snap a preferred_qty_g se disponibile (es. [100, 125, 170] per yogurt),
          altrimenti a multipli di 5g
        - unconstrained: snap a 2.5g (più preciso ma comunque praticabile)

        LOGICA:
        1. Se mode='realistic' e preferred_qty_g esiste:
           - Trova il preferred più vicino a qty
           - Se differenza < 20% → usa preferred
           - Altrimenti → fallback a step 5g
        2. Altrimenti:
           - realistic: step 5g (es. 156.2 → 155g)
           - unconstrained: step 2.5g (es. 156.2 → 157.5g)

        Args:
            food_db_id: ID alimento
            qty: Quantità calcolata (es. 156.2)
            mode: "realistic" o "unconstrained"

        Returns:
            Quantità snappata a valore pratico

        Examples:
            >>> snap_to_realistic_qty('yogurt_greco_0_lipidi', 156.2, 'realistic')
            170.0  # snap a preferred_qty [100, 125, 170], 170 più vicino

            >>> snap_to_realistic_qty('pasta_di_semola', 83.7, 'realistic')
            85.0  # no preferred vicino < 20%, snap a 5g

            >>> snap_to_realistic_qty('olio_di_oliva_extra_vergine', 12.3, 'unconstrained')
            12.5  # snap a 2.5g (unconstrained più preciso)
        """
        personal_limit = self.data.personal_limits_index.get(food_db_id)

        if mode == 'realistic' and personal_limit and 'preferred_qty_g' in personal_limit:
            # Snap a preferred_qty_g più vicino
            preferred = personal_limit['preferred_qty_g']
            closest = min(preferred, key=lambda x: abs(x - qty))

            # Ma solo se la differenza è < SNAP_TOLERANCE_PCT (altrimenti usa qty originale snappato)
            if abs(closest - qty) / qty < self.SNAP_TOLERANCE_PCT:
                return float(closest)

        # Fallback: snap a step standard
        if mode == 'realistic':
            step = self.SNAP_STEP_REALISTIC
        else:
            step = self.SNAP_STEP_UNCONSTRAINED

        return self.quantize_to_step(qty, step)

    def generate_quantity_candidates(self,
                                     food_db_id: str,
                                     meal_context: str,
                                     mode: str,
                                     must_include_food_db_ids: Optional[List[str]] = None) -> List[Tuple[float, Optional[float], List[str]]]:
        """
        Genera candidati di quantità per un alimento seguendo priorità vincoli.

        LOGICA:
        1. Se is_ingredient=true (es. passata_di_pomodoro):
           - Genera qty a step_g (es. 20g, 40g, 60g, 80g, 100g)
           - realistic: rispetta max_qty_g (100g)
           - unconstrained: può arrivare a 2× max_qty_g (200g), marca violations

        2. Se LARN/OPERATIVE:
           - Genera qty = standard_qty × multiplier per ogni multiplier ammesso
           - Applica snap_to_realistic_qty()
           - realistic: skip se qty > max_qty_g
           - unconstrained: permette fino a 2× max_qty_g, marca violations

        3. Context-dependent (es. prosciutto_crudo):
           - Se meal_context='snack' → usa snack_max_qty_g (40g)
           - Se meal_context='meal' → usa meal_max_qty_g (120g)

        4. Opzione 0 (non usare alimento):
           - SEMPRE inclusa TRANNE se food_db_id in must_include_food_db_ids
           - must_include = hard constraint: alimento DEVE essere usato

        Args:
            food_db_id: ID alimento (es. 'passata_di_pomodoro')
            meal_context: "meal" o "snack"
            mode: "realistic" o "unconstrained"
            must_include_food_db_ids: Lista alimenti obbligatori (no opzione 0)

        Returns:
            Lista di (qty_amount, multiplier, violations)
            - qty_amount: quantità in g/mL
            - multiplier: moltiplicatore LARN (None per ingredient)
            - violations: lista violations (es. ['PERSONAL_LIMITS:max_qty_g'])

        Examples:
            >>> generate_quantity_candidates('passata_di_pomodoro', 'meal', 'realistic')
            [
                (0, None, []),        # opzione: non usare
                (20, None, []),       # step 20g
                (40, None, []),
                (60, None, []),
                (80, None, []),
                (100, None, [])       # max 100g per realistic
            ]

            >>> generate_quantity_candidates('prosciutto_crudo', 'snack', 'realistic')
            [
                (0, None, []),
                (25, 0.5, []),        # 50g × 0.5 (LARN)
                (40, 0.8, [])         # snap a 40g (snack_max)
                # 50g+ skipped (supera snack_max 40g)
            ]

            >>> generate_quantity_candidates('olio_di_oliva_extra_vergine', 'meal', 'unconstrained')
            [
                (0, None, []),
                (2.25, 0.25, []),     # 9g × 0.25
                (4.5, 0.5, []),
                ...
                (15, 1.67, []),       # max_qty_g 15g
                (20, 2.22, ['PERSONAL_LIMITS:max_qty_g']),  # viola cap
                (27, 3.0, ['PERSONAL_LIMITS:max_qty_g'])    # 3× porzione LARN
            ]
        """
        portion_info = self.get_portion_info(food_db_id, meal_context)

        if portion_info['mode'] == 'unmapped':
            return [(0, None, [])]  # Solo opzione "non usare"

        candidates = []

        # Opzione 0: non usare alimento (skip se must-include)
        is_must_include = (must_include_food_db_ids is not None and
                          food_db_id in must_include_food_db_ids)

        if not is_must_include:
            candidates.append((0, None, []))

        max_qty = portion_info['max_qty']

        if portion_info['is_ingredient']:
            # Ingredient: step discreto
            step = portion_info['step']

            if mode == 'realistic':
                # Rispetta max_qty
                if max_qty:
                    qty = step
                    while qty <= max_qty:
                        candidates.append((qty, None, []))
                        qty += step
                else:
                    # No limit: usa fino a 10 step (ragionevole)
                    for i in range(1, 11):
                        candidates.append((i * step, None, []))
            else:
                # Unconstrained: può superare max fino a 2× (ma segna violation)
                cap_unconstrained = max_qty * 2 if max_qty else step * 10
                qty = step
                while qty <= cap_unconstrained:
                    violations = []
                    if max_qty and qty > max_qty:
                        violations.append('PERSONAL_LIMITS:max_qty_g')
                    candidates.append((qty, None, violations))
                    qty += step

        else:
            # LARN/OPERATIVE: usa multipliers
            standard_qty = portion_info['standard_qty']
            multipliers = portion_info['multipliers']

            for mult in multipliers:
                qty = standard_qty * mult

                # Snap a quantità realistiche
                qty = self.snap_to_realistic_qty(food_db_id, qty, mode)

                violations = []

                if mode == 'realistic':
                    # Rispetta max_qty
                    if max_qty and qty > max_qty:
                        continue  # Skip questo multiplier
                else:
                    # Unconstrained: può superare max fino a 2×
                    if max_qty and qty > max_qty:
                        if qty > max_qty * 2:
                            continue  # Troppo folle, skip
                        violations.append('PERSONAL_LIMITS:max_qty_g')

                candidates.append((qty, mult, violations))

        return candidates

    def calculate_score(self,
                       totals: NutrientValues,
                       target: NutrientValues,
                       items: List[FoodItem],
                       mode: str,
                       extra_penalty_fn: Optional[callable] = None) -> float:
        """
        Calcola score per beam search (lower is better).

        OBIETTIVO: Minimizzare errore sui nutrienti con priorità decrescente.

        FORMULA:
        score = Σ (|actual - target| / target × 100) × peso + extra_penalty

        PESI (priorità):
        - kcal: 5.0 (massima priorità)
        - P: 4.0
        - CHO: 3.0
        - F: 2.0
        - Fibre: 1.0 (minima priorità)

        PENALITÀ PRATICITÀ (solo mode='realistic'):
        - Troppi alimenti (>7): +5 per ogni alimento extra
        - qty non in preferred_qty_g: +0.5 per ogni alimento

        EXTRA PENALTY (optional, v1.0):
        - Se extra_penalty_fn fornito, chiama fn(items, mode) per penalty aggiuntiva
        - Usato per soft constraints esterni (es. volume penalty da orchestrator)

        EDGE CASES:
        - Se target = 0 ma actual > 0: penalità 10 × actual
        - Se target = 0 e actual = 0: penalità 0

        Args:
            totals: Nutrienti totali del pasto corrente
            target: Nutrienti target
            items: Lista alimenti nel pasto
            mode: "realistic" o "unconstrained"
            extra_penalty_fn: Optional callback for external penalties

        Returns:
            Score (float, lower is better)

        Examples:
            >>> # Target: kcal 450, P 25, CHO 60, F 12, Fibre 8
            >>> # Actual: kcal 446, P 25.5, CHO 60.2, F 12.1, Fibre 8.0
            >>> calculate_score(totals, target, items, 'realistic')
            2.15  # Errore minimo:
                  # kcal: -0.9% × 5.0 = 4.5
                  # P: +2.0% × 4.0 = 8.0
                  # CHO: +0.3% × 3.0 = 0.9
                  # F: +0.8% × 2.0 = 1.6
                  # Fibre: 0% × 1.0 = 0
                  # Total weighted = 15.0
                  # + penalità praticità = 2.15

            >>> # Target impossibile: kcal 200, P 50
            >>> # Actual: kcal 350, P 30
            >>> calculate_score(totals, target, items, 'unconstrained')
            455.0  # Errore grande:
                   # kcal: +75% × 5.0 = 375
                   # P: -40% × 4.0 = 160
                   # Total = 535 (nessuna penalità praticità per unconstrained)
        """
        # Base error (weighted)
        error = 0
        for nutrient, weight in self.SCORE_WEIGHTS.items():
            target_val = getattr(target, nutrient)
            actual_val = getattr(totals, nutrient)

            if target_val > 0:
                pct_error = abs((actual_val - target_val) / target_val) * 100
            else:
                pct_error = abs(actual_val) * 10  # Penalità se target 0 ma actual > 0

            error += pct_error * weight

        # Penalità praticità (solo realistic)
        if mode == 'realistic':
            # Penalità se troppi alimenti (>7)
            if len(items) > 7:
                error += (len(items) - 7) * 5

            # Penalità se qty non in preferred
            for item in items:
                if item.qty.amount == 0:
                    continue

                personal_limit = self.data.personal_limits_index.get(item.food_db_id)
                if personal_limit and 'preferred_qty_g' in personal_limit:
                    preferred = personal_limit['preferred_qty_g']
                    # Se qty non è esattamente in preferred, piccola penalità
                    if item.qty.amount not in preferred:
                        error += 0.5

        # Extra penalty from external sources (v1.0 - orchestrator can inject)
        if extra_penalty_fn:
            extra = extra_penalty_fn(items, mode)
            error += extra

        return error

    def beam_search(self,
                   target: NutrientValues,
                   food_ids: List[str],
                   meal_context: str,
                   mode: str,
                   beam_width: Optional[int] = None,
                   extra_penalty_fn: Optional[callable] = None,
                   must_include_food_db_ids: Optional[List[str]] = None) -> BeamState:
        """
        Beam search per trovare combinazione ottimale di quantità.

        ALGORITMO:
        1. Inizializza beam con stato vuoto (pasto senza alimenti)
        2. Per ogni alimento in food_ids:
           a. Genera candidati di quantità (include opzione 0 = non usare)
           b. Espandi ogni stato nel beam con ogni candidato
           c. Applica pruning kcal (realistic: 1.2×, unconstrained: 1.4×)
           d. Calcola score per ogni nuovo stato
           e. Ordina per score e tieni solo i migliori beam_width stati
        3. Ritorna stato con score minimo (migliore)

        PRUNING:
        - Se nuovo stato supera kcal_target × multiplier → skip (sfora budget)
        - realistic: max 1.2× kcal (es. 450 → 540 kcal)
        - unconstrained: max 1.4× kcal (es. 450 → 630 kcal)

        OPZIONE 0:
        - Ogni alimento può avere qty=0 (non usato nel pasto)
        - Permette al sistema di escludere alimenti se non utili per target

        BEAM WIDTH:
        - Default 300: bilancia qualità soluzione vs performance
        - Più alto → soluzione migliore ma più lento
        - Più basso → più veloce ma soluzione potenzialmente subottimale

        Args:
            target: Target nutrizionali (es. kcal 450, P 25, CHO 60, F 12, Fibre 8)
            food_ids: Lista alimenti da considerare (es. ['yogurt_greco_0_lipidi', 'mandorle'])
            meal_context: "meal" o "snack"
            mode: "realistic" (rispetta caps) o "unconstrained" (può violare)
            beam_width: Numero stati da tenere per iterazione (default 300)

        Returns:
            BeamState con:
            - items: Lista FoodItem con quantità ottimali
            - totals: Nutrienti totali del pasto
            - score: Score finale (lower is better)

        Examples:
            >>> # COLAZIONE: 5 alimenti, target 450 kcal
            >>> target = NutrientValues(kcal=450, P=25, CHO=60, F=12, Fibre=8)
            >>> foods = ['caffe_espresso', 'fette_biscottate', 'marmellata',
            ...          'yogurt_greco_0_lipidi', 'mandorle']
            >>> state = beam_search(target, foods, 'meal', 'realistic', 300)
            >>>
            >>> # Risultato ottimale:
            >>> state.items = [
            ...     FoodItem('yogurt_greco_0_lipidi', qty=170g, multiplier=1.36),  # 170g vasetto
            ...     FoodItem('fette_biscottate', qty=30g, multiplier=1.0),  # 4 fette
            ...     FoodItem('marmellata', qty=20g, multiplier=2.0),        # 2 cucchiai
            ...     FoodItem('mandorle', qty=15g, multiplier=0.5),          # mezza porzione
            ...     # caffe_espresso qty=0 (opzione 0, non serve per target)
            ... ]
            >>> state.totals = NutrientValues(kcal=446, P=25.5, CHO=60.2, F=12.1, Fibre=8)
            >>> state.score = 2.15  # Errore minimo

            >>> # SPUNTINO: context-dependent, prosciutto max 40g in snack
            >>> target = NutrientValues(kcal=250, P=18, CHO=20, F=10, Fibre=3)
            >>> foods = ['prosciutto_crudo', 'pane_integrale']
            >>> state = beam_search(target, foods, 'snack', 'realistic', 300)
            >>>
            >>> # Risultato:
            >>> state.items = [
            ...     FoodItem('prosciutto_crudo', qty=40g, multiplier=0.8),  # max snack
            ...     FoodItem('pane_integrale', qty=50g, multiplier=1.0)     # 1 panino
            ... ]
        """
        # Use default beam width if not specified
        if beam_width is None:
            beam_width = self.DEFAULT_BEAM_WIDTH

        # Pruning kcal thresholds
        if mode == 'realistic':
            max_kcal_multiplier = self.PRUNING_KCAL_REALISTIC
        else:
            max_kcal_multiplier = self.PRUNING_KCAL_UNCONSTRAINED

        max_kcal_pruning = target.kcal * max_kcal_multiplier

        # Stato iniziale: pasto vuoto
        initial_state = BeamState(
            items=[],
            totals=NutrientValues(kcal=0, P=0, CHO=0, F=0, Fibre=0),
            score=self.calculate_score(
                NutrientValues(kcal=0, P=0, CHO=0, F=0, Fibre=0),
                target,
                [],
                mode,
                extra_penalty_fn
            )
        )

        beam = [initial_state]

        # Per ogni alimento
        for food_id in food_ids:
            # Genera candidati
            candidates = self.generate_quantity_candidates(food_id, meal_context, mode, must_include_food_db_ids)

            # Espandi beam
            new_beam = []

            for state in beam:
                for qty_amount, multiplier, violations in candidates:
                    # Crea nuovo stato
                    new_state = state.copy()

                    if qty_amount == 0:
                        # Non usare alimento: nessun item aggiunto
                        new_beam.append(new_state)
                        continue

                    # Calcola macros
                    macros = self.calculate_macros(food_id, qty_amount)

                    # Pruning kcal
                    new_kcal = new_state.totals.kcal + macros.kcal
                    if new_kcal > max_kcal_pruning:
                        continue  # Skip, troppo calorie

                    # Aggiorna totals
                    new_state.totals.kcal += macros.kcal
                    new_state.totals.P += macros.P
                    new_state.totals.CHO += macros.CHO
                    new_state.totals.F += macros.F
                    new_state.totals.Fibre += macros.Fibre

                    # Get food info
                    food = self.data.food_db_index[food_id]
                    mapping_entry = self.data.mapping_index.get(food_id)
                    portion_info = self.get_portion_info(food_id, meal_context)

                    # Create item
                    item = FoodItem(
                        food_db_id=food_id,
                        name=food['name'],
                        larn_portion_id=mapping_entry.get('larn_portion_id') if mapping_entry else None,
                        operational_portion_id=mapping_entry.get('operational_portion_id') if mapping_entry else None,
                        multiplier=multiplier,
                        qty=FoodQuantity(amount=qty_amount, unit=portion_info['unit']),
                        macros=macros,
                        violations=violations,
                        is_ingredient=portion_info['is_ingredient']
                    )

                    new_state.items.append(item)

                    # Calcola score
                    new_state.score = self.calculate_score(
                        new_state.totals,
                        target,
                        new_state.items,
                        mode,
                        extra_penalty_fn
                    )

                    new_beam.append(new_state)

            # Tieni solo i migliori beam_width stati
            new_beam.sort(key=lambda s: s.score)
            beam = new_beam[:beam_width]

            # Se beam vuoto, problema
            if not beam:
                # Fallback: ritorna stato iniziale
                return initial_state

        # Ritorna miglior stato
        return beam[0]

    def calculate_delta(self, target: NutrientValues, totals: NutrientValues) -> Dict[str, float]:
        """Calcola delta assoluto e percentuale"""
        delta = {}

        for nutrient in ['kcal', 'P', 'CHO', 'F', 'Fibre']:
            target_val = getattr(target, nutrient)
            actual_val = getattr(totals, nutrient)
            abs_delta = actual_val - target_val

            if target_val > 0:
                pct_delta = (abs_delta / target_val) * 100
            else:
                pct_delta = 0 if abs_delta == 0 else 999

            delta[nutrient] = round(abs_delta, 1)
            delta[f'{nutrient}_pct'] = round(pct_delta, 1)

        return delta

    def calculate_total_error(self, delta: Dict[str, float]) -> float:
        """
        Calcola errore totale per recommendation.
        Priorità: kcal > P > CHO > F > Fibre
        """
        total = 0
        for nutrient, weight in self.SCORE_WEIGHTS.items():
            pct_key = f'{nutrient}_pct'
            if pct_key in delta:
                total += abs(delta[pct_key]) * weight

        return total

    def choose_recommendation(self,
                            unconstrained: MatchResult,
                            realistic: MatchResult) -> str:
        """
        Sceglie quale versione raccomandare usando regola "+5% pareggio".

        REGOLA:
        1. Se realistic ha errore ≤ unconstrained → raccomanda realistic
           (stesso errore, ma quantità più pratiche)

        2. Se realistic ha errore > unconstrained MA differenza < 5%
           → raccomanda realistic (pareggio: praticità vince)

        3. Altrimenti → raccomanda unconstrained
           (differenza significativa, precisione vince)

        MOTIVAZIONE:
        - realistic usa quantità pratiche (170g yogurt, 20g marmellata)
        - unconstrained usa quantità precise (156.2g yogurt, 18.7g marmellata)
        - Se delta è simile, preferire praticità per facilità esecuzione

        CALCOLO ERRORE:
        errore = Σ (|delta_pct| × peso) per kcal, P, CHO, F, Fibre
        Con pesi: kcal=5, P=4, CHO=3, F=2, Fibre=1

        Args:
            unconstrained: MatchResult versione unconstrained
            realistic: MatchResult versione realistic

        Returns:
            'best_match_realistic' o 'best_match_unconstrained'

        Examples:
            >>> # CASO 1: Realistic uguale/migliore
            >>> unconstrained.delta = {'kcal_pct': -1.2, 'P_pct': +2.5}
            >>> realistic.delta = {'kcal_pct': -0.9, 'P_pct': +1.8}
            >>> choose_recommendation(unconstrained, realistic)
            'best_match_realistic'  # Realistic migliore, usa quello

            >>> # CASO 2: Pareggio (+5%)
            >>> # unconstrained: errore pesato = 15.0
            >>> # realistic: errore pesato = 15.6 (+4% rispetto a unconstrained)
            >>> choose_recommendation(unconstrained, realistic)
            'best_match_realistic'  # Entro 5%, pareggio → preferire praticità

            >>> # CASO 3: Differenza significativa
            >>> # unconstrained: errore pesato = 15.0
            >>> # realistic: errore pesato = 24.0 (+60% rispetto a unconstrained)
            >>> choose_recommendation(unconstrained, realistic)
            'best_match_unconstrained'  # Differenza troppo grande, precisione vince

            >>> # CASO 4: Target impossibile per realistic
            >>> # unconstrained: kcal 380 (-5%), P 28g (-12%)
            >>> # realistic: kcal 310 (-22%), P 20g (-37%)
            >>> choose_recommendation(unconstrained, realistic)
            'best_match_unconstrained'  # Realistic molto peggio, usa unconstrained
        """
        error_unconstrained = self.calculate_total_error(unconstrained.delta)
        error_realistic = self.calculate_total_error(realistic.delta)

        # Se realistic è uguale o migliore → realistic
        if error_realistic <= error_unconstrained:
            return 'best_match_realistic'

        # Se realistic aumenta errore < PAREGGIO_THRESHOLD_PCT → realistic (praticità vince)
        increase_pct = ((error_realistic - error_unconstrained) / error_unconstrained) * 100
        if increase_pct < self.PAREGGIO_THRESHOLD_PCT:
            return 'best_match_realistic'

        # Altrimenti unconstrained è significativamente migliore
        return 'best_match_unconstrained'

    def optimize_for_food_set(self,
                                target_nutrients: NutrientValues,
                                food_ids: List[str],
                                meal_context: str,
                                respect_limits: bool,
                                extra_penalty_fn: Optional[callable] = None,
                                must_include_food_db_ids: Optional[List[str]] = None) -> Tuple[List[FoodItem], NutrientValues, List[str]]:
        """
        Ottimizza per un dato set di alimenti usando beam search.

        Args:
            target_nutrients: Target nutrizionali
            food_ids: Lista food_db_ids da usare
            meal_context: "meal" o "snack"
            respect_limits: True per realistic, False per unconstrained

        Returns:
            (items, totals, violations_notes)
        """
        mode = 'realistic' if respect_limits else 'unconstrained'
        violations_notes = []

        # Run beam search
        best_state = self.beam_search(
            target=target_nutrients,
            food_ids=food_ids,
            meal_context=meal_context,
            mode=mode,
            beam_width=300,
            extra_penalty_fn=extra_penalty_fn,
            must_include_food_db_ids=must_include_food_db_ids
        )

        # Extract results
        items = best_state.items
        totals = best_state.totals

        # Check for unmapped foods (warnings)
        for food_id in food_ids:
            portion_info = self.get_portion_info(food_id, meal_context)
            if portion_info['mode'] == 'unmapped':
                violations_notes.append(f"⚠️ {food_id}: no portion mapping")

        return items, totals, violations_notes

    def balance_meal(self,
                    target: Dict[str, float],
                    meal_context: str = "meal",
                    allowed_food_db_ids: Optional[List[str]] = None,
                    extra_penalty_fn: Optional[callable] = None,
                    must_include_food_db_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Main entry point - bilanciamento pasto completo con vincoli LARN + PERSONAL_LIMITS.

        WORKFLOW:
        1. Converte target dict → NutrientValues
        2. Se allowed_food_db_ids non specificato → usa tutti i 49 alimenti in FOOD_DB
        3. Ottimizza versione UNCONSTRAINED (ignora PERSONAL_LIMITS max_qty)
           - Permette quantità oltre limiti realistici
           - Marca violations per alimenti che violano max_qty_g
        4. Ottimizza versione REALISTIC (rispetta PERSONAL_LIMITS)
           - Quantità pratiche (preferred_qty_g o snap a 5g)
           - Rispetta max_qty_g e context-dependent (snack_max vs meal_max)
        5. Sceglie recommendation usando regola "+5% pareggio"
        6. Genera notes formato "Problema → Causa → Soluzione" (max 6)

        SISTEMA VINCOLI (priority order):
        1. is_ingredient=true → quantità libere a step_g (es. passata 20g, 40g, 60g...)
        2. LARN portion → qty = standard_qty × multiplier (es. pasta 80g × 1.5 = 120g)
        3. OPERATIVE portion → qty = standard_qty × multiplier (es. burro arachidi 15g × 2)
        4. Unmapped → warning, alimento non usabile

        CONTEXT-DEPENDENT:
        - meal_context='snack' → usa snack_max_qty_g (es. prosciutto max 40g)
        - meal_context='meal' → usa meal_max_qty_g (es. prosciutto max 120g)

        Args:
            target: Target nutrizionali
                - Obbligatori: kcal, P, CHO, F
                - Opzionale: Fibre
                - Es: {'kcal': 450, 'P': 25, 'CHO': 60, 'F': 12, 'Fibre': 8}
            meal_context: Contesto pasto (default: "meal")
                - "meal": pasto principale (pranzo, cena)
                - "snack": spuntino (context-dependent usa snack_max)
            allowed_food_db_ids: Lista alimenti consentiti (opzionale)
                - Se None → usa tutti gli alimenti in FOOD_DB
                - Es: ['yogurt_greco_0_lipidi', 'mandorle', 'fette_biscottate']

        Returns:
            Dict con struttura:
            {
                'target': {...},  # Target input
                'best_match_unconstrained': {
                    'comment': "Soluzione ottimale matematica...",
                    'items': [
                        {
                            'food_db_id': '...',
                            'name': '...',
                            'larn_portion_id': '...',
                            'multiplier': 1.5,
                            'qty': {'amount': 120, 'unit': 'g'},
                            'macros': {...},
                            'violations': ['PERSONAL_LIMITS:max_qty_g']  # se viola
                        }
                    ],
                    'totals': {...},
                    'delta': {'kcal': -4, 'kcal_pct': -0.9, ...}
                },
                'best_match_realistic': {
                    'comment': "Soluzione con quantità realistiche...",
                    'items': [...],  # stessi field, ma NO violations
                    'totals': {...},
                    'delta': {...}
                },
                'recommendation': 'best_match_realistic' | 'best_match_unconstrained',
                'notes': [
                    "Problema → Causa → Soluzione",
                    ...  # max 6 righe
                ]
            }

        Examples:
            >>> # ESEMPIO 1: COLAZIONE standard
            >>> data = MealBalancerData(Path('data'))
            >>> balancer = MealBalancer(data)
            >>>
            >>> result = balancer.balance_meal(
            ...     target={'kcal': 450, 'P': 25, 'CHO': 60, 'F': 12, 'Fibre': 8},
            ...     meal_context='meal',
            ...     allowed_food_db_ids=[
            ...         'caffe_espresso',
            ...         'fette_biscottate',
            ...         'marmellata',
            ...         'yogurt_greco_0_lipidi',
            ...         'mandorle'
            ...     ]
            ... )
            >>>
            >>> # Output:
            >>> result['best_match_realistic']['items'] = [
            ...     {'food_db_id': 'yogurt_greco_0_lipidi', 'qty': {'amount': 170, 'unit': 'g'},
            ...      'multiplier': 1.36, 'macros': {'kcal': 170, 'P': 17, ...}},
            ...     {'food_db_id': 'fette_biscottate', 'qty': {'amount': 30, 'unit': 'g'},
            ...      'multiplier': 1.0, 'macros': {'kcal': 120, 'P': 3.6, ...}},
            ...     {'food_db_id': 'marmellata', 'qty': {'amount': 20, 'unit': 'g'},
            ...      'multiplier': 2.0, 'macros': {'kcal': 50, 'P': 0.1, ...}},
            ...     {'food_db_id': 'mandorle', 'qty': {'amount': 15, 'unit': 'g'},
            ...      'multiplier': 0.5, 'macros': {'kcal': 90, 'P': 3.2, ...}}
            ... ]
            >>> result['best_match_realistic']['totals'] = {
            ...     'kcal': 446, 'P': 25.5, 'CHO': 60.2, 'F': 12.1, 'Fibre': 8
            ... }
            >>> result['best_match_realistic']['delta'] = {
            ...     'kcal': -4, 'kcal_pct': -0.9,
            ...     'P': 0.5, 'P_pct': 2.0,
            ...     'CHO': 0.2, 'CHO_pct': 0.3,
            ...     'F': 0.1, 'F_pct': 0.8,
            ...     'Fibre': 0, 'Fibre_pct': 0
            ... }
            >>> result['recommendation'] = 'best_match_realistic'
            >>> result['notes'] = [
            ...     "Versione realistic raccomandata: delta simile a unconstrained, "
            ...     "quantità più pratiche."
            ... ]

            >>> # ESEMPIO 2: SPUNTINO con context-dependent
            >>> result = balancer.balance_meal(
            ...     target={'kcal': 250, 'P': 18, 'CHO': 20, 'F': 10, 'Fibre': 3},
            ...     meal_context='snack',  # ← context snack
            ...     allowed_food_db_ids=[
            ...         'prosciutto_crudo',           # context-dependent
            ...         'pane_integrale',
            ...         'formaggio_cremoso_spalmabile_light'  # context-dependent
            ...     ]
            ... )
            >>>
            >>> # Realistic: rispetta snack_max
            >>> result['best_match_realistic']['items'] = [
            ...     {'food_db_id': 'prosciutto_crudo', 'qty': {'amount': 40, 'unit': 'g'},
            ...      'multiplier': 0.8},  # snack_max 40g (NOT 120g meal_max)
            ...     {'food_db_id': 'formaggio_cremoso_spalmabile_light', 'qty': {'amount': 50, 'unit': 'g'},
            ...      'multiplier': 2.0},  # snack_max 50g
            ...     {'food_db_id': 'pane_integrale', 'qty': {'amount': 50, 'unit': 'g'},
            ...      'multiplier': 1.0}
            ... ]
            >>>
            >>> # Unconstrained: può violare
            >>> result['best_match_unconstrained']['items'] = [
            ...     {'food_db_id': 'prosciutto_crudo', 'qty': {'amount': 50, 'unit': 'g'},
            ...      'multiplier': 1.0,
            ...      'violations': ['PERSONAL_LIMITS:max_qty_g']},  # supera snack_max 40g
            ...     ...
            ... ]
            >>> result['notes'] = [
            ...     "Versione unconstrained viola limiti per: prosciutto_crudo.",
            ...     "Versione unconstrained raccomandata: delta significativamente migliore."
            ... ]

            >>> # ESEMPIO 3: INGREDIENT mode (passata step libero)
            >>> result = balancer.balance_meal(
            ...     target={'kcal': 650, 'P': 35, 'CHO': 85, 'F': 18, 'Fibre': 10},
            ...     meal_context='meal',
            ...     allowed_food_db_ids=[
            ...         'pasta_di_semola',
            ...         'salsa_di_carne_manzo',
            ...         'passata_di_pomodoro',  # is_ingredient=true
            ...         'olio_di_oliva_extra_vergine',
            ...         'zucchine_crude'
            ...     ]
            ... )
            >>>
            >>> # Passata usa step libero (20g, 40g, 60g, 80g, 100g)
            >>> # NON vincolato a 200g × multiplier (porzione operativa)
            >>> result['best_match_realistic']['items'] = [
            ...     {'food_db_id': 'pasta_di_semola', 'qty': {'amount': 100, 'unit': 'g'},
            ...      'multiplier': 1.25},
            ...     {'food_db_id': 'salsa_di_carne_manzo',
            ...      'qty': {'amount': 100, 'unit': 'g'}, 'multiplier': 0.5},
            ...     {'food_db_id': 'passata_di_pomodoro', 'qty': {'amount': 80, 'unit': 'g'},
            ...      'multiplier': None, 'is_ingredient': True},  # step 20g
            ...     {'food_db_id': 'olio_di_oliva_extra_vergine', 'qty': {'amount': 15, 'unit': 'g'},
            ...      'multiplier': 1.67},
            ...     {'food_db_id': 'zucchine_crude', 'qty': {'amount': 200, 'unit': 'g'},
            ...      'multiplier': 1.0}
            ... ]
        """
        # Convert target to NutrientValues
        target_nutrients = NutrientValues(
            kcal=target.get('kcal', 0),
            P=target.get('P', 0),
            CHO=target.get('CHO', 0),
            F=target.get('F', 0),
            Fibre=target.get('Fibre', 0)
        )

        # Se non specificati, usa tutti gli alimenti disponibili
        if not allowed_food_db_ids:
            allowed_food_db_ids = list(self.data.food_db_index.keys())

        # Optimize unconstrained (ignora PERSONAL_LIMITS)
        items_uncon, totals_uncon, violations_uncon = self.optimize_for_food_set(
            target_nutrients=target_nutrients,
            food_ids=allowed_food_db_ids,
            meal_context=meal_context,
            respect_limits=False,
            extra_penalty_fn=extra_penalty_fn,
            must_include_food_db_ids=must_include_food_db_ids
        )

        delta_uncon = self.calculate_delta(target_nutrients, totals_uncon)

        unconstrained = MatchResult(
            items=items_uncon,
            totals=totals_uncon,
            delta=delta_uncon
        )

        # Optimize realistic (rispetta PERSONAL_LIMITS)
        items_real, totals_real, violations_real = self.optimize_for_food_set(
            target_nutrients=target_nutrients,
            food_ids=allowed_food_db_ids,
            meal_context=meal_context,
            respect_limits=True,
            extra_penalty_fn=extra_penalty_fn,
            must_include_food_db_ids=must_include_food_db_ids
        )

        delta_real = self.calculate_delta(target_nutrients, totals_real)

        realistic = MatchResult(
            items=items_real,
            totals=totals_real,
            delta=delta_real
        )

        # Choose recommendation
        recommendation = self.choose_recommendation(unconstrained, realistic)

        # Generate notes
        notes = self._generate_notes(
            target_nutrients,
            unconstrained,
            realistic,
            recommendation,
            violations_uncon + violations_real
        )

        return {
            'target': target_nutrients.to_dict(),
            'best_match_unconstrained': unconstrained.to_dict(
                "Soluzione ottimale matematica (ignora PERSONAL_LIMITS)"
            ),
            'best_match_realistic': realistic.to_dict(
                "Soluzione con quantità realistiche (rispetta PERSONAL_LIMITS)"
            ),
            'recommendation': recommendation,
            'notes': notes
        }

    def _generate_notes(self,
                       target: NutrientValues,
                       unconstrained: MatchResult,
                       realistic: MatchResult,
                       recommendation: str,
                       violations_notes: List[str]) -> List[str]:
        """
        Genera notes formato: Problema → Causa → Soluzione
        Max 6 righe, zero giudizi.
        """
        notes = []

        # Check se ci sono gap significativi (>10%)
        for nutrient in ['kcal', 'P', 'CHO', 'F', 'Fibre']:
            target_val = getattr(target, nutrient)
            delta_key = f'{nutrient}_pct'

            # Check realistic version
            delta_pct = realistic.delta.get(delta_key, 0)

            if abs(delta_pct) > 10:
                actual = getattr(realistic.totals, nutrient)
                notes.append(
                    f"Target {nutrient} {target_val} non raggiunto "
                    f"({actual:.1f}, {delta_pct:+.1f}%)."
                )

        # Violations
        if any(item.violations for item in unconstrained.items):
            violated = [item.food_db_id for item in unconstrained.items if item.violations]
            notes.append(
                f"Versione unconstrained viola limiti per: {', '.join(violated)}."
            )

        # Recommendation reasoning
        if recommendation == 'best_match_realistic':
            notes.append(
                "Versione realistic raccomandata: delta simile a unconstrained, "
                "quantità più pratiche."
            )
        else:
            notes.append(
                "Versione unconstrained raccomandata: delta significativamente migliore."
            )

        # Warnings
        for note in violations_notes:
            if note not in notes:
                notes.append(note)

        # Limit to 6
        return notes[:6]


# ============================================================================
# CLI INTERFACE
# ============================================================================

def main():
    """Main CLI entry point"""
    print("🍽️  Meal Balancer v1.0")
    print("=" * 60)

    # Load data
    base_dir = Path(__file__).resolve().parents[2]
    data_dir = base_dir / 'data'

    print("\n📂 Loading data files...")
    data = MealBalancerData(data_dir)
    print("✅ All data loaded successfully")

    # Test info
    print("\n📊 Data Summary:")
    print(f"  - FOOD_DB: {len(data.food_db_index)} foods")
    print(f"  - FOOD_CATALOG strict mode: {'yes' if data.catalog_active else 'no'}")
    print(f"  - LARN_PORTIONS: {len(data.larn_index)} portions (+ variants)")
    print(f"  - OPERATIVE_PORTIONS: {len(data.operative_index)} portions")
    print(f"  - MAPPING: {len(data.mapping_index)} mappings")
    print(f"  - PERSONAL_LIMITS: {len(data.personal_limits_index)} limits")

    # Create balancer
    balancer = MealBalancer(data)

    # Test case: COLAZIONE
    print("\n🧪 Test Case: COLAZIONE 450 kcal")
    print("-" * 60)

    target = {
        'kcal': 450,
        'P': 25,
        'CHO': 60,
        'F': 12,
        'Fibre': 8
    }

    result = balancer.balance_meal(
        target=target,
        meal_context='meal',
        allowed_food_db_ids=[
            'caffe_espresso',
            'fette_biscottate',
            'marmellata',
            'yogurt_greco_0_lipidi',
            'mandorle'
        ]
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    print("\n✅ meal_balancer.py is operational!")
    print("Next step: Implement optimization algorithm")


if __name__ == '__main__':
    main()
