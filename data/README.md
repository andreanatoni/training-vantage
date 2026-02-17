# Data Directory Reference

Questa cartella contiene i dati ufficiali usati dal progetto `training-vantage` (nutrizione, porzioni, allenamento e storico misurazioni).
Se lavori su questi file, considera questa documentazione come riferimento operativo.

## Obiettivo

- Centralizzare i dataset in formato JSON.
- Rendere i dati validabili, versionabili e rigenerabili da sorgenti note (CREA, PDF LARN, input utente).
- Separare i file **master** da quelli **derivati**.

## Modalita' Multi-Atleta

- Runtime atleta isolato in `data/athletes/<id>/`.
- Se non passi `--athlete`, i comandi usano `data/athletes/default/` (anche per `default`), con eccezione `running setup`:
  - quando il contesto e' `default`, il `Nome atleta` inserito diventa l'`athlete_id` target (normalizzato)
  - `--athlete` resta prioritario come override esplicito
- Esempio:
  - `./tv --athlete mario running setup`
  - `./tv --athlete mario running generate --from 2026-03-01 --to 2026-06-30`
  - `./tv --athlete mario plan week 2026-W11`

## Source of Truth

- Nutrizione:
  - `FOOD_DB.json` = master alimenti e nutrienti.
  - `FOOD_DB_TO_LARN_MAPPING.json` = master mapping verso porzioni.
  - `DIETABIT_DB.json` = export completo Dietabit (dataset esterno di confronto/integrazione).
  - `DIETABIT_COMPARE_REPORT.json` = report confronto Dietabit vs FOOD_DB (identici/conflitti/aggiunte).
  - `NUTRITION_ENGINE_CONFIG.json` = centralina strategia nutrizionale (deficit, EA, macro floor, day-profile).
  - `templates/nutrition_base_template.shared.json` = template base shared (strutturale, senza grammature).
  - `templates/nutrition_base_template.schema.json` = schema JSON del template base.
  - `athletes/<id>/nutrition_base_template.json` = copia template base per atleta (gusti/abitudini personali).
  - `training_load.json` = carico allenante importato da CSV TrainingPeaks e/o Garmin.
- Running:
  - `RUNNING_ATHLETE_PROFILE.json` = profilo atleta raccolto via colloquio setup.
  - `RUNNING_PLAN_CONFIG.json` = regole generator piano running (progressione, deload, taper).
  - `INTEGRATION_CONFIG.json` = integrazione strict running↔nutrition (mapping day-type, modello costo, gare, alert/status).
  - `running_plan.json` = piano running periodizzato generato su finestra temporale.
- Porzioni:
  - `PORTION_STANDARDS.json` = estrazione tabellare completa dal PDF sorgente.
  - `LARN_PORTIONS.json` = subset/normalizzazione operativa della Tabella 2.
  - `OPERATIVE_PORTIONS.json` = porzioni pratiche usate dai flussi applicativi.
- CREA:
  - `CREA_INDEX.json` = indice alimenti CREA (`id`, nome, URL).

## Catalogo File

