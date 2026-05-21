"""
Config NIV Weekly Digest — versione sicura per repo pubblico
"""

import os

ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL    = "claude-sonnet-4-6"
GMAIL_USER         = os.environ.get("GMAIL_USER", "")
NCBI_EMAIL         = "francesco.panero@aslcittaditorino.it"
NCBI_TOOL          = "niv_weekly_digest_torino"

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
]

RIVISTE_NIV = [
    {"nome": "American Journal of Respiratory and Critical Care Medicine", "nlmta": "Am J Respir Crit Care Med", "issn": "1073-449X"},
    {"nome": "European Respiratory Journal",                              "nlmta": "Eur Respir J",              "issn": "0903-1936"},
    {"nome": "Thorax",                                                    "nlmta": "Thorax",                    "issn": "0040-6376"},
    {"nome": "Respiratory Care",                                          "nlmta": "Respir Care",               "issn": "0020-1324"},
]

ARTICOLI_FINALI = 5
GIORNI_RICERCA  = 7

NOME_NEWSLETTER = "NIV Weekly Digest"
NOME_SERVIZIO   = "Pronto Soccorso · San Giovanni Bosco · Torino"
COLOR_ACCENT    = "#2e7d32"
COLOR_DARK      = "#1a2a1e"

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "newsletter_niv.log")

PROMPT_SINTESI = """Sei un medico di Pronto Soccorso italiano esperto in ventilazione non invasiva e supporto respiratorio.

Analizza questo articolo e produci in italiano:
1. SINTESI: 3-4 frasi che rispondano a — domanda clinica, risultato principale, impatto per la gestione dell'insufficienza respiratoria acuta in PS/ICU
2. RILEVANZA: una sola frase sulla rilevanza pratica per il supporto ventilatorio in Pronto Soccorso

Articolo:
Titolo: {titolo}
Autori: {autori}
Rivista: {rivista} ({data})
Abstract: {abstract}

Rispondi SOLO in questo formato:
SINTESI: [testo]
RILEVANZA: [testo]"""


def valida_config():
    mancanti = []
    if not ANTHROPIC_API_KEY: mancanti.append("ANTHROPIC_API_KEY")
    if not GMAIL_USER:        mancanti.append("GMAIL_USER")
    if mancanti:
        raise RuntimeError(
            f"Variabili d'ambiente mancanti: {', '.join(mancanti)}.\n"
            "Configurale nei GitHub Secrets."
        )
    return True
