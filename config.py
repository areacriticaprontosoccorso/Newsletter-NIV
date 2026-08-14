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
MINIMO_ARTICOLI       = 3    # sotto questa soglia si riempie per data
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

LOGO_URL = "https://raw.githubusercontent.com/areacriticaprontosoccorso/Newsletter-NIV/main/logo.png"

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

[
  {{"pmid": "12345678", "tema": "sepsi", "perche": "motivo in max 15 parole"}}
]

Ordina dal più rilevante al meno rilevante."""

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

[
  {{
    "pmid": "{pmid}",
    "sintesi": "...",
    "rilevanza": "...",
    "limite": "...",
    "tipo": "conferma"
  }}
]"""


def valida_config():
    mancanti = []
    if not ANTHROPIC_API_KEY: mancanti.append("ANTHROPIC_API_KEY")
    # In prova a vuoto non si invia nulla: le credenziali SMTP non servono.
    if not DRY_RUN:
        if not GMAIL_USER:         mancanti.append("GMAIL_USER")
        if not GMAIL_APP_PASSWORD: mancanti.append("GMAIL_APP_PASSWORD")
    if mancanti:
        raise RuntimeError(
            f"Variabili d'ambiente mancanti: {', '.join(mancanti)}.\n"
            "Configurale nei GitHub Secrets."
        )
    return True
