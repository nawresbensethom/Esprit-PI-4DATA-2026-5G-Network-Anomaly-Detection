.PHONY: install test lint typecheck train serve serve-training serve-monitoring clean demo-batch format format-check security

PYTHON := python
PIP    := pip

install:
	$(PIP) install -e ".[dev,api,mlflow]"

test:
	pytest tests/ -v --cov=moe_ids --cov-report=term-missing

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v -s

lint:
	ruff check moe_ids/ scripts/ tests/ services/

format:
	black moe_ids/ scripts/ tests/ services/
	ruff check --fix moe_ids/ scripts/ tests/ services/

format-check:
	black --check moe_ids/ scripts/ tests/ services/
	ruff check moe_ids/ scripts/ tests/ services/

security:
	bandit -r moe_ids/ services/ scripts/ -ll
	pip-audit --strict || true

typecheck:
	mypy moe_ids/ scripts/

train:
	$(PYTHON) scripts/train.py \
		--data-5g "$${DATA_5G_PATH:-../MoE/Global_CLEANED.csv}" \
		--data-6g "$${DATA_6G_PATH:-../MoE/AIoT_6G_CLEANED.csv}" \
		--artefacts-dir "$${ARTEFACTS_DIR:-artefacts}" \
		--seed "$${SEED:-42}" \
		--mlflow-tracking-uri "$${MLFLOW_TRACKING_URI:-http://localhost:5000}"

train-offline:
	$(PYTHON) scripts/train.py \
		--data-5g "$${DATA_5G_PATH:-../MoE/Global_CLEANED.csv}" \
		--data-6g "$${DATA_6G_PATH:-../MoE/AIoT_6G_CLEANED.csv}" \
		--artefacts-dir "$${ARTEFACTS_DIR:-artefacts}" \
		--seed "$${SEED:-42}" \
		--no-mlflow

evaluate:
	$(PYTHON) scripts/evaluate.py \
		--artefacts-dir "$${ARTEFACTS_DIR:-artefacts}" \
		--data-5g "$${DATA_5G_PATH:-../MoE/Global_CLEANED.csv}" \
		--data-6g "$${DATA_6G_PATH:-../MoE/AIoT_6G_CLEANED.csv}"

serve:
	uvicorn services.inference.main:app --host 0.0.0.0 --port 8000 --reload

serve-training:
	uvicorn services.training.main:app --host 0.0.0.0 --port 8010 --reload

serve-monitoring:
	uvicorn services.monitoring.main:app --host 0.0.0.0 --port 8011 --reload

demo-batch:
	@echo "Posting sample 5G CSV to batch endpoint..."
	curl -s -F "file=@tests/fixtures/sample_5g_10rows.csv" \
		http://localhost:8000/predict/batch | python -m json.tool

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage dist build