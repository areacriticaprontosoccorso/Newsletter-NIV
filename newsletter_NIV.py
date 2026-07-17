"""
NIV Weekly Digest — Newsletter insufficienza respiratoria acuta
Area Critica e Pronto Soccorso San Giovanni Bosco, Torino
Comando: python newsletter_NIV.py
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


def esc(s):
    """Escape per testo dinamico inserito nell'HTML (email e Telegram)."""
    return html.escape(str(s or ""), quote=True)


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
    articoli = []
    for item in root.findall(".//item"):
        titolo  = (item.findtext("title") or "").strip()
        link    = (item.findtext("link") or "").strip()
        desc    = item.findtext("description") or ""
        pubdate = parse_pubdate(item.findtext("pubDate"))
        pmid    = estrai_pmid(item)
        if not pmid or not titolo:
            continue
        articoli.append({
            "pmid":       pmid,
            "titolo":     titolo.rstrip("."),
            "autori":     estrai_autori(item),
            "rivista":    rivista["nome"],
            "data":       pubdate.strftime("%Y %b %d") if pubdate else "",
            "pubdate_dt": pubdate,
            "doi":        estrai_doi(item),
            "abstract":   estrai_abstract(desc),
            "url":        link or f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        })
    log.info(f"  {rivista['nlmta']}: {len(articoli)} articoli")
    return articoli


def raccogli_candidati(giorni=7):
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
    ok = [a for a in unici if a["abstract"] and len(a["abstract"]) > 100]
    log.info(f"Unici: {len(unici)}, con abstract: {len(ok)}")
    return ok


def chiama_claude(prompt, max_tokens=1500):
    payload = json.dumps({
        "model":      cfg.ANTHROPIC_MODEL,
        "max_tokens": max_tokens,
        # Sonnet 5 ha l'adaptive thinking attivo di default: lo disattiviamo,
        # cosi' la risposta e' solo testo e max_tokens non viene speso in thinking.
        "thinking":   {"type": "disabled"},
        "messages":   [{"role": "user", "content": prompt}],
    }).encode("utf-8")
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
            # Estrai il primo blocco di tipo "text" (content[0] non e' garantito
            # essere testo: possono esserci blocchi "thinking").
            blocchi = data.get("content", [])
            testo = next((b.get("text", "") for b in blocchi if b.get("type") == "text"), "")
            if not testo:
                raise RuntimeError(f"Nessun blocco di testo nella risposta API: {str(data)[:300]}")
            return testo.strip()
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


