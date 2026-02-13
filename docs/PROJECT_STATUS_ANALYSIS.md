# Training Vantage - Analisi Stato Progetto

**Data Analisi**: 2026-02-12 (Updated after Phase 1)
**Version**: 2.1 (meal planning + tracking base)

---

## Executive Summary

**Stato Complessivo**: ~60% completo (+30% da Phase 1)

Il progetto Training Vantage è un CLI tool completo per gestione running + nutrizione + composizione corporea. Attualmente sono completate:
- **Meal planning system** (v2.0 FROZEN) - 30%
- **Tracking base** (v2.1 COMPLETE) - 30%

**Componenti completate**:
- ✅ Meal planning system (v2.0 FROZEN)
- ✅ CLI per generazione piani nutrizionali
- ✅ Data validation layer
- ✅ Tracking composizione corporea (v2.1 NEW)
- ✅ Tracking zone running (v2.1 NEW)
- ✅ Dashboard status (v2.1 NEW)
- ✅ Test suite completa (52/52)

**Componenti mancanti** (priorità dal PRD):
- ❌ Tracking composizione corporea (`/weigh`, `/status`)
- ❌ Gestione zone running (`/zones`, `/test`)
- ❌ Piano running (stagionale, blocchi, settimanale)
- ❌ Analisi workout Garmin
- ❌ Progressione forza
- ❌ Sistema checkpoint

---

## 📊 Analisi Dettagliata

### ✅ IMPLEMENTATO (v2.0 FROZEN)

#### 1. Meal Planning System

**Componenti**:
- `scripts/meal_balancer.py` - Beam search optimizer con constraint layers
- `scripts/plan_builder.py` - Orchestrator per day profiles
- `scripts/cli.py` - CLI tool production-ready
- `scripts/data_validator.py` - Data integrity validator

**Features**:
- Meal balancing con beam search (width 300)
- Constraint layers:
  - Volume penalty (soft, via callback)
  - Must include (hard structural)
  - Protein floor (hard target)
  - Template validation (required/forbidden groups)
- Dual solutions (realistic + unconstrained)
- Personal limits con context-dependent mode
- LARN portion system
- Exit codes strutturati (0/1/2)
- JSON export

**Data Files** (10 JSON):
- FOOD_DB.json (49 alimenti)
- LARN_PORTIONS.json
- OPERATIVE_PORTIONS.json
- FOOD_DB_TO_LARN_MAPPING.json
- PERSONAL_LIMITS.json
- DAY_PROFILES.json (8 profiles)
- MEAL_DISTRIBUTION.json
- FOOD_GROUPS.json
- MEAL_TEMPLATES.json
- REALISM_RULES.json

**Test Coverage**:
- 47/47 tests passing (100%)
- Meal balancer: 5/5
- Plan builder: 3/3
- Meal templates: 6/6
- Template fixes: 4/4
- Volume penalty: 4/4
- Must include: 5/5
- Protein floor: 4/4
- Data validator: 8/8
- Solver frozen: 1/1
- CLI: 4/4

**Documentation**:
- docs/CLI_USAGE.md (600+ lines)
- docs/V2_FREEZE_DECLARATION.md (356 lines)
- docs/MEAL_BALANCER.md (technical reference)
- 5 stress test reports

**Comando CLI**:
```bash
python3 scripts/cli.py plan <profile_id> [--mode realistic|unconstrained|recommended] [--json] [--debug]
```

**Profiles Disponibili**:
- rest, easy_run, qualita, tempo, lungo, forza, pizza_day, domenica

---

### ❌ NON IMPLEMENTATO

#### 1. Tracking Composizione Corporea

**Priorità**: 1 (ALTA - dal PRD)

**Comandi Mancanti**:
- `/weigh <peso> <bf%>` - Registra pesata, calcola FFM/BMR, aggiorna composition.json
- `/status` - Mostra stato attuale (ultima pesata, zone, prossima gara, alerts)
- `/checkpoint` - Genera checkpoint template con dati attuali
- `/alerts` - Red flags attive (FFM < 59.5, peso drop > 0.6%/sett, etc.)

**Data File Esistente**:
- ✅ `data/composition.json` (già presente con 7 misurazioni storiche)

