"""Avvisi periodici dei corsi organizzati da Francesco Panero.

I corsi stanno in corsi.json (stesso formato in ogni repo, vedi README). A ogni
uscita compaiono i corsi non ancora conclusi, in cima alla mail, in un messaggio
Telegram e (solo POCUS) in un post Facebook programmato. Passata la data del
corso l'avviso sparisce da solo.

Solo libreria standard. Un errore in questo modulo NON deve mai bloccare la
newsletter: carica_corsi() non solleva eccezioni e in caso di problemi restituisce [].
"""
import html
import json
import logging
import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

log = logging.getLogger("corsi")

FILE_CORSI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corsi.json")
MAX_CORSI = 2            # al massimo due avvisi per uscita: i piu' vicini nel tempo
MAX_DESCRIZIONE = 400    # caratteri

_MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
         "agosto", "settembre", "ottobre", "novembre", "dicembre"]
_GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]


def _avviso(msg):
    """Log e, su GitHub Actions, annotazione gialla visibile nel riepilogo del run
    (un corsi.json sbagliato non blocca la newsletter, ma deve vedersi)."""
    log.warning(msg)
    print(f"::warning title=corsi.json::{msg}", flush=True)


def oggi_roma():
    return datetime.now(ZoneInfo("Europe/Rome")).date()


