# Meal Balancer

Sistema di bilanciamento pasti basato su vincoli LARN, FOOD_DB e limiti personali con algoritmo beam search.

---

## 🏷️ Version 1.0 - STABLE

**Status**: Production-ready per uso personale
**Algorithm**: Beam Search discrete optimizer (width 300, pruning intelligente)
**Test Coverage**: 5/5 regression tests passed ✅
**Last Updated**: 2026-02-12

### 🔧 Configurable Constants

Tutti i parametri chiave sono ora configurabili come costanti in `MealBalancer` class:

```python
# Score weights (priorità nutrienti)
SCORE_WEIGHTS = {'kcal': 5.0, 'P': 4.0, 'CHO': 3.0, 'F': 2.0, 'Fibre': 1.0}

# Pruning thresholds
PRUNING_KCAL_REALISTIC = 1.2        # realistic può arrivare a 1.2× target kcal
PRUNING_KCAL_UNCONSTRAINED = 1.4    # unconstrained può arrivare a 1.4× target kcal

# Beam search
DEFAULT_BEAM_WIDTH = 300

# Pareggio rule
PAREGGIO_THRESHOLD_PCT = 5.0        # Se realistic aumenta errore <5% → raccomanda realistic

# Snapping
SNAP_TOLERANCE_PCT = 0.2            # 20% tolerance per snap a preferred_qty
SNAP_STEP_REALISTIC = 5.0           # Step default per realistic (g)
SNAP_STEP_UNCONSTRAINED = 2.5       # Step default per unconstrained (g)
```

### 🧪 Regression Tests

5 test automatici garantiscono stabilità v1.0:

1. **colazione_standard** — Baseline con 5 alimenti standard
2. **snack_context_dependent** — Context-aware limits (snack_max vs meal_max)
3. **ingredient_mode** — is_ingredient=true con step libero
4. **target_impossibile** — Failure mode gracefully handled
5. **pareggio_rule** — +5% recommendation threshold

Run tests: `python3 tests/run_regression_tests.py`

---

## 🏷️ Version 2.0 - Feature Complete

**Status**: FROZEN - Production-ready
**Date**: 2026-02-12
**Test Coverage**: 32/32 tests passed ✅

### Architecture Freeze

- **Solver core frozen**: beam_search + scoring + pruning unchanged
- **Orchestrator stable**: plan_builder.py + constraint layers complete
- **Validation layer complete**: data_validator.py validates all 10 JSON files
- **No new constraint layers planned**: Existing patterns sufficient

### Implemented Constraint Layers

1. **Volume Penalty** (Soft - Callback): Penalty for excessive vegetable volume
   - Pattern: extra_penalty_fn passed to solver
   - Layer: Orchestrator-only
   - Status: Stable

2. **Must Include** (Hard - Candidate Filter): Required foods in meal
   - Pattern: Candidate generation + skip qty=0
   - Layer: Solver API extended
   - Status: Stable

3. **Protein Floor** (Hard - Target Adjustment): Minimum protein per meal slot
   - Pattern: Target bumped before solver call
   - Layer: Orchestrator-only (purest implementation)
   - Status: Stable

### Rule for Future Constraints

**New constraints MUST follow existing patterns:**
- Soft constraint → Callback pattern (extra_penalty_fn)
- Hard structural → Candidate filter (generate_quantity_candidates)
- Hard target → Target adjustment (orchestrator-only)

**No new patterns.** Architecture is stable and complete.

---

## 📌 Cos'è (e cosa NON è)

### ✅ Cosa È

- **Planner discreto** che ottimizza combinazioni di alimenti per raggiungere target nutrizionali
- Usa **vincoli scientifici** (LARN - Livelli di Assunzione di Riferimento di Nutrienti)
- Rispetta **limiti personali** (quantità realistiche, contesto snack/meal)
- Algoritmo **beam search** con pruning intelligente
- Produce **due soluzioni**: ottimo matematico vs quantità realistiche

### ❌ Cosa NON È

- **Non è un nutrizionista**: non prescrive diete né dà consigli medici
- **Non inventa dati**: usa SOLO valori da FOOD_DB.json (fonti: USDA, CREA, etichette)
- **Non crea alimenti**: se un alimento non esiste in FOOD_DB, non può usarlo
- **Non giudica target**: se chiedi P 50g con 200 kcal, ti dice che è impossibile ma non "è troppo alto"

