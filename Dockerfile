# syntax=docker/dockerfile:1.7
#
# Image du site du collectif. Trois étapes (idée reprise de BD_ditor, deploy/Dockerfile :
# ce qu'on teste doit être ce qu'on exécute) :
#   base     dépendances d'exécution, jamais lancée telle quelle ;
#   test     base + outils de test, joue la suite DANS l'image :
#              docker build --target test -t univ-enragee:test . && docker run --rm univ-enragee:test
#   runtime  l'image livrée (par défaut), sans outils de test, sous un utilisateur non root.

# --- base ------------------------------------------------------------------------------
FROM python:3.13-slim-trixie AS base

# tzdata : le fuseau Europe/Paris, pour Django comme pour les horaires du cron.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.12.21 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    TZ=Europe/Paris

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# --- test ------------------------------------------------------------------------------
FROM base AS test
RUN uv sync --frozen --no-install-project
COPY . .
ENV DJANGO_ENV=test
CMD ["sh", "-c", "python -m pytest -q -o addopts='' && DJANGO_ENV=prod DJANGO_SECRET_KEY=verification-du-deploiement-pas-un-vrai-secret-0123456789abcdefghij DJANGO_ALLOWED_HOSTS=exemple.org python manage.py check --deploy --fail-level WARNING"]

# --- runtime ---------------------------------------------------------------------------
FROM base AS runtime

# supercronic : le cron du conteneur, binaire épinglé et vérifié par sha256. L'architecture
# est lue ici plutôt que dans TARGETARCH, que tous les constructeurs ne renseignent pas.
ARG SUPERCRONIC_VERSION=v0.2.49
RUN set -eu; \
    arch="$(dpkg --print-architecture)"; \
    case "$arch" in \
      amd64) sum=a53ae236602c7338aba3fbaff40bda6300eae3b9fedb8261eb06cfe3724430c1 ;; \
      arm64) sum=02aa0cb229ba09050cba6638059dadb9eedc2276632ea43d6a57a2f8c1629dd5 ;; \
      *) echo "Architecture non prise en charge : $arch" >&2; exit 1 ;; \
    esac; \
    python -c "import sys, urllib.request; urllib.request.urlretrieve(sys.argv[1], sys.argv[2])" \
      "https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-${arch}" \
      /usr/local/bin/supercronic; \
    echo "${sum}  /usr/local/bin/supercronic" | sha256sum -c -; \
    chmod 0755 /usr/local/bin/supercronic

RUN useradd --create-home --uid 1000 collectif \
    && mkdir -p /data /srv/static \
    && chown collectif:collectif /data /srv/static

COPY --chown=collectif:collectif . .
# Une crontab mal écrite fait échouer la construction, pas les sauvegardes de la nuit.
RUN supercronic -test /app/deploy/crontab

ENV DJANGO_ENV=prod \
    DJANGO_DB_PATH=/data/db.sqlite3 \
    DJANGO_BACKUP_DIR=/data/sauvegardes \
    DJANGO_STATIC_ROOT=/srv/static

USER collectif
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD ["python", "/app/deploy/sante.py"]
ENTRYPOINT ["/app/deploy/entrypoint.sh"]
CMD ["web"]
