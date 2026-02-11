# ReShape CLI - Architettura Claude Code

## Overview

Sistema di gestione per programma di ricomposizione corporea + preparazione gare,
basato su Claude Code con orchestratore centrale e tool specializzati.

**Filosofia**: Non multi-agente, ma un orchestratore + tool deterministici.
L'automazione serve per consistenza e validazione, non per decisioni strategiche.

---

## Struttura progetto

```
reshape-cli/
|-- CLAUDE.md                    # Istruzioni orchestratore
|-- knowledge/
|   |-- linee-guida.md           # Source of truth regole
|   |-- food-db.md               # MASTER nutrizionale
|   |-- piano-base.md            # Combinazioni approvate (Fase 1)
|   +-- zones.json               # Zone attuali + storico test
|-- plans/
|   |-- nutrition/               # Piani nutrizionali (8 categorie)
|   |   |-- rest.md
|   |   |-- forza.md
|   |   |-- easy-run.md
|   |   |-- qualita.md
|   |   |-- progressivo.md
|   |   |-- lungo.md
|   |   |-- pizza-day.md
|   |   +-- domenica.md
|   +-- running/                 # Piani running (3 livelli)
|       |-- season.md            # Livello 1: macro-struttura stagione
|       |-- block-01.md          # Livello 2: mesociclo dettagliato
|       |-- block-02.md
|       +-- ...
|-- data/
|   |-- composition.json         # Storico pesate
|   |-- running-log.json         # Settimane + workout
|   |-- checkpoints.json         # Storico checkpoint
|   |-- changelog.json           # Log modifiche (append-only)
|   +-- strength-progress.json   # Livelli esercizi + storico sessioni forza
|-- garmin/                      # CSV Garmin importati
|   +-- ...
|-- tools/
|   |-- nutrition-calc/          # Tool calcolo piani
|   |-- zone-calc/               # Tool ricalcolo zone
|   |-- analyze/                 # Tool analisi CSV Garmin
|   +-- validate/                # Tool validazione cross-doc
+-- output/
    +-- ...                      # Report e piani generati
```

---

## CLAUDE.md (orchestratore)

```markdown
# ReShape CLI - Running Coach & Nutrition System

## Ruolo
Sistema di gestione per programma di ricomposizione corporea
+ preparazione gare di un runner amatoriale competitivo.

## Source of Truth
- Regole e vincoli: knowledge/linee-guida.md
- Dati nutrizionali: knowledge/food-db.md
- Combinazioni pasti: knowledge/piano-base.md
- Zone: knowledge/zones.json
- Composizione: data/composition.json

## Regole critiche
- OGNI modifica a un piano DEVE passare per il tool di validazione
- Nessun output piano senza audit superato
- I valori nutrizionali derivano SOLO da food-db.md (MASTER)
- Le distribuzioni % derivano SOLO da linee-guida.md
- Le zone derivano SOLO da zones.json
```

---

## Formato file piani nutrizionali (`plans/*.md`)

