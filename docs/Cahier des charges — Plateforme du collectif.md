# Cahier des charges — Plateforme du collectif

Oct 21, 2026 · @Hugo

## 1. Contexte et objectifs

Le collectif a besoin d'un site web léger, indépendant de l'université, pour décider, s'organiser et se rendre visible. Le collectif est auto-organisé et regroupe environ 50 personnes : enseignants-chercheurs, personnels administratifs, techniques et ingénieurs.

Le site doit permettre de :

1. Faire remonter des idées, envies, projets et disponibilités, sans obligation de vote, et les caler ensuite dans l'agenda ; voter sur des propositions quand une décision est nécessaire.
2. Tenir un agenda commun, facilement modifiable par les membres.
3. Organiser des espaces de discussion par groupe de travail.
4. Gérer des emplois du temps et des réservations de salles.
5. Rendre visibles certains contenus à un public extérieur.
6. Exporter les données (votes, décisions, agenda).

Principes directeurs :

- **Pas de compte à créer** : on participe avec son nom ou un pseudo ; seuls l'administrateur et les gestionnaires se connectent ; un code d'accès commun protège la partie interne.
- **Interface claire** : utilisable sans formation par tous les profils.
- **Indépendance** : hébergement, nom de domaine et données hors de l'infrastructure universitaire.
- **Sobriété** : peu de fonctionnalités, mais qui marchent bien.

## 2. Utilisateurs, rôles et identification

Seuls l'administrateur et les gestionnaires s'identifient ; les autres participants agissent sous leur nom ou un pseudo, sans compte, sans mot de passe et sans e-mail. La partie interne est protégée par un code d'accès commun au collectif. Une identification individuelle pourra être ajoutée plus tard si le besoin apparaît.

### Rôles

| Rôle | Qui | Peut |
| --- | --- | --- |
| Administrateur principal | Une personne (le porteur du projet) | Tout, y compris créer et retirer les gestionnaires, choisir leurs droits, changer le code d'accès, accéder au serveur et aux sauvegardes |
| Gestionnaire (optionnel) | Personnes désignées par l'administrateur | Les droits que l'administrateur leur attribue parmi : votes, agenda, salles, espaces, modération, page publique, exports |
| Participant | Toute personne connaissant le code d'accès | Proposer, commenter, voter, créer et modifier des événements, réserver une salle |
| Public | Visiteur extérieur | Consulter la page publique |

### Fonctionnement

- À sa première visite, le participant saisit le code d'accès commun ; le navigateur le mémorise.
- À sa première action (vote, message, événement), il saisit son nom ou un pseudo, mémorisé lui aussi et modifiable à tout moment.
- Aucune autre donnée n'est demandée.
- L'administrateur et les gestionnaires se connectent avec un identifiant et un mot de passe ; double authentification recommandée.

### Code d'accès commun

- Un mot de passe unique pour tout le collectif, transmis en réunion ou par les canaux habituels du collectif. Ce n'est pas une identification individuelle.
- Changeable à tout moment par l'administrateur ; les navigateurs devront alors saisir le nouveau code.
- La partie interne n'est pas indexée par les moteurs de recherche.
- La page publique reste accessible sans code.

### Limites assumées

- Sans identification, rien n'empêche techniquement de voter deux fois sous deux noms. Le système repose sur la confiance, adaptée à un collectif d'environ 50 personnes qui se connaissent.
- Contre-mesures : liste des votants visible, noms en double signalés, invalidation par un admin avec motif affiché.
- Le code est structuré pour qu'une identification individuelle puisse être ajoutée sans refonte.

## 3. Agenda

L'agenda est le module central : tout participant doit pouvoir y créer ou déplacer un événement en moins de 30 secondes.

### Affichage

- Vues **semaine**, **mois** et **liste** (prochains événements). Vue liste par défaut sur téléphone.
- Filtres par espace et par salle ; couleur par espace.
- Superposition optionnelle de calendriers externes en lecture seule (flux iCal, par exemple un emploi du temps ADE), affichés en grisé.

### Création et modification

