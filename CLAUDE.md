# CLAUDE.md — Université Enragée (plateforme du collectif)

## Présentation

Ce dépôt contient un site web léger, autonome et hébergé hors de l'université, pour un collectif auto-organisé d'environ 50 personnes (il doit pouvoir passer à 300). Il sert à tenir un agenda commun, recueillir des idées sans vote, déposer des propositions et les voter, ouvrir des espaces de discussion, gérer des salles, publier une page publique et exporter les données.

Les participants n'ont pas de compte : ils entrent un **code d'accès commun** puis agissent sous un **nom ou pseudo**. Seuls l'administrateur principal et les gestionnaires se connectent.

**Source de vérité** : `docs/Cahier des charges — Plateforme du collectif.md` (le « CDC », cité sous la forme §N). Pour un détail fonctionnel, relis le CDC. Si ce fichier contredit le CDC, signale la contradiction au lieu de trancher en silence.

## État du projet

- **Le POC est codé** (22/10/2026) : agenda alimenté par des propositions extérieures, décrit dans `docs/poc-calendrier-propositions.md`. Voir le `README.md` pour le démarrer.
- **Phase 1 en cours**, par lots testés et commités un à un : A socle · B agenda des membres · C salles et espaces · D présences et sondages de dates · E idées des membres · F mise en ligne. **Pas de séries d'événements** (voir la décision 12).
  - **Lot A fait** : modèle `accounts.User` (7 droits, `require_capability`, `CapabilityAdminMixin`), double authentification TOTP + codes de secours (`accounts/two_factor.py`, obligatoire hors `DJANGO_ENV=dev`, forcée avec `DJANGO_ADMIN_2FA=1`), code d'accès commun (`core/access.py`, `@public_view`), nom mémorisé et `request.actor` (`actors/resolvers.py`), journal `audit.log()` en ajout seul, page `/gestion/` selon les droits.
  - **Lot B fait** : agenda des membres `/agenda/` (semaine, mois, liste par défaut sur téléphone, filtre par salle), création en un formulaire court (`/agenda/nouveau/`, pré-rempli depuis le créneau cliqué ou par duplication `?depuis=<id>`), modification, annulation (reste visible, barrée), glisser-déposer sous le nom retenu, avertissement de salle en direct (`/agenda/verifier/`), historique `EventChange` avec restauration, verrou, demandes de publication (`/gestion/publication/`).
  - **Lot C fait** : salles avec plages d'ouverture (`OpeningHours`, une salle sans plage n'a pas de restriction) et mode « libre » ou « soumise à validation » (`Event.room_status`, file `/gestion/salles/`, un refus retire la salle mais garde l'événement) ; dérogation (salle occupée ou fermée) par le seul droit « salles », case `override`, journalisée `rooms.derogation` ; page `/salles/` ; app `spaces` minimale (nom, couleur, archivage), couleur et filtre par espace dans l'agenda ; flux iCal internes par jeton `/flux/<feeds_token>/{agenda.ics, espace/<slug>.ics, salle/<id>.ics}` et page `/agenda/abonnements/` (le flux public n'inclut jamais le lien visio).
  - **Lot D fait** (choix du porteur du projet, 22/10/2026) : **présences plutôt qu'indisponibilités**. Chacun annonce « je serai là » par demi-journée (matin, après-midi, soir) avec un lieu par jour (`/presences/ma-semaine/`, bouton « reprendre ma semaine précédente », pas de règle récurrente) ; tableau « Qui est là ? » (`/presences/`). Présences purgées après 60 jours (`purge_presences`, à planifier). **Sondage de dates** avancé de la phase 2 (app `polls`, nominatif, « oui » / « si besoin ») : « Fixer ce créneau » ouvre le formulaire d'événement pré-rempli et clôt le sondage.
  - **Lot E fait** : idées des membres (`/idees/`). Une proposition extérieure est une `Idea` d'origine `external` qui passe d'abord par `pending` (modération) ; acceptée, elle devient `new` et suit le cycle commun `new`/`preparing`/`abandoned` (à la main) → `planned` → `done` (automatiques). Champs du CDC §4 (type, espace, format, durée, public, intervenants pressentis, besoins, contraintes, créneaux), réactions `Reaction` à bascule, tableau triable (date, intéressés, titre) et filtrable (type, espace, public, statut ; « En cours » par défaut). Un créneau précis place l'idée en provisoire, **non publique** pour une idée de membre (publique par défaut pour une proposition extérieure, comme au POC). « Créer un événement depuis cette idée » (`/agenda/nouveau/?idee=<id>`) donne un provisoire lié. Abandonner annule les placements provisoires. `Event.idea` est une clé étrangère (décision 13). **La programmation est ouverte aux membres** (`/agenda/programmation/`) : placer et déplacer sous son nom, filtres type/espace/public/statut, avertissements désactivables ; confirmer et publier restent sous `/gestion/api/` (droits « agenda » / « page publique »). L'e-mail du porteur n'est envoyé qu'aux comptes de gestion. Intervenants : `Event.speakers` (noms libres, pré-remplis depuis l'idée) et `speakers_public` (PUB-1 : page et flux publics seulement si coché) ; avertissement AGE-7 « mêmes intervenants à la même heure », toutes salles confondues, noms comparés après normalisation, aussi en direct dans le formulaire. Une restauration ignore les champs absents d'une version ancienne. Reste à faire : l'avertissement « même public visé en parallèle » (l'événement n'a pas de champ public), pas de commentaires sur les idées (fil `discussions`, phase 3), pas de transformation en proposition (IDE-4, phase 2).
  - **Site installable** : `/manifest.webmanifest`, service worker `/sw.js` (enregistré en production seulement : en développement, les statiques gardent des noms fixes), page `/hors-ligne/`. Le service worker ne met **jamais** une page en cache (espace des membres, téléphones partagés) : seulement les statiques versionnés et la page hors ligne. Icônes générées par `scripts/icones.py`.
  - **Page publique (avancée de la phase 3, décision du porteur du projet, 22/10/2026 : tout en Django, pas d'Astro)** : app `public`. `/` envoie les visiteurs vers `/p/` (présentation en Markdown assaini par `core/markdown.py`, prochains rendez-vous, dernières actualités) ; actualités `NewsPost` (`/p/actualites/`, flux RSS `/p/actualites.rss`, publiées seulement via `NewsPost.objects.public()`, jamais supprimées) ; contact `/p/contact/` (`ContactMessage`, e-mail facultatif, anti-spam et limitation de débit, purgé au bout d'un an par `purge_contact_messages`) ; présentation éditée dans `/gestion/presentation/` avec aperçu. Le tout réservé au droit « Page publique ». Les visiteurs et les membres ont chacun leur navigation.
  - **Idées publiques** (décision du porteur du projet, 23/10/2026) : le formulaire public `/p/proposer/` (« Proposer une idée ») reçoit des événements, des projets et des envies ; durée, créneaux et salle ne valent que pour un événement. E-mail obligatoire pour tous les types. Case « Ne pas afficher mon nom sur la page publique » (`Idea.owner_hidden`), aussi au dépôt d'une idée de membre et sur le lien de suivi. Une idée n'est publique que si un habilité « modération » ou « page publique » le décide (`Idea.is_public`, case à l'acceptation ou cadre « Page publique » de la fiche interne, `services.set_public`, journalisé) ; `/p/idees/` lit **uniquement** `Idea.objects.public()` (cochée et `new`/`preparing`/`planned`/`done`). Le public y voit titre, type, statut, description, espace, format, public visé et les événements publics liés, jamais l'e-mail, les besoins, les contraintes, les intervenants pressentis ni les créneaux. Il réagit sous un nom (`/p/idees/<id>/reagir/`, limité par `PUBLIC_REACTION_RATE_LIMIT`) : la page publique n'affiche que les nombres, les membres voient les noms, et une réaction publique ne se retire jamais (n'importe qui peut taper n'importe quel nom). Reste à faire : décisions publiques (phase 2), demande d'adhésion.
  - **Guides** dans le site : `/aide/` pour les membres (lien dans le pied de page et l'accueil), `/gestion/aide/` pour les gestionnaires. Les tenir à jour quand un libellé ou un parcours change.
  - **Navigation** décrite une seule fois dans `apps/accounts/navigation.py` (liens des membres ou des visiteurs, onglet en cours) : onglets soulignés sur ordinateur, barre d'onglets en bas de l'écran sous 60rem (liens `primary`, les autres sous « Plus », un `<details>` sans JavaScript). Ajouter une page = y ajouter son lien.
  - **Session de gestion sans TOTP** : hors de `/gestion/`, elle est traitée comme anonyme (`RequireTwoFactorMiddleware`), donc sans aucun droit ni dispense de code d'accès (ACC-3).
  - `request.actor` vaut `None` sans nom ni compte (résolu tout de suite, pas d'objet paresseux).
  - **Historique : modèle maison `agenda.EventChange`** (et non django-simple-history) : chaque entrée référence un `Actor`, garde `changes` ({champ: [avant, après]}) et un `snapshot` complet pour restaurer. Toute écriture sur un événement passe par `agenda/services.py`, qui l'enregistre.
  - URL : public sous `/p/` (`/p/agenda/`, `/p/proposer/`, `/p/idees/`, `/p/suivi/<jeton>/`, `/p/agenda.ics`), interne `/accueil/`, `/nom/`, `/agenda/`, `/agenda/programmation/`, `/idees/`, `/salles/`, `/presences/`, `/sondages/`, gestion `/gestion/` (admin Django sous `/gestion/admin/`).
  - **Lot F fait (mise en ligne)**, décision 19 tranchée : SQLite + Docker + Caddy, la pile déjà éprouvée par le porteur du projet sur BD_ditor. `Dockerfile` en trois étapes (`base`, `test` qui joue la suite DANS l'image, `runtime` non root), `compose.yaml` (`app` gunicorn sans journal d'accès, `cron` supercronic épinglé par sha256, `caddy` HTTPS automatique et fichiers statiques, sans journal d'accès), variante `compose.derriere-proxy.yaml` pour un serveur qui a déjà un relais HTTPS (**cas réel : le serveur partagé avec Improliante et BD_ditor, où le Nginx de l'hôte tient 80/443 et gère certbot ; à activer par `COMPOSE_FILE` dans `.env`, bloc Nginx dans `deploy/nginx-hote.conf.exemple` ; adresse `univ-enragee.edito-revue.fr`, domaine du porteur du projet, sslip.io en repli**), `deploy/deployer.sh` (gardes, tests dans l'image, sauvegarde avant migration, jamais de retour arrière automatique), CI `.github/workflows/ci.yml`. Mode d'emploi : `docs/deploiement.md`. Statiques versionnés en production (`apps/core/storage.py`, qui ignore les `.map` des bibliothèques tierces). Sauvegarde et restauration : `apps/core/backup.py`, commandes `backup` et `restore`, bouton « Sauvegarde complète » (`/gestion/sauvegarde/`, superuser). `/sante/`, page `/p/donnees-personnelles/` (contact réglable dans les Réglages du site), anonymisation d'une personne par une action de l'admin (superuser). Pas de Docker sur le poste de développement : l'image est construite et essayée par la CI (suite dans l'image, démarrage du conteneur). **Reste à organiser : la copie des sauvegardes hors du serveur.**
  - **Choix restés simples, à revoir si besoin** : ni htmx, ni django-csp (la CSP est posée par `core/middleware.py`), ni WhiteNoise (Caddy sert les statiques), ni django-environ (réglages lus dans `os.environ`, `.env` lu par Docker Compose), ni pre-commit. Une seule salle par événement.
  - Le reste de ce fichier décrit encore quelques **cibles à créer** (phases 2 et 3 : votes, discussions, exports, recherche).
- Commence par la **phase 1** (voir « Phasage »). Ne code pas une phase suivante avant que le collectif ait validé la phase en cours. Seule exception : les modèles minimaux dont la phase en cours a besoin.
- Tiens ce fichier à jour : quand une cible devient réelle, quand une décision par défaut est confirmée ou changée, quand une commande change.

## Stack

| Brique | Choix |
|---|---|
| Langage, framework | Python 3.13 (3.12 au minimum), **Django 5.2 LTS** |
| Base | **SQLite en WAL** : `transaction_mode="IMMEDIATE"`, `busy_timeout=5000`, `foreign_keys=ON`. Le seul code propre à SQLite (FTS5) est isolé dans `apps/core/search.py`, pour pouvoir passer à PostgreSQL au-delà de 300 personnes |
| Interactivité | Rendu serveur + **htmx 2.0** + `django-htmx`. Pas de SPA, pas de chaîne Node |
| Agenda | **`@event-calendar` 5.3** (vkurko/calendar, **MIT**), bundle autonome `@event-calendar/build` (`event-calendar.min.js` + `.min.css`) copié dans `static/vendor/`, jamais chargé depuis un CDN. Il fournit les vues semaine, mois et liste, **les colonnes par salle** (`resourceTimeGridDay` / `resourceTimeGridWeek`) et le glisser-déposer (plugin interaction inclus). Son API est proche de FullCalendar, sans module payant |
| CSS | Pico CSS 2 copiée dans le dépôt + `static/css/app.css` (variables ; modes clair, sombre et « Enragé » rouge braise, choisis par l’icône de l’en-tête, `static/js/theme.js`) |
| Formats | `icalendar` 6 ; `django.contrib.syndication` (RSS) ; CSV natif (UTF-8 avec BOM, séparateur `;`) ; **WeasyPrint** (PDF, polices dans le dépôt) |
| Markdown | `markdown` + `nh3`. Balises autorisées : p, br, strong, em, ul, ol, li, a. Les liens reçoivent `rel="nofollow noopener"` |
| Historique | Modèle maison `agenda.EventChange` (avant/après par champ + instantané pour restaurer), dont l'auteur est un `Actor` |
| Administrateurs | `argon2-cffi`, `django-otp` (TOTP + codes de secours), `segno` (QR code en SVG) |
| Sécurité HTTP | `django-csp` 4 : `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'` |
| Statique, configuration | Caddy sert `/static/` (noms versionnés, cache d'un an) ; un seul `config/settings.py` piloté par `DJANGO_ENV=dev|prod|test` et des variables d'environnement (`.env` lu par Docker Compose) |
| Production | Docker multi-étapes (utilisateur non root) + `compose.yaml` : `app` (gunicorn, journal d'accès désactivé), `caddy` (HTTPS automatique), `cron` (supercronic), volume `/data` (base, sauvegardes). **Ni Celery ni Redis** |
| Qualité | `uv` (`pyproject.toml` + `uv.lock`), `ruff` (E,F,I,B,UP,DJ,S,SIM, ligne de 100), `pytest`, `pytest-django`, `factory-boy`, `time-machine`, `pre-commit` |

Les bibliothèques JS et CSS tierces vont dans `static/vendor/<lib>-<version>/`. Elles sont téléchargées par `scripts/fetch_vendor.sh` (versions épinglées, sha256 vérifiés) et recensées dans `static/vendor/VERSIONS.md`.

## Contraintes dures (non négociables)

- **Aucune ressource externe** : ni CDN, ni Google Fonts, ni script, police ou CSS tiers chargé à distance. La CSP le garantit, ne l'assouplis jamais pour un domaine extérieur. Le navigateur ne contacte jamais un service tiers : même les calendriers externes (ADE) sont récupérés par le serveur. (§9)
- **Aucun envoi d'e-mail** : pas de serveur mail, pas de notification, pas de lien envoyé. L'information passe par le site, l'iCal et le RSS. (§7, §9)
- **Deux champs e-mail seulement** : celui du porteur d'une idée ou d'un événement proposé depuis la page publique (PUB-2, obligatoire) et celui, **facultatif**, du formulaire de contact public (décision du porteur du projet, 22/10/2026 : « on connaît les gens », on retrouve ceux qui n'en laissent pas). Tous deux servent à répondre hors du site, et à rien d'autre. Ailleurs, pas de champ e-mail.
- **Aucun traceur** ni outil d'analyse. Les seules données personnelles collectées sont le nom ou pseudo, l'e-mail du porteur d'un événement et celui, facultatif, d'un message de contact. (§9, modifié par PUB-2)
- **Licence libre** (§9). Aucune dépendance n'impose de licence particulière : le choix revient au collectif (voir les décisions).
- **SQLite** comme base unique, sans service supplémentaire à exploiter.
- **Interface en français**, accessibilité RGAA / WCAG 2.1 AA, responsive, installable (manifest + service worker). Toute action courante doit se faire en **3 clics au plus** depuis l'accueil. (§9)

## Architecture

### Arborescence cible

```
config/            settings.py urls.py wsgi.py
apps/
  core/            SiteSettings (singleton), middlewares, ratelimit, search (FTS5), markdown, csv,
                   décorateurs public_view / require_capability, accueil, saisie du code
  actors/          Actor, résolveurs, normalisation des noms, anonymisation RGPD
  accounts/        User personnalisé (dès la 1re migration), 7 droits, connexion + TOTP obligatoire
  audit/           AuditLog en ajout seul, audit.log()
  rooms/           Room, OpeningHours
  spaces/          Space, Document, MeetingReport
  discussions/     Thread, Message (fil unique pour sujets, idées, propositions)
  agenda/          Event, EventChange, EventType, Audience, Unavailability, ExternalCalendar,
                   recurrence.py conflicts.py services.py queries.py api.py
  ideas/           Idea, IdeaSlot, Reaction
  proposals/       Proposal, ProposalVersion, Support
  votes/           Vote, VoteOption, Ballot, BallotChoice, AnonymousTally, InPersonTally, counting.py
  moderation/      IPBlock, masquage, écran d'anonymisation
  public/          NewsPost, ContactMessage, MembershipRequest, vues publiques
  exports/         ical.py rss.py csv_exports.py pdf.py backup.py, commandes backup / restore
templates/         base.html base_internal.html base_public.html base_gestion.html includes/ errors/
static/            css/ js/{agenda,programming,actor,newbadge,theme}.js fonts/ vendor/
deploy/            Caddyfile Caddyfile.derriere-proxy crontab entrypoint.sh sante.py deployer.sh
Dockerfile compose.yaml compose.derriere-proxy.yaml .env.exemple
tests/             conftest.py factories.py acceptance/test_reception.py
```

Chaque app suit la même structure : `apps.py models.py services.py views.py urls.py forms.py admin.py templates/<app>/ tests/`. Le nom est de la forme `name="apps.agenda"`, `label="agenda"`.

Les dépendances vont dans un seul sens : `core ← actors ← audit ← accounts ← {rooms, spaces, discussions} ← agenda ← ideas ← proposals ← votes ← {exports, public}`. (`audit` ne connaît les comptes que par `settings.AUTH_USER_MODEL` ; `accounts` l'appelle.) Entorses admises : la vue de programmation (`agenda/views.py`) lit les idées à placer et leurs créneaux ; la création d'événement (`agenda/member_views.py`) lit l'idée d'origine ; `agenda.services.confirm` et `cancel` importent `ideas.services` à l'intérieur de la fonction ; l'accueil et la création d'événement (`agenda/views.py`, `agenda/member_views.py`) lisent `presences` et `polls`. Entre modèles, les clés étrangères s'écrivent sous forme de chaîne (`"agenda.Event"`).

### Couches

- **Toute écriture passe par `services.py`.** Les fonctions reçoivent `actor` et/ou `user` explicitement, valident les règles métier, s'exécutent dans `transaction.atomic()` et appellent `audit.log()` dès que l'auteur est un gestionnaire ou l'administrateur.
- Les vues restent minces : formulaire, appel au service, rendu. Les lectures complexes vont dans des méthodes de `QuerySet` (`queries.py`).
- Les vues publiques lisent **uniquement** via `Event.objects.public()` et `Proposal.objects.public_decisions()`. C'est un point d'entrée unique et testé.

### Modèle « acteur » (prévu pour une identification individuelle future, §2)

- `Actor(id UUID, display_name, name_key unique, user OneToOne null, anonymized_at)`. `name_key` est le nom normalisé : NFKD sans accents, casefold, espaces fusionnés, ponctuation retirée.
- **Un acteur correspond à un nom, pas à un navigateur.** « Marie » saisi depuis deux téléphones donne le même acteur.
- **Toute contribution référence `Actor` par clé étrangère** (événements, historique, messages, idées, réactions, propositions, versions, soutiens, bulletins nominatifs, documents, indisponibilités). Aucun champ texte libre ne sert d'auteur.
- Un seul point de résolution : `request.actor`, posé par `ActorMiddleware` via `settings.ACTOR_RESOLVER`.
  - Aujourd'hui, `NameCookieResolver` lit le cookie `pseudo`.
  - Un gestionnaire connecté est résolu vers `user.actor`.
  - Demain, un `AccountResolver` et une commande `claim_actor` suffiront, **sans changer aucune clé étrangère ni aucune vue**.
- L'acteur est créé à la première écriture (`actors.services.get_or_create_for_name()`). Les formulaires d'action héritent de `ActorNameFormMixin` (champ `author_name` pré-rempli). **Les vues et les services ne lisent jamais le cookie `pseudo` directement.**
- L'anonymisation RGPD tient en une seule écriture sur `Actor` : `display_name="Anonyme"`, `name_key="anonyme:<uuid>"`. Les champs texte libres (`organizers_text`, `speakers_text`, `Event.speakers`) sont listés pour être corrigés à la main.
- Le cookie signé `browser_id` ne sert qu'aux aides « déjà voté » et « modifier mon vote ». En base, il n'apparaît que sous la forme `browser_hash = HMAC(SECRET, browser_id + vote_id)`, et seulement sur les bulletins nominatifs.

### Code d'accès et vues publiques

- `AccessCodeMiddleware` est **fermé par défaut** : une vue n'est publique que si elle porte `@public_view`. Sont publiques : `/`, `/p/*`, `/acces/`, `/sante/`, `/static/*`, `/gestion/*` (connexion : `/gestion/admin/login/`), et les flux à jeton.
- Une saisie réussie pose le cookie signé `acces = SiteSettings.access_code_stamp` (400 jours, httponly, Secure, Lax). Changer le code régénère `access_code_stamp`, ce qui invalide aussitôt tous les cookies.
- Les flux iCal et RSS internes passent par `/flux/<feeds_token>/…`. Ce jeton est indépendant du code d'accès et révocable par le superuser. Les flux publics (`/p/agenda.ics`, `/p/decisions.rss`) n'ont pas de jeton.
- Toute réponse non publique porte `X-Robots-Tag: noindex, nofollow` et `<meta name="robots" content="noindex">`. `robots.txt` n'autorise que `/` et `/p/`.

## Commandes

Disponibles (`Makefile`) :

| Commande | Effet |
|---|---|
| `make install` | `uv sync` |
| `make dev` | `runserver` sur la base `db.sqlite3` (ou `DJANGO_DB_PATH`) |
| `make migrate` | `makemigrations` puis `migrate` |
| `make demo` | `migrate` puis `seed_demo --reset` : code d'accès `collectif2026`, administrateur `admin` et gestionnaire `camille` (agenda + modération), mot de passe `demo-collectif-2026`, salles, propositions dans tous les états, événements datés à partir de lundi prochain |
| `make test` | `uv run pytest` |
| `make lint` / `make fmt` | `ruff check` + `ruff format --check` + migrations à jour / correction automatique |
| `make check-deploy` | `manage.py check --deploy --fail-level WARNING` avec des réglages de production factices |
| `make backup` | sauvegarde de la base locale dans `sauvegardes/` |
| `make image-test` | construit l'étape `test` de l'image et y joue la suite (Docker requis) |

En production (voir `docs/deploiement.md`) : `./deploy/deployer.sh` met en ligne ; `manage.py restore <archive> [--confirmer]` restaure.

Cibles à créer : `pre-commit`, `scripts/fetch_vendor.sh`, la copie des sauvegardes hors du serveur, et la démo des phases suivantes (votes, discussions).

Tâches planifiées (`deploy/crontab`, supercronic, fuseau Europe/Paris) :

| Fréquence | Commande |
|---|---|
| 3 h | `backup` (rotation sur 30 jours) |
| Chaque nuit | `purge_presences`, `purge_ip_data`, `clearsessions`, `purge_contact_messages` |
| Chaque heure | `ideas_mark_done` |
| À ajouter avec leurs phases | `close_due_votes` (chaque minute), `refresh_external_calendars` (30 min) |

## Conventions de code

- **Identifiants en anglais** (modèles, champs, fonctions, fichiers). **Tout ce que voit l'utilisateur est en français**, écrit directement : templates, `verbose_name`, messages, URL (`/agenda/`, `/idees/`, `/propositions/`, `/votes/`, `/espaces/<slug>/`, `/salles/`, `/gestion/`, `/p/…`), PDF, CSV. Pas de `gettext` ni de `.po`. Réglages : `LANGUAGE_CODE="fr-fr"`, `USE_I18N=True`, `TIME_ZONE="Europe/Paris"`, `USE_TZ=True`.
- **Commentaires, docstrings, commits et documentation en français.** Chaque règle métier cite le CDC, par exemple `# CDC §4 Garanties : un vote par nom`. Format des commits : `agenda: avertissement de salle avant l'enregistrement`.
- Les templates htmx partiels sont préfixés par `_`. La vue choisit le fragment selon `request.htmx`. **Pas de `hx-on`** (il est incompatible avec la CSP) et **pas de script inline** : la configuration JS passe par `{{ config|json_script:"…" }}`.
- `|safe` est **interdit**, sauf sur la sortie de `core.markdown.render()`.
- Formulaires accessibles : `label` explicite, erreurs liées par `aria-describedby`. Le glisser-déposer a **toujours** une alternative au clavier (vue liste et formulaire d'édition).
- Choix techniques du client agenda : vue liste par défaut sous 640 px. Un POST de déplacement envoie `X-CSRFToken` et `revision`. Un code 409 déclenche `info.revert()`.

Glossaire FR→EN : acteur=Actor · gestionnaire=manager (User avec droits) · espace=Space · sujet/fil=Thread · salle=Room · plage d'ouverture=OpeningHours · idée=Idea (y compris une **proposition d'événement** venue de l'extérieur : `Proposal` reste réservé aux propositions à voter) · créneau envisagé=IdeaSlot · réaction=Reaction · proposition=Proposal · amendement=ProposalVersion · soutien=Support · scrutin=Vote · bulletin=Ballot · en séance=in_person · indisponibilité=Unavailability · compte rendu=MeetingReport · actualité=NewsPost · provisoire/confirmé/annulé=provisional/confirmed/cancelled · verrou=lock · masquer=hide.

## Règles métier invariantes

« Habilité » désigne l'administrateur principal (`is_superuser`) ou un gestionnaire qui a le droit du domaine concerné. Les 7 droits (`Meta.permissions` de `User`) sont : `manage_votes`, `manage_agenda`, `manage_rooms`, `manage_spaces`, `moderate`, `manage_public`, `export_data`.

**Accès et rôles**
- ACC-1. Toute page interne exige un code d'accès valide, sinon redirection vers `/acces/`. Changer le code invalide tous les navigateurs. (§2)
- ACC-2. Un participant ne fournit qu'un nom ou pseudo : pas de compte, pas de mot de passe, pas d'e-mail. Le nom est demandé à la première action, puis pré-rempli et modifiable. (§2)
- ACC-3. Les comptes administrateurs exigent un mot de passe robuste **et le TOTP** : sans appareil confirmé, l'utilisateur est redirigé vers `/gestion/2fa/`, et hors de `/gestion/` une session non vérifiée n'a aucun droit. L'admin Django passe par `OTPAdminSite`. (§2, §9)
- ACC-4. Sont réservés au superuser : changer le code d'accès, créer ou retirer des gestionnaires et leurs droits, consulter le journal d'activité, télécharger une sauvegarde. Un retrait invalide immédiatement les sessions du gestionnaire. (§2, §8)
- ACC-5. Un gestionnaire n'a que les droits cochés. Toute autre action lui est refusée (`@require_capability`). (§8)
- LOG-1. Toute action d'un habilité est tracée dans `AuditLog` (qui, quoi, quand, objet). Ce journal accepte uniquement des ajouts : ni modification ni suppression depuis l'interface. (§8)

**Agenda et salles**
- AGE-1. Un événement a trois statuts, `provisional`, `confirmed` et `cancelled`. Un événement annulé reste visible et barré. **Un événement n'est jamais supprimé.** (§3)
- AGE-2. Seuls le titre, le début et la fin sont obligatoires, avec fin > début. (§3)
- AGE-3. Tout participant crée, modifie, déplace, duplique ou annule un événement non verrouillé, sous son nom. **Seulement si le réglage « Les membres modifient l'agenda directement » est coché** (décision 22) ; sinon, un participant consulte et propose (idée), et seuls les habilités « agenda » écrivent dans l'agenda et la programmation. **Seul un habilité « agenda » peut passer un événement de `provisional` à `confirmed`**, à l'unité ou par lot. (§3)
- AGE-4. Toute modification crée une entrée d'historique : nom saisi, date, avant et après, champ par champ. Un habilité « agenda » peut restaurer une version, et la restauration crée elle-même une nouvelle entrée. (§3, §11)
- AGE-5. Un événement verrouillé refuse toute modification par un participant (formulaire, glisser-déposer, annulation). Les modifications concurrentes sont détectées par verrouillage optimiste (`revision`, réponse 409). (§3)
- AGE-6. **Pas de séries d'événements.** Un événement qui revient se crée par « Dupliquer » (formulaire pré-rempli) ou se recrée. Ne pas ajouter de modèle de série ni de règle de récurrence. *Décision du porteur du projet (22/10/2026), qui retire ce point du CDC §3.*
- SAL-1. Une réservation **est** un `Event` rattaché à une `Room` : il n'existe pas d'entité de réservation séparée. (§6)
- SAL-2. **Conflit bloquant** : un chevauchement strict dans la même salle avec un événement `confirmed`, ou dont la salle est `pending` ou `approved`. Deux événements bout à bout ne sont pas en conflit. Salles différentes, « lieu libre » et événements annulés ne déclenchent jamais de conflit. Le contrôle se fait **côté serveur**. La dérogation est réservée à un habilité « salles » et journalisée. (§3, §6)
- SAL-3. Une réservation hors des `OpeningHours` est refusée, sauf dérogation journalisée. (§6)
- SAL-4. Une salle `approval` met la réservation en `pending` jusqu'à sa validation. Une réservation en attente bloque déjà le créneau. (§6)
- AGE-7. Mêmes intervenants à la même heure, ou même public visé en parallèle : simple **avertissement**, désactivable, jamais bloquant. L'occupation de la salle est signalée dans le formulaire avant l'enregistrement (`hx-get /agenda/verifier/`). (§3)
- AGE-9. Les calendriers externes et les indisponibilités sont en lecture seule et affichés grisés, sans détail (« Nom – indisponible »). Ils ne sont **jamais** publics, confirmables ou exportés publiquement. (§3)

**Idées**
- IDE-1. Seuls le nom, le titre et le type (`event`, `project`, `wish`) sont obligatoires. Une idée **ne passe jamais par un vote**. (§4)
- IDE-2. Une idée a un créneau précis → elle est placée en provisoire (hachurée) sur son créneau préféré, et ses autres créneaux s'affichent en pointillé. Une idée sans créneau précis va dans « À placer ». Les créneaux ne sollicitent aucune réponse. (§3, §4)
- IDE-3. À la confirmation, l'événement est pré-rempli (titre, description, intervenants, salle). L'idée passe **automatiquement** à `planned`, puis à `done` une fois la fin de l'événement dépassée (`ideas_mark_done`). (§4)
- IDE-4. Une idée se transforme en proposition sans ressaisie (titre, description, espace, auteur, pièces jointes via le même `Thread`). L'idée subsiste, avec un lien croisé. (§4)

**Propositions et votes**
- PRO-1. Transitions autorisées : dépôt→`discussion` ; `discussion`→`voting` (habilité votes) ; `voting`→`adopted`|`rejected` (automatique à la clôture) ; `adopted`→`implementing` (habilité) ; `discussion`→`withdrawn` (habilité, à la demande de l'auteur). **Toute autre transition lève une erreur** (`services.transition`). (§4)
- PRO-2. Les amendements créent une `ProposalVersion` en ajout seul. Au vote, **le texte est figé**, et le vote porte sur une version précise. (§4)
- VOT-1. Le paramétrage est affiché avant le bulletin et **immuable dès l'ouverture** (`params_snapshot`). `Vote.save()` lève une exception si un paramètre change hors `draft`. (§4, §8)
- VOT-2. **Un vote anonyme n'enregistre aucun nom** : aucune ligne `Ballot`, aucun `Actor` créé, aucun historique, aucune IP. Seuls `AnonymousTally.count` et `anonymous_ballot_count` sont incrémentés. (§4, §10)
- VOT-3. Vote nominatif : la liste des votants est visible. Un nom déjà présent (après normalisation, tous canaux confondus) est **signalé avant validation**. `UniqueConstraint(vote, actor, condition=status="valid")`. (§4, §10)
- VOT-4. Un habilité « votes » peut invalider un bulletin avec un motif affiché dans le vote. Le bulletin est conservé, marqué, et exclu du décompte. (§4)
- VOT-5. Avec `allow_change`, le même navigateur modifie son bulletin jusqu'à la clôture, sans en créer un second. Après la clôture, plus rien ne change. (§4)
- VOT-6. Avec `results=after_close`, les décomptes sont masqués **partout** (pages, fragments, RSS, CSV) jusqu'à la clôture. (§4)
- VOT-7. La clôture est automatique (`close_due_votes`, et à la volée à la lecture d'un vote échu). Elle fige `result` et applique le statut de la proposition. (§4)
- VOT-8. Quorum non atteint → `rejected` (« quorum non atteint »). Seuil simple ou qualifié (2/3 par défaut) → `adopted` seulement s'il est atteint. (§4, §10)
- VOT-9. En séance et en hybride, `InPersonTally` (main levée) ou `Ballot(channel=in_person, entered_by)`. Chaque saisie est horodatée, attribuée et journalisée. Le décompte affiche séparément en ligne, en séance et total. Un nom présent dans les deux canaux est signalé : le gestionnaire choisit, l'autre bulletin passe en `superseded` avec un motif. (§4)
- VOT-10. `counting.py` ne contient que des **fonctions pures** (`Distribution` → `Result`), sans accès à la base.

**Espaces, modération, page publique**
- ESP-1. Un espace archivé est en lecture seule. Les réponses n'ont qu'un niveau. Seuls gras, listes et liens sont permis, avec un HTML assaini. (§5)
- ESP-2. Les fichiers sont contrôlés **côté serveur** : 20 Mo maximum, liste blanche pdf, odt/ods/odp, doc(x)/xls(x)/ppt(x), txt, md, png, jpg, webp. **Pas de SVG ni de HTML.** Ils sont servis après contrôle d'accès, en `attachment` sauf pdf et images. (§5)
- MOD-1. **Aucune suppression** de messages, idées ou propositions. On masque (`Moderatable`) avec un motif visible à la place du contenu. Dans l'admin, `has_delete_permission` renvoie `False`. Un blocage d'IP dure 30 jours au plus. (§8)
- PUB-1. **Rien n'est public par défaut.** Seuls les événements `confirmed` **et** `is_public`, les idées cochées `is_public` par un habilité (`Idea.objects.public()`), et les propositions adoptées marquées `is_public_decision`, sortent, sans aucun nom de votant ni de personne qui réagit. Les intervenants ne sont affichés que si `speakers_public`, le nom du porteur d'une idée que sans `owner_hidden`. (§7)
- PUB-2. **Un événement est porté par quelqu'un.**
  - Le **nom du porteur** est affiché avec l'événement, y compris sur la page publique et dans les flux publics. Le formulaire l'annonce avant l'envoi : proposer un événement vaut accord.
  - L'**e-mail du porteur** est obligatoire et **réservé à l'interne** : visible des admins (et gestionnaires) dans l'administration, **jamais** sur la page publique, dans un flux, un export public ou le HTML d'une page publique.
  - Le site **n'envoie jamais rien** à cette adresse. Les admins écrivent eux-mêmes depuis leur messagerie quand il faut transmettre une information (un lien `mailto:` dans l'administration suffit). Tout n'a pas à être automatisé.
  - L'adresse n'est pas purgée (adresse universitaire, déjà connue en interne).
  - *Décision du porteur du projet (21/10/2026), qui s'écarte du CDC §7 et §9 : elle prime sur eux.*

## Sécurité et RGPD

- HTTPS obligatoire : HSTS, cookies `Secure`, `SECURE_PROXY_SSL_HEADER`, `X_FRAME_OPTIONS="DENY"`, `Referrer-Policy: same-origin`. `check --deploy` doit passer en CI.
- Les protections CSRF, XSS et ORM de Django restent actives. Pas de `csrf_exempt`, pas de SQL brut hors migrations et `core/search.py` (avec paramètres liés).
- Limitation de débit dans `core/ratelimit.py`, sur la table `RateLimitHit`, avec la clé `HMAC(SECRET, ip)` et **jamais l'IP en clair**. Les limites sont larges, parce qu'environ 50 personnes peuvent partager l'IP de l'université :

| Seau | Limite |
|---|---|
| Échecs du code d'accès | 10 / 10 min |
| Échecs de connexion admin | 5 / 15 min par (IP + identifiant) |
| Votes | 300 / 10 min |
| Messages, idées, événements | 200 / 10 min |
| Envois de fichiers | 30 / h |

  Un dépassement renvoie une page 429 en français.
- Les IP ne figurent jamais dans les données métier. Elles n'apparaissent que dans les journaux Caddy (30 jours), dans `RateLimitHit` sous forme d'empreinte, et dans `IPBlock` (30 jours au plus). Toutes sont purgées par `purge_ip_data`. Django ne journalise aucune IP.
- La page « Données personnelles » (`/p/donnees-personnelles/`) indique la finalité, les responsables, les durées et les droits. L'anonymisation se fait sur demande : aujourd'hui par l'action « Anonymiser » de l'admin des personnes (superuser), demain depuis l'écran de modération.
- Sauvegarde quotidienne via `sqlite3.Connection.backup()` (jamais un `cp` sur une base en WAL), avec une archive des médias et un `manifest.json`. Rotation sur 30 jours, copie `restic` hors du serveur. Le bouton « Sauvegarde complète » est réservé au superuser.

## Tests obligatoires

Les tests des règles de vote sont exigés par le CDC (§10, §11), dans `apps/votes/tests/`. **Une règle de vote sans test n'est pas terminée.**
- `test_duplicates.py` : nom déjà votant signalé (casse, accents, espaces), y compris entre en ligne et en séance. Une modification depuis le même navigateur n'est pas un doublon.
- `test_anonymity.py` : un vote anonyme ne crée **aucun** `Ballot`, `Actor`, historique ou trace d'IP, et l'export du vote ne contient aucun nom.
- `test_counting.py` : quorum (abstentions comptées, invalidés exclus) ; seuil simple et 2/3 aux cas limites exacts ; égalité oui = non → rejet ; départage du jugement majoritaire ; choix unique et multiple.
- `test_lifecycle.py` : gel des paramètres, clôture automatique et clôture à la lecture, masquage des résultats avant la clôture, invalidation exclue du décompte, matrice de transitions des propositions.

Autres tests exigés :
- conflit de salle refusé côté serveur (SAL-2) ;
- **rien de non public** sur `/p/*` ni dans les flux publics (PUB-1) ;
- l'historique et la restauration d'un événement (AGE-4) ;
- un participant ne peut pas confirmer (AGE-3) ;
- une vue sans `@public_view` est privée ;
- test de restauration d'une sauvegarde **en CI**.

`tests/acceptance/test_reception.py` reprend les critères de réception du §11.

## Phasage et ordre de travail

Le tableau « Estimation de charge » du §11 fait foi, car le schéma du phasage est perdu dans le CDC. Chaque phase est mise en ligne et utilisée par le collectif avant de lancer la suivante.

1. **Phase 1 — Socle, agenda, idées.**
   - Squelette, réglages, Docker et Caddy, `User` personnalisé + TOTP, droits, `AuditLog`, `Actor`, code d'accès, noindex, limitation de débit.
   - Agenda complet : vues, création rapide, glisser-déposer, duplication, historique, restauration, verrou, conflits, indisponibilités, iCal par agenda, espace et salle.
   - Idées avec créneaux et réactions, vue de programmation (colonnes par salle, « À placer », confirmation par lot).
   - Prévoir des modèles **minimaux** `Room` + `OpeningHours` et `Space` (nom, couleur), dont la phase 1 a besoin. Calendriers externes (ADE) livrés désactivés.
2. **Phase 2 — Propositions et votes.** Propositions, amendements, soutiens, tous les types de vote, sondage de dates (avec transformation en événement), hybride et saisie en séance, anonymat par compteurs, exports CSV et PDF (procès-verbal), RSS.
3. **Phase 3 — Espaces, salles, page publique.** Fils de discussion, documents, comptes rendus, recherche FTS5, fiches salles complètes (photo, mode validation, planning), page publique et actualités, contact et adhésion, sauvegarde et restauration en un clic.
4. **Transversal.** Accessibilité, mode sombre, PWA, test mobile « événement en moins de 30 s » (Playwright en option), guides des membres et de l'administrateur, notes de version.

Postes les plus lourds d'après le §11 : séries récurrentes (abandonnées, AGE-6), jugement majoritaire, anonymat réel.

## Décisions par défaut (à confirmer par le collectif)

Chacune est appliquée tant que le collectif n'a pas tranché. Indique-la en commentaire dans le code avec `# DÉCISION (à confirmer)`.

1. **Licence AGPL-3.0-or-later** par défaut, pour qu'une instance modifiée reste libre. `@event-calendar` étant sous MIT, rien n'y oblige : MIT ou GPL restent possibles.
2. **Abstentions** : comptées pour le quorum, exclues des suffrages exprimés pour le seuil. Une égalité oui = non donne un rejet. Les bulletins invalidés sont exclus des deux calculs.
3. **Vote anonyme** : il n'y a pas de bulletin, seulement des compteurs. **La modification du vote et l'invalidation sont impossibles** (`CheckConstraint` : `allow_change=False`). En séance, on ne saisit que des totaux, avec un avertissement « sans contrôle des doublons ». Le vote anonyme est disponible, mais n'est pas proposé par défaut.
4. **Jugement majoritaire** : 6 mentions (Très bien → À rejeter), médiane inférieure si le nombre de voix est pair, départage par retrait itératif de la mention majoritaire. Une égalité persistante est tranchée par l'habilité, avec un motif journalisé. Si la mention du gagnant est « À rejeter », le vote est rejeté. Le quorum s'applique, le seuil non.
5. **Choix unique** : majorité relative, avec une option « blanc ». **Choix multiple** : nombre maximal de choix paramétrable, résultat sous forme de classement.
6. **Clôture** : en ligne et en hybride, uniquement à la date fixée. En séance, manuelle. Un vote mal paramétré est annulé avec un motif public, puis recréé. Invalidations et saisies en séance sont possibles jusqu'à la clôture seulement.
7. **Doublon de nom** : avertissement avec confirmation, pas blocage (des homonymes existent). Les noms proches (similarité > 0,85) sont signalés à l'admin.
8. **Votants d'un vote nominatif avec `after_close`** : les noms des votants sont visibles en direct, leurs choix restent masqués.
9. **Sondage de dates** : toujours nominatif, sans quorum ni seuil, sans proposition liée.
10. **Statut à la création** : un événement créé directement dans l'agenda est `confirmed` s'il passe les contrôles de salle. Un événement issu d'une idée est `provisional`. Les provisoires peuvent se chevaucher (avertissement) ; le conflit ne bloque qu'à la confirmation.
11. **Case « public » cochée par un participant** : elle vaut demande de publication (`public_requested`). `is_public` n'est posé que par un habilité « agenda » ou « page publique ».
12. **Séries** : abandonnées (décision du porteur du projet, 22/10/2026). La duplication suffit.
13. **Idée et événements** : une idée peut avoir plusieurs événements (`Event.idea` est une clé étrangère, `idea.events`). Elle passe à `done` quand tous ses événements confirmés sont passés, et revient à `preparing` si tous sont annulés. Tout participant change les statuts manuels. `planned` et `done` sont uniquement automatiques.
14. **Retrait d'une proposition** : par un habilité, sur demande de l'auteur, uniquement depuis `discussion`, avec journalisation.
15. **Épingler** relève du droit `manage_spaces`. **Masquer** relève de `moderate`. L'auteur peut éditer son message depuis le même navigateur (mention « modifié »). Le « retirer » est un masquage avec le motif « retiré par l'auteur ».
16. **Le droit `export_data`** n'inclut pas la sauvegarde complète, qui contient les empreintes de mots de passe.
17. **Anonymisation** : elle couvre l'historique, les réactions et les bulletins nominatifs, sans changer les décomptes. Le journal note « anonymisation de N contributions » sans reprendre le nom.
18. **Valeurs de lancement** (§12) :
    - aucun gestionnaire ;
    - code d'accès changé chaque année ;
    - vote nominatif, majorité simple, sans quorum, 7 jours, modification autorisée ;
    - aucune salle préchargée ;
    - ADE désactivé ;
    - page publique limitée à la présentation et au contact ;
    - identification individuelle réévaluée après les 3 premiers votes.
19. **Infrastructure : SQLite + Docker + Caddy** (décision du porteur du projet, 22/10/2026), la pile déjà éprouvée sur BD_ditor, plutôt que celle d'Improliante (PostgreSQL, Nginx, systemd).
20. **HSTS sans « preload »** (`security.W021` réduit au silence) : l'inscription dans les navigateurs engage le domaine pour des mois. À reconsidérer une fois le domaine stable.
21. **Messages de contact gardés un an** (`CONTACT_KEEP_DAYS`), puis effacés : `# DÉCISION (à confirmer)`.
22. **Usage réel** (décision du porteur du projet, 26/10/2026) : le travail est fait par quelques admins principaux ; les autres viennent **consulter** l'emploi du temps, **proposer** (un événement, une idée) et, quand c'est possible, **voter**. Rien n'est retiré : l'espace des membres reste, au cas où les usages évoluent. L'édition directe de l'agenda par les membres (création, modification, glisser-déposer, annulation, duplication, programmation, réservation depuis `/salles/`, « Fixer ce créneau ») dépend du réglage `SiteSettings.members_edit_agenda`, **décoché au lancement** ; décoché, ces actions renvoient vers « Déposer une idée » et restent ouvertes aux habilités « agenda ». Déposer une idée (y compris avec un créneau précis, IDE-2), réagir, annoncer sa présence et répondre aux sondages restent ouverts à tous les membres.
23. **« Qui est là ? »** (même décision) : sert à **coordonner les admins** et à afficher des **permanences publiques**. Tout membre annonce sa présence. Une présence n'est publique que si la personne la marque « permanence » ; la page publique n'affiche alors que le jour, le moment et le lieu, **jamais de nom** (PUB-1).
24. **Votes (phase 2, à préciser)** : piste du porteur du projet, un **code d'accès par vote**. La page du vote serait publique, gérée en interne, et ne fonctionnerait qu'avec le code donné pour ce vote (distinct du code d'accès commun). Variante à étudier au moment de la phase 2 : un code par votant, à usage unique, qui garantirait un vote par personne sans compte.

## Projets de référence (à consulter, pas à imiter)

Le porteur du projet a d'autres projets dans `~/Dev/` et sur GitHub. Ils contiennent des solutions déjà éprouvées et des pièges déjà rencontrés. **Ce ne sont pas des modèles à recopier.**

Règles d'usage :
- **Consulte-les pour une question précise**, pas avant chaque lot. La source de vérité reste le CDC, puis ce fichier.
- **Ne recopie jamais un module entier.** Reprends une idée, un algorithme, un piège documenté, puis réécris-le pour ce projet. Les contextes diffèrent : là-bas des membres avec compte et des envois d'e-mails, ici ni l'un ni l'autre.
- **Improliante n'est pas stabilisé** : son backend a été beaucoup retravaillé et le chantier continue. Avant de t'appuyer sur un fichier, lis sa version sur GitHub (`git fetch` puis `git show origin/main:<chemin>`), regarde les derniers commits qui le touchent et la fiche `pilotage/` concernée. Si le code semble en cours de refonte, ne t'en inspire pas, et signale-le.
- Cite la source en commentaire quand une idée vient de là (`# Inspiré d'Improliante apps/common/debit.py : IP réelle derrière le proxy`).

**Improliante** (`~/Dev/Improliante`, GitHub `Hsbtqemy/Improliante`), Django, même famille de stack :

| Où regarder | Pour quelle question | Prudence |
|---|---|---|
| `apps/gouvernance/services.py` + `tests.py` | Quorum, majorités, règles figées à l'ouverture d'une réunion, décompte à main levée (`Resolution`, `Presence`) | Ne couvre ni le vote en ligne, ni l'anonymat, ni le jugement majoritaire. Modèle de réunion différent du nôtre. |
| `apps/common/moderation.py` | Transitions d'état centralisées, transition invalide = exception | Le cycle (brouillon → proposé → publié) n'est pas le nôtre. Ne reprends que le principe. |
| `apps/common/debit.py` | Limitation de débit, IP réelle derrière le proxy, compteur partagé entre workers | Récent (audit SEC-1), relis la version à jour. |
| `apps/common/pdf.py`, `apps/common/fichiers.py` | WeasyPrint ; fichiers servis après contrôle d'accès | — |
| `apps/coeur/roles.py` | Centraliser les droits plutôt que disperser des `is_staff` | Rôles par groupe, nous par permissions fines : à adapter. |
| `deploiement/` | Sauvegarde avec copie hors serveur, Nginx, systemd | Ses scripts visent PostgreSQL, pas SQLite. |
| `CLAUDE.md`, `pilotage/` | Format des règles non négociables, journal par lot | — |

**BD_ditor** (GitHub `Hsbtqemy/BD_ditor`, pas de clone local), FastAPI + SQLite, déployé en Docker + Caddy sur un VPS :

| Où regarder | Pour quelle question | Prudence |
|---|---|---|
| `deploy/Dockerfile` | Étape `test` qui joue la suite dans l'image livrée | Image lourde (modèles ML) : seul le principe compte. |
| `deploy/deployer.sh`, `deploy/veille-deploiement.sh`, `deploy/systemd/` | Gardes de déploiement, déploiement tiré par un timer, sans clé chez GitHub | Authelia et LDAP n'ont pas d'équivalent ici. |
| `deploy/Caddyfile.derriere-proxy` | Caddy derrière un relais HTTPS existant | — |
| `docs/deploiement-docker.md`, `docs/exploitation.md` | Pannes déjà rencontrées en production | — |

**FoReLLISTS** (`~/Dev/FoReLLISTS`), SvelteKit + Supabase, **stack différente** : rien ne se copie, seule la logique se transpose.

| Où regarder | Pour quelle question |
|---|---|
| `src/lib/calendar/ics-generator.ts` | Échappement iCal, retours chariot Windows, fuseau Europe/Paris |
| `src/lib/calendar/ical-parser.ts` | Lecture d'un flux iCal externe (superposition ADE) |
| `src/lib/calendar/week-layout.ts` | Événements sur plusieurs jours dans la vue mois |
| `src/lib/calendar/duplicate-detection.ts` | Détection d'événements en double |
| Circuit `proposed_by` / `confirmed_by`, table `event_suggestions` | Passage d'une proposition à un événement confirmé |

Le calendrier de FoReLLISTS est fait à la main, sans grille horaire ni glisser-déposer. Il n'aide **pas** pour l'agenda interactif : pour cela, c'est la documentation d'`@event-calendar`.

## Ce qu'il ne faut pas faire

- Charger une ressource externe (CDN, police, script, iframe, analytics).
- Envoyer un e-mail ou configurer un serveur mail. Ajouter un champ e-mail ailleurs que pour le porteur d'un événement (PUB-2).
- Écrire en base depuis une vue ou un template sans passer par `services.py`, ou oublier `audit.log()` sur une action d'un habilité.
- Créer une vue publique sans `@public_view`, ou lire des événements ou propositions publics sans passer par `public()` / `public_decisions()`.
- Supprimer un contenu (message, idée, proposition, événement, bulletin, entrée d'historique ou de journal) : on masque, on annule, on invalide.
- Enregistrer quoi que ce soit d'identifiant pour un vote anonyme, ou permettre de modifier un paramètre de vote après son ouverture.
- Stocker une IP en clair dans une table métier, ou journaliser des IP côté Django.
- Ajouter un champ texte comme auteur au lieu d'une clé étrangère vers `Actor`, ou lire le cookie `pseudo` hors du résolveur.
- Utiliser `|safe`, `mark_safe`, `hx-on`, un script inline, `csrf_exempt` ou du SQL brut non paramétré.
- Ajouter Celery, Redis, PostgreSQL, Node ou un framework JS sans décision explicite du collectif.
- Réintroduire des séries d'événements ou des récurrences (AGE-6). Seules les indisponibilités hebdomadaires de chacun suivent une règle qui se répète.
- Remplacer `@event-calendar` par FullCalendar : la vue en colonnes par salle y est un module payant, ou impose une licence GPL.
- Copier un fichier de FoReLLISTS ou d'Improliante sans l'avoir relu et adapté (voir « Projets de référence »).
- Fusionner une règle de vote sans son test, ou une migration non générée (`makemigrations --check` en pre-commit).
- Commencer une phase suivante avant la validation de la phase en cours.