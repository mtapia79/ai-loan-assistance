.PHONY: help install dev lint test test-cov build up down migrate seed clean

PYTHON := python3
PIP    := pip
APP    := app.main:app

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Local setup ─────────────────────────────────────────────
install: ## Install production dependencies
	$(PIP) install -e .

dev: ## Install dev dependencies
	$(PIP) install -e ".[dev]"

# ── Code quality ────────────────────────────────────────────
lint: ## Run ruff linter
	ruff check app tests
	ruff format --check app tests

format: ## Auto-format code
	ruff format app tests
	ruff check --fix app tests

typecheck: ## Run mypy type checker
	mypy app

# ── Testing ──────────────────────────────────────────────────
test: ## Run tests (requires running DB)
	pytest tests/ -v --asyncio-mode=auto

test-cov: ## Run tests with coverage report
	pytest tests/ -v --asyncio-mode=auto --cov=app --cov-report=html --cov-report=term-missing

test-unit: ## Run only unit tests (no DB required)
	pytest tests/unit/ -v --asyncio-mode=auto

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
	alembic upgrade head

migrate-create: ## Create a new migration (use: make migrate-create MSG="description")
	alembic revision --autogenerate -m "$(MSG)"

seed: ## Seed lending policies into pgvector
	$(PYTHON) -m app.rag.ingestion

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
