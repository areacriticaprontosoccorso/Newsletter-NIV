"""
Config NIV Weekly Digest — versione sicura per repo pubblico

Logica di selezione a due stadi:
  1. filtro NIV STRETTO  -> solo articoli davvero pertinenti al supporto ventilatorio.
     Può restituire meno di ARTICOLI_FINALI, anche zero.
  2. integrazione EM     -> le posizioni rimaste libere vengono riempite con
     articoli di medicina d'urgenza selezionati con i criteri di EM Weekly Digest
     (newsletter-ps): impatto decisionale, applicabilità, qualità metodologica,
     novità.
"""

import os

ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL    = "claude-sonnet-5"
GMAIL_USER         = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

# Modalità prova a vuoto: esegue tutta la pipeline (feed, efetch, filtro, sintesi)
# ma NON invia né email né Telegram; scrive l'HTML su file e logga la selezione.
DRY_RUN      = os.environ.get("DRY_RUN", "").strip().lower() in ("1", "true", "yes", "si")
DRY_RUN_FILE = "anteprima_digest.html"
# Prova dell'invio su Instagram: stessa selezione e sintesi di una corsa vera, ma pubblica SOLO su
# Instagram (carosello e Reel veri, didascalia normale): niente mail o Telegram.
# Attivazione: SOLO_INSTAGRAM=1. Ha effetto solo se DRY_RUN non e' attivo.
SOLO_INSTAGRAM = os.environ.get("SOLO_INSTAGRAM", "").strip().lower() in ("1", "true", "yes", "si")
IG_PREFISSO_PROVA = ""      # vuoto: la didascalia e' quella di sempre (serve a recuperare un'uscita mancata)
NCBI_TOOL          = "niv_weekly_digest_torino"

# ═══════════════════════════════════════════════════════════════════════════════
# RIVISTE
# ═══════════════════════════════════════════════════════════════════════════════
# Generaliste / area critica / medicina d'urgenza: allineate a newsletter-ps (15),
# così il bacino da cui pescare gli articoli EM sostitutivi è lo stesso.
RIVISTE = [
    {"nome": "New England Journal of Medicine", "nlmta": "N Engl J Med",       "issn": "0028-4793"},
    {"nome": "The Lancet",                      "nlmta": "Lancet",             "issn": "0140-6736"},
    {"nome": "JAMA",                            "nlmta": "JAMA",               "issn": "0098-7484"},
    {"nome": "BMJ",                             "nlmta": "BMJ",                "issn": "0959-8138"},
    {"nome": "Circulation",                     "nlmta": "Circulation",        "issn": "0009-7322"},
    {"nome": "Chest",                           "nlmta": "Chest",              "issn": "0012-3692"},
    {"nome": "Annals of Emergency Medicine",    "nlmta": "Ann Emerg Med",      "issn": "0196-0644"},
    {"nome": "Critical Care Medicine",          "nlmta": "Crit Care Med",      "issn": "0090-3493"},
    {"nome": "Intensive Care Medicine",         "nlmta": "Intensive Care Med", "issn": "0342-4642"},
    {"nome": "Resuscitation",                   "nlmta": "Resuscitation",      "issn": "0300-9572"},
    {"nome": "Academic Emergency Medicine",     "nlmta": "Acad Emerg Med",     "issn": "1069-6563"},
    {"nome": "Emergency Medicine Journal",      "nlmta": "Emerg Med J",        "issn": "1472-0205"},
    {"nome": "Stroke",                          "nlmta": "Stroke",             "issn": "0039-2499"},
    # Critical Care è solo online: se il feed torna vuoto, usare l'eISSN 1466-609X.
    {"nome": "Critical Care",                   "nlmta": "Crit Care",          "issn": "1364-8535"},
    {"nome": "Annals of Intensive Care",        "nlmta": "Ann Intensive Care", "issn": "2110-5820"},
]

# Riviste del nucleo tematico: passano dal filtro NIV stretto.
# NB: AJRCCM, ERJ e Thorax pubblicano molta pneumologia cronica, che il filtro
# scarta correttamente ma che lascia poco materiale sul supporto non invasivo in
# acuto. Le riviste di area critica respiratoria qui sotto servono a colmare
# quel vuoto. "limit" alza la finestra RSS sulle riviste ad alto volume.
RIVISTE_NIV = [
    # Prima espansione: attive subito; le successive potranno usare fase=2,3...
    {"nome": "Journal of Critical Care", "nlmta": "J Crit Care", "issn": "0883-9441", "fase": 1, "limit": 50},
    {"nome": "Respiratory Medicine", "nlmta": "Respir Med", "issn": "0954-6111", "fase": 1, "limit": 50},
    {"nome": "European Respiratory Review", "nlmta": "Eur Respir Rev", "issn": "0905-9180", "fase": 1, "limit": 50},
    # ─── Respiratorie generali ────────────────────────────────────────────────
    {"nome": "Am J Respiratory and Critical Care Medicine", "nlmta": "Am J Respir Crit Care Med", "issn": "1073-449X", "limit": 50},
    {"nome": "European Respiratory Journal",                "nlmta": "Eur Respir J",              "issn": "0903-1936", "limit": 50},
    {"nome": "Thorax",                                      "nlmta": "Thorax",                    "issn": "0040-6376"},
    # ─── Area critica respiratoria e ventilazione ─────────────────────────────
    {"nome": "Respiratory Care",                            "nlmta": "Respir Care",               "issn": "0020-1324"},
    {"nome": "Annals of the American Thoracic Society",     "nlmta": "Ann Am Thorac Soc",         "issn": "2329-6933", "limit": 50},
    {"nome": "The Lancet Respiratory Medicine",             "nlmta": "Lancet Respir Med",         "issn": "2213-2600"},
    {"nome": "Journal of Intensive Care",                   "nlmta": "J Intensive Care",          "issn": "2052-0492"},
    {"nome": "Critical Care Explorations",                  "nlmta": "Crit Care Explor",          "issn": "2639-8028"},
    {"nome": "Respirology",                                 "nlmta": "Respirology",               "issn": "1323-7799"},
    {"nome": "ERJ Open Research",                           "nlmta": "ERJ Open Res",              "issn": "2312-0541"},
    {"nome": "BMJ Open Respiratory Research",               "nlmta": "BMJ Open Respir Res",       "issn": "2052-4439"},
    # Vie aeree e preossigenazione: qui escono spesso i lavori su HFNC e NIV
    # prima dell'intubazione.
    {"nome": "British Journal of Anaesthesia",              "nlmta": "Br J Anaesth",              "issn": "0007-0912"},
    {"nome": "Anaesthesia",                                 "nlmta": "Anaesthesia",               "issn": "0003-2409"},
]

