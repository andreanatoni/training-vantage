# Flow End-to-End (Fase 0 -> Output Finale)

Questo documento riassume il flusso operativo completo attuale, con focus su:
- inserimento dati utente
- setup nutrizione multi-atleta
- validazioni strict
- generazione piani
- file letti/scritti per ogni fase

## Fase 0 - Contesto Atleta

### Spiegazione
Imposta lo "spazio di lavoro" dell'atleta: da qui in poi letture/scritture vanno nelle sue cartelle dedicate.

### Comando
```bash
./tv --athlete <id> <comando>
```

Se non passi `--athlete`, viene usato `default`.

### Esempio input/output
Input:
```bash
./tv --athlete matteo status
```
Output atteso (estratto):
```text
Atleta: matteo
Profile path: data/athletes/matteo/...
```

### Modulo coinvolto
- `scripts/athlete_context.py`

### Path runtime per atleta
- `data/athletes/<id>/...`
- `knowledge/athletes/<id>/...`
- `plans/nutrition/athletes/<id>/...`

---

## Fase 1 - Profilazione Utente Nutrizione

### Spiegazione
Raccoglie i dati base e avanzati necessari per stimare fabbisogni, vincoli e guardrail nutrizionali.

### Comando
```bash
./tv nutrition setup-profile
```

### Modulo coinvolto
- `scripts/nutrition/setup_profile.py`

### Input raccolti
- Core: sesso, età, altezza, peso
- Goal: fat_loss / maintenance / performance / recomposition
- Training context: running days, strength days, training time
- BIA avanzata opzionale: BF, FFM, BMR, massa muscolare, acqua, ecc.

### File scritti
- `data/athletes/<id>/NUTRITION_PROFILE.json`
- `knowledge/athletes/<id>/nutrition-profile.md`

### Esempio input/output
Input:
```bash
./tv --athlete matteo nutrition setup-profile
```
Output atteso (estratto):
```text
[OK] Profilo nutrizione salvato
- data/athletes/matteo/NUTRITION_PROFILE.json
- knowledge/athletes/matteo/nutrition-profile.md
```

---

## Fase 2 - Setup Base Template Pasti

### Spiegazione
Costruisce il template pasti dell'atleta (5 pasti, opzioni e blocchi) con regole, safety check e tracciabilità.

### Comando
```bash
./tv nutrition setup-base [--autodraft] [--allow-manual-block-overrides] [--edit]
```

### Moduli coinvolti
- `scripts/nutrition/setup_base.py`
- `scripts/nutrition/rules_engine.py`

### File letti
- `data/athletes/<id>/NUTRITION_PROFILE.json` (obbligatorio)
- `data/FOOD_DB.json`
- `data/NUTRITION_SAFETY_TRIGGERS.json`
- `knowledge/nutrition-rules.md`
- `data/templates/nutrition_base_template.shared.json` (bootstrap)

### Logica principale
- Validazione profilo obbligatoria (fail se mancante/incompleto)
- Safety check:
  - warning: setup continua
  - hard stop: setup bloccato
- Proposta scenario + blocchi guidata da rules engine
- OR per blocco (`one_of`) con `food_db_id`
- `rules_trace` obbligatorio per opzione

### Modalità autodraft
- `--autodraft`: crea 1 opzione bozza per pasto
- review guidata: `accetta` / `sostituisci` / `rigenera`
- quality gate finale prima del salvataggio

### File scritti
- `data/athletes/<id>/nutrition_base_template.json`
- `knowledge/athletes/<id>/nutrition-base-template.md`

### Esempio input/output
Input:
```bash
./tv --athlete matteo nutrition setup-base --autodraft
```
Output atteso (estratto):
```text
Template base creato in modalità autodraft.
[OK] Salvato:
- data/athletes/matteo/nutrition_base_template.json
```

---

## Fase 3 - Pre-flight Validazione Template

### Spiegazione
Controlla che il template sia realmente usabile dal planner, bloccando errori prima della generazione piani.

### Comando
```bash
./tv nutrition validate-template [--json]
```

### Modulo coinvolto
- `scripts/nutrition/validate_template.py`

### File letti
- `data/athletes/<id>/nutrition_base_template.json`
- `data/FOOD_DB.json`

### Cosa valida
- presenza meal_id obbligatori (5 pasti)
- opzioni presenti
- blocchi e `one_of` non vuoti
- `food_db_id` validi
- `rules_trace` completo

### Esito
- exit `0`: planner-ready
- exit `1`: non valido (con elenco errori)

### Esempio input/output
Input:
```bash
./tv --athlete matteo nutrition validate-template
```
Output atteso (estratto):
```text
Template valido: planner-ready
```
Output errore (estratto):
```text
Template non valido:
- meal breakfast senza opzioni
- food_db_id non trovato: xxx
```

---

## Fase 4 - Generazione Piano Giornaliero

### Spiegazione
Genera il piano del giorno/categoria scegliendo la combinazione migliore delle opzioni pasto rispetto ai target.

### Comando
```bash
./tv plan <categoria>
```

