# Training Vantage — Setup Claude Code

## Cosa è questo file

Questo file è il punto di partenza per implementare Training Vantage con Claude Code.
Il PRD completo è in `training-vantage-prd.md` (2600+ righe). Questo file estrae solo
ciò che serve per iniziare a codare.

---

## Modello da usare

**Sonnet** per tutta l'implementazione. Opus solo se Sonnet si blocca su logica complessa.
Vedi `guida-opus-vs-sonnet.md` nel progetto per i criteri dettagliati.

---

## Architettura

Training Vantage è un **CLI tool** (non web app) che gira dentro Claude Code come set di comandi.

```
training-vantage/
├── CLAUDE.md                    # Istruzioni per Claude Code (leggi SEMPRE prima)
├── knowledge/
│   ├── linee-guida.md           # Bibbia del programma (già esistente nel progetto)
│   ├── food-db.md               # Database nutrizionale master (già esistente)
│   └── piano-base.md            # Piano base validato (convertire da piano_base_ottimizzato.md)
├── plans/
│   ├── nutrition/
│   │   ├── forza.md
│   │   ├── easy-run.md
│   │   ├── qualita.md
│   │   ├── tempo.md
│   │   ├── lungo.md
│   │   ├── rest.md
│   │   ├── pizza-day.md
│   │   └── domenica.md
│   └── running/
│       └── week-{N}.md          # Piani settimanali running
├── data/
│   ├── composition.json         # Storico pesate
│   ├── zones.json               # Zone attuali + storico test
│   ├── running-log.json         # Log sessioni (Excel + Garmin)
│   ├── strength-progress.json   # Progressione forza
│   └── changelog.json           # Log modifiche
└── scripts/
    └── garmin-import.py         # Parser CSV Garmin
```

---

## CLAUDE.md — Il file più importante

Questo file va nella root del progetto e Claude Code lo legge automaticamente.
Deve contenere:

```markdown
# Training Vantage — Istruzioni per Claude Code

## Contesto
Tool CLI per gestione allenamento running + nutrizione + composizione corporea.
Utente: Andrea, runner amatoriale competitivo, preparazione maratona dic 2026.

## File di riferimento
- PRD completo: training-vantage-prd.md (consultare per specifiche dettagliate)
- Linee guida: knowledge/linee-guida.md (SEMPRE consultare prima di modificare piani)
- Food DB: knowledge/food-db.md (SSoT per valori nutrizionali)
- Piano base: knowledge/piano-base.md (SSoT per combinazioni alimentari)

## Comandi disponibili (implementare in ordine di priorità)

### Priorità 1 — Tracking base
- `/weigh <peso> <bf%>` — Registra pesata, calcola FFM/BMR, aggiorna composition.json
- `/status` — Mostra stato attuale (ultima pesata, zone, prossima gara, alerts)
- `/zones [test_time]` — Mostra zone attuali o ricalcola da nuovo test

### Priorità 2 — Nutrizione
- `/plan <categoria>` — Genera piano quantitativo da piano-base + food-db
- `/plan all` — Rigenera tutti e 8 i piani
- `/food add <alimento>` — Aggiunge alimento a food-db.md

### Priorità 3 — Running
- `/week <N> [type]` — Mostra/genera piano running settimanale
- `/analyze <file.csv>` — Analizza export CSV Garmin singolo workout
- `/compare <tipo> [periodo]` — Confronta sessioni simili

### Priorità 4 — Forza e validazione
- `/strength <week_type>` — Genera scheda forza (base/build/peak/scarico)
- `/checkpoint` — Template checkpoint con dati attuali
- `/validate sync` — Verifica allineamento file

## Regole operative
1. MAI modificare knowledge/ senza chiedere conferma
2. Ogni modifica a plans/ o data/ → entry in changelog.json
3. Piani nutrizionali: SOLO combinazioni da piano-base.md, valori da food-db.md
4. Se FFM < 59.5 → WARNING in ogni output
5. Se un file è STALE (FFM nel META ≠ composition.json) → segnalare
```

---

## Step 1 — Bootstrap (prima sessione)

Cosa fare nella prima sessione di Claude Code:

### 1. Crea struttura cartelle
```bash
mkdir -p training-vantage/{knowledge,plans/nutrition,plans/running,data,scripts}
```

### 2. Crea CLAUDE.md
Copia il contenuto dalla sezione sopra.

### 3. Popola data/composition.json
7 misurazioni dal PRD (sezione "1. composition.json — Storico pesate").

### 4. Popola data/zones.json
3 test + zone attuali dal PRD (sezione "2. zones.json").

### 5. Converti piano-base
Da `piano_base_ottimizzato.md` (progetto) → `knowledge/piano-base.md` (formato pulito).
Vedi PRD sezione "piano-base.md format" per le regole di conversione.

### 6. Copia file esistenti in knowledge/
- `linee-guida.md` → `knowledge/linee-guida.md`
- `tabella_opzioni_raccomandate.md` o food-db equivalente → `knowledge/food-db.md`