# ═══════════════════════════════════════════════════════════════════════════════
# PARAMETRI PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════
ARTICOLI_FINALI       = 5    # posizioni totali nel digest
GIORNI_RICERCA        = 7
GIORNI_RICERCA_ESTESO = 14   # fallback se la settimana è povera
FASE_RIVISTE = int(os.environ.get("FASE_RIVISTE", "1"))
PUBMED_TEMATICA = True
# Ricerca su TUTTE le riviste PubMed: scopre lavori fuori dal nucleo RSS.
PUBMED_QUERY = ('("Noninvasive Ventilation"[MeSH Terms] OR '
                '"Continuous Positive Airway Pressure"[MeSH Terms] OR '
                '"noninvasive ventilation"[Title/Abstract] OR '
                '"non-invasive ventilation"[Title/Abstract] OR '
                '"high flow nasal"[Title/Abstract] OR '
                '"high-flow nasal"[Title/Abstract] OR HFNC[Title/Abstract] OR '
                'CPAP[Title/Abstract] OR preoxygenation[Title/Abstract]) AND '
                '("acute respiratory failure"[Title/Abstract] OR '
                '"respiratory insufficiency"[MeSH Terms] OR '
                'emergency[Title/Abstract] OR "critical care"[Title/Abstract] OR '
                'extubation[Title/Abstract] OR intubation[Title/Abstract] OR '
                '"pulmonary edema"[Title/Abstract] OR exacerbation[Title/Abstract])')
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_MAX_RECORDS = 500  # superamento segnalato nel report, mai nascosto
PUBMED_PAGE_SIZE = 100
QUALITY_REPORT_FILE = "quality_report.json"
QUALITY_REPORT_MD = "quality_report.md"
MINIMO_ARTICOLI       = 1    # sotto questa soglia l'invio e' annullato; nessun riempimento per data
MAX_PER_TEMA          = 2    # max articoli sullo stesso tema clinico (parte EM)
# La newsletter è sulla ventilazione NON invasiva: la ventilazione invasiva entra
# solo quando è in continuità con essa (fallimento della NIV, preossigenazione,
# supporto dopo l'estubazione). Questo è il tetto di articoli di quel tipo.
MAX_COLLEGATI         = 2    # max articoli categoria "collegata" su ARTICOLI_FINALI
MAX_CANDIDATI_PROMPT  = 150  # tetto di candidati inviati a ogni filtro

# Integrazione con articoli di medicina d'urgenza quando mancano articoli NIV.
# False = comportamento "solo NIV": il digest esce corto.
INTEGRA_CON_EM = True

# NB: NON reintrodurre "temperature": è deprecato per questo modello (HTTP 400).
MAX_TOKENS_FILTRO          = 800
MAX_TOKENS_FILTRO_MISTO    = 1200  # due stadi in una risposta
MAX_TOKENS_SINTESI_MULTI   = 4000
MAX_TOKENS_SINTESI_SINGOLA = 800

# ═══════════════════════════════════════════════════════════════════════════════
# PRE-FILTRO DETERMINISTICO (portato da newsletter-ps)
# ═══════════════════════════════════════════════════════════════════════════════
# Il feed RSS di PubMed non espone PublicationType, ma questi tipi sono
# riconoscibili dal titolo: scartarli qui costa zero token.
ESCLUSIONI_TITOLO = [
    r"^correction\b", r"^corrigendum\b", r"^erratum\b", r"^retraction\b",
    r"^withdrawn\b", r"^expression of concern\b", r"^notice of\b",
    r"^comments? on\b", r"^reply\b", r"^in reply\b", r"^response to\b",
    r"^re:\s", r"^letter\b", r"^correspondence\b", r"^authors?'? repl",
    r"^editorial\b", r"^this month in\b", r"^highlights\b", r"^in this issue\b",
    r"^images? in\b", r"^image of\b", r"^clinical picture\b",
    r"^visual diagnosis\b", r"^obituary\b", r"^in memoriam\b",
    r"^podcast\b", r"^book review\b",
]

ABSTRACT_MIN_CHARS = 120

# Troncatura degli abstract passati al modello. Al FILTRO basta l'inizio; alla
# SINTESI serve tutto: con gli abstract completi di efetch, 2000 caratteri
# mutilavano i trial maggiori.
ABSTRACT_MAX_FILTRO  = 700
ABSTRACT_MAX_SINTESI = 6000

# ═══════════════════════════════════════════════════════════════════════════════
# E-UTILITIES efetch — abstract veri e tipi di pubblicazione
# ═══════════════════════════════════════════════════════════════════════════════
# Il feed RSS di PubMed non contiene l'abstract per una larga quota di record
# (segnaposto di 11 caratteri) né il campo PublicationType. efetch fornisce
# entrambi con una sola richiesta per lotto di PMID.
EFETCH_URL     = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
EFETCH_BATCH   = 200
EFETCH_TIMEOUT = 30
EFETCH_RETRY   = 2     # tentativi aggiuntivi prima di degradare sulla description RSS
NCBI_EMAIL     = ""    # opzionale: NCBI chiede un contatto per usi automatizzati

# PublicationType da escludere: etichette ufficiali PubMed, esatte e non euristiche.
# "Review" e "Practice Guideline" NON sono qui: revisioni sistematiche e linee guida
# sono fra i contenuti più utili del digest.
PUBTYPE_ESCLUSI = {
    "Letter", "Comment", "Editorial", "Published Erratum", "Retraction of Publication",
    "Retracted Publication", "Expression of Concern", "Case Reports", "News",
    "Newspaper Article", "Biography", "Historical Article", "Portrait", "Interview",
    "Congress", "Video-Audio Media", "Address", "Autobiography", "Bibliography",
    "Personal Narrative", "Introductory Journal Article", "Patient Education Handout",
}

# Sintesi di letteratura senza dati primari: su questi il badge "revisione" viene
# imposto in codice. "Meta-Analysis" è escluso di proposito, perché produce stime
# quantitative proprie e può legittimamente essere "cambia-pratica".
PUBTYPE_REVISIONE = {
    "Review", "Systematic Review", "Scoping Review", "Practice Guideline",
    "Guideline", "Consensus Development Conference",
    "Consensus Development Conference, NIH",
}

# Classificazione dell'articolo -> badge nell'email. Le chiavi sono i soli valori
# accettati dal parser: qualunque altro valore viene scartato.
TIPI_ARTICOLO = {
    "cambia-pratica": {"label": "Cambia la pratica", "colore": "#c41e3a"},
    "conferma":       {"label": "Conferma",          "colore": "#4a7c59"},
    "controverso":    {"label": "Controverso",       "colore": "#b8860b"},
    "esplorativo":    {"label": "Esplorativo",       "colore": "#6b7a8f"},
    "revisione":      {"label": "Revisione",         "colore": "#6f5b8e"},
}

# Frase fissa richiesta al modello quando l'abstract non permette di giudicare:
# essendo fissa, in build_html si può decidere di non stampare la riga.
LIMITE_NON_DESUMIBILE = "Limiti non desumibili dall'abstract."

# ═══════════════════════════════════════════════════════════════════════════════
# BRANDING
# ═══════════════════════════════════════════════════════════════════════════════
NOME_NEWSLETTER     = "NIV Weekly Digest"
NOME_SERVIZIO       = "Area Critica e Pronto Soccorso · San Giovanni Bosco · Torino"
COLOR_ACCENT        = "#2e7d32"   # verde: articoli NIV
COLOR_EM            = "#c41e3a"   # rosso EM Weekly Digest: articoli sostitutivi
COLOR_DARK          = "#1a2a1e"
NEWSLETTER_PAGE_URL = "https://areacriticaprontosoccorso.github.io/Newsletter-NIV/"

BASE_URL_LOGHI  = "https://raw.githubusercontent.com/areacriticaprontosoccorso/Newsletter-NIV/main/"
# Loghi nell'intestazione della mail, affiancati da sinistra a destra.
LOGHI = [
    {"url": BASE_URL_LOGHI + "logo-medicina-urgenza.png",
     "alt": "Medicina d'Emergenza-Urgenza - Pronto Soccorso e Area Critica, Ospedale San Giovanni Bosco"},
]
LOGO_ALTEZZA    = 100   # px
LOGO_URL        = LOGHI[0]["url"]   # compatibilita'
# Schede degli articoli (immagini PNG, una per articolo): servono al carosello Instagram.
IMG_DIR        = "immagini"
IMG_LARGHEZZA  = 720   # px CSS della scheda
IMG_SCALA      = 2     # device scale factor: 2 = testo nitido
IMG_TIMEOUT_MS = 30000

# Facebook: qui serve solo per caricare le diapositive di Instagram (foto NON pubblicate sulla
# Pagina, di cui Instagram scarica l'indirizzo pubblico). Stessa Pagina di EM e POCUS.
FB_API_VERSION = "v21.0"
FB_PAGE_ID     = os.environ.get("FB_PAGE_ID", "")
FB_PAGE_TOKEN  = os.environ.get("FB_PAGE_TOKEN", "")

