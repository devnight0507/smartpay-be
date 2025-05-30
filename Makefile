.PHONY: help setup dev-setup dev-up dev-down dev-restart prod-up prod-down prod-restart lint format test coverage migrations migrate migrate-down shell logs clean

PYTHON := python
DOCKER_COMPOSE := docker-compose
DEV_COMPOSE := docker-compose -f docker-compose.yml --env-file .env
DEV_SERVICE := smartpay-api-dev
ALEMBIC := alembic

help:
	@echo "FastAPI Microservice Template Makefile"
	@echo ""
	@echo "Usage:"
	@echo "  make dev-setup         Setup development environment"
	@echo "  make dev-up            Start development containers"
	@echo "  make dev-down          Stop development containers"
	@echo "  make dev-restart       Restart development containers"
	@echo "  make prod-up           Start production containers"
	@echo "  make prod-down         Stop production containers"
	@echo "  make prod-restart      Restart production containers"
	@echo "  make lint              Run linters (black, isort, flake8, mypy)"
	@echo "  make format            Format code with black and isort"
	@echo "  make test              Run tests in Docker"
	@echo "  make coverage          Run tests with coverage report (min 80%)"
	@echo "  make migrations        Create migration with alembic (dev)"
	@echo "  make migrate           Apply all migrations (dev)"
	@echo "  make migrate-down      Rollback last migration (dev)"
	@echo "  make shell             Start a shell in the API container (dev)"
	@echo "  make logs              Show logs from containers"
	@echo "  make clean             Remove cache files and directories"

setup:
	$(PYTHON) -m pip install poetry
	poetry install

dev-setup:
	mkdir -p ./docker/postgres
	cp .env.dev .env

dev-up:
	$(DEV_COMPOSE) up -d

dev-down:
	$(DEV_COMPOSE) down

dev-restart:
	$(DEV_COMPOSE) restart

lint:
	poetry run black --check .
	poetry run isort --check-only .
	poetry run flake8 .
	poetry run mypy app

format:
	poetry run black .
	poetry run isort .

test:
	$(DEV_COMPOSE) exec $(DEV_SERVICE) pytest -xvs $(T)

coverage:
	$(DEV_COMPOSE) exec $(DEV_SERVICE) pytest --cov=app --cov-report=term-missing --cov-report=xml --cov-fail-under=80

migrations:
	$(DEV_COMPOSE) exec $(DEV_SERVICE) $(ALEMBIC) revision --autogenerate -m "$(M)"

migrate:
	$(DEV_COMPOSE) run $(DEV_SERVICE) $(ALEMBIC) upgrade head

migrate-down:
	$(DEV_COMPOSE) exec $(DEV_SERVICE) $(ALEMBIC) downgrade -1

shell:
	$(DEV_COMPOSE) exec $(DEV_SERVICE) /bin/bash

logs:
	$(DEV_COMPOSE) logs -f $(DEV_SERVICE)

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "*.egg" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".coverage" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
