"""
NIV Weekly Digest — Newsletter insufficienza respiratoria acuta
Pronto Soccorso San Giovanni Bosco, Torino
"""

import os, re, json, time, logging, smtplib
import urllib.request, urllib.error
import xml.etree.ElementTree as ET
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone
import config as cfg

def carica_destinatari():
    try:
        sub_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "subscribers.json")
        with open(sub_path, encoding="utf-8") as f:
            subs = json.load(f)
        emails = [
            s["email"].strip()
            for s in subs
            if "@" in s.get("email", "") and " " not in s.get("email", "")
        ]
        fisso = "francesco.panero@aslcittaditorino.it"
        if fisso not in emails:
            emails.insert(0, fisso)
        print(f"Destinatari caricati: {len(emails)}")
        return emails
    except Exception as e:
        print(f"Errore carica subscribers: {e}")
        return ["francesco.panero@aslcittaditorino.it"]

DESTINATARI = carica_destinatari()
TUTTE_RIVISTE = cfg.RIVISTE_NIV + cfg.RIVISTE
ARTICOLI_FINALI = 5
COLOR_ACCENT = "#2e7d32"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(cfg.LOG_FILE, encoding="utf-8"), logging.StreamHandler()])
log = logging.getLogger("newsletter_niv")

def numero_settimana():
    now = datetime.now()
    mesi = ["Gennaio","Febbraio","Marzo","Aprile","Maggio","Giugno","Luglio","Agosto","Settembre","Ottobre","Novembre","Dicembre"]
    return {"settimana": now.isocalendar()[1], "anno": now.year, "giorno": now.day, "mese": mesi[now.month - 1]}

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
    if not s: return None
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(s)
    except: return None

def estrai_abstract(desc):
    if not desc: return ""
    t = re.sub(r"<[^>]+>", " ", desc)
    t = t.replace("&nbsp;"," ").replace("&amp;","&").replace("&lt;","<").replace("&gt;",">").replace("&quot;",'"')
    t = re.sub(r"PMID:\s*\d+.*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"DOI:\s*[\w./-]+", "", t, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", t).strip()[:2500]

def estrai_pmid(item):
    link_el = item.find("link")
    if link_el is not None and link_el.text:
        m = re.search(r"/(\d{7,9})/?", link_el.text)
        if m: return m.group(1)
    for ident in item.findall("dc:identifier", NS):
        if ident.text and ident.text.startswith("pmid:"):
            return ident.text.replace("pmid:","").strip()
    return ""

def estrai_doi(item):
    for ident in item.findall("dc:identifier", NS):
        if ident.text and ident.text.startswith("doi:"):
            return ident.text.replace("doi:","").strip()
    return ""