# Instagram: un carosello a ogni uscita (schede degli articoli e locandina del corso NIV).
# Attivo solo con IG_USER_ID (ID dell'account Instagram Business collegato alla Pagina) e con
# FB_PAGE_ID / FB_PAGE_TOKEN; senza, non fa nulla. IG_ABILITATO=0 lo spegne.
IG_ABILITATO    = os.environ.get("IG_ABILITATO", "1").strip().lower() not in ("0", "false", "no")
IG_USER_ID      = os.environ.get("IG_USER_ID", "").strip()

# X (ex Twitter): un post con il Reel delle schede e un testo breve (x_social.py). Servono le quattro chiavi
# dell'app X, come secret del repo; senza, X viene saltato. X_REEL = False lo spegne. X addebita ogni post
# sui crediti dell'app. X_HASHTAG / X_INVITO: hashtag e riga d'invito (se vuoti: i primi tre di IG_HASHTAG, nessun invito).
X_REEL          = True
X_API_KEY       = os.environ.get("X_API_KEY", "").strip()
X_API_SECRET    = os.environ.get("X_API_SECRET", "").strip()
X_ACCESS_TOKEN  = os.environ.get("X_ACCESS_TOKEN", "").strip()
X_ACCESS_SECRET = os.environ.get("X_ACCESS_SECRET", "").strip()
X_HASHTAG       = ""
X_INVITO        = ""
# Token della Pagina usato solo da Instagram: se manca si usa FB_PAGE_TOKEN (che resta dei post Facebook).
IG_PAGE_TOKEN   = os.environ.get("IG_PAGE_TOKEN", "").strip()
IG_DIR          = "instagram"
IG_INTESTAZIONE = "NIV Weekly Digest — Settimana {settimana}/{anno}\nGli articoli più rilevanti sulla ventilazione non invasiva e sull'insufficienza respiratoria acuta."
IG_CHIUSURA     = "Sintesi generate con supporto di intelligenza artificiale: verifica sempre la fonte originale. Iscrizione alla newsletter dal link in bio."
# Reel: stesse diapositive del carosello, una dopo l'altra (IG_REEL_SCHEDE=False lo spegne). Senza
# musica; se esiste il file IG_MUSICA (senza diritti d'autore: va controllata la licenza) viene
# messo sotto le schede.
IG_REEL_SCHEDE  = True
IG_MUSICA       = "musica/sottofondo.mp3"
# Credito della musica dei Reel, in fondo alla didascalia (solo se il file IG_MUSICA esiste).
IG_MUSICA_CREDITO = "Musica: «Soft Corporate» di Yuri Megis (CC BY 4.0, freemusicarchive.org)"
# Invito scritto in testa alle locandine dei corsi nei Reel (Instagram, Facebook, X); il carosello non cambia.
# Vuoto = nessuna scritta. Sotto l'invito: REEL_INVITO_SOTTO.
REEL_INVITO_LOCANDINA = "Sei un medico d'emergenza-urgenza? Partecipa ai nostri corsi!"
REEL_INVITO_SOTTO     = "Date, sede e iscrizioni nella newsletter"
# Diapositiva con i tre loghi: sempre l'ultima del carosello e dei Reel (se il file esiste).
IG_LOGHI        = "loghi/chiusura.png"
# Prima diapositiva del carosello e del Reel: la schermata della pagina di iscrizione (index.html)
# con titolo di presentazione e invito a iscriversi. IG_COPERTINA_ISCRIZIONE=False la toglie.
IG_COPERTINA_ISCRIZIONE = True
IG_COPERTINA_TITOLO = "NIV Weekly Digest"
IG_COPERTINA_SOTTOTITOLO = "La newsletter settimanale sulla ventilazione non invasiva e sull'insufficienza respiratoria acuta"
IG_COPERTINA_INVITO = "Iscriviti alla newsletter"
IG_HASHTAG      = "#NIV #VentilazioneNonInvasiva #MedicinaDUrgenza #AreaCritica #ProntoSoccorso #FOAMed"

# Base pubblica dei file del repo (locandine dei corsi): https://.../main/<percorso>
URL_RAW_REPO = "https://raw.githubusercontent.com/areacriticaprontosoccorso/Newsletter-NIV/main/"

# ═══════════════════════════════════════════════════════════════════════════════
# PODCAST SETTIMANALE (podcast.py, lo stesso file di newsletter-ps)
# ═══════════════════════════════════════════════════════════════════════════════
# Il podcast (video MP4 con le schede e la voce, o in ripiego l'MP3) si genera prima della mail e
# parte ALLEGATO alla mail degli iscritti. Mai bloccante: se manca, la mail esce senza.
# Serve il secret GEMINI_API_KEY. PODCAST=0 (variabile d'ambiente) lo spegne.
DIR_BASE = os.path.dirname(os.path.abspath(__file__))
PODCAST_ABILITATO  = os.environ.get("PODCAST", "1").strip().lower() not in ("0", "false", "no")
PODCAST_DIR        = "podcast"
PODCAST_ARCHIVIO   = os.path.join(PODCAST_DIR, "digest.json")     # articoli e schede per podcast.py
PODCAST_ESITO      = os.path.join(PODCAST_DIR, "esito.json")
# Il podcast si genera dentro la newsletter, prima della mail, e l'MP3 parte allegato.
# Oltre PODCAST_TIMEOUT_MAIL secondi il processo viene chiuso e la mail esce senza.
PODCAST_TIMEOUT_MAIL = 25 * 60
# Cosa allegare alla mail, in ordine: il video (MP4, ~4 MB, audio + schede) e, se
# l'invio col video fallisce, l'MP3 (~2 MB). Nessuno dei due se gli allegati
# supererebbero MAIL_MAX_MB (Gmail accetta 25 MB; molte caselle aziendali meno).
PODCAST_MAIL_ALLEGATI = ["mp4", "mp3"]
MAIL_MAX_MB           = 15
# Il workflow passa l'esito del passo che installa torch/chatterbox: se è fallito
# non si perde tempo a tentare. In locale (variabile assente) si tenta.
PODCAST_DIPENDENZE_OK = os.environ.get("PODCAST_DIPENDENZE", "success").strip() in ("success", "")
# Motore della voce: "gemini" (Gemini TTS, API di Google: voci italiane native, serve
# il secret GEMINI_API_KEY) oppure "chatterbox" (modello locale sul runner, imita
# podcast_voce.wav; richiede torch e chatterbox nel passo delle dipendenze).
PODCAST_MOTORE = os.environ.get("PODCAST_MOTORE", "gemini").strip().lower()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# Se Gemini non risponde (quota, chiave, blocchi) il podcast si rifà con Chatterbox
# sul runner: stesso copione, nessuna chiamata API in più, ma 20-30 minuti e voce
# meno italiana. "0" nella variabile di repository PODCAST_RIPIEGO lo disattiva.
PODCAST_RIPIEGO_CHATTERBOX = False     # in NIV il ripiego locale non e' installato: senza Gemini niente podcast
# Modelli provati in ordine: se uno non esiste (404) si passa al successivo.
PODCAST_GEMINI_MODELLI = ["gemini-3.8-flash-tts", "gemini-3.1-flash-tts-preview",
                          "gemini-2.5-flash-preview-tts", "gemini-2.5-pro-preview-tts"]
