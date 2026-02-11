# Note Tecniche — Formule Zone Running

## Stato Attuale

Le formule per il calcolo automatico delle zone da test 5km in `scripts/zones.py` sono implementate ma **potrebbero necessitare verifica** rispetto al PRD.

## Discrepanza Rilevata

Test 5km: **18:27** (3:41/km)

### Zone attese (dal PRD):
- Z6: 3:42 - 3:50
- Z4: 4:02 - 4:16
- Z2: 4:40 - 5:11
- Z1: 5:11+

### Zone calcolate dallo script:
- Z6: 3:50 - 3:58  (+8" shift)
- Z4: 4:10 - 4:24  (+8" shift)
- Z2: 4:48 - 5:19  (+8" shift)
- Z1: 5:19+        (+8" shift)

## Formule Implementate (da verificare)

```python
pace_seconds = test_time_seconds / 5

z6_sec = pace_seconds + 9
z5_sec = z6_sec + 8
z4_sec = z6_sec + 20
z3_sec = z4_sec + 14
z2_sec = z3_sec + 24
z1_sec = z2_sec + 31

z7_from_sec = pace_seconds - 2
z7_to_sec = pace_seconds - 12
z8_from_sec = pace_seconds - 12
z8_to_sec = pace_seconds - 16
```

## Formule dal PRD (da interpretare)

> Z6 = pace + 9"
> Z5 = Z6 + 8"
> Z4 = Z6 + 20"
> Z3 = Z4 + 14"
> Z2 = Z3 + 24"
> Z1 = Z2 + 31"
> Z7 = pace - 2" a pace - 12"
> Z8 = pace - 12" a pace - 16"

**Ambiguità**: Non è chiaro se le formule si riferiscono a:
- Il limite "from" della zona
- Il limite "to" della zona
- Il centro della zona

## Workaround Attuale

Per ora, le zone vengono **ripristinate manualmente** dal PRD quando necessario. Il comando `/zones [test_time]` calcola automaticamente ma i valori potrebbero necessitare aggiustamento manuale.

## TODO

1. Chiarire l'interpretazione corretta delle formule con l'utente
2. Verificare con test reali se le zone calcolate sono utilizzabili
3. Eventualmente aggiustare le formule in `scripts/zones.py`
4. Opzione alternativa: permettere override manuale delle zone

## Priorità

**BASSA** — Il comando `/zones` senza argomenti funziona perfettamente per visualizzare le zone attuali. Il calcolo automatico è un nice-to-have che può essere raffinato successivamente.

---

**Data**: 11/02/2026
**Autore**: Bootstrap Phase 1
