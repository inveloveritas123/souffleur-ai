#!/usr/bin/env bash
# Lädt Souffleur-Secrets von AUSSERHALB des Repos (kein Secret im Repo-Baum → D3 grün).
# Default: ~/.config/souffleur/souffleur.env  (override via $SOUFFLEUR_ENV_FILE)
SOUFFLEUR_ENV_FILE="${SOUFFLEUR_ENV_FILE:-$HOME/.config/souffleur/souffleur.env}"
if [ -f "$SOUFFLEUR_ENV_FILE" ]; then set -a; . "$SOUFFLEUR_ENV_FILE"; set +a; else
  echo "WARN: $SOUFFLEUR_ENV_FILE fehlt — siehe .env.example" >&2; fi
