# apps/web/Dockerfile — Souffleur AI Web-UI (Vite/React, Phase 1, Welle 10)
#
# Build-Kontext ist dieses Verzeichnis (apps/web), siehe docker/docker-compose.yml
# (`build.context: ../apps/web`). Zweistufig: Node baut das statische Bundle, nginx
# liefert es aus (kleineres Laufzeit-Image, kein Node/npm im Runtime-Container).
#
# VITE_SOUFFLEUR_API_BASE wird zur Build-Zeit gebacken (Vite/import.meta.env, siehe
# src/config/env.ts) — Default ist das lokale Backend (http://localhost:8000), kann pro
# Build per --build-arg überschrieben werden. Kein Secret/Modell-Name hier, nur die
# Backend-Basis-URL des eigenen Services (Gate E1: das Web-UI spricht nie direkt mit
# Mistral/Gladia).

# --- Stage 1: Build -----------------------------------------------------------------
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_SOUFFLEUR_API_BASE=http://localhost:8000
ENV VITE_SOUFFLEUR_API_BASE=${VITE_SOUFFLEUR_API_BASE}

RUN npm run build

# --- Stage 2: Runtime (statisches Serving via nginx) --------------------------------
FROM nginx:1.27-alpine AS runtime

# SPA-Fallback (React Router) auf SOUFFLEUR_WEB_PORT=5173 (ARCHITECTURE.md), kein
# zusätzliches Config-File im Repo nötig — Scope dieser Welle ist nur das Dockerfile.
RUN printf 'server {\n\
    listen 5173;\n\
    server_name _;\n\
    root /usr/share/nginx/html;\n\
    index index.html;\n\
    location / {\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
}\n' > /etc/nginx/conf.d/default.conf

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 5173

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD ["wget", "--quiet", "--spider", "http://127.0.0.1:5173/"]

CMD ["nginx", "-g", "daemon off;"]
