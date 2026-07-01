# apps/backend/Dockerfile — Souffleur AI Backend (FastAPI, Welle 10)
#
# Build-Kontext ist dieses Verzeichnis (apps/backend), siehe docker/docker-compose.yml
# (`build.context: ../apps/backend`). Es gibt im Repo bewusst keine requirements.txt für
# das Backend (Quellcode-Pfad ist gesperrt für diese Welle) — die Versionen unten sind
# exakt die Versionen, gegen die der Backend-Code laut Code-Kommentaren entwickelt und
# verifiziert wurde (z. B. adapters/llm/mistral.py: "Verifiziert gegen das installierte
# mistralai==1.10.0").
#
# Kein Secret im Image: MISTRAL_API_KEY/GLADIA_API_KEY kommen ausschließlich zur Laufzeit
# über `env_file`/Host-Env (siehe docker-compose.yml), niemals als ARG/ENV mit echtem Wert
# hier. EU-Routing (Gate E1): MISTRAL_BASE_URL/GLADIA_BASE_URL werden nicht hier
# hartkodiert, sondern bleiben Laufzeit-Konfiguration (Defaults in core/settings.py sind
# bereits EU-Endpunkte: api.mistral.ai/Paris, api.gladia.io/Frankreich).
#
# Apple-Silicon-kompatibel: keine plattformspezifischen Wheels nötig (reine Python-Pakete),
# baut nativ als linux/arm64 unter OrbStack/Docker Desktop.

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

# Pinned Laufzeit-Abhängigkeiten (keine "latest"-Ranges, Gate F1 ist zwar nur für
# Modell-IDs verbindlich, dieselbe Disziplin gilt aber für reproduzierbare Images).
RUN pip install --no-cache-dir \
        fastapi==0.128.8 \
        uvicorn==0.39.0 \
        pydantic==2.13.4 \
        python-multipart==0.0.20 \
        mistralai==1.10.0 \
        httpx==0.28.1 \
        websockets==15.0.1

COPY src/ /app/src/

# Audit-Log-Default (SOUFFLEUR_AUDIT_LOG_PATH=./data/audit-log.jsonl, core/settings.py)
# ist relativ zum CWD — als Volume gemountet (siehe docker-compose.yml), hier nur das
# Verzeichnis vorbereiten, damit ein Erststart ohne Volume nicht mit ENOENT abbricht.
RUN mkdir -p /app/data

# Nicht als root laufen lassen.
RUN useradd --no-create-home --shell /usr/sbin/nologin souffleur \
    && chown -R souffleur:souffleur /app
USER souffleur

EXPOSE 8000

# Healthcheck ohne zusätzliches Tool (kein curl im Image): FastAPI liefert /openapi.json
# unauthenticated aus (kein API-Key/Netzaufruf nötig, App baut Adapter nur lazy).
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/openapi.json', timeout=3).status==200 else 1)"]

CMD ["uvicorn", "souffleur.core.app:app", "--host", "0.0.0.0", "--port", "8000"]