I piani sono sia **output** (generati da `/plan`) che **input** (letti da `/validate`,
`/swap`, e dall'utente per uso quotidiano). Il formato deve essere:
- **Leggibile** da un umano che apre il .md
- **Parsabile** deterministicamente dai tool

**Principio**: il contenuto visibile resta identico al formato attuale (markdown standard
con tabelle, opzioni, totali, swap). I metadati per il tool vanno in **commenti HTML**
invisibili al rendering.

---

### Struttura completa di un piano

```markdown
<!-- META
categoria: QUALITA
generato: 2026-02-11
ffm: 59.57
peso: 68.65
bmr: 1657
pal: 1.65
tdee: 2734
deficit: -5%
target_kcal: 2597
fase: Pre-gara HM
zones_date: 2026-02-09
-->

# Piano QUALITA' - Mercoledi' (Quantificato)

**Categoria**: Allenamento Qualita' (18:00-19:30)
**Distribuzione**: 17% | 7% | 33% | 18% | 5% | 25%
**Logica**: Max CHO pre-intensita', performance su ripetute/soglia

---

## FOOD_DB - Database Nutrizionale

| Alimento | Riferimento | kcal | P (g) | CHO (g) | F (g) | Fibre (g) | Fonte |
|----------|-------------|------|-------|---------|-------|-----------|-------|
| Pasta secca (di semola) | 100 g | 341 | 13.5 | 72.7 | 1.2 | 1.7 | CREA |
| Olio EVO | 100 g | 899 | 0.0 | 0.0 | 99.9 | 0.0 | CREA |
| ... | ... | ... | ... | ... | ... | ... | ... |

**FOOD_DB: 42 voci importate dal MASTER (0 mismatch)**

---

## CALCOLO TARGET GIORNO

**Dati fisici**: Peso 68.65 kg | FFM 59.57 kg

[calcoli BMR, TDEE, deficit, macro, EA — identici al formato attuale]

---

## DISTRIBUZIONE PER PASTO

| Pasto | % | Kcal | P (g) | F (g) | CHO (g) |
|-------|---|------|-------|-------|---------|
| Colazione | 17% | 441 | ... | ... | ... |
| ... | ... | ... | ... | ... | ... |

---

# COLAZIONE - 07:30-08:30
**Target**: 441 kcal | 24g P | 11g F | 61g CHO

### Opzione 1 - Dolce classica con fette biscottate
- Caffe' espresso: 100 ml
- Fette biscottate: 50 g
- Marmellata: 25 g
- Yogurt magro 0.1%: 125 g
- Mandorle: 11 g

**Totali**: 450 kcal | 15.8g P | 12.9g CHO | 59.9g F | 5.6g Fibre

**Swap**: Fette 50g <-> Pane integrale 55g | Mandorle <-> Noci 11g
**Quando**: Colazione veloce, CHO per qualita' serale.

---

### Opzione 2 - ...
[altre opzioni, stesso formato]

---

# SPUNTINO_AM - 10:30-11:00
[stesso pattern]

# PRANZO - 13:00-13:30
[stesso pattern]

# SPUNTINO_PM - 16:00
[stesso pattern]

# SPUNTINO_SERA - Post-qualita'
[stesso pattern]

# CENA - 20:15-20:45
[stesso pattern]

---

## AUDIT FINALE

**Verifica opzioni per pasto** (tutte entro +/-20 kcal, +/-1g P, +/-2g CHO/F): OK

**Verifica media pasti** (tutte entro +/-30 kcal dal target): OK

**Totali giornata**:
- Target: 2597 kcal | 137g P | 62g F | 350g CHO
- Calcolato: 2595 kcal | 138g P | 63g F | 349g CHO
- Delta%: -0.08% OK | P 2.01 g/kg OK | F 0.92 g/kg OK

**STATO: PIANO VALIDATO**

<!-- AUDIT: VALIDATO | 2026-02-11 | delta_kcal:-0.08% | P:2.01g/kg | F:0.92g/kg | food_db:42/0 -->

---

## TIMING OTTIMALE GIORNATA

[timing identico al formato attuale]
```

---

### Regole di parsing per i tool

I tool leggono i piani con queste convenzioni:

**1. Commento META** (riga 1 del file)
```
Regex: <!-- META\n(.*?)\n-->
```
Contiene coppie `chiave: valore` una per riga. Il tool usa:
- `ffm` e `peso`: per verificare se il piano e' stale (confronto con composition.json)
- `target_kcal`: per validazione rapida senza ricalcolare
- `generato`: data ultima generazione
- `fase`: per contestualizzare
- `zones_date`: per verificare allineamento zone (rilevante per piani running)

**Staleness check**: se `ffm` nel META differisce da composition.json corrente
di piu' di 0.5 kg, il piano e' stale e `/validate sync` lo segnala.

**2. Sezione FOOD_DB**
```
Trigger: riga che inizia con "## FOOD_DB" o "## 📊 FOOD_DB"
Fine: prima riga vuota dopo la tabella, o prossimo "##"
Formato: tabella markdown standard con separatore "|"
```
Il tool confronta ogni riga con il MASTER food-db.md.
Mismatch = stesso alimento ma valori diversi.

**3. Sezione pasti**
```
Trigger: riga "# COLAZIONE" o "# PRANZO" ecc. (H1 con nome pasto)
Il nome pasto e' il testo dopo "# " e prima di " -" (es. "COLAZIONE", "SPUNTINO_AM")
```
Nomi pasto riconosciuti: COLAZIONE, SPUNTINO_AM, PRANZO, SPUNTINO_PM,
SPUNTINO_SERA, CENA

**4. Opzioni dentro un pasto**
```
Trigger: "### Opzione N" (H3)
ID implicito: <PASTO>-<N> (es. COLAZIONE-1, PRANZO-3)
```
Non servono ID espliciti nel testo: la posizione nel file li determina.

**5. Ingredienti di un'opzione**
```
Formato: "- <Alimento>: <quantita'> <unita'>"
Regex: ^- (.+?):\s*(\d+)\s*(g|ml|porzione)
```
Le righe con "OR" contengono alternative:
```
"- Pollo piastra: 125g OR Tacchino: 115g OR Vitello: 125g"
Regex: (.+?):\s*(\d+)\s*g(?:\s*OR\s*(.+?):\s*(\d+)\s*g)*
```

**6. Totali opzione**
```
Trigger: riga che inizia con "**Totali**:"
Regex: \*\*Totali\*\*:\s*(\d+)\s*kcal\s*\|\s*([\d.]+)g\s*P\s*\|\s*([\d.]+)g\s*CHO\s*\|\s*([\d.]+)g\s*F
```
Il tool ricalcola i totali da ingredienti x FOOD_DB e confronta.

**7. Swap**
```
Trigger: riga che inizia con "**Swap**:"
Formato: "Alimento Xg <-> Alimento Yg"
Separatore tra swap diversi: " | "
```

**8. Commento AUDIT** (fine file)
```
Regex: <!-- AUDIT: (.+?) \| (.+?) \| delta_kcal:(.+?) \| P:(.+?) \| F:(.+?) \| food_db:(\d+)/(\d+) -->
```
Parsing rapido dello stato senza dover rileggere tutto il file.
Il primo numero food_db e' il totale voci, il secondo i mismatch (deve essere 0).

---

### Migrazione formato attuale -> nuovo

Delta minimo rispetto ai piani esistenti:

| Elemento | Formato attuale | Nuovo formato | Azione |
|----------|----------------|---------------|--------|
| Header piano | Emoji + titolo | Titolo senza emoji | Rimuovi emoji (opzionale, parsing le ignora) |
| META | Assente | Commento HTML in testa | **Aggiungere** |
| FOOD_DB | Presente, identica | Identica | Nessuna |
| Calcolo target | Presente, identico | Identico | Nessuna |
| Distribuzione | Presente, identica | Identica | Nessuna |
| Header pasti | "# ☕ COLAZIONE" | "# COLAZIONE" | Rimuovi emoji (opzionale) |
| Opzioni | Identiche | Identiche | Nessuna |
| Totali/Swap | Identiche | Identiche | Nessuna |
| Audit visibile | Presente, identico | Identico | Nessuna |
| Audit parsabile | Assente | Commento HTML in coda | **Aggiungere** |

**In pratica**: aggiungi 8 righe di commento HTML in testa + 1 riga in coda.
Il resto del file resta identico.

---

### Gestione emoji

Le emoji nel formato attuale (📊, ☕, 🍝, 🍽️, ✅, ecc.) sono decorative.
I tool le ignorano nel parsing (le regex matchano il testo dopo l'emoji).
Si possono tenere o rimuovere a preferenza dell'utente — nessun impatto funzionale.

Consiglio: **tenerle** per la leggibilita' umana, il tool le salta.

---

## Formato file piani running

I piani running hanno 3 livelli di file, corrispondenti ai 3 livelli di comando.

### `plans/running/season.md` — piano stagionale

```markdown
<!-- META
generato: 2026-02-11
gare: roma-ostia,latina-hm,pedagnalonga,mezza-roma,maratona-latina
fase_corrente: Pre-gara HM
zones_date: 2026-02-09
-->

# Stagione 2026

## Calendario gare

| Data | Gara | Tipo | Target | Taper |
|------|------|------|--------|-------|
| 1 mar | Roma-Ostia HM | A-race | 1:24:00 (4:00/km) | 10-12 gg |
| 29 mar | Latina HM | PB | sub 1:24 | 5-7 gg |
| 26 apr | Pedagnalonga | Allenamento | - | Nessuno |
| 18 ott | Mezza Roma | Test | TBD | Nessuno |
| 6 dic | Maratona Latina | A-race | TBD | 3 sett |

## Mesocicli e volume

| Sett | Date | Meso | Tipo | Vol(km) | Fase | Note |
|------|------|------|------|---------|------|------|
| 1-3 | 6-26 gen | M1 | Carico | 30/33/35 | Pre-gara HM | Build |
| 4 | 27 gen | M1 | Scarico | 20 | Pre-gara HM | Test 5km |
| 5-7 | 3-17 feb | M2 | Carico | 35/40/44 | Pre-gara HM | Peak |
| 8 | 24 feb | M2 | Scarico | 25 | Pre-gara HM | Test pre-RO |
| -- | 1 mar | -- | GARA | -- | -- | Roma-Ostia |
| ... | ... | ... | ... | ... | ... | ... |

## Curva volume

[dati per visualizzazione grafica: sett, volume_target]
```

**Parsing**: tabella mesocicli parsata per riga, colonna `Sett` identifica
la settimana, `Meso` il mesociclo di appartenenza, `Vol(km)` il target.

---

### `plans/running/block-N.md` — piano mesociclo

```markdown
<!-- META
blocco: 6
settimane: 21-24
generato: 2026-04-01
fase: Transizione
focus: base aerobica + ricostruzione FFM
volume_blocco: 131
zones_date: 2026-03-29
prossima_gara: Pedagnalonga 26 apr (allenamento)
-->

# Blocco 6 (sett 21-24) — Transizione

**Focus**: Base aerobica + ricostruzione FFM
**Volume blocco**: 131 km (media 33 km/sett)
**Prossima gara**: Pedagnalonga 26 apr (allenamento)

## Settimana 21 (Base) — 30 km

| Giorno | Sessione | Dettaglio | Km |
|--------|----------|-----------|-----|
| Lun | D.A. | 6 km [Z2 + 4x200m allunghi Z7-Z8] | 6 |
| Mar | FORZA | Scheda Base, sett 1 | - |
| Mer | Ripetute | 5x1km rec 2' [Z5-Z6 3:50-4:02] | 8 |
| Gio | FORZA | Scheda Base, sett 1 | - |
| Ven | Progressivo | 4L+2M [L=Z2 4:50 / M=Z3 4:30] | 8 |
| Sab | Lungo | 12 km L [Z2 4:45-5:00] | 12 |
| Dom | Rest | - | - |

**Volume**: 34 km (target: 30) [nota: +4 da risc/defat]

## Settimana 22 (Build) — 34 km
[stesso formato tabella]

## Settimana 23 (Peak) — 38 km
[stesso formato tabella]

## Settimana 24 (Scarico) — 25 km
[stesso formato tabella, include TEST 5km il sabato]

<!-- AUDIT: GENERATO | 2026-04-01 | vol_totale:131km | 80/20:82/18 | max_increment:12% -->
```

**Parsing**: ogni settimana e' un H2 con formato fisso
`## Settimana N (Tipo) — X km`. La tabella interna ha colonne fisse.

---

### Dettaglio settimanale (output di `/week`)

Il `/week` non genera un file persistente. Produce output a console/chat
con il dettaglio operativo di una settimana gia' presente in un block.
Se serve persistenza, l'utente puo' salvarlo, ma non e' un file gestito dai tool.

---

## Comandi disponibili

### NUTRIZIONE

| Comando | Cosa fa | Input | Output |
|---------|---------|-------|--------|
| `/plan <categoria>` | Genera piano quantitativo completo | Categoria (rest/forza/easy-run/qualita/progressivo/lungo/pizza-day/domenica) | Piano .md validato con audit |
| `/plan all` | Rigenera tutti gli 8 piani | - | 8 piani .md |
| `/plan update <cat> <modifica>` | Modifica chirurgica a un piano | Categoria + descrizione modifica | Piano aggiornato |
| `/swap <old> <new>` | Swap alimento in tutti i piani | Alimento da sostituire + sostituto | Piani aggiornati + audit |
| `/food add <alimento> <valori>` | Aggiunge voce al MASTER food-db | Nome, kcal, P, CHO, F, fibre, fonte | food-db.md aggiornato |
| `/food check <alimento>` | Verifica valori di un alimento nel MASTER | Nome alimento | Valori + fonte |
| `/macro <categoria>` | Mostra target macro senza generare piano | Categoria | Target kcal, P, F, CHO + distribuzione pasti |

#### Logica interna `/plan`

```
1. Legge food-db.md (importa valori per 100g)
2. Legge linee-guida.md (distribuzioni % per categoria)
3. Legge piano-base.md (combinazioni approvate)
4. Legge composition.json (FFM, peso attuali)
5. Calcola: BMR -> TDEE -> deficit (per fase) -> macro giorno
6. Distribuisce per pasto (% da linee-guida per categoria)
7. Calcola grammature per ogni opzione
8. Arrotonda: cereali/pasta/riso/pane 5g, verdure 10g,
   olio/burro arachidi 1g, proteine/affettati/formaggi/pesce 5g
9. Verifica soglie:
   - Opzione: +/-20 kcal, +/-1g P, +/-2g CHO, +/-2g F
   - Pasto medio: +/-30 kcal
   - Giorno: +/-1% kcal, P 2.0-2.2 g/kg
10. Se fallisce -> ricalcola internamente (max 3 tentativi)
11. Output: piano validato con FOOD_DB + calcoli + pasti + audit
```

---

### ZONE E TEST

| Comando | Cosa fa | Input | Output |
|---------|---------|-------|--------|
| `/test <tempo>` | Registra test 5km, ricalcola zone | Tempo test (mm:ss) | Nuove zone + confronto precedenti |
| `/zones` | Mostra zone attuali | - | Tabella Z1-Z8 |
| `/zones history` | Storico test e progressione | - | Tabella cronologica test + zone |

#### Logica interna `/test`

```
1. Parsing tempo -> calcola ritmo medio (min/km)
2. Applica formule:
   Z6 = ritmo test + 9"
   Z5 = Z6 + 8"
   Z4 = Z6 + 20"
   Z3 = Z4top + 14"
   Z2 = Z3top + 24"
   Z1 = Z2top + 31"
   Z7 = ritmo test -2" a -12"
   Z8 = ritmo test -12" a -16"
3. Salva in zones.json (append, non sovrascrivere storico)
4. Mostra confronto con test precedente
5. Chiede: "Vuoi rigenerare i piani running con le nuove zone? [y/n]"
```

---

### FORZA E TECNICA DI CORSA

#### Comandi

| Comando | Cosa fa | Input | Output |
|---------|---------|-------|--------|
| `/strength <sett_tipo>` | Genera scheda forza per la settimana | base/build/peak/scarico | Scheda completa con esercizi, serie, rip, note |
| `/strength progress` | Mostra progressione esercizi | - | Stato corrente ogni esercizio + prossimo step |
| `/drills` | Mostra routine drills pre-lungo | - | Sequenza drills tecnica con cue |

---

#### Filosofia: scheda unica full-body

**Perche' full-body e non split:**
L'aderenza storica alle sessioni forza e' bassa (quasi zero nov 2025 - feb 2026).
Con una scheda full-body unica:
- Se fai 2x/sett (Mar+Gio): copri tutto due volte, risultati ottimali
- Se fai 1x/sett: copri comunque tutto una volta, meglio di zero
- Con lo split (upper/lower), saltare un giorno = perdere meta' del lavoro

**Regola**: stessa struttura Mar e Gio, esercizi variati per diversita'.
Il tool genera 2 varianti (A e B) dalla stessa struttura.

---

#### Struttura seduta full-body (40-50')

```
BLOCCO 1 — Warm-up dinamico (5')
  Obiettivo: mobilita' articolare + attivazione neuromuscolare
  Non e' stretching statico. E' preparazione al movimento.

BLOCCO 2 — Pliometria / Esplosivita' (8')
  Obiettivo: stiffness tendinea, esplosivita', reclutamento fibre rapide
  VA SEMPRE PRIMA DELLA FORZA (richiede SN fresco)
  Volume basso: 2-3 esercizi, 2-3 serie, 5-8 rip
  Recupero: completo (60-90" tra serie)

BLOCCO 3 — Lower body forza (10')
  Obiettivo: forza monopodalica + catena posteriore + stiffness tendine Achille
  2 esercizi, 3 serie ciascuno
  Focus single-leg (la corsa e' una sequenza di appoggi singoli)

BLOCCO 4 — Core intensive (12')
  Obiettivo: anti-estensione, anti-rotazione, flessione
  3 esercizi, 3-4 serie ciascuno
  Pool esercizi: identico a linee-guida attuali

BLOCCO 5 — Upper push/pull (8')
  Obiettivo: mantenimento FFM upper body, bilanciamento posturale
  2 esercizi in superserie (push + pull -> risparmia tempo)
  3 serie per esercizio

BLOCCO 6 — Mobilita' funzionale running (5')
  Obiettivo: ROM attivo su caviglie, anche, colonna toracica
  Non stretching passivo. Mobilita' sotto carico o dinamica.
```

**Ordine non negoziabile**: Pliometria PRIMA di forza.
Farla affaticati annulla il beneficio neuromuscolare e aumenta rischio infortunio.

---

#### Pool esercizi completo

##### BLOCCO 1 — Warm-up dinamico

| Esercizio | Rip/Durata | Note |
|-----------|-----------|------|
| Cerchi caviglie (bipodalico) | 10 per direzione | Piedi scalzi se possibile |
| World's greatest stretch | 5 per lato | Mobilita' anche + thoracic rotation |
| Cat-cow | 10 rip | Segmentale, lento |
| Glute bridge hold | 2x15" | Attivazione glutei pre-lavoro |
| Inchworm | 5 rip | Catena posteriore + core |
| Leg swing frontale + laterale | 10 per gamba per direzione | Progressivi, non forzati |

**Seleziona 4-5 esercizi per sessione (5' totali)**

---

##### BLOCCO 2 — Pliometria / Esplosivita'

**Pool esercizi (dal meno al piu' impegnativo):**

| Esercizio | Serie x Rip | Progressione | Attrezzatura | Note |
|-----------|------------|-------------|-------------|------|
| Pogo jump (caviglie) | 3x10 | Base | Nessuna | Minimo piegamento ginocchio, rimbalzo elastico puro. Focus: stiffness tendine Achille |
| Skip basso sul posto | 3x15" | Base | Nessuna | Contatto rapido, piede sotto baricentro |
| Squat jump | 3x6 | Intermedio | Nessuna | Accosciata parallelo, esplosione verso l'alto, atterraggio morbido |
| Split squat jump | 3x5/lato | Intermedio | Nessuna | Alternare gambe in volo. Stabilita' all'atterraggio |
| Box jump (su blocchi yoga impilati) | 3x5 | Intermedio | Blocchi yoga | Salire esplosivi, scendere camminando (no drop jump) |
| Single-leg pogo | 3x8/lato | Avanzato | Nessuna | Come pogo bipodalico ma monopodalico. Richiede base solida |
| Depth drop + jump | 3x5 | Avanzato | Blocchi yoga | Scendere da blocco, assorbire, esplodere. Solo se tecnica pogo perfetta |
| Bounding (balzi alternati) | 3x6/lato | Avanzato | Nessuna (spazio 10m) | Balzi orizzontali alternando gamba. Massimo transfer alla corsa |

**Regola progressione**: 2 settimane su ogni livello prima di avanzare.
Inizia SEMPRE da pogo + skip. Non saltare passaggi.

**Volume massimo per sessione**: 40-60 contatti totali (es. 3x10 pogo + 3x6 squat jump = 48)

**Seleziona 2-3 esercizi per sessione**

---

##### BLOCCO 3 — Lower body forza

| Esercizio | Serie x Rip | Progressione | Attrezzatura | Note |
|-----------|------------|-------------|-------------|------|
| Goblet squat | 3x10-12 | Base | Kettlebell 12kg | Fondamentale. Profondita' controllata |
| Bulgarian split squat | 3x8-10/lato | Base -> KB | Blocco yoga (piede dietro) + opz. KB 12kg | Esercizio re per runner: monopodalico, stabilita', forza |
| Single-leg deadlift | 3x8-10/lato | BW -> KB | Opz. Kettlebell 12kg | Catena posteriore + equilibrio. Critico per prevenzione infortuni |
| Step-up esplosivo | 3x8/lato | Blocchi -> KB | Blocchi yoga + opz. KB | Salita esplosiva, discesa controllata |
| Calf raise (bipodalico) | 3x15-20 | Piano -> rialzo -> monopodalico | Nessuna (rialzo: bordo scalino) | 3" eccentrica obbligatoria. Stiffness tendine Achille |
| Calf raise monopodalico | 3x10-12/lato | Avanzato | Nessuna (rialzo) | Solo dopo 4 sett di bipodalico senza dolore |
| Tibialis raise (seduto) | 3x15-20 | Base | Nessuna | Piede a terra, alza punta. Previene shin splints |
| Nordic curl assistito | 3x5-8 | Avanzato | Nessuna (piedi bloccati) | Eccentrica lenta. Solo se hamstring pronti |

**Seleziona 2-3 esercizi per sessione (1 squat/lunge + 1 hinge/deadlift + 1 calf)**

---

##### BLOCCO 4 — Core intensive

Pool identico alle linee-guida attuali, riportato per completezza:

**Anti-estensione:**
| Esercizio | Serie x Rip | Progressione | Note |
|-----------|------------|-------------|------|
| Plank standard | 3-4x30-60" | Base | Retroversione bacino obbligatoria |
| Plank su AB wheel (statico) | 3-4x30-60" | Intermedio | Mani su wheel, zero roll-out |
| AB wheel short roll-out | 3x6-8 | Intermedio | ROM 20-30cm, da ginocchia |
| AB wheel medium roll-out | 3-4x8-10 | Avanzato | ROM 50-60cm |
| AB wheel full roll-out | 3-4x10-12 | Expert | Solo se tecnica perfetta |
| Dead bug | 3x10/lato | Base | Opposite limbs, lombare a terra |
| Hollow hold | 3x30-60" | Intermedio -> Avanzato | Tuck -> half -> full |

**Flessione dinamica:**
| Esercizio | Serie x Rip | Note |
|-----------|------------|------|
| Leg raises (terra) | 3x12-15 | Ginocchia piegate -> gambe tese |
| V-sit progression | 3x15-30" | Tuck -> half -> full |
| Hollow rocks | 3x15-30 | Controllati, no slancio |

**Anti-rotazione:**
| Esercizio | Serie x Rip | Attrezzatura | Note |
|-----------|------------|-------------|------|
| Pallof press | 3x10-15/lato | KB o manubrio | Pressa e tiene, resiste rotazione |
| Side plank | 3x30-45"/lato | Nessuna | Standard -> con rotation -> leg raise |
| Copenhagen plank | 3x15-30"/lato | Nessuna | Se tollerato, ottimo per adduttori |
| Bird-dog | 3x10/lato | Nessuna | Controllo anti-rotazione + anti-estensione |

**Rotazione controllata:**
| Esercizio | Serie x Rip | Note |
|-----------|------------|------|
| Russian twist | 3x20-30 totali | Con manubrio 5kg, lento e controllato |
| Bicycle crunch | 3x20 totali | Slow, gomito a ginocchio opposto |

**Seleziona 3-4 esercizi per sessione (1 anti-est + 1 flessione + 1 anti-rot + 1 opzionale)**

---

##### BLOCCO 5 — Upper push/pull

**Push:**
| Esercizio | Serie x Rip | Progressione | Note |
|-----------|------------|-------------|------|
| Push-up | 3x8-15 | Inclinati (blocchi) -> standard -> diamond -> archer | Base |
| Pike push-up | 3x6-10 | Standard -> su blocchi (ROM aumentato) | Spalle |
| Scapular push-up | 3x10-15 | — | Attivazione scapolare, postura |

**Pull (limitato da attrezzatura, no sbarra):**
| Esercizio | Serie x Rip | Attrezzatura | Note |
|-----------|------------|-------------|------|
| Bent-over row | 3x12-15 | Manubri 5kg o KB 12kg | Principale esercizio pull |
| Renegade row | 2x10/lato | Manubri 5kg | Se tollerato, aggiunge core |
| Face pull con KB | 3x15-20 | Kettlebell 12kg | Compensazione posturale |
| Reverse fly | 3x12-15 | Manubri 5kg | Deltoide posteriore, postura |

**Esegui in superserie**: 1 push + 1 pull senza recupero tra loro,
90" recupero tra le superserie. Risparmia 4-5 minuti.

**Seleziona 1 push + 1 pull per sessione**

---

##### BLOCCO 6 — Mobilita' funzionale running

| Esercizio | Rip/Durata | Target | Note |
|-----------|-----------|--------|------|
| Caviglia sotto carico (knee-over-toe) | 3x10/lato | Dorsi-flessione caviglia | Piede a terra, ginocchio avanti oltre punta. Progressione: aggiungere peso |
| 90/90 hip switch | 10 rip | Rotazione interna/esterna anca | Lento, cerca ROM attivo non passivo |
| Deep squat hold | 2x30-45" | Caviglie + anche + colonna | Talloni a terra, petto alto. Assistito se necessario |
| Pigeon stretch dinamico | 30" per lato | Piriforme + gluteo | Leggero rock avanti-indietro, non statico |
| Thoracic rotation da quadrupedia | 8/lato | Rotazione toracica | Mano dietro la testa, apri verso il soffitto |
| Couch stretch | 30" per lato | Flessore anca + quadricipite | Con blocco yoga sotto ginocchio posteriore |

**Seleziona 3-4 esercizi per sessione (5' totali)**

---

#### Varianti A e B (Mar vs Gio)

Stessa struttura, esercizi diversi per varieta' e stimolo complementare.

```
VARIANTE A (es. Martedi')

Warm-up: Cerchi caviglie + World's greatest stretch + Cat-cow + Glute bridge
Pliometria: Pogo jump 3x10 + Squat jump 3x6
Lower: Bulgarian split squat 3x8/lato (BW o KB) + Calf raise 3x15
Core: AB wheel [livello corrente] 3x8 + Leg raises 3x12 + Pallof press 3x10/lato
Upper: Push-up [livello] + Bent-over row (superserie 3x)
Mobilita': Knee-over-toe 3x10 + 90/90 switch 10 + Deep squat hold 30"

VARIANTE B (es. Giovedi')

Warm-up: Leg swings + Inchworm + Cat-cow + Glute bridge
Pliometria: Skip basso 3x15" + Split squat jump 3x5/lato
Lower: Single-leg deadlift 3x8/lato (KB) + Tibialis raise 3x15
Core: Dead bug 3x10/lato + Hollow hold 3x30-45" + Side plank 3x30"/lato
Upper: Pike push-up + Face pull KB (superserie 3x)
Mobilita': Couch stretch 30"/lato + Thoracic rotation 8/lato + Pigeon 30"/lato
```

---

#### Periodizzazione forza (allineata a mesociclo running 3:1)

Stessa logica delle linee-guida attuali, estesa ai nuovi blocchi:

| Settimana | Tipo | Volume core | Volume plio | Volume lower | Intensita' (RIR) | Note |
|-----------|------|------------|------------|-------------|------------------|------|
| 1 | Base | 12-14 serie | 30-40 contatti | 6 serie | 3-4 | Tecnica, ROM controllato |
| 2 | Build | 14-16 serie | 40-50 contatti | 6 serie | 2-3 | Aumenta ROM/leve/carico |
| 3 | Peak | 12-14 serie | 40-50 contatti | 6 serie | 2-3 | Mantieni, non aumentare (running al picco) |
| 4 | Scarico | 8-10 serie | 20-30 contatti | 4 serie | 4-5 | -40% volume, zero stress |

**Upper e mobilita'**: volume costante (3 serie push + 3 pull + mobilita' 5').
Non serve periodizzare — il focus e' mantenimento, non progressione.

**Progressione esercizi**: ogni 2 settimane, non settimanale.
In deficit + running, il recupero e' limitato. Avanzare troppo veloce = infortuni.

---

#### Progressioni chiave (criteri per avanzare)

| Esercizio | Da | A | Criterio avanzamento |
|-----------|-----|---|---------------------|
| AB wheel | Plank statico 4x45" | Short roll-out | 4x45" senza perdita controllo lombare |
| AB wheel | Short roll-out 3x8 | Medium roll-out | 3x8 con ROM 30cm, RIR 3, zero compenso |
| Pogo jump | Bipodalico 3x10 | Single-leg 3x8 | 3x10 senza dolore Achille/plantare x4 sett |
| Squat jump | BW 3x6 | Split squat jump 3x5 | Atterraggio stabile, zero valgismo |
| Calf raise | Bipodalico 3x20 | Monopodalico 3x12 | 3x20 con 3" eccentrica x4 sett |
| Push-up | Standard 3x12 | Diamond 3x8 | 3x12 con scapole stabili, RIR 2 |
| Bulgarian | BW 3x10 | KB 12kg 3x8 | 3x10 BW senza instabilita', ginocchio tracking |
| Single-leg DL | BW 3x10 | KB 12kg 3x8 | 3x10 BW senza perdita equilibrio |

**Red flag pliometria**:
- Dolore tendine Achille durante o dopo -> STOP, torna a calf raise
- Dolore ginocchio all'atterraggio -> STOP, verifica tecnica con video
- Shin splints -> aggiungi tibialis raise, riduci volume pogo

---

#### Drills tecnica di corsa — Pre-lungo (sabato)

**Timing**: Dopo 10' riscaldamento Z1, prima del lungo vero.
**Durata**: 10-12 minuti. **Volume aggiuntivo**: ~1.5 km (non impattante).
**Obiettivo**: Attivare pattern motori corretti da usare nei km successivi.
I dati biomeccanici di Andrea confermano che la tecnica migliora sotto sforzo
(GCT 248->228ms, osc. vert. 9.4->8.7cm). Le drills rendono automatici
questi pattern anche a bassa intensita'.

**Sequenza fissa:**

```
1. SKIP BASSO (2x30m)
   Cue: "Tocco e via" — contatto rapido, piede sotto baricentro
   NON alzare le ginocchia. Pensa frequenza, non altezza.
   Recupero: cammina al punto di partenza

2. SKIP ALTO (2x30m)
   Cue: "Ginocchio al petto, postura alta"
   Ritmo controllato, braccia coordinate (gomito a 90 gradi)
   Recupero: cammina al punto di partenza

3. CALCIATA DIETRO (2x30m)
   Cue: "Tallone al gluteo, frequenza alta"
   Attiva catena posteriore + flessori anca
   Recupero: cammina al punto di partenza

4. CORSA BALZATA (2x30m)
   Cue: "Spingi orizzontale, atterra sotto il baricentro"
   Tempo di volo lungo, atterraggio controllato
   L'esercizio con massimo transfer alla meccanica di corsa
   Recupero: cammina al punto di partenza

5. ALLUNGHI TECNICI (3x80-100m)
   Progressione: Z2 -> Z3 -> Z5 (non sprint)
   Cue durante l'allungo:
   - "Suolo bollente" (GCT minimo)
   - "Cadi in avanti dalle caviglie" (non dai fianchi)
   - "Cadenza alta" (>180 spm)
   - "Mani rilassate, gomiti a 90 gradi"
   Recupero: cammina 1' tra ciascuno
```

**Integrazione nel sabato:**
```
Sabato tipico con drills:
  10' riscaldamento Z1 (corsetta leggera)
  12' drills tecnica (skip + calciata + balzata + allunghi)
  [Lungo effettivo: X km Z2]
  5' defaticamento Z1

I km delle drills NON si conteggiano nel volume del lungo.
Il lungo inizia "pulito" dopo le drills.
```

**Periodizzazione drills:**
- Settimane 1-4: Solo skip basso + calciata + 2 allunghi (base)
- Settimane 5-8: Aggiungere skip alto + corsa balzata + 3 allunghi
- Da settimana 9: Sequenza completa

Non servono progressioni di carico sulle drills. Sono educative.
La "progressione" e' la qualita' di esecuzione, non il volume.

---

#### Comando `/strength`

```
/strength <sett_tipo>

Input: base | build | peak | scarico
Output: Scheda completa variante A + variante B con:
  - Esercizi selezionati dal pool (in base a livello corrente)
  - Serie, ripetizioni, RIR
  - Note di esecuzione
  - Recuperi
  - Ordine blocchi
  - Tempo stimato
```

**Logica interna:**
```
1. Legge livello corrente da data/strength-progress.json
   (es. AB wheel: "medium roll-out", push-up: "standard",
    pogo: "bipodalico", calf: "bipodalico")
2. Seleziona esercizi appropriati al livello per ogni blocco
3. Applica volume/intensita' della settimana tipo:
   - Base: RIR 3-4, volume 12-14 core, 30-40 contatti plio
   - Build: RIR 2-3, volume 14-16 core, 40-50 contatti plio
   - Peak: RIR 2-3, volume 12-14 core, 40-50 contatti plio
   - Scarico: RIR 4-5, volume 8-10 core, 20-30 contatti plio
4. Genera variante A (Mar) e variante B (Gio)
   con esercizi complementari dallo stesso pool
5. Output: 2 schede pronte all'uso
```

**Esempio output:**
```
SCHEDA FORZA — Settimana Build | Variante A (Martedi')
Durata stimata: 45'

WARM-UP (5')
  Cerchi caviglie: 10/direzione
  World's greatest stretch: 5/lato
  Cat-cow: 10
  Glute bridge hold: 2x15"

PLIOMETRIA (8') — 48 contatti totali
  A1. Pogo jump: 3x10 | Rec 60"
      Cue: rimbalzo elastico, minimo piegamento ginocchio
  A2. Squat jump: 3x6 | Rec 90"
      Cue: accosciata parallelo, esplosione verticale, atterraggio morbido

LOWER (10')
  B1. Bulgarian split squat (BW): 3x10/lato | RIR 2-3 | Rec 90"
      Cue: ginocchio tracking su 2o dito, busto eretto
  B2. Calf raise bipodalico (rialzo): 3x15 | 3" eccentrica | Rec 60"
      Cue: salita esplosiva, discesa lenta 3 secondi

CORE (12') — 14 serie totali
  C1. AB wheel medium roll-out: 4x8 | RIR 2-3 | Rec 60"
      Cue: retroversione bacino, glutei contratti, ritorno controllato
  C2. Leg raises (gambe tese): 3x12 | Rec 45"
      Cue: lombare incollata a terra, discesa lenta
  C3. Pallof press (manubrio 5kg): 3x12/lato | Rec 45"
      Cue: braccia tese, resisti rotazione, core rigido
  C4. Bird-dog: 4x10/lato | Rec 30"
      Cue: bacino fermo, estensione completa

UPPER — superserie (8')
  D1. Push-up standard: 3x12 | RIR 2-3
  D2. Bent-over row (KB 12kg): 3x12 | RIR 2-3
  -> Esegui D1 + D2 senza pausa, 90" recupero tra superserie

MOBILITA' (5')
  Knee-over-toe: 3x10/lato
  90/90 hip switch: 10
  Deep squat hold: 30"
```

---

#### File: `data/strength-progress.json`

```json
{
  "current_levels": {
    "ab_wheel": "medium_rollout",
    "push_up": "standard",
    "pogo": "bilateral",
    "squat_jump": true,
    "split_squat_jump": false,
    "bulgarian": "bodyweight",
    "single_leg_dl": "bodyweight",
    "calf_raise": "bilateral",
    "calf_raise_single": false
  },
  "history": [
    {
      "date": "2026-02-12",
      "week_type": "base",
      "variant": "A",
      "completed": true,
      "notes": "Prima sessione dopo 3 mesi. Tutto base. AB wheel solo plank.",
      "pain_flags": []
    }
  ],
  "progression_log": [
    {
      "date": "2026-02-27",
      "exercise": "ab_wheel",
      "from": "plank_static",
      "to": "short_rollout",
      "reason": "4x45\" plank stabile per 2 settimane"
    }
  ]
}
```

---

### ANALISI GARMIN — `/analyze`

```
/analyze <file.csv> [opzioni]

Opzioni:
  --type auto|test|lungo|ripetute|progressivo|easy|gara
         (default: auto, rileva dal profilo passo/distanza)
  --compare <file2.csv>
         (confronto tra due attivita')
  --zones
         (forza mapping su zone attuali anche se non test)
  --export md|json
         (formato output, default md)
```

#### Struttura CSV Garmin (input)

25 colonne, dati per-km (lap). Formato rilevato da export Garmin Connect italiano.

```
Colonne:
 1. (vuota)
 2. Intervallo
 3. Tipo di fase
 4. Lap
 5. Tempo               (mm:ss.d o h:mm:ss)
 6. Tempo cumulato
 7. Distanza             (km, 2 decimali)
 8. Passo medio          (m:ss)
 9. FC Media             (bpm)
10. FC max               (bpm)
11. Ascesa totale        (m)
12. Discesa totale       (m)
13. Cadenza di corsa media (spm)
14. Tempo medio contatto suolo (ms)
15. Media bilanciamento TCS (es. "50.6% S / 49.4% D")
16. Lunghezza media passo (m)
17. Oscillazione verticale media (cm)
18. Rapporto verticale medio (%)
19. Calorie              (kcal)
20. Temperatura med      (C)
21. Passo migliore       (m:ss)
22. Cadenza di corsa max (spm)
23. Tempo in movimento
24. Passo medio in movimento
25. Potenza Corsa Media  (W, "--" nel sommario)
```

Struttura righe:
- Riga 1: header
- Riga 2: sommario intervallo (es. lap "1 - 5")
- Righe successive: dettaglio per km (lap 1, 2, 3...)
- Righe vuote tra ogni lap (separatore da gestire nel parsing)
- Penultima riga: eventuale "Defaticamento"
- Ultima riga: "Riepilogo"

Note parsing:
- Separatore: virgola, campi tra doppi apici
- Line ending: \r\n (Windows)
- Potenza: "--" nel sommario/riepilogo, valore numerico (W) nei lap
- Bilanciamento TCS: stringa composta (es. "50.6% S / 49.4% D")
  -> parsing: split su "/" e estrai numeri
- Passo: formato m:ss -> convertire in secondi per calcoli

#### Report output: 6 sezioni

**SEZIONE 1 - Overview**

```
Attivita': [tipo rilevato] | Data: [da filename o metadata]
Distanza: X.XX km | Tempo: mm:ss | Passo medio: m:ss/km
FC media: XXX bpm | FC max: XXX bpm
Calorie: XXX | Temperatura: XX.X C
Potenza media: XXX W (media pesata da lap, escluso sommario)
Dislivello: +Xm / -Xm
```

**SEZIONE 2 - Analisi passo (split e trend)**

```
Km   Passo   Delta   Zona    Trend
1    3:38    -       Z7
2    3:38    +0"     Z7      = stabile
3    3:42    +4"     Z7      ^ lieve calo
...

Metriche calcolate:
- Variabilita' passo: CV% (coefficiente di variazione)
  [eccellente <2% | buono 2-4% | da migliorare >4%]
- Profilo: negative split / positive split / even split
  (confronto media prima meta' vs seconda meta')
- Km piu' veloce e piu' lento
- Delta primo-ultimo km
```

**SEZIONE 3 - Analisi FC (progressione cardiaca)**

```
Km   FC med  FC max  Drift vs km1
1    160     170     baseline
2    174     181     +8.7%
...

Metriche calcolate:
- Cardiac drift totale: (FC ultimo km - FC primo km) / FC primo km x 100
  [ottimo <5% | normale 5-10% | elevato >10% | atteso all-out >12%]
- Accoppiamento passo/FC: confronto variazione % passo vs variazione % FC
  -> Se passo stabile e FC sale molto = drift cardiovascolare
  -> Se passo cala e FC cala = gestione conservativa
  -> Se passo sale e FC stabile = ottima efficienza
- Interpretazione contestuale per tipo attivita':
  - Test: drift alto atteso e normale
  - Lungo Z2: drift >10% = problematico (base aerobica debole o disidratazione)
  - Easy: drift >8% = troppo veloce per Z2
```

**SEZIONE 4 - Dinamiche di corsa (efficienza biomeccanica)**

```
Km   GCT(ms)  Cadenza  Lung.passo(m)  Osc.vert(cm)  Rapp.vert(%)  Potenza(W)
1    230      184      1.48           9.4           6.3           476
...

Metriche calcolate:
- Trend GCT: primo vs ultimo km (% variazione)
  [migliora sotto fatica = positivo | peggiora >5% = segnale fatica]
- Trend cadenza: adattamento naturale (sale = positivo)
- Trend oscillazione verticale: cala = meno spreco energia verticale
- Rapporto verticale: <6% eccellente | 6-8% buono | >8% da migliorare
- Bilanciamento TCS: <1% asimmetria = ottimo | >2% = investigare
- Potenza: trend e correlazione con passo
  -> Potenza cala con passo stabile = efficienza peggiora
  -> Potenza stabile con passo che cala = fatica neuromuscolare

Confronto con benchmark personali (se storico disponibile):
- GCT tipico easy: ~245ms | GCT test: ~228ms
- Cadenza tipica easy: ~179 | Cadenza test: ~186
```

**SEZIONE 5 - Mapping zone**

```
Distribuzione tempo per zona (basata su zones.json attuali):

Zona   Range         Km in zona   Tempo    %
Z8     3:25-3:29     0            0:00     0%
Z7     3:29-3:42     3 km         10:54    59%
Z6     3:42-3:50     2 km         7:27     40%
...

Interpretazione per tipo:
- Test 5km: atteso 80-100% Z7+ -> [valutazione]
- Lungo: atteso 80-90% Z2 -> [valutazione compliance]
- Easy: atteso 100% Z2-Z3 -> [valutazione, segnala se troppo veloce]
- Ripetute: fasi lavoro in Z5-Z8, recuperi in Z1-Z2
- Progressivo: distribuzione crescente Z2 -> Z3 -> Z4 -> Z5
```

**SEZIONE 6 - Insight e raccomandazioni**

```
Segnali positivi:
[OK] Descrizione

Segnali di attenzione:
[!] Descrizione

Raccomandazioni:
-> Azione suggerita
```

Logica generazione insight (per tipo attivita'):

TEST 5km:
- [OK] se CV passo <2%
- [OK] se biomeccanica migliora sotto fatica (GCT cala, osc. cala)
- [!] se km centrali rallentano >5" vs km 1 senza ripresa finale
- [!] se FC max raggiunta prima dell'ultimo km (partenza troppo forte)
- Ricalcolo zone automatico se --type test

LUNGO:
- [OK] se >80% tempo in Z2
- [OK] se cardiac drift <8%
- [!] se tempo in Z3+ >30% (troppo veloce)
- [!] se GCT peggiora >8% negli ultimi 3km vs primi 3km
- [!] se cardiac drift >12% (possibile disidratazione o base debole)
- -> "Prossimo lungo: mantieni km 1-3 a X:XX per restare in Z2"

EASY RUN:
- [OK] se 100% Z2-Z3
- [!] se qualsiasi km in Z4+ (troppo veloce per easy)
- [!] se FC media >70% FC max stimata
- -> "Rallenta di X"/km per restare in Z2"

RIPETUTE:
- Analisi separata fasi lavoro vs recupero
- [OK] se fasi lavoro nella zona target
- [!] se drift >10% tra prima e ultima ripetuta
- [!] se recupero non scende sotto Z3

PROGRESSIVO:
- [OK] se progressione costante (ogni fase piu' veloce)
- [!] se salto >15"/km tra fasi consecutive
- Verifica: fasi L in Z2-Z3, M in Z3-Z4, TR in Z5-Z6

#### Flag --compare (confronto tra attivita')

```
/analyze test_feb.csv --compare test_gen.csv

Output aggiuntivo:

Confronto [tipo]: [data1] vs [data2]
                    [data1]     [data2]     Delta       %
Tempo:              19:03       18:26       -37"        -3.2%
Passo medio:        3:49        3:41        -8"/km      -3.5%
FC media:           176         174         -2 bpm      -1.1%
FC max:             186         184         -2 bpm      -1.1%
GCT medio:          235         228         -7 ms       -3.0%
Cadenza media:      183         186         +3 spm      +1.6%
Osc. verticale:     9.8         9.1         -0.7 cm     -7.1%
Rapp. verticale:    6.5         6.0         -0.5%       -7.7%
Potenza media:      458         464         +6 W        +1.3%
Cardiac drift:      15.2%       13.1%       -2.1%       migliore

Interpretazione:
-> "Miglioramento significativo: piu' veloce (-3.2%) con FC piu'
    bassa (-1.1%) e biomeccanica migliore. Efficienza in crescita."
```

#### Auto-detection tipo attivita' (--type auto)

Logica di rilevamento:
```
1. Distanza:
   - 4.5-5.5 km -> probabile test 5km
   - 12-22 km -> probabile lungo
   - 5-10 km -> ulteriore analisi

2. Variabilita' passo (CV):
   - CV <3% -> test o lungo (passo costante)
   - CV 3-8% -> progressivo
   - CV >8% -> ripetute o fartlek

3. Profilo passo:
   - Costante alto (Z6+) -> test
   - Costante basso (Z2-Z3) -> lungo o easy
   - Crescente -> progressivo
   - Alternato rapido/lento -> ripetute

4. Durata:
   - <25 min -> test o easy breve
   - 25-50 min -> easy o progressivo
   - 50-90 min -> lungo
   - >90 min -> lungo esteso
```

---

### COMPOSIZIONE E TRACKING

| Comando | Cosa fa | Input | Output |
|---------|---------|-------|--------|
| `/weigh <peso> <bf> <ffm>` | Registra pesata | Peso, BF%, FFM | Trend + alert |
| `/checkpoint` | Genera checkpoint template | Usa ultimi dati | Report checkpoint completo |
| `/status` | Panoramica stato attuale | - | Fase, gara, ultimo check, trend |
| `/alerts` | Red flags attive | - | Lista alert con priorita' |
| `/log` | Mostra ultime 10 entry changelog | - | Storico modifiche recenti |
| `/log <file>` | Storico modifiche di un file | Path file | Entry changelog filtrate |
| `/log diff <file>` | Diff ultima modifica | Path file | Delta dettagliato vs versione precedente |

#### Logica `/weigh`

```
1. Salva in composition.json (append con timestamp)
2. Calcola BMR = 370 + 21.6 x FFM
3. Confronta con precedente:
   - Delta peso, BF%, FFM
   - Ritmo perdita peso (%/sett)
4. Verifica alert:
   - FFM < 59.5 kg -> RED FLAG
   - FFM in calo per >4 pesate consecutive -> WARNING
   - Peso calo >0.6%/sett per >4 sett -> RED FLAG
   - BF% stallo >6 sett -> ATTENZIONE
5. Calcola impatto su piani:
   - Delta BMR -> Delta TDEE -> serve rigenerare piani? (soglia: >30 kcal)
6. Output: riepilogo + trend + alert + raccomandazione
```

Esempio output:
```
Pesata 11/02/2026
Peso: 68.65 kg | BF: 13.2% | FFM: 59.57 kg | BMR: 1657 kcal

Trend (vs 03/02/2026, 8 giorni):
  Peso:  -0.75 kg (-1.08%/sett) [!] Troppo rapido (target 0.2-0.4%)
  BF%:   -0.2%  [OK]
  FFM:   -0.51 kg [!] Sotto floor 60 kg

Alert attivi:
  [!] FFM 59.57 < floor 60.0 kg — a 0.07 kg da red flag 59.5
  [!] Ritmo perdita peso 1.08%/sett > soglia 0.6%

Impatto piani: Delta BMR -12 kcal (sotto soglia 30 -> no rigenerazione)

Azione: forza 2x/sett obbligatoria per invertire trend FFM
```

---

### PIANO RUNNING — Architettura a 3 livelli

La pianificazione running lavora **dall'alto verso il basso**: prima la stagione,
poi i blocchi (mesocicli), infine il dettaglio settimanale. La singola settimana
e' il livello di dettaglio piu' basso, non il punto di partenza.

#### Comandi

| Comando | Livello | Frequenza | Cosa fa |
|---------|---------|-----------|---------|
| `/plan-season` | Strategico | 1-2x/anno | Macro-struttura stagione intera da calendario gare |
| `/plan-season update` | Strategico | Dopo risultato gara o cambio obiettivo | Ricalcola da un punto in poi |
| `/plan-block <N>` | Tattico | Ogni 4 settimane | Dettaglia mesociclo 3:1 completo |
| `/plan-block adjust <N> <motivo>` | Tattico | Se imprevisto | Rimodula blocco in corso |
| `/week <N>` | Operativo | Consultazione pre-settimana | Esplode sessioni con ritmi e note |
| `/taper <gara>` | Specializzato | 2-3 sett pre-gara | Protocollo taper + nutrizione race week |
| `/race <gara>` | Specializzato | Pre-gara | Race strategy: pacing, piano A/B, nutrizione |

---

#### Livello 1 — `/plan-season` (strategico)

Prende il calendario gare e genera la macro-struttura stagionale.
Si fa 1-2 volte l'anno o dopo cambio significativo di calendario.

**Logica interna:**
```
1. Legge calendario gare da linee-guida
2. Per ogni gara, calcola:
   - Settimane disponibili
   - Tipo taper: full 3 sett (maratona), standard 10-12 gg (HM A-race),
     mini 1 sett (HM B-race), nessuno (test/allenamento)
   - Fase di periodizzazione (da tabella fasi in linee-guida)
3. Piazza vincoli fissi all'INDIETRO dalla gara:
   - Taper pre-gara
   - Settimana test/scarico pre-taper
   - Picco volume 2-3 sett prima dello scarico pre-taper
4. Riempie con mesocicli 3:1 (3 carico + 1 scarico con test 5km)
5. Costruisce curva volume:
   - Incremento max 5-10%/sett nelle settimane build
   - Scarico -30-40% ogni 4a settimana
   - Picchi coerenti con storico (max raggiunto: 50 km/sett)
   - Progressione maratona: da ~35 a 60-70 km/sett al picco
6. Integra fasi nutrizionali:
   - Pre-gara HM (feb-mar): deficit -8-10%
   - Transizione (apr-giu): mantenimento/surplus
   - Prep specifica (lug-nov): deficit -5-8% con alto volume
   - Race (dic): mantenimento
```

**Output esempio:**
```
STAGIONE 2026

Sett  Periodo     Meso  Tipo     Vol(km)  Gara/Note
1-3   6-26 gen    M1    Carico   30-35    -
4     27 gen      M1    Scarico  20       Test 5km
5-7   3-17 feb    M2    Carico   35-44    -
8     24 feb      M2    Scarico  25       Test pre Roma-Ostia
--    1 mar       -     GARA     -        Roma-Ostia HM (A)
9-11  3-17 mar    M3    Carico   35-42    Recovery + rebuild
12    24 mar      M3    Scarico  20       Mini-taper
--    29 mar      -     GARA     -        Latina HM (PB)
13-16 apr         M4    Carico   30-38    Transizione, base maratona
...
45-47 nov         M12   Carico   55-65    Picco volume maratona
48    24 nov      M12   Scarico  40       Inizio taper
49-50 1-8 dic     -     Taper    30->20   Taper maratona
--    6 dic       -     GARA     -        Maratona Latina

Curva volume: [grafico ASCII o dati per chart]
```

---

#### Livello 2 — `/plan-block <N>` (tattico)

Prende un mesociclo e lo dettaglia in 4 settimane. Conosce il contesto
dalla season: fase, gara prossima, volume target, focus del periodo.

**Logica interna:**
```
1. Identifica mesociclo N nella season plan
2. Determina contesto:
   - Fase periodizzazione (Pre-gara/Transizione/Prep specifica/Race)
   - Distanza dalla prossima gara
   - Volume target dal season plan
   - Focus: base aerobica / soglia / VO2max / ritmo gara / recupero
3. Per ogni settimana (Base/Build/Peak/Scarico):
   a. Calcola volume (incremento progressivo, scarico -30-40%)
   b. Seleziona workout dal bacino storico per ogni giorno:
      - Lun: D.A. (km in base a volume settimana)
      - Mer: Ripetute (complessita' crescente Base->Peak)
      - Ven: Progressivo (struttura crescente Base->Peak)
      - Sab: Lungo (km crescente, con inserti in Peak)
   c. Assegna intensita':
      - Base: 85% Z2, ripetute corte
      - Build: 80% Z2, ripetute medie, progressivi strutturati
      - Peak: 75% Z2, ripetute lunghe/ritmo gara, lungo con inserti
      - Scarico: 90% Z2, volume ridotto, test 5km
4. Verifica:
   - Volume totale blocco coerente con season plan (+/-5%)
   - Incremento settimanale <=10%
   - Rapporto 80/20 intensita' (80% Z1-Z2, 20% Z3+)
5. Output: tabella 4 settimane con workout, volume, note
```

**Output esempio:**
```
BLOCCO 6 (sett 21-24) | Fase: Transizione | Focus: base aerobica + ricostruzione FFM
Volume blocco: 131 km (media 33 km/sett)
Prossima gara: Pedagnalonga 26 apr (allenamento)

Sett 21 (Base) — 30 km
  Lun: 6 km D.A. facile [Z2 + 4x200m allunghi Z7-Z8]
  Mar: FORZA
  Mer: 5x1km TR rec 2' [Z5-Z6 3:50-4:02 | rec Z1]  ~8 km totale
  Gio: FORZA
  Ven: 4L+2M [L=Z2 4:50 | M=Z3 4:30]  ~8 km
  Sab: 12 km L [Z2 4:45-5:00]
  Dom: Rest

Sett 22 (Build) — 34 km
  Lun: 8 km D.A. [Z2 + 5x200m allunghi Z7-Z8]
  Mar: FORZA
  Mer: 4x1600m rec 2' LG [Z5-Z6 | rec Z1-Z2]  ~10 km
  Gio: FORZA
  Ven: 3x(1kmL+1kmM+1kmTR) [L=Z2 | M=Z3 | TR=Z5]  ~11 km
  Sab: 14 km L [Z2 costante]
  Dom: Rest

Sett 23 (Peak) — 38 km
  Lun: 10 km D.A. [Z2 + 6x200m allunghi Z7-Z8]
  Mar: FORZA
  Mer: 3x2km rec 2' [Z5 3:50-4:00]  ~10 km
  Gio: FORZA
  Ven: 3kmL+3x(1kmL+1kmM+1kmTR) [progressivo strutturato]  ~12 km
  Sab: 15L+3M [Z2 + ultimi 3km Z3]  ~18 km
  Dom: Rest

Sett 24 (Scarico) — 25 km
  Lun: 6 km D.A. facile
  Mar: FORZA (volume ridotto -40%)
  Mer: 30' lenti [Z2 easy]  ~6 km
  Gio: FORZA (volume ridotto)
  Ven: 4L+2M [facile]  ~6 km
  Sab: TEST 5km [risc 15' + test + defat 10']  ~8 km
  Dom: Rest
```

---

#### Livello 3 — `/week <N>` (operativo)

Prende una settimana gia' pianificata nel blocco e la esplode con tutti
i dettagli operativi: ritmi esatti, timing, note pratiche, meteo se utile.

**Logica interna:**
```
1. Cerca settimana N nel plan-block corrispondente
   (se non esiste, suggerisce di generare il blocco prima)
2. Per ogni sessione:
   a. Legge zones.json per ritmi aggiornati
   b. Espande abbreviazioni in istruzioni complete:
      - "5x1km TR rec 2'" -> ritmi Z5-Z6, tempi attesi, sensazioni target
   c. Aggiunge note operative:
      - Riscaldamento: sempre 10' Z1-Z2 (non nei km)
      - Defaticamento: 10' Z1
      - Idratazione: in base a temperatura/durata
   d. Integra forza (se Mar/Gio):
      - Riferimento a scheda corrente (settimana del mesociclo)
3. Output: piano giorno-per-giorno pronto all'uso
```

**Output esempio:**
```
SETTIMANA 22 (Build) | Blocco 6 | Volume: 34 km

LUNEDI' — D.A. 8 km
  Riscaldamento: 10' corsetta Z1 (non conteggiata)
  Workout: 5x [1.3 km Z2 4:45-5:00 + 200m allungo Z7 3:29-3:42]
  = 8 km totali (6.5 km Z2 + 1 km allunghi + 0.5 km transizione)
  RPE target: 3-4 (deve sentirsi facile)
  Defaticamento: 5' camminata

MARTEDI' — FORZA (scheda Build, sett 2 mesociclo)
  Vedi scheda forza corrente
  Volume: 14-16 serie core | RIR 2-3
  Durata: 40-50'

MERCOLEDI' — RIPETUTE: 4x1600m rec 2' LG
  Riscaldamento: 10' Z1 + 3x100m allunghi progressivi
  Workout: 4x 1600m a Z5-Z6 (3:50-4:02/km -> target 6:08-6:27 per 1600m)
  Recupero: 2' corsa leggera Z1 (5:11+)
  Defaticamento: 10' Z1
  Volume totale: ~10 km (risc 1.5 + 6.4 lavoro + 1.2 rec + defat 1.5)
  RPE target: 7 sulle ripetute, 2 sui recuperi
  Sensazione: impegnativo ma completabile. Se km 3-4 RPE >8, rallenta 5"/km

GIOVEDI' — FORZA (come martedi')

VENERDI' — PROGRESSIVO: 3x(1kmL+1kmM+1kmTR)
  Riscaldamento: 10' Z1
  Blocco 1: 1km Z2 (4:50) + 1km Z3 (4:30) + 1km Z5 (3:55)
  Blocco 2: ripeti
  Blocco 3: ripeti (se RPE <8 sul TR, chiudi a 3:50)
  Defaticamento: 10' Z1
  Volume totale: ~11 km
  RPE target: crescente 3 -> 5 -> 7 per ogni blocco

SABATO — LUNGO: 14 km L
  Colazione: 2h prima (piano LUNGO)
  Riscaldamento: primi 2 km naturalmente lenti (non forzare Z2)
  Workout: 14 km Z2 costante (4:40-5:11)
  Target: passo uniforme, cardiac drift <10%
  Idratazione: 400-500 ml durante (>60')
  RPE target: 3-4 costante per tutta la durata
  Nota: se ultimi 3 km RPE >5, stai andando troppo forte

DOMENICA — Rest
  Pesata mattutina (se giorno programmato)
```

---

#### `/taper <gara>` (specializzato)

Genera protocollo taper completo con integrazione nutrizionale.

**Logica interna:**
```
1. Identifica gara, distanza, importanza (A/B/test/allenamento)
2. Seleziona protocollo taper:
   - Maratona (A-race): 3 settimane
     Sett -3: volume -20%, mantieni 1 qualita'
     Sett -2: volume -40%, qualita' ridotta (es. 3x4km ritmo mezza)
     Sett -1: volume -60%, solo shakeout + allunghi
   - HM A-race: 10-12 giorni
     Sett -2: volume -25%, mantieni 1 qualita' specifica
     Sett -1: volume -50%, shakeout + allunghi
   - HM B-race / test: 5-7 giorni
     Solo riduzione volume -30%, 1-2 sedute facili
   - Gara allenamento: nessun taper specifico
3. Integra nutrizione race week:
   - Giorno -3 a -1: CHO loading (8-10 g/kg per maratona, 6-8 per HM)
   - Giorno -1: pasto pre-gara (alto CHO, basso fibra/grasso)
   - Mattina gara: colazione 3-4h prima (2-3 g/kg CHO)
   - Durante gara: piano alimentazione in gara (gel/liquidi per maratona)
4. Genera piano giorno-per-giorno fino a race day
```

**Output esempio (Roma-Ostia HM A-race):**
```
TAPER ROMA-OSTIA (1 marzo) — 12 giorni

Lun 17 feb: 8 km D.A. facile (volume -25%)
Mar 18 feb: FORZA (volume ridotto -30%)
Mer 19 feb: 3x4km RITMO MEZZA rec 2' L [4:00/km]
            Sessione chiave: conferma ritmo target
Gio 20 feb: FORZA leggera (solo core + mobilita')
Ven 21 feb: 6 km progressivo leggero (4L+2M)
Sab 22 feb: 10 km L facile (Z2 basso, 5:00+)
Dom 23 feb: Rest

Lun 24 feb: 6 km D.A. molto facile + 4x100m allunghi
Mar 25 feb: Rest o 30' camminata
Mer 26 feb: 5 km facile + 3x200m a ritmo gara
Gio 27 feb: Rest completo
Ven 28 feb: 20' facile + 4x100m allunghi
             Ultimo shakeout, sensazioni di gambe
Sab 1 mar:  GARA - Roma-Ostia HM

NUTRIZIONE RACE WEEK:
- Lun-Mer: piano normale della fase
- Gio-Ven: +50g CHO/die (focus pasta pranzo)
- Sab mattina: colazione 3h pre-gara
  Pane + marmellata + caffe' (~500 kcal, 80-90g CHO)
  Idratazione: 500ml acqua nelle 2h pre-partenza
```

---

#### `/race <gara>` (specializzato)

Race strategy dettagliata. Questo comando resta semi-conversazionale:
genera una bozza strutturata ma richiede conferma/aggiustamento umano
per variabili contestuali (meteo, sensazioni, obiettivo aggiornato).

**Output esempio (Roma-Ostia):**
```
RACE STRATEGY — Roma-Ostia HM | 1 marzo 2026
Target: 1:24:00 (4:00/km)

PIANO A (condizioni ottimali, 8-15C, no vento forte):
  Km 1-5:   4:02-4:05 (conservativo, lascia passare adrenalina)
  Km 6-10:  4:00 (ritmo target)
  Km 11-15: 3:58-4:00 (se sensazioni ok, leggero push)
  Km 16-18: 3:58 (mantieni)
  Km 19-21: 3:55-3:58 (chiusura progressiva se c'e')
  Split target 10km: 40:10-40:30
  Split target 15km: 1:00:00-1:00:30

PIANO B (caldo >18C o vento forte o sensazioni pesanti):
  Target rivisto: 1:26:00 (4:05/km)
  Km 1-10:  4:08 (prudente)
  Km 11-21: valuta se accelerare o mantenere
  Meglio finire forte a 1:26 che scoppiare a 1:28+

IDRATAZIONE:
  Ogni 5km: 100-150ml acqua o sport drink
  Non saltare il ristoro del km 5 (errore comune)

CHECK MENTALI:
  Km 5: "Come mi sento? Piano A o B?"
  Km 10: "Meta' fatta. Posso mantenere?"
  Km 15: "Ultimi 6km. E' una 6km veloce, ce la fai."
  Km 18: "3km. Qualsiasi dolore e' temporaneo."
```

---

### BOOTSTRAP — `/bootstrap`

Comando one-shot per popolare i file iniziali del progetto a partire dai dati
esistenti. Si esegue una sola volta all'inizio. Dopo, i file si aggiornano
con i comandi specifici (`/weigh`, `/test`, ecc.).

```
/bootstrap

Esegue in sequenza:
1. composition.json     <- dati storici pesate
2. zones.json           <- storico test 5km + zone correnti
3. running-log.json     <- piano running sett 1-20 da Excel
4. strength-progress.json <- inizializzazione livello base
5. changelog.json       <- vuoto, prima entry = bootstrap
6. piano-base.md        <- conversione formato PRD da piano_base_ottimizzato.md
7. piani nutrizionali   <- aggiunta META + AUDIT comment ai piani esistenti
```

#### 1. composition.json — Storico pesate

**Fonti**: screenshot app bilancia impedenza (7 misurazioni verificate)

```json
{
  "measurements": [
    {
      "date": "2025-09-29",
      "weight": 70.95, "bmi": 25.1, "bf_pct": 13.8, "ffm": 61.13,
      "subcut_fat_pct": 11.6, "visceral_fat": 7, "water_pct": 62.2,
      "skeletal_muscle_pct": 55.7, "muscle_mass": 58.10,
      "muscle_storage": 5, "bone_mass": 3.06, "protein_pct": 19.6,
      "bmr": 1690, "metabolic_age": 36,
      "source": "impedance_scale",
      "note": "Stato iniziale programma"
    },
    {
      "date": "2025-11-11",
      "weight": 69.90, "bmi": 24.8, "bf_pct": 13.5, "ffm": 60.43,
      "subcut_fat_pct": 11.4, "visceral_fat": 7, "water_pct": 62.4,
      "skeletal_muscle_pct": 55.9, "muscle_mass": 57.40,
      "muscle_storage": 5, "bone_mass": 3.02, "protein_pct": 19.7,
      "bmr": 1675, "metabolic_age": 35,
      "source": "impedance_scale",
      "note": "W5 — primo mese programma"
    },
    {
      "date": "2025-11-27",
      "weight": 68.90, "bmi": 24.4, "bf_pct": 13.3, "ffm": 59.77,
      "subcut_fat_pct": 11.2, "visceral_fat": 7, "water_pct": 62.6,
      "skeletal_muscle_pct": 56.0, "muscle_mass": 56.80,
      "muscle_storage": 5, "bone_mass": 2.99, "protein_pct": 19.8,
      "bmr": 1661, "metabolic_age": 35,
      "source": "impedance_scale",
      "note": "W7 — FFM gia' sotto 60kg"
    },
    {
      "date": "2025-12-04",
      "weight": 68.60, "bmi": 24.3, "bf_pct": 13.2, "ffm": 59.53,
      "subcut_fat_pct": 11.2, "visceral_fat": 7, "water_pct": 62.7,
      "skeletal_muscle_pct": 56.1, "muscle_mass": 56.60,
      "muscle_storage": 5, "bone_mass": 2.98, "protein_pct": 19.8,
      "bmr": 1655, "metabolic_age": 36,
      "source": "impedance_scale",
      "note": "W8 scarico M2 — FFM vicina a red flag"
    },
    {
      "date": "2026-01-22",
      "weight": 68.40, "bmi": 24.2, "bf_pct": 13.2, "ffm": 59.40,
      "subcut_fat_pct": 11.1, "visceral_fat": 7, "water_pct": 62.7,
      "skeletal_muscle_pct": 56.1, "muscle_mass": 56.40,
      "muscle_storage": 5, "bone_mass": 2.97, "protein_pct": 19.8,
      "bmr": 1652, "metabolic_age": 36,
      "source": "impedance_scale",
      "note": "W15 — minimo peso, FFM sotto red flag 59.5"
    },
    {
      "date": "2026-02-03",
      "weight": 69.40, "bmi": 24.6, "bf_pct": 13.4, "ffm": 60.08,
      "subcut_fat_pct": 11.3, "visceral_fat": 7, "water_pct": 62.5,
      "skeletal_muscle_pct": 55.9, "muscle_mass": 57.10,
      "muscle_storage": 5, "bone_mass": 3.00, "protein_pct": 19.7,
      "bmr": 1667, "metabolic_age": 36,
      "source": "impedance_scale",
      "note": "W17 — rimbalzo +1kg (probabile idratazione/glicogeno post-gara 29K)"
    },
    {
      "date": "2026-02-11",
      "weight": 68.65, "bmi": 24.3, "bf_pct": 13.2, "ffm": 59.57,
      "subcut_fat_pct": 11.2, "visceral_fat": 7, "water_pct": 62.6,
      "skeletal_muscle_pct": 56.0, "muscle_mass": 56.70,
      "muscle_storage": 5, "bone_mass": 2.99, "protein_pct": 19.8,
      "bmr": 1656, "metabolic_age": 36,
      "source": "impedance_scale",
      "note": "W20 scarico — FFM 59.57, appena sopra red flag 59.5"
    }
  ]
}
```

**Trend chiave (19.3 settimane):**
- Peso: 70.95 -> 68.65 = -2.30 kg (-0.12 kg/sett) — ritmo OK
- BF%: 13.8 -> 13.2 = -0.6 pp — calo modesto
- FFM: 61.13 -> 59.57 = -1.56 kg (-0.08 kg/sett) — CRITICO, 68% del peso perso e' FFM
- Grasso perso: ~0.74 kg su 2.30 totali = solo 32% — ratio pessimo senza forza

**File Excel di riferimento**: `composizione_corporea.xlsx` (export completo con delta e note)

#### 2. zones.json — Storico test e zone

**Fonti**: linee-guida + conversazioni

```json
{
  "current": {
    "test_date": "2026-02-09",
    "test_time": "18:26",
    "test_pace": "3:41",
    "zones": {
      "Z1": {"from": "5:11", "to": "inf"},
      "Z2": {"from": "4:40", "to": "5:11"},
      "Z3": {"from": "4:16", "to": "4:40"},
      "Z4": {"from": "4:02", "to": "4:16"},
      "Z5": {"from": "3:50", "to": "4:02"},
      "Z6": {"from": "3:42", "to": "3:50"},
      "Z7": {"from": "3:29", "to": "3:42"},
      "Z8": {"from": "3:25", "to": "3:29"}
    }
  },
  "history": [
    {
      "date": "2025-11-21",
      "time": "19:40",
      "pace": "3:56",
      "hr_avg": 170,
      "note": "W6 - primo test strutturato del programma"
    },
    {
      "date": "2026-01-02",
      "time": "19:46",
      "pace": "3:57",
      "hr_avg": 144,
      "note": "W12 - FC 144 inattendibile (senza fascia cardio, solo polso ottico). Tempo valido."
    },
    {
      "date": "2026-02-09",
      "time": "18:27",
      "pace": "3:41",
      "hr_avg": 174,
      "note": "W20 scarico - miglioramento 73s da W6, post blocco pre-gara"
    }
  ]
}
```

**Stato**: Zone Z1-Z8 confermate e caricate su Garmin (screenshot 11/02/2026).
Z9-Z10 presenti su Garmin (3:25-3:18 e 3:18-0:01) ma non usate nei workout —
richiedono test specifici (200m/400m) per validazione.

Date test confermate da CSV Garmin storico:
- W6: 21/11/2025 confermato (19:40, FC 170)
- W12: 02/01/2026 confermato (19:46, FC 144 — anomala, possibile test non massimale)
- W20: 09/02/2026 confermato (18:27, FC 174)

#### 3. running-log.json — Piano running sett 1-20

**Fonte**: `pianorunning.xlsx` foglio "Piano-completo"

Il tool converte l'Excel in JSON strutturato. Ogni settimana diventa un oggetto:

```json
{
  "weeks": [
    {
      "week": 1,
      "start_date": "2025-10-13",
      "phase": "Pre-gara HM",
      "mesocycle": 1,
      "mesocycle_week": 1,
      "mesocycle_type": "Base",
      "volume_planned": 27,
      "volume_actual": 27,
      "sessions": [
        {
          "date": "2025-10-13",
          "day": "Mon",
          "type": "DA",
          "workout": "7km D.A.",
          "structure": "7x[0.85L+0.15All]",
          "distance": 7.0,
          "garmin_file": null
        },
        {
          "date": "2025-10-15",
          "day": "Wed",
          "type": "Ripetute",
          "workout": "10x400m",
          "structure": "10x400m",
          "distance": 4.0,
          "garmin_file": null
        },
        {
          "date": "2025-10-17",
          "day": "Fri",
          "type": "Progressivo",
          "workout": "4L+2M",
          "structure": "4L+2M",
          "distance": 6.0,
          "garmin_file": null
        },
        {
          "date": "2025-10-18",
          "day": "Sat",
          "type": "Lungo",
          "workout": "10L",
          "structure": "10L",
          "distance": 10.0,
          "garmin_file": null
        }
      ]
    }
  ]
}
```

**Logica conversione Excel -> JSON:**
```
1. Leggi pianorunning.xlsx, foglio "Piano-completo"
2. Per ogni riga con dati:
   - Estrai: data, settimana, giorno, tipo workout, distanza, struttura, volume
3. Raggruppa per settimana
4. Assegna metadati:
   - mesocycle: calcola da pattern 3:1
     W1-4 = M1, W5-8 = M2, W9-12 = M3, W13-16 = M4, W17-20 = M5
   - mesocycle_week: 1/2/3/4 ciclico
   - mesocycle_type: Base/Build/Peak/Scarico
   - phase: "Pre-gara HM" per W1-20
5. Gestisci anomalie:
   - W10: "Tosse e raffreddore" -> sessione con distance=0, note="Malattia"
   - W11: "Maltempo" -> sessione con distance=0, note="Maltempo"
   - W13: "Maltempo" -> idem
   - W6 mer: "30' L (pre-test)" -> tipo cambia da Ripetute a Easy
   - W12 ven: "Test 5km" -> tipo = Test
   - W18 lun: "Test 5km" -> tipo = Test
6. Sett 21-32: presenti nell'Excel ma vuote -> ignora o segna come "planned"
7. Salva running-log.json
```

**Riepilogo dati Excel (per verifica):**

| Sett | Vol | D.A. | Ripetute | Progressivo | Lungo | Note |
|------|-----|------|----------|-------------|-------|------|
| 1 | 27 | 7km | 10x400m | 4L+2M | 10L | M1 Base |
| 2 | 31 | 7km | 5x1TR | 6L+2M | 11L | M1 Build |
| 3 | 35 | 8km | 4x1600m | 3x(1L+1M+1TR) | 12L | M1 Peak |
| 4 | 20 | 7km | 5x1TR | 4L+2M | 30'L | M1 Scarico |
| 5 | 35 | 7km | 4x2km | 6L+2M | 12L | M2 Base |
| 6 | 32 | 8km | 30'L pre-test | 5km | 13L | M2 Build (test ven) |
| 7 | 38 | 9km | 5x1km | 6L+2M | 16L | M2 Peak |
| 8 | 23 | 6km | 5x1km TR | 4L+2M | 30'L | M2 Scarico |
| 9 | 37 | 9km | 4x1600m | 3x(1L+1M+1TR) | 13L | M3 Base |
| 10 | 21 | 0 | 0 | 6L | 15L | Malattia |
| 11 | 28 | 6km | 0 | 8L | 30'L | Maltempo |
| 12 | 27 | 6km | 6kmL | Test 5km | 10L | M3 Scarico (test) |
| 13 | 24 | 12km | 0 | 0 | 8L+4M | Maltempo x2 |
| 14 | 50 | 13km | 5x1600m RM | 8L+4M+1TR | 1h20'L | M4 Peak |
| 15 | 50 | 13km | 3x2km RM | 6L+3M+2TR+1VR | 15L+4M | M4 Build (picco) |
| 16 | 21 | 6km | 5x1km TR | 30'L | 20'L | M4 Scarico |
| 17 | 39 | 6km | 3x2km RM | 3L+3x(1L+1M+1TR) | 15L | M5 Build |
| 18 | 47 | Test 5km | 3x4km RM | 6L+3M+2TR+1VR | 12L+6M | M5 Peak |
| 19 | 44 | 10km | 4x2500m RM | 3x(1L+1M+1TR) | 15L | M5 carico |
| 20 | 25 | 6km | 5x1km RM | 6L+2M | 30'L | M5 Scarico (test 5km 09/02) |

#### 3b. Arricchimento running-log da storico Garmin

**Fonte**: `storico.csv` — export Garmin Connect, 100 attivita' (gen 2025 - feb 2026)

**Colonne disponibili per sessione:**
- Data, Titolo, Distanza, Tempo, Passo medio, Passo migliore
- FC Media, FC max, TE aerobico
- Cadenza media/max, Lunghezza passo
- GCT medio, Bilanciamento TCS
- Oscillazione verticale, Rapporto verticale
- Calorie, Temperatura, Dislivello, Passi

**Nota**: GCT e oscillazione verticale disponibili solo da ~ottobre 2025
(probabilmente cambio orologio/fascia). Prima: dati parziali (solo cadenza e FC).

**Logica match Excel <-> Garmin:**
```
Per ogni sessione nel running-log (da Excel):
1. Cerca nel CSV Garmin per data (+/- 1 giorno per gestire sfasamenti)
2. Match primario: data + distanza simile (+/- 15%)
3. Match secondario: titolo Garmin contiene struttura workout
4. Se match trovato: arricchisci sessione con dati Garmin
5. Se nessun match: sessione resta con solo dati Excel (planned)
```

**Dati Garmin aggiunti a ogni sessione:**
```json
{
  "date": "2025-10-13",
  "day": "Mon",
  "type": "DA",
  "workout": "7km D.A.",
  "structure": "7x[0.85L+0.15All]",
  "distance_planned": 7.0,
  "garmin": {
    "title": "Latina - 7 km D.A.",
    "distance_actual": 7.01,
    "time": "00:32:12",
    "pace_avg": "4:36",
    "pace_best": "4:06",
    "hr_avg": 172,
    "hr_max": 184,
    "cadence_avg": 174,
    "gct_avg": null,
    "vertical_osc": null,
    "vertical_ratio": null,
    "stride_length": null,
    "calories": 455,
    "temperature": "18-22",
    "elevation_gain": 8
  }
}
```

**Valore aggiunto:**
- Trend biomeccanici su 5 mesi (GCT, cadenza, osc. vert.)
- Confronto planned vs actual distance
- Analisi FC per tipo di sessione (easy dovrebbe stare in Z2)
- Tracking passo medio per sessioni comparabili (es. tutti i D.A.)
- Base dati per `/analyze --compare` tra sessioni storiche

**Sessioni pre-programma (gen-set 2025):**
Il CSV contiene ~30 sessioni prima dell'inizio del programma (W1 = 13/10/2025).
Queste vanno nel running-log come `week: 0, phase: "pre-programma"`.
Utili come baseline per confronti.

#### 4. strength-progress.json — Inizializzazione

```json
{
  "current_levels": {
    "ab_wheel": "not_started",
    "push_up": "not_started",
    "pogo": "not_started",
    "squat_jump": false,
    "split_squat_jump": false,
    "bulgarian": "not_started",
    "single_leg_dl": "not_started",
    "calf_raise": "not_started",
    "calf_raise_single": false
  },
  "history": [],
  "progression_log": []
}
```

Tutti i livelli partono da "not_started". La prima sessione (12/02/2026)
li porta a livello "base" e registra la prima entry in history.

#### 5. changelog.json — Prima entry

```json
{
  "entries": [
    {
      "timestamp": "2026-02-12T00:00:00",
      "command": "/bootstrap",
      "trigger": "initial setup",
      "files_modified": [
        "data/composition.json",
        "data/zones.json",
        "data/running-log.json",
        "data/strength-progress.json",
        "data/changelog.json"
      ],
      "changes": {
        "composition": "3 misurazioni importate (set 2025 - feb 2026)",
        "zones": "3 test importati, zone correnti da test 09/02/2026",
        "running_log": "20 settimane importate da pianorunning.xlsx",
        "strength": "inizializzato a livello base (zero storico)"
      }
    }
  ]
}
```

#### 6. piano-base.md — Conversione formato

**Fonte**: `piano_base_ottimizzato.md` (585 righe, formato attuale)
**Target**: `knowledge/piano-base.md` (formato PRD, vedi sezione dedicata)

Conversione:
- Rimuovi emoji, istruzioni per IA, note Fase 2
- Aggiungi META comment (data validazione, versione)
- Semplifica formato: H2 per pasti, H3 per opzioni, ingredienti su una riga
- Mantieni OR, SWAP, (opzionale) come marker
- Aggiungi sezione REGOLE con vincoli hard

Questa conversione e' manuale (richiede giudizio), non automatizzabile.
Il tool verifica solo che il formato finale rispetti le regole di parsing.

#### 7. Piani nutrizionali — Aggiunta META + AUDIT

**Fonte**: 8 file `piano_*.md` esistenti
**Azione**: Aggiungi in testa a ciascuno il commento META e in coda l'AUDIT

```
Per ogni piano in [rest, forza, easy_run, qualita, tempo, lungo, pizza_day, domenica]:
1. Leggi FFM, BMR, target kcal dal calcolo in testa al piano
2. Genera META comment:
   <!-- META
   categoria: [NOME]
   generato: 2025-10 (data originale stimata)
   ffm: 61.13 (valore usato alla generazione - STALE)
   peso: 70.95
   bmr: 1690
   pal: [dal piano]
   tdee: [dal piano]
   deficit: [dal piano]
   target_kcal: [dal piano]
   fase: Pre-gara HM
   -->
3. Genera AUDIT comment:
   <!-- AUDIT: STALE | 2026-02-12 bootstrap | ffm_current:59.57 vs ffm_plan:61.13 | delta:1.56kg -->
4. Tutti i piani risulteranno STALE perche' generati con FFM 61.13 vs attuale 59.57
   Questo e' corretto: il bootstrap documenta lo stato, non lo corregge.
   La rigenerazione e' un'azione separata (/plan all).
```

**Nota critica**: I piani attuali sono funzionali ma calcolati su FFM obsoleta.
L'impatto pratico e' ~20-30 kcal/giorno (differenza piccola).
La rigenerazione completa (/plan all) e' consigliata ma non urgente.

---

#### Riepilogo azioni utente per il bootstrap

| # | Azione | Urgenza | Note |
|---|--------|---------|------|
| 1 | Conferma pesate intermedie (ott-gen) | Media | Se esistono, arricchiscono il trend |
| 2 | Conferma date/tempi test 5km | Alta | Necessario per zones.json accurato |
| 3 | Segnala CSV Garmin gia' scaricati | Bassa | Opzionale, per linkare a running-log |
| 4 | Conferma primo giorno forza (12/02) | Alta | Inizializza strength-progress |

---

### VALIDAZIONE

| Comando | Cosa fa | Input | Output |
|---------|---------|-------|--------|
| `/validate plans` | Verifica tutti i piani vs food-db e linee-guida | - | Report mismatch |
| `/validate sync` | Controlla allineamento cross-documento | - | Report consistenza |
| `/validate plan <cat>` | Verifica singolo piano | Categoria | Report dettagliato |

#### Logica `/validate sync`

```
Controlla:
1. FFM in composition.json == FFM usata nei calcoli dei piani
2. Zone in zones.json == zone usate nei piani running
3. Alimenti nei piani == presenti in food-db.md con stessi valori
4. Distribuzioni % nei piani == distribuzioni in linee-guida.md
5. Combinazioni pasti nei piani == presenti in piano-base.md
6. Target macro nei piani == coerenti con fase corrente

Output:
- [SYNC] Tutti i documenti allineati
oppure
- [DRIFT] Lista mismatch con file + riga + valore atteso vs trovato
  + raccomandazione (rigenerare / ignorabile / critico)
```

#### Logica `/validate plans`

```
Per ogni piano (8 categorie):
1. Importa FOOD_DB dal piano
2. Confronta ogni voce con food-db.md MASTER
3. Per ogni opzione: ricalcola totali da grammature x valori 100g
4. Verifica:
   - Opzione: +/-20 kcal, +/-1g P, +/-2g CHO, +/-2g F
   - Pasto medio: +/-30 kcal
   - Giorno: +/-1% kcal, P 2.0-2.2 g/kg
5. Verifica vincoli alimentari:
   - Colazione: no mix dolce+salato
   - Cena: no pasta/riso
   - Patate: swap pane indicato
   - Olio: porzione fissa (no range)
   - Yogurt: tipo corretto per categoria

Output per piano:
- [OK] Piano XXXXX: 0 errori, 0 warning
oppure
- [ERR] Piano XXXXX: N errori
  - Opzione X pasto Y: kcal 485 vs target 450 (delta +35, soglia +/-20)
  - FOOD_DB mismatch: "tonno" 116 kcal vs MASTER 103 kcal
  - Vincolo violato: cena con pasta
```

---

## Priorita' di implementazione

| Passo | Comando | Valore | Complessita' | Note |
|-------|---------|--------|-------------|------|
| 1 | `/validate sync` + `/validate plans` | Altissimo | Bassa | Previene drift, problema gia' sperimentato |
| 2 | `/analyze` | Alto | Media | Analisi Garmin automatizzata, uso frequente |
| 3 | `/plan <categoria>` | Alto | Media-alta | Task piu' ripetitivo e error-prone |
| 4 | `/weigh` + `/status` + `/alerts` | Medio | Bassa | Tracking centralizzato |
| 5 | `/test` + `/zones` | Medio | Bassa | Utile ma raro (ogni 4 sett) |
| 6 | `/plan all` + `/swap` | Medio | Media | Dipende da /plan funzionante |
| 7 | `/plan-season` | Alto (da luglio) | Media | Fondamentale per prep maratona. Ora gia' utile per visualizzare la stagione |
| 8 | `/plan-block` | Alto (da luglio) | Media | Dettaglia mesocicli. Diventa critico con volumi maratona |
| 9 | `/week` | Medio | Bassa | Consultazione dettaglio, dipende da plan-block |
| 10 | `/taper` | Alto (pre-gara) | Media | Critico 2-3 sett prima di ogni gara A |
| 11 | `/race` | Medio | Alta | Semi-conversazionale, meno automatizzabile |
| 12 | `/checkpoint` | Basso | Bassa | Template gia' nelle istruzioni, facile manuale |
| 13 | `/strength` | Alto (immediato) | Bassa | Pool esercizi gia' definito, periodizzazione semplice |
| 14 | `/drills` | Basso | Minima | Sequenza fissa, non richiede logica. Utile come reference |

---

## Error handling e recovery

Pattern uniforme per tutti i comandi. L'obiettivo e' **non produrre output
corrotto** — meglio fermarsi e spiegare che generare un piano sbagliato.

### Pattern generale

```
1. Validazione input
   - Input mancante/malformato -> messaggio chiaro + esempio uso corretto
   - File dipendenza non trovato -> "Manca [file]. Esegui prima [comando]."

2. Esecuzione
   - Errore recuperabile -> retry automatico (max 3 tentativi)
   - Errore non recuperabile -> stop + spiegazione + azione suggerita

3. Validazione output
   - Soglie superate -> ricalcola internamente (max 3 tentativi)
   - Ancora fuori soglia dopo 3 tentativi -> stop + mostra il problema
```

### Casistiche specifiche

**`/plan` — tolleranze non rispettate dopo 3 tentativi**
```
[ERRORE] Piano QUALITA': impossibile rispettare tolleranze.
Opzione PRANZO-3: target 875 kcal, calcolato 912 kcal (delta +37, soglia +/-20)
Causa probabile: combinazione alimenti con granularita' troppo grossa.

Azioni possibili:
  1. Modificare l'opzione nel Piano Base (rimuovere/sostituire alimento)
  2. Rilassare la tolleranza per questa opzione a +/-40 kcal [richiede conferma]
  3. Provare con quantita' tampone diversa
```

**`/plan` — alimento mancante nel MASTER**
```
[STOP] Alimento "fiocchi di farro" non trovato in food-db.md.
Generazione piano sospesa.

Azioni:
  1. /food add "fiocchi di farro" <valori> <fonte>  -> poi riesegui /plan
  2. Sostituire con alimento esistente nel Piano Base
```

**`/analyze` — CSV con formato inatteso**
```
[ERRORE] Formato CSV non riconosciuto.
Colonne attese: 25 | Colonne trovate: 18
Colonne mancanti: Potenza, Oscillazione verticale, Rapporto verticale, ...

Possibili cause:
  - Export da dispositivo diverso (non Garmin)
  - Export parziale (solo dati base)

Azione: il report verra' generato con le colonne disponibili.
        Le sezioni mancanti saranno indicate con [DATI NON DISPONIBILI].
[Procedere? y/n]
```

**`/analyze` — auto-detection tipo fallita**
```
[INFO] Tipo attivita' non determinato automaticamente.
Distanza: 7.2 km | CV passo: 5.3% | Profilo: misto

Seleziona manualmente:
  1. easy     (corsa facile Z2)
  2. progressivo  (progressione Z2->Z5)
  3. ripetute     (intervalli)
  4. gara         (competizione)
```

**`/weigh` — dato anomalo**
```
[WARNING] Variazione peso anomala: -1.8 kg in 3 giorni.
Probabile causa: fluttuazione idrica, non perdita reale.

Dato registrato ma escluso dal calcolo trend.
Prossima pesata confermera' o corregera'.
```

**`/validate` — mismatch trovati**
```
[DRIFT] 3 mismatch trovati:

1. plans/nutrition/qualita.md: FOOD_DB "tonno al naturale" = 116 kcal
   food-db.md MASTER: 103 kcal
   -> Impatto: tutte le opzioni pranzo con tonno sovrastimano +10-15 kcal
   -> Fix: rigenera con /plan qualita

2. plans/nutrition/forza.md: META ffm=61.13, composition.json ffm=59.57
   -> Piano stale (delta 1.56 kg > soglia 0.5 kg)
   -> Fix: rigenera con /plan forza

3. plans/running/block-05.md: META zones_date=2026-01-02, zones.json=2026-02-09
   -> Zone non aggiornate
   -> Fix: rigenera con /plan-block 5
```

**Dipendenza circolare / file mancante**
```
[ERRORE] /plan-block 7: richiede plans/running/season.md (non trovato).
Esegui prima: /plan-season
```

---

## Changelog e versioning

Quando un piano viene rigenerato, il tool produce un **diff sintetico**
che mostra cosa e' cambiato. Non serve version control completo (git),
basta un log append-only.

### File: `data/changelog.json`

```json
{
  "entries": [
    {
      "timestamp": "2026-02-11T14:30:00",
      "command": "/plan qualita",
      "trigger": "FFM update 60.08 -> 59.57",
      "files_modified": ["plans/nutrition/qualita.md"],
      "changes": {
        "meta": {
          "ffm": {"old": 60.08, "new": 59.57},
          "bmr": {"old": 1668, "new": 1657},
          "target_kcal": {"old": 2650, "new": 2597}
        },
        "distribution": {
          "colazione_kcal": {"old": 451, "new": 441},
          "pranzo_kcal": {"old": 875, "new": 857}
        },
        "options_modified": 12,
        "options_unchanged": 18,
        "max_portion_delta": "-5g pasta (100->95g) in PRANZO-1"
      }
    },
    {
      "timestamp": "2026-02-11T14:35:00",
      "command": "/swap tonno_naturale tonno_sgocciolato",
      "trigger": "user request",
      "files_modified": [
        "plans/nutrition/qualita.md",
        "plans/nutrition/easy-run.md",
        "plans/nutrition/lungo.md"
      ],
      "changes": {
        "food_db": {
          "removed": "Tonno al naturale (drenato)",
          "added": "Tonno sgocciolato"
        },
        "affected_options": ["QUALITA/PRANZO-1", "EASY-RUN/PRANZO-1", "LUNGO/PRANZO-3"],
        "portion_adjustments": "80g -> 75g (compensazione delta kcal)"
      }
    },
    {
      "timestamp": "2026-03-29T18:00:00",
      "command": "/test 17:52",
      "trigger": "test 5km post-Latina HM",
      "files_modified": ["knowledge/zones.json"],
      "changes": {
        "test_time": {"old": "18:26", "new": "17:52"},
        "test_pace": {"old": "3:41", "new": "3:34"},
        "zones": {
          "Z2": {"old": "4:40-5:11", "new": "4:33-5:04"},
          "Z6": {"old": "3:42-3:50", "new": "3:35-3:43"}
        },
        "stale_files": ["plans/running/block-07.md"]
      }
    }
  ]
}
```

### Comandi changelog

| Comando | Cosa fa |
|---------|---------|
| `/log` | Mostra ultime 10 entry del changelog |
| `/log <file>` | Mostra storico modifiche di un file specifico |
| `/log diff <file>` | Mostra diff dettagliato ultima modifica vs precedente |

### Logica

Ogni comando che modifica un file in `plans/` o `knowledge/` **deve**
appendere una entry al changelog. Il tool lo fa automaticamente.

Il changelog serve anche per rispondere a domande tipo:
- "Quando ho aggiornato l'ultimo piano?" -> `/log`
- "Cosa e' cambiato nel piano forza?" -> `/log plans/nutrition/forza.md`
- "Quante volte ho rigenerato i piani questo mese?" -> `/log` + filtro

---

## Dipendenze tra comandi (grafo)

Quando un dato cambia, altri file diventano potenzialmente stale.
Il tool deve conoscere queste dipendenze per suggerire azioni a cascata.

### Grafo dipendenze

```
composition.json (FFM, peso)
  |
  +-> plans/nutrition/*.md  (se delta FFM > 0.5 kg)
  |     Suggerisce: /plan all
  |
  +-> data/changelog.json
        Registra: variazione composizione

zones.json (zone aggiornate)
  |
  +-> plans/running/block-*.md  (se zones_date diversa)
  |     Suggerisce: /plan-block <N> per blocchi attivi
  |
  +-> plans/running/season.md   (nessun impatto diretto,
  |     le zone non cambiano la struttura stagionale)
  |
  +-> data/changelog.json

knowledge/food-db.md (valori nutrizionali)
  |
  +-> plans/nutrition/*.md  (se alimento modificato e' usato)
  |     Suggerisce: /plan <categorie_coinvolte> oppure /plan all
  |
  +-> data/changelog.json

knowledge/piano-base.md (combinazioni approvate)
  |
  +-> plans/nutrition/*.md  (se opzioni aggiunte/rimosse/modificate)
  |     Suggerisce: /plan all (rigenerazione completa)
  |
  +-> data/changelog.json

knowledge/linee-guida.md (distribuzioni %, regole)
  |
  +-> plans/nutrition/*.md  (se distribuzioni % cambiate)
  |     Suggerisce: /plan all
  |
  +-> plans/running/season.md  (se periodizzazione/fasi cambiate)
  |     Suggerisce: /plan-season
  |
  +-> plans/running/block-*.md  (se bacino workout/regole cambiate)
        Suggerisce: /plan-block <N> per blocchi futuri
```

### Implementazione nel tool

Dopo ogni comando che modifica un file sorgente, il tool esegue
un **check cascata** automatico:

```
1. Identifica file modificato
2. Cerca dipendenze nel grafo
3. Per ogni file dipendente:
   a. Confronta META del file dipendente con sorgente aggiornato
   b. Se stale: aggiungi a lista "suggerimenti"
4. Mostra suggerimenti all'utente:

   [CASCADE] Aggiornamento FFM ha reso stale 8 piani nutrizionali.
   
   File stale:
     plans/nutrition/rest.md        (META ffm: 60.08 -> 59.57)
     plans/nutrition/forza.md       (META ffm: 60.08 -> 59.57)
     ... (6 altri)
   
   Azioni suggerite:
     /plan all              -> rigenera tutti i piani
     /validate plans        -> verifica impatto prima di rigenerare
   
   [I piani restano funzionali, la differenza e' ~20 kcal/giorno]
```

Il tool **suggerisce** ma non esegue automaticamente le cascate.
L'utente decide se rigenerare subito o aspettare.

Eccezione: `/validate sync` mostra TUTTI i file stale senza suggerire
cascate — e' un report puro.

---

## Formato `knowledge/piano-base.md`

Il piano base e' l'output della Fase 1 (validazione qualitativa) e l'input
fondamentale per `/plan`. Contiene le combinazioni approvate senza quantita'.

### Struttura

```markdown
<!-- META
validato: 2026-02-11
versione: 3
note: Aggiunto hummus fagioli a cena, rimosso yogurt greco da colazione standard
-->

# Piano Base Validato

## REGOLE

### Colazione
- NO mix dolce+salato (solo tutto dolce OPPURE tutto salato)
- Marmellata MAI con crudo/bresaola
- Yogurt consentito in entrambe le versioni
- MAI pomodoro
- MAI uova sode

### Yogurt
- Default: Yogurt magro 0.1% 125g + frutta secca OPPURE fiocchi d'avena
- Solo se necessario (es. PIZZA DAY low-fat): Yogurt greco 0% 170g

### Pranzo
- Pasta/riso SOLO a pranzo, MAI a cena
- Frutta obbligatoria

### Cena
- MAI pasta/riso
- Struttura: proteine + verdure + patate o pane (con swap esplicito)
- Patate: sempre lesse o al forno senza olio (olio EVO a crudo)
- Olio: solo a crudo

### Generale
- Olio EVO: porzione fissa 10g
- Pollo: piastra o forno (MAI lesso)

---

## COLAZIONE

### Dolce - Fette biscottate + marmellata + yogurt + frutta secca
Caffe', Fette biscottate, Marmellata, Yogurt magro 0.1%, Mandorle OR Noci OR Nocciole
Swap: Fette <-> Pane integrale

### Dolce - Pane + marmellata + yogurt + frutta secca
Pane integrale, Marmellata, Yogurt magro 0.1%, Mandorle OR Noci OR Nocciole

### Salata - Pane + affettato + formaggio
Pane integrale, Prosciutto crudo OR Bresaola OR Fesa tacchino, Formaggio spalmabile light, Caffe'

### Dolce - Torta homemade + yogurt
Plum cake OR Ciambellone (senza latte/burro), Yogurt magro 0.1%, Mandorle

### Dolce - Biscotti + burro d'arachidi + yogurt
Oro Saiwa, Burro d'arachidi, Yogurt magro 0.1%
Variante: Oro Saiwa + Marmellata + Yogurt + Mandorle

---

## SPUNTINO_AM

### Frutta + frutta secca
Mela OR Banana, Mandorle OR Noci OR Burro d'arachidi

### Yogurt dolce + frutta
Yogurt magro 0.1%, Banana OR Mela, Miele

### Crackers + affettato
Crackers integrali, Bresaola OR Prosciutto crudo OR Formaggio spalmabile, Mela (opzionale)

### Yogurt + affettato + crackers
Yogurt magro 0.1%, Bresaola OR Prosciutto crudo, Crackers integrali

---

## PRANZO

### Pasta al tonno + verdure + frutta
Pasta secca, Tonno al naturale OR Tonno sott'olio, Zucchine OR Carote, Olio EVO, Frutta

### Pasta al ragu' + verdure + frutta
Pasta secca, Ragu' di vitello, Zucchine OR Carote, Olio EVO, Frutta

### Riso + proteina + verdure + frutta
Riso basmati, Pollo OR Salmone OR Pesce spada OR Uova, Piselli, Zucchine OR Carote, Olio EVO, Frutta

### Tortellini + parmigiano + verdure + frutta
Tortellini vitello, Parmigiano, Zucchine OR Carote, Olio EVO, Frutta

### Pasta semplice + verdure + frutta
Pasta secca, Olio EVO, Parmigiano, Passata pomodoro (opzionale), Zucchine OR Carote, Frutta

### Piatto proteico freddo + pane + verdure + frutta
Mozzarella bufala, Prosciutto crudo OR Bresaola, Parmigiano, Pane integrale, Zucchine OR Carote, Olio EVO, Frutta

---

## SPUNTINO_PM

### Frutta + yogurt + frutta secca
Banana OR Mela, Yogurt magro 0.1%, Mandorle OR Noci

### Frutta + burro d'arachidi
Banana OR Mela, Burro d'arachidi

### Frutta + frutta secca
Banana OR Mela, Mandorle OR Noci

### Crackers + affettato
Crackers integrali, Prosciutto crudo OR Bresaola

### Pre-workout max CHO
Banana, Crackers integrali OR Fette biscottate, Miele

---

## SPUNTINO_SERA (opzionale)

### Solo frutta
Banana OR Mela

### Frutta + yogurt
Banana OR Mela, Yogurt magro 0.1%

### Affettato + crackers
Bresaola OR Prosciutto crudo, Crackers integrali

---

## CENA

### Carne + patate/pane + verdure
Pollo piastra OR Tacchino OR Vitello OR Manzo, Patate lesse SWAP Pane integrale, Zucchine OR Carote, Olio EVO

### Pesce + patate/pane + verdure
Salmone OR Pesce spada OR Merluzzo OR Tonno tagliata, Patate lesse SWAP Pane integrale, Zucchine OR Carote, Olio EVO

### Uova + pane + verdure/vellutata
Uova, Pane integrale, Zucchine OR Carote OPPURE Vellutata, Olio EVO

### Hummus + pane + verdure
Hummus ceci OR Hummus fagioli, Pane integrale, Zucchine OR Carote, Olio EVO
```

---

### Regole di parsing piano-base

**Sezioni pasto**: H2 (`##`) con nome pasto (COLAZIONE, SPUNTINO_AM, ecc.)

**Opzioni**: H3 (`###`) con nome descrittivo.
L'ID implicito e' `<PASTO>/<indice>` in ordine di apparizione.

**Ingredienti**: una riga per opzione, lista separata da virgole.
Le alternative sono indicate con `OR`.
Gli elementi opzionali sono indicati con `(opzionale)`.
Gli swap sono indicati con `SWAP` o `<->`.
Le varianti sono righe separate che iniziano con `Variante:`.

**Vincoli del `/plan`**:
- Il tool legge le opzioni dal piano-base e le quantifica
- NON puo' creare combinazioni non presenti nel piano-base
- Se un'opzione non riesce a rispettare le tolleranze, segnala l'errore
  (non inventa alternative)
- Le regole nella sezione REGOLE sono **vincoli hard**: il tool le verifica
  e rifiuta output che le violano

---

## Cosa resta conversazionale (NON automatizzare)

- Decisioni strategiche: refeed, cambio fase, riduzione deficit
- Analisi qualitative: interpretazione test anomali, diagnosi calo performance
- Modifiche al piano base (Fase 1): processo umano-nel-loop
- Race strategy complessa: `/race` genera bozza, ma revisione finale e' conversazionale (Opus)
- Revisione linee-guida: richiede giudizio critico
- Conflitti tra obiettivi: trade-off multi-variabile
- Cambio calendario gare: impatta `/plan-season`, richiede decisione strategica prima di rigenerare

Regola: **Sonnet per eseguire i comandi, Opus per le conversazioni strategiche.**

---

## Data model

### composition.json
```json
{
  "measurements": [
    {
      "date": "2026-02-11",
      "weight": 68.65,
      "bf_pct": 13.2,
      "ffm": 59.57,
      "bmr": 1656,
      "muscle_mass": 56.60,
      "subcutaneous_fat": 11.2,
      "visceral_fat": 7,
      "body_water": 62.7,
      "bone_mass": 2.98,
      "metabolic_age": 36,
      "source": "impedance_scale"
    }
  ]
}
```

### zones.json
```json
{
  "current": {
    "test_date": "2026-02-09",
    "test_time": "18:26",
    "test_pace": "3:41",
    "zones": {
      "Z1": {"from": "5:11", "to": "inf", "rpe": "1-2", "use": "Recovery"},
      "Z2": {"from": "4:40", "to": "5:11", "rpe": "3-4", "use": "Easy/Long"},
      "Z3": {"from": "4:16", "to": "4:40", "rpe": "5", "use": "Moderate"},
      "Z4": {"from": "4:02", "to": "4:16", "rpe": "6", "use": "High Aerobic"},
      "Z5": {"from": "3:50", "to": "4:02", "rpe": "7", "use": "Threshold-"},
      "Z6": {"from": "3:42", "to": "3:50", "rpe": "7-8", "use": "Threshold"},
      "Z7": {"from": "3:29", "to": "3:42", "rpe": "8-9", "use": "VO2max-"},
      "Z8": {"from": "3:25", "to": "3:29", "rpe": "9", "use": "VO2max"}
    }
  },
  "history": [
    {"date": "2024-01-01", "time": "20:30", "pace": "4:06"},
    {"date": "2026-01-02", "time": "19:03", "pace": "3:49"},
    {"date": "2026-02-09", "time": "18:26", "pace": "3:41"}
  ]
}
```

### running-log.json (esempio settimana)
```json
{
  "weeks": [
    {
      "week": 20,
      "phase": "Pre-gara HM",
      "mesocycle_week": 4,
      "mesocycle_type": "Scarico",
      "volume_planned": 25,
      "volume_actual": 25,
      "sessions": [
        {
          "day": "Mon",
          "type": "DA",
          "workout": "6km D.A. facile",
          "distance": 6,
          "garmin_file": "activity_xxxxx.csv"
        }
      ]
    }
  ]
}
```