- `CREA_INDEX.json`: indice completo alimenti CREA.
- `FOOD_DB.json`: database nutrizionale master condiviso.
- `FOOD_DB_TO_LARN_MAPPING.json`: associazioni alimento -> porzione LARN/operativa + stato revisione.
- `DIETABIT_DB.json`: dump categorie/alimenti Dietabit in formato FOOD_DB-like (`kcal`, `P`, `CHO`, `F` per 100 g).
- `DIETABIT_COMPARE_REPORT.json`: esito confronto Dietabit -> FOOD_DB con preview conflitti.
- `LARN_AUTOMAP_REPORT.json`: report ultimo passaggio auto-mapping FOOD_DB -> LARN.
- `LARN_MAPPING_REVIEW_QUEUE.json`: coda review dei mapping a confidenza non sufficiente.
- `LARN_MANUAL_MAPPING.xlsx`: file operativo per revisione manuale mapping con menu a tendina `larn_portion_id`.
- `NUTRITION_ENGINE_CONFIG.json`: configurazione motore nutrizionale periodizzato (obiettivi, priorita', soglie EA, mapping categorie).
- `templates/nutrition_base_template.shared.json`: bootstrap shared del piano base 5 pasti (solo struttura/option-set).
- `templates/nutrition_base_template.schema.json`: regole di validazione (strict mode, opzioni immutabili, no merge).
- `PORTION_STANDARDS.json`: tabelle 1-6 estratte da `sources/Standard-Quantitativi-delle-Porzioni.pdf`.
- `LARN_PORTIONS.json`: porzioni standard LARN strutturate (v3).
- `OPERATIVE_PORTIONS.json`: porzioni operative con moltiplicatori/annotazioni.
- `composition.json`: storico composizione corporea.
- `running-log.json`: log running per settimane/sessioni.
- `training_load.json`: periodi pianificati (durata/distanza) + day-type + costo energetico stimato.
- `RUNNING_PLAN_CONFIG.json`: configurazione del motore piano running (default volumi e taper).
- `RUNNING_ATHLETE_PROFILE.json`: output colloquio coach (`tv running setup`) con obiettivi/stato/preferenze.
- `running_plan.json`: output piano running generato (settimane, sessioni, fase, target km).
- `INTEGRATION_CONFIG.json`: configurazione strict per atleta usata da `status`, `plan week/month` e fallback `goal_race` in `running generate`.
- `FOOD_DB_ACTIVE.json`: sottoinsieme per-atleta derivato da template/piani per lavorare su alimenti realmente usati.
- `FOOD_CATALOG.json`: vista derivata shadow unificata (food + mapping + porzione + limiti), non source-of-truth.
  - `meal_balancer` la usa automaticamente quando e' valida/completa; altrimenti fallback ai dataset legacy.
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
./tv food sync-dietabit
./tv food auto-map-larn --dry-run
./tv food import-mapped --dry-run --strict-complete
./tv food map-larn next --limit 20
./tv food map-larn set bresaola salumi
./tv food build-active
./tv food build-catalog
./tv food extract-portions
./tv load import sources/workouts-2.csv
./tv running setup --no-history
./tv running generate --from 2026-03-01 --to 2026-06-30 --goal-race 2026-10-18
./tv running summary
./tv nutrition setup-base
./tv plan rest
./tv plan week 2026-W11
./tv plan month 2026-03
./tv plan build-options
```

- `food check`: validazione coerenza JSON/markdown e conteggi.
- `food sync`: rigenera `knowledge/food-db.md` dai JSON.
- `crawl-index`: aggiorna indice CREA.
- `rebuild-from-crea`: ricostruisce DB alimenti da `CREA_INDEX.json` (con backup).
- `sync-dietabit [--no-merge]`: crawl completo Dietabit -> `DIETABIT_DB.json`, confronto con `FOOD_DB` e merge sicuro dei mancanti (se non usi `--no-merge`) + report in `DIETABIT_COMPARE_REPORT.json`.
- `auto-map-larn [--threshold X] [--dry-run]`: mapping semiautomatico verso `LARN_PORTIONS` con regole deterministiche.
  - applica solo suggerimenti sopra soglia (`default 0.90`)
  - salva report in `LARN_AUTOMAP_REPORT.json`
  - salva casi dubbi/non mappati in `LARN_MAPPING_REVIEW_QUEUE.json`
- `food map-larn <subcommand>`: revisione manuale mapping one-by-one.
  - `next`: lista voci in pending review
  - `set/unset`: applica/rimuove mapping singolo
  - `larn`: elenco `larn_portion_id` disponibili
- `food import-mapped [--file ...] [--dry-run] [--strict-complete]`: import massivo da file `food_db_id|larn_portion_id`.
  - validazioni hard su formato, duplicati e id non validi
  - con `--strict-complete` fallisce se non copre esattamente tutti i `food_db_id` del `FOOD_DB`
  - scrive report in `data/FOOD_MAPPED_IMPORT_REPORT.json` e `data/FOOD_MAPPED_IMPORT_REPORT.md`
  - in apply mode crea backup automatico del mapping prima della scrittura
- `extract-portions`: rigenera `PORTION_STANDARDS.json` dal PDF e pulisce il testo.
- `food build-active`: genera `data/athletes/<id>/FOOD_DB_ACTIVE.json` (cache derivata non distruttiva) da:
  - `data/athletes/<id>/nutrition_base_template.json` (food_db_id espliciti)
  - `plans/nutrition/athletes/<id>/**/*.json` (food_db_id diretti e tentativo match per nome)
- `food build-catalog [--dry-run] [--no-strict]`: genera `data/FOOD_CATALOG.json` come vista derivata shadow da:
  - `data/FOOD_DB.json`
  - `data/FOOD_DB_TO_LARN_MAPPING.json`
  - `data/LARN_PORTIONS.json`
  - `data/PERSONAL_LIMITS.json`
- `food validate-data`: esegue validazione strutturale globale dei dataset e coerenza `FOOD_CATALOG` rispetto alle sorgenti.
- `load import [--tp ...] [--garmin ...]`: importa uno o piu' CSV TrainingPeaks/Garmin (anche insieme), fa merge per data/seduta e aggiorna `training_load.json` con profili energetici per day-type.
- `running generate ...`: genera `running_plan.json` su periodi multi-settimana/mensili con logica progressione, scarico e taper.
  - include sessioni `forza` secondo configurazione atleta (`day_type=forza`, km=0)
  - applica pattern 3:1 (ogni 4a settimana scarico) con `test_5k` in seduta qualita'
  - aggiunge `pace_target` da `data/zones.json` per sedute running
  - periodizza il contenuto sedute per fase (`build/specific/taper/race`), non solo il volume
  - calcola TID settimanale (`low/moderate/high`) con guardrail da `RUNNING_PLAN_CONFIG.json`
  - con flag `--enforce-tid` prova a riallineare automaticamente il mix intensita' riducendo la "zona grigia"
- `running setup`: colloquio coach interattivo (ispirato a Daniels/Pfitz/Canova/Seiler/Hudson) con import storico CSV (`TrainingPeaks`/`Garmin`) oppure setup manuale (`--no-history`), con scrittura profilo/config/report + `training_load.json`.
  - genera anche `INTEGRATION_CONFIG.json` atleta (strict mode).
  - senza `--athlete`, se il contesto e' `default`, i file vengono scritti sotto `data/athletes/<nome-normalizzato>/` e `knowledge/athletes/<nome-normalizzato>/`.
  - in `--no-history`, se il profilo non ha volumi pregressi, il setup puo' proporre stima `auto` del volume iniziale (beginner/returning/trained) in base ai giorni running disponibili.
  - i campi setup richiedono input esplicito (nessun default implicito).
  - vincolo forza derivato automaticamente: `giorni_forza >= 1` -> non negoziabile `true`.
- template base nutrizione:
  - bootstrap shared: `data/templates/nutrition_base_template.shared.json`
  - inizializzazione atleta: `data/athletes/<id>/nutrition_base_template.json`
  - schema validazione: `data/templates/nutrition_base_template.schema.json`
  - wizard compilazione: `./tv nutrition setup-base`
    - senza `--athlete`, se il contesto e' `default`, il `Nome atleta` inserito nel wizard diventa la cartella target
    - opzione `--strict-no-defaults`: azzera campi non strutturali prima del wizard
    - i tag opzione sono inferiti automaticamente dal sistema in base ai blocchi alimentari selezionati
    - il campo `when_to_use` e' suggerito automaticamente dal sistema
    - i blocchi sono proposti dal sistema per scenario (`pre_workout`, `post_workout`, `default_day`)
  - export leggibile atleta: `knowledge/athletes/<id>/nutrition-base-template.md`
  - i vincoli personali non sono hardcodati nello shared template: vengono inseriti nel wizard e salvati nel `user_constraints` del template atleta.
  - invarianti: nessuna grammatura nel template base, 1 sola opzione per pasto, no merge tra opzioni, mapping ingredienti via `food_db_id` obbligatorio.
- `running month` / `running summary`: analisi operativa dei volumi per controllo periodizzazione.
- `plan <categoria>`: genera piano quantitativo applicando configurazione in `NUTRITION_ENGINE_CONFIG.json` (deficit day-type + guardrail EA) con output:
  - `plans/nutrition/athletes/<id>/<categoria>.md` (versione leggibile)
  - `plans/nutrition/athletes/<id>/<categoria>.json` (versione strutturata)
  - legge il repository strutturato `knowledge/meal_options/<categoria>.json` (obbligatorio)
- `plan build-options [--category <categoria>]`: rigenera `knowledge/meal_options/*.json` dai file legacy `sources/piano_*.md`.
- `plan week <YYYY-Www>`: genera pacchetto settimanale in `plans/nutrition/athletes/<id>/weeks/<YYYY-Www>/` partendo dalle sedute di `running_plan.json`:
  - 7 file giornalieri `.md/.json`
  - `week-summary.md` e `week-summary.json`
  - ogni giorno applica `training_cost_kcal` specifico della seduta (source `running_plan_day`) e salva metadata (`phase`, `workout_label`, `session_date`) nel JSON
- `plan month <YYYY-MM>`: genera pacchetto mensile in `plans/nutrition/athletes/<id>/months/<YYYY-MM>/` partendo dalle sedute di `running_plan.json`:
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
