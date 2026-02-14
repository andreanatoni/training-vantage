# Data Directory Reference

Questa cartella contiene i dati ufficiali usati dal progetto `training-vantage` (nutrizione, porzioni, allenamento e storico misurazioni).
Se lavori su questi file, considera questa documentazione come riferimento operativo.

## Obiettivo

- Centralizzare i dataset in formato JSON.
- Rendere i dati validabili, versionabili e rigenerabili da sorgenti note (CREA, PDF LARN, input utente).
- Separare i file **master** da quelli **derivati**.

## Source of Truth

- Nutrizione:
  - `FOOD_DB.json` = master alimenti e nutrienti.
  - `FOOD_DB_TO_LARN_MAPPING.json` = master mapping verso porzioni.
  - `NUTRITION_ENGINE_CONFIG.json` = centralina strategia nutrizionale (deficit, EA, macro floor, day-profile).
  - `training_load.json` = carico allenante FUTURO (planned) importato da export TrainingPeaks.
- Running:
  - `RUNNING_PLAN_CONFIG.json` = regole generator piano running (progressione, deload, taper).
  - `running_plan.json` = piano running periodizzato generato su finestra temporale.
- Porzioni:
  - `PORTION_STANDARDS.json` = estrazione tabellare completa dal PDF sorgente.
  - `LARN_PORTIONS.json` = subset/normalizzazione operativa della Tabella 2.
  - `OPERATIVE_PORTIONS.json` = porzioni pratiche usate dai flussi applicativi.
- CREA:
  - `CREA_INDEX.json` = indice alimenti CREA (`id`, nome, URL).

## Catalogo File

- `CREA_INDEX.json`: indice completo alimenti CREA.
- `FOOD_DB.json`: database nutrizionale (832 alimenti al momento).
- `FOOD_DB_TO_LARN_MAPPING.json`: associazioni alimento -> porzione LARN/operativa + stato revisione.
- `NUTRITION_ENGINE_CONFIG.json`: configurazione motore nutrizionale periodizzato (obiettivi, priorita', soglie EA, mapping categorie).
- `PORTION_STANDARDS.json`: tabelle 1-6 estratte da `sources/Standard-Quantitativi-delle-Porzioni.pdf`.
- `LARN_PORTIONS.json`: porzioni standard LARN strutturate (v3).
- `OPERATIVE_PORTIONS.json`: porzioni operative con moltiplicatori/annotazioni.
- `composition.json`: storico composizione corporea.
- `running-log.json`: log running per settimane/sessioni.
- `training_load.json`: periodi pianificati (durata/distanza) + day-type + costo energetico stimato.
- `RUNNING_PLAN_CONFIG.json`: configurazione del motore piano running (default volumi e taper).
- `running_plan.json`: output piano running generato (settimane, sessioni, fase, target km).
- `strength-progress.json`: progressione forza.
- `zones.json`: zone di allenamento correnti + storico.
- `changelog.json`: log tecnico delle operazioni script/CLI.
- `backups/`: snapshot timestampati prima di rebuild/upgrade.

## Rigenerazione e Sync

Comandi principali (dalla root del repo):

```bash
./tv food check
./tv food sync
./tv food crawl-index
./tv food rebuild-from-crea
./tv food extract-portions
./tv load import sources/workouts-2.csv
./tv running generate --from 2026-03-01 --to 2026-06-30 --goal-race 2026-10-18
./tv running summary
./tv plan rest
./tv plan week 2026-W11
./tv plan month 2026-03
```

- `food check`: validazione coerenza JSON/markdown e conteggi.
- `food sync`: rigenera `knowledge/food-db.md` dai JSON.
- `crawl-index`: aggiorna indice CREA.
- `rebuild-from-crea`: ricostruisce DB alimenti da `CREA_INDEX.json` (con backup).
- `extract-portions`: rigenera `PORTION_STANDARDS.json` dal PDF e pulisce il testo.
- `load import <csv>`: importa export TrainingPeaks FUTURO (planned) in `training_load.json` e calcola profili energetici per day-type.
- `running generate ...`: genera `running_plan.json` su periodi multi-settimana/mensili con logica progressione, scarico e taper.
  - include forza obbligatoria Mar+Gio (`day_type=forza`, km=0)
  - applica pattern 3:1 (ogni 4a settimana scarico) con `test_5k` in seduta qualita'
  - aggiunge `pace_target` da `data/zones.json` per sedute running
  - periodizza il contenuto sedute per fase (`build/specific/taper/race`), non solo il volume
  - calcola TID settimanale (`low/moderate/high`) con guardrail da `RUNNING_PLAN_CONFIG.json`
  - con flag `--enforce-tid` prova a riallineare automaticamente il mix intensita' riducendo la "zona grigia"
- `running month` / `running summary`: analisi operativa dei volumi per controllo periodizzazione.
- `plan <categoria>`: genera piano quantitativo applicando configurazione in `NUTRITION_ENGINE_CONFIG.json` (deficit day-type + guardrail EA) con output:
  - `plans/nutrition/<categoria>.md` (versione leggibile)
  - `plans/nutrition/<categoria>.json` (versione strutturata)
- `plan week <YYYY-Www>`: genera pacchetto settimanale in `plans/nutrition/weeks/<YYYY-Www>/` partendo dalle sedute di `running_plan.json`:
  - 7 file giornalieri `.md/.json`
  - `week-summary.md` e `week-summary.json`
  - ogni giorno applica `training_cost_kcal` specifico della seduta (source `running_plan_day`) e salva metadata (`phase`, `workout_label`, `session_date`) nel JSON
- `plan month <YYYY-MM>`: genera pacchetto mensile in `plans/nutrition/months/<YYYY-MM>/` partendo dalle sedute di `running_plan.json`:
  - file giornalieri `.md/.json` per tutti i giorni coperti nel mese
  - `month-summary.md` e `month-summary.json`

## Regole di Modifica

- Non modificare manualmente i backup in `backups/`.
- Prima di refactor massivi: creare sempre backup timestampato.
- Se cambi schema JSON, aggiorna:
  - script che lo leggono/scrivono;
  - test (`tests/`);
  - questa documentazione.
- Se cambi strategia nutrizionale (cut/mantenimento/performance), modifica prima `NUTRITION_ENGINE_CONFIG.json` e poi rigenera i piani.
- Dopo ogni modifica dati: eseguire `./tv food check` e test automatici.

## Convenzioni Qualità

- Nomi chiari, minuscoli dove possibile, no caratteri “sporchi”.
- Campi numerici coerenti (`float` o `null`, non stringhe arbitrarie).
- Tracciabilità: valorizzare metadati (`source_url`, `last_verified_at`, `review_status`) quando disponibili.