- **Clic sur un créneau** → formulaire court : titre, début, fin. Champs optionnels : espace, salle, lieu libre, description, lien visio, case « public ».
- **Glisser-déposer** pour déplacer, tirer le bord pour changer la durée.
- **Récurrence** : chaque jour, chaque semaine, toutes les 2 semaines, chaque mois ; avec date de fin. Modification « cet événement » ou « toute la série ».
- **Duplication** d'un événement en un clic.
- Statut : confirmé, provisoire, annulé (un événement annulé reste visible, barré).

### Vue de programmation

Une vue de l'agenda sert à caler la masse d'événements proposés (conférences, séminaires, rencontres) avant de les rendre définitifs et publics.

- Affichage possible **en colonnes par salle** pour une journée ou une semaine, pour voir d'un coup d'œil les événements en parallèle et les salles encore libres.

* Les idées placées provisoirement apparaissent **hachurées**, à côté des événements confirmés.
* Chaque événement provisoire affiche ses autres créneaux possibles en pointillé ; on le déplace d'un clic vers l'un d'eux, ou librement par glisser-déposer.
* **Signalement des chevauchements** : plusieurs événements au même moment sont normaux dès qu'ils sont dans des salles différentes. Seul un conflit de salle (même salle, même créneau) bloque la confirmation. Les autres cas sont de simples avertissements, désactivables : mêmes intervenants à la même heure, ou même public visé en parallèle.
* Colonne **« À placer »** : les idées sans créneau, à faire glisser sur le calendrier.
* Filtres par type, espace, public visé et statut (provisoire ou confirmé).
* Bouton **« Confirmer »** par événement ou par sélection ; seuls les événements confirmés et cochés « public » sont visibles de l'extérieur.
* Le placement provisoire est modifiable par tous les participants ; la confirmation est réservée à l'administrateur et aux gestionnaires ayant le droit « agenda ».

### Droits

- Tout participant peut créer, modifier ou annuler un événement ; son nom est demandé à chaque action.
- **Historique** de chaque événement : qui (nom saisi), quand, et la valeur avant/après.
- Un admin peut restaurer une version précédente ou **verrouiller** un événement pour empêcher toute modification.

### Salles dans l'agenda

- Si une salle choisie est déjà occupée, un avertissement s'affiche immédiatement, avant l'enregistrement.

### Abonnement et partage

- Flux **iCal** par agenda global, par espace et par salle, pour s'abonner depuis Outlook, Thunderbird, Google Agenda ou un téléphone.
- Le flux des événements publics alimente la page publique.

### Emplois du temps

- Chacun peut indiquer, sous son nom, ses **indisponibilités récurrentes** (cours, permanences), visibles sous forme de créneaux grisés sans détail.
- **Sondage de dates** intégré : proposer plusieurs créneaux, chacun coche ses disponibilités, le meilleur créneau se transforme en événement en un clic.

## 4. Idées, propositions et votes

Tout le monde peut faire remonter une contribution ; seule une partie d'entre elles passe par un vote.

### Trois types de contributions

| Type | Exemples | Vote | Aboutit à |
| --- | --- | --- | --- |
| Idée d'événement | Un séminaire, un repas, une assemblée, une projection | Non | Un événement dans l'agenda |
| Projet ou envie | Monter un groupe de travail, écrire un texte, une action à mener | Non | Un espace, des événements, ou une proposition au vote |
| Proposition à voter | Une position du collectif, une dépense, une règle | Oui | Une décision adoptée ou rejetée |

Une idée ou un projet peut être transformé en proposition à voter à tout moment, sans ressaisie.

### Idées et projets (sans vote)

Une idée se dépose avec un formulaire court ; seuls le nom, le titre et le type sont obligatoires, le reste peut être complété plus tard par l'auteur ou les autres participants.

**Contenu**

- Titre, type (événement, projet ou envie), espace concerné.
- Description : de quoi il s'agit, objectifs, déroulé envisagé.
- Format : présentiel, visio ou hybride ; durée souhaitée (1 h, demi-journée, journée…).
- Besoins : salle, capacité, matériel, budget éventuel.
- Liens et pièces jointes.

**Personnes concernées**

- Public visé : tout le collectif, un groupe de travail, enseignants-chercheurs, personnels BIATSS, étudiants, extérieurs…
- Nombre de participants attendu.
- Organisateurs et intervenants pressentis (noms libres).
- Réactions en un clic, sous son nom : **« Je participe »**, **« Je peux aider »**, **« Intéressé·e »**, avec la liste visible des personnes pour chaque réaction.

