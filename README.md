# Training Vantage

**CLI tool** per gestione completa allenamento running, nutrizione e composizione corporea.

Utente: Andrea, runner amatoriale competitivo, preparazione maratona dicembre 2026.

---

## Quick Start

```bash
# Mostra stato attuale
./tv status

# Registra nuova pesata
./tv weigh 68.5 13.0 "Nota opzionale"

# Mostra zone running
./tv zones

# Ricalcola zone da nuovo test 5km
./tv zones 18:15 "Post gara"

# Help
./tv help

# Aggiungi alimento a food DB
./tv food add "Gallette riso" "100 g" 387 7.4 81.0 2.8 3.5 CREA

# Aggiungi alimento direttamente da CREA
./tv food add https://www.alimentinutrizione.it/tabelle-nutrizionali/150030

# Sostituisci alimento esistente (nome o id) con nuovi valori
./tv food add --replace "Yogurt greco 0%" https://www.alimentinutrizione.it/tabelle-nutrizionali/150030

# Scarica indice alfabetico CREA (nome + url + id)
./tv food crawl-index

# Import singolo alimento da CREA (by id)
./tv food import-crea --id 150030

# Import massivo da indice locale CREA
./tv food import-crea --all --limit 50

# Backup + rebuild completo FOOD_DB/mapping/markdown da CREA_INDEX
./tv food rebuild-from-crea

# Estrai database porzioni dal PDF standard LARN
./tv food extract-portions

# Importa carico allenante futuro da export TrainingPeaks
./tv load import sources/workouts-2.csv

# Genera piano running periodizzato (multi-mese + taper)
./tv running generate --from 2026-03-01 --to 2026-06-30 --goal-race 2026-10-18
./tv running summary

# Analizza export Garmin
./tv analyze sources/storico.csv
```

---

## Stato Implementazione

### ✅ Completato (Priorità 1 — Tracking base)

| Comando | Stato | Descrizione |
|---------|-------|-------------|
| `./tv weigh <peso> <bf%>` | ✅ | Registra pesata, calcola FFM/BMR, alerts red flags |
| `./tv status` | ✅ | Dashboard completo: composizione, zone, piano, gare |
| `./tv zones [test]` | ✅ | Mostra/ricalcola zone running da test 5km |

### ✅ Completato (Priorità 2 — Nutrizione)

| Comando | Stato | Descrizione |
|---------|-------|-------------|
| `./tv plan <cat>` | ✅ | Genera piano nutrizionale con target kcal/macro in `plans/nutrition/<cat>.md` + `.json` |
| `./tv plan --all` | ✅ | Rigenera tutti gli 8 piani (AGGIORNATI) |
| `./tv plan week <YYYY-Www>` | ✅ | Genera pacchetto nutrizione settimanale da `data/running_plan.json` |
| `./tv plan month <YYYY-MM>` | ✅ | Genera pacchetto nutrizione mensile da `data/running_plan.json` |

### ✅ Completato (Priorità 3 — Running)

| Comando | Stato | Descrizione |
|---------|-------|-------------|
| `./tv week <N>` | ✅ | Mostra piano running settimana N (W1-W20) |
| `./tv analyze <file.csv>` | ✅ | Analizza export Garmin CSV (distanza/tempo/passo/FC) |
| `./tv running generate ...` | ✅ | Genera piano running periodizzato su finestra temporale (`data/running_plan.json`) |
| `./tv running week <N>` | ✅ | Mostra dettaglio settimana dal piano running generato |
| `./tv running month <YYYY-MM>` | ✅ | Riepilogo mensile volumi/day-type |
| `./tv running summary` | ✅ | Riepilogo periodo + preview taper |

### ✅ Utility Disponibili

| Comando | Stato | Descrizione |
|---------|-------|-------------|
| `./tv food add ...` | ✅ | Aggiunge alimento a `knowledge/food-db.md`, `data/FOOD_DB.json`, `data/FOOD_DB_TO_LARN_MAPPING.json` |
| `./tv analyze <file.csv>` | ✅ | Analizza export Garmin CSV (distanza/tempo/passo/FC) |
| `./tv food sync` | ✅ | Rigenera `knowledge/food-db.md` da `data/FOOD_DB.json` + validazione mapping |
| `./tv food check` | ✅ | Check coerenza FOOD_DB/mapping senza scrittura |
| `./tv food crawl-index` | ✅ | Estrae indice alfabetico CREA in `data/CREA_INDEX.json` e `knowledge/crea-index.md` |
| `./tv food import-crea ...` | ✅ | Importa schede CREA in FOOD_DB (singolo/lista/all) |
| `./tv food rebuild-from-crea` | ✅ | Esegue backup e ricostruisce FOOD_DB + mapping + markdown da indice CREA |
| `./tv food extract-portions` | ✅ | Estrae tabelle porzioni dal PDF in `data/PORTION_STANDARDS.json` |
| `./tv load import <csv>` | ✅ | Importa export TrainingPeaks FUTURO in `data/training_load.json` |

