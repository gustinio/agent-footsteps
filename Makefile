.DEFAULT_GOAL := help
.PHONY: help setup lint test reproduce run-demo label clean

help: ## Print this list of targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

setup: ## Install Python dependencies
	uv sync

lint: ## Lint and check formatting
	uv run ruff check .
	uv run ruff format --check .

test: ## Run the Python tests
	uv run pytest

reproduce: ## Download public data at its pinned revision, then regenerate results with no model calls
	uv run footsteps ingest
	uv run footsteps export

run-demo: ## Run planted behaviours (USES MODEL CREDIT)
	@echo "warning: run-demo uses model credit" >&2
	uv run footsteps runner

label: ## Name behaviours with the LLM (USES MODEL CREDIT)
	@echo "warning: label uses model credit" >&2
	uv run footsteps label

# Never touches data/, raw transcripts or results/.
clean: ## Remove build output and caches
	rm -rf .pytest_cache .ruff_cache dist web/dist
	find src tests -name __pycache__ -type d -prune -exec rm -rf {} +