**Créneaux envisagés**

- Le porteur indique un ou plusieurs **créneaux possibles** : une date et un horaire précis, ou une période plus large (« une après-midi la semaine du 10 novembre »), avec un ordre de préférence.
- Il peut préciser des **contraintes** : jours impossibles, date limite, durée, salle souhaitée.
- Aucune réponse n'est demandée aux autres participants : ces créneaux servent à placer l'événement dans le calendrier collectif, pas à sonder des disponibilités.
- Dès qu'un créneau est indiqué, l'idée apparaît dans la **vue de programmation** de l'agenda (voir section 3).

**Suivi**

- Commentaires pour préciser, compléter, proposer un lieu ou un format.
- Statuts : *Nouvelle*, *En préparation*, *Planifiée*, *Réalisée*, *Abandonnée*.
- Vue **tableau** des idées, triable par nombre d'intéressés et par date, et filtrable par type, espace, public visé et statut.

### De l'idée à l'agenda

1. L'idée est déposée avec ses créneaux envisagés ; elle est placée **provisoirement** dans la vue de programmation, sur son créneau préféré.
2. L'administrateur ou un gestionnaire voit toutes les idées placées ensemble, repère les chevauchements et déplace un événement vers un autre de ses créneaux, ou ailleurs, par glisser-déposer.
3. Quand le créneau est arrêté, il **confirme** : l'événement passe dans l'agenda définitif, pré-rempli (titre, description, intervenants, salle).
4. S'il est coché « public », il apparaît sur la page publique et dans le flux iCal public.
5. L'idée passe au statut *Planifiée* et renvoie vers l'événement ; après la date, elle passe automatiquement à *Réalisée*.

### Dépôt d'une proposition à voter

- Tout participant peut déposer une proposition : nom, titre, texte, espace concerné, pièces jointes éventuelles.
- Les autres participants peuvent la **soutenir** (avec leur nom) et la **commenter**.
- Des amendements peuvent être apportés pendant la discussion ; les versions successives sont conservées avec le nom de leur auteur.

### Statuts

| Statut | Qui le déclenche | Ce qui se passe |
| --- | --- | --- |
| En discussion | Dépôt | Commentaires et soutiens ouverts, amendements possibles |
| Au vote | Admin | Texte figé, vote ouvert jusqu'à la date de clôture |
| Adoptée / Rejetée | Automatique à la clôture | Résultat publié, archivé |
| Mise en œuvre | Admin | Suivi : responsable, échéance, état d'avancement |
| Retirée | Admin, à la demande de l'auteur | Archivée sans vote |

### Types de vote

- **Oui / Non / Abstention** (par défaut).
- **Choix unique** ou **choix multiple** entre options.
- **Jugement majoritaire** (chaque option notée de « Très bien » à « À rejeter ») pour les choix à plusieurs options.
- **Sondage de dates** (voir Agenda).

### Paramètres réglables pour chaque vote

| Paramètre | Options |
| --- | --- |
| Secret | Nominatif (par défaut : chacun voit qui a voté quoi) / anonyme (aucun nom enregistré, donc aucun contrôle des doublons) |
| Résultats visibles | En direct / seulement après la clôture |
| Durée | Date et heure de clôture |
| Quorum | Aucun / nombre minimal de votants |
| Seuil | Majorité simple / majorité qualifiée (par ex. 2/3) |
| Modification du vote | Autorisée depuis le même navigateur jusqu'à la clôture / non |

### Garanties

- Un vote par nom : un nom déjà présent dans la liste des votants est signalé avant validation.
- **Liste des votants** visible pour les votes nominatifs, ce qui permet au collectif de repérer un abus.
- Un admin peut invalider un bulletin, avec motif affiché publiquement dans le vote.
- Le navigateur retient qu'il a déjà voté et l'indique ; ce n'est pas une garantie, seulement une aide.
- Le paramétrage est **affiché avant de voter** et ne peut plus changer une fois le vote ouvert.

### Votes en assemblée et en ligne (vote hybride)

Un même vote peut réunir des participants présents en réunion et d'autres en ligne, avec un seul résultat.

