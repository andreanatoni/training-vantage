# Nutrition Rules (Operational v1)

Questo file contiene regole operative conservative per proporre blocchi pasto nel setup.

## Gerarchia fonti

1. LARN (SINU)
2. CREA linee guida
3. ACSM/AND/DC consensus (performance sportiva)
4. IOC/ISSN per rifiniture sport-specific

## Principi

- Non sostituisce un professionista sanitario.
- Se i dati sono incompleti, usa regole conservative centrali (mai estremi).
- In caso trigger hard, il sistema si ferma e richiede consulto professionale.

## Regole blocchi (v1)

- `pre_workout`: priorita digestione e disponibilita energia.
  - blocchi base: `carb`, `protein`, `beverage`
- `post_workout`: priorita recupero.
  - blocchi base: `carb`, `protein`, `beverage`, `fruit`
- `default_day`: equilibrio.
  - blocchi base: `carb`, `protein`, `fat`

Meal adjustments:
- pranzo/cena: aggiungi `veg` salvo eccezioni pratiche.
- snack: mantieni struttura semplice (no `veg`), con `fruit` frequente.

Goal adjustments:
- `fat_loss`: riduci densita energetica snack, aumenta verdure nei pasti principali.
- `performance`: preserva presenza carboidrati nei pasti chiave.

Training adjustments:
- running >= 5 giorni/sett: carboidrati sempre presenti nei pasti principali.
- forza >= 2 giorni/sett: proteine in tutti i pasti principali.

## Trigger safety

I trigger sono definiti in `data/NUTRITION_SAFETY_TRIGGERS.json`.
- hard stop: blocco setup + messaggio di escalation
- warning: setup continua con avviso esplicito
