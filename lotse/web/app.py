"""FastAPI-App des SV KI-Lotsen. Sitzungen liegen im Speicher und als JSON unter `CACHE_DIR/sitzungen/`."""

from __future__ import annotations

import json
import logging
import threading
import uuid
from collections import OrderedDict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from lotse import config, llm, speicher, texte, wissen
from lotse.lotse import Antwort, Lotse, Sitzung
from lotse.models import WEITERE_SPRACHEN

log = logging.getLogger(__name__)

STATIC = Path(__file__).resolve().parent / "static"
MAX_SITZUNGEN = 500  # im Speicher; ältere liegen weiter auf der Platte
MAX_UPLOAD = 10 * 1024 * 1024  # 10 MB
MAX_IMPORT = 2 * 1024 * 1024  # 2 MB

# Demo-Dokumente: synthetische Beispiele (Repo) immer, SV-Box-Befund nur wenn lokal vorhanden.
_BEISPIELE = config.REPO_ROOT / "examples"
DEMO_DOKUMENTE: dict[str, tuple[Path, str]] = {
    "entlassungsbrief_synthetisch.txt": (_BEISPIELE / "entlassungsbrief_synthetisch.txt", "demo_synthetisch"),
    "impfpass_synthetisch.txt": (_BEISPIELE / "impfpass_synthetisch.txt", "demo_impfpass"),
    "entlassungsbrief_foto.jpg": (_BEISPIELE / "entlassungsbrief_foto.jpg", "demo_foto"),
    "Entlassungsbefund.pdf": (config.datei("Befunde/Entlassungsbefund.pdf"), "demo_sv_box"),
}

_lotse = Lotse()
_sitzungen: OrderedDict[str, Sitzung] = OrderedDict()
_sitzungen_sperre = threading.Lock()
_ui_cache: dict[str, dict] = {}  # übersetzte UI-Texte je weiterer Sprache


def _vorwaermen() -> None:
    try:
        wissen.wissensbasis()
    except Exception:  # Aufwärmen ist optional; Fehler zeigen sich beim ersten Zugriff erneut
        log.exception("Wissensbasis konnte nicht vorab geladen werden")


@asynccontextmanager
async def _lebenszyklus(_: FastAPI) -> AsyncIterator[None]:
    try:
        if n := speicher.aufraeumen():
            log.info("%d Sitzungsdateien älter als %d Tage gelöscht", n, speicher.MAX_ALTER_TAGE)
    except OSError:
        log.exception("Alte Sitzungsdateien konnten nicht gelöscht werden")
    if config.daten_vorhanden():
        threading.Thread(target=_vorwaermen, name="wissen-vorwaermen", daemon=True).start()
    yield


app = FastAPI(title="SV KI-Lotse", version="0.2", lifespan=_lebenszyklus)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.middleware("http")
async def _sicherheitsheader(request: Request, call_next):
    antwort = await call_next(request)
    antwort.headers.setdefault("Content-Security-Policy",
                               "default-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'")
    antwort.headers.setdefault("X-Content-Type-Options", "nosniff")
    antwort.headers.setdefault("Referrer-Policy", "no-referrer")
    return antwort


class NeueSitzung(BaseModel):
    sprache: str = "de"
    stil: str = "einfach"


class Nachricht(BaseModel):
    text: str


class Einstellungen(BaseModel):
    sprache: str | None = None
    stil: str | None = None


class Status(BaseModel):
    status: str


class TerminStart(BaseModel):
    anlass: str | None = None
    leistung: str | None = None


class TerminAenderung(BaseModel):
    datum: str | None = None
    uhrzeit: str | None = None
    status: str | None = None


def _merke(s: Sitzung) -> None:
    """Sitzung im Speicher halten (LRU); verdrängte bleiben auf der Platte und werden bei Bedarf geladen."""
    with _sitzungen_sperre:
        _sitzungen[s.id] = s
        _sitzungen.move_to_end(s.id)
        while len(_sitzungen) > MAX_SITZUNGEN:
            _sitzungen.popitem(last=False)


def _sitzung(sitzung_id: str) -> Sitzung:
    with _sitzungen_sperre:
        s = _sitzungen.get(sitzung_id)
        if s is not None:
            _sitzungen.move_to_end(sitzung_id)
            return s
        # nach einem Neustart oder Verdrängen: von der Platte
        s = speicher.lade(sitzung_id)
        if s is None:
            raise HTTPException(404, "Sitzung nicht gefunden")
        _sitzungen[s.id] = s
        while len(_sitzungen) > MAX_SITZUNGEN:
            _sitzungen.popitem(last=False)
        return s