PODCAST_GEMINI_VOCE    = "Charon"     # voce predefinita di Gemini (informativa, maschile)
# Parole per chiamata: nelle letture oltre il minuto il modello cambia timbro verso la
# fine, quindi il podcast si genera in blocchi di sezioni intere (~40 s ciascuno).
PODCAST_GEMINI_PAROLE_BLOCCO = 100
# Fra una chiamata e l'altra il timbro cambia un po': lo spettro medio di ogni blocco
# viene portato su quello del primo (correzione massima in dB) e il volume pareggiato.
PODCAST_GEMINI_UNIFORMA = True
PODCAST_GEMINI_EQ_MAX_DB = 4
# Note di regia: vanno nella sezione "NOTE DI REGIA" del prompt, separate dalla
# "TRASCRIZIONE" (se scritte come frase prima del testo, il modello le legge ad alta voce).
PODCAST_GEMINI_STILE = ("Leggi in italiano, come un medico d'urgenza che presenta ai colleghi "
                        "la rassegna settimanale della letteratura: tono professionale, caldo "
                        "e naturale, ritmo sostenuto ma ben scandito, senza enfasi. Stessa voce, "
                        "stesso timbro e stesso ritmo dall'inizio alla fine. Breve pausa "
                        "fra un paragrafo e l'altro. Nomi delle riviste e termini inglesi in "
                        "pronuncia inglese.")
PODCAST_VOCE_RIF   = "podcast_voce.wav"   # campione di voce (sintetica) da imitare

PODCAST_INTRO = ("Benvenuti! Questa è la newsletter settimanale sulla ventilazione non invasiva "
                 "della Medicina d'Emergenza-Urgenza dell'ospedale San Giovanni Bosco di Torino. "
                 "{Articoli} articoli, due minuti, ventilazione non invasiva e insufficienza "
                 "respiratoria. Buon ascolto!")
# Titolo e tema sulla copertina del video; servizio di corsi.json per le locandine in coda.
PODCAST_TITOLO = "NIV Weekly Digest"
PODCAST_TEMA   = "ventilazione non invasiva e insufficienza respiratoria"
PODCAST_CORSI  = "niv"
# Chiusura parlata: avvertenza, (se ci sono corsi in programma) l'invito ai corsi, saluti.
# L'invito compare anche scritto sulle locandine, che appaiono mentre lo si dice.
PODCAST_CHIUSURA_AVVISO = ("Sintesi generate con l'intelligenza artificiale: verificate sempre sulle "
                           "fonti. Le sintesi complete e i link agli articoli sono nella newsletter.")
PODCAST_CHIUSURA_CORSI = "Sei un medico d'emergenza-urgenza? Partecipa ai nostri corsi!"
PODCAST_CHIUSURA_SALUTI = "Alla prossima."
PODCAST_CHIUSURA = PODCAST_CHIUSURA_AVVISO + " " + PODCAST_CHIUSURA_SALUTI      # senza corsi

# Carattere della voce Chatterbox: valori più bassi = intonazione più calma e meno
# enfatica. 0,35 / 0,3 scelti all'ascolto il 30/10 (prima: 0,5 / 0,5).
PODCAST_ESAGERAZIONE = 0.35
PODCAST_CFG          = 0.3

# Durata: se il parlato supera PODCAST_DURATA_MAX secondi si accelera fino a
# PODCAST_ATEMPO_MAX (oltre, la voce si snatura: si pubblica comunque, con avviso).
PODCAST_DURATA_MAX = 140   # 2 minuti e 20 secondi, concessi dal 2/11 (sigla e avvertenza comprese)
PODCAST_ATEMPO_MAX = 1.10
# Parole del copione per TUTTI gli articoli insieme (intro e chiusura escluse),
# riferite a un digest di ARTICOLI_FINALI articoli: con meno articoli i limiti
# scalano in proporzione. Misurato sul run del 30/10: 235 parole + intro = 124 s anche
# a velocità 1,10, quindi il tetto è sceso a 220 (circa 120 s).
# In PODCAST_INTRO, {Articoli} diventa il numero in lettere ("Cinque", "Quattro"...).
# Dal 2/11 il podcast ha apertura, avvertenza e sigla e può durare fino a 2'20".
PODCAST_PAROLE_MIN = 175
# Loghi in coda al video, in silenzio: secondi. La voce di chiusura corre sulle locandine dei corsi (POCUS e NIV).
PODCAST_LOCANDINA_SEC = 5
# Diapositiva con i tre loghi: sempre l'ultima del video del podcast (PODCAST_LOCANDINA_SEC secondi).
PODCAST_LOGHI = "loghi/chiusura.png"
PODCAST_PAROLE_MAX = 210
# Frase d'apertura scritta da Claude ("Questa settimana: ..."), inserita prima di "Buon ascolto".
PODCAST_APERTURA_MAX_PAROLE = 16
# Sottotitoli nel video (testo del copione con i tempi delle parole di Whisper) e sigla.
PODCAST_SOTTOTITOLI = True
# Tappeto musicale sotto la voce del podcast (solo se il file esiste), PODCAST_MUSICA_DB LU sotto la voce.
PODCAST_MUSICA = "musica/podcast.mp3"
PODCAST_MUSICA_DB = -24
PODCAST_MUSICA_CREDITO = "Musica: «The Distant Sun» di Scott Buckley (CC BY 4.0, www.scottbuckley.com.au)"   # riga in fondo alla mail
PODCAST_SIGLA = True
PODCAST_SIGLA_DB = -6      # loudness della sigla rispetto alla voce (LUFS): resta sotto, senza sparire

# Verifica della voce: ogni frase viene ritrascritta con Whisper e confrontata
# col testo; sotto soglia si rigenera (fino a PODCAST_TENTATIVI volte, si tiene
# la migliore).
PODCAST_SOGLIA_WHISPER = 0.82
PODCAST_TENTATIVI      = 3
# Sotto questo punteggio complessivo (o se Gemini legge le note di regia) la voce si scarta:
# EM passa alla voce di riserva, NIV manda la mail senza podcast (con avviso).
PODCAST_SOGLIA_MINIMA  = 0.75
# Pulizia della voce prima della normalizzazione (filtro passa-alto e riduzione del rumore).
PODCAST_PULIZIA        = True
PODCAST_WHISPER_MODELLO = os.environ.get("PODCAST_WHISPER", "small")

# Pronuncia: sostituzioni applicate SOLO al testo dato alla sintesi vocale.
PODCAST_PRONUNCIA_IT = {
    "Emergenza-Urgenza": "Emergenza  Urgenza",   # col trattino "Urgenza" si fonde
    "emergenza-urgenza": "emergenza  urgenza",
    "EM": "I-em",
    "NIV": "Niv",
    "PS": "Pronto Soccorso",
    "OBI": "o-bi-i",
    "ASL": "a-esse-elle",
}
# Parole inglesi brevi dentro una frase italiana: invece di un segmento in voce
# inglese (che spezzerebbe il ritmo) si usa questa grafia fonetica.
PODCAST_GRAFIA_FONETICA = {
    "trial": "tràial",
    "cluster": "clàster",
    "stepped-wedge": "stèpd-uèdg",
    "outcome": "àutcam",
    "endpoint": "èndpoint",
    "score": "scòr",
    "follow-up": "follou-àp",
    "setting": "sètting",
    "timing": "tàiming",
}