---

## 🗂️ Architettura: 5 JSON come Single Source of Truth

```
data/
├── FOOD_DB.json                    # Nutrienti (kcal, P, CHO, F, Fibre)
├── LARN_PORTIONS.json              # Porzioni standard LARN (es: pasta 80g, yogurt 125g)
├── FOOD_DB_TO_LARN_MAPPING.json    # Mapping food_db_id → larn_portion_id
├── OPERATIVE_PORTIONS.json         # Porzioni operative (fallback per alimenti senza LARN)
└── PERSONAL_LIMITS.json            # Limiti realistici + context (snack/meal)
```

### 1. FOOD_DB.json

**Scopo**: Unica fonte di verità per valori nutrizionali.

**Struttura**:
```json
{
  "foods": [
    {
      "id": "yogurt_greco_0",
      "name": "Yogurt greco 0%",
      "reference": { "amount": 170, "unit": "g" },
      "nutrients_per_reference": {
        "kcal": 100, "P": 17, "CHO": 6, "F": 0, "Fibre": 0
      },
      "data_source": "Etichetta"
    }
  ]
}
```

**Regole**:
- Reference amount può variare (100g, 125g, 170g) → calcolo proporzionale automatico
- Se alimento non esiste → non può essere usato (no invenzioni)

### 2. LARN_PORTIONS.json

**Scopo**: Porzioni standard validate scientificamente (Tabella 2 LARN).

**Struttura**:
```json
{
  "portions": [
    {
      "id": "yogurt",
      "group": "LATTE_E_DERIVATI",
      "item": "yogurt e altri latti fermentati",
      "standard": { "qty": 125, "unit": "g" },
      "practical": ["1 vasetto standard"]
    }
  ]
}
```

**Varianti**: Es. pasta normale 80g vs pasta ripiena 125g.

### 3. FOOD_DB_TO_LARN_MAPPING.json

**Scopo**: Collega food_db_id a porzione LARN o operativa.

**Struttura**:
```json
{
  "mapping": [
    {
      "food_db_id": "yogurt_greco_0",
      "food_db_name": "Yogurt greco 0%",
      "larn_portion_id": "yogurt",
      "note": "125g = vasetto standard."
    }
  ]
}
```

**Priorità**: LARN > OPERATIVE > unmapped (errore).

### 4. OPERATIVE_PORTIONS.json

**Scopo**: Porzioni operative SOLO per alimenti senza LARN univoca.

**Esempio**: Passata di pomodoro (può essere verdura o sugo → no LARN univoca).

### 5. PERSONAL_LIMITS.json

**Scopo**: Vincoli realistici personali (max quantità, preferred, context snack/meal).

**Struttura**:
```json
{
  "limits": [
    {
      "food_db_id": "yogurt_greco_0",
      "preferred_qty_g": [100, 125, 170],
      "max_qty_g": 170,
      "snack_max_qty_g": 125,
      "meal_max_qty_g": 170,
      "context_dependent": true,
      "note": "170g = vasetto monoporzione."
    },
    {
      "food_db_id": "passata_di_pomodoro",
      "preferred_qty_g": [50, 80, 100],
      "max_qty_g": 100,
      "step_g": 20,
      "is_ingredient": true,
      "note": "Ingrediente/salsa: quantità libere a step 20g."
    }
  ]
}
```

**Tipi di limiti**:
- **Standard**: `max_qty_g` + `preferred_qty_g`
- **Context-dependent**: `snack_max_qty_g` vs `meal_max_qty_g`
- **Ingredient**: `is_ingredient=true` → step libero (es: passata 80g, non 200g×multiplier)

---

## 🔄 Algoritmo: Beam Search con Vincoli

### Input

```python
{
  "target": { "kcal": 450, "P": 25, "CHO": 60, "F": 12, "Fibre": 8 },
  "meal_context": "meal",  # "meal" | "snack"
  "allowed_food_db_ids": ["yogurt_greco_0", "fette_biscottate", ...]
}
```

### Output

