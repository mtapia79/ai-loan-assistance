.PHONY: help install dev lint format test test-cov test-unit build up down logs migrate migrate-create seed clean pre-commit k8s-apply k8s-delete k8s-status

PYTHON := python3
POETRY := poetry
APP    := app.main:app

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Local setup ─────────────────────────────────────────────
install: ## Install production dependencies with Poetry
	$(POETRY) install --no-dev

dev: ## Install all dependencies including dev tools
	$(POETRY) install

# ── Code quality ────────────────────────────────────────────
lint: ## Run linters (ruff + black)
	$(POETRY) run ruff check app tests
	$(POETRY) run ruff format --check app tests
	$(POETRY) run black --check app tests

format: ## Auto-format code with Black and Ruff
	$(POETRY) run black app tests
	$(POETRY) run ruff check --fix app tests
	$(POETRY) run ruff format app tests

typecheck: ## Run mypy type checker
	$(POETRY) run mypy app

pre-commit: ## Run pre-commit hooks
	$(POETRY) run pre-commit run --all-files

# ── Testing ──────────────────────────────────────────────────
test: ## Run all tests (requires running DB)
	$(POETRY) run pytest tests/ -v --asyncio-mode=auto

test-cov: ## Run tests with coverage report
	$(POETRY) run pytest tests/ -v --asyncio-mode=auto --cov=app --cov-report=html --cov-report=term-missing

test-unit: ## Run only unit tests (no DB required)
	$(POETRY) run pytest tests/unit/ -v --asyncio-mode=auto

# ── Docker ───────────────────────────────────────────────────
build: ## Build Docker image
	docker build -t ai-loan-assistance:local .

up: ## Start all services with docker-compose
	docker compose up -d

down: ## Stop all services
	docker compose down

logs: ## Follow app logs
	docker compose logs -f app

# ── Database ─────────────────────────────────────────────────
migrate: ## Run Alembic migrations
	$(POETRY) run alembic upgrade head

migrate-create: ## Create a new migration (use: make migrate-create MSG="description")
	$(POETRY) run alembic revision --autogenerate -m "$(MSG)"

seed: ## Seed database with sample data and policies
	$(POETRY) run $(PYTHON) -m app.db.seed
	$(POETRY) run $(PYTHON) -m app.rag.ingestion


# ── Kubernetes ───────────────────────────────────────────────
k8s-apply: ## Apply k8s manifests to current context
	kubectl apply -f k8s/

k8s-delete: ## Delete k8s resources
	kubectl delete -f k8s/

k8s-status: ## Show pod status
	kubectl get pods -n loan-assistance

# ── Cleanup ──────────────────────────────────────────────────
clean: ## Remove build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .coverage htmlcov/ .pytest_cache/ dist/ build/ *.egg-info/