PODCAST_PROMPT = """Scrivi il copione parlato del podcast settimanale di un Pronto Soccorso sulla ventilazione \
non invasiva e l'insufficienza respiratoria: una sola voce, in italiano, tono tecnico ma \
colloquiale, per medici d'urgenza. Presenta i \
{n} articoli qui sotto, nell'ordine dato. Saluto iniziale, avvertenza e congedo li aggiunge \
il programma: tu scrivi l'APERTURA e i paragrafi degli articoli.

REGOLE
1. LUNGHEZZA, il vincolo più importante: il podcast dura poco più di due minuti, quindi devi \
scegliere, non riassumere tutto. Un paragrafo per articolo, da {per_min} a {per_max} \
parole ciascuno, MAI di più (3 o 4 frasi brevi). Tutti i paragrafi insieme: fra \
{min_parole} e {max_parole} parole. Conta le parole prima di rispondere.
2. APERTURA: una sola frase, al massimo {max_apertura} parole, che comincia con \
"Questa settimana" e annuncia il tema più importante (di solito il primo articolo). \
Nessun numero.
3. Apri ogni paragrafo con un connettivo d'ordine e la rivista, per esempio: \
"Si parte da [[Circulation]], ...", "Secondo studio, su ...", "Terzo, su ...", \
"Quarto, ancora su ...", "Infine, una metanalisi su ...".
4. Ogni paragrafo, in quest'ordine: il disegno dello studio in poche parole; UN \
risultato principale, con il suo confronto ("X% contro Y%", mai un valore isolato); \
il peso dell'evidenza detto a parole, partendo dal campo "badge" (per esempio "cambia \
la pratica", "da confermare", "studio esplorativo"), oppure il limite principale. Ometti \
intervalli di confidenza, \
valori p, analisi secondarie e dettagli di metodo. Scrivi i termini medici italiani per \
esteso e nella forma corretta ("ritorno della circolazione spontanea", non "circolo \
spontaneo").
5. NUMERI: usa SOLO numeri presenti nell'abstract o nella sintesi di QUELL'articolo, \
scritti in cifre (decimali con la virgola, migliaia col punto: 60.000; percentuali col \
simbolo %). Puoi arrotondare solo premettendo "circa". NON calcolare numeri nuovi: \
niente differenze, conversioni, rapporti o percentuali derivate.
6. TERMINI INGLESI: racchiudi fra doppie parentesi quadre OGNI nome di rivista, nome o \
acronimo di studio e termine tecnico inglese: [[Critical Care Medicine]], \
[[point-of-care]], [[odds]], [[trial]]. Se la pronuncia inglese non si deduce dalla \
grafia, aggiungi dopo una barra verticale come si legge: [[ICare-FASTER|Eye-Care Faster]], \
[[ARDS|A R D S]]. Usa la parola italiana quando esiste ed è d'uso comune \
(rianimazione, ventilazione non invasiva, esito).
7. Frasi brevi, adatte all'ascolto: al massimo 30 parole per frase. Niente parentesi, \
elenchi, virgolette doppie o abbreviazioni da leggere (scrivi "intervallo di \
confidenza", non "IC"). Le sigle italiane d'uso comune (PS, NIV, TC) vanno bene.
8. Non aggiungere nulla che non sia negli abstract o nelle sintesi.

Rispondi SOLO con un array JSON: per primo l'oggetto dell'apertura, poi un oggetto per \
articolo nello stesso ordine:
[{{"pmid": "apertura", "testo": "Questa settimana ..."}}, {{"pmid": "...", "testo": "..."}}]

ARTICOLI
{blocchi}"""


LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "newsletter_niv.log")

# ═══════════════════════════════════════════════════════════════════════════════
# CONTESTO E SYSTEM PROMPT
# ═══════════════════════════════════════════════════════════════════════════════
CONTESTO_PS = """CONTESTO DEL LETTORE:
- Pronto Soccorso generale per adulti di ospedale urbano, Torino, Italia.
- Annesse Osservazione Breve Intensiva e Area Critica/shock room.
- Casistica: indifferenziata, prevalenza di patologia medica acuta,
  quota rilevante di anziani fragili e pluripatologici.
- Sistema sanitario pubblico italiano: privilegia interventi con farmaci
  in commercio in Italia e risorse realisticamente disponibili."""

SYSTEM_FILTRO_NIV = """Sei un medico di Area Critica e Pronto Soccorso italiano, esperto
di insufficienza respiratoria acuta e di ventilazione NON invasiva. Selezioni la
letteratura settimanale sul supporto respiratorio non invasivo per i colleghi del tuo
reparto. Sei severo: preferisci una selezione corta e centrata a una lunga e annacquata,
e non lasci che la newsletter scivoli sulla ventilazione invasiva in terapia intensiva.

""" + CONTESTO_PS

SYSTEM_FILTRO_EM = """Sei un medico strutturato di Pronto Soccorso italiano con esperienza
in medicina d'urgenza e cure critiche. Selezioni la letteratura settimanale per i
colleghi del tuo reparto.

""" + CONTESTO_PS

# ═══════════════════════════════════════════════════════════════════════════════
# STADIO 1 — FILTRO NIV STRETTO
# ═══════════════════════════════════════════════════════════════════════════════
# Differenza chiave rispetto alla versione precedente: NON è consentito
# "riempire" con articoli genericamente respiratori. Se non c'è nulla di
# pertinente, la risposta corretta è un array vuoto.
PROMPT_FILTRO_NIV = """COMPITO: dalla lista di articoli candidati, seleziona AL MASSIMO {n}
articoli pertinenti al supporto respiratorio NON INVASIVO nel paziente acuto.
Puoi restituirne meno di {n}, e anche nessuno.

La newsletter è dedicata alla ventilazione NON invasiva. La ventilazione invasiva
non è il suo argomento: entra solo quando è in continuità diretta con la gestione
non invasiva. Classifica quindi ogni articolo che selezioni in una di due categorie.

CATEGORIA "non-invasiva" — il nucleo della newsletter, da privilegiare sempre.
L'oggetto dello studio è:
- ventilazione non invasiva (NIV, BiPAP, bilevel), CPAP, casco, maschere e interfacce;
- ossigenoterapia ad alti flussi (HFNC), ossigenoterapia convenzionale e target
  di ossigenazione;
- insufficienza respiratoria acuta ipossiemica o ipercapnica trattata senza intubazione;
- edema polmonare acuto cardiogeno trattato con supporto non invasivo;
- riacutizzazione di BPCO, asma acuto grave, polmonite con insufficienza respiratoria,
  quando lo studio riguarda il supporto non invasivo o l'outcome respiratorio;
- posizione prona da sveglio, monitoraggio respiratorio non invasivo, emogasanalisi,
  drive respiratorio e P-SILI nel paziente in respiro spontaneo;
- criteri e indici di fallimento della NIV o dell'HFNC, timing dell'intubazione.

CATEGORIA "collegata" — ammessa, ma con parsimonia. L'articolo riguarda la
ventilazione invasiva ED è in continuità diretta con la gestione non invasiva:
- preossigenazione e intubazione dopo fallimento del supporto non invasivo;
- estubazione e supporto non invasivo profilattico dopo l'estubazione;
- confronto diretto fra strategia invasiva e non invasiva.

NON è pertinente e va ESCLUSO, anche se contiene la parola "respiratorio" o
"ventilazione":
- gestione della ventilazione invasiva durante la degenza in terapia intensiva:
  strategie di ventilazione protettiva, PEEP, reclutamento, weaning prolungato,
  tracheostomia, sedazione e curarizzazione del paziente intubato;
- ARDS trattata con ventilazione invasiva, quando il supporto non invasivo non è
  in questione;
- pneumologia cronica ambulatoriale (asma stabile, BPCO stabile, OSAS elettiva,
  fibrosi, riabilitazione respiratoria, cessazione del fumo);
- epidemiologia o prevenzione delle infezioni respiratorie senza dati sul supporto
  ventilatorio;
- studi in cui la ventilazione compare solo come variabile di aggiustamento o come
  endpoint secondario marginale;
- case report, case series, lettere, editoriali, commenti, errata.

SOGLIA: nel dubbio, ESCLUDI. È preferibile un digest di 2 articoli davvero sulla
ventilazione non invasiva che uno di 5 in cui 3 riguardano il paziente intubato in
terapia intensiva. Non usare la categoria "collegata" per fare entrare articoli di
terapia intensiva che non hanno un legame reale con il supporto non invasivo.

ARTICOLI CANDIDATI:
{articoli}

FORMATO DI RISPOSTA - restituisci SOLO un array JSON valido, senza testo prima o dopo,
senza blocchi markdown. Scegli esclusivamente PMID presenti nella lista qui sopra:
non inventare né modificare PMID. Se nessun articolo è pertinente restituisci
esattamente: []
Nei valori testuali NON usare mai virgolette doppie: per citare un nome, un termine o una frase usa gli apici singoli ('...') oppure le caporali «...». Una virgoletta doppia dentro il testo rompe il formato JSON.

[
  {{"pmid": "12345678", "tema": "HFNC", "categoria": "non-invasiva", "perche": "motivo in max 15 parole"}},
  {{"pmid": "23456789", "tema": "intubazione", "categoria": "collegata", "perche": "..."}}
]

Ordina dal più rilevante al meno rilevante, mettendo per primi gli articoli di
categoria "non-invasiva"."""