**Logica da Implementare**:
1. Calcolo FFM = peso × (1 - bf/100)
2. Calcolo BMR (Katch-McArdle) = 370 + 21.6 × FFM
3. Delta vs misurazione precedente
4. Check red flags:
   - FFM < 59.5 kg → RED FLAG
   - FFM calo per >4 pesate → WARNING
   - Peso calo >0.6%/sett per >4 sett → RED FLAG
   - BF% stallo >6 sett → ATTENZIONE
5. Impatto su piani nutrizionali (Delta BMR > 30 kcal → rigenera piani)

**Complessità**: BASSA (calcoli semplici, no ottimizzazione)

**Stima**: 2-3 ore implementazione + test

---

#### 2. Gestione Zone Running

**Priorità**: 1 (ALTA - dal PRD)

**Comandi Mancanti**:
- `/zones` - Mostra zone attuali
- `/zones history` - Storico test e progressione
- `/test <tempo>` - Registra test 5km, ricalcola zone

**Data File Esistente**:
- ✅ `data/zones.json` (già presente con 3 test storici + zone attuali)

**Logica da Implementare** (formule dal PRD):
```
Parsing tempo test 5km (es. "18:27") → ritmo medio (3:41/km)

Calcolo zone:
- Z6 = ritmo + 9"
- Z5 = Z6 + 8"
- Z4 = Z6 + 20"
- Z3 = Z4top + 14"
- Z2 = Z3top + 24"
- Z1 = Z2top + 31"
- Z7 = ritmo -2" a -12"
- Z8 = ritmo -12" a -16"

Salva in zones.json (append storico)
Mostra confronto con test precedente
```

**Complessità**: BASSA (parsing tempo + formule aritmetiche)

**Stima**: 1-2 ore implementazione + test

---

#### 3. Piano Running

**Priorità**: 3 (MEDIA - dal PRD)

**Architettura a 3 Livelli**:

**Livello 1 - Strategico** (`/plan-season`):
- Input: calendario gare
- Output: macro-struttura stagione (12+ settimane)
- Frequenza: 1-2x/anno

**Livello 2 - Tattico** (`/plan-block <N>`):
- Input: mesociclo target (es. "Base 1", "Build 2", "Peak")
- Output: blocco 4 settimane dettagliato (3:1 ratio)
- Frequenza: ogni 4 settimane

**Livello 3 - Operativo** (`/week <N>`):
- Input: numero settimana
- Output: dettaglio 7 giorni con sessioni, ritmi zone, note
- Frequenza: consultazione pre-settimana

**Data File Esistente**:
- ✅ `data/running-log.json` (già presente con storico workout)
- ❌ `plans/running/` (cartella vuota)

**Comandi Mancanti**:
- `/plan-season` - Genera stagione completa
- `/plan-season update` - Aggiorna da un punto
- `/plan-block <N>` - Genera mesociclo dettagliato
- `/plan-block adjust <N> <motivo>` - Rimodula blocco
- `/week <N>` - Mostra settimana operativa
- `/taper <gara>` - Protocollo taper pre-gara
- `/race <gara>` - Race strategy

**Logica da Implementare**:
1. Parser calendario gare (date, distanza, obiettivo)
2. Periodizzazione automatica (base → build → peak → taper)
3. Template mesocicli 3:1 (3 settimane progressive + 1 scarico)
4. Generatore sessioni settimanali da zone
5. Algoritmo taper (riduzione volume, mantenimento intensità)
6. Race pacing calculator

**Complessità**: ALTA (logica complessa, molte variabili)

**Stima**: 15-20 ore implementazione + test

---

#### 4. Analisi Workout Garmin

**Priorità**: 3 (MEDIA - dal PRD)

**Comandi Mancanti**:
- `/analyze <file.csv>` - Analizza export CSV Garmin singolo workout
- `/compare <tipo> [periodo]` - Confronta sessioni simili

**Data File Parziale**:
- ✅ `data/running-log.json` (storico workout ma senza dettagli CSV)
- ❌ `garmin/` (cartella mancante per CSV import)

**Logica da Implementare**:
1. Parser CSV Garmin (columne: time, distance, HR, pace, elevation, cadence)
2. Calcolo metriche:
   - Pace medio/min/max per lap
   - HR medio/max per zona
   - Cadence media
   - Elevation gain/loss
   - Consistency (pace std deviation)
