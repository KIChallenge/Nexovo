"""Pfade und Umgebung. Zugangsdaten kommen ausschließlich aus Umgebungsvariablen oder `.env`."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PAKET_DATEN = Path(__file__).resolve().parent / "data"


def _lade_env(pfad: Path) -> None:
    """Liest `KEY=VALUE`-Zeilen aus `.env`, ohne bestehende Umgebungsvariablen zu überschreiben."""
    if not pfad.is_file():
        return
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#") or "=" not in zeile:
            continue
        key, _, value = zeile.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_lade_env(REPO_ROOT / ".env")

DATA_DIR = Path(os.environ.get("LOTSE_DATA_DIR", REPO_ROOT)).resolve()
CACHE_DIR = Path(os.environ.get("LOTSE_CACHE_DIR", REPO_ROOT / ".cache")).resolve()


def datei(rel: str) -> Path:
    """Absoluter Pfad einer SV-Box-Quelldatei (relativ zu `DATA_DIR`)."""
    return DATA_DIR / rel


def daten_vorhanden() -> bool:
    """True, wenn die SV-Box-Quelldaten lokal vorliegen."""
    return (DATA_DIR / "Rechtstexte").is_dir() and (DATA_DIR / "Anträge und Formulare").is_dir()


def azure_endpoint() -> str:
    return os.environ.get("AZURE_OPENAI_ENDPOINT", "")


def azure_api_key() -> str:
    return os.environ.get("AZURE_API_KEY", "")


def azure_modell() -> str:
    return os.environ.get("AZURE_OPENAI_MODEL", "gpt-5-4-mini")
