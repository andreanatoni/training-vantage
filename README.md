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
| `./tv plan <cat>` | ✅ | Genera piano nutrizionale con target kcal/macro |
| `./tv plan --all` | ✅ | Rigenera tutti gli 8 piani (AGGIORNATI) |

### 🚧 In Sviluppo (Priorità 2-3)

| Comando | Stato | Descrizione |
|---------|-------|-------------|
| `./tv food add` | 🚧 | Aggiunge alimento a food-db.md |

### 📋 Pianificato (Priorità 3-4)

- `./tv week <N>` — Mostra piano running settimana N
- `./tv analyze <file.csv>` — Analizza workout Garmin
- `./tv compare <tipo>` — Confronta sessioni simili
- `./tv strength <type>` — Genera scheda forza
- `./tv checkpoint` — Template checkpoint con dati attuali

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
│   ├── nutrition/              # 8 piani quantitativi (STALE - da rigenerare)
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
- **Food DB**: `knowledge/food-db.md` (SSoT per valori nutrizionali)
- **Piano base**: `knowledge/piano-base.md` (SSoT per combinazioni alimentari)

---

## Log Modifiche

Tutte le modifiche ai dati sono tracciate in `data/changelog.json`:
- Bootstrap iniziale: 11/02/2026 18:00
- Ultima pesata: 11/02/2026 14:11 (68.5kg, 13.0%)
- Ultimo test zone: 11/02/2026 14:18 (18:00, miglioramento 27s)

---

**Versione**: 1.0
**Ultimo aggiornamento**: 11 febbraio 2026
