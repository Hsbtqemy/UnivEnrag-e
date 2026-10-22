#!/usr/bin/env bash
#
# Met en ligne la dernière version de `main`, sur le serveur, depuis le clone du dépôt :
#
#   cd ~/collectif && ./deploy/deployer.sh
#
# Une suite de gardes qui refusent d'avancer dès que quelque chose cloche (idée reprise de
# BD_ditor, deploy/deployer.sh). Ce que le script ne fait PAS, exprès :
#   * il ne revient jamais en arrière tout seul : une migration ne se défait pas, et
#     remettre l'ancien code sur une base migrée serait pire que la panne. En cas d'échec,
#     il dit où il s'est arrêté ; la décision revient à quelqu'un qui a lu les journaux.
#   * il ne touche ni à `.env` ni aux volumes. Aucun secret n'est affiché.
#
# Variable : DERRIERE_PROXY=1 pour la variante derrière un relais HTTPS existant.

set -euo pipefail
cd "$(dirname "$0")/.."

stop() { echo "ARRÊT : $*" >&2; exit 1; }
step() { echo; echo "==> $*"; }

compose=(docker compose -f compose.yaml)
if [ "${DERRIERE_PROXY:-0}" = 1 ]; then
  compose+=(-f compose.derriere-proxy.yaml)
fi

step "Vérifications"
[ -f .env ] || stop "pas de fichier .env (copier .env.exemple et le remplir)."
grep -q '^DJANGO_SECRET_KEY=.\+' .env || stop "DJANGO_SECRET_KEY est vide dans .env."
domain=$(sed -n 's/^SITE_DOMAINE=//p' .env)
[ -n "$domain" ] || stop "SITE_DOMAINE est vide dans .env."
[ "$(git rev-parse --abbrev-ref HEAD)" = main ] || stop "le clone n'est pas sur la branche main."
git diff --quiet && git diff --cached --quiet || stop "modifications locales dans le clone : rien n'est déployé."

step "Récupération de la dernière version"
before=$(git rev-parse --short HEAD)
git pull --ff-only || stop "git pull impossible sans fusion : à régler à la main."
after=$(git rev-parse --short HEAD)
echo "version : $before -> $after"

step "Tests DANS l'image (ce qu'on teste est ce qu'on exécute)"
docker build --target test -t collectif:test . || stop "l'image de test ne se construit pas."
docker run --rm collectif:test || stop "tests en échec dans l'image : rien n'est déployé (version en place : $before)."

step "Construction de l'image livrée"
"${compose[@]}" build app || stop "l'image ne se construit pas : rien n'est déployé."

if [ -n "$("${compose[@]}" ps --status running -q app 2>/dev/null)" ]; then
  step "Sauvegarde avant la mise à jour (les migrations ne se défont pas)"
  "${compose[@]}" exec -T app python manage.py backup || stop "sauvegarde impossible : rien n'est déployé."
fi

step "Redémarrage"
"${compose[@]}" up -d --remove-orphans

step "Contrôle : https://$domain/sante/"
for _ in $(seq 1 30); do
  if curl -fsS --max-time 5 "https://$domain/sante/" >/dev/null 2>&1; then
    echo "En ligne : version $after."
    exit 0
  fi
  sleep 2
done
stop "le site ne répond pas après 60 s. Voir : docker compose logs app caddy (version précédente : $before)."
