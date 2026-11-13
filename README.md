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

## Avvisi per email (errori e invii incompleti)

Alla fine di ogni run (`avviso.py`, ultimo passo del workflow) il log del run viene letto e, **solo se qualcosa è andato storto**, parte un'email a `AVVISI_EMAIL`. Se va tutto bene non arriva nulla. Conta come problema: il job fallito, le righe `ERROR` del log, e le righe `WARNING` che dicono che qualcosa non è uscito («non pubblicato», «fallito», «non programmato»...). I tentativi ripetuti («tentativo 1/3») non contano. Nell'email: le righe da guardare (senza token né indirizzi) e il link al run.

Serve il secret `AVVISI_EMAIL` (l'indirizzo che riceve gli avvisi; senza, l'avviso va all'indirizzo mittente della newsletter). Non partono nelle prove (`dry_run`, `solo_*`). Un avviso che non riesce a partire non fa mai fallire il run. `avviso.py` è una copia identica nei tre repo (EM, POCUS, NIV): se lo modifichi, modificalo in tutti e tre.

## Instagram

Il venerdì, dopo la mail, esce su Instagram **un carosello** con le schede degli articoli e la locandina del corso NIV. Le diapositive sono
JPEG 4:5 (1080x1350): le schede e le locandine stanno intere, con bande bianche ai lati. Nel testo
ci sono l'elenco degli articoli, i corsi in programma e `www.ecm.unito.it`; la didascalia rispetta i
limiti di Instagram (2200 caratteri, 30 hashtag). La locandina esce ogni settimana, a prescindere
dalla frequenza dell'avviso su Telegram e in mail.

**Schede essenziali.** Le schede di Instagram sono diverse da quelle della mail e di Facebook: solo
numero, tipo di studio, rivista e data, titolo (in italiano) e il riquadro «Perché conta» (la rilevanza;
in mancanza, la prima frase della sintesi), con il PubMed ID. I caratteri si adattano da soli alla
lunghezza del titolo. Il codice è `instagram.py` (`dati_scheda`, `html_scheda`, `genera_schede`).

**Prima diapositiva: la pagina di iscrizione.** Il carosello e il Reel aprono con una diapositiva fatta di titolo di presentazione, schermata di `index.html` (la pagina di iscrizione, ripresa dal repo: è la stessa che pubblica GitHub Pages) in una finestra di browser con l'indirizzo vero, e l'invito «Iscriviti alla newsletter · link in bio». Nel Reel dura 4 s. Titolo, sottotitolo e invito si cambiano in `config.py` (`IG_COPERTINA_TITOLO`, `IG_COPERTINA_SOTTOTITOLO`, `IG_COPERTINA_INVITO`); `IG_COPERTINA_ISCRIZIONE = False` la toglie. Se la schermata non si genera, il carosello esce senza (nel log: «prima immagine non generata»). Il codice è `genera_copertina_iscrizione` in `instagram.py`.

**Loghi in chiusura.** L'ultima diapositiva del carosello e l'ultima dei Reel (3 s; anche in coda all'estratto del podcast, in EM) è sempre `loghi/chiusura.png`, con i tre loghi (Medicina d'Emergenza-Urgenza, Pronto Soccorso Area Critica, Emergency Ultrasound School Turin). Per cambiarla basta sostituire il file (1080x1350); `IG_LOGHI` in `config.py` ne indica il percorso.

**Invito sulle locandine dei Reel.** `REEL_INVITO_LOCANDINA` e `REEL_INVITO_SOTTO` in `config.py`; vuoto = nessuna scritta. Acceso: nei Reel (e quindi anche su Facebook e X) la locandina ha in testa «Sei un medico d'emergenza-urgenza? Partecipa ai nostri corsi!» con sotto «Date, sede e iscrizioni nella newsletter»; la locandina sta intera sotto, su fondo scuro. Il carosello non cambia. Il codice è `diapositive_reel` in `instagram.py`.

**Musica.** Il Reel delle schede ha la musica se nel repo c'è `musica/sottofondo.mp3` (`IG_MUSICA`); allora in fondo alla didascalia del Reel va il credito `IG_MUSICA_CREDITO` (licenza CC BY: l'autore va citato). Senza il file il Reel resta muto e senza credito.

## Podcast (allegato alla mail)