def estrai_autori(item):
    nomi = [c.text for c in item.findall("dc:creator", NS) if c.text]
    if not nomi: return ""
    if len(nomi) > 3: return ", ".join(nomi[:3]) + " et al."
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
        titolo = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = item.findtext("description") or ""
        pubdate = parse_pubdate(item.findtext("pubDate"))
        pmid = estrai_pmid(item)
        if not pmid or not titolo: continue
        articoli.append({"pmid": pmid, "titolo": titolo.rstrip("."), "autori": estrai_autori(item),
            "rivista": rivista["nome"], "data": pubdate.strftime("%Y %b %d") if pubdate else "",
            "pubdate_dt": pubdate, "doi": estrai_doi(item), "abstract": estrai_abstract(desc),
            "url": link or f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"})
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
    payload = json.dumps({"model": cfg.ANTHROPIC_MODEL, "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]}).encode("utf-8")
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=payload,
        headers={"Content-Type": "application/json", "x-api-key": cfg.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read().decode("utf-8"))
        return data["content"][0]["text"].strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        raise RuntimeError(f"API errore {e.code}: {body[:400]}")

FILTRO = "Sei un medico di PS/terapia intensiva esperto in insufficienza respiratoria acuta e supporto ventilatorio. Dalla lista sotto, seleziona i 5 articoli PIU' PERTINENTI alla gestione del paziente con problemi respiratori acuti. Sono PERTINENTI gli articoli che trattano, anche solo in parte: ventilazione non invasiva (NIV/BiPAP/BiLevel), CPAP, High-Flow Nasal Cannula (HFNC/HFNO), ossigenoterapia, insufficienza respiratoria acuta ipossiemica o ipercapnica, ARDS e strategie ventilatorie, edema polmonare acuto cardiogeno, riacutizzazione BPCO, asma acuto grave, polmonite con insufficienza respiratoria, ventilazione meccanica invasiva, weaning e post-estubazione, intubazione e gestione delle vie aeree nel paziente critico, monitoraggio respiratorio, emogasanalisi e scambi gassosi, sedazione/analgesia nel paziente ventilato, outcome del paziente con insufficienza respiratoria. Dai priorita' agli articoli con focus ventilatorio non invasivo, ma includi anche i temi correlati sopra se mancano articoli strettamente su NIV. Escludi solo cio' che e' chiaramente fuori tema (cardiologia interventistica, neurologia, oncologia, nefrologia, endocrinologia, chirurgia non toracica) e i case reports, lettere, errata, commenti. Se trovi meno di 5 articoli pertinenti restituisci quelli che ci sono; se nessuno e' pertinente in senso stretto, scegli comunque i 5 piu' vicini al tema respiratorio/critico. ARTICOLI:\n{articoli}\n\nRestituisci SOLO i PMID, uno per riga, nessun commento."


def filtra_top(candidati):
    if len(candidati) <= ARTICOLI_FINALI: return candidati, True
    blocchi = [f"PMID: {a['pmid']}\nRIVISTA: {a['rivista']}\nTITOLO: {a['titolo']}\nABSTRACT: {a['abstract'][:700]}" for a in candidati]
    risposta = chiama_claude(FILTRO.format(articoli="\n---\n".join(blocchi)), 200)
    pmids = re.findall(r"\b\d{7,9}\b", risposta)[:ARTICOLI_FINALI]
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
        return ordinati[:ARTICOLI_FINALI], True
    return selezionati, False

def sintetizza(art):
    prompt = cfg.PROMPT_SINTESI.format(titolo=art["titolo"], autori=art["autori"],
        rivista=art["rivista"], data=art["data"],
        abstract=art["abstract"][:2000] if art["abstract"] else "(non disponibile)")
    try:
        r = chiama_claude(prompt, 600)
        sm = re.search(r"^SINTESI:\s*([\s\S]+?)(?=\nRILEVANZA:)", r, re.MULTILINE)
        rm = re.search(r"^RILEVANZA:\s*(.+)", r, re.MULTILINE)
        art["sintesi_it"] = sm.group(1).strip() if sm else r[:400]
        art["rilevanza"] = rm.group(1).strip() if rm else ""
    except Exception as e:
        log.error(f"Sintesi fallita {art['pmid']}: {e}")
        art["sintesi_it"] = ""
        art["rilevanza"] = ""
    return art

def build_html(articoli, fallback=False):
    wl = numero_settimana()
    arts = ""
    for i, a in enumerate(articoli):
        doi = f' | <a href="https://doi.org/{a["doi"]}" style="font-family:monospace;font-size:11px;color:#0a4d68;text-decoration:none;">DOI</a>' if a.get("doi") else ""
        syn = ""
        if a.get("sintesi_it"):
            rel = f'<br/><strong style="color:{COLOR_ACCENT};">{a["rilevanza"]}</strong>' if a.get("rilevanza") else ""
            syn = f'<div style="background:#f4f8f4;border-left:3px solid {COLOR_ACCENT};padding:12px 16px;font-family:Georgia,serif;font-size:14px;color:#2a2a2a;line-height:1.6;margin-bottom:12px;">{a["sintesi_it"]}{rel}</div>'
        ab = ""
        if a.get("abstract"):
            ab = f'<details style="margin-bottom:10px;"><summary style="font-family:monospace;font-size:10px;color:#0a4d68;cursor:pointer;letter-spacing:1px;text-transform:uppercase;list-style:none;">Abstract (EN)</summary><p style="font-family:Georgia,serif;font-size:12px;color:#666;line-height:1.65;margin-top:8px;padding:10px 12px;background:#fafafa;border:1px solid #eee;">{a["abstract"]}</p></details>'
        arts += f'<tr><td style="padding:28px 32px 24px;border-bottom:1px solid #dde8dd;"><div style="margin-bottom:10px;"><span style="font-family:monospace;font-size:12px;color:{COLOR_ACCENT};font-weight:700;">{str(i+1).zfill(2)}</span> <span style="font-family:monospace;font-size:11px;color:#aaa;">{a["rivista"]} - {a["data"]}</span></div><a href="{a["url"]}" style="font-family:Georgia,serif;font-size:19px;font-weight:700;color:#1a1a1a;text-decoration:none;line-height:1.35;display:block;margin-bottom:6px;">{a["titolo"]}</a><div style="font-family:monospace;font-size:12px;color:#999;font-style:italic;margin-bottom:14px;">{a["autori"]}</div>{syn}{ab}<div><a href="{a["url"]}" style="font-family:monospace;font-size:11px;color:#0a4d68;text-decoration:none;">PubMed {a["pmid"]}</a>{doi}</div></td></tr>'
    niv_str = " - ".join(r["nlmta"] for r in cfg.RIVISTE_NIV)
    disclaimer = ('<tr><td style="background:#fff8e1;padding:14px 32px;border-bottom:1px solid #f0e0a0;">'
                  '<p style="font-family:Georgia,serif;font-size:13px;color:#8a6d00;margin:0;line-height:1.5;">'
                  '<strong>Nota:</strong> questa settimana non sono stati individuati articoli dedicati '
                  'specificamente alla ventilazione non invasiva. Di seguito una selezione di articoli '
                  'recenti su temi respiratori e di area critica correlati.</p></td></tr>') if fallback else ''
    return f'''<!DOCTYPE html><html lang="it"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>{cfg.NOME_NEWSLETTER}</title></head><body style="margin:0;padding:0;background:#eaf0ea;"><table width="100%" cellpadding="0" cellspacing="0" bgcolor="#eaf0ea"><tr><td align="center" style="padding:32px 16px;"><table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;"><tr><td style="background:{cfg.COLOR_DARK};padding:0;"><table width="100%" cellpadding="0" cellspacing="0"><tr><td style="background:{COLOR_ACCENT};height:4px;"></td></tr><tr><td style="padding:28px 32px 24px;"><div style="font-family:monospace;font-size:10px;color:#778;letter-spacing:3px;text-transform:uppercase;margin-bottom:8px;">{cfg.NOME_SERVIZIO}</div><h1 style="font-family:Georgia,serif;font-size:32px;color:#ffffff;margin:0 0 6px;font-weight:700;">NIV Weekly<br/><em style="color:{COLOR_ACCENT};font-style:italic;">Digest</em></h1><div style="font-family:monospace;font-size:11px;color:#667;">Settimana {wl["settimana"]} - {wl["giorno"]} {wl["mese"]} {wl["anno"]} - {len(articoli)} articoli</div></td><td style="padding:28px 32px 24px;text-align:right;vertical-align:top;"><div style="font-family:monospace;font-size:52px;font-weight:700;color:#2a3a2e;letter-spacing:-3px;line-height:1;">{str(wl["settimana"]).zfill(2)}</div><div style="font-family:monospace;font-size:10px;color:#556;letter-spacing:3px;">WEEK</div></td></tr></table></td></tr><tr><td style="background:#f0f5f0;padding:12px 32px;border-bottom:2px solid {cfg.COLOR_DARK};"><span style="font-family:monospace;font-size:10px;color:#889;letter-spacing:1px;">NIV: {niv_str} + generaliste</span></td></tr>{disclaimer}<tr><td style="background:#ffffff;"><table width="100%" cellpadding="0" cellspacing="0">{arts}</table></td></tr><tr><td style="background:{cfg.COLOR_DARK};padding:22px 32px;"><p style="font-family:monospace;font-size:10px;color:#556;margin:0;line-height:1.8;">Generato con Claude Sonnet 4.6 - Fonte: PubMed RSS<br/>Sintesi AI - verificare le fonti primarie.</p></td></tr></table></td></tr></table></body></html>'''

def invia_email(oggetto, html):
    app_password = os.environ.get("GMAIL_APP_PASSWORD", "")
    if not app_password:
        log.error("GMAIL_APP_PASSWORD mancante")
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = oggetto
    msg["From"] = f"NIV Weekly Digest <{cfg.GMAIL_USER}>"
    msg["To"] = cfg.GMAIL_USER
    msg["Bcc"] = ", ".join(DESTINATARI)
    msg.attach(MIMEText(f"NIV Weekly Digest - {oggetto}", "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(cfg.GMAIL_USER, app_password)
            smtp.send_message(msg)
        log.info(f"Email inviata a {len(DESTINATARI)} destinatari")
        return True
    except Exception as e:
        log.error(f"Invio fallito: {e}")
        return False


# ─── Telegram ────────────────────────────────────────────────

NIV_PAGE_URL = "https://areacriticaprontosoccorso.github.io/Newsletter-NIV/"

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
        f"<i>{cfg.NOME_SERVIZIO}</i>\n\n"
        f"📚 {len(articoli)} articoli questa settimana\n"
    )
    if fallback:
        testo += ("\n⚠️ <i>Questa settimana non sono stati individuati articoli dedicati "
                  "specificamente alla NIV. Di seguito una selezione di articoli recenti su "
                  "temi respiratori e di area critica correlati.</i>\n")
    return testo + ("━" * 25)

def build_tg_articolo(i, a):
    parti = [f"<b>{i}. {a['titolo']}</b>", f"<i>{a['rivista']} · {a['data']}</i>"]
    if a.get("autori"):
        parti.append(f"👤 {a['autori']}")
    parti.append("")
    if a.get("sintesi_it"):
        parti.append(a["sintesi_it"])
    if a.get("rilevanza"):
        parti.append(f"\n🎯 <b>Rilevanza:</b> {a['rilevanza']}")
    parti.append("")
    link = f'🔗 <a href="{a["url"]}">PubMed {a["pmid"]}</a>'
    if a.get("doi"):
        link += f' · <a href="https://doi.org/{a["doi"]}">DOI</a>'
    parti.append(link)
    return "\n".join(parti)

def build_tg_footer():
    return (
        f"{'━' * 25}\n"
        f"📬 <a href=\"{NIV_PAGE_URL}\">Iscriviti alla newsletter via email</a>\n"
        f"🤖 Sintesi generate con Claude · Fonte: PubMed\n"
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
    log.info(f"Telegram: inviati {successi}/{totale} messaggi a {chat_id}")
    return successi == totale

def main():
    cfg.valida_config()
    wl = numero_settimana()
    log.info(f"=== NIV Weekly Digest - settimana {wl['settimana']}/{wl['anno']} ===")
    candidati = raccogli_candidati(giorni=7)
    if len(candidati) < ARTICOLI_FINALI + 3:
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
    log.info("Sintesi Claude...")
    for i, art in enumerate(selezionati):
        log.info(f"  Sintesi {i+1}/{len(selezionati)}: {art['pmid']}")
        selezionati[i] = sintetizza(art)
        time.sleep(1)
    html = build_html(selezionati, fallback)
    ok_email = invia_email(f"NIV Weekly Digest - Settimana {wl['settimana']}/{wl['anno']}", html)
    ok_telegram = invia_telegram(selezionati, fallback)
    log.info("=== Email: OK ===" if ok_email else "=== Email: FALLITO ===")
    log.info("=== Telegram: OK ===" if ok_telegram else "=== Telegram: FALLITO o non configurato ===")
    return ok_email

if __name__ == "__main__":
    main()
