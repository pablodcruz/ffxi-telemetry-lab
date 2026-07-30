PYTHON ?= python3
SOURCE_ROOT ?=

.PHONY: install test backfill prepare dbt-build notebook dashboard observer

install:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest

backfill:
	$(PYTHON) -m ffxi_telemetry.cli backfill --source-root "$(SOURCE_ROOT)"

prepare:
	$(PYTHON) -m ffxi_telemetry.cli prepare-warehouse

dbt-build:
	dbt build --profiles-dir .

notebook:
	$(PYTHON) scripts/run_notebook.py

dashboard:
	streamlit run dashboard/app.py

observer:
	$(PYTHON) -m ffxi_telemetry.cli observe --source-root "$(SOURCE_ROOT)"
