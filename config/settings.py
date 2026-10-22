"""Réglages du projet, pilotés par des variables d'environnement.

`DJANGO_ENV` vaut `dev` (défaut), `test` ou `prod`. En production, `DJANGO_SECRET_KEY`
et `DJANGO_ALLOWED_HOSTS` sont obligatoires.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

ENV = os.environ.get("DJANGO_ENV", "dev")
DEBUG = ENV == "dev"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if ENV == "prod":
        raise RuntimeError("DJANGO_SECRET_KEY est obligatoire en production.")
    SECRET_KEY = "dev-uniquement-ne-pas-utiliser-en-production"

ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h]
if DEBUG:
    ALLOWED_HOSTS += ["localhost", "127.0.0.1", "[::1]"]

# Derrière un proxy (Caddy, Nginx), REMOTE_ADDR est celle du proxy : on lit alors la
# première adresse de X-Forwarded-For. À n'activer que si le proxy écrase cet en-tête.
TRUST_X_FORWARDED_FOR = os.environ.get("DJANGO_TRUST_X_FORWARDED_FOR", "") == "1"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
    "apps.core",
    "apps.actors",
    "apps.audit",
    "apps.accounts",
    "apps.rooms",
    "apps.spaces",
    "apps.ideas",
    "apps.agenda",
    "apps.presences",
    "apps.polls",
    "apps.public",
]

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "apps.accounts.two_factor.RequireTwoFactorMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.SecurityHeadersMiddleware",
    "apps.core.access.AccessCodeMiddleware",
    "apps.actors.resolvers.ActorMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site",
                "apps.accounts.context_processors.management",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DJANGO_DB_PATH", BASE_DIR / "db.sqlite3"),
        "OPTIONS": {
            "transaction_mode": "IMMEDIATE",
            "timeout": 5,
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;",
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
# En production, Caddy sert ce dossier directement (volume partagé, deploy/Caddyfile).
STATIC_ROOT = Path(os.environ.get("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles"))

# Sauvegardes quotidiennes (commande `backup`), conservées 30 jours.
BACKUP_DIR = Path(os.environ.get("DJANGO_BACKUP_DIR", BASE_DIR / "sauvegardes"))
BACKUP_KEEP_DAYS = 30

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "admin:login"

# Double authentification des comptes de gestion (CLAUDE.md ACC-3). Obligatoire hors
# développement ; en local, DJANGO_ADMIN_2FA=1 permet de l'essayer.
ADMIN_2FA_REQUIRED = os.environ.get("DJANGO_ADMIN_2FA", "1" if ENV != "dev" else "0") == "1"
OTP_TOTP_ISSUER = "Université Enragée"  # nom affiché dans l'application d'authentification

ACTOR_RESOLVER = "apps.actors.resolvers.NameCookieResolver"

X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CONTENT_TYPE_NOSNIFF = True

if ENV == "prod":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    # La sonde de santé du conteneur interroge gunicorn en HTTP, sans passer par Caddy.
    SECURE_REDIRECT_EXEMPT = [r"^sante/$"]
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Noms de fichiers statiques versionnés (app.3f2a9c.css) : Caddy peut les garder en
    # cache un an, et une mise à jour ne mélange jamais l'ancien JS et le nouveau HTML.
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "apps.core.storage.StaticStorage"},
    }
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # Pas de « preload » : l'inscription dans les navigateurs engage le domaine pour des
    # mois et se défait mal. À décider avec le collectif une fois le domaine stable.
    SILENCED_SYSTEM_CHECKS = ["security.W021"]

# Formulaire public de proposition (fiche du POC, « Anti-spam »).
PROPOSAL_MIN_FILL_SECONDS = 3
PROPOSAL_RATE_LIMIT = (5, 3600)  # 5 propositions par heure et par adresse IP
CONTACT_RATE_LIMIT = (5, 3600)  # 5 messages de contact par heure et par adresse IP
# DÉCISION (à confirmer) : messages de contact effacés après un an (purge_contact_messages).
CONTACT_KEEP_DAYS = 365

# Journaux : erreurs sur la sortie standard, jamais d'adresse IP (CLAUDE.md « Sécurité et
# RGPD »). gunicorn tourne sans journal d'accès et Caddy sans directive `log`.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
}
