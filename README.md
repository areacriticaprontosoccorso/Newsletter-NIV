# Newsletter-NIV


## Selezione: solo articoli validati

Il digest pubblica soltanto gli articoli confermati dai filtri AI (NIV e, per le
posizioni libere, medicina d'urgenza). Nessun articolo viene aggiunto per
raggiungere un numero: anche uno solo puo' essere pubblicato. Se il filtro NIV non
risponde, o se nessun articolo supera i controlli, la newsletter non viene inviata
e GitHub Actions segnala l'errore.

Test offline: `python -m unittest discover -s tests -v` (eseguiti sulle PR e prima di ogni invio).

### Chiamate API per run

Filtro NIV+EM in una sola chiamata (due stadi nello stesso prompt), sintesi di tutti
gli articoli in una sola chiamata, poi un controllo per articolo: 7 chiamate con 5
articoli. Con `INTEGRA_CON_EM = False` il filtro e' solo NIV.
