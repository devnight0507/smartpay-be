.PHONY: help setup dev-setup dev-up dev-down dev-restart lint format test migrations migrate migrate-down shell logs clean

PYTHON := python
DOCKER_COMPOSE := docker-compose
SERVICE := api
ALEMBIC := alembic

help:
	@echo "FastAPI Microservice Template Makefile"
	@echo ""
	@echo "Usage:"
	@echo "  make setup             Install Python dependencies"
	@echo "  make dev-setup         Setup development environment"
	@echo "  make dev-up            Start development containers"
	@echo "  make dev-down          Stop development containers"
	@echo "  make dev-restart       Restart development containers"
	@echo "  make lint              Run linters (black, isort, flake8, mypy)"
	@echo "  make format            Format code with black and isort"
	@echo "  make test              Run tests in Docker"
	@echo "  make migrations        Create migration with alembic"
	@echo "  make migrate           Apply all migrations"
	@echo "  make migrate-down      Rollback last migration"
	@echo "  make shell             Start a shell in the API container"
	@echo "  make logs              Show logs from containers"
	@echo "  make clean             Remove cache files and directories"

setup:
	$(PYTHON) -m pip install poetry
	poetry install

dev-setup:
	mkdir -p ./docker/postgres
	cp .env.example .env

dev-up:
	$(DOCKER_COMPOSE) up -d

dev-down:
	$(DOCKER_COMPOSE) down

dev-restart:
	$(DOCKER_COMPOSE) restart

lint:
	poetry run black --check .
	poetry run isort --check-only .
	poetry run flake8 .
	poetry run mypy app

format:
	poetry run black .
	poetry run isort .

test:
	$(DOCKER_COMPOSE) exec $(SERVICE) pytest -xvs $(T)

migrations:
	$(DOCKER_COMPOSE) exec $(SERVICE) $(ALEMBIC) revision --autogenerate -m "$(M)"

migrate:
	$(DOCKER_COMPOSE) exec $(SERVICE) $(ALEMBIC) upgrade head

migrate-down:
	$(DOCKER_COMPOSE) exec $(SERVICE) $(ALEMBIC) downgrade -1

shell:
	$(DOCKER_COMPOSE) exec $(SERVICE) /bin/bash

logs:
	$(DOCKER_COMPOSE) logs -f $(S)

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "*.egg" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".coverage" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