# ═══════════════════════════════════════════════════════════════════════════════
# STADIO 2 — FILTRO EM (criteri di newsletter-ps)
# ═══════════════════════════════════════════════════════════════════════════════
PROMPT_FILTRO_EM = """COMPITO: dalla lista di articoli candidati, seleziona al massimo {n} articoli,
quelli con il maggior impatto sulla pratica clinica quotidiana in Pronto Soccorso,
Medicina d'Urgenza e Terapia Intensiva.

CRITERI DI SELEZIONE, in ordine di priorità decrescente:
1. IMPATTO DECISIONALE - l'articolo può modificare una decisione presa in PS nelle
   prime ore: triage, scelta diagnostica, terapia, destinazione del paziente.
2. APPLICABILITA' - l'intervento è realizzabile nel contesto descritto sopra.
   Scarta studi su farmaci non disponibili in Italia o su risorse assenti.
3. QUALITA' METODOLOGICA - trial randomizzati, meta-analisi e revisioni sistematiche
   prima di studi osservazionali; numerosità adeguata; endpoint clinici anziché surrogati.
4. NOVITA' - a parità di tutto il resto, preferisci ciò che cambia o ribalta una
   pratica consolidata rispetto a ciò che conferma quanto già noto.

VINCOLI DI COMPOSIZIONE:
- Massimo 2 articoli sullo stesso tema clinico (es. non 3 studi sulla sepsi).
- Massimo 2 articoli dalla stessa rivista.
- Preferisci una selezione che copra aree cliniche diverse.

ESCLUDI:
- Case report e case series.
- Studi puramente organizzativi su sistemi sanitari non europei.
- Ricerca di base o preclinica senza ricaduta clinica immediata.
- Cardiologia interventistica elettiva, chirurgia elettiva, oncologia ambulatoriale.

IMPORTANTE: se meno di {n} articoli soddisfano davvero questi criteri, restituiscine
di meno. Non completare la lista con articoli mediocri: una selezione di 3 articoli
solidi è preferibile a 5 di cui 2 irrilevanti.

ARTICOLI CANDIDATI:
{articoli}

FORMATO DI RISPOSTA - restituisci SOLO un array JSON valido, senza testo prima o dopo,
senza blocchi markdown. Scegli esclusivamente PMID presenti nella lista qui sopra:
non inventare né modificare PMID.
Nei valori testuali NON usare mai virgolette doppie: per citare un nome, un termine o una frase usa gli apici singoli ('...') oppure le caporali «...». Una virgoletta doppia dentro il testo rompe il formato JSON.

[
  {{"pmid": "12345678", "tema": "sepsi", "perche": "motivo in max 15 parole"}}
]

Ordina dal più rilevante al meno rilevante."""

# ═══════════════════════════════════════════════════════════════════════════════
# FILTRO MISTO — stadi NIV ed EM in UNA sola chiamata
# ═══════════════════════════════════════════════════════════════════════════════
# Costruito dai due prompt sopra, per non far divergere i criteri: la parte prima di
# "ARTICOLI CANDIDATI:" di ciascuno resta identica.
_TESTA_NIV = PROMPT_FILTRO_NIV.split("ARTICOLI CANDIDATI:")[0].rstrip()
_TESTA_EM = PROMPT_FILTRO_EM.split("ARTICOLI CANDIDATI:")[0].rstrip().replace("{n}", "R")

SYSTEM_FILTRO_MISTO = """Sei un medico strutturato di Area Critica e Pronto Soccorso italiano,
esperto di insufficienza respiratoria acuta, di ventilazione NON invasiva e di
medicina d'urgenza. Selezioni la letteratura settimanale per i colleghi del tuo
reparto. Sei severo: preferisci una selezione corta e centrata a una lunga e
annacquata, e non lasci che la newsletter scivoli sulla ventilazione invasiva in
terapia intensiva.

""" + CONTESTO_PS

PROMPT_FILTRO_MISTO = """Il compito ha DUE STADI, da eseguire in sequenza sulla STESSA lista di articoli.
Lo STADIO A ha la precedenza: lo STADIO B serve solo a riempire le posizioni che
l'STADIO A lascia libere.

=== STADIO A — SUPPORTO RESPIRATORIO NON INVASIVO (al massimo {n} articoli) ===
""" + _TESTA_NIV + """

=== STADIO B — MEDICINA D'URGENZA ===
Sia R = {n} meno il numero di articoli selezionati nello STADIO A. Se R è zero,
salta lo STADIO B. Nello STADIO B considera SOLO articoli NON selezionati nello
STADIO A; non puoi riproporre un articolo dello STADIO A.
""" + _TESTA_EM + """

ARTICOLI CANDIDATI:
{articoli}

FORMATO DI RISPOSTA - restituisci SOLO un array JSON valido, senza testo prima o dopo,
senza blocchi markdown. Scegli esclusivamente PMID presenti nella lista qui sopra:
non inventare né modificare PMID. Se nessun articolo è pertinente restituisci
esattamente: []
Ogni oggetto porta il campo "stadio" ("A" oppure "B"). Il campo "categoria"
("non-invasiva" o "collegata") serve solo per lo STADIO A. Gli articoli dello
STADIO A vengono prima, ordinati dal più rilevante, con "non-invasiva" davanti a
"collegata"; poi quelli dello STADIO B, dal più rilevante.
Nei valori testuali NON usare mai virgolette doppie: per citare un nome, un termine o una frase usa gli apici singoli ('...') oppure le caporali «...». Una virgoletta doppia dentro il testo rompe il formato JSON.

[
  {{"pmid": "12345678", "stadio": "A", "tema": "HFNC", "categoria": "non-invasiva", "perche": "motivo in max 15 parole"}},
  {{"pmid": "23456789", "stadio": "B", "tema": "sepsi", "perche": "motivo in max 15 parole"}}
]"""

