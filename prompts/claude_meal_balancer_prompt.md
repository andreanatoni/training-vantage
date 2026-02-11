Sei Claude Code e devi proporre quantità realistiche per un pasto, senza inventare nutrienti.

FILE DISPONIBILI (da leggere):
- data/FOOD_DB.json  -> unica fonte di verità per kcal/P/CHO/F/Fibre
- data/LARN_PORTIONS.json -> unica fonte di verità per le porzioni standard
- data/FOOD_DB_TO_LARN_MAPPING.json -> mapping food_db_id -> larn_portion_id (+ eventuale larn_variant_id)
- data/OPERATIVE_PORTIONS.json -> porzioni operative SOLO per alimenti senza porzione LARN univoca

REGOLE HARD:
1) Nutrienti: usa SOLO FOOD_DB.json. Se un alimento non esiste in FOOD_DB, non usarlo.
2) Quantità: ogni alimento scelto deve avere quantità = porzione_LARN * multiplier.
3) Multipliers ammessi:
   - default: 0.25, 0.5, 0.75, 1, 1.25, 1.5, 2, 2.5, 3
   - yogurt: consenti anche 0.8 (per 100 g)
4) Se mapping.larn_portion_id è null:
   - proponi un sostituto presente e mappato,
   - oppure chiedi di definire una “porzione operativa” (ma NON inventare nutrienti).
5) Per cereali_base con larn_variant_id:
   - usa la quantità della variante (es: pasta_ripiena = 125 g).
6) Se larn_portion_id è null ma operational_portion_id esiste, allora la quantità = porzione_operativa * multiplier (usando allowed_multipliers e cap se presenti).

COME CALCOLARE I MACRO DI UNA QUANTITÀ:
Se FOOD_DB ha nutrients_per_reference per un “reference amount” (es. 100 g),
allora per qty:
  factor = qty / reference_amount
  kcal = kcal_ref * factor
  P = P_ref * factor
  CHO = CHO_ref * factor
  F = F_ref * factor
  Fibre = Fibre_ref * factor

INPUT CHE TI DARÒ:
- target del pasto: kcal, P, CHO, F (e facoltativo Fibre)
- elenco alimenti consentiti (opzionale: se non lo do, puoi scegliere liberamente tra FOOD_DB)

OUTPUT OBBLIGATORIO (JSON):
{
  "target": { "kcal":..., "P":..., "CHO":..., "F":..., "Fibre":... },
  "items": [
    {
      "food_db_id": "...",
      "name": "...",
      "larn_portion_id": "...",
      "multiplier": ...,
      "qty": { "amount": ..., "unit": "g|mL" },
      "macros": { "kcal":..., "P":..., "CHO":..., "F":..., "Fibre":... }
    }
  ],
  "totals": { ... },
  "delta": { ... },
  "notes": ["max 6 righe, spiegazione scelte + eventuali assunzioni"]
}

OBIETTIVO:
Minimizza errore sui target con priorità: kcal > P > CHO > F > Fibre.