def filtra_top(candidati):
    """Ritorna (selezionati, fallback). fallback=True quando la selezione non è
    frutto del filtro tematico (Claude non ha risposto o non ha trovato nulla):
    in quel caso email e Telegram mostrano il disclaimer."""
    if len(candidati) <= cfg.ARTICOLI_FINALI:
        return candidati, True
    blocchi = [
        f"PMID: {a['pmid']}\nRIVISTA: {a['rivista']}\nTITOLO: {a['titolo']}\nABSTRACT: {a['abstract'][:700]}"
        for a in candidati
    ]
    prompt = cfg.PROMPT_FILTRO_NIV.format(
        n=cfg.ARTICOLI_FINALI,
        articoli="\n---\n".join(blocchi),
    )
    log.info(f"Claude filtra {len(candidati)} -> {cfg.ARTICOLI_FINALI}")
    try:
        risposta = chiama_claude(prompt, max_tokens=200)
        pmids = re.findall(r"\b\d{7,9}\b", risposta)[:cfg.ARTICOLI_FINALI]
    except Exception as e:
        log.error(f"Filtro Claude fallito ({e}); fallback ai piu' recenti")
        pmids = []
    log.info(f"Claude selezionati: {pmids}")
    m = {a["pmid"]: a for a in candidati}
    selezionati = [m[p] for p in pmids if p in m]
    if not selezionati:
        log.warning("Claude non ha selezionato nulla: fallback ai piu' recenti")
        ordinati = sorted(
            candidati,
            key=lambda a: a["pubdate_dt"] or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return ordinati[:cfg.ARTICOLI_FINALI], True
    return selezionati, False


def _parse_sintesi_blocco(testo):
    """Estrae SINTESI e RILEVANZA da un blocco di risposta."""
    sintesi_m   = re.search(r"SINTESI:\s*([\s\S]+?)(?=\nRILEVANZA:|\Z)", testo)
    rilevanza_m = re.search(r"RILEVANZA:\s*(.+)", testo)
    return (
        sintesi_m.group(1).strip() if sintesi_m else "",
        rilevanza_m.group(1).strip() if rilevanza_m else "",
    )


def sintetizza(art):
    """Sintesi di un singolo articolo (fallback)."""
    prompt = cfg.PROMPT_SINTESI.format(
        titolo=art["titolo"],
        autori=art["autori"],
        rivista=art["rivista"],
        data=art["data"],
        abstract=art["abstract"][:2000] if art["abstract"] else "(non disponibile)",
    )
    try:
        r = chiama_claude(prompt, max_tokens=600)
        sintesi, rilevanza = _parse_sintesi_blocco(r)
        art["sintesi_it"] = sintesi or r[:400]
        art["rilevanza"]  = rilevanza
    except Exception as e:
        log.error(f"Sintesi fallita {art['pmid']}: {e}")
        art["sintesi_it"] = ""
        art["rilevanza"]  = ""
    return art


def sintetizza_articoli(articoli):
    """Sintetizza tutti gli articoli in UNA chiamata API.
    Se dalla risposta manca qualche articolo, recupera i mancanti con
    chiamate singole (fallback)."""
    blocchi = []
    for a in articoli:
        blocchi.append(
            f"PMID: {a['pmid']}\n"
            f"Titolo: {a['titolo']}\n"
            f"Autori: {a['autori']}\n"
            f"Rivista: {a['rivista']} ({a['data']})\n"
            f"Abstract: {a['abstract'][:2000] if a['abstract'] else '(non disponibile)'}"
        )
    prompt = cfg.PROMPT_SINTESI_MULTI.format(articoli="\n\n---\n\n".join(blocchi))
    log.info(f"Sintesi unica di {len(articoli)} articoli con Claude…")

    per_pmid = {}
    try:
        risposta = chiama_claude(prompt, max_tokens=4000)
        pezzi = re.split(r"###\s*PMID:\s*(\d{7,9})", risposta)
        for i in range(1, len(pezzi) - 1, 2):
            pmid, blocco = pezzi[i], pezzi[i + 1]
            sintesi, rilevanza = _parse_sintesi_blocco(blocco)
            if sintesi:
                per_pmid[pmid] = (sintesi, rilevanza)
    except Exception as e:
        log.error(f"Sintesi multipla fallita: {e}")

    for art in articoli:
        if art["pmid"] in per_pmid:
            art["sintesi_it"], art["rilevanza"] = per_pmid[art["pmid"]]
        else:
            log.warning(f"PMID {art['pmid']} assente dalla sintesi multipla — fallback singolo")
            sintetizza(art)
            time.sleep(1)
    return articoli


def build_html(articoli, fallback=False):
    wl = numero_settimana()
    arts = ""
    for i, a in enumerate(articoli):
        doi = (
            f' | <a href="https://doi.org/{esc(a["doi"])}" '
            f'style="font-family:monospace;font-size:11px;color:#0a4d68;text-decoration:none;">DOI</a>'
        ) if a.get("doi") else ""
        syn = ""
        if a.get("sintesi_it"):
            rel = (
                f'<br/><strong style="color:{cfg.COLOR_ACCENT};">{esc(a["rilevanza"])}</strong>'
                if a.get("rilevanza") else ""
            )
            syn = (
                f'<div style="background:#f4f8f4;border-left:3px solid {cfg.COLOR_ACCENT};'
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
            f'<span style="font-family:monospace;font-size:12px;color:{cfg.COLOR_ACCENT};font-weight:700;">{str(i+1).zfill(2)}</span> '
            f'<span style="font-family:monospace;font-size:11px;color:#aaa;">{esc(a["rivista"])} - {esc(a["data"])}</span></div>'
            f'<a href="{esc(a["url"])}" style="font-family:Georgia,serif;font-size:19px;font-weight:700;'
            f'color:#1a1a1a;text-decoration:none;line-height:1.35;display:block;margin-bottom:6px;">{esc(a["titolo"])}</a>'
            f'<div style="font-family:monospace;font-size:12px;color:#999;font-style:italic;margin-bottom:14px;">{esc(a["autori"])}</div>'
            f'{syn}{ab}'
            f'<div><a href="{esc(a["url"])}" style="font-family:monospace;font-size:11px;color:#0a4d68;text-decoration:none;">PubMed {esc(a["pmid"])}</a>{doi}</div>'
            '</td></tr>'
        )
    niv_str = " - ".join(r["nlmta"] for r in cfg.RIVISTE_NIV)
    disclaimer = (
        '<tr><td style="background:#fff8e1;padding:14px 32px;border-bottom:1px solid #f0e0a0;">'
        '<p style="font-family:Georgia,serif;font-size:13px;color:#8a6d00;margin:0;line-height:1.5;">'
        '<strong>Nota:</strong> questa settimana non sono stati individuati articoli dedicati '
        'specificamente alla ventilazione non invasiva. Di seguito una selezione di articoli '
        'recenti su temi respiratori e di area critica correlati.</p></td></tr>'
    ) if fallback else ''
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


def build_tg_header(articoli, fallback):
    wl = numero_settimana()
    testo = (
        f"🫁 <b>NIV Weekly Digest</b>\n"
        f"Settimana {wl['settimana']} · {wl['giorno']} {wl['mese']} {wl['anno']}\n"
        f"<i>{esc(cfg.NOME_SERVIZIO)}</i>\n\n"
        f"📚 {len(articoli)} articoli questa settimana\n"
    )
    if fallback:
        testo += ("\n⚠️ <i>Questa settimana non sono stati individuati articoli dedicati "
                  "specificamente alla NIV. Di seguito una selezione di articoli recenti su "
                  "temi respiratori e di area critica correlati.</i>\n")
    return testo + ("━" * 25)


def build_tg_articolo(i, a):
    """NB: parse_mode=HTML richiede l'escape di <, > e & nei testi dinamici,
    altrimenti l'API rifiuta il messaggio."""
    parti = [f"<b>{i}. {esc(a['titolo'])}</b>", f"<i>{esc(a['rivista'])} · {esc(a['data'])}</i>"]
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


def invia_telegram(articoli, fallback=False):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not bot_token or not chat_id:
        log.warning("TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID mancanti - salto Telegram")
        return False
    successi = 0
    if telegram_send_message(bot_token, chat_id, build_tg_header(articoli, fallback)):
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

    candidati = raccogli_candidati(giorni=7)
    if len(candidati) < cfg.ARTICOLI_FINALI + 3:
        log.warning(f"Solo {len(candidati)} a 7g - estendo a 14g")
        candidati = raccogli_candidati(giorni=14)
    if not candidati:
        log.error("Nessun articolo trovato")
        return False

    selezionati, fallback = filtra_top(candidati)
    log.info(f"Selezionati {len(selezionati)} articoli{' (fallback)' if fallback else ''}")
    if not selezionati:
        log.error("Filtro vuoto")
        return False

    selezionati = sintetizza_articoli(selezionati)

    html_body = build_html(selezionati, fallback)

    ok_email = invia_email(f"NIV Weekly Digest - Settimana {wl['settimana']}/{wl['anno']}", html_body, destinatari)
    ok_telegram = invia_telegram(selezionati, fallback)

    log.info("=== Email: OK ===" if ok_email else "=== Email: FALLITO ===")
    log.info("=== Telegram: OK ===" if ok_telegram else "=== Telegram: FALLITO o non configurato ===")
    return ok_email


if __name__ == "__main__":
    main()
