# Training Vantage

CLI per gestione integrata di:
- running plan
- nutrizione
- composizione corporea
- food database

## Quick Start

```bash
# Help
./tv help

# Stato atleta attivo
./tv status

# Misurazioni e zone
./tv weigh 68.5 13.0 "check"
./tv zones
./tv zones 18:15 "test 5k"

# Setup running (crea/aggiorna profilo atleta)
./tv running setup
./tv running setup --no-history

# Generazione running plan
./tv running generate --from 2026-03-01 --to 2026-06-30 --goal-race 2026-10-18
./tv running week 1
./tv running month 2026-03
./tv running summary

# Setup template nutrizione base atleta
./tv nutrition setup-base

# Piani nutrizione
./tv plan rest
./tv plan --all
./tv plan week 2026-W11
./tv plan month 2026-03
```

## Multi-Atleta

- Context esplicito: `./tv --athlete <id> <command>`
- Se non passi `--athlete`, il context e' `default`
- Eccezioni wizard:
  - `./tv running setup`: se il context e' `default`, il `Nome atleta` inserito diventa la cartella target
  - `./tv nutrition setup-base`: stesso comportamento
- Runtime per atleta:
  - `data/athletes/<id>/...`
  - `knowledge/athletes/<id>/...`
  - `plans/nutrition/athletes/<id>/...`

## Integrazione Strict Running↔Nutrition

`status`, `plan week/month` e `running generate` usano config strict per atleta:
- `data/athletes/<id>/INTEGRATION_CONFIG.json`

Contiene:
- mapping `day_type -> categoria nutrizione`
- modello costo energetico (`running_kcal_per_kg_per_km`, `strength_base_kcal`, moltiplicatori per day_type)
- `race_calendar`
- soglie alert/status

`running setup` crea/aggiorna automaticamente questo file.

`./tv plan week/month` passa anche `phase` e `workout_label` dal `running_plan` al motore nutrizione.
Se in `NUTRITION_ENGINE_CONFIG.json` e' presente `phase_adjustments`, il deficit/guardrail puo' essere corretto per fase (es. `taper`, `race`).

## Nutrizione

### Path primario
- Path supportato: `./tv plan ...`
- `python3 scripts/cli.py plan ...` e' deprecato e non supportato (usa `./tv plan ...`)
- stack planner storico (`piano_base_parser`, `option_generator`, `category_plan_generator`, ecc.) e' in `scripts/legacy/planner/` (maintenance-only, non path runtime principale)

### Setup base
- `./tv nutrition setup-base` crea/aggiorna:
  - `data/athletes/<id>/nutrition_base_template.json`
  - `knowledge/athletes/<id>/nutrition-base-template.md`
- Template senza grammature, opzioni rigide (no merge), mapping ingredienti via `food_db_id`

### Generazione piani
- Giornaliero categoria: `./tv plan <categoria>`
- Settimanale da running plan: `./tv plan week <YYYY-Www>`
- Mensile da running plan: `./tv plan month <YYYY-MM>`
- Build/migrazione meal options strutturati: `./tv plan build-options` (genera `knowledge/meal_options/*.json`)

Path primario planner:
- `./tv plan ...` legge `knowledge/meal_options/<categoria>.json`
- se manca il JSON fallisce con errore e richiede `./tv plan build-options`
- implementazione dominio: `scripts/nutrition/*.py`

Output:
- `plans/nutrition/athletes/<id>/*.md`
- `plans/nutrition/athletes/<id>/*.json`

## Food DB e Mapping LARN

### Food DB
- Master: `data/FOOD_DB.json`
- Vista markdown generata: `knowledge/food-db.md`
- Sync/check:
  - `./tv food sync`
  - `./tv food check`

### Import e sync fonti
- CREA: `food crawl-index`, `food import-crea`, `food rebuild-from-crea`
- Dietabit: `food sync-dietabit [--no-merge]`

### Mapping LARN (Path Attivo)
- Import massivo da file mappato:
  - `./tv food import-mapped --dry-run --strict-complete`
  - `./tv food import-mapped --file data/food_mapped.md --strict-complete`
- Export revisione in Excel:
  - `data/LARN_MANUAL_MAPPING.xlsx` (colonna D con dropdown `larn_portion_id`)

### Legacy Archiviato
- Pipeline LARN one-by-one (`auto-map-larn`, `map-larn`) e' stata archiviata.
- Artefatti e script storici sono in `archive/larn-pipeline/`.
- Path supportato: `food import-mapped` -> `food build-catalog` -> `food validate-data`.

### Active set per atleta
- `./tv food build-active`
- Genera `data/athletes/<id>/FOOD_DB_ACTIVE.json` da template+piani atleta
- E' una cache derivata (non sostituisce `FOOD_DB.json`)

### Catalogo derivato (shadow)
- `./tv food build-catalog`
- Genera `data/FOOD_CATALOG.json` come vista derivata da `FOOD_DB + FOOD_DB_TO_LARN_MAPPING + LARN_PORTIONS + PERSONAL_LIMITS`
- `meal_balancer` lo usa in strict mode (se manca/incoerente il runtime fallisce)
- Non sostituisce i file sorgente: resta una vista derivata per semplificazione progressiva
- `./tv food validate-data` valida coerenza completa dataset, incluso allineamento `FOOD_CATALOG` vs file sorgente


## Struttura Progetto (Essenziale)

```text
training-vantage/
├── tv
├── scripts/
│   ├── nutrition/
│   ├── running/
│   ├── tracking/
│   ├── food/
│   └── common/
├── data/
│   ├── athletes/<id>/
│   └── templates/
├── knowledge/
├── plans/nutrition/athletes/<id>/
└── sources/
```

## Sviluppo e Verifica

```bash
# smoke principali
./tv help
./tv status
./tv running summary
./tv food check

# test python
python3 -m unittest discover -s tests -p "test_*.py"
```

## Riferimenti

- Data reference: `data/README.md`
- Food DB master: `data/FOOD_DB.json`
- Mapping LARN: `data/FOOD_DB_TO_LARN_MAPPING.json`
