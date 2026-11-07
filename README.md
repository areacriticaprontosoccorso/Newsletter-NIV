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
solo in un messaggio Telegram, subito dopo l'intestazione (non nella mail).
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
- `ogni_settimane`: frequenza dell'avviso (es. `2` = a settimane alterne; se manca, ogni settimana). L'ultima uscita prima del corso lo annuncia sempre; con `mostra_dal` le settimane si contano da quella data.
- `mostra_dal`: non mostrarlo prima di quella data. `attivo: false`: sospende l'avviso senza cancellarlo.
- Al massimo **2 corsi** per uscita, i piu' vicini nel tempo.
- `immagine`: locandina del corso. Carica il file nella cartella `locandine/` (GitHub: *Add file > Upload files*) e scrivi `"immagine": "locandine/nome-file.jpg"`; in alternativa un URL `https://...`. Formati jpg, png, gif, massimo 5 MB (meglio sotto 1 MB). Compare in cima all'avviso nella mail (cliccabile se c'e' il `link`), come foto su Telegram. Se il file manca o e' troppo grande l'avviso esce senza locandina.
- Un esempio completo e' in `corsi.esempio.json`.
- Se il file ha un errore, la newsletter parte lo stesso senza avvisi e il run di GitHub Actions mostra un avviso giallo ("Controlla corsi.json"). `python corsi.py` lo controlla in locale.

## Instagram

Il venerdì, dopo la mail, esce su Instagram **un carosello** con le schede degli articoli e la locandina del corso NIV. Le diapositive sono
JPEG 4:5 (1080x1350): le schede e le locandine stanno intere, con bande bianche ai lati. Nel testo
ci sono l'elenco degli articoli, i corsi in programma e `www.ecm.unito.it`; la didascalia rispetta i
limiti di Instagram (2200 caratteri, 30 hashtag). La locandina esce ogni settimana, a prescindere
dalla frequenza dell'avviso su Telegram e in mail.

Serve un account Instagram **Business o Creator collegato alla Pagina Facebook**, e tre secret del repo:
`FB_PAGE_ID`, `FB_PAGE_TOKEN` (il token deve avere i permessi `instagram_basic`,
`instagram_content_publish` e `pages_read_engagement`) e `IG_USER_ID` (l'ID dell'account Instagram).
Facoltativo: `IG_PAGE_TOKEN`, un token solo per Instagram; se c'è si usa quello e `FB_PAGE_TOKEN`
(i post Facebook) non va toccato, altrimenti Instagram usa `FB_PAGE_TOKEN`.
Senza `IG_USER_ID` non succede nulla; `IG_ABILITATO=0` lo spegne. Le diapositive passano dalla Pagina
come foto **non pubblicate** (Instagram scarica da lì l'indirizzo pubblico): nulla compare su Facebook.
Un errore Instagram non blocca mai l'invio. Con `dry_run` non si chiama nessuna API: le diapositive e
la didascalia finiscono nell'artefatto del run (cartella `instagram/`). Il codice sta in `instagram.py`.

