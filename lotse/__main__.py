"""`python -m lotse` startet die Weboberfläche auf 127.0.0.1 (Port über `LOTSE_PORT`, Standard 8000)."""

import os

import uvicorn


def main() -> None:
    port = int(os.environ.get("LOTSE_PORT", "8000"))
    uvicorn.run("lotse.web.app:app", host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
