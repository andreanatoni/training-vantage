# Session Summary - 2026-02-14

## Contesto
Obiettivo principale della sessione: consolidare il sistema dati nutrizionale (CREA + porzioni LARN), migliorare workflow CLI (`tv food ...`) e impostare la base per la generazione piani alimentari quantitativi da template.

## Risultati principali

### 1) Food DB e import CREA
- Implementato import da URL/id CREA in `./tv food add`.
- Aggiornamento atomico dei 3 file:
  - `data/FOOD_DB.json`
  - `data/FOOD_DB_TO_LARN_MAPPING.json`
  - `knowledge/food-db.md`
- Gestione fuzzy match su nome alimento.
- Aggiunta opzione sostituzione (`--replace`) per rimpiazzare alimento esistente.
- Implementata tabella comparativa valori (nuovo alimento vs possibili match) per decidere skip/sostituzione.

### 2) Pipeline CREA massiva
- Creati comandi:
  - `./tv food crawl-index` -> genera `data/CREA_INDEX.json` + `knowledge/crea-index.md`
  - `./tv food import-crea ...`
  - `./tv food rebuild-from-crea`
- Rebuild completo eseguito con successo:
  - 832 alimenti importati
  - 0 fallimenti finali
- Backup automatici creati in `data/backups/`.

### 3) Source of truth e sync/check
- Consolidato approccio JSON-master:
  - `data/FOOD_DB.json` come source of truth
  - `knowledge/food-db.md` vista generata
- Introdotti:
  - `./tv food sync`
  - `./tv food check`
- Verifica corrente: `[CHECK] FOOD_DB OK - foods: 832, mapping: 832`.

### 4) Estrazione porzioni da PDF LARN
- Implementata estrazione tabelle dal PDF `sources/Standard-Quantitativi-delle-Porzioni.pdf`:
  - output: `data/PORTION_STANDARDS.json`
- Pulizia testuale/casing e normalizzazione tramite script dedicato.

### 5) LARN_PORTIONS e OPERATIVE_PORTIONS
- Allineato `data/LARN_PORTIONS.json` alla Tabella 2 (42 voci complete), poi evoluto a v3 con metadata/compatibilità.
- Aggiornato `data/OPERATIVE_PORTIONS.json` a v2 (campi aggiuntivi + compatibilità legacy).

### 6) Mapping v2.1
- Upgrade completato su `data/FOOD_DB_TO_LARN_MAPPING.json`:
  - `meta.version = v2.1`
  - campi revisione inizializzati (`review_status`, `mapping_confidence`, `mapping_source`, `last_reviewed_at`)
- Backup creato:
  - `data/backups/FOOD_DB_TO_LARN_MAPPING-20260214-105331.json`

### 7) Documentazione
- Creato `AGENTS.md` (Repository Guidelines).
- Creato `data/README.md` come documentazione ufficiale cartella dati.
- Aggiornato `README.md` root con link a `data/README.md`.

## Decisioni prodotto approvate

1. Nuovo template alimentare in formato JSON (master), da cui generare anche versione markdown leggibile.
2. Il template contiene opzioni equivalenti A/B/C per ciascun pasto.
3. I vincoli qualitativi sono in `linee-guida.md`.
4. Quantità generate automaticamente, ma solo usando gli alimenti/opzioni approvati nel piano base.
5. Priorità motore: `performance > aderenza > precisione macro`.
6. Supporto output doppio: `.json` + `.md`.
7. Supporto comando per giornata tipo e modifica singolo pasto.

## Backup recente richiesto
- File backup creato:
  - `sources/piano_base_ottimizzato-backup-20260214-113039.md`

## Stato tecnico rapido
- Test automatici: `22 OK`.
- Controllo food DB: OK.
- Working tree contiene molte modifiche e nuovi file (coerenti con le attività della sessione).

## Prossimi passi suggeriti

1. Definire schema `data/PLAN_BASE_TEMPLATE.json` (v1) e validatore.
2. Creare convertitore da `sources/piano_base_ottimizzato.md` -> JSON template.
3. Implementare generatore giornata:
   - input: day-type + dati composizione + fase/carico
   - output: `plans/nutrition/<day>.json` e `.md`
4. Introdurre hard-limit porzioni per categoria alimento (LEAN + personalizzazione).
5. Aggiungere test su:
   - validità schema
   - rispetto hard-limit
   - fallback quando target macro non raggiungibili con opzioni scelte.
