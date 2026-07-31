"""
NIV Weekly Digest — Newsletter insufficienza respiratoria acuta
Area Critica e Pronto Soccorso San Giovanni Bosco, Torino
Comando: python newsletter_NIV.py

Selezione a due stadi:
  1. filtro NIV stretto: solo articoli davvero sul supporto ventilatorio (puo' dare 0);
  2. se restano posizioni libere, si riempiono con articoli di medicina d'urgenza
     selezionati con i criteri di EM Weekly Digest (newsletter-ps).
Ogni articolo porta il campo "origine" ("niv" | "em"), usato per la sintesi
e per il badge in email e Telegram.
"""

import os
import re
import json
import time
import html
import logging
import smtplib
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone

import config as cfg

TUTTE_RIVISTE = cfg.RIVISTE_NIV + cfg.RIVISTE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(cfg.LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("newsletter_niv")

_RE_ESCLUSI = [re.compile(p, re.IGNORECASE) for p in cfg.ESCLUSIONI_TITOLO]


def esc(s):
    """Escape per testo dinamico inserito nell'HTML (email e Telegram)."""
    return html.escape(str(s or ""), quote=True)


def escluso_per_titolo(titolo):
    """True se il titolo indica un tipo di pubblicazione da escludere.
    PubMed racchiude tra parentesi quadre i titoli tradotti da altre lingue."""
    t = (titolo or "").strip().lstrip("[").strip()
    return any(r.search(t) for r in _RE_ESCLUSI)


def _estrai_json_array(testo):
    """Estrae il primo array JSON dalla risposta, tollerando i fence markdown."""
    t = re.sub(r"^```(?:json)?\s*", "", testo.strip())
    t = re.sub(r"\s*```$", "", t)
    inizio, fine = t.find("["), t.rfind("]")
    if inizio == -1 or fine == -1 or fine < inizio:
        raise ValueError(f"Nessun array JSON nella risposta: {t[:200]}")
    return json.loads(t[inizio:fine + 1])


def carica_destinatari():
    """Destinatario fisso + iscritti da subscribers.json.
    NB: il log riporta solo i CONTEGGI, mai gli indirizzi."""
    fisso = "francesco.panero@aslcittaditorino.it"
    try:
        sub_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "subscribers.json")
        with open(sub_path, encoding="utf-8") as f:
            subs = json.load(f)
        emails = [
            s["email"].strip()
            for s in subs
            if "@" in s.get("email", "") and " " not in s.get("email", "")
        ]
        if fisso not in emails:
            emails.insert(0, fisso)
        log.info(f"Destinatari caricati: {len(emails)}")
        return emails
    except Exception as e:
        log.error(f"Errore carica subscribers: {e} — uso solo destinatario fisso")
        return [fisso]


def numero_settimana():
    now = datetime.now()
    mesi = ["Gennaio","Febbraio","Marzo","Aprile","Maggio","Giugno",
            "Luglio","Agosto","Settembre","Ottobre","Novembre","Dicembre"]
    return {
        "settimana": now.isocalendar()[1],
        "anno":      now.year,
        "giorno":    now.day,
        "mese":      mesi[now.month - 1],
    }