def _data(valore):
    """'2026-11-14' -> date; None se assente o non valida."""
    if not valore:
        return None
    try:
        return datetime.strptime(str(valore).strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _testo(valore, massimo=None):
    t = " ".join(str(valore or "").split())
    if massimo and len(t) > massimo:
        t = t[:massimo - 1].rstrip() + "…"
    return t


def _url(valore):
    u = str(valore or "").strip()
    return u if u.lower().startswith(("https://", "http://")) and " " not in u else ""


def carica_corsi(newsletter, oggi=None, percorso=None, massimo=MAX_CORSI):
    """Corsi da annunciare oggi su `newsletter` ('pocus' o 'niv'), dal piu' vicino.
    Mai eccezioni: file mancante o rotto -> [] (con un avviso nel log)."""
    percorso = percorso or FILE_CORSI
    oggi = oggi or oggi_roma()
    try:
        if not os.path.exists(percorso):
            return []
        with open(percorso, encoding="utf-8") as f:
            dati = json.load(f)
        voci = dati.get("corsi", []) if isinstance(dati, dict) else dati
        if not isinstance(voci, list):
            raise ValueError("'corsi' deve essere un elenco")
    except Exception as e:
        _avviso(f"corsi.json non leggibile, nessun avviso corsi: {e}")
        return []

    risultato = []
    for i, v in enumerate(voci, 1):
        try:
            if not isinstance(v, dict) or v.get("attivo", True) is False:
                continue
            dove = v.get("newsletter")
            if dove is not None and newsletter not in (
                    [dove] if isinstance(dove, str) else list(dove)):
                continue
            titolo = _testo(v.get("titolo"), 160)
            inizio = _data(v.get("data_inizio"))
            if not titolo or not inizio:
                _avviso(f"voce {i} ignorata: servono 'titolo' e "
                        "'data_inizio' (AAAA-MM-GG)")
                continue
            fine = _data(v.get("data_fine")) or inizio
            if fine < inizio:
                _avviso(f"voce {i} ({titolo}): data_fine prima di data_inizio")
                fine = inizio
            mostra_dal = _data(v.get("mostra_dal"))
            if fine < oggi or (mostra_dal and oggi < mostra_dal):
                continue
            iscr = _data(v.get("iscrizioni_fino"))
            risultato.append({
                "titolo": titolo, "inizio": inizio, "fine": fine,
                "ora": _testo(v.get("ora"), 60),
                "luogo": _testo(v.get("luogo"), 160),
                "descrizione": _testo(v.get("descrizione"), MAX_DESCRIZIONE),
                "posti": _testo(v.get("posti"), 80),
                "link": _url(v.get("link")),
                "iscrizioni_fino": iscr if iscr and iscr >= oggi else None,
            })
        except Exception as e:
            _avviso(f"voce {i} ignorata: {e}")
    risultato.sort(key=lambda c: (c["inizio"], c["titolo"]))
    if len(risultato) > massimo:
        log.info(f"{len(risultato)} corsi in programma: ne annuncio i primi {massimo}")
    return risultato[:massimo]


def _g(d):
    return f"{d.day} {_MESI[d.month - 1]}"


def data_leggibile(c):
    """'sabato 14 novembre 2026' / '14–15 novembre 2026' / '30 novembre – 1 dicembre 2026'."""
    a, b = c["inizio"], c["fine"]
    if a == b:
        return f"{_GIORNI[a.weekday()]} {_g(a)} {a.year}"
    if (a.year, a.month) == (b.year, b.month):
        return f"{a.day}–{b.day} {_MESI[a.month - 1]} {a.year}"
    if a.year == b.year:
        return f"{_g(a)} – {_g(b)} {a.year}"
    return f"{_g(a)} {a.year} – {_g(b)} {b.year}"


def _esc(s):
    return html.escape(str(s), quote=True)


def html_corsi(corsi, colore="#0a6e8a"):
    """Riga <tr> per la mail, da inserire sotto l'intestazione. '' se non ci sono corsi."""
    if not corsi:
        return ""
    etichetta = "Corso in programma" if len(corsi) == 1 else "Corsi in programma"
    schede = ""
    for c in corsi:
        meta = [f"<strong>{_esc(data_leggibile(c))}</strong>"]
        if c["ora"]:
            meta.append(_esc(c["ora"]))
        if c["luogo"]:
            meta.append(_esc(c["luogo"]))
        if c["posti"]:
            meta.append(_esc(c["posti"]))
        extra = ""
        if c["iscrizioni_fino"]:
            extra = (f'<div style="font-family:monospace;font-size:11px;color:#8a6d00;'
                     f'margin:6px 0 0;">Iscrizioni entro il {_esc(_g(c["iscrizioni_fino"]))} '
                     f'{c["iscrizioni_fino"].year}</div>')
        descr = (f'<div style="font-family:Georgia,serif;font-size:13.5px;color:#2a2a2a;'
                 f'line-height:1.55;margin:8px 0 0;">{_esc(c["descrizione"])}</div>'
                 if c["descrizione"] else "")
        bottone = (f'<table cellpadding="0" cellspacing="0" style="margin-top:12px;"><tr>'
                   f'<td bgcolor="{colore}" style="border-radius:4px;">'
                   f'<a href="{_esc(c["link"])}" style="display:inline-block;padding:9px 18px;'
                   f'font-family:Arial,sans-serif;font-size:13px;font-weight:700;color:#ffffff;'
                   f'text-decoration:none;">Programma e iscrizioni</a></td></tr></table>'
                   if c["link"] else "")
        schede += (f'<div style="margin:0 0 14px;padding-bottom:14px;'
                   f'border-bottom:1px solid #e3ddd0;">'
                   f'<div style="font-family:Georgia,serif;font-size:18px;font-weight:700;'
                   f'color:#1a1a1a;line-height:1.3;">{_esc(c["titolo"])}</div>'
                   f'<div style="font-family:Arial,sans-serif;font-size:13px;color:#444;'
                   f'margin:6px 0 0;">{" &middot; ".join(meta)}</div>'
                   f'{extra}{descr}{bottone}</div>')
    return (f'<tr><td style="background:#fffdf7;padding:18px 32px 4px;'
            f'border-bottom:1px solid #e3ddd0;border-top:3px solid {colore};">'
            f'<div style="font-family:monospace;font-size:10px;letter-spacing:2px;'
            f'text-transform:uppercase;color:{colore};margin:0 0 10px;">{etichetta}</div>'
            f'{schede}</td></tr>')


def testo_telegram(corsi):
    """Un solo messaggio (HTML di Telegram) con tutti i corsi, oppure ''."""
    if not corsi:
        return ""
    blocchi = ["📣 <b>" + ("Corso in programma" if len(corsi) == 1 else "Corsi in programma")
               + "</b>"]
    for c in corsi:
        riga = [f"\n<b>{_esc(c['titolo'])}</b>", f"📅 {_esc(data_leggibile(c))}"
                + (f" · {_esc(c['ora'])}" if c["ora"] else "")]
        if c["luogo"]:
            riga.append(f"📍 {_esc(c['luogo'])}")
        if c["posti"]:
            riga.append(f"👥 {_esc(c['posti'])}")
        if c["iscrizioni_fino"]:
            riga.append(f"⏳ Iscrizioni entro il {_esc(_g(c['iscrizioni_fino']))} "
                        f"{c['iscrizioni_fino'].year}")
        if c["descrizione"]:
            riga.append(f"\n{_esc(c['descrizione'])}")
        if c["link"]:
            riga.append(f'\n🔗 <a href="{_esc(c["link"])}">Programma e iscrizioni</a>')
        blocchi.append("\n".join(riga))
    testo = "\n".join(blocchi)
    return testo if len(testo) <= 4096 else testo[:4090] + "\n…"


def testo_facebook(c):
    """Testo semplice del post Facebook per un corso."""
    righe = [f"📣 CORSO — {c['titolo']}", "",
             f"📅 {data_leggibile(c)}" + (f" · {c['ora']}" if c["ora"] else "")]
    if c["luogo"]:
        righe.append(f"📍 {c['luogo']}")
    if c["posti"]:
        righe.append(f"👥 {c['posti']}")
    if c["iscrizioni_fino"]:
        righe.append(f"⏳ Iscrizioni entro il {_g(c['iscrizioni_fino'])} "
                     f"{c['iscrizioni_fino'].year}")
    if c["descrizione"]:
        righe += ["", c["descrizione"]]
    if c["link"]:
        righe += ["", f"Programma e iscrizioni: {c['link']}"]
    return "\n".join(righe)


def verifica(percorso=None):
    """Elenco dei problemi di corsi.json (vuoto = file a posto)."""
    percorso = percorso or FILE_CORSI
    if not os.path.exists(percorso):
        return []
    try:
        with open(percorso, encoding="utf-8") as f:
            dati = json.load(f)
    except Exception as e:
        return [f"file non leggibile: {e}"]
    voci = dati.get("corsi") if isinstance(dati, dict) else None
    if not isinstance(voci, list):
        return ["manca l'elenco \"corsi\""]
    problemi = []
    for i, v in enumerate(voci, 1):
        if not isinstance(v, dict):
            problemi.append(f"voce {i}: non e' un oggetto")
            continue
        nome = f"voce {i} ({_testo(v.get('titolo'), 40) or 'senza titolo'})"
        if not _testo(v.get("titolo")):
            problemi.append(f"{nome}: manca 'titolo'")
        for campo in ("data_fine", "mostra_dal", "iscrizioni_fino"):
            if v.get(campo) not in (None, "") and not _data(v.get(campo)):
                problemi.append(f"{nome}: '{campo}' deve essere AAAA-MM-GG")
        if not _data(v.get("data_inizio")):
            problemi.append(f"{nome}: manca 'data_inizio' valida")
        if v.get("link") and not _url(v.get("link")):
            problemi.append(f"{nome}: 'link' deve iniziare con https://")
        dove = v.get("newsletter")
        if dove is not None:
            for x in ([dove] if isinstance(dove, str) else list(dove)):
                if x not in ("pocus", "niv"):
                    problemi.append(f"{nome}: newsletter '{x}' sconosciuta (usa pocus, niv)")
    return problemi


if __name__ == "__main__":
    import sys
    probl = verifica()
    for p in probl:
        print(f"::warning title=corsi.json::{p}")
        print(f"PROBLEMA: {p}")
    for nl in ("pocus", "niv"):
        c = carica_corsi(nl)
        print(f"{nl}: {len(c)} corsi da annunciare oggi" + "".join(
            f"\n  - {x['titolo']} ({data_leggibile(x)})" for x in c))
    sys.exit(1 if probl else 0)
