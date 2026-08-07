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

RIVISTE_NIV = [
    {"nome": "American Journal of Respiratory and Critical Care Medicine", "nlmta": "Am J Respir Crit Care Med", "issn": "1073-449X"},
    {"nome": "European Respiratory Journal",                              "nlmta": "Eur Respir J",              "issn": "0903-1936"},
    {"nome": "Thorax",                                                    "nlmta": "Thorax",                    "issn": "0040-6376"},
    {"nome": "Respiratory Care",                                          "nlmta": "Respir Care",               "issn": "0020-1324"},
]

# ═══════════════════════════════════════════════════════════════════════════════
# PARAMETRI PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════
ARTICOLI_FINALI       = 5    # posizioni totali nel digest
GIORNI_RICERCA        = 7
GIORNI_RICERCA_ESTESO = 14   # fallback se la settimana è povera
MINIMO_ARTICOLI       = 3    # sotto questa soglia si riempie per data
MAX_PER_TEMA          = 2    # max articoli sullo stesso tema clinico (parte EM)
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

ABSTRACT_MIN_CHARS = 200

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
di insufficienza respiratoria acuta e supporto ventilatorio. Selezioni la letteratura
settimanale sul tema per i colleghi del tuo reparto. Sei severo: preferisci una
selezione corta e centrata a una lunga e annacquata.

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
articoli STRETTAMENTE pertinenti alla gestione del supporto respiratorio nel paziente
acuto. Puoi restituirne meno di {n}, e anche nessuno.

E' PERTINENTE un articolo il cui oggetto di studio è uno di questi:
- ventilazione non invasiva (NIV/BiPAP/bilevel), CPAP, casco;
- high-flow nasal cannula / ossigenoterapia ad alti flussi;
- ossigenoterapia e target di ossigenazione;
- insufficienza respiratoria acuta ipossiemica o ipercapnica;
- ARDS e strategie ventilatorie;
- edema polmonare acuto cardiogeno trattato con supporto ventilatorio;
- riacutizzazione di BPCO, asma acuto grave, polmonite con insufficienza respiratoria,
  quando lo studio riguarda il supporto respiratorio o l'outcome respiratorio;
- ventilazione meccanica invasiva, intubazione e gestione delle vie aeree nel paziente
  critico, weaning, estubazione e supporto post-estubazione;
- monitoraggio respiratorio, emogasanalisi, scambi gassosi, drive respiratorio, P-SILI;
- sedazione e analgesia specificamente nel paziente ventilato.

NON è pertinente — e va escluso anche se contiene la parola "respiratorio":
- studi di pneumologia cronica ambulatoriale (asma stabile, BPCO stabile, OSAS
  elettiva, fibrosi, riabilitazione respiratoria, cessazione del fumo);
- epidemiologia o prevenzione delle infezioni respiratorie senza dati sul supporto
  ventilatorio;
- studi in cui la ventilazione compare solo come variabile di aggiustamento o come
  endpoint secondario marginale;
- case report, case series, lettere, editoriali, commenti, errata.

SOGLIA: nel dubbio, ESCLUDI. E' preferibile un digest di 2 articoli davvero
sul supporto ventilatorio che uno di 5 in cui 3 c'entrano poco.

ARTICOLI CANDIDATI:
{articoli}

FORMATO DI RISPOSTA - restituisci SOLO un array JSON valido, senza testo prima o dopo,
senza blocchi markdown. Scegli esclusivamente PMID presenti nella lista qui sopra:
non inventare né modificare PMID. Se nessun articolo è pertinente restituisci
esattamente: []

[
  {{"pmid": "12345678", "tema": "HFNC", "perche": "motivo in max 15 parole"}}
]

Ordina dal più rilevante al meno rilevante."""

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
REGOLE_COMUNI = """Attieniti SOLO ai dati dell'abstract: non aggiungere, non inferire, non inventare.
NON alterare numeri, dosi, unità di misura, percentuali: riporta cifre e separatore
decimale esattamente come nell'originale (0.85; p<0.001).
Traduci il significato clinico, mai parola per parola: "severe"=grave, "evidence"=prove,
"consistent"=coerente, "rate"=tasso, "compliance"=aderenza, "management"=gestione.
Mantieni in forma originale le scale validate (GCS, SOFA, NEWS2, CURB-65) e le misure
statistiche (OR, HR, RR, IC 95%)."""

SYSTEM_SINTESI_NIV = """Sei un medico di Area Critica e Pronto Soccorso italiano esperto in
ventilazione non invasiva e supporto respiratorio, e in traduzione medico-scientifica
dall'inglese all'italiano.