### 7. Popola data/running-log.json
Converti `pianorunning.xlsx` → JSON (vedi PRD sezione bootstrap).
Match con `storico.csv` per arricchire con dati Garmin.

### 8. Inizializza data/strength-progress.json
Tutto "not_started", prima sessione 2026-02-12.

### 9. Inizializza data/changelog.json
Prima entry = bootstrap stesso.

---

## Step 2 — Implementa /weigh e /status

Questi sono i comandi più semplici e immediatamente utili.

### /weigh
```
Input: peso (float), bf% (float)
Processo:
  1. Calcola FFM = peso × (1 - bf/100)
  2. Calcola BMR (Katch-McArdle) = 370 + 21.6 × FFM
  3. Appendi a composition.json
  4. Confronta con misurazione precedente (delta)
  5. Check red flags: FFM < 59.5, peso drop > 0.6%/sett
Output: Tabella con valori + delta + alerts
```

### /status
```
Legge: composition.json, zones.json, running-log.json, prossima gara
Output:
  - Ultima pesata + trend
  - Zone attuali + data test
  - Settimana corrente nel piano
  - Giorni a prossima gara
  - Alerts attivi (FFM, stale plans, etc.)
```

---

## Step 3 — Implementa /zones

```
Input opzionale: tempo test 5km (es. "18:26" o "17:55")
Se senza input: mostra zone attuali
Se con input:
  1. Calcola pace = tempo / 5
  2. Applica formule:
     Z6 = pace + 9"
     Z5 = Z6 + 8"
     Z4 = Z6 + 20"
     Z3 = Z4 + 14"
     Z2 = Z3 + 24"
     Z1 = Z2 + 31"
     Z7 = pace - 2" a pace - 12"
     Z8 = pace - 12" a pace - 16"
  3. Aggiorna zones.json (nuovo set + storico)
  4. Mostra confronto vecchie vs nuove
  5. Segnala piani running che usano zone vecchie
```

---

## Dati attuali per reference

### Composizione (11/02/2026)
- Peso: 68.65 kg | BF: 13.2% | FFM: 59.57 kg | BMR: 1656 kcal

### Zone (test 09/02/2026 — 18:27, 3:41/km)
- Z1: 5:11+ | Z2: 4:40-5:11 | Z3: 4:16-4:40 | Z4: 4:02-4:16
- Z5: 3:50-4:02 | Z6: 3:42-3:50 | Z7: 3:29-3:42 | Z8: 3:25-3:29

### Prossima gara
Roma-Ostia Half Marathon — 1 marzo 2026 (18 giorni)

### Calendario
| Gara | Data | Target |
|------|------|--------|
| Roma-Ostia HM | 01/03/2026 | 4:00/km (1:24) |
| Latina HM | 29/03/2026 | sub 1:24 (PB) |
| Mezza Roma | 18/10/2026 | test pre-maratona |
| Maratona Latina | 06/12/2026 | prima maratona |

---

## File del progetto Claude da portare in training-vantage/

Questi file sono nella Knowledge Base del progetto Claude e vanno copiati/convertiti:

| File progetto | Destinazione | Note |
|---------------|-------------|------|
| linee-guida.md | knowledge/linee-guida.md | Copia diretta |
| piano_base_ottimizzato.md | knowledge/piano-base.md | Convertire formato (vedi PRD) |
| tabella_opzioni_raccomandate.md | knowledge/food-db.md | Verificare completezza |
| piano_forza.md | plans/nutrition/forza.md | Aggiungere META comment |
| piano_easy_run.md | plans/nutrition/easy-run.md | Aggiungere META comment |
| piano_qualita.md | plans/nutrition/qualita.md | Aggiungere META comment |
| piano_tempo.md | plans/nutrition/tempo.md | Aggiungere META comment |
| piano_lungo.md | plans/nutrition/lungo.md | Aggiungere META comment |
| piano_rest.md | plans/nutrition/rest.md | Aggiungere META comment |
| piano_pizza_day.md | plans/nutrition/pizza-day.md | Aggiungere META comment |
| piano_domenica.md | plans/nutrition/domenica.md | Aggiungere META comment |
| pianorunning.xlsx | → data/running-log.json | Convertire via script |
| storico.csv | Merge in running-log.json | Match per data+distanza |
| composizione_corporea.xlsx | → data/composition.json | Già convertito |

---

## Prompt da dare a Claude Code per iniziare

```
Leggi CLAUDE.md e training-vantage-prd.md. 
Poi esegui il bootstrap:
1. Crea la struttura cartelle
2. Popola composition.json con le 7 misurazioni dal PRD
3. Popola zones.json con i 3 test e le zone attuali
4. Inizializza changelog.json e strength-progress.json
5. Mostrami lo stato dei file creati.

Non convertire ancora i piani nutrizionali né il running log — quelli richiedono 
i file sorgente che ti passerò dopo.
```
