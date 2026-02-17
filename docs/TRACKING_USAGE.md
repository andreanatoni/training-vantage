# Training Vantage - Tracking Commands

> NOTE
> I comandi `python3 scripts/cli.py ...` sono legacy.
> Entry point ufficiale: `./tv ...` (es. `./tv weigh`, `./tv status`, `./tv zones`).

**Version**: 2.1 (Phase 1 - Tracking Base)
**Date**: 2026-02-12

---

## Overview

Comandi per tracking composizione corporea e zone running:
- `/weigh` - Registra pesata con calcolo FFM/BMR
- `/status` - Dashboard stato attuale
- `/zones` - Gestione zone running da test 5km

---

## `/weigh` - Registra Pesata

### Sintassi

```bash
python3 scripts/cli.py weigh <peso> <bf%> [note]
```

### Parametri

- `peso`: Peso corporeo in kg (float, es. 68.5)
- `bf%`: Body Fat percentage (float, es. 13.0)
- `note`: Note opzionali (string, tra virgolette se contiene spazi)

### Calcoli Automatici

Il comando calcola automaticamente:
- **FFM** (Fat-Free Mass) = peso × (1 - bf/100)
- **BMR** (Basal Metabolic Rate) = 370 + 21.6 × FFM (formula Katch-McArdle)

### Output

- Dati misurazione corrente
- Trend vs misurazione precedente (delta peso, BF%, FFM, BMR)
- **Alerts** automatici:
  - 🔴 RED: FFM < 59.5 kg
  - ⚠️ WARNING: FFM < 60.0 kg
  - ⚠️ WARNING: Perdita peso > 0.6%/sett
  - ⚠️ WARNING: FFM in calo per 4+ pesate consecutive
  - ℹ️ INFO: Delta BMR > 30 kcal → rigenera piani nutrizionali

### Esempi

```bash
# Pesata semplice
python3 scripts/cli.py weigh 68.5 13.0

# Pesata con nota
python3 scripts/cli.py weigh 68.65 13.2 "W20 scarico"

# Pesata post-gara
python3 scripts/cli.py weigh 69.4 13.4 "Post 29K Latina"
```

### Output Esempio

```
================================================================================
📊 NUOVA PESATA
================================================================================

Data: 2026-02-12
Peso: 68.50 kg
BF%: 13.0%
FFM: 59.59 kg
BMR: 1657 kcal
Note: Test tracking implementation

================================================================================
📈 TREND (vs 2026-02-11, 1 giorni)
================================================================================

  Peso:  +0.00 kg (+0.00%, +0.00%/sett)
  BF%:   +0.0%
  FFM:   +0.00 kg
  BMR:   +0 kcal

================================================================================
⚠️  ALERTS
================================================================================

  ⚠️  FFM 59.59 kg < FLOOR 60.0 kg (a 0.09 kg da red flag)

================================================================================
✅ Pesata registrata con successo
================================================================================
```

---

## `/status` - Dashboard

### Sintassi

```bash
python3 scripts/cli.py status
```

### Output

Dashboard completo con:
- **Composizione corporea**:
  - Ultima pesata (data, peso, BF%, FFM, BMR)
  - Trend recente (delta peso, FFM)
- **Zone running**:
  - Ultimo test 5km (data, tempo, pace)
  - Tabella zone Z1-Z8
- **Alerts attivi** (tutti i warning/red flags)

### Esempio

```bash
python3 scripts/cli.py status
```

### Output Esempio

```
================================================================================
📊 TRAINING VANTAGE - STATUS DASHBOARD
================================================================================

🏋️  COMPOSIZIONE CORPOREA
────────────────────────────────────────────────────────────────────────────────

  Ultima pesata: 2026-02-12
  Peso: 68.50 kg | BF: 13.0% | FFM: 59.59 kg
  BMR: 1657 kcal

  Trend (1 giorni):
    Peso: +0.00 kg (+0.00%/sett)
    FFM: +0.00 kg

🏃 ZONE RUNNING
────────────────────────────────────────────────────────────────────────────────

  Ultimo test: 2026-02-09
  Tempo 5km: 18:27 (pace 3:41/km)

  Zone:
    Z1: 5:11+ (Recovery)
    Z2: 4:40-5:11 (Easy)
    Z3: 4:16-4:40 (Moderate)
    Z4: 4:02-4:16 (High Aerobic)
    Z5: 3:50-4:02 (Threshold-)
    Z6: 3:42-3:50 (Threshold)
    Z7: 3:29-3:42 (VO2max-)
    Z8: 3:25-3:29 (VO2max)

⚠️  ALERTS ATTIVI
────────────────────────────────────────────────────────────────────────────────

  ⚠️  FFM 59.59 kg < FLOOR 60.0 kg (a 0.09 kg da red flag)

================================================================================
```

---

## `/zones` - Gestione Zone Running

### Sintassi

```bash
# Mostra zone attuali
python3 scripts/cli.py zones

# Aggiorna zone da nuovo test 5km
python3 scripts/cli.py zones <tempo_test> [note]
```

### Parametri

- `tempo_test`: Tempo test 5km in formato "MM:SS" (es. "18:27")
- `note`: Note opzionali sul test

### Formule Zone

Basate su test 5km pace (tempo/5):