# ═══════════════════════════════════════════════════════════════════════════════
# SINTESI
# ═══════════════════════════════════════════════════════════════════════════════
REGOLE_COMUNI = """REGOLE DI TRADUZIONE (obbligatorie):
- ORTOGRAFIA: usa gli accenti italiani corretti (è, à, ì, ò, ù, é). Non sostituirli
  mai con l'apostrofo: si scrive "qualità", non "qualita'"; "è", non "e'";
  "più", non "piu'"; "perché", non "perche'".
- ORTOGRAFIA DI TERMINI RICORRENTI, spesso storpiati: si scrive "preospedaliero"
  (non "preistospedaliero" né "prestospedaliero"), "intraospedaliero",
  "extraospedaliero", "endotracheale", "emogasanalisi", "ipercapnico".
- Traduci il SIGNIFICATO clinico, mai parola per parola. Vietati i calchi dall'inglese.
- Evita i falsi amici: "severe"=grave (non "severo"); "evidence"=prove/evidenze
  (non "evidenza"); "eventually"=infine; "actual"=effettivo/reale (non "attuale");
  "consistent"=coerente/costante (non "consistente"); "to require"=necessitare;
  "rate"=tasso; "compliance"=aderenza (ma "lung compliance"=compliance polmonare,
  termine tecnico che resta); "management"=gestione; "care"=assistenza/cure;
  "mortality"=mortalità; "morbidity"=morbilità.
- Terminologia respiratoria italiana corrente: "weaning"=svezzamento dal ventilatore,
  "airway"=vie aeree, "breathing effort"=sforzo respiratorio, "work of breathing"=
  lavoro respiratorio, "tidal volume"=volume corrente, "driving pressure"=pressione
  di distensione, "awake prone positioning"=posizione prona da sveglio.
- Lascia in inglese SOLO i termini realmente in uso in clinica italiana: NIV, CPAP,
  HFNC, ARDS, PEEP, P/F, shock, outcome, endpoint, follow-up, weaning, setting,
  cut-off, bias, propensity score; usa "basale" per baseline.
- Lessico dei trial: "arm"=braccio; "blinded"=in cieco; "open-label"=in aperto;
  "primary/secondary endpoint"=endpoint primario/secondario; "number needed to
  treat"=NNT; "confounding"=confondimento.
- Riporta con precisione le misure statistiche: odds ratio (OR), hazard ratio (HR),
  rischio relativo (RR), intervallo di confidenza (IC) al 95%, valore di p.
- NUMERI: riporta cifre e separatore decimale ESATTAMENTE come nell'originale
  (punto decimale: 0.85; p<0.001). Non alterare dosi, unità di misura, percentuali,
  né i parametri ventilatori (FiO2, PEEP, cmH2O, L/min).
- Mantieni in forma originale le scale validate (GCS, SOFA, NEWS2, CURB-65, HACOR,
  indice ROX).
- Espandi ogni acronimo alla prima comparsa, poi usa la sigla.
- Non usare mai "significativo" da solo: specifica "statisticamente significativo"
  oppure "clinicamente rilevante".
- Attieniti SOLO ai dati dell'abstract: non aggiungere, non inferire, non inventare."""

SYSTEM_SINTESI_NIV = """Sei un medico di Area Critica e Pronto Soccorso italiano esperto in
ventilazione non invasiva e supporto respiratorio, e in traduzione medico-scientifica
dall'inglese all'italiano.

""" + REGOLE_COMUNI

SYSTEM_SINTESI_EM = """Sei un medico di Pronto Soccorso italiano esperto di letteratura
scientifica e di traduzione medico-scientifica dall'inglese all'italiano.

""" + REGOLE_COMUNI

# --- NIV: focus sul supporto ventilatorio -------------------------------------
PROMPT_SINTESI_MULTI = """Analizza OGNI articolo della lista e produci per ciascuno quattro campi:

1. "sintesi" - da 90 a 120 parole, che rispondano nell'ordine a: quesito clinico;
   disegno dello studio e popolazione, con numerosità; risultato principale con i
   numeri chiave e la misura di effetto; ricaduta sulla pratica nella gestione dell'insufficienza respiratoria acuta e del supporto ventilatorio non invasivo in PS/Area Critica.
2. "rilevanza" - UNA sola frase, massimo 30 parole, sulla ricaduta pratica concreta
   per il supporto respiratorio non invasivo in Pronto Soccorso.
3. "limite" - UNA sola frase, massimo 25 parole, sul principale limite metodologico:
   monocentrico, non in cieco, endpoint surrogato, campione ridotto, popolazione
   selezionata, interruzione precoce, follow-up breve, conflitti di interesse.
   Per le sintesi di letteratura il limite riguarda il metodo della revisione:
   narrativa e non sistematica, selezione non riproducibile, eterogeneità degli studi.
   Solo se l'abstract non consente davvero di identificare alcun limite, scrivi
   esattamente: "Limiti non desumibili dall'abstract."
4. "tipo" - UNO SOLO fra questi valori, riportato esattamente così:
   "cambia-pratica" = lo studio modifica una condotta oggi diffusa
   "conferma"       = rafforza una pratica già consolidata
   "controverso"    = risultati discordanti con evidenze o linee guida attuali
   "esplorativo"    = ipotesi generatrice, dati preliminari, campione insufficiente
   "revisione"      = sintesi di letteratura senza dati primari originali (review
                      narrativa, scoping review, revisione sistematica, linea guida)

SE L'ABSTRACT È ASSENTE O PRIVO DI RISULTATI NUMERICI: scrivi nella "sintesi" una
sola frase che lo dichiari esplicitamente, non inferire nulla dal titolo, usa
"esplorativo" come tipo.

ARTICOLI:
{articoli}

FORMATO DI RISPOSTA - restituisci SOLO un array JSON valido, senza testo prima o dopo,
senza blocchi markdown, con un oggetto per articolo, nello stesso ordine della lista.
Riporta il "pmid" esattamente come ti è stato fornito.
Nei valori testuali NON usare mai virgolette doppie: per citare un nome, un termine o una frase usa gli apici singoli ('...') oppure le caporali «...». Una virgoletta doppia dentro il testo rompe il formato JSON.

[
  {{
    "pmid": "12345678",
    "sintesi": "...",
    "rilevanza": "...",
    "limite": "...",
    "tipo": "cambia-pratica"
  }}
]"""

PROMPT_SINTESI = """Analizza l'articolo e produci quattro campi:

1. "sintesi" - da 90 a 120 parole, che rispondano nell'ordine a: quesito clinico;
   disegno dello studio e popolazione, con numerosità; risultato principale con i
   numeri chiave e la misura di effetto; ricaduta sulla pratica nella gestione dell'insufficienza respiratoria acuta e del supporto ventilatorio non invasivo in PS/Area Critica.
2. "rilevanza" - UNA sola frase, massimo 30 parole, sulla ricaduta pratica concreta
   per il supporto respiratorio non invasivo in Pronto Soccorso.
3. "limite" - UNA sola frase, massimo 25 parole, sul principale limite metodologico:
   monocentrico, non in cieco, endpoint surrogato, campione ridotto, popolazione
   selezionata, interruzione precoce, follow-up breve, conflitti di interesse.
   Per le sintesi di letteratura il limite riguarda il metodo della revisione:
   narrativa e non sistematica, selezione non riproducibile, eterogeneità degli studi.
   Solo se l'abstract non consente davvero di identificare alcun limite, scrivi
   esattamente: "Limiti non desumibili dall'abstract."
4. "tipo" - UNO SOLO fra questi valori, riportato esattamente così:
   "cambia-pratica" = lo studio modifica una condotta oggi diffusa
   "conferma"       = rafforza una pratica già consolidata
   "controverso"    = risultati discordanti con evidenze o linee guida attuali
   "esplorativo"    = ipotesi generatrice, dati preliminari, campione insufficiente
   "revisione"      = sintesi di letteratura senza dati primari originali (review
                      narrativa, scoping review, revisione sistematica, linea guida)

SE L'ABSTRACT È ASSENTE O PRIVO DI RISULTATI NUMERICI: scrivi nella "sintesi" una
sola frase che lo dichiari esplicitamente, non inferire nulla dal titolo, usa
"esplorativo" come tipo.

Articolo:
PMID: {pmid}
Titolo: {titolo}
Autori: {autori}
Rivista: {rivista} ({data})
Abstract: {abstract}

FORMATO DI RISPOSTA - restituisci SOLO un array JSON valido con UN solo oggetto,
senza testo prima o dopo, senza blocchi markdown:
Nei valori testuali NON usare mai virgolette doppie: per citare un nome, un termine o una frase usa gli apici singoli ('...') oppure le caporali «...». Una virgoletta doppia dentro il testo rompe il formato JSON.

[
  {{
    "pmid": "{pmid}",
    "sintesi": "...",
    "rilevanza": "...",
    "limite": "...",
    "tipo": "conferma"
  }}
]"""

