SHELL := /bin/sh
export NEXT_TELEMETRY_DISABLED := 1

PYTHON := $(if $(wildcard worker/.venv/bin/python),$(abspath worker/.venv/bin/python),python3)
UV ?= uv
DOCKER_BIN ?= docker
RELEASE_ID := fixture-2026-08-16-001
FIXTURE_RELEASE := ../work/release/$(RELEASE_ID)/public-release.json

.PHONY: recovery-rehearsal joined-local-e2e deployment-local-e2e bootstrap check test database-test eval demo web collect-dry-run open-source-audit pages-artifact-check

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
	node --check cloudflare/scheduler/src/index.mjs
	node --check cloudflare/scheduler/test/index.test.mjs
	node --check cloudflare/backup-scheduler/src/index.mjs
	node --check cloudflare/backup-scheduler/test/index.test.mjs
	$(MAKE) open-source-audit
	cd web && npm run check

test:
	$(PYTHON) -m pytest worker/tests supabase/tests
	node --test cloudflare/scheduler/test/*.test.mjs
	node --test cloudflare/backup-scheduler/test/*.test.mjs
	cd web && npm run test:e2e
	$(PYTHON) scripts/check_secrets.py --export web/out

database-test:
	./scripts/run_local_database_tests.sh
	$(PYTHON) scripts/check_database_public_export.py
	PYTHONPATH=worker/src $(PYTHON) worker/tests/integration/local_pipeline_e2e.py --full-review
	RUN_EXISTING_PATTERN_CONTRACT=true ./scripts/run_local_database_tests.sh

joined-local-e2e:
	@case "$(SCAM_RADAR_LOCAL_API_URL)" in http://127.0.0.1:*) ;; *) echo "Set SCAM_RADAR_LOCAL_API_URL to an isolated localhost Supabase API." >&2; exit 1;; esac
	@case "$(SUPABASE_DB_CONTAINER)" in supabase_db_scam-radar-*) ;; *) echo "Set SUPABASE_DB_CONTAINER to a named synthetic local stack." >&2; exit 1;; esac
	PYTHONPATH=worker/src $(PYTHON) worker/tests/integration/local_pipeline_e2e.py --full-review --browser-review
	PYTHONPATH=worker/src $(PYTHON) worker/tests/integration/local_existing_crash_e2e.py
	PYTHONPATH=worker/src $(PYTHON) worker/tests/integration/local_pending_review_e2e.py
	PYTHONPATH=worker/src $(PYTHON) worker/tests/integration/local_update_release_e2e.py

deployment-local-e2e:
	@case "$(SCAM_RADAR_LOCAL_API_URL)" in http://127.0.0.1:*) ;; *) echo "Set SCAM_RADAR_LOCAL_API_URL to an isolated localhost Supabase API." >&2; exit 1;; esac
	@case "$(SUPABASE_DB_CONTAINER)" in supabase_db_scam-radar-*) ;; *) echo "Set SUPABASE_DB_CONTAINER to a named synthetic local stack." >&2; exit 1;; esac
	PYTHONPATH=worker/src $(PYTHON) worker/tests/integration/local_pipeline_e2e.py --full-review --browser-review
	PYTHONPATH=worker/src $(PYTHON) worker/tests/integration/local_deployment_e2e.py

eval:
	$(PYTHON) evals/run_recorded_eval.py
	$(PYTHON) evals/check_behavior_manifest.py

demo:
	$(PYTHON) scripts/run_fixture_demo.py
	cd web && SCAM_RADAR_RELEASE_PATH=$(FIXTURE_RELEASE) NEXT_PUBLIC_RELEASE_ID=$(RELEASE_ID) npm run build
	$(PYTHON) scripts/check_secrets.py --export web/out
	$(MAKE) pages-artifact-check

pages-artifact-check:
	$(PYTHON) scripts/check_pages_artifact.py --root web/out --release-id $(RELEASE_ID)

web:
	cd web && npm run dev

collect-dry-run:
	PYTHONPATH=worker/src $(PYTHON) -m scam_radar.cli collect-dry-run

open-source-audit:
	$(PYTHON) scripts/check_secrets.py --repo
	$(PYTHON) scripts/check_secrets.py --history
	$(PYTHON) scripts/check_public_boundary.py

recovery-rehearsal:
	@case "$(SUPABASE_DB_CONTAINER)" in supabase_db_scam-radar-*) ;; *) echo "Set SUPABASE_DB_CONTAINER to a named synthetic local stack." >&2; exit 1;; esac
	$(PYTHON) scripts/rehearse_database_recovery.py --container $(SUPABASE_DB_CONTAINER) --age-directory work/launch-readiness/age
	$(PYTHON) worker/tests/integration/local_backup_e2e.py --container $(SUPABASE_DB_CONTAINER) --docker "$(DOCKER_BIN)" --age-directory work/launch-readiness/age --rclone work/launch-readiness/rclone-mac-tool/rclone-v1.75.1-osx-arm64/rclone