```python
{
  "target": {...},
  "best_match_unconstrained": {
    "comment": "Soluzione ottimale matematica (ignora PERSONAL_LIMITS)",
    "items": [
      {
        "food_db_id": "fette_biscottate",
        "name": "Fette biscottate",
        "qty": { "amount": 75, "unit": "g" },
        "macros": { "kcal": 290.2, "P": 8.5, ... },
        "larn_portion_id": "cereali_colazione_fette",
        "multiplier": 2.5,
        "violations": ["PERSONAL_LIMITS:max_qty_g"]  # ← Viola max 60g
      }
    ],
    "totals": { "kcal": 472.8, "P": 27.1, ... },
    "delta": { "kcal": 22.8, "kcal_pct": 5.1, "P": 2.1, "P_pct": 8.4, ... }
  },
  "best_match_realistic": {
    "comment": "Soluzione con quantità realistiche (rispetta PERSONAL_LIMITS)",
    "items": [
      {
        "food_db_id": "fette_biscottate",
        "qty": { "amount": 60, "unit": "g" },  # ← Rispetta max 60g
        "macros": {...},
        "multiplier": 2.0
      },
      {
        "food_db_id": "marmellata",
        "qty": { "amount": 15, "unit": "g" },  # ← Compensazione CHO
        ...
      }
    ],
    "totals": { "kcal": 446, "P": 25.5, ... },
    "delta": { "kcal": -4, "kcal_pct": -0.9, "P": 0.5, "P_pct": 1.8, ... }
  },
  "recommendation": "best_match_realistic",
  "notes": [
    "Versione unconstrained usa 75g fette (viola max 60g).",
    "Versione realistic rispetta 60g max + aggiunge marmellata per compensare CHO.",
    "Delta quasi identico. Preferisci realistic per praticità."
  ]
}
```

### Recommendation Rule

```python
if error_realistic <= error_unconstrained:
    return 'best_match_realistic'
elif (error_realistic - error_unconstrained) / error_unconstrained < 0.05:
    return 'best_match_realistic'  # +5% pareggio rule
else:
    return 'best_match_unconstrained'
```

### Beam Search Parameters

- **Beam width**: 300 stati
- **Pruning kcal**:
  - realistic: scarta stati con kcal > target × 1.2
  - unconstrained: scarta stati con kcal > target × 1.4
- **Opzione 0**: Ogni alimento può essere escluso (qty=0) → optimizer intelligente

### Score Function

```python
score = Σ(|delta_pct| × peso)

Pesi (priorità):
  kcal: 5.0
  P: 4.0
  CHO: 3.0
  F: 2.0
  Fibre: 1.0

# Penalità praticità (realistic):
+ (num_alimenti - 7) × 5  se num_alimenti > 7
+ 0.5 per ogni qty non in preferred_qty_g
```

---

## 🎯 Regole Chiave

### 1. Priorità Quantità

```
1. Se PERSONAL_LIMITS.is_ingredient=true
   → qty libera, quantizzata a step_g, max_qty_g

2. Altrimenti se mapping.larn_portion_id != null
   → qty = LARN.standard_qty × multiplier
   - multipliers default: [0.25, 0.5, 0.75, 1, 1.25, 1.5, 2, 2.5, 3]
   - yogurt: anche 0.8 (per 100g)

3. Altrimenti se mapping.operational_portion_id != null
   → qty = OPERATIVE.standard_qty × multiplier

4. Altrimenti → unmapped (warning)
```

### 2. Context-Dependent (Snack vs Meal)

Se `context_dependent=true`:
```python
if meal_context == 'snack':
    max_qty = snack_max_qty_g  # Es: prosciutto 40g
else:
    max_qty = meal_max_qty_g   # Es: prosciutto 120g
```

### 3. Snapping Quantità Realistiche

**Realistic**:
- Se `preferred_qty_g` disponibile e delta < 20% → snap al più vicino
- Altrimenti: snap a 5g

**Unconstrained**:
- Snap a 2.5g (più preciso ma praticabile)

**Esempio**:
```
156.2g yogurt → 170g (preferred) ✅
12.5g marmellata → 10g o 15g (step 5g) ✅
83g passata → 80g (step 20g) ✅
```

### 4. Ingredient Mode