def fetch_url(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": cfg.NCBI_TOOL})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            log.warning(f"Tentativo {attempt+1}/3 fallito: {e}")
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Fetch fallito: {url}")


NS = {"dc": "http://purl.org/dc/elements/1.1/"}


def url_rss_pubmed(issn):
    return f"https://pubmed.ncbi.nlm.nih.gov/rss/journals/{issn}/?limit=20&utm_campaign=journals"


def parse_pubdate(s):
    if not s:
        return None
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(s)
    except Exception:
        return None


def estrai_abstract(desc):
    if not desc:
        return ""
    t = re.sub(r"<[^>]+>", " ", desc)
    t = html.unescape(t)
    t = re.sub(r"PMID:\s*\d+.*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"DOI:\s*[\w./-]+", "", t, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", t).strip()[:2500]


def estrai_pmid(item):
    link_el = item.find("link")
    if link_el is not None and link_el.text:
        m = re.search(r"/(\d{7,9})/?", link_el.text)
        if m:
            return m.group(1)
    for ident in item.findall("dc:identifier", NS):
        if ident.text and ident.text.startswith("pmid:"):
            return ident.text.replace("pmid:", "").strip()
    return ""


def estrai_doi(item):
    for ident in item.findall("dc:identifier", NS):
        if ident.text and ident.text.startswith("doi:"):
            return ident.text.replace("doi:", "").strip()
    return ""


def estrai_autori(item):
    nomi = [c.text for c in item.findall("dc:creator", NS) if c.text]
    if not nomi:
        return ""
    if len(nomi) > 3:
        return ", ".join(nomi[:3]) + " et al."
    return ", ".join(nomi)


def fetch_feed(rivista):
    url = url_rss_pubmed(rivista["issn"])
    try:
        raw = fetch_url(url)
        root = ET.fromstring(raw)
    except Exception as e:
        log.error(f"  {rivista['nlmta']}: errore RSS {e}")
        return []
    articoli, scartati = [], 0
    for item in root.findall(".//item"):
        titolo  = (item.findtext("title") or "").strip()
        link    = (item.findtext("link") or "").strip()
        desc    = item.findtext("description") or ""
        pubdate = parse_pubdate(item.findtext("pubDate"))
        pmid    = estrai_pmid(item)
        if not pmid or not titolo:
            continue
        # Pre-filtro deterministico: errata, lettere, editoriali, immagini.
        if escluso_per_titolo(titolo):
            scartati += 1
            continue
        articoli.append({
            "pmid":       pmid,
            "titolo":     titolo.rstrip("."),
            "autori":     estrai_autori(item),
            "rivista":    rivista["nome"],
            "nlmta":      rivista["nlmta"],
            "data":       pubdate.strftime("%Y %b %d") if pubdate else "",
            "pubdate_dt": pubdate,
            "doi":        estrai_doi(item),
            "abstract":   estrai_abstract(desc),
            "url":        link or f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "origine":    "",
        })
    log.info(f"  {rivista['nlmta']}: {len(articoli)} articoli"
             + (f" ({scartati} scartati per tipo)" if scartati else ""))
    return articoli


def raccogli_candidati(giorni=None):
    giorni = giorni or cfg.GIORNI_RICERCA
    log.info(f"RSS PubMed: ultimi {giorni}g su {len(TUTTE_RIVISTE)} riviste")
    cutoff = datetime.now(timezone.utc) - timedelta(days=giorni)
    tutti = []
    for r in TUTTE_RIVISTE:
        feed = fetch_feed(r)
        recenti = [a for a in feed if a["pubdate_dt"] and a["pubdate_dt"].astimezone(timezone.utc) >= cutoff]
        log.info(f"    -> {len(recenti)} ultimi {giorni}g")
        tutti.extend(recenti)
        time.sleep(0.3)
    seen = set()
    unici = [a for a in tutti if not (a["pmid"] in seen or seen.add(a["pmid"]))]
    ok = [a for a in unici if a["abstract"] and len(a["abstract"]) >= cfg.ABSTRACT_MIN_CHARS]
    log.info(f"Unici: {len(unici)}, con abstract utile: {len(ok)}")
    return ok


def chiama_claude(prompt, max_tokens=1500, system=None, temperature=None, prefill=None):
    """prefill: testo con cui far iniziare la risposta (es. "[" per forzare il JSON).
    Viene riconcatenato in testa al risultato, perche' l'API restituisce solo la
    continuazione."""
    messaggi = [{"role": "user", "content": prompt}]
    if prefill:
        messaggi.append({"role": "assistant", "content": prefill})
    corpo = {
        "model":      cfg.ANTHROPIC_MODEL,
        "max_tokens": max_tokens,
        # Sonnet 5 ha l'adaptive thinking attivo di default: lo disattiviamo,
        # cosi' la risposta e' solo testo e max_tokens non viene speso in thinking.
        "thinking":   {"type": "disabled"},
        "messages":   messaggi,
    }
    if system:
        corpo["system"] = system
    if temperature is not None:
        corpo["temperature"] = temperature
    payload = json.dumps(corpo).encode("utf-8")
    # Retry con backoff su rate-limit (429) e errori server transitori (5xx).
    ultimo_errore = None
    for attempt in range(4):
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type":      "application/json",
                "x-api-key":         cfg.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read().decode("utf-8"))
            blocchi = data.get("content", [])
            testo = next((b.get("text", "") for b in blocchi if b.get("type") == "text"), "")
            if not testo:
                raise RuntimeError(f"Nessun blocco di testo nella risposta API: {str(data)[:300]}")
            return (prefill or "") + testo.strip()
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            ultimo_errore = f"Anthropic API errore {e.code}: {body[:400]}"
            if e.code == 429 or 500 <= e.code < 600:
                attesa = 2 ** attempt
                log.warning(f"{ultimo_errore} — retry tra {attesa}s ({attempt+1}/4)")
                time.sleep(attesa)
                continue
            raise RuntimeError(ultimo_errore)
        except urllib.error.URLError as e:
            ultimo_errore = f"Anthropic API errore di rete: {e}"
            attesa = 2 ** attempt
            log.warning(f"{ultimo_errore} — retry tra {attesa}s ({attempt+1}/4)")
            time.sleep(attesa)
    raise RuntimeError(ultimo_errore or "Anthropic API: fallito dopo i retry")


