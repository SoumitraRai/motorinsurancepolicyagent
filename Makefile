# One-command checks for the sdlc loop (sdlc.config.json `commands.*`).
# Healthy output markers: build -> "Build succeeded", test -> "passed", lint -> "All checks passed".
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.PHONY: build test e2e lint format run run-api run-worker

BACKEND := backend
FRONTEND := frontend

build:
	cd $(BACKEND) && uv sync --frozen
	cd $(FRONTEND) && npm ci --no-audit --no-fund && npm run build
	@echo "Build succeeded"

test:
	cd $(BACKEND) && uv run pytest -q
	cd $(FRONTEND) && npx vitest --run

# End-to-end on the four samples (slow: OCR of 40 pages). Must pass before submission.
e2e:
	cd $(BACKEND) && uv run pytest -q -m e2e

lint:
	cd $(BACKEND) && uv run ruff check . && uv run ruff format --check . && uv run mypy src
	cd $(FRONTEND) && npx eslint . --max-warnings 0 && npx tsc -b
	python3 scripts/check_no_sample_answers.py $(BACKEND)/tests
	@echo "All checks passed"

# `make format` formats everything; `make format <file>...` (used by the sdlc format-on-edit hook)
# formats just those files.
FORMAT_FILES := $(filter-out format,$(MAKECMDGOALS))
format:
ifeq ($(strip $(FORMAT_FILES)),)
	cd $(BACKEND) && uv run ruff format . && uv run ruff check --fix .
	cd $(FRONTEND) && npx prettier --write src
else
	@for f in $(FORMAT_FILES); do \
	  case "$$f" in \
	    *.py) uv run --project $(BACKEND) ruff format "$$f" ;; \
	    *.ts|*.tsx|*.css|*.json) (cd $(FRONTEND) && npx prettier --write "$$f") ;; \
	  esac; \
	done
endif
ifneq ($(filter format,$(MAKECMDGOALS)),)
$(FORMAT_FILES):
	@:
endif

run:
	$(MAKE) -j2 run-api run-worker

run-api:
	cd $(BACKEND) && uv run uvicorn rater.api.app:app --reload --port 8000

run-worker:
	cd $(BACKEND) && uv run python -m rater.worker
