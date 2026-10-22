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
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "admin:login"

# Double authentification des comptes de gestion (CLAUDE.md ACC-3). Obligatoire hors
# développement ; en local, DJANGO_ADMIN_2FA=1 permet de l'essayer.
ADMIN_2FA_REQUIRED = os.environ.get("DJANGO_ADMIN_2FA", "1" if ENV != "dev" else "0") == "1"
OTP_TOTP_ISSUER = "Plateforme du collectif"

ACTOR_RESOLVER = "apps.actors.resolvers.NameCookieResolver"

X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CONTENT_TYPE_NOSNIFF = True

if ENV == "prod":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# Formulaire public de proposition (fiche du POC, « Anti-spam »).
PROPOSAL_MIN_FILL_SECONDS = 3
PROPOSAL_RATE_LIMIT = (5, 3600)  # 5 propositions par heure et par adresse IP
