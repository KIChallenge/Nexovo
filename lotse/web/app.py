"""FastAPI-App des SV KI-Lotsen. Sitzungen liegen nur im Speicher."""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from lotse import config, texte, wissen
from lotse.lotse import Antwort, Lotse, Sitzung

log = logging.getLogger(__name__)

STATIC = Path(__file__).resolve().parent / "static"
MAX_SITZUNGEN = 500
MAX_UPLOAD = 10 * 1024 * 1024  # 10 MB

# Demo-Dokumente: synthetischer Brief (Repo) immer, SV-Box-Befund nur wenn lokal vorhanden.
DEMO_DOKUMENTE: dict[str, tuple[Path, str]] = {
    "entlassungsbrief_synthetisch.txt": (config.REPO_ROOT / "examples" / "entlassungsbrief_synthetisch.txt",
                                         "demo_synthetisch"),
    "Entlassungsbefund.pdf": (config.datei("Befunde/Entlassungsbefund.pdf"), "demo_sv_box"),
}

_lotse = Lotse()
_sitzungen: OrderedDict[str, Sitzung] = OrderedDict()
_sitzungen_sperre = threading.Lock()


def _vorwaermen() -> None:
    try:
        wissen.wissensbasis()
    except Exception:  # Aufwärmen ist optional; Fehler zeigen sich beim ersten Zugriff erneut
        log.exception("Wissensbasis konnte nicht vorab geladen werden")


@asynccontextmanager
async def _lebenszyklus(_: FastAPI) -> AsyncIterator[None]:
    if config.daten_vorhanden():
        threading.Thread(target=_vorwaermen, name="wissen-vorwaermen", daemon=True).start()
    yield


app = FastAPI(title="SV KI-Lotse", version="0.1", lifespan=_lebenszyklus)
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


def _sitzung(sitzung_id: str) -> Sitzung:
    with _sitzungen_sperre:
        s = _sitzungen.get(sitzung_id)
        if s is None:
            raise HTTPException(404, "Sitzung nicht gefunden")
        _sitzungen.move_to_end(sitzung_id)
        return s


def _json(antwort: Antwort) -> dict:
    return antwort.to_dict()


@app.get("/", include_in_schema=False)
def startseite() -> FileResponse:
    return FileResponse(STATIC / "index.html", media_type="text/html")


@app.get("/api/texte")
def ui_texte() -> dict:
    return texte.ui_texte()


@app.post("/api/sitzung")
def sitzung_anlegen(daten: NeueSitzung | None = None) -> dict:
    daten = daten or NeueSitzung()
    try:
        s = _lotse.neue_sitzung(daten.sprache, daten.stil)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    with _sitzungen_sperre:
        _sitzungen[s.id] = s
        while len(_sitzungen) > MAX_SITZUNGEN:
            _sitzungen.popitem(last=False)
    with s.sperre:
        return _json(_lotse.aktuell(s))


@app.get("/api/sitzung/{sitzung_id}")
def sitzung_lesen(sitzung_id: str) -> dict:
    s = _sitzung(sitzung_id)
    with s.sperre:
        return _json(_lotse.aktuell(s))


@app.post("/api/sitzung/{sitzung_id}/nachricht")
def nachricht(sitzung_id: str, daten: Nachricht) -> dict:
    s = _sitzung(sitzung_id)
    with s.sperre:
        return _json(_lotse.nachricht(s, daten.text))


@app.post("/api/sitzung/{sitzung_id}/dokument")
def dokument_hochladen(sitzung_id: str, datei: UploadFile = File(...)) -> dict:
    s = _sitzung(sitzung_id)
    inhalt = datei.file.read(MAX_UPLOAD + 1)
    if len(inhalt) > MAX_UPLOAD:
        raise HTTPException(413, "Dokument ist größer als 10 MB")
    name = Path(datei.filename or "dokument").name
    with s.sperre:
        return _json(_lotse.dokument(s, name, inhalt))


@app.post("/api/sitzung/{sitzung_id}/einstellungen")
def einstellungen(sitzung_id: str, daten: Einstellungen) -> dict:
    s = _sitzung(sitzung_id)
    with s.sperre:
        try:
            return _json(_lotse.einstellungen(s, daten.sprache, daten.stil))
        except ValueError as e:
            raise HTTPException(400, str(e)) from e


@app.post("/api/sitzung/{sitzung_id}/schritt/{schritt_id}")
def schritt_status(sitzung_id: str, schritt_id: str, daten: Status) -> dict:
    s = _sitzung(sitzung_id)
    with s.sperre:
        try:
            return _json(_lotse.setze_status(s, schritt_id, daten.status))
        except KeyError as e:
            raise HTTPException(404, "Schritt nicht gefunden") from e
        except ValueError as e:
            raise HTTPException(400, str(e)) from e


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
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{form_id}_Entwurf.pdf"'},
    )


@app.get("/api/demo/dokumente")
def demo_dokumente() -> list[dict]:
    return [
        {"name": name, "titel": {sp: texte.UI[key][sp] for sp in texte.SPRACHEN}}
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
        return _json(_lotse.dokument(s, name, eintrag[0].read_bytes()))
