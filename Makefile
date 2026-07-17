.PHONY: setup lint typecheck test demo clean

UV := $(HOME)/.local/bin/uv

setup:
	$(UV) sync --group dev

lint:
	$(UV) run ruff check .

typecheck:
	$(UV) run mypy

test:
	$(UV) run pytest

demo:
	$(UV) run python scripts/seed_demo_data.py

clean:
	rm -rf data/lead_radar.db data/exports/*
