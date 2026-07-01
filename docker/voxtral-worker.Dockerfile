# docker/voxtral-worker.Dockerfile — optionaler lokaler STT-Worker (Compose-Profil
# `local-stt`, Welle 10). NICHT im Default-Pfad aktiv (Default ist Cloud: voxtral_api).
#
# KRITISCH — warum hier kein MLX: MLX ist Apple-Silicon/Metal-only und läuft NICHT in
# Linux-Containern (auch nicht auf einem Apple-Silicon-Host, weil Docker/OrbStack dort
# eine Linux-VM nutzt, keinen direkten Metal-Zugriff hat). Der `voxtral_local`-MLX-Adapter
# (apps/backend/src/souffleur/adapters/stt/voxtral_local.py) ist daher NICHT für diesen
# Container vorgesehen. Um SOUFFLEUR_STT_PROVIDER=voxtral_local tatsächlich zu nutzen,
# muss das Backend HOST-seitig laufen (außerhalb Docker, direkt auf macOS, z. B.
# `uvicorn souffleur.core.app:app --host 0.0.0.0 --port 8000` in einer lokalen venv) —
# der MLX-Adapter greift dann direkt auf die Apple-Silicon-GPU/Neural-Engine des Hosts zu.
#
# Dieses Image ist stattdessen ein bewusst schlanker CPU-Platzhalter für einen künftigen
# containerisierbaren faster-whisper-Worker (CPU, kein MLX): es gibt in diesem Repo noch
# KEINEN Anwendungscode für einen solchen Worker (das wäre neuer Quellcode außerhalb des
# Scopes dieser Welle, die nur Docker-Artefakte umfasst) — daher startet der Container nur
# einen minimalen Stdlib-HTTP-Health-Stub auf Port 9000 und dokumentiert den Zustand.
# Sobald ein echter faster-whisper-Server-Code existiert (spätere Welle), ersetzt dessen
# Dockerfile diesen Platzhalter 1:1 (gleicher Port, gleiches Compose-Profil).
#
# Kein Secret im Image, kein Non-EU-Endpunkt: dieser Stub öffnet keine ausgehende
# Verbindung.

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --no-create-home --shell /usr/sbin/nologin souffleur

USER souffleur

EXPOSE 9000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD ["python3", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:9000/',timeout=3).status==200 else 1)"]

# Minimaler Health-Only-Stub (kein STT, kein Modell-Aufruf) — siehe Kommentar oben.
CMD ["python3", "-c", "from http.server import BaseHTTPRequestHandler, HTTPServer\n\nclass Handler(BaseHTTPRequestHandler):\n    def do_GET(self):\n        self.send_response(200)\n        self.send_header('Content-Type', 'text/plain')\n        self.end_headers()\n        self.wfile.write(b'voxtral-worker placeholder (kein MLX, kein Modell-Aufruf) - siehe docker/voxtral-worker.Dockerfile')\n    def log_message(self, *args):\n        pass\n\nHTTPServer(('0.0.0.0', 9000), Handler).serve_forever()\n"]
