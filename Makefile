.PHONY: install dev migrate demo test lint fmt check-deploy backup image-test

install:
	uv sync

dev:
	uv run python manage.py runserver

migrate:
	uv run python manage.py makemigrations
	uv run python manage.py migrate

demo:
	uv run python manage.py migrate
	uv run python manage.py seed_demo --reset

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run python manage.py makemigrations --check --dry-run

fmt:
	uv run ruff check --fix .
	uv run ruff format .

check-deploy:
	DJANGO_ENV=prod DJANGO_SECRET_KEY=verification-du-deploiement-pas-un-vrai-secret-0123456789abcdefghij DJANGO_ALLOWED_HOSTS=exemple.org \
		uv run python manage.py check --deploy --fail-level WARNING

backup:
	uv run python manage.py backup

image-test:
	docker build --target test -t collectif:test .
	docker run --rm collectif:test
