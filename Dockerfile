# Obraz sluzy do pracy nad panelem, API i testami, nie do sterowania gra.
# Kontener nie ma mikrofonu ani dostepu do klawiatury Windowsa, wiec nasluch
# i wciskanie klawiszy dzialaja tylko w aplikacji uruchomionej na hoscie.

# --- panel -----------------------------------------------------------------
FROM node:20-alpine AS webui

WORKDIR /build
COPY webui/package.json webui/package-lock.json ./
RUN npm ci
COPY webui/ ./
RUN npm run build


# --- warstwa wspolna -------------------------------------------------------
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    LOLVOICE_HOME=/data

WORKDIR /app

COPY requirements-docker.txt ./
RUN pip install --no-cache-dir -r requirements-docker.txt

COPY app/ ./app/
COPY server/ ./server/
COPY controller/ ./controller/
COPY controls/ ./controls/
COPY game/ ./game/
COPY utils/ ./utils/
COPY data/ ./data/
COPY tools/ ./tools/
COPY main.py version.json pyproject.toml ./

RUN mkdir -p /data && \
    adduser --disabled-password --gecos "" --uid 10001 lolvoice && \
    chown -R lolvoice:lolvoice /app /data


# --- obraz uruchomieniowy --------------------------------------------------
FROM base AS runtime

COPY --from=webui --chown=lolvoice:lolvoice /build/dist ./webui/dist

USER lolvoice
EXPOSE 21337

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "tools/healthcheck.py"]

CMD ["python", "-m", "uvicorn", "server.api:app", "--host", "0.0.0.0", "--port", "21337"]


# --- obraz deweloperski, testy i lint --------------------------------------
FROM base AS dev

USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg espeak-ng git && \
    rm -rf /var/lib/apt/lists/*

COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY tests/ ./tests/
RUN chown -R lolvoice:lolvoice /app

USER lolvoice
CMD ["python", "-m", "pytest", "-q", "-m", "not slow and not audio"]