# ═══════════════════════════════════════════════════════════════════════════════
# SELEZIONE
# ═══════════════════════════════════════════════════════════════════════════════

def _limita_candidati(candidati):
    """Tetto ai candidati inviati al modello: una lista troppo lunga peggiora la
    selezione, oltre ai costi."""
    if len(candidati) <= cfg.MAX_CANDIDATI_PROMPT:
        return candidati
    log.warning(
        f"{len(candidati)} candidati: ne invio al filtro i "
        f"{cfg.MAX_CANDIDATI_PROMPT} piu' recenti"
    )
    return sorted(
        candidati,
        key=lambda a: a["pubdate_dt"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )[:cfg.MAX_CANDIDATI_PROMPT]


def _blocchi_prompt(candidati):
    return "\n\n---\n\n".join(
        f"PMID: {a['pmid']}\n"
        f"RIVISTA: {a['rivista']} ({a['data']})\n"
        f"TITOLO: {a['titolo']}\n"
        f"ABSTRACT: {a['abstract'][:700]}"
        for a in candidati
    )


def _filtro_json(candidati, prompt, system, n, max_per_tema=None, etichetta=""):
    """Esegue un filtro che risponde in JSON e restituisce (selezionati, riserva).
    Solleva l'eccezione al chiamante se la chiamata API fallisce del tutto."""
    map_pmid = {a["pmid"]: a for a in candidati}
    selezionati, riserva, conteggio_temi = [], [], {}
    risposta = chiama_claude(
        prompt,
        max_tokens=cfg.MAX_TOKENS_FILTRO,
        system=system,
        temperature=cfg.TEMPERATURE_FILTRO,
        prefill="[",
    )
    for voce in _estrai_json_array(risposta):
        if len(selezionati) >= n:
            break
        if not isinstance(voce, dict):
            continue
        pmid   = str(voce.get("pmid", "")).strip()
        tema   = (str(voce.get("tema", "")).strip().lower() or "n/d")
        perche = str(voce.get("perche", "")).strip()
        # Il PMID deve esistere tra i candidati: blocca le allucinazioni.
        if pmid not in map_pmid:
            log.warning(f"    [{etichetta}] PMID non tra i candidati, ignorato: {pmid!r}")
            continue
        if any(a["pmid"] == pmid for a in selezionati):
            continue
        if max_per_tema and conteggio_temi.get(tema, 0) >= max_per_tema:
            log.info(f"    [{etichetta}] {pmid} in riserva: tema '{tema}' gia' saturo")
            riserva.append(map_pmid[pmid])
            continue
        conteggio_temi[tema] = conteggio_temi.get(tema, 0) + 1
        selezionati.append(map_pmid[pmid])
        log.info(f"    [{etichetta}] {pmid} — {tema} — {perche}")
    return selezionati, riserva


def filtra_niv(candidati, n):
    """Stadio 1: articoli STRETTAMENTE pertinenti al supporto ventilatorio.
    Puo' restituire una lista vuota: e' un esito legittimo, non un errore."""
    pool = _limita_candidati(candidati)
    prompt = cfg.PROMPT_FILTRO_NIV.format(n=n, articoli=_blocchi_prompt(pool))
    log.info(f"Filtro NIV stretto su {len(pool)} candidati -> max {n}")
    try:
        selezionati, _ = _filtro_json(
            pool, prompt, cfg.SYSTEM_FILTRO_NIV, n, etichetta="NIV"
        )
    except Exception as e:
        log.error(f"Filtro NIV fallito ({e})")
        return None  # None = filtro non eseguito, diverso da [] = nessun pertinente
    for a in selezionati:
        a["origine"] = "niv"
    log.info(f"Articoli NIV pertinenti: {len(selezionati)}")
    return selezionati


def filtra_em(candidati, esclusi_pmid, n):
    """Stadio 2: articoli di medicina d'urgenza con i criteri di newsletter-ps,
    usati per riempire le posizioni lasciate libere dal filtro NIV.
    Restituisce (selezionati, riserva): la riserva sono gli articoli validi messi
    da parte dal vincolo di diversita', da usare solo per il riempimento minimo."""
    pool = _limita_candidati([a for a in candidati if a["pmid"] not in esclusi_pmid])
    if not pool:
        return [], []
    prompt = cfg.PROMPT_FILTRO_EM.format(n=n, articoli=_blocchi_prompt(pool))
    log.info(f"Filtro EM (criteri newsletter-ps) su {len(pool)} candidati -> max {n}")
    try:
        selezionati, riserva = _filtro_json(
            pool, prompt, cfg.SYSTEM_FILTRO_EM, n,
            max_per_tema=cfg.MAX_PER_TEMA, etichetta="EM",
        )
    except Exception as e:
        log.error(f"Filtro EM fallito ({e})")
        selezionati, riserva = [], []
    # Nessun riempimento per data qui: come in newsletter-ps, se gli articoli
    # davvero solidi sono meno di n si preferisce un digest piu' corto.
    for a in selezionati:
        a["origine"] = "em"
    log.info(f"Articoli EM sostitutivi: {len(selezionati)}")
    return selezionati, riserva


def componi_selezione(candidati):
    """Restituisce (articoli, stato).
    stato = {"n_niv": int, "n_em": int, "filtro_ko": bool}"""
    n_tot = cfg.ARTICOLI_FINALI
    niv = filtra_niv(candidati, n_tot)

    if niv is None:  # il filtro non ha risposto: ripiego sui piu' recenti
        ordinati = sorted(
            candidati,
            key=lambda a: a["pubdate_dt"] or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )[:n_tot]
        for a in ordinati:
            a["origine"] = "em"
        return ordinati, {"n_niv": 0, "n_em": len(ordinati), "filtro_ko": True}

    mancanti = n_tot - len(niv)
    if mancanti <= 0 or not cfg.INTEGRA_CON_EM:
        return niv, {"n_niv": len(niv), "n_em": 0, "filtro_ko": False}

    log.info(f"Mancano {mancanti} articoli NIV: integro con medicina d'urgenza")
    em = filtra_em(candidati, {a["pmid"] for a in niv}, mancanti)
    em, riserva = em
    articoli = niv + em

    # Riempimento minimo: solo se il digest resta sotto MINIMO_ARTICOLI si attinge
    # prima alla riserva scartata per diversita', poi ai piu' recenti.
    if len(articoli) < cfg.MINIMO_ARTICOLI:
        log.warning(
            f"Solo {len(articoli)} articoli (minimo {cfg.MINIMO_ARTICOLI}): "
            "completo con riserva e poi per data"
        )
        gia = {a["pmid"] for a in articoli}
        altri = sorted(
            [a for a in candidati if a["pmid"] not in gia
             and a["pmid"] not in {r["pmid"] for r in riserva}],
            key=lambda a: a["pubdate_dt"] or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        for a in riserva + altri:
            if len(articoli) >= cfg.MINIMO_ARTICOLI:
                break
            if a["pmid"] in gia:
                continue
            a["origine"] = "em"
            articoli.append(a)
            gia.add(a["pmid"])
            em.append(a)

    return articoli, {"n_niv": len(niv), "n_em": len(articoli) - len(niv), "filtro_ko": False}


# ═══════════════════════════════════════════════════════════════════════════════
# SINTESI
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_sintesi_blocco(testo):
    """Estrae SINTESI e RILEVANZA da un blocco di risposta."""
    sintesi_m   = re.search(r"SINTESI:\s*([\s\S]+?)(?=\nRILEVANZA:|\Z)", testo)
    rilevanza_m = re.search(r"RILEVANZA:\s*(.+)", testo)
    return (
        sintesi_m.group(1).strip() if sintesi_m else "",
        rilevanza_m.group(1).strip() if rilevanza_m else "",
    )


def _prompt_sintesi(origine):
    """Il taglio della sintesi segue l'origine dell'articolo: quelli NIV vengono
    letti in chiave ventilatoria, i sostitutivi in chiave di medicina d'urgenza."""
    if origine == "em":
        return cfg.PROMPT_SINTESI_MULTI_EM, cfg.PROMPT_SINTESI_EM, cfg.SYSTEM_SINTESI_EM
    return cfg.PROMPT_SINTESI_MULTI, cfg.PROMPT_SINTESI, cfg.SYSTEM_SINTESI_NIV


def sintetizza(art):
    """Sintesi di un singolo articolo (fallback)."""
    _, prompt_singolo, system = _prompt_sintesi(art.get("origine"))
    prompt = prompt_singolo.format(
        pmid=art["pmid"],
        titolo=art["titolo"],
        autori=art["autori"],
        rivista=art["rivista"],
        data=art["data"],
        abstract=art["abstract"][:2000] if art["abstract"] else "(non disponibile)",
    )
    try:
        r = chiama_claude(
            prompt,
            max_tokens=cfg.MAX_TOKENS_SINTESI_SINGOLA,
            system=system,
            temperature=cfg.TEMPERATURE_SINTESI,
        )
        sintesi, rilevanza = _parse_sintesi_blocco(r)
        art["sintesi_it"] = sintesi or r[:400]
        art["rilevanza"]  = rilevanza
    except Exception as e:
        log.error(f"Sintesi fallita {art['pmid']}: {e}")
        art["sintesi_it"] = ""
        art["rilevanza"]  = ""
    return art


def _sintetizza_gruppo(articoli, origine):
    """Sintetizza in UNA chiamata tutti gli articoli della stessa origine."""
    if not articoli:
        return
    prompt_multi, _, system = _prompt_sintesi(origine)
    blocchi = [
        f"PMID: {a['pmid']}\n"
        f"Titolo: {a['titolo']}\n"
        f"Autori: {a['autori']}\n"
        f"Rivista: {a['rivista']} ({a['data']})\n"
        f"Abstract: {a['abstract'][:2000] if a['abstract'] else '(non disponibile)'}"
        for a in articoli
    ]
    prompt = prompt_multi.format(articoli="\n\n---\n\n".join(blocchi))
    log.info(f"Sintesi gruppo '{origine}': {len(articoli)} articoli in una chiamata")

    per_pmid = {}
    try:
        risposta = chiama_claude(
            prompt,
            max_tokens=cfg.MAX_TOKENS_SINTESI_MULTI,
            system=system,
            temperature=cfg.TEMPERATURE_SINTESI,
        )
        pezzi = re.split(r"###\s*PMID:\s*(\d{7,9})", risposta)
        for i in range(1, len(pezzi) - 1, 2):
            pmid, blocco = pezzi[i], pezzi[i + 1]
            sintesi, rilevanza = _parse_sintesi_blocco(blocco)
            if sintesi:
                per_pmid[pmid] = (sintesi, rilevanza)
    except Exception as e:
        log.error(f"Sintesi multipla '{origine}' fallita: {e}")

    for art in articoli:
        if art["pmid"] in per_pmid:
            art["sintesi_it"], art["rilevanza"] = per_pmid[art["pmid"]]
        else:
            log.warning(f"PMID {art['pmid']} assente dalla sintesi multipla — fallback singolo")
            sintetizza(art)
            time.sleep(1)


def sintetizza_articoli(articoli):
    """Due chiamate al massimo: una per gli articoli NIV, una per i sostitutivi EM."""
    _sintetizza_gruppo([a for a in articoli if a.get("origine") != "em"], "niv")
    _sintetizza_gruppo([a for a in articoli if a.get("origine") == "em"], "em")
    return articoli


# ═══════════════════════════════════════════════════════════════════════════════
# RENDERING
# ═══════════════════════════════════════════════════════════════════════════════

def testo_nota(stato):
    """Nota sulla composizione del numero. None se il digest e' tutto NIV."""
    n_niv, n_em = stato["n_niv"], stato["n_em"]
    if stato["filtro_ko"]:
        return ("Il filtro tematico non e' stato disponibile in questa esecuzione: "
                "di seguito gli articoli piu' recenti delle riviste monitorate.")
    if n_em == 0:
        return None
    if n_niv == 0:
        return (f"Questa settimana non sono stati pubblicati articoli dedicati al supporto "
                f"ventilatorio. Al loro posto {n_em} articoli di medicina d'urgenza, "
                f"selezionati con i criteri di EM Weekly Digest: impatto sulla decisione "
                f"in Pronto Soccorso, applicabilita' nel nostro contesto, qualita' "
                f"metodologica, novita'.")
    return (f"Articoli sul supporto ventilatorio disponibili questa settimana: {n_niv}. "
            f"Le altre {n_em} posizioni sono occupate da articoli di medicina d'urgenza, "
            f"selezionati con i criteri di EM Weekly Digest.")


def _badge_html(origine):
    if origine == "em":
        return (f'<span style="font-family:monospace;font-size:9px;font-weight:700;'
                f'letter-spacing:1px;color:#ffffff;background:{cfg.COLOR_EM};'
                f'padding:2px 6px;border-radius:3px;">MED. URGENZA</span> ')
    return (f'<span style="font-family:monospace;font-size:9px;font-weight:700;'
            f'letter-spacing:1px;color:#ffffff;background:{cfg.COLOR_ACCENT};'
            f'padding:2px 6px;border-radius:3px;">NIV</span> ')


def build_html(articoli, stato):
    wl = numero_settimana()
    arts = ""
    for i, a in enumerate(articoli):
        colore = cfg.COLOR_EM if a.get("origine") == "em" else cfg.COLOR_ACCENT
        doi = (
            f' | <a href="https://doi.org/{esc(a["doi"])}" '
            f'style="font-family:monospace;font-size:11px;color:#0a4d68;text-decoration:none;">DOI</a>'
        ) if a.get("doi") else ""
        syn = ""
        if a.get("sintesi_it"):
            rel = (
                f'<br/><strong style="color:{colore};">{esc(a["rilevanza"])}</strong>'
                if a.get("rilevanza") else ""
            )
            syn = (
                f'<div style="background:#f4f8f4;border-left:3px solid {colore};'
                f'padding:12px 16px;font-family:Georgia,serif;font-size:14px;color:#2a2a2a;'
                f'line-height:1.6;margin-bottom:12px;">{esc(a["sintesi_it"])}{rel}</div>'
            )
        ab = ""
        if a.get("abstract"):
            ab = (
                '<details style="margin-bottom:10px;"><summary style="font-family:monospace;'
                'font-size:10px;color:#0a4d68;cursor:pointer;letter-spacing:1px;'
                'text-transform:uppercase;list-style:none;">Abstract (EN)</summary>'
                '<p style="font-family:Georgia,serif;font-size:12px;color:#666;line-height:1.65;'
                'margin-top:8px;padding:10px 12px;background:#fafafa;border:1px solid #eee;">'
                f'{esc(a["abstract"])}</p></details>'
            )
        arts += (
            '<tr><td style="padding:28px 32px 24px;border-bottom:1px solid #dde8dd;">'
            '<div style="margin-bottom:10px;">'
            f'<span style="font-family:monospace;font-size:12px;color:{colore};font-weight:700;">{str(i+1).zfill(2)}</span> '
            f'{_badge_html(a.get("origine"))}'
            f'<span style="font-family:monospace;font-size:11px;color:#aaa;">{esc(a["rivista"])} - {esc(a["data"])}</span></div>'
            f'<a href="{esc(a["url"])}" style="font-family:Georgia,serif;font-size:19px;font-weight:700;'
            f'color:#1a1a1a;text-decoration:none;line-height:1.35;display:block;margin-bottom:6px;">{esc(a["titolo"])}</a>'
            f'<div style="font-family:monospace;font-size:12px;color:#999;font-style:italic;margin-bottom:14px;">{esc(a["autori"])}</div>'
            f'{syn}{ab}'
            f'<div><a href="{esc(a["url"])}" style="font-family:monospace;font-size:11px;color:#0a4d68;text-decoration:none;">PubMed {esc(a["pmid"])}</a>{doi}</div>'
            '</td></tr>'
        )
    niv_str = " - ".join(r["nlmta"] for r in cfg.RIVISTE_NIV)
    nota = testo_nota(stato)
    disclaimer = (
        '<tr><td style="background:#fff8e1;padding:14px 32px;border-bottom:1px solid #f0e0a0;">'
        '<p style="font-family:Georgia,serif;font-size:13px;color:#8a6d00;margin:0;line-height:1.5;">'
        f'<strong>Nota:</strong> {esc(nota)}</p></td></tr>'
    ) if nota else ''
    logo_html = (
        f'<img src="{cfg.LOGO_URL}" alt="Pronto Soccorso Area Critica" '
        f'style="display:block;height:84px;width:auto;margin-bottom:14px;'
        f'background:#ffffff;padding:6px 10px;border-radius:6px;" />'
    ) if getattr(cfg, "LOGO_URL", "") else ""
    return f'''<!DOCTYPE html>
<html lang="it">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{esc(cfg.NOME_NEWSLETTER)}</title></head>
<body style="margin:0;padding:0;background:#eaf0ea;">
<table width="100%" cellpadding="0" cellspacing="0" bgcolor="#eaf0ea">
  <tr><td align="center" style="padding:32px 16px;">
    <table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;">
      <tr>
        <td style="background:{cfg.COLOR_DARK};padding:0;">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr><td style="background:{cfg.COLOR_ACCENT};height:4px;"></td></tr>
            <tr>
              <td style="padding:28px 32px 24px;">
                {logo_html}
                <div style="font-family:monospace;font-size:10px;color:#778;letter-spacing:3px;text-transform:uppercase;margin-bottom:8px;">
                  {esc(cfg.NOME_SERVIZIO)}
                </div>
                <h1 style="font-family:Georgia,serif;font-size:32px;color:#ffffff;margin:0 0 6px;font-weight:700;">
                  NIV Weekly<br/>
                  <em style="color:{cfg.COLOR_ACCENT};font-style:italic;">Digest a cura di Francesco Panero</em>
                </h1>
                <div style="font-family:monospace;font-size:11px;color:#667;">
                  Settimana {wl["settimana"]} - {wl["giorno"]} {wl["mese"]} {wl["anno"]} - {len(articoli)} articoli
                  ({stato["n_niv"]} NIV / {stato["n_em"]} med. urgenza)
                </div>
              </td>
              <td style="padding:28px 32px 24px;text-align:right;vertical-align:top;">
                <div style="font-family:monospace;font-size:52px;font-weight:700;color:#2a3a2e;letter-spacing:-3px;line-height:1;">
                  {str(wl["settimana"]).zfill(2)}
                </div>
                <div style="font-family:monospace;font-size:10px;color:#556;letter-spacing:3px;">WEEK</div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
      <tr>
        <td style="background:#f0f5f0;padding:12px 32px;border-bottom:2px solid {cfg.COLOR_DARK};">
          <span style="font-family:monospace;font-size:10px;color:#889;letter-spacing:1px;">NIV: {niv_str} + generaliste</span>
        </td>
      </tr>
      {disclaimer}
      <tr><td style="background:#ffffff;"><table width="100%" cellpadding="0" cellspacing="0">{arts}</table></td></tr>
      <tr>
        <td style="background:{cfg.COLOR_DARK};padding:22px 32px;">
          <p style="font-family:monospace;font-size:10px;color:#556;margin:0;line-height:1.8;">
            Generato con {esc(cfg.ANTHROPIC_MODEL)} (Anthropic) a cura di Francesco Panero &middot; Fonte dati: PubMed RSS feeds<br/>
            Le sintesi sono prodotte da AI e devono essere verificate prima dell'applicazione clinica.<br/>
            <a href="{cfg.NEWSLETTER_PAGE_URL}" style="color:{cfg.COLOR_ACCENT};">Condividi: invita un collega</a> · <a href="{cfg.NEWSLETTER_PAGE_URL}#unsub" style="color:#999;">Disiscriviti</a>
          </p>
        </td>
      </tr>
    </table>
  </td></tr>
</table></body></html>'''


def invia_email(oggetto, html_body, destinatari):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = oggetto
    msg["From"]    = f"NIV Weekly Digest <{cfg.GMAIL_USER}>"
    msg["To"]      = cfg.GMAIL_USER
    msg["Bcc"]     = ", ".join(destinatari)
    msg.attach(MIMEText(f"NIV Weekly Digest - {oggetto}", "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(cfg.GMAIL_USER, cfg.GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
        log.info(f"Email inviata a {len(destinatari)} destinatari (Bcc)")
        return True
    except Exception as e:
        log.error(f"Invio fallito: {e}")
        return False


# ─── Telegram ────────────────────────────────────────────────

def telegram_send_message(bot_token, chat_id, text):
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read().decode("utf-8"))
        if not resp.get("ok"):
            log.error(f"Telegram API errore: {resp}")
            return False
        return True
    except Exception as e:
        log.error(f"Telegram invio fallito: {e}")
        return False


def build_tg_header(articoli, stato):
    wl = numero_settimana()
    testo = (
        f"🫁 <b>NIV Weekly Digest</b>\n"
        f"Settimana {wl['settimana']} · {wl['giorno']} {wl['mese']} {wl['anno']}\n"
        f"<i>{esc(cfg.NOME_SERVIZIO)}</i>\n\n"
        f"📚 {len(articoli)} articoli: {stato['n_niv']} sul supporto ventilatorio, "
        f"{stato['n_em']} di medicina d'urgenza\n"
    )
    nota = testo_nota(stato)
    if nota:
        testo += f"\n⚠️ <i>{esc(nota)}</i>\n"
    return testo + ("━" * 25)


def build_tg_articolo(i, a):
    """NB: parse_mode=HTML richiede l'escape di <, > e & nei testi dinamici,
    altrimenti l'API rifiuta il messaggio."""
    tag = "🚑 MED. URGENZA" if a.get("origine") == "em" else "🫁 NIV"
    parti = [
        f"<b>{i}. {esc(a['titolo'])}</b>",
        f"<code>{tag}</code> · <i>{esc(a['rivista'])} · {esc(a['data'])}</i>",
    ]
    if a.get("autori"):
        parti.append(f"👤 {esc(a['autori'])}")
    parti.append("")
    if a.get("sintesi_it"):
        parti.append(esc(a["sintesi_it"]))
    if a.get("rilevanza"):
        parti.append(f"\n🎯 <b>Rilevanza:</b> {esc(a['rilevanza'])}")
    parti.append("")
    link = f'🔗 <a href="{esc(a["url"])}">PubMed {esc(a["pmid"])}</a>'
    if a.get("doi"):
        link += f' · <a href="https://doi.org/{esc(a["doi"])}">DOI</a>'
    parti.append(link)
    return "\n".join(parti)


def build_tg_footer():
    return (
        f"{'━' * 25}\n"
        f"📬 <a href=\"{cfg.NEWSLETTER_PAGE_URL}\">Iscriviti alla newsletter via email</a>\n"
        f"🤖 Sintesi generate con Claude (Anthropic) · Fonte: PubMed\n"
        f"⚠️ Le sintesi AI vanno verificate sulle fonti primarie."
    )


def invia_telegram(articoli, stato):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not bot_token or not chat_id:
        log.warning("TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID mancanti - salto Telegram")
        return False
    successi = 0
    if telegram_send_message(bot_token, chat_id, build_tg_header(articoli, stato)):
        successi += 1
    time.sleep(1)
    for i, a in enumerate(articoli, 1):
        msg = build_tg_articolo(i, a)
        if len(msg) > 4096:
            msg = msg[:4090] + "\n…"
        if telegram_send_message(bot_token, chat_id, msg):
            successi += 1
        time.sleep(1)
    if telegram_send_message(bot_token, chat_id, build_tg_footer()):
        successi += 1
    totale = len(articoli) + 2
    log.info(f"Telegram: inviati {successi}/{totale} messaggi al canale")
    return successi == totale


def main():
    cfg.valida_config()
    wl = numero_settimana()
    log.info(f"=== NIV Weekly Digest - settimana {wl['settimana']}/{wl['anno']} ===")

    destinatari = carica_destinatari()

    candidati = raccogli_candidati(cfg.GIORNI_RICERCA)
    if len(candidati) < cfg.ARTICOLI_FINALI + 3:
        log.warning(f"Solo {len(candidati)} a {cfg.GIORNI_RICERCA}g - estendo a {cfg.GIORNI_RICERCA_ESTESO}g")
        candidati = raccogli_candidati(cfg.GIORNI_RICERCA_ESTESO)
    if not candidati:
        log.error("Nessun articolo trovato")
        return False

    selezionati, stato = componi_selezione(candidati)
    log.info(f"Selezione finale: {len(selezionati)} articoli "
             f"({stato['n_niv']} NIV + {stato['n_em']} EM)")
    if not selezionati:
        log.error("Selezione vuota")
        return False

    selezionati = sintetizza_articoli(selezionati)

    html_body = build_html(selezionati, stato)

    ok_email = invia_email(
        f"NIV Weekly Digest - Settimana {wl['settimana']}/{wl['anno']}",
        html_body, destinatari,
    )
    ok_telegram = invia_telegram(selezionati, stato)

    log.info("=== Email: OK ===" if ok_email else "=== Email: FALLITO ===")
    log.info("=== Telegram: OK ===" if ok_telegram else "=== Telegram: FALLITO o non configurato ===")
    return ok_email


if __name__ == "__main__":
    main()
