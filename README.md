# Plateforme du collectif — POC d'agenda

Premier jalon de la plateforme décrite dans [le cahier des charges](docs/Cahier%20des%20charges%20—%20Plateforme%20du%20collectif.md) : un agenda collectif alimenté par des **propositions d'événements venues de l'extérieur**. Le périmètre est fixé par [la fiche du POC](docs/poc-calendrier-propositions.md), et les règles de travail par [CLAUDE.md](CLAUDE.md).

Le parcours couvert :

1. **Proposer** (`/proposer/`, public, sans compte) : nom, e-mail, titre, description, durée, jusqu'à trois créneaux possibles. La personne reçoit un lien de suivi personnel ; le site n'envoie aucun e-mail.
2. **Modérer** (`/gestion/moderation/`) : accepter, ne pas retenir (avec un motif), écarter le spam en lot.
3. **Placer** (`/gestion/programmation/`) : une colonne par salle, provisoires hachurés, autres créneaux envisagés en pointillé (un clic y déplace l'événement), panneau « À placer », glisser-déposer, et déplacement au clavier depuis le panneau de détails.
4. **Confirmer** : à l'unité ou par sélection. Seul un conflit de salle avec un événement confirmé bloque.
5. **Publier** (`/agenda/`, `/agenda/semaine/`, `/agenda.ics`) : uniquement les événements confirmés et publics, avec le nom du porteur, jamais son e-mail.

## Démarrer

Prérequis : Python 3.12+ et [uv](https://docs.astral.sh/uv/).

```bash
make install   # dépendances
make demo      # base SQLite + données de démonstration (compte admin : admin / demo-collectif-2026)
make dev       # http://127.0.0.1:8000
```

La démo commence **lundi prochain** : avancez d'une semaine dans les calendriers. L'administration est sur `/gestion/admin/`, la connexion admin donne accès à la modération et à la programmation.

Pour créer un vrai compte admin : `uv run python manage.py createsuperuser`.

## Vérifier

```bash
make test    # tests (règles métier, étanchéité du public, anti-spam, API)
make lint    # ruff + migrations à jour
```

## Organisation

```
config/          réglages (DJANGO_ENV=dev|test|prod), URL
apps/core/       en-têtes de sécurité, limitation de débit (IP hachée), anti-spam, dates
apps/actors/     Actor : une personne qui agit sous son nom, sans compte
apps/rooms/      Room : les salles gérées par le collectif
apps/ideas/      Idea, IdeaSlot : propositions d'événements, modération, suivi
apps/agenda/     Event : agenda collectif, conflits, programmation, pages publiques, iCal
templates/       gabarits (public, gestion)
static/          CSS, JS, @event-calendar servi en local (static/vendor/VERSIONS.md)
```

Toute écriture passe par les `services.py` de chaque app ; les vues ne font qu'appeler ces services.

## Production (à venir)

Le POC tourne avec `runserver`. Pour une mise en ligne de test : `DJANGO_ENV=prod`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_DB_PATH`, et `DJANGO_TRUST_X_FORWARDED_FOR=1` derrière un proxy qui écrase cet en-tête ; servir les fichiers statiques (`collectstatic`) derrière Caddy. Le choix d'infrastructure reste ouvert (CLAUDE.md, décision 19).