# --- EM: focus generale sulla pratica in PS ------------------------------------
PROMPT_SINTESI_MULTI_EM = """Analizza OGNI articolo della lista e produci per ciascuno quattro campi:

1. "sintesi" - da 90 a 120 parole, che rispondano nell'ordine a: quesito clinico;
   disegno dello studio e popolazione, con numerosità; risultato principale con i
   numeri chiave e la misura di effetto; ricaduta sulla pratica in Pronto Soccorso e Area Critica.
2. "rilevanza" - UNA sola frase, massimo 30 parole, sulla ricaduta pratica concreta
   per la pratica in Pronto Soccorso.
3. "limite" - UNA sola frase, massimo 25 parole, sul principale limite metodologico:
   monocentrico, non in cieco, endpoint surrogato, campione ridotto, popolazione
   selezionata, interruzione precoce, follow-up breve, conflitti di interesse.
   Per le sintesi di letteratura il limite riguarda il metodo della revisione:
   narrativa e non sistematica, selezione non riproducibile, eterogeneità degli studi.
   Solo se l'abstract non consente davvero di identificare alcun limite, scrivi
   esattamente: "Limiti non desumibili dall'abstract."
4. "tipo" - UNO SOLO fra questi valori, riportato esattamente così:
   "cambia-pratica" = lo studio modifica una condotta oggi diffusa
   "conferma"       = rafforza una pratica già consolidata
   "controverso"    = risultati discordanti con evidenze o linee guida attuali
   "esplorativo"    = ipotesi generatrice, dati preliminari, campione insufficiente
   "revisione"      = sintesi di letteratura senza dati primari originali (review
                      narrativa, scoping review, revisione sistematica, linea guida)

SE L'ABSTRACT È ASSENTE O PRIVO DI RISULTATI NUMERICI: scrivi nella "sintesi" una
sola frase che lo dichiari esplicitamente, non inferire nulla dal titolo, usa
"esplorativo" come tipo.

ARTICOLI:
{articoli}

FORMATO DI RISPOSTA - restituisci SOLO un array JSON valido, senza testo prima o dopo,
senza blocchi markdown, con un oggetto per articolo, nello stesso ordine della lista.
Riporta il "pmid" esattamente come ti è stato fornito.
Nei valori testuali NON usare mai virgolette doppie: per citare un nome, un termine o una frase usa gli apici singoli ('...') oppure le caporali «...». Una virgoletta doppia dentro il testo rompe il formato JSON.

[
  {{
    "pmid": "12345678",
    "sintesi": "...",
    "rilevanza": "...",
    "limite": "...",
    "tipo": "cambia-pratica"
  }}
]"""

PROMPT_SINTESI_EM = """Analizza l'articolo e produci quattro campi:

1. "sintesi" - da 90 a 120 parole, che rispondano nell'ordine a: quesito clinico;
   disegno dello studio e popolazione, con numerosità; risultato principale con i
   numeri chiave e la misura di effetto; ricaduta sulla pratica in Pronto Soccorso e Area Critica.
2. "rilevanza" - UNA sola frase, massimo 30 parole, sulla ricaduta pratica concreta
   per la pratica in Pronto Soccorso.
3. "limite" - UNA sola frase, massimo 25 parole, sul principale limite metodologico:
   monocentrico, non in cieco, endpoint surrogato, campione ridotto, popolazione
   selezionata, interruzione precoce, follow-up breve, conflitti di interesse.
   Per le sintesi di letteratura il limite riguarda il metodo della revisione:
   narrativa e non sistematica, selezione non riproducibile, eterogeneità degli studi.
   Solo se l'abstract non consente davvero di identificare alcun limite, scrivi
   esattamente: "Limiti non desumibili dall'abstract."
4. "tipo" - UNO SOLO fra questi valori, riportato esattamente così:
   "cambia-pratica" = lo studio modifica una condotta oggi diffusa
   "conferma"       = rafforza una pratica già consolidata
   "controverso"    = risultati discordanti con evidenze o linee guida attuali
   "esplorativo"    = ipotesi generatrice, dati preliminari, campione insufficiente
   "revisione"      = sintesi di letteratura senza dati primari originali (review
                      narrativa, scoping review, revisione sistematica, linea guida)

SE L'ABSTRACT È ASSENTE O PRIVO DI RISULTATI NUMERICI: scrivi nella "sintesi" una
sola frase che lo dichiari esplicitamente, non inferire nulla dal titolo, usa
"esplorativo" come tipo.

Articolo:
PMID: {pmid}
Titolo: {titolo}
Autori: {autori}
Rivista: {rivista} ({data})
Abstract: {abstract}

FORMATO DI RISPOSTA - restituisci SOLO un array JSON valido con UN solo oggetto,
senza testo prima o dopo, senza blocchi markdown:
Nei valori testuali NON usare mai virgolette doppie: per citare un nome, un termine o una frase usa gli apici singoli ('...') oppure le caporali «...». Una virgoletta doppia dentro il testo rompe il formato JSON.

[
  {{
    "pmid": "{pmid}",
    "sintesi": "...",
    "rilevanza": "...",
    "limite": "...",
    "tipo": "conferma"
  }}
]"""


# --- Sintesi mista: NIV ed EM in UNA sola chiamata -----------------------------
# Derivata dal prompt NIV: cambia solo l'ambito della ricaduta, indicato per articolo.
def _sostituisci_unico(testo, vecchio, nuovo):
    if testo.count(vecchio) != 1:
        raise RuntimeError(f"Prompt di sintesi cambiato: frase non trovata ({vecchio[:50]}...)")
    return testo.replace(vecchio, nuovo)

_RICADUTA_NIV = ("ricaduta sulla pratica nella gestione dell'insufficienza respiratoria acuta "
                 "e del supporto ventilatorio non invasivo in PS/Area Critica.")
_RILEVANZA_NIV = "per il supporto respiratorio non invasivo in Pronto Soccorso."

PROMPT_SINTESI_MULTI_MISTO = _sostituisci_unico(
    _sostituisci_unico(
        PROMPT_SINTESI_MULTI, _RICADUTA_NIV,
        "ricaduta sulla pratica secondo l'AMBITO indicato per ciascun articolo: per "
        "\"NIV\" nella gestione dell'insufficienza respiratoria acuta e del supporto "
        "ventilatorio non invasivo in PS/Area Critica; per \"EM\" nella pratica in "
        "Pronto Soccorso e Area Critica."),
    _RILEVANZA_NIV,
    "per l'AMBITO indicato (\"NIV\": supporto respiratorio non invasivo in Pronto "
    "Soccorso; \"EM\": pratica in Pronto Soccorso).")

SYSTEM_SINTESI_MISTO = """Sei un medico di Area Critica e Pronto Soccorso italiano esperto in
ventilazione non invasiva, supporto respiratorio e letteratura di medicina d'urgenza, e in
traduzione medico-scientifica dall'inglese all'italiano.

""" + REGOLE_COMUNI


def valida_config():
    mancanti = []
    if not ANTHROPIC_API_KEY: mancanti.append("ANTHROPIC_API_KEY")
    # In prova a vuoto o su Instagram non si invia nulla: le credenziali SMTP non servono.
    if not DRY_RUN and not SOLO_INSTAGRAM:
        if not GMAIL_USER:         mancanti.append("GMAIL_USER")
        if not GMAIL_APP_PASSWORD: mancanti.append("GMAIL_APP_PASSWORD")
    if mancanti:
        raise RuntimeError(
            f"Variabili d'ambiente mancanti: {', '.join(mancanti)}.\n"
            "Configurale nei GitHub Secrets."
        )
    return True