def _json(s: Sitzung, antwort: Antwort) -> dict:
    """Antwort ausliefern und den Stand der Sitzung sichern (nach jeder Änderung)."""
    speicher.speichere(s)
    return antwort.to_dict()


@app.get("/", include_in_schema=False)
def startseite() -> FileResponse:
    return FileResponse(STATIC / "index.html", media_type="text/html")


def _ui_uebersetzt(sprache: str) -> dict:
    """UI-Texte einer weiteren Sprache: einmal übersetzen (Modell), dann aus dem Cache; Fehlendes bleibt Englisch."""
    if sprache in _ui_cache:
        return _ui_cache[sprache]
    basis = texte.ui_texte()["en"]
    felder: list[tuple[dict, str]] = [(basis, k) for k, v in basis.items() if isinstance(v, str)]
    for k in ("beispiele_saetze", "status"):
        felder += [(basis[k], x) for x in basis[k]]
    uebersetzt = llm.uebersetze([c[k] for c, k in felder], sprache)
    for (c, k), u in zip(felder, uebersetzt):
        if u is not None:
            c[k] = u
    if all(u is not None for u in uebersetzt):
        _ui_cache[sprache] = basis
    return basis


@app.get("/api/texte")
def ui_texte(sprache: str = "de") -> dict:
    ki = llm.aktiv()
    if sprache in texte.SPRACHEN:
        werte = texte.ui_texte()[sprache]
    elif sprache in WEITERE_SPRACHEN:
        if not ki:
            raise HTTPException(400, f"Sprache {sprache} gibt es nur im KI-Modus")
        werte = _ui_uebersetzt(sprache)
    else:
        raise HTTPException(400, f"Unbekannte Sprache: {sprache}")
    return {"texte": werte, "sprachen": texte.sprachen(ki), "ki": ki}


@app.post("/api/sitzung")
def sitzung_anlegen(daten: NeueSitzung | None = None) -> dict:
    daten = daten or NeueSitzung()
    try:
        s = _lotse.neue_sitzung(daten.sprache, daten.stil)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    _merke(s)
    with s.sperre:
        return _json(s, _lotse.aktuell(s))


@app.get("/api/sitzung/{sitzung_id}")
def sitzung_lesen(sitzung_id: str) -> dict:
    s = _sitzung(sitzung_id)
    with s.sperre:
        return _lotse.aktuell(s).to_dict()


@app.post("/api/sitzung/{sitzung_id}/nachricht")
def nachricht(sitzung_id: str, daten: Nachricht) -> dict:
    s = _sitzung(sitzung_id)
    with s.sperre:
        return _json(s, _lotse.nachricht(s, daten.text))


@app.post("/api/sitzung/{sitzung_id}/dokument")
def dokument_hochladen(sitzung_id: str, datei: UploadFile = File(...)) -> dict:
    s = _sitzung(sitzung_id)
    inhalt = datei.file.read(MAX_UPLOAD + 1)
    if len(inhalt) > MAX_UPLOAD:
        raise HTTPException(413, "Dokument ist größer als 10 MB")
    name = Path(datei.filename or "dokument").name
    with s.sperre:
        return _json(s, _lotse.dokument(s, name, inhalt))


@app.post("/api/sitzung/{sitzung_id}/einstellungen")
def einstellungen(sitzung_id: str, daten: Einstellungen) -> dict:
    s = _sitzung(sitzung_id)
    with s.sperre:
        try:
            return _json(s, _lotse.einstellungen(s, daten.sprache, daten.stil))
        except ValueError as e:
            raise HTTPException(400, str(e)) from e


@app.post("/api/sitzung/{sitzung_id}/schritt/{schritt_id}")
def schritt_status(sitzung_id: str, schritt_id: str, daten: Status) -> dict:
    s = _sitzung(sitzung_id)
    with s.sperre:
        try:
            return _json(s, _lotse.setze_status(s, schritt_id, daten.status))
        except KeyError as e:
            raise HTTPException(404, "Schritt nicht gefunden") from e
        except ValueError as e:
            raise HTTPException(400, str(e)) from e