```
Z8 (VO2max):       pace -16s a pace -12s
Z7 (VO2max-):      pace -12s a pace +1s
Z6 (Threshold):    pace +1s a pace +9s
Z5 (Threshold-):   pace +9s a pace +21s
Z4 (High Aerobic): pace +21s a pace +35s
Z3 (Moderate):     pace +35s a pace +59s
Z2 (Easy):         pace +59s a pace +90s
Z1 (Recovery):     pace +90s+
```

### Output

**Display mode** (senza parametri):
- Data ultimo test
- Tempo 5km e pace
- Tabella zone Z1-Z8

**Update mode** (con tempo_test):
- Nuove zone calcolate
- Confronto con test precedente
- Delta tempo (miglioramento/peggioramento)

### Esempi

```bash
# Mostra zone correnti
python3 scripts/cli.py zones

# Registra nuovo test
python3 scripts/cli.py zones 18:27

# Registra nuovo test con nota
python3 scripts/cli.py zones 18:15 "Test post scarico"
```

### Output Esempio (Display)

```
================================================================================
🏃 ZONE RUNNING ATTUALI
================================================================================

Test: 2026-02-09
Tempo 5km: 18:27 (pace 3:41/km)

Zone:
────────────────────────────────────────────────────────────────────────────────
  Z1: 5:11+ min/km  (Recovery)
  Z2: 4:40-5:11 min/km  (Easy)
  Z3: 4:16-4:40 min/km  (Moderate)
  Z4: 4:02-4:16 min/km  (High Aerobic)
  Z5: 3:50-4:02 min/km  (Threshold-)
  Z6: 3:42-3:50 min/km  (Threshold)
  Z7: 3:29-3:42 min/km  (VO2max-)
  Z8: 3:25-3:29 min/km  (VO2max)
================================================================================
```

### Output Esempio (Update)

```
================================================================================
🏃 ZONE AGGIORNATE DA NUOVO TEST
================================================================================

Data test: 2026-02-12
Tempo 5km: 18:15 (pace 3:39/km)
Note: Test più veloce

NUOVE ZONE:
────────────────────────────────────────────────────────────────────────────────
  Z1: 5:09+ min/km  (Recovery)
  Z2: 4:38-5:09 min/km  (Easy)
  Z3: 4:14-4:38 min/km  (Moderate)
  Z4: 4:00-4:14 min/km  (High Aerobic)
  Z5: 3:48-4:00 min/km  (Threshold-)
  Z6: 3:40-3:48 min/km  (Threshold)
  Z7: 3:27-3:40 min/km  (VO2max-)
  Z8: 3:23-3:27 min/km  (VO2max)

CONFRONTO CON TEST PRECEDENTE:
────────────────────────────────────────────────────────────────────────────────
  Test precedente: 2026-02-09 - 18:27 (pace 3:41/km)
  Delta tempo: -12s
  🎉 Miglioramento di 12s!

================================================================================
✅ Zone aggiornate con successo
================================================================================
```

---

## Data Files

### `data/composition.json`

Storico pesate con struttura:

```json
{
  "measurements": [
    {
      "date": "2026-02-12",
      "weight": 68.5,
      "bf_pct": 13.0,
      "ffm": 59.59,
      "bmr": 1657,
      "source": "manual_cli",
      "note": "Test tracking implementation"
    }
  ]
}
```

### `data/zones.json`

Zone correnti + storico test:

```json
{
  "current": {
    "test_date": "2026-02-09",
    "test_time": "18:27",
    "test_pace": "3:41",
    "zones": {
      "Z1": {"name": "Recovery", "from": "5:11", "to": null},
      "Z2": {"name": "Easy", "from": "4:40", "to": "5:11"},
      ...
    }
  },
  "history": [
    {
      "date": "2026-02-09",
      "time": "18:27",
      "pace": "3:41",
      "note": "W20 scarico"
    }
  ]
}
```

---

## Exit Codes

- **0**: Success
- **1**: Error (invalid input, missing data, etc.)

---

## Use Cases

### Weekly Tracking Routine

```bash
# Lunedì mattina: pesata settimanale
python3 scripts/cli.py weigh 68.5 13.0 "W21"

# Check status
python3 scripts/cli.py status

# Se alerts: valuta azioni (aumenta kcal, più forza, etc.)
```

### Test 5km Routine

```bash
# Dopo test 5km
python3 scripts/cli.py zones 18:15 "Test post scarico M3"

# Check nuove zone
python3 scripts/cli.py zones

# TODO: Rigenera piani running con nuove zone (Phase 4)
```

### Pre-Gara Check

```bash
# 1-2 giorni pre-gara
python3 scripts/cli.py status

# Verifica:
# - FFM stabile (non in calo)
# - Peso nel range target
# - Zone fresche (ultimo test non > 4 settimane)
```

---

## Testing

Test suite disponibile:

```bash
python3 tests/test_tracking.py
```

**Test coverage**:
- FFM/BMR calculation (formula Katch-McArdle)
- Zones calculation (formule da dati reali)
- Weigh command (save + analysis)
- Zones command (update + history)
- Alerts generation (red flags, warnings)

**Results**: 5/5 tests passing ✅

---

## Next Steps (Phase 2+)

**Non ancora implementato**:
- `/checkpoint` - Checkpoint template
- Next race info in status
- Integration con piani running (rigenera con nuove zone)
- Garmin CSV import per arricchire test history (HR data, splits, etc.)

---

**Version**: 2.1 (Phase 1 complete)
**Status**: Production-ready
**Date**: 2026-02-12