Ogni venerdì, prima della mail, si genera il podcast della settimana: una voce, circa due minuti, come quello di EM Weekly Digest. Parte **allegato alla mail degli iscritti** come video MP4 (copertina, le schede degli articoli che scorrono mentre se ne parla, sottotitoli; in coda la locandina del corso NIV con l'invito a voce e i loghi), o come MP3 se il video supera `MAIL_MAX_MB` (15 MB). Nella mail compare la riga «Podcast».

**Controllo della voce (Gemini).** Se Gemini legge ad alta voce le note di regia (`PODCAST_GEMINI_STILE`), il blocco si rigenera senza note; se succede in tutti i tentativi, o se il parlato complessivo è troppo diverso dal copione (punteggio Whisper sotto `PODCAST_SOGLIA_MINIMA` = 0,75), la voce si scarta: NIV manda la mail senza podcast e arriva l'avviso. Prima della normalizzazione la voce passa da un filtro passa-alto e da una riduzione del rumore (`PODCAST_PULIZIA`).

- **Codice:** `podcast.py` è lo stesso file di newsletter-ps (copia identica: se lo modifichi, modificalo in entrambi). Testi e limiti sono nel blocco «PODCAST SETTIMANALE» di `config.py` (`PODCAST_INTRO`, `PODCAST_PROMPT`, `PODCAST_TITOLO`, `PODCAST_TEMA`...).
- **Passi:** copione scritto da Claude e controllato (ogni numero deve stare nell'abstract o nella sintesi), voce Gemini TTS, verifica con Whisper, MP3 e video. Le schede del video sono quelle essenziali di Instagram.
- **Secret:** `GEMINI_API_KEY` (lo stesso di newsletter-ps). Senza, o se qualcosa fallisce, la mail parte **senza** podcast e arriva l'avviso per email («Podcast non generato»). Se l'invio con l'allegato fallisce, la mail si rispedisce senza.
- **Spegnerlo:** variabile `PODCAST=0`. Non esce su Telegram né sui social.
- **Prova:** il run con `dry_run` genera il podcast senza inviare nulla; lo trovi nell'artifact, cartella `podcast/`.
- **Musica:** con `musica/podcast.mp3` nel repo, tappeto sotto la voce e credito nella riga della mail.

**Reel delle schede.** Subito dopo il carosello esce un Reel 9:16 con le stesse diapositive, una dopo
l'altra: 3 s la copertina, da 5 a 8 s ogni scheda (secondo le parole da leggere), 4 s ogni locandina.
Le diapositive stanno in un riquadro 4:5 sotto i 240 px di sopra, che l'app copre col profilo. Senza
musica: se esiste il file `IG_MUSICA` (`musica/sottofondo.mp3` nel repo), viene messo sotto, a volume
basso e con dissolvenza finale. Va scelta una traccia senza diritti d'autore e con licenza che consenta
l'uso commerciale. `IG_REEL_SCHEDE = False` in `config.py` spegne il Reel.
Il Reel si carica con l'upload «resumable» dell'API (`rupload.facebook.com`), senza indirizzi pubblici.
Non è stato provato con l'API reale (nei test è simulata): se il primo Reel non esce, nel log cerca
«Instagram: Reel non pubblicato». Se Instagram non riesce a elaborare il video (`ProcessingFailedError`), il Reel si riprova una volta con un contenitore nuovo dopo 30 s; la pubblicazione non si ripete mai, quindi niente doppioni. Il log dice in che fase è fallito (creazione, caricamento, elaborazione, pubblicazione).

**Post su X.** Dopo il Reel su Instagram e su Facebook, il Reel delle schede esce anche su X (`x_social.py`): un post con il video e un testo breve (titolo e settimana, tre hashtag, niente link: X fa pagare di più i post con link). Account unico per tutte e tre le newsletter. Servono quattro secret del repo, le chiavi dell'app X con permesso di scrittura (autenticazione OAuth 1.0a, chiavi che non scadono): `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_SECRET`. Senza, X viene saltato senza errori. X addebita ogni post sui crediti dell'app (circa 0,015 $ per un post senza link, secondo il listino del 2026: da verificare su developer.x.com); a crediti finiti il post non esce e il log riporta l'errore. `X_REEL = False` in `config.py` lo spegne; `X_HASHTAG` e `X_INVITO` cambiano hashtag e riga d'invito. Non parte con `solo_instagram`; in `dry_run` il testo finisce in `instagram/testo-x.txt`. Non provato con l'API reale (nei test è simulata): se il post non esce, nel log cerca «X: post non pubblicato».

**Prova dell'invio su Instagram.** Per provare solo Instagram, senza mail, Telegram o Facebook: Actions → il workflow → *Run workflow* → spunta **solo_instagram** (e lascia spenti gli altri). Il run fa la selezione e la sintesi come una corsa vera, poi pubblica davvero su Instagram il carosello e il Reel, con la didascalia di sempre (serve anche a recuperare un'uscita mancata; se era solo una prova, i post vanno cancellati a mano dall'app). Serve che `IG_USER_ID`, `IG_PAGE_TOKEN` e `FB_PAGE_ID` siano nei secret. Il run risulta riuscito se il carosello è uscito; se il Reel non esce, nel log compare «Instagram: Reel non pubblicato». Variabile: `SOLO_INSTAGRAM`.

Serve un account Instagram **Business o Creator collegato alla Pagina Facebook**, e tre secret del repo:
`FB_PAGE_ID`, `FB_PAGE_TOKEN` (il token deve avere i permessi `instagram_basic`,
`instagram_content_publish` e `pages_read_engagement`) e `IG_USER_ID` (l'ID dell'account Instagram).
Facoltativo: `IG_PAGE_TOKEN`, un token solo per Instagram; se c'è si usa quello e `FB_PAGE_TOKEN`
(i post Facebook) non va toccato, altrimenti Instagram usa `FB_PAGE_TOKEN`.
Senza `IG_USER_ID` non succede nulla; `IG_ABILITATO=0` lo spegne. Le diapositive passano dalla Pagina
come foto **non pubblicate** (Instagram scarica da lì l'indirizzo pubblico): nulla compare su Facebook.
Un errore Instagram non blocca mai l'invio. Con `dry_run` non si chiama nessuna API: diapositive, Reel (`reel-schede.mp4`) e didascalia finiscono nell'artefatto del run (cartella `instagram/`). Il codice sta in `instagram.py`.