Se `is_ingredient=true` (es: passata, olio come condimento):
- **NON** vincolare a multipli di porzione LARN/operativa
- Usa quantità libere a `step_g`
- Esempio: passata 80g (step 20g), non 200g×0.4

### 5. Violations Tracking

**Unconstrained** può violare `max_qty_g` fino a 2× e marca:
```json
"violations": ["PERSONAL_LIMITS:max_qty_g"]
```

**Realistic** NON può mai violare.

---

## 📚 Esempi

### Esempio 1: Colazione (target standard)

**Input**:
```python
python3 scripts/meal_balancer.py
# Default test: colazione 450 kcal, P 25g
```

**Output** (simplified):
```
REALISTIC:
- Fette biscottate: 60g (2× LARN 30g)
- Marmellata: 15g (1.5× LARN 10g)
- Yogurt greco: 170g (1.36× LARN 125g, snappato a preferred)
- Mandorle: 15g (0.5× LARN 30g)

Totals: 446 kcal | P 25.5g | CHO 61.0g | F 11.4g
Delta: kcal -0.9% | P +1.8%  ← QUASI PERFETTO!
```

### Esempio 2: Ingredient Mode (passata step libero)

**Input**:
```python
{
  "target": { "kcal": 650, "P": 35, "CHO": 85, "F": 18 },
  "meal_context": "meal",
  "allowed_food_db_ids": [
    "pasta_secca_di_semola",
    "passata_di_pomodoro",
    "olio_evo",
    "zucchine_crude"
  ]
}
```

**Output**:
```
REALISTIC:
- Pasta: 100g (1.25× LARN 80g)
- Passata: 100g (is_ingredient=true, step 20g, max 100g) ✅
- Olio: 15g (max 15g rispettato) ✅
- Zucchine: 600g

Delta: kcal -5.0%
```

**Verifica**: Passata usa step 20g (80g, 100g validi), non 200g×multiplier.

### Esempio 3: Context-Dependent (snack vs meal)

**Input SNACK**:
```python
{
  "target": { "kcal": 250, "P": 18, "CHO": 20, "F": 10 },
  "meal_context": "snack",
  "allowed_food_db_ids": [
    "prosciutto_crudo",
    "pane_integrale",
    "formaggio_spalmabile_light"
  ]
}
```

**Output**:
```
REALISTIC (snack):
- Prosciutto: 40g (snack_max 40g) ✅
- Pane: 50g
- Spalmabile: 25g (snack_max 50g) ✅

UNCONSTRAINED:
- Prosciutto: 50g → VIOLATION: PERSONAL_LIMITS:max_qty_g ✅

Delta realistic: kcal +3.7%, P -1.9%
```

**Con meal_context="meal"**: Prosciutto potrebbe arrivare a 120g.

---

## 🐛 Troubleshooting

### Target Impossibile

**Esempio**: 200 kcal e P 50g con alimenti normali.

**Output atteso**:
```json
"notes": [
  "Target P 50g non raggiunto (18.2g, -63.6%).",
  "Causa: con budget 200 kcal, max P ottenibile ~20-25g con proteine pure.",
  "Soluzione: aumentare kcal target o usare integratori proteici."
]
```

**NON giudica** ("troppo alto"), solo vincolo matematico.

### Perché un Alimento è Escluso?

**Opzione 0**: L'optimizer può scegliere qty=0 (non usare alimento).

**Motivi**:
1. **Kcal pruning**: Aggiungerlo sfora kcal target × 1.2/1.4
2. **Score peggiore**: Include alimento peggiora il delta totale
3. **Contributo inutile**: Es. caffè 2 kcal, P 0.1g → non aiuta target

**Esempio**: Ragù escluso in Test B perché pasta + passata già vicine a 650 kcal target.

### Alimento Unmapped

**Errore**:
```
"⚠️ food_db_id: no portion mapping"
```

**Fix**:
1. Aggiungi entry in `data/FOOD_DB_TO_LARN_MAPPING.json`:
```json
{
  "food_db_id": "nuovo_alimento",
  "larn_portion_id": "porzione_larn_corrispondente"
}
```
2. Se no LARN univoca, crea porzione operativa in `OPERATIVE_PORTIONS.json`
3. Se serve limit personalizzato, aggiungi in `PERSONAL_LIMITS.json`