Categorie: `rest`, `forza`, `easy-run`, `qualita`, `tempo`, `lungo`, `pizza-day`, `domenica`

### Moduli coinvolti
- `scripts/nutrition/plan.py`
- `scripts/nutrition/meal_balancer.py`
- `scripts/nutrition/meal_options_repository.py` (fallback baseline)

### Sorgente opzioni (strict)
1. primaria: `data/athletes/<id>/nutrition_base_template.json`
2. fallback: `knowledge/meal_options/<categoria>.json` **solo se template atleta assente**
3. se template atleta esiste ma non planner-ready: errore (no fallback silenzioso)

### OR nativo nei blocchi
- per ogni opzione template: il planner testa combinazioni `one_of` (1 scelta per blocco)
- ogni combinazione passa da `MealBalancer`
- viene selezionata la combinazione con match migliore

### File letti principali
- `data/athletes/<id>/nutrition_base_template.json`
- `data/athletes/<id>/composition.json`
- `data/athletes/<id>/NUTRITION_ENGINE_CONFIG.json` (o fallback shared)
- `data/athletes/<id>/training_load.json`
- `data/FOOD_DB.json`
- `data/FOOD_DB_TO_LARN_MAPPING.json`
- `data/LARN_PORTIONS.json`
- `data/PERSONAL_LIMITS.json`

### File scritti
- `plans/nutrition/athletes/<id>/<categoria>.md`
- `plans/nutrition/athletes/<id>/<categoria>.json`

### Metadati output rilevanti
- `engine.plan_source` (`athlete_template` / `knowledge_fallback`)
- trace opzione (`rules_trace`, OR combo selezionata)

### Esempio input/output
Input:
```bash
./tv --athlete matteo plan easy-run
```
Output atteso (estratto):
```text
[OK] Piano generato: easy-run
- plans/nutrition/athletes/matteo/easy-run.md
- plans/nutrition/athletes/matteo/easy-run.json
```

---

## Fase 5 - Generazione Settimanale / Mensile

### Spiegazione
Compone più piani giornalieri in una vista settimana/mese usando il running plan come driver dei day type.

### Comandi
```bash
./tv plan week <YYYY-Www>
./tv plan month <YYYY-MM>
```

### Modulo coinvolto
- `scripts/nutrition/plan.py`

### Dipendenza running
- legge `data/athletes/<id>/running_plan.json`
- mappa `day_type -> categoria nutrizione` via integrazione strict

### File scritti
- settimana:
  - `plans/nutrition/athletes/<id>/weeks/<YYYY-Www>/*.md`
  - `plans/nutrition/athletes/<id>/weeks/<YYYY-Www>/*.json`
  - `week-summary.md`, `week-summary.json`
- mese:
  - `plans/nutrition/athletes/<id>/months/<YYYY-MM>/*.md`
  - `plans/nutrition/athletes/<id>/months/<YYYY-MM>/*.json`
  - `month-summary.md`, `month-summary.json`

### Esempio input/output
Input:
```bash
./tv --athlete matteo plan week 2026-W12
```
Output atteso (estratto):
```text
[OK] Week plan generato: 2026-W12
- plans/nutrition/athletes/matteo/weeks/2026-W12/week-summary.md
```

---

## Fase 6 - Running (se usi integrazione completa)

### Spiegazione
Configura profilo e pianificazione corsa; i risultati alimentano l'integrazione nutrizione tramite day type e carico.

### Comandi base
```bash
./tv running setup
./tv running generate --from ... --to ... --goal-race ...
```

### Moduli coinvolti
- `scripts/running/running_setup.py`
- `scripts/running/running_plan.py`

### File impattati (principali)
- `data/athletes/<id>/RUNNING_ATHLETE_PROFILE.json`
- `data/athletes/<id>/RUNNING_PLAN_CONFIG.json`
- `data/athletes/<id>/INTEGRATION_CONFIG.json`
- `data/athletes/<id>/training_load.json`
- `data/athletes/<id>/running_plan.json`
- `knowledge/athletes/<id>/running-setup-report.md`

### Esempio input/output
Input:
```bash
./tv --athlete matteo running setup
```
Output atteso (estratto):
```text
[OK] Running setup completato.
- data/athletes/matteo/RUNNING_ATHLETE_PROFILE.json
- data/athletes/matteo/RUNNING_PLAN_CONFIG.json
```

---

## Sequenza consigliata operativa

1. `./tv nutrition setup-profile`
2. `./tv nutrition setup-base --autodraft`
3. `./tv nutrition validate-template`
4. `./tv plan rest` (smoke)
5. `./tv running setup` (se non fatto)
6. `./tv running generate ...`
7. `./tv plan week ...` / `./tv plan month ...`

---

## Errori attesi (by design)

- Profilo nutrizione mancante/incompleto -> `setup-base` bloccato
- Trigger safety hard -> `setup-base` bloccato
- Template atleta presente ma non planner-ready -> `plan` bloccato
- `food_db_id` non validi -> validazione fallisce

Questo comportamento e' intenzionale per evitare fallback silenziosi e garantire coerenza multi-utente.