- À l'ouverture, l'administrateur ou un gestionnaire choisit le mode : **en ligne**, **en séance** ou **hybride**.
- **En séance** : le gestionnaire saisit les résultats du vote à main levée (nombre de oui, non, abstentions), ou la liste nominative des présents et de leur vote pour un vote nominatif.
- **Hybride** : le vote en ligne reste ouvert jusqu'à la clôture ; les voix de la séance sont ajoutées par le gestionnaire. Le décompte affiche séparément voix en ligne, voix en séance et total.
- Un nom saisi en séance qui a aussi voté en ligne est signalé ; le gestionnaire choisit lequel retenir.
- La saisie en séance est horodatée et attribuée au gestionnaire qui l'a faite ; elle figure dans le procès-verbal exporté.
- Option de **saisie depuis un téléphone** pendant la réunion, avec un écran simplifié de comptage.

## 5. Espaces de discussion

Un espace regroupe tout ce qui concerne un groupe de travail : discussions, propositions, événements et documents.

- Création par un admin : nom, description courte, couleur.
- Tous les espaces sont ouverts à tous les participants.
- Page d'un espace en 4 onglets : **Fil**, **Idées et propositions**, **Agenda**, **Documents**.
- **Fil de discussion** organisé en sujets ; réponses sur un niveau ; mise en forme simple (gras, listes, liens) ; nom saisi à chaque message.
- Messages épinglables par un admin.
- **Documents** : dépôt de fichiers (PDF, bureautique, images ; 20 Mo maximum par fichier) et de liens.
- **Comptes rendus** : modèle de compte rendu de réunion lié à un événement de l'agenda.
- Repère « nouveau » sur les messages publiés depuis la dernière visite (mémorisée par le navigateur).
- Recherche plein texte dans les messages, propositions et documents de l'espace.
- Espace archivable quand le groupe de travail a terminé (lecture seule).

## 6. Salles

Le site gère les salles dont le collectif dispose directement ; les salles de l'université réservées par ailleurs sont simplement mentionnées comme lieu.

- Fiche salle (gérée par un admin) : nom, bâtiment, capacité, équipements (vidéoprojecteur, visio, accessibilité PMR), consignes d'accès, photo.
- **Planning par salle** : vue semaine montrant les créneaux libres et occupés.
- **Réservation** = un événement de l'agenda rattaché à une salle ; pas de double saisie.
- **Détection des conflits** : impossible de réserver un créneau déjà pris, sauf dérogation par un admin.
- Option par salle : **réservation libre** ou **soumise à validation** d'un admin.
- Plages d'ouverture par salle (par ex. lundi–vendredi 8 h–20 h) ; réservation impossible en dehors.
- Champ **lieu libre** pour les réunions hors salles gérées (« Amphi B, réservé via la scolarité »).
- Flux iCal par salle.

## 7. Page publique, notifications et exports

### Page publique

Par défaut, rien n'est public : chaque contenu est rendu visible explicitement, élément par élément.

- Présentation du collectif (texte libre modifiable par les admins) et contact.
- **Agenda public** : événements cochés « public », avec flux iCal.
- **Décisions publiques** : propositions adoptées que les admins ont choisi de publier, avec date et résultat (sans noms des votants).
- **Actualités** : courts articles rédigés par les admins.
- Formulaire de contact et, si activé, de demande d'adhésion.
- Aucun nom de membre affiché publiquement sans son accord.

### Se tenir informé (sans e-mail)

Le site n'envoie aucun e-mail ; l'information passe par le site lui-même et par des flux auxquels chacun peut s'abonner.

| Moyen | Contenu |
| --- | --- |
| Bandeau d'accueil | Votes en cours et date de clôture, avec « déjà voté depuis ce navigateur » |
| Repère « nouveau » | Propositions, messages et événements publiés depuis la dernière visite |
| Flux iCal | Événements, mis à jour automatiquement dans l'agenda personnel de chacun |
| Flux RSS | Nouvelles propositions, votes ouverts et résultats, par espace ou global |

### Exports

| Contenu | Formats |
| --- | --- |
| Résultats d'un vote | CSV, PDF (procès-verbal avec paramètres, dates, résultat ; nominatif ou non selon le vote) |
| Liste des propositions et statuts | CSV |
| Agenda, espace, salle | iCal (abonnement), CSV |
| Réservations de salles | CSV |
| Discussions d'un espace | PDF ou Markdown |
| Sauvegarde complète | Archive (base de données + fichiers), en un clic, pour changer d'hébergeur |