@app.post("/api/sitzung/{sitzung_id}/termin")
def termin_starten(sitzung_id: str, daten: TerminStart | None = None) -> dict:
    """Terminvorbereitung beginnen (Anlass oder Leistung optional); gebucht wird nie durch den Lotsen."""
    daten = daten or TerminStart()
    s = _sitzung(sitzung_id)
    with s.sperre:
        try:
            return _json(s, _lotse.termin_starten(s, daten.anlass, daten.leistung))
        except KeyError as e:
            raise HTTPException(404, "Leistung nicht gefunden") from e
        except ValueError as e:
            raise HTTPException(400, str(e)) from e


@app.post("/api/sitzung/{sitzung_id}/termin/{termin_id}")
def termin_aendern(sitzung_id: str, termin_id: str, daten: TerminAenderung) -> dict:
    """Vereinbartes Datum/Uhrzeit eintragen oder den Termin als erledigt markieren."""
    s = _sitzung(sitzung_id)
    with s.sperre:
        try:
            return _json(s, _lotse.termin_aktualisieren(s, termin_id, daten.datum, daten.uhrzeit, daten.status))
        except KeyError as e:
            raise HTTPException(404, "Termin nicht gefunden") from e
        except ValueError as e:
            raise HTTPException(400, str(e)) from e


@app.get("/api/sitzung/{sitzung_id}/termin/{termin_id}.ics")
def termin_kalender(sitzung_id: str, termin_id: str) -> Response:
    s = _sitzung(sitzung_id)
    with s.sperre:
        try:
            kalender = _lotse.termin_ics(s, termin_id)
        except KeyError as e:
            raise HTTPException(404, "Termin nicht gefunden") from e
        except ValueError as e:
            raise HTTPException(404, "Für diesen Termin ist noch kein Datum eingetragen") from e
    return Response(
        content=kalender,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{termin_id}.ics"'},
    )


@app.get("/api/sitzung/{sitzung_id}/export")
def exportieren(sitzung_id: str) -> Response:
    """Fall als versioniertes JSON zum Speichern auf dem eigenen Gerät (ohne sensible Angaben)."""
    s = _sitzung(sitzung_id)
    with s.sperre:
        daten = speicher.zu_dict(s)
    return Response(
        content=json.dumps(daten, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="sv-ki-lotse-fall-{date.today().isoformat()}.json"'},
    )


@app.post("/api/import")
def importieren(datei: UploadFile = File(...)) -> dict:
    """Gespeicherten Fall laden: neue Sitzung mit geprüftem Inhalt (400 bei falscher Datei)."""
    roh = datei.file.read(MAX_IMPORT + 1)
    if len(roh) > MAX_IMPORT:
        raise HTTPException(413, "Fall-Datei ist größer als 2 MB")
    try:
        daten = json.loads(roh.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise HTTPException(400, "Keine gültige JSON-Datei") from e
    try:
        s = speicher.aus_dict(daten, neue_id=uuid.uuid4().hex)
    except speicher.UngueltigeSitzung as e:
        raise HTTPException(400, str(e)) from e
    _merke(s)
    with s.sperre:
        return _json(s, _lotse.wiederhergestellt(s))


@app.get("/api/sitzung/{sitzung_id}/formular/{form_id}")
def formular(sitzung_id: str, form_id: str, leistung: str | None = None) -> Response:
    s = _sitzung(sitzung_id)
    with s.sperre:
        try:
            pdf = _lotse.formular_pdf(s, form_id, leistung)
        except KeyError as e:
            raise HTTPException(404, "Formular nicht gefunden") from e
        except FileNotFoundError as e:
            raise HTTPException(503, "Formularvorlage ist lokal nicht vorhanden") from e
        speicher.speichere(s)  # Ausfüllen ist jetzt „in Arbeit“
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{form_id}_Entwurf.pdf"'},
    )


@app.get("/api/demo/dokumente")
def demo_dokumente() -> list[dict]:
    return [
        {"name": name, "titel": {sp: texte.UI[key][sp] for sp in texte.SPRACHEN}, "text_key": key,
         "nur_ki": pfad.suffix == ".jpg"}
        for name, (pfad, key) in DEMO_DOKUMENTE.items()
        if pfad.is_file()
    ]


@app.post("/api/sitzung/{sitzung_id}/demo/{name}")
def demo_laden(sitzung_id: str, name: str) -> dict:
    s = _sitzung(sitzung_id)
    eintrag = DEMO_DOKUMENTE.get(name)
    if eintrag is None or not eintrag[0].is_file():
        raise HTTPException(404, "Demo-Dokument nicht vorhanden")
    with s.sperre:
        return _json(s, _lotse.dokument(s, name, eintrag[0].read_bytes()))
