# LARN Pipeline Archive

Questa cartella contiene file e script archiviati del vecchio workflow
di mapping LARN one-by-one.

Motivo archiviazione:
- runtime core migrato su `FOOD_CATALOG` in strict mode
- mapping manuale/automatico one-by-one non piu' supportato da CLI operativa
- mantenuti solo per audit storico

Path operativo corrente:
1. `./tv food import-mapped`
2. `./tv food build-catalog`
3. `./tv food validate-data`

