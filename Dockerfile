# SV KI-Lotse – Container für Demo und Betrieb ohne lokale Python-Installation.
#   docker build -t nexovo-lotse .
#   docker run --rm -p 8000:8000 nexovo-lotse                      # regelbasiert
#   docker run --rm -p 8000:8000 --env-file .env nexovo-lotse      # mit KI-Modus
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LOTSE_CACHE_DIR=/app/.cache

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Suchindex beim Bauen erzeugen, damit der erste Start sofort antwortet
RUN python -c "from lotse.wissen import wissensbasis; wissensbasis()" \
    && useradd --create-home --uid 10001 lotse \
    && chown -R lotse /app/.cache

USER lotse
EXPOSE 8000
CMD ["uvicorn", "lotse.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