## 8. Administration

L'administration se fait dans une interface dédiée, accessible aux seuls administrateurs.

- **Administrateur principal** : une seule personne, en surplomb ; seule à pouvoir créer ou retirer des gestionnaires, définir leurs droits, changer le code d'accès et accéder au serveur.
- **Gestionnaires** : comptes créés par l'administrateur, avec des droits choisis parmi les domaines ci-dessous ; retrait immédiat possible.
- **Espaces** : création, archivage.
- **Salles** : fiches, plages d'ouverture, mode de réservation, validation des demandes.
- **Votes** : ouverture, clôture, choix du mode (en ligne, en séance, hybride), saisie des voix en séance, correction d'un vote mal paramétré avant ouverture uniquement, invalidation de bulletins en double avec motif affiché.
- **Agenda** : restauration d'une version précédente d'un événement, verrouillage.
- **Modération** : masquer un message ou une proposition (avec motif visible), jamais de suppression silencieuse ; blocage temporaire d'une adresse IP en cas d'abus.
- **Page publique** : textes, actualités, choix de ce qui est publié.
- **Réglages** : nom du collectif, logo, couleur principale.
- **Journal d'activité** : toutes les actions de l'administrateur et des gestionnaires sont tracées (qui, quoi, quand), consultables par l'administrateur.

## 9. Exigences non fonctionnelles

### Interface

- Utilisable sans formation : toute action courante (voter, créer un événement, poster un message) en 3 clics maximum depuis l'accueil.
- **Accueil** : prochains événements, votes en cours avec mention « vous n'avez pas encore voté », dernières propositions et messages publiés depuis la dernière visite.
- Adaptée au téléphone (responsive) ; installable comme application web.
- Accessibilité : niveau RGAA / WCAG 2.1 AA visé (contrastes, navigation au clavier, lecteurs d'écran).
- Interface en français ; textes simples, sans jargon technique.
- Mode sombre optionnel.

### Données personnelles (RGPD)

- Seule donnée personnelle collectée : le nom ou pseudo saisi par le participant. Aucune adresse e-mail.
- Les adresses IP ne sont conservées que dans les journaux techniques, 30 jours maximum, pour la lutte contre les abus.
- Page « Données personnelles » : finalité, responsables, durée de conservation, droits.
- Sur demande à un admin, les contributions d'une personne sont anonymisées (« Anonyme »).
- Aucun traceur publicitaire ni outil d'analyse tiers ; pas de police ou script chargé depuis un service externe.

### Sécurité

- HTTPS obligatoire.
- Comptes administrateurs protégés par mot de passe robuste et double authentification.
- Limitation du nombre d'actions par adresse IP (votes, messages, tentatives de code d'accès).
- Protection contre les attaques web courantes (CSRF, XSS, injections), fournie par le framework.
- **Sauvegarde automatique quotidienne**, conservée 30 jours, dont une copie hors du serveur.

### Hébergement et indépendance

- Hébergement hors de l'université : petit serveur privé loué au nom du collectif.
- Nom de domaine propre au collectif, éventuellement.
- Pas d'envoi de mails.
- Code source sous licence libre, déposé dans un dépôt accessible au collectif, pour qu'un autre développeur puisse reprendre le projet.

### Performance et volumétrie

- Dimensionné pour environ 50 membres actifs, extensible à 300 sans changement d'architecture.
- Pages affichées en moins d'une seconde dans des conditions normales.

## 10. Choix techniques

Les choix ci-dessous sont des recommandations : ils privilégient des outils libres, répandus et faciles à reprendre. Un prestataire peut en proposer d'autres en le justifiant.

| Brique | Recommandation | Raison |
| --- | --- | --- |
| Framework | Django (Python) | Interface d'administration et authentification des admins intégrées, sécurité par défaut |
| Base de données | SQLite, ou PostgreSQL si plus de 300 participants | Un seul fichier, sauvegarde triviale ; suffisant pour la volumétrie |
| Interface | Pages rendues côté serveur + htmx pour l'interactivité | Peu de JavaScript, maintenance simple |
| Agenda | FullCalendar | Bibliothèque de référence : glisser-déposer, récurrences, vues multiples |
| Flux iCal et RSS | Bibliothèque `icalendar` et flux Django natifs | Formats standard, lisibles par tous les agendas et lecteurs |
| Exports | CSV natif, PDF via WeasyPrint | Procès-verbaux mis en page |
| Déploiement | Conteneur Docker + docker-compose | Installation et migration en quelques commandes |

