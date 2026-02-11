# Guida: quando usare Opus 4.6 vs Sonnet 4.5

**Regola pratica**: se la risposta giusta e' gia' nelle linee-guida e serve "solo" applicarla -> Sonnet. Se devi *decidere cosa fare* o *capire perche' qualcosa non funziona* -> Opus.

---

## Sonnet 4.5 - Esecuzione strutturata

| Scenario | Perche' | Esempio prompt |
|----------|---------|----------------|
| Rigenerazione piani alimentari (8 categorie) | Esecuzione procedurale: segue algoritmo definito, calcoli ripetitivi, output strutturato lungo | *"Piano Base confermato. Procedi con Fase 2: genera piano quantitativo REST. Parametri: FFM 60.08, BMR 1668, PAL 1.55. Usa distribuzioni da linee-guida e FOOD_DB dal MASTER."* |
| Compilazione piano running settimanale | Selezione workout dal bacino + assemblaggio secondo regole gia' scritte | *"Compila piano running settimana 22 (Build, mesociclo 6). Volume target 38 km. Scegli workout dal bacino storico, zone aggiornate dal test 18:26."* |
| Ricalcolo zone dopo test 5km | Applicazione formule meccaniche, zero ambiguita' | *"Test 5km completato: 17:55 (3:35/km). Ricalcola tutte le zone Z1-Z8 con le formule dalle linee-guida."* |
| Modifica singola a un piano esistente | Swap alimento, aggiustamento grammature - task chirurgico | *"Nel piano EASY RUN, sostituisci l'opzione 3 della cena (salmone) con pesce bianco. Ricalcola grammature mantenendo target pasto."* |
| Creazione scheda forza Mar/Gio | Progressioni e parametri gia' definiti nelle linee-guida | *"Genera scheda forza settimana 3 (Build). Segui progressioni AB wheel e parametri di lavoro dalle linee-guida. Attrezzatura: tappetino, AB wheel, blocchi yoga, kettlebell 12kg, manubri 5kg."* |
| Checkpoint pre-gara (template fisso) | Compilazione tabella standard con dati forniti | *"Checkpoint pre Roma-Ostia. Dati: peso 69.1 kg, BF 13.1%, FFM 60.05 kg. Test 5km 18:26. Benessere: energia 8, sonno 7, umore 8, fame 6. Compila template checkpoint dalle istruzioni."* |
| Aggiornamento FOOD_DB con nuovo alimento | Inserimento dati + ricalcolo nelle opzioni interessate | *"Aggiungi al MASTER FOOD_DB: crackers integrali Misura (valori da etichetta: 420 kcal, 11g P, 64g CHO, 14g F, 7g fibre per 100g). Poi aggiorna le opzioni spuntino che usano crackers."* |
| Generazione lista spesa settimanale | Aggregazione quantita' dai piani giornalieri | *"Genera lista spesa per la settimana: Lun EASY, Mar FORZA, Mer QUALITA', Gio FORZA, Ven PROGRESSIVO, Sab LUNGO, Dom DOMENICA. Aggrega quantita' da tutti i piani."* |

---

## Opus 4.6 - Decisioni strategiche e analisi

| Scenario | Perche' | Esempio prompt |
|----------|---------|----------------|
| Revisione/aggiornamento linee-guida | Analisi critica, identificazione incoerenze, decisioni strutturali | *"Analizza le linee-guida aggiornate. Sei soddisfatto o cambieresti qualcosa? Identifica incoerenze, ridondanze, sezioni obsolete."* |
| Pianificazione mesocicli maratona (sett 21-40) | Strategia multi-fase con trade-off volume/intensita'/recupero/deficit | *"Pianifica i mesocicli dalla settimana 21 (post Latina HM) alla settimana 52 (Maratona Latina). Integra fasi di periodizzazione, volume progressivo, e transizione nutrizionale da deficit a mantenimento."* |
| Analisi test anomalo o calo performance | Diagnosi differenziale: overtraining? deficit? biomeccanica? malattia? | *"Test 5km peggiorato di 25 secondi rispetto al precedente. Settimana scorsa: volume 42km, sonno 6/10, peso stabile. Analizza le possibili cause e proponi azioni."* |
| Decisione refeed vs continuare deficit | Valutazione segnali multipli, pesatura pro/contro | *"Peso stallo da 3 settimane (69.3-69.5 range). Performance stabili. Energia 6/10, fame 5/10, sonno 7/10. Devo fare refeed o continuare? Analizza pro e contro."* |
| Race strategy Roma-Ostia / Latina HM | Pacing plan con variabili meteo, stato forma, obiettivo, piano B | *"Roma-Ostia tra 2 settimane. Ultimo test 18:26 su 5km. Target 1:24. Crea race strategy completa: pacing per km, piano A/B, gestione meteo, nutrizione pre-gara, warm-up."* |
| Ridefinizione target maratona dopo test ottobre | Proiezione performance, analisi realismo, periodizzazione finale | *"Test Mezza Roma completato in 1:21:30. Mancano 7 settimane alla Maratona Latina. Definisci target realistico maratona, taper plan, e strategia nutrizionale race week."* |
| Conflitto tra obiettivi (peso scende ma FFM cala) | Trade-off strategico con implicazioni su multiple variabili | *"Checkpoint: peso 68.5 (-0.9 kg), ma FFM 59.8 (-0.3 kg nonostante forza 2x/sett). Performance ok. Come interpreto? Devo cambiare strategia?"* |
| Valutazione cambio di approccio dopo infortunio | Ripianificazione globale con vincoli nuovi | *"Fastidio al tendine d'Achille da 5 giorni, peggiora dopo ripetute. Come rimodulo piano running, forza e nutrizione? Devo saltare Roma-Ostia?"* |
| Analisi di fine fase con transizione | Bilancio fase completata + impostazione fase successiva | *"Fase Pre-gara HM completata. Risultati: Roma-Ostia 1:23:45, Latina HM 1:22:10. Peso 68.8, FFM 60.2. Analizza la fase e imposta la Transizione (apr-giu): obiettivi, deficit, volume, forza."* |

---

## Casi limite - dipende dal contesto

| Scenario | Se semplice -> Sonnet | Se complesso -> Opus |
|----------|----------------------|---------------------|
| Analisi workout Garmin | Lettura dati e confronto con target zone | Interpretazione pattern anomali o trend multi-settimana |
| Domanda nutrizionale | "Quante proteine nel salmone?" | "Sto perdendo FFM nonostante 2.0g/kg proteine, perche'?" |
| Modifica piano settimanale | Swap di un workout con equivalente dal bacino | Riorganizzazione settimana dopo imprevisto (malattia, viaggio, gara aggiunta) |
| Preparazione gara | Checklist pre-gara standard | Strategia gara su percorso specifico con analisi condizioni |