### 📋 Pianificato

- `./tv compare <tipo>` — Confronto sessioni simili
- `./tv strength <type>` — Generazione scheda forza
- `./tv checkpoint` — Template checkpoint con dati attuali
- `./tv validate sync` — Verifica allineamento file e metadata

---

## Struttura Progetto

```
training-vantage/
├── tv                          # CLI dispatcher principale
├── CLAUDE.md                   # Istruzioni per Claude Code
├── README.md                   # Questo file
│
├── knowledge/                  # Single Source of Truth
│   ├── linee-guida.md          # Bibbia del programma
│   ├── food-db.md              # Database nutrizionale master
│   ├── opzioni-raccomandate.md # Opzioni raccomandate per pasto
│   └── piano-base.md           # Piano base validato
│
├── plans/
│   ├── nutrition/              # 8 piani quantitativi generati
│   │   ├── forza.md            # 2510 kcal
│   │   ├── easy-run.md         # 2565 kcal
│   │   ├── qualita.md          # 2650 kcal
│   │   ├── tempo.md            # 2565 kcal
│   │   ├── lungo.md            # 2730 kcal
│   │   ├── rest.md             # 2160 kcal
│   │   ├── pizza-day.md        # 2565 kcal
│   │   └── domenica.md         # 2205 kcal
│   └── running/                # Piani settimanali (generati on-demand)
│
├── data/                       # Dati dinamici
│   ├── README.md               # Documentazione ufficiale dataset e workflow data
│   ├── composition.json        # Storico pesate (8 misurazioni)
│   ├── zones.json              # Zone attuali + storico test
│   ├── running-log.json        # Log sessioni (32 settimane da Excel)
│   ├── strength-progress.json  # Progressione forza
│   └── changelog.json          # Log modifiche
│
└── scripts/                    # Python scripts per comandi CLI
    ├── weigh.py
    ├── status.py
    ├── zones.py
    └── convert-running-plan.py
```

---

## Dati Attuali (11/02/2026)

> Nota: questa sezione e' uno snapshot storico. Per lo stato corrente usare sempre `./tv status`.

### Composizione Corporea
- **Peso**: 68.50 kg | **BF**: 13.0% | **FFM**: 59.59 kg | **BMR**: 1657 kcal
- **Trend** (ultimi 76 giorni): -0.40kg peso, -0.18kg FFM
- ⚠️  FFM vicino a red flag 59.5kg

### Zone Running (Test 11/02/2026 — 18:00, 3:36/km)
- **Z1** (Recovery): 5:14+
- **Z2** (Easy): 4:43 - 5:14
- **Z3** (Moderate): 4:19 - 4:43
- **Z4** (High Aerobic): 4:05 - 4:19
- **Z5** (Threshold-): 3:53 - 4:05
- **Z6** (Threshold): 3:45 - 3:53
- **Z7** (VO2max-): 3:34 - 3:24
- **Z8** (VO2max): 3:24 - 3:20

### Piano Running
- **Settimana corrente**: W20 (M5 - Mesociclo 5)
- **Prossima gara**: Roma-Ostia Half Marathon, 01/03/2026 (17 giorni)
- **Target**: 4:00/km (1:24)

### Calendario Gare 2026
| Gara | Data | Target |
|------|------|--------|
| Roma-Ostia HM | 01/03/2026 | 4:00/km (1:24) |
| Latina HM | 29/03/2026 | sub 1:24 (PB) |
| Mezza Roma | 18/10/2026 | test pre-maratona |
| Maratona Latina | 06/12/2026 | prima maratona |

---

## Piani Nutrizionali

✅ **Tutti gli 8 piani aggiornati** (11/02/2026):
- Generati con FFM 59.59 e BMR 1657 attuali
- Target kcal e macro corretti per ogni categoria
- Status: CURRENT (non più STALE)

**Note**: I piani attuali mostrano target giornalieri e opzioni consigliate. Le grammature esatte verranno calcolate in fase di implementazione avanzata.

---

## Riferimenti

- **PRD completo**: `training-vantage-prd.md` (2600+ righe)
- **Linee guida**: `knowledge/linee-guida.md` (SEMPRE consultare prima di modificare piani)
- **Documentazione dati (ufficiale)**: `data/README.md`
- **Food DB (master)**: `data/FOOD_DB.json`
- **Food DB (generated view)**: `knowledge/food-db.md`
- **Piano base**: `knowledge/piano-base.md` (SSoT per combinazioni alimentari)