Livrables techniques attendus : code source commenté, fichier README d'installation, jeu de données de démonstration, tests automatisés des règles de vote (signalement des doublons, anonymat, quorum, seuil).

## 11. Phasage, livrables et critères de réception

Le projet se construit en trois phases, en commençant par l'agenda : c'est l'outil utilisé chaque jour, donc celui qui fait adopter le site.

&#91;embedded content: phasage · 3 phases, 3 validations\]

Chaque phase est mise en ligne et utilisée par le collectif avant de démarrer la suivante.

### Estimation de charge

Le développement sera assisté par IA : environ 30 à 40 jours de travail effectif, soit 3 mois de bout en bout à temps plein en incluant les périodes de test par le collectif.

| Phase | Contenu principal | Développement assisté par IA |
| --- | --- | --- |
| 1 — Socle, agenda et idées | Installation, code d'accès, admin et gestionnaires, agenda complet, idées sans vote avec créneaux envisagés, vue de programmation et confirmation | 10 à 14 jours |
| 2 — Propositions et votes | Propositions et amendements, types de vote, vote hybride, anonymat, exports CSV/PDF, RSS | 7 à 10 jours |
| 3 — Espaces, salles, page publique | Fils de discussion, documents, comptes rendus, recherche, salles, page publique, sauvegarde | 6 à 9 jours |
| Transversal | Interface et accessibilité, tests, corrections après retours, documentation, mise en production | 7 à 9 jours |

L'IA accélère surtout l'écriture du code ; les tests avec les participants, les corrections et la vérification des règles de vote se compressent beaucoup moins. Les postes les plus lourds sont les événements récurrents (modification d'une occurrence ou de la série), le jugement majoritaire et l'anonymat réel des votes ; ils peuvent être reportés à une version ultérieure pour réduire la charge d'environ un quart.

### Livrables à chaque phase

- Site en ligne sur l'hébergement du collectif.
- Code source à jour dans le dépôt, avec notes de version.
- Guide utilisateur d'une page (membres) et guide administrateur.

### Critères de réception finale

- [ ] Un participant vote, poste un message et crée un événement sans aide, en saisissant seulement son nom.
- [ ] Un événement est créé en moins de 30 secondes depuis un téléphone.
- [ ] Un nom déjà présent parmi les votants est signalé ; un vote anonyme n'enregistre aucun nom.
- [ ] Toute modification d'événement apparaît dans l'historique et peut être annulée par un admin.
- [ ] Une réservation en conflit est refusée.
- [ ] Un contenu non coché « public » n'apparaît jamais sur la page publique.
- [ ] Les exports CSV, PDF, iCal et RSS s'ouvrent correctement dans un tableur, un lecteur PDF, un agenda et un lecteur de flux courants.
- [ ] La sauvegarde complète permet de réinstaller le site à l'identique sur un autre serveur.

## 12. Questions ouvertes à trancher par le collectif

- [ ] Faut-il des gestionnaires dès le lancement, et avec quels droits ?
- [ ] Comment transmettre le code d'accès commun, et à quelle fréquence le changer ?
- [ ] Qui développe : un membre du collectif, un bénévole extérieur, un prestataire rémunéré ? Avec quel budget ?
- [ ] Quel serveur ? Faut-il confier un accès de secours (serveur et sauvegardes) à une seconde personne de confiance ?
- [ ] Nom de domaine propre, ou adresse fournie par l'hébergeur ?
- [ ] Quelles règles de décision par défaut : majorité simple ? quorum ? durée standard d'un vote ?
- [ ] Le vote anonyme, sans contrôle des doublons, est-il acceptable pour certains sujets ?
- [ ] Quelles salles le collectif gère-t-il réellement lui-même ?
- [ ] Faut-il afficher les emplois du temps universitaires (ADE), sachant que cela suppose de récupérer les liens iCal de chacun ?
- [ ] Qu'est-ce qui doit figurer sur la page publique dès le lancement ?
- [ ] À quel moment réévaluer le besoin d'une identification individuelle (par ex. après les premiers votes) ?
