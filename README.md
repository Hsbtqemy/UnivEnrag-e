# Plateforme du collectif

Site du collectif décrit dans [le cahier des charges](docs/Cahier%20des%20charges%20—%20Plateforme%20du%20collectif.md). Règles de travail et état d'avancement : [CLAUDE.md](CLAUDE.md).

Ce qui existe :

- **Public, sans code** : page du collectif (`/p/` : présentation, prochains rendez-vous, actualités), agenda public (`/p/agenda/`, semaine et liste, flux `/p/agenda.ics`), actualités (`/p/actualites/`, flux RSS), contact (`/p/contact/`), proposition d'événement (`/p/proposer/`) avec lien de suivi personnel. Le site n'envoie aucun e-mail. Voir [la fiche du POC](docs/poc-calendrier-propositions.md).
- **Membres, avec le code d'accès commun** (`/acces/`) : accueil (`/accueil/`), agenda (`/agenda/`) où chacun crée, modifie, déplace ou annule un événement sous son nom, avec historique ; salles (`/salles/`, avec leur planning), abonnement iCal à l'agenda, à un espace ou à une salle (`/agenda/abonnements/`) ; « Qui est là ? » (`/presences/`), où chacun annonce ses demi-journées de présence ; sondages de dates (`/sondages/`), dont le meilleur créneau devient un événement ; idées et projets (`/idees/`) : dépôt en trois champs, réactions « Je participe », « Je peux aider », « Intéressé·e », tableau triable et filtrable, statuts ; programmation en colonnes par salle (`/agenda/programmation/`), où chacun place les idées et déplace les provisoires ; nom ou pseudo retenu par le navigateur (`/nom/`). Pas de compte.
- **Gestion** (`/gestion/`), comptes de l'administrateur principal et des gestionnaires, avec double authentification :
  - modération des propositions reçues, demandes de publication, réservations de salles à valider ;
  - sur chaque événement : confirmer, publier, verrouiller, restaurer une version ;
  - dans la programmation : confirmer (à l'unité ou par sélection, bloqué par les seuls conflits de salle) et publier ;
  - administration (`/gestion/admin/`) : comptes et droits, code d'accès, journal d'activité (administrateur principal seulement), salles, événements, anonymisation d'une personne ;
  - sauvegarde complète à télécharger (`/gestion/sauvegarde/`, administrateur principal).

## Mettre en ligne

Docker + Caddy + SQLite, sauvegarde chaque nuit : voir [docs/deploiement.md](docs/deploiement.md). En bref, sur le serveur : `cp .env.exemple .env`, le remplir, puis `./deploy/deployer.sh`.

## Démarrer

Prérequis : Python 3.12+ et [uv](https://docs.astral.sh/uv/).

```bash
make install   # dépendances
make demo      # base SQLite + données de démonstration
make dev       # http://127.0.0.1:8000
```

Démo :

| Quoi | Valeur |
|---|---|
| Code d'accès des membres | `collectif2026` |
| Administrateur principal | `admin` / `demo-collectif-2026` |
| Gestionnaire (agenda + modération) | `camille` / `demo-collectif-2026` |

La démo commence **lundi prochain** : avancez dans les calendriers. En développement, la double authentification est désactivée ; `DJANGO_ADMIN_2FA=1 make dev` permet de l'essayer (QR code à scanner avec une application d'authentification). Elle est toujours obligatoire en production.

Pour créer le vrai compte de l'administrateur principal : `uv run python manage.py createsuperuser`, puis choisir le code d'accès dans l'administration (Réglages du site).

## Vérifier

```bash
make test    # tests (règles métier, étanchéité du public, anti-spam, API)
make lint    # ruff + migrations à jour
make check-deploy   # réglages de production
make image-test     # la suite jouée dans l'image Docker (Docker requis)
```

## Organisation

```
config/          réglages (DJANGO_ENV=dev|test|prod), URL
deploy/          Caddyfile, crontab, point d'entrée de l'image, script de déploiement
Dockerfile, compose.yaml   image (base / test / runtime) et conteneurs app, cron, caddy
apps/core/       réglages du site, code d'accès (@public_view), en-têtes de sécurité, limitation de débit (IP hachée), anti-spam, dates, sauvegarde/restauration, /sante/
apps/actors/     Actor : une personne qui agit sous son nom, sans compte ; nom retenu par le navigateur
apps/audit/      journal d'activité des comptes de gestion (ajout seul)
apps/accounts/   comptes de gestion, 7 droits, double authentification
apps/rooms/      Room, OpeningHours : salles du collectif, horaires, réservation libre ou sur validation
apps/spaces/     Space : groupes de travail (nom, couleur, archivage)
apps/presences/  Presence : « je serai là », par demi-journée et lieu
apps/polls/      Poll, PollSlot, PollAnswer : sondages de dates
apps/public/     NewsPost, ContactMessage : actualités et contact de la page publique
apps/ideas/      Idea, IdeaSlot, Reaction : idées des membres et propositions extérieures (modération, suivi)
apps/agenda/     Event : agenda collectif, conflits, programmation, pages publiques, iCal
templates/       gabarits (public, membres, gestion)
static/          CSS, JS, @event-calendar servi en local (static/vendor/VERSIONS.md)
```

Toute écriture passe par les `services.py` de chaque app ; les vues ne font qu'appeler ces services.

## Production (à venir)

Le POC tourne avec `runserver`. Pour une mise en ligne de test : `DJANGO_ENV=prod`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_DB_PATH`, et `DJANGO_TRUST_X_FORWARDED_FOR=1` derrière un proxy qui écrase cet en-tête ; servir les fichiers statiques (`collectstatic`) derrière Caddy. Le choix d'infrastructure reste ouvert (CLAUDE.md, décision 19).
