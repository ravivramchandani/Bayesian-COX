PYTHON ?= python
CONDA_ENV ?= bayes-cox

# The thesis document lives in a separate Overleaf-backed repository beside
# this one, so `thesis` compiles out of tree.
THESIS_DIR ?= ../thesis-overleaf
THESIS_MAIN ?= Main

.PHONY: env data eda benchmark explain figures reports thesis jargon test schemas lint format all clean

env:
	conda env create -f environment.yml || conda env update -f environment.yml

data:
	$(PYTHON) scripts/download_datasets.py
	$(PYTHON) scripts/prepare_dataset.py

eda:
	$(PYTHON) scripts/run_eda.py

benchmark:
	$(PYTHON) scripts/run_benchmark.py

explain:
	$(PYTHON) scripts/run_explainability.py

figures:
	$(PYTHON) scripts/make_figures.py

reports:
	$(PYTHON) scripts/make_reports.py

thesis:
	@test -d $(THESIS_DIR) || { echo "thesis repository not found at $(THESIS_DIR)"; exit 1; }
	cd $(THESIS_DIR) && latexmk -pdf -bibtex -interaction=nonstopmode $(THESIS_MAIN).tex

# Internal identifiers and process language must not reach the compiled
# chapters. The reproducibility appendix is exempt.
jargon:
	@hits=$$(grep -rEn "ADR-[0-9]|INV-[0-9]|T-[0-9]{3}|Q-[0-9]{3}|coordination/" \
		$(THESIS_DIR) --include="*.tex" 2>/dev/null \
		| grep -v "appendix_reproducibility.tex" || true); \
	if [ -n "$$hits" ]; then \
		echo "internal project language found in thesis chapters:"; \
		echo "$$hits"; \
		exit 1; \
	fi; \
	echo "no internal project language in thesis chapters"

schemas:
	$(PYTHON) tests/test_coordination_schemas.py

test: schemas
	$(PYTHON) -m pytest tests -q

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff format .

all: data eda benchmark explain figures reports

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache build dist src/*.egg-info
