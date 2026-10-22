# CLAUDE.md — Plateforme du collectif (UnivEnrag-e)

## Présentation

Ce dépôt contient un site web léger, autonome et hébergé hors de l'université, pour un collectif auto-organisé d'environ 50 personnes (il doit pouvoir passer à 300). Il sert à tenir un agenda commun, recueillir des idées sans vote, déposer des propositions et les voter, ouvrir des espaces de discussion, gérer des salles, publier une page publique et exporter les données.

Les participants n'ont pas de compte : ils entrent un **code d'accès commun** puis agissent sous un **nom ou pseudo**. Seuls l'administrateur principal et les gestionnaires se connectent.

**Source de vérité** : `docs/Cahier des charges — Plateforme du collectif.md` (le « CDC », cité sous la forme §N). Pour un détail fonctionnel, relis le CDC. Si ce fichier contredit le CDC, signale la contradiction au lieu de trancher en silence.

## État du projet

- **Le POC est codé** (22/10/2026) : agenda alimenté par des propositions extérieures, décrit dans `docs/poc-calendrier-propositions.md`. Voir le `README.md` pour le démarrer.
- **Phase 1 en cours**, par lots testés et commités un à un : A socle · B agenda des membres · C salles et espaces · D indisponibilités · E idées des membres · F mise en ligne. **Pas de séries d'événements** (voir la décision 12).
  - **Lot A fait** : modèle `accounts.User` (7 droits, `require_capability`, `CapabilityAdminMixin`), double authentification TOTP + codes de secours (`accounts/two_factor.py`, obligatoire hors `DJANGO_ENV=dev`, forcée avec `DJANGO_ADMIN_2FA=1`), code d'accès commun (`core/access.py`, `@public_view`), nom mémorisé et `request.actor` (`actors/resolvers.py`), journal `audit.log()` en ajout seul, page `/gestion/` selon les droits.
  - **Lot B fait** : agenda des membres `/agenda/` (semaine, mois, liste par défaut sur téléphone, filtre par salle), création en un formulaire court (`/agenda/nouveau/`, pré-rempli depuis le créneau cliqué ou par duplication `?depuis=<id>`), modification, annulation (reste visible, barrée), glisser-déposer sous le nom retenu, avertissement de salle en direct (`/agenda/verifier/`), historique `EventChange` avec restauration, verrou, demandes de publication (`/gestion/publication/`).
  - **Lot C fait** : salles avec plages d'ouverture (`OpeningHours`, une salle sans plage n'a pas de restriction) et mode « libre » ou « soumise à validation » (`Event.room_status`, file `/gestion/salles/`, un refus retire la salle mais garde l'événement) ; dérogation (salle occupée ou fermée) par le seul droit « salles », case `override`, journalisée `rooms.derogation` ; page `/salles/` ; app `spaces` minimale (nom, couleur, archivage), couleur et filtre par espace dans l'agenda ; flux iCal internes par jeton `/flux/<feeds_token>/{agenda.ics, espace/<slug>.ics, salle/<id>.ics}` et page `/agenda/abonnements/` (le flux public n'inclut jamais le lien visio).
  - **Historique : modèle maison `agenda.EventChange`** (et non django-simple-history) : chaque entrée référence un `Actor`, garde `changes` ({champ: [avant, après]}) et un `snapshot` complet pour restaurer. Toute écriture sur un événement passe par `agenda/services.py`, qui l'enregistre.
  - URL : public sous `/p/` (`/p/agenda/`, `/p/proposer/`, `/p/suivi/<jeton>/`, `/p/agenda.ics`), interne `/accueil/`, `/nom/`, gestion `/gestion/` (admin Django sous `/gestion/admin/`).
  - **Choix restés simples, à revoir si besoin** : ni htmx, ni django-csp (la CSP est posée par `core/middleware.py`), ni WhiteNoise, ni django-environ (réglages lus dans `os.environ`), ni pre-commit. Une seule salle par événement.
  - Le reste de ce fichier (arborescence, commandes cron, sauvegarde…) décrit encore des **cibles à créer**.
- Commence par la **phase 1** (voir « Phasage »). Ne code pas une phase suivante avant que le collectif ait validé la phase en cours. Seule exception : les modèles minimaux dont la phase en cours a besoin.
- Tiens ce fichier à jour : quand une cible devient réelle, quand une décision par défaut est confirmée ou changée, quand une commande change.

## Stack

| Brique | Choix |
|---|---|
| Langage, framework | Python 3.12, **Django 5.2 LTS** |
| Base | **SQLite en WAL** : `transaction_mode="IMMEDIATE"`, `busy_timeout=5000`, `foreign_keys=ON`. Le seul code propre à SQLite (FTS5) est isolé dans `apps/core/search.py`, pour pouvoir passer à PostgreSQL au-delà de 300 personnes |
| Interactivité | Rendu serveur + **htmx 2.0** + `django-htmx`. Pas de SPA, pas de chaîne Node |
| Agenda | **`@event-calendar` 5.3** (vkurko/calendar, **MIT**), bundle autonome `@event-calendar/build` (`event-calendar.min.js` + `.min.css`) copié dans `static/vendor/`, jamais chargé depuis un CDN. Il fournit les vues semaine, mois et liste, **les colonnes par salle** (`resourceTimeGridDay` / `resourceTimeGridWeek`) et le glisser-déposer (plugin interaction inclus). Son API est proche de FullCalendar, sans module payant |
| CSS | Pico CSS 2 copiée dans le dépôt + `static/css/app.css` (variables, mode sombre) |
| Formats | `icalendar` 6 ; `django.contrib.syndication` (RSS) ; CSV natif (UTF-8 avec BOM, séparateur `;`) ; **WeasyPrint** (PDF, polices dans le dépôt) |
| Markdown | `markdown` + `nh3`. Balises autorisées : p, br, strong, em, ul, ol, li, a. Les liens reçoivent `rel="nofollow noopener"` |
| Historique | Modèle maison `agenda.EventChange` (avant/après par champ + instantané pour restaurer), dont l'auteur est un `Actor` |
| Administrateurs | `argon2-cffi`, `django-otp` (TOTP + codes de secours), `segno` (QR code en SVG) |
| Sécurité HTTP | `django-csp` 4 : `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'` |
| Statique, configuration | WhiteNoise ; `django-environ` (`.env`), un seul `config/settings.py` piloté par `DJANGO_ENV=dev|prod|test` |
| Production | Docker multi-étapes (utilisateur non root) + `compose.yaml` : `app` (gunicorn, journal d'accès désactivé), `caddy` (HTTPS automatique), `cron` (supercronic), volume `/data` (base, médias, sauvegardes). **Ni Celery ni Redis** |
| Qualité | `uv` (`pyproject.toml` + `uv.lock`), `ruff` (E,F,I,B,UP,DJ,S,SIM, ligne de 100), `pytest`, `pytest-django`, `factory-boy`, `time-machine`, `pre-commit` |

Les bibliothèques JS et CSS tierces vont dans `static/vendor/<lib>-<version>/`. Elles sont téléchargées par `scripts/fetch_vendor.sh` (versions épinglées, sha256 vérifiés) et recensées dans `static/vendor/VERSIONS.md`.

## Contraintes dures (non négociables)

- **Aucune ressource externe** : ni CDN, ni Google Fonts, ni script, police ou CSS tiers chargé à distance. La CSP le garantit, ne l'assouplis jamais pour un domaine extérieur. Le navigateur ne contacte jamais un service tiers : même les calendriers externes (ADE) sont récupérés par le serveur. (§9)
- **Aucun envoi d'e-mail** : pas de serveur mail, pas de notification, pas de lien envoyé. L'information passe par le site, l'iCal et le RSS. (§7, §9)
- **Un seul champ e-mail** : celui du porteur d'un événement proposé (PUB-2). Il sert à le contacter hors du site, et à rien d'autre. Ailleurs, pas de champ e-mail.
- **Aucun traceur** ni outil d'analyse. Les seules données personnelles collectées sont le nom ou pseudo, et l'e-mail du porteur d'un événement. (§9, modifié par PUB-2)
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
deploy/            Caddyfile crontab entrypoint.sh
tests/             conftest.py factories.py acceptance/test_reception.py
```

Chaque app suit la même structure : `apps.py models.py services.py views.py urls.py forms.py admin.py templates/<app>/ tests/`. Le nom est de la forme `name="apps.agenda"`, `label="agenda"`.

Les dépendances vont dans un seul sens : `core ← actors ← audit ← accounts ← {rooms, spaces, discussions} ← agenda ← ideas ← proposals ← votes ← {exports, public}`. (`audit` ne connaît les comptes que par `settings.AUTH_USER_MODEL` ; `accounts` l'appelle.) Seule entorse admise : la vue de programmation (`agenda/views.py`) lit les idées à placer, et `agenda.services.confirm` importe `ideas.services` à l'intérieur de la fonction. Entre modèles, les clés étrangères s'écrivent sous forme de chaîne (`"agenda.Event"`).

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

- `AccessCodeMiddleware` est **fermé par défaut** : une vue n'est publique que si elle porte `@public_view`. Sont publiques : `/`, `/p/*`, `/acces/`, `/sante/`, `/static/*`, `/gestion/connexion/`, et les flux à jeton.
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
| `make check-deploy` | `manage.py check --deploy` avec des réglages de production factices |

Cibles à créer : `pre-commit`, `scripts/fetch_vendor.sh`, Docker / `bootstrap`, `backup` / `restore`, et la démo des phases suivantes (votes, discussions).

Tâches cron (`deploy/crontab`, supercronic) :

| Fréquence | Commande |
|---|---|
| Chaque minute | `close_due_votes` |
| Toutes les 30 min | `refresh_external_calendars` |
| Chaque nuit | `ideas_mark_done`, `purge_ip_data`, `clearsessions`, `purge_contact_messages` |
| 3 h | `backup` puis `restic` vers un stockage hors serveur |

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
- ACC-3. Les comptes administrateurs exigent un mot de passe robuste **et le TOTP** : sans appareil confirmé, l'utilisateur est redirigé vers `/gestion/2fa/`. L'admin Django passe par `OTPAdminSite`. (§2, §9)
- ACC-4. Sont réservés au superuser : changer le code d'accès, créer ou retirer des gestionnaires et leurs droits, consulter le journal d'activité, télécharger une sauvegarde. Un retrait invalide immédiatement les sessions du gestionnaire. (§2, §8)
- ACC-5. Un gestionnaire n'a que les droits cochés. Toute autre action lui est refusée (`@require_capability`). (§8)
- LOG-1. Toute action d'un habilité est tracée dans `AuditLog` (qui, quoi, quand, objet). Ce journal accepte uniquement des ajouts : ni modification ni suppression depuis l'interface. (§8)

**Agenda et salles**
- AGE-1. Un événement a trois statuts, `provisional`, `confirmed` et `cancelled`. Un événement annulé reste visible et barré. **Un événement n'est jamais supprimé.** (§3)
- AGE-2. Seuls le titre, le début et la fin sont obligatoires, avec fin > début. (§3)
- AGE-3. Tout participant crée, modifie, déplace, duplique ou annule un événement non verrouillé, sous son nom. **Seul un habilité « agenda » peut passer un événement de `provisional` à `confirmed`**, à l'unité ou par lot. (§3)
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
- PUB-1. **Rien n'est public par défaut.** Seuls les événements `confirmed` **et** `is_public`, et les propositions adoptées marquées `is_public_decision`, sortent, sans aucun nom de votant. Les intervenants ne sont affichés que si `speakers_public`. (§7)
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
- La page « Données personnelles » (`/p/donnees-personnelles/`) indique la finalité, les responsables, les durées et les droits. L'anonymisation se fait sur demande, depuis l'écran de modération.
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
13. **Idée et événements** : une idée peut avoir plusieurs événements (`Event.origin_idea` est une clé étrangère). Elle passe à `done` quand tous ses événements confirmés sont passés, et revient à `preparing` si tous sont annulés. Tout participant change les statuts manuels. `planned` et `done` sont uniquement automatiques.
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
19. **Infrastructure (ouvert, ne pas trancher seul).** On s'en tient à SQLite + Docker comme le recommande le CDC. L'alternative serait de reprendre l'infrastructure d'Improliante (PostgreSQL, VPS, Nginx, systemd, déploiement par webhook), déjà éprouvée. À arbitrer avec le porteur du projet avant d'écrire la configuration de production.

## Projets de référence (à consulter, pas à imiter)

Le porteur du projet a deux autres projets dans `~/Dev/`. Ils contiennent des solutions déjà éprouvées et des pièges déjà rencontrés. **Ce ne sont pas des modèles à recopier.**

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