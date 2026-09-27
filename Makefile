PYTHON ?= python
CONDA_LOCK ?= conda-lock
LOCK_ENV ?= bayes-cox-lock-verify
LOCK_FILE ?= conda-lock.yml
LOCK_VIRTUAL_PACKAGES ?= conda-lock-virtual-packages.yml
CONFIRMATORY_RUN ?=
EXPLAINABILITY_ARTIFACT ?=
ROBUSTNESS_RUN ?=
RENDER_OUTPUT ?=
REPRODUCTION_SELECTION ?= quick
REPRODUCTION_WORKERS ?= 1
REPRODUCTION_REPORT ?=
RENDER_OPTIONAL_ARGS = $(if $(EXPLAINABILITY_ARTIFACT),--explainability-artifact "$(EXPLAINABILITY_ARTIFACT)") $(if $(ROBUSTNESS_RUN),--robustness-dir "$(ROBUSTNESS_RUN)") $(if $(RENDER_OUTPUT),--output-dir "$(RENDER_OUTPUT)")

# The thesis document lives in a separate Overleaf-backed repository beside
# this one, so `thesis` compiles out of tree.
THESIS_DIR ?= ../thesis-overleaf
THESIS_MAIN ?= Main

.PHONY: env lock env-locked verify-env clean-build data confirmatory-rehearsal confirmatory confirmatory-resume reproduce-confirmatory robustness robustness-resume explain render-confirmatory figures reports thesis jargon test schemas lint format all clean

env: env-locked

lock:
	$(CONDA_LOCK) lock --platform osx-arm64 --file environment.yml \
		--lockfile $(LOCK_FILE) --virtual-package-spec $(LOCK_VIRTUAL_PACKAGES) \
		--metadata input_md5 --metadata input_sha
	shasum -a 256 $(LOCK_FILE) > $(LOCK_FILE).sha256

env-locked:
	$(CONDA_LOCK) install --name $(LOCK_ENV) $(LOCK_FILE)

verify-env:
	$(PYTHON) scripts/verify_environment.py --lock-file $(LOCK_FILE) \
		--hash-file $(LOCK_FILE).sha256

# LOCK_ENV must be a new environment name. Keeping the verified environment
# permits an independent rerun and avoids deleting user-managed environments.
clean-build:
	$(CONDA_LOCK) install --name $(LOCK_ENV) $(LOCK_FILE)
	conda run --name $(LOCK_ENV) python scripts/verify_environment.py \
		--lock-file $(LOCK_FILE) --hash-file $(LOCK_FILE).sha256
	conda run --name $(LOCK_ENV) python -m pytest tests -q
	conda run --name $(LOCK_ENV) python -m ruff check .

data:
	$(PYTHON) scripts/download_datasets.py

confirmatory-rehearsal:
	$(PYTHON) scripts/run_confirmatory.py --mode rehearsal

confirmatory:
	$(PYTHON) scripts/run_confirmatory.py --mode confirmatory

confirmatory-resume:
	$(PYTHON) scripts/run_confirmatory.py --mode confirmatory --resume

reproduce-confirmatory:
	@test -n "$(CONFIRMATORY_RUN)" || { echo "set CONFIRMATORY_RUN to a completed frozen run"; exit 1; }
	$(PYTHON) scripts/reproduce_confirmatory_cells.py --run-dir "$(CONFIRMATORY_RUN)" --selection "$(REPRODUCTION_SELECTION)" --workers $(REPRODUCTION_WORKERS) $(if $(REPRODUCTION_REPORT),--report "$(REPRODUCTION_REPORT)")

robustness:
	@test -n "$(CONFIRMATORY_RUN)" || { echo "set CONFIRMATORY_RUN to a completed frozen run"; exit 1; }
	$(PYTHON) scripts/run_robustness.py --mode robustness --confirmatory-run "$(CONFIRMATORY_RUN)"

robustness-resume:
	@test -n "$(CONFIRMATORY_RUN)" || { echo "set CONFIRMATORY_RUN to a completed frozen run"; exit 1; }
	$(PYTHON) scripts/run_robustness.py --mode robustness --confirmatory-run "$(CONFIRMATORY_RUN)" --resume

explain:
	@test -n "$(CONFIRMATORY_RUN)" || { echo "set CONFIRMATORY_RUN to a completed frozen run"; exit 1; }
	$(PYTHON) scripts/run_confirmatory_explainability.py --run-dir "$(CONFIRMATORY_RUN)"

render-confirmatory:
	@test -n "$(CONFIRMATORY_RUN)" || { echo "set CONFIRMATORY_RUN to a completed frozen run"; exit 1; }
	$(PYTHON) scripts/render_confirmatory.py --run-dir "$(CONFIRMATORY_RUN)" $(RENDER_OPTIONAL_ARGS)

figures: render-confirmatory

reports: render-confirmatory

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

all: verify-env test lint

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache build dist src/*.egg-info
