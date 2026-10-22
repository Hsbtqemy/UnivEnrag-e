.PHONY: install dev migrate demo test lint fmt check-deploy

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
	DJANGO_ENV=prod DJANGO_SECRET_KEY=verification DJANGO_ALLOWED_HOSTS=exemple.org \
		uv run python manage.py check --deploy
