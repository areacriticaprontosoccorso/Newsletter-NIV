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

## Avvisi dei corsi

I corsi organizzati da Francesco Panero compaiono ogni settimana, finche' non sono passati:
in cima alla mail, in un messaggio Telegram subito dopo l'intestazione.
Si gestiscono dal file **`corsi.json`** (da GitHub: apri il file, matita, modifica,
*Commit changes*). Nessuna modifica al codice.

```json
{
  "corsi": [
    {
      "titolo": "Corso base di ecografia in emergenza-urgenza",
      "data_inizio": "2026-11-14",
      "data_fine": "2026-11-15",
      "ora": "9:00–17:00",
      "luogo": "Torino, Ospedale San Giovanni Bosco",
      "descrizione": "Due giornate con parte pratica su simulatori e modelli vivi.",
      "posti": "Massimo 20 partecipanti",
      "iscrizioni_fino": "2026-11-07",
      "link": "https://...",
      "newsletter": ["pocus", "niv"],
      "mostra_dal": "2026-10-01",
      "attivo": true
    }
  ]
}
```

- Obbligatori: `titolo` e `data_inizio` (formato `AAAA-MM-GG`). Tutto il resto e' facoltativo.
- `data_fine`: per i corsi di piu' giorni. L'avviso resta fino all'ultimo giorno incluso, poi sparisce da solo.
- `newsletter`: dove mostrarlo (`pocus`, `niv`); se manca, compare in entrambe.
- `mostra_dal`: non mostrarlo prima di quella data. `attivo: false`: sospende l'avviso senza cancellarlo.
- Al massimo **2 corsi** per uscita, i piu' vicini nel tempo.
- `immagine`: locandina del corso. Carica il file nella cartella `locandine/` (GitHub: *Add file > Upload files*) e scrivi `"immagine": "locandine/nome-file.jpg"`; in alternativa un URL `https://...`. Formati jpg, png, gif, massimo 5 MB (meglio sotto 1 MB). Compare in cima all'avviso nella mail (cliccabile se c'e' il `link`), come foto su Telegram. Se il file manca o e' troppo grande l'avviso esce senza locandina.
- Un esempio completo e' in `corsi.esempio.json`.
- Se il file ha un errore, la newsletter parte lo stesso senza avvisi e il run di GitHub Actions mostra un avviso giallo ("Controlla corsi.json"). `python corsi.py` lo controlla in locale.