---

## 🛠️ Come Aggiungere un Nuovo Alimento

### Step 1: FOOD_DB.json

```json
{
  "id": "nuovo_alimento",
  "name": "Nome Alimento",
  "reference": { "amount": 100, "unit": "g" },
  "nutrients_per_reference": {
    "kcal": 250, "P": 20, "CHO": 30, "F": 5, "Fibre": 3
  },
  "data_source": "USDA"
}
```

### Step 2: FOOD_DB_TO_LARN_MAPPING.json

```json
{
  "food_db_id": "nuovo_alimento",
  "food_db_name": "Nome Alimento",
  "larn_portion_id": "carne_bianca",  // Se esiste LARN corrispondente
  "note": "100g = porzione LARN."
}
```

### Step 3: PERSONAL_LIMITS.json (opzionale)

```json
{
  "food_db_id": "nuovo_alimento",
  "preferred_qty_g": [100, 150, 200],
  "max_qty_g": 200,
  "step_g": 50,
  "note": "Max 200g per controllo volume."
}
```

### Step 4: Validazione

```bash
python3 scripts/validate_meal_data.py
```

**Verifica**:
- ✅ 100% coverage (nessun unmapped)
- ✅ Nessun errore di riferimenti

---

## 🧪 Testing

### Run Test Suite

```bash
python3 scripts/test_meal_balancer.py
```

**Test inclusi**:
- Test B: Ingredient mode (passata step libero)
- Test A: Context-dependent (snack vs meal)

### Quick Test

```bash
python3 scripts/meal_balancer.py
# Esegue test default: colazione 450 kcal
```

---

## 📖 API Reference

### Main Entry Point

```python
from scripts.meal_balancer import MealBalancerData, MealBalancer

# Load data
data = MealBalancerData(Path('data'))
balancer = MealBalancer(data)

# Balance meal
result = balancer.balance_meal(
    target={
        'kcal': 450,
        'P': 25,
        'CHO': 60,
        'F': 12,
        'Fibre': 8
    },
    meal_context='meal',  # 'meal' | 'snack'
    allowed_food_db_ids=[
        'yogurt_greco_0',
        'fette_biscottate',
        'mandorle'
    ]
)
```

### Output Structure

```python
{
  'target': {...},
  'best_match_unconstrained': {
    'comment': str,
    'items': [FoodItem],
    'totals': NutrientValues,
    'delta': Dict[str, float]
  },
  'best_match_realistic': {
    'comment': str,
    'items': [FoodItem],
    'totals': NutrientValues,
    'delta': Dict[str, float]
  },
  'recommendation': 'best_match_realistic' | 'best_match_unconstrained',
  'notes': List[str]  # Max 6, formato Problema→Causa→Soluzione
}
```

---

## 🔍 Performance

**Benchmark** (colazione 5 alimenti):
- Beam width: 300
- Candidati per alimento: 4-6
- Tempo: < 1 secondo
- Memoria: < 50 MB

**Scalabilità**:
- OK fino a 10 alimenti per pasto
- Oltre 10: aumentare beam_width o split in sub-pasti

---

## ✅ Validazione

Sistema validato con:
- ✅ Ingredient mode (passata step 20g)
- ✅ Context-dependent (snack 40g vs meal 120g prosciutto)
- ✅ Snapping quantità (170g yogurt invece di 156.2g)
- ✅ Violations tracking (unconstrained marca violazioni)
- ✅ Opzione 0 smart (esclude alimenti inutili)
- ✅ Delta < 2% su nutrienti principali

---

## 📜 License

Parte di Training Vantage - Sistema personale di gestione allenamento running + nutrizione.

---

## 🤝 Contributing

Per modifiche ai dati:
1. Modifica JSON file in `data/`
2. Run `python3 scripts/validate_meal_data.py`
3. Se passa, commit

Per modifiche algoritmo:
1. Modifica `scripts/meal_balancer.py`
2. Run `python3 scripts/test_meal_balancer.py`
3. Verifica delta non peggiora

---

## 📞 Support

Per domande tecniche: vedi `training-vantage-prd.md` (PRD completo).
