"""
Il podcast della settimana anche sul canale Telegram (POCUS e NIV).

Bot API di Telegram, solo libreria standard: il video MP4 con sendVideo (si guarda nell'app senza
scaricarlo); se pesa piu' di LIMITE_MB (i bot caricano al massimo 50 MB) o Telegram lo rifiuta,
l'MP3 con sendAudio. Servono TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID, gli stessi dei messaggi della
newsletter. Mai eccezioni: un errore finisce nel log (ERROR, quindi nell'email di avviso).

Copia identica in newsletter-pocus e Newsletter-NIV.
"""
import json
import logging
import os
import urllib.error
import urllib.request
import uuid

log = logging.getLogger("telegram_podcast")

LIMITE_MB = 49
DIDASCALIA_MAX = 1024          # limite di Telegram per la didascalia di un file


def _multipart(campi, campo_file, percorso, tipo):
    confine = uuid.uuid4().hex
    parti = [f'--{confine}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode("utf-8")
             for k, v in campi.items()]
    with open(percorso, "rb") as f:
        dati = f.read()
    parti.append(f'--{confine}\r\nContent-Disposition: form-data; name="{campo_file}"; '
                 f'filename="{os.path.basename(percorso)}"\r\nContent-Type: {tipo}\r\n\r\n'.encode("utf-8")
                 + dati + b"\r\n")
    parti.append(f"--{confine}--\r\n".encode("utf-8"))
    return b"".join(parti), f"multipart/form-data; boundary={confine}"


def _invia(token, metodo, campi, campo_file, percorso, tipo):
    """Carica il file con il metodo della Bot API. message_id; solleva RuntimeError col motivo."""
    corpo, intestazione = _multipart(campi, campo_file, percorso, tipo)
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/{metodo}", data=corpo,
                                 headers={"Content-Type": intestazione}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            risposta = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            motivo = json.loads(e.read().decode("utf-8")).get("description", "")
        except Exception:
            motivo = ""
        raise RuntimeError(f"HTTP {e.code} {motivo}".strip()) from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"rete: {e.reason}") from None
    if not risposta.get("ok"):
        raise RuntimeError(risposta.get("description") or "risposta non ok")
    return risposta["result"]["message_id"]


def invia_podcast(podcast, didascalia, titolo="", token=None, chat_id=None):
    """`podcast`: {"mp4": percorso, "mp3": percorso} (anche uno solo). Prima il video, poi l'MP3.
    `titolo`: titolo del brano per l'MP3 (lettore audio di Telegram). message_id o None."""
    token = token if token is not None else os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = chat_id if chat_id is not None else os.environ.get("TELEGRAM_CHAT_ID", "")
    if not podcast:
        return None
    if not token or not chat_id:
        log.warning("Telegram: TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID mancanti - podcast non inviato")
        return None
    testo = (didascalia or "")[:DIDASCALIA_MAX]
    motivi = []
    for tipo in ("mp4", "mp3"):
        percorso = podcast.get(tipo)
        if not percorso or not os.path.exists(percorso):
            continue
        mb = os.path.getsize(percorso) / 1e6
        if mb > LIMITE_MB:
            motivi.append(f"{tipo} di {mb:.0f} MB oltre il limite dei bot ({LIMITE_MB} MB)")
            continue
        campi = {"chat_id": chat_id, "caption": testo, "parse_mode": "HTML"}
        try:
            if tipo == "mp4":
                campi["supports_streaming"] = "true"
                mid = _invia(token, "sendVideo", campi, "video", percorso, "video/mp4")
            else:
                campi.update(title=titolo or "Podcast", performer="Pronto Soccorso San Giovanni Bosco")
                mid = _invia(token, "sendAudio", campi, "audio", percorso, "audio/mpeg")
            log.info(f"Telegram: podcast inviato ({tipo}, {mb:.1f} MB)")
            return mid
        except Exception as e:
            motivi.append(f"{tipo}: {str(e)[:160]}")
            log.warning(f"Telegram: podcast {tipo} non inviato ({str(e)[:160]})")
    if motivi:
        log.error(f"Telegram: podcast non inviato ({'; '.join(motivi)})")
    return None
