# packages/coaching-mcp/Dockerfile — Coaching-MCP-Server (Welle 10)
#
# Build-Kontext ist dieses Verzeichnis (packages/coaching-mcp), siehe
# docker/docker-compose.yml (`build.context: ../packages/coaching-mcp`).
#
# WICHTIG zum Transport: `src/coaching_mcp/server.py` implementiert bewusst nur den
# MCP-stdio-Transport (newline-delimited JSON-RPC über stdin/stdout) — siehe Docstring
# dort: das offizielle `mcp`-SDK braucht Python >=3.10, der Server wurde dafür absichtlich
# so gebaut, dass `tools.py`/`knowledge_store.py` unverändert bleiben, wenn der Transport
# später (Welle 13, Container läuft bereits auf Python 3.11) auf das offizielle SDK
# (SSE/Streamable-HTTP) umgestellt wird. Diese Welle (W10) ändert ausschließlich
# Docker-Artefakte, kein Quellcode in packages/coaching-mcp/src — daher überbrückt dieser
# Container den vorhandenen stdio-Server testweise auf TCP/8080 (wie in .env.example
# SOUFFLEUR_MCP_URL=http://coaching-mcp:8080 vorgesehen) mit `socat`: pro TCP-Verbindung
# wird ein frischer `python -m coaching_mcp`-Prozess gestartet, dessen stdin/stdout an den
# Socket gebunden werden. Kein Anwendungscode wird dafür verändert. Die echte
# SDK-Transport-Anbindung ist Aufgabe der späteren Welle.
#
# Kein Secret im Image: dieser Server braucht keinen API-Key (rein lokales Wissen,
# kein externer Datenabfluss, siehe Tool-Beschreibung in server.py). Kein Non-EU-Endpunkt:
# der Server öffnet keinerlei ausgehende Verbindung.
#
# Apple-Silicon-kompatibel: reine Python-Stdlib + socat (apt, multi-arch), kein MLX hier.

FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends socat \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

# Bewusst kein `pip install .`: ein regulärer Wheel-Install kopiert den Code nach
# site-packages, wo `knowledge_store.py`s `Path(__file__).resolve().parents[2]`-Auflösung
# (Paket-Root als Geschwister von `knowledge/`) ins Leere liefe. Stattdessen Quelltextbaum
# 1:1 wie im Repo erhalten (src/ + knowledge/ als Geschwister) und per PYTHONPATH geladen —
# keine Laufzeit-Abhängigkeiten nötig (`pyproject.toml`: dependencies = []).
COPY src/ /app/src/
COPY knowledge/ /app/knowledge/

RUN useradd --no-create-home --shell /usr/sbin/nologin souffleur \
    && chown -R souffleur:souffleur /app
USER souffleur

EXPOSE 8080

# TCP-Verbindungstest statt HTTP — der Server spricht JSON-RPC, nicht HTTP.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python3", "-c", "import socket,sys; s=socket.create_connection(('127.0.0.1',8080),3); s.close()"]

CMD ["socat", "TCP-LISTEN:8080,fork,reuseaddr", "EXEC:python3 -m coaching_mcp"]
