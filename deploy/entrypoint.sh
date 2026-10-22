#!/bin/sh
# Point d'entrée de l'image : `web` (le site), `cron` (tâches planifiées), ou une commande.
set -eu

case "${1:-web}" in
  web)
    for dir in /data /srv/static; do
      if [ ! -w "$dir" ]; then
        echo "Le dossier $dir n'est pas accessible en écriture (volume créé par un autre conteneur ?)." >&2
        exit 1
      fi
    done
    # Le site seul applique les migrations : le cron attend qu'il soit en bonne santé.
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput --clear --verbosity 0
    # Pas de journal d'accès : aucune adresse IP côté Django (CLAUDE.md, RGPD).
    exec gunicorn config.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers "${GUNICORN_WORKERS:-3}" \
      --timeout 30 \
      --max-requests 1000 --max-requests-jitter 100
    ;;
  cron)
    exec supercronic /app/deploy/crontab
    ;;
  *)
    exec "$@"
    ;;
esac
