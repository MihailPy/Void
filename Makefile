.PHONY: cli api web web-install check clean help

help:
	@echo "Void commands:"
	@echo "  make cli          Run CLI"
	@echo "  make api          Run FastAPI backend"
	@echo "  make web          Run Web UI"
	@echo "  make web-install  Install Web UI deps"
	@echo "  make check        Run Python compile check"
	@echo "  make clean        Remove caches"

cli:
	uv run python -m void.main

api:
	uv run python -m void.api.server

web:
	cd web && npm run dev

web-install:
	cd web && npm install

check:
	uv run python -m compileall .

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -prune -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -prune -exec rm -rf {} +
