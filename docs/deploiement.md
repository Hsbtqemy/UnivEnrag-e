# Mettre le site en ligne

Le site tourne sur un serveur Linux avec Docker : trois conteneurs, une base SQLite dans un volume, aucun autre service à exploiter.

| Conteneur | Rôle |
|---|---|
| `app` | le site (Django + gunicorn). Applique les migrations et prépare les fichiers statiques à chaque démarrage. |
| `cron` | les tâches planifiées (`deploy/crontab`) : sauvegarde à 3 h, purges, idées réalisées. |
| `caddy` | HTTPS automatique (Let's Encrypt), fichiers statiques, relais vers `app`. |

Volumes : `donnees` (base et sauvegardes : **le seul à protéger**), `statiques` (régénéré), `caddy_data` (certificats).

Ni Caddy ni gunicorn ne tiennent de journal d'accès : aucune adresse IP n'est conservée côté site.

## Prérequis

- Un serveur Linux (1 Go de mémoire suffit) avec Docker et le greffon `docker compose`.
- Un nom de domaine dont l'enregistrement DNS (A, et AAAA si IPv6) pointe vers le serveur.
- Les ports 80 et 443 libres. Sur le serveur partagé avec Improliante et BD_ditor, ils sont pris par Nginx : suivre « Sur le serveur partagé ».

## Première installation

```bash
git clone https://github.com/<compte>/UnivEnrag-e.git collectif
cd collectif
cp .env.exemple .env
python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # à coller dans DJANGO_SECRET_KEY
nano .env                                                       # SITE_DOMAINE, DJANGO_SECRET_KEY
./deploy/deployer.sh
```

Le script joue les tests dans l'image, construit, démarre, puis vérifie `https://<domaine>/sante/`. Le premier démarrage prend une minute de plus, le temps d'obtenir le certificat.

### Créer l'administrateur principal



```bash
docker compose exec app python manage.py createsuperuser
```

Puis, dans le navigateur :

1. `https://<domaine>/gestion/` : connexion, puis configuration de la double authentification (QR code à scanner). Noter les codes de secours.
2. Administration → **Réglages du site** : nom du collectif, **code d'accès** des membres, contact pour les données personnelles.
3. Administration → Salles, Espaces : les créer. Gestionnaires : leur donner les droits utiles.

## Mettre à jour

```bash
cd ~/collectif && ./deploy/deployer.sh
```

Le script s'arrête au premier problème, sans rien casser :

- clone modifié à la main, ou pas sur `main` ;
- tests en échec dans l'image ;
- image qui ne se construit pas.

Il **sauvegarde la base avant** de redémarrer, car une migration ne se défait pas. Il ne revient jamais en arrière tout seul. En cas d'échec, il dit quelle version était en place.

## Sauvegardes

- **Chaque nuit à 3 h**, une archive `sauvegarde-AAAAMMJJ-HHMMSS.tar.gz` est écrite dans le volume `donnees` (`/data/sauvegardes`), et celles de plus de 30 jours sont effacées. Chaque archive contient la base (copie cohérente par l'API de SQLite) et un manifeste avec son empreinte.
- **À la demande** : `docker compose exec app python manage.py backup`, ou le bouton **Sauvegarde complète** de `/gestion/` (administrateur principal seulement, car l'archive contient les empreintes des mots de passe).
- **Hors du serveur** : à organiser. Une sauvegarde qui reste sur le serveur disparaît avec lui. Le plus simple est une copie quotidienne, depuis un autre poste, du dossier des archives :
  ```bash
  rsync -a serveur:/var/lib/docker/volumes/collectif_donnees/_data/sauvegardes/ ~/sauvegardes-collectif/
  ```
  ou `restic` / `borg` lancés sur le serveur vers un stockage distant.

### Restaurer

```bash
docker compose stop app cron
docker compose run --rm app python manage.py restore /data/sauvegardes/<archive>.tar.gz              # vérifie seulement
docker compose run --rm app python manage.py restore /data/sauvegardes/<archive>.tar.gz --confirmer  # remplace
docker compose up -d
```

La restauration :

- vérifie l'empreinte et l'intégrité de l'archive ;
- refuse une sauvegarde venue d'une version plus récente du site ;
- sauvegarde d'abord l'état actuel (`…-avant-restauration.tar.gz`) ;
- applique ensuite les migrations.

Pour restaurer une archive venue d'ailleurs, la copier d'abord dans le volume : `docker compose cp <archive> app:/data/sauvegardes/`.

## Sur le serveur partagé (Improliante, BD_ditor)

Sur ce serveur, le Nginx de l'hôte tient déjà les ports 80 et 443 et gère les certificats (certbot) pour les autres sites. Le Caddy du collectif écoute donc seulement en local, et Nginx lui relaie le trafic : c'est la même organisation que BD_ditor.

**Adresse : `collectif.edito-revue.fr`.** Préalable : chez le gestionnaire DNS de `edito-revue.fr`, ajouter un enregistrement `A` (`collectif` → `83.228.221.204`, et `AAAA` si le serveur a une IPv6), puis vérifier qu'il répond : `dig +short collectif.edito-revue.fr`.

*Solution de repli, sans toucher au DNS* : `collectif.83-228-221-204.sslip.io` résout vers le serveur sans rien configurer. Mais `sslip.io` n'est pas un suffixe public : le quota de Let's Encrypt est partagé avec tous ses utilisateurs, et certbot peut refuser (`rateLimited`). Il faut alors réessayer plus tard. Changer d'adresse ensuite revient à modifier `SITE_DOMAINE` et le `server_name`, puis à relancer certbot. Les abonnements iCal déjà pris seront à refaire.

1. Vérifier qu'un port local est libre (BD_ditor utilise 8080) :
   ```bash
   ss -ltn | grep -E ':8081\b' || echo "8081 libre"
   ```
2. Dans le clone, régler `.env` **une fois pour toutes**. Sans `COMPOSE_FILE`, un `docker compose up -d` tapé à la main tenterait de prendre 80 et 443, à côté de Nginx (leçon de BD_ditor) :
   ```
   SITE_DOMAINE=collectif.edito-revue.fr
   COMPOSE_FILE=compose.yaml:compose.derriere-proxy.yaml
   PORT_LOCAL=8081
   DJANGO_SECRET_KEY=…
   ```
   Contrôle : `docker compose config | grep Caddyfile.derriere-proxy` doit afficher une ligne.
3. Démarrer : `./deploy/deployer.sh`. Le contrôle final échoue tant que Nginx n'est pas réglé : c'est attendu la première fois. `curl -H "Host: collectif.edito-revue.fr" http://127.0.0.1:8081/sante/` doit déjà répondre `ok`.
4. Nginx : copier `deploy/nginx-hote.conf.exemple` dans `/etc/nginx/sites-available/collectif`, y vérifier le nom et le port, puis :
   ```bash
   sudo ln -s /etc/nginx/sites-available/collectif /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl reload nginx     # nginx -t TOUJOURS avant : une erreur coupe aussi les autres sites
   sudo certbot --nginx -d collectif.edito-revue.fr
   ```
5. `https://collectif.edito-revue.fr/sante/` répond `ok` : passer à « Créer l'administrateur principal » ci-dessus.

Le bloc Nginx n'écrit pas de journal d'accès (`access_log off`) et transmet l'adresse du client par `X-Forwarded-For $remote_addr`, sans reprendre un en-tête fourni par le client.

## Au quotidien

| Besoin | Commande |
|---|---|
| État des conteneurs | `docker compose ps` |
| Journaux (erreurs, tâches de nuit) | `docker compose logs --tail 100 app cron` |
| Une commande Django | `docker compose exec app python manage.py <commande>` |
| Arrêter / relancer | `docker compose stop` / `docker compose up -d` |

## Tâches planifiées

| Heure | Commande | Effet |
|---|---|---|
| 3 h 00 | `backup` | sauvegarde de la base, rotation sur 30 jours |
| 3 h 30 | `purge_presences` | efface les présences de plus de 60 jours |
| 3 h 35 | `purge_ip_data` | efface les empreintes d'IP de plus de 30 jours |
| 3 h 40 | `clearsessions` | efface les sessions expirées |
| 3 h 45 | `purge_contact_messages` | efface les messages de contact de plus d'un an |
| chaque heure | `ideas_mark_done` | passe à « Réalisée » les idées dont l'événement est passé |