## Regola Food DB

- **Source of truth nutrizionale**: `data/FOOD_DB.json`
- `knowledge/food-db.md` e' un file generato con `./tv food sync`
- `data/FOOD_DB_TO_LARN_MAPPING.json` deve referenziare solo `food_db_id` esistenti
- Strategia motore piani (deficit/EA/day-profile): `data/NUTRITION_ENGINE_CONFIG.json`

## Regola Piano Nutrizione

- `./tv plan <categoria>` applica una strategia centralizzata da `data/NUTRITION_ENGINE_CONFIG.json`
- Output piano: `plans/nutrition/<categoria>.md` (human-readable) e `plans/nutrition/<categoria>.json` (machine-readable)
- Se presente `data/training_load.json`, il motore usa i costi energetici stimati per day-profile da export TrainingPeaks futuro (`tv load import ...`)
- `./tv plan week <YYYY-Www>` usa `data/running_plan.json` e genera 7 piani giornalieri in `plans/nutrition/weeks/<YYYY-Www>/` + `week-summary.md/.json`
- `./tv plan month <YYYY-MM>` usa `data/running_plan.json` e genera i piani giornalieri del mese in `plans/nutrition/months/<YYYY-MM>/` + `month-summary.md/.json`
- Nei pacchetti `week/month`, ogni giorno usa il proprio `training_cost_kcal` stimato dalla seduta del `running_plan` (source: `running_plan_day`) invece di un profilo medio
- Ogni categoria (`rest`, `easy-run`, `qualita`, `tempo`, `lungo`, `forza`, `pizza-day`, `domenica`) viene mappata a un day-profile
- Il motore applica:
  - deficit percentuale per day-profile
  - guardrail `Energy Availability` (hard floor)
  - metadata nel piano generato (`Engine Config`, `Day Profile`, `Deficit Applied`, `EA`)
- Per cambiare priorita' future (es. mantenimento invece di cut), aggiornare il file config senza modificare il codice.

## Regola Piano Running

- `./tv running generate --from ... --to ... [--goal-race ...]` crea il piano periodizzato in `data/running_plan.json`
- Opzionale: `--enforce-tid` applica aggiustamenti automatici ai workout label per rispettare meglio i guardrail TID
- Parametri default e vincoli progressione/taper stanno in `data/RUNNING_PLAN_CONFIG.json`
- Il piano supporta pianificazione per blocchi mensili o periodi lunghi verso una gara obiettivo
- `./tv running month` e `./tv running summary` servono per monitorare andamento volumi e taper prima della gara
- Base metodologica allineata alle linee guida progetto (`sources/istruzioni di progetto.md`, `sources/linee-guida.md`):
  - routine settimanale fissa con running 4x (`easy`, `qualita`, `progressivo`, `lungo`) + forza obbligatoria 2x (`Mar`, `Gio`)
  - mesociclo 3:1 (3 carico + 1 scarico) con test 5km in settimana scarico
  - prescrizione ritmo seduta tramite zone correnti (`data/zones.json`)
  - contenuto sedute periodizzato per fase: `build`, `specific`, `taper`, `race` (non solo variazione km)
  - guardrail TID (Training Intensity Distribution) stile Seiler: controllo `low/moderate/high` per settimana con warning automatici su zona grigia
- Riferimenti metodologici usati: `Daniels` (zone/VDOT), `Pfitzinger` (periodizzazione e long run), `Canova` (specificita' ritmo gara), `Seiler` (TID), `Hudson` (adattivita' e recovery)

---

## Sviluppo Locale

```bash
# Valida e rigenera food-db.md dal JSON master
./tv food sync

# Solo validazione coerenza FOOD_DB e mapping
./tv food check

# Aggiorna indice alfabetico CREA (richiede rete)
./tv food crawl-index

# Import da CREA (richiede rete)
./tv food import-crea --id 150030

# Rebuild completo da indice CREA (richiede rete)
./tv food rebuild-from-crea

# Estrazione tabelle porzioni da PDF (locale)
./tv food extract-portions

# Test smoke CLI + validazione schema minima JSON
python3 -m unittest discover -s tests -p "test_*.py"

# Lint Python (dopo: pip install -r requirements-dev.txt)
ruff check .
```

---

## Log Modifiche

Tutte le modifiche ai dati sono tracciate in `data/changelog.json`:
- Bootstrap iniziale: 11/02/2026 18:00
- Ultima pesata: 11/02/2026 14:11 (68.5kg, 13.0%)
- Ultimo test zone: 11/02/2026 14:18 (18:00, miglioramento 27s)

---

**Versione**: 1.0
**Ultimo aggiornamento**: 11 febbraio 2026
