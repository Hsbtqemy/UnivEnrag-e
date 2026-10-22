# POC — Calendrier alimenté par des propositions extérieures

Oct 21, 2026 · fiche de cadrage

## Objectif

Tester, avant la phase 1 complète, la boucle centrale de l'agenda :

**une personne extérieure propose un événement → un admin le modère → il le place dans le calendrier → il le confirme → l'événement apparaît publiquement.**

Le POC doit répondre à quatre questions :

1. Le formulaire est-il assez court pour qu'une personne extérieure le remplisse jusqu'au bout ?
2. Le placement dans la vue de programmation se comprend-il sans explication, sur ordinateur comme sur téléphone ?
3. La règle « seul un conflit de salle bloque la confirmation » suffit-elle ?
4. Le volume de spam reste-t-il gérable sans captcha externe ?

Si les réponses sont positives, le code sert de base à la phase 1. Il suit donc dès maintenant les conventions du [CLAUDE.md](../CLAUDE.md) (`services.py`, `Actor`, règles AGE et SAL).

## Parcours

### 1. Proposer (public, sans code d'accès)

`/proposer/` est accessible depuis l'agenda public. Le formulaire comporte :

- **Obligatoire** : nom du porteur, e-mail du porteur, titre, description courte, durée souhaitée.
- **Facultatif** :
  - 1 à 3 créneaux possibles, classés par préférence. Chacun est soit une date et une heure précises, soit une période libre (« une après-midi la semaine du 10 novembre ») ;
  - salle souhaitée, public visé, nombre de personnes attendues.

Au-dessus du bouton d'envoi, le formulaire annonce : « Votre nom sera affiché avec l'événement. Votre adresse e-mail ne sera vue que par les organisateurs du collectif. » (CLAUDE.md PUB-2)

**Le site n'utilise jamais l'e-mail** : il n'a pas de serveur mail. L'adresse permet aux admins d'écrire au porteur depuis leur propre messagerie, quand il faut transmettre une information. Après l'envoi, la personne reçoit donc un **lien de suivi** personnel (`/suivi/<jeton>/`), affiché à l'écran, à conserver. Ce lien montre l'état de sa proposition (reçue, acceptée, planifiée avec date et lieu, ou non retenue) et lui permet de la corriger tant qu'elle n'est pas planifiée.

### 2. Modérer (admin)

Les nouvelles propositions arrivent dans une file **« À modérer »**, invisible du public et absente de la vue de programmation. L'admin peut :

- les **accepter** : elles passent dans la vue de programmation ;
- les **refuser**, avec un motif court visible sur le lien de suivi ;
- **refuser en lot** le spam.

Rien n'est supprimé ni purgé (CLAUDE.md MOD-1). L'admin voit le nom et l'e-mail du porteur pour le contacter hors du site si besoin.

### 3. Placer (admin)

`/programmation/` utilise `@event-calendar` en `resourceTimeGridWeek`, avec une colonne par salle et une colonne « Lieu libre ».

- Une proposition acceptée avec un créneau précis est placée en `provisional` (**hachurée**) sur son créneau préféré.
- Ses autres créneaux précis s'affichent en **pointillé**. Un clic l'y déplace.
- Le glisser-déposer et le redimensionnement sont libres pour tout événement déjà placé.
- Le panneau latéral **« À placer »** liste les propositions sans créneau précis (périodes libres). On clique la proposition, puis le créneau voulu.
  - `@event-calendar` ne gère pas le glisser depuis un élément extérieur au calendrier. Le clic, puis clic, est aussi la version accessible au clavier.
- Tout chevauchement s'affiche en avertissement. Seul le conflit de salle bloquera la confirmation.

### 4. Confirmer et publier (admin)

- Bouton **« Confirmer »** par événement, ou par sélection.
- Un conflit de salle (même salle, chevauchement strict, entre événements confirmés) **refuse** la confirmation, avec la liste des événements en conflit (SAL-2).
- La case « Public » est cochée par défaut pour une proposition extérieure, et reste modifiable.
- À la confirmation, la proposition passe à **« Planifiée »** et son lien de suivi affiche la date et le lieu.

### 5. Agenda public

- `/agenda/` : vue liste (par défaut sur téléphone) et vue semaine.
- `/agenda.ics` : abonnement iCal.
- On n'y voit que les événements `confirmed` et `is_public` (PUB-1).
- **Chaque événement affiche son porteur** : « Porté par Nom », y compris dans la description du flux iCal.
- **L'e-mail du porteur n'apparaît jamais** côté public : ni dans la page, ni dans le HTML, ni dans le flux iCal (PUB-2). Un test le vérifie.

