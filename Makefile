SHELL := /bin/sh

PYTHON := $(if $(wildcard worker/.venv/bin/python),$(abspath worker/.venv/bin/python),python3)
UV ?= uv
RELEASE_ID := fixture-2026-08-16-001
FIXTURE_RELEASE := ../work/release/$(RELEASE_ID)/public-release.json

.PHONY: bootstrap check test database-test eval demo web collect-dry-run

bootstrap:
	@command -v $(UV) >/dev/null 2>&1 || { echo "uv is required: https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
	$(UV) sync --project worker --locked --extra dev
	cd web && npm ci
	cd web && npx playwright install chromium

check:
	$(PYTHON) scripts/check_env.py
	$(PYTHON) -m ruff format --check worker/src worker/tests scripts evals supabase/tests
	$(PYTHON) -m ruff check worker/src worker/tests scripts evals supabase/tests
	cd worker && $(PYTHON) -m mypy
	$(PYTHON) scripts/generate_database_types.py --check
	$(PYTHON) scripts/check_workflows_pinned.py
	$(PYTHON) scripts/check_secrets.py --repo
	cd web && npm run check

test:
	$(PYTHON) -m pytest worker/tests supabase/tests
	cd web && npm run test:e2e
	$(PYTHON) scripts/check_secrets.py --export web/out

database-test:
	./scripts/run_local_database_tests.sh

eval:
	$(PYTHON) evals/run_recorded_eval.py
	$(PYTHON) evals/check_behavior_manifest.py

demo:
	$(PYTHON) scripts/run_fixture_demo.py
	cd web && SCAM_RADAR_RELEASE_PATH=$(FIXTURE_RELEASE) NEXT_PUBLIC_RELEASE_ID=$(RELEASE_ID) npm run build
	$(PYTHON) scripts/check_secrets.py --export web/out

web:
	cd web && npm run dev

collect-dry-run:
	PYTHONPATH=worker/src $(PYTHON) -m scam_radar.cli collect-dry-run