""" + REGOLE_COMUNI

SYSTEM_SINTESI_EM = """Sei un medico di Pronto Soccorso italiano esperto di letteratura
scientifica e di traduzione medico-scientifica dall'inglese all'italiano.

""" + REGOLE_COMUNI

# --- NIV: focus sul supporto ventilatorio -------------------------------------
PROMPT_SINTESI_MULTI = """Analizza OGNI articolo della lista e produci per ciascuno, in italiano:
1. SINTESI: 3-4 frasi che rispondano a — domanda clinica, disegno e popolazione,
   risultato principale (con i numeri chiave), impatto per la gestione
   dell'insufficienza respiratoria acuta in PS/ICU
2. RILEVANZA: una sola frase sulla rilevanza pratica per il supporto ventilatorio
   in Pronto Soccorso

ARTICOLI:
{articoli}

Rispondi SOLO in questo formato, ripetuto per ogni articolo, nello stesso ordine
della lista, senza alcun altro testo prima o dopo:

### PMID: [pmid]
SINTESI: [testo]
RILEVANZA: [testo]"""

PROMPT_SINTESI = """Analizza questo articolo e produci in italiano:
1. SINTESI: 3-4 frasi che rispondano a — domanda clinica, disegno e popolazione,
   risultato principale con i numeri chiave, impatto per la gestione
   dell'insufficienza respiratoria acuta in PS/ICU
2. RILEVANZA: una sola frase sulla rilevanza pratica per il supporto ventilatorio
   in Pronto Soccorso

Articolo:
PMID: {pmid}
Titolo: {titolo}
Autori: {autori}
Rivista: {rivista} ({data})
Abstract: {abstract}

Rispondi SOLO in questo formato:
### PMID: {pmid}
SINTESI: [testo]
RILEVANZA: [testo]"""

# --- EM: focus generale sulla pratica in PS ------------------------------------
PROMPT_SINTESI_MULTI_EM = """Analizza OGNI articolo della lista e produci per ciascuno, in italiano:
1. SINTESI: 3-4 frasi che rispondano a — quesito clinico, disegno dello studio e
   popolazione con numerosità, risultato principale con i numeri chiave e la misura
   di effetto, ricaduta sulla pratica in PS/Area Critica
2. RILEVANZA: una sola frase, massimo 30 parole, sulla ricaduta pratica concreta
   in Pronto Soccorso

ARTICOLI:
{articoli}

Rispondi SOLO in questo formato, ripetuto per ogni articolo, nello stesso ordine
della lista, senza alcun altro testo prima o dopo:

### PMID: [pmid]
SINTESI: [testo]
RILEVANZA: [testo]"""

PROMPT_SINTESI_EM = """Analizza questo articolo e produci in italiano:
1. SINTESI: 3-4 frasi che rispondano a — quesito clinico, disegno e popolazione con
   numerosità, risultato principale con i numeri chiave e la misura di effetto,
   ricaduta sulla pratica in PS/Area Critica
2. RILEVANZA: una sola frase, massimo 30 parole, sulla ricaduta pratica concreta

Articolo:
PMID: {pmid}
Titolo: {titolo}
Autori: {autori}
Rivista: {rivista} ({data})
Abstract: {abstract}

Rispondi SOLO in questo formato:
### PMID: {pmid}
SINTESI: [testo]
RILEVANZA: [testo]"""


def valida_config():
    mancanti = []
    if not ANTHROPIC_API_KEY:  mancanti.append("ANTHROPIC_API_KEY")
    if not GMAIL_USER:         mancanti.append("GMAIL_USER")
    if not GMAIL_APP_PASSWORD: mancanti.append("GMAIL_APP_PASSWORD")
    if mancanti:
        raise RuntimeError(
            f"Variabili d'ambiente mancanti: {', '.join(mancanti)}.\n"
            "Configurale nei GitHub Secrets."
        )
    return True