## Périmètre

| Dans le POC | Hors du POC (phase 1 ou plus tard) |
|---|---|
| Formulaire public + lien de suivi | Propositions des membres derrière le code d'accès |
| File de modération | Placement provisoire par tous les participants |
| Vue de programmation en colonnes par salle | Récurrences, historique, verrouillage |
| Créneaux alternatifs, panneau « À placer » | Gestionnaires et droits fins, 2FA |
| Confirmation avec conflit de salle bloquant | Plages d'ouverture des salles, validation des réservations |
| Agenda public (liste et semaine) + iCal | Indisponibilités, superposition ADE |
| Salles gérées dans l'admin Django | Votes, espaces, exports CSV/PDF, RSS, PWA |
| Anti-spam local | Docker, sauvegarde automatique |

## Modèle de données

| Modèle | Champs principaux |
|---|---|
| `Actor` | `display_name`, `name_key` (cf. CLAUDE.md, conservé pour la suite) |
| `Room` | `name`, `building`, `capacity`, `color` |
| `Idea` | `owner` (FK `Actor`, le porteur), `owner_email` (`EmailField`, obligatoire), `title`, `description`, `duration_minutes`, `audience`, `expected_count`, `wanted_room` (FK nulle), `status` (`pending`, `accepted`, `refused`, `planned`), `refusal_reason`, `tracking_token` (UUID), `created_at` |
| `IdeaSlot` | `idea` (FK), `rank`, `start`/`end` (nulls si période libre), `period_text` |
| `Event` | `idea` (OneToOne nulle), `owner` (FK `Actor`, le porteur), `owner_email`, `title`, `description`, `start`, `end`, `room` (FK nulle), `place_text`, `status` (`provisional`, `confirmed`, `cancelled`), `is_public`, `revision` |

`owner` et `owner_email` sont recopiés depuis la proposition dès son placement. Un événement créé directement par un admin a aussi un porteur.

Dans le code, une proposition d'événement est une `Idea` (CDC §4, « idée d'événement ») : `Proposal` est réservé aux propositions à voter de la phase 2.

Transitions dans `apps/ideas/services.py`. Toute autre transition lève une exception :

- `pending` → `accepted` ou `refused` ;
- `accepted` → `planned`, à la confirmation de l'événement.

## Anti-spam, sans service externe

Le CDC interdit tout script externe, donc pas de reCAPTCHA ni de hCaptcha.

- **Champ piège** caché : rempli, la soumission est ignorée en silence.
- **Temps minimal** de remplissage (environ 3 s), mesuré avec un horodatage signé dans le formulaire.
- **Limitation de débit** : 5 propositions par heure par adresse IP, avec IP hachée (cf. CLAUDE.md, « Sécurité et RGPD »).
- **Longueurs bornées** : titre 120 caractères, description 3 000 caractères. Liens autorisés, mais au plus 3.
- Modération obligatoire avant toute visibilité : un spam qui passe ne se voit nulle part.

## Décisions à prendre

*Tranché le 21/10/2026* (CLAUDE.md PUB-2) :
- le nom du porteur est affiché publiquement ;
- son e-mail est obligatoire, réservé à l'interne (admins), jamais utilisé par le site et jamais purgé.

Reste à décider :

1. **Qui modère et place** pendant le POC : l'administrateur seul, ou aussi quelques membres ?
   - *Proposition* : 1 ou 2 comptes admin dans l'admin Django. Les droits fins viendront en phase 1.
2. **Salles du POC** : lesquelles le collectif gère-t-il vraiment ? (CDC §12)

## Charge

| Lot | Jours |
|---|---|
| Socle Django, `Actor`, salles dans l'admin, données de démo | 0,5 |
| Formulaire public, anti-spam, lien de suivi | 0,5–1 |
| File de modération | 0,5 |
| Vue de programmation (hachures, pointillés, « À placer », glisser-déposer, conflits) | 1,5–2 |
| Agenda public + iCal | 0,5 |
| Tests (transitions, conflit de salle, rien de non public sur `/agenda/`, aucun e-mail dans les pages et flux publics, anti-spam) | 0,5 |
| **Total** | **≈ 4 à 5 jours** |

S'ajoutent 1 à 2 semaines d'usage réel. Il faut aussi une mise en ligne minimale pour que des personnes extérieures puissent proposer : un petit VPS avec Caddy, sans Docker ni sauvegarde automatique à ce stade.
