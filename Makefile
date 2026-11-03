# Orkestr developer commands
.PHONY: help up down logs ps test eval workflows demo dev-api dev-web n8n-import fmt

help:            ## Show commands
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/'

up:              ## Start the core stack (postgres, n8n, api, web)
	@test -f .env || cp .env.example .env
	docker compose up -d --build

up-obs:          ## Core stack + OpenTelemetry collector, Jaeger and Prometheus
	docker compose --profile observability up -d --build

down:            ## Stop everything (data volumes are kept)
	docker compose --profile observability down

logs:            ## Follow API and n8n logs
	docker compose logs -f api n8n

test:            ## Backend test suite (needs PostgreSQL with pgvector; see README)
	cd backend && python -m pytest -q

eval:            ## Run evaluation suites; writes backend/evals/results and the landing-page summary
	cd backend && python -m evals.run_evals

workflows:       ## Regenerate n8n workflow JSON from n8n/build_workflows.py
	python n8n/build_workflows.py

n8n-import:      ## Re-import workflows into the running n8n container and restart it
	docker compose run --rm n8n-init && docker compose restart n8n

demo:            ## Send signed demo events through n8n (requires the stack to be up)
	./scripts/demo.sh

dev-api:         ## Run the API locally with reload
	cd backend && uvicorn app.main:app --reload --port 8000

dev-web:         ## Run the web app locally
	cd frontend && npm run dev