3. Comparazione sessioni:
   - Stesso tipo (easy run, tempo, intervals, long run)
   - Stesso periodo (ultime 4/8/12 settimane)
   - Trend progressione
4. Visualizzazione:
   - Tabella laps con split
   - Distribuzione HR per zona
   - Grafico pace vs HR
   - Note automatiche (es: "Pacing erratico", "HR deriva >10 bpm")

**Complessità**: MEDIA (parsing CSV, aggregazione dati)

**Stima**: 8-10 ore implementazione + test

---

#### 5. Progressione Forza

**Priorità**: 4 (BASSA - dal PRD)

**Comandi Mancanti**:
- `/strength <week_type>` - Genera scheda forza (base/build/peak/scarico)
- `/strength progress` - Mostra progressione esercizi

**Data File Esistente**:
- ✅ `data/strength-progress.json` (già inizializzato, tutto "not_started")

**Logica da Implementare**:
1. Template scheda full-body (6 blocchi):
   - Warm-up dinamico (5')
   - Pliometria/esplosività (8')
   - Lower body forza (10')
   - Core intensive (12')
   - Upper push/pull (8')
   - Mobilità funzionale (5')
2. Pool esercizi per blocco con progressioni
3. Algoritmo periodizzazione forza (base → build → peak → scarico)
4. Tracking progressione:
   - Serie × rip × carico
   - Volume totale (tonnellaggio)
   - Difficulty rating (1-10)
5. Autoregolazione:
   - Se sessione fallita → riprova stesso livello
   - Se sessione facile → avanza progressione
   - Se scarico → riduci volume/intensità

**Complessità**: MEDIA (molti template, logica progressione)

**Stima**: 10-12 ore implementazione + test

---

#### 6. Sistema Changelog

**Priorità**: 4 (BASSA - infrastruttura)

**Comandi Mancanti**:
- `/log` - Mostra ultime 10 entry changelog
- `/log <file>` - Storico modifiche di un file
- `/log diff <file>` - Diff ultima modifica

**Data File Esistente**:
- ✅ `data/changelog.json` (già presente, vuoto o con poche entry)

**Logica da Implementare**:
1. Append-only log di tutte le modifiche
2. Entry con: timestamp, file, tipo_modifica, autore, descrizione
3. Filtri per file/data/tipo
4. Diff tra versioni (se applicabile)
5. Integration con comandi esistenti:
   - Ogni `/plan` → entry in changelog
   - Ogni `/weigh` → entry in changelog
   - Ogni `/test` → entry in changelog

**Complessità**: BASSA (CRUD su JSON)

**Stima**: 2-3 ore implementazione + test

---

#### 7. Plans Nutrition (formato Markdown)

**Priorità**: 2 (MEDIA - usabilità)

**Status Attuale**:
- ❌ `plans/nutrition/` - Cartella vuota
- ✅ CLI genera piani ma NON li salva come .md

**Cosa Manca**:
1. Export piani da CLI come file .md in `plans/nutrition/`
2. Formato markdown leggibile (tabelle, opzioni, totali)
3. Metadata HTML comments per parsabilità
4. Comando `/plan all` per rigenerare tutti gli 8 piani

**Esempio Output Desiderato**:
```markdown
<!-- META
categoria: REST
generato: 2026-02-12
ffm: 59.57
peso: 68.65
bmr: 1657
-->

# Piano REST - Giorno di riposo

**Distribuzione**: 22% | 8% | 32% | 12% | 26%
**Logica**: Kcal moderate, proteine alte per recupero

---

## COLAZIONE - 07:30-08:30

**Target**: kcal 484 | P 30.8g | CHO 55.0g | F 12.6g

### Opzione 1 (RACCOMANDATA)
- Fette biscottate: 15g
- Yogurt greco 0%: 250g
- Mandorle: 22.5g
- Marmellata: 25g
- Mela: 112.5g

**Totali**: kcal 462 | P 31.6g | CHO 61.3g | F 12.8g
**Delta**: kcal -4.5% | P +2.7% | CHO +11.5% | F +2.0%

[... altri pasti ...]

---

## TOTALI GIORNO

| Nutriente | Target | Actual | Delta |
|-----------|--------|--------|-------|
| Kcal | 2200 | 2138 | -2.8% |
| P (g) | 140.0 | 146.2 | +4.4% |
| CHO (g) | 220.0 | 225.5 | +2.5% |
| F (g) | 70.0 | 71.1 | +1.6% |
```

**Complessità**: BASSA (formattazione output)

**Stima**: 3-4 ore implementazione

---

## 📋 Roadmap Suggerita

### Phase 1: Tracking Base (Priorità ALTA)
**Durata stimata**: 1 settimana
**Obiettivo**: Avere i comandi di tracking fondamentali

1. **Implementa `/weigh`** (2-3 ore)
   - Parsing input
   - Calcolo FFM/BMR
   - Append composition.json
   - Delta e alerts
   - Output formattato

2. **Implementa `/status`** (2-3 ore)
   - Legge composition.json
   - Legge zones.json
   - Legge running-log.json
   - Calcola trend
   - Display dashboard

3. **Implementa `/zones`** (1-2 ore)
   - Display zone attuali
   - Parsing tempo test
   - Calcolo formule zone
   - Append zones.json
   - Storico test

4. **Testing** (2-3 ore)
   - Test suite comandi tracking
   - Integration tests
   - Documentation

**Deliverable**: CLI con comandi `/weigh`, `/status`, `/zones` funzionanti

---

### Phase 2: Plans Export (Priorità MEDIA)
**Durata stimata**: 3-4 giorni
**Obiettivo**: Generare file .md leggibili

1. **Implementa export markdown** (3-4 ore)
   - Formatter markdown da plan JSON
   - Template con metadata HTML
   - Write to plans/nutrition/

2. **Implementa `/plan all`** (1-2 ore)
   - Loop su tutti gli 8 profiles
   - Batch generation
   - Progress indicator

3. **Aggiorna `/plan <categoria>`** (1 ora)
   - Save output come .md
   - Overwrite se esiste
   - Entry in changelog.json

4. **Testing + Documentation** (2-3 ore)

**Deliverable**: CLI genera e salva piani come .md

---

### Phase 3: Analisi Garmin (Priorità MEDIA)
**Durata stimata**: 1 settimana
**Obiettivo**: Import e analisi workout CSV

1. **Implementa parser CSV Garmin** (3-4 ore)
   - Identifica formato CSV
   - Parser columns (time, distance, HR, pace, etc.)
   - Validation data

2. **Implementa `/analyze <file.csv>`** (4-5 ore)
   - Load CSV
   - Calcolo metriche (laps, zones, cadence)
   - Output formattato con insights

3. **Implementa `/compare`** (3-4 ore)
   - Query running-log.json per tipo/periodo
   - Confronto metriche
   - Trend analysis

4. **Testing + Documentation** (2-3 ore)

**Deliverable**: CLI analizza CSV Garmin e confronta sessioni

---

### Phase 4: Piano Running (Priorità MEDIA-BASSA)
**Durata stimata**: 2-3 settimane
**Obiettivo**: Planning running completo a 3 livelli

1. **Implementa `/plan-season`** (5-6 ore)
   - Parser calendario gare
   - Algoritmo periodizzazione
   - Output season structure

2. **Implementa `/plan-block <N>`** (5-6 ore)
   - Template mesocicli 3:1
   - Generatore sessioni da zone
   - Output block dettagliato

3. **Implementa `/week <N>`** (3-4 ore)
   - Formatter settimana operativa
   - Dettaglio sessioni con ritmi
   - Note e recovery days

4. **Implementa `/taper` e `/race`** (4-5 ore)
   - Algoritmo taper
   - Race pacing calculator
   - Nutrizione race week

5. **Testing + Documentation** (4-5 ore)

**Deliverable**: CLI planning running completo

---

### Phase 5: Forza e Changelog (Priorità BASSA)
**Durata stimata**: 1 settimana
**Obiettivo**: Completare funzionalità secondarie

1. **Implementa `/strength`** (6-8 ore)
   - Template scheda full-body
   - Pool esercizi + progressioni
   - Algoritmo periodizzazione

2. **Implementa `/strength progress`** (2-3 ore)
   - Tracking progressione
   - Display stato esercizi
   - Next step recommendation

3. **Implementa sistema `/log`** (2-3 ore)
   - Display changelog
   - Filtri
   - Diff calculator

4. **Testing + Documentation** (2-3 ore)

**Deliverable**: CLI completo al 100%

---

## 📈 Stima Totale

**Durata Totale Stimata**: 6-8 settimane full-time

**Breakdown**:
- Phase 1 (Tracking): 1 settimana
- Phase 2 (Plans Export): 3-4 giorni
- Phase 3 (Garmin): 1 settimana
- Phase 4 (Running): 2-3 settimane
- Phase 5 (Forza+Log): 1 settimana

**Effort**: ~150-200 ore sviluppo + test + documentazione

---

## 🎯 Prossimi Passi Consigliati

### Immediate (Questa Settimana)

1. **Implementa Phase 1 - Tracking Base**
   - Comandi: `/weigh`, `/status`, `/zones`
   - Durata: 1 settimana
   - Priorità: ALTA (dal PRD)

   **Perché iniziare da qui**:
   - Foundation per tutto il resto
   - Comandi semplici (no ottimizzazione complessa)
   - File data già pronti (composition.json, zones.json)
   - Impatto immediato sull'usabilità
   - Test facili da scrivere

2. **Crea issue/task tracking**
   - GitHub issues per ogni comando
   - Milestone per ogni phase
   - Labels: priority, complexity, status

3. **Setup testing framework**
   - Estendi test suite esistente
   - Add fixtures per data files
   - Mock I/O per tests CLI

### Short-Term (Prossime 2 Settimane)

1. **Completa Phase 1 + Phase 2**
   - Tracking base funzionante
   - Export piani markdown
   - CLI usabile quotidianamente

### Medium-Term (Prossimo Mese)

1. **Implementa Phase 3 - Garmin**
   - Analisi workout
   - Tracking progressione running

### Long-Term (Prossimi 2-3 Mesi)

1. **Completa Phase 4 + Phase 5**
   - Piano running completo
   - Forza + changelog

---

## 🔍 Note Architetturali

### Separazione Concerns

Il progetto mantiene una chiara separazione:

1. **Meal Planning** (v2.0 FROZEN)
   - Solver core frozen
   - No modifiche al beam search
   - Solo bug fixes

2. **Tracking & Running** (da implementare)
   - Comandi separati
   - Nessuna dipendenza dal meal balancer
   - Possono essere sviluppati in parallelo

### Filosofia CLI

- **Comandi singoli** (`/weigh`, `/status`, `/zones`)
- **Exit codes standard** (0=success, 1=error)
- **Output formattato** (human-readable)
- **JSON export opzionale** (`--json`)
- **Validazione sempre attiva** (fail-fast)

### Data Integrity

Tutti i comandi che modificano data files devono:
1. Validare input
2. Append (non overwrite) se storico
3. Entry in changelog.json
4. Verificare integrità cross-file
5. Exit code appropriato

---

## 📚 Risorse Esistenti

### Documentation
- CLAUDE.md - Setup e comandi
- training-vantage-prd.md - PRD completo (2600+ righe)
- docs/CLI_USAGE.md - Guida CLI meal planning
- docs/V2_FREEZE_DECLARATION.md - Architettura freeze v2.0

### Data Files (Pronti)
- data/composition.json (7 misurazioni storiche)
- data/zones.json (3 test + zone attuali)
- data/running-log.json (storico workout)
- data/strength-progress.json (inizializzato vuoto)
- data/changelog.json (vuoto)

### Knowledge Base
- knowledge/linee-guida.md (regole nutrizionali + running)
- sources/ (file sorgente vari)

---

## ✅ Conclusioni

**Status**: Progetto al ~30% di completamento

**Componente Completata**:
- Meal planning v2.0 (FROZEN) - Production-ready

**Priorità Immediate** (dal PRD):
1. Tracking base (`/weigh`, `/status`, `/zones`) - **1 settimana**
2. Export piani markdown - **3-4 giorni**

**Stima Completamento Totale**: 6-8 settimane

**Next Action**: Implementare Phase 1 (Tracking Base) seguendo roadmap sopra.

---

**Analisi effettuata**: 2026-02-12
**Version attuale**: 2.0 (meal planning only)
**Target version completa**: 3.0 (all features)
