.PHONY: install test lint typecheck train serve clean demo-batch

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
	ruff check moe_ids/ scripts/ tests/

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
	uvicorn services.api.main:app --host 0.0.0.0 --port 8000 --reload

demo-batch:
	@echo "Posting sample 5G CSV to batch endpoint..."
	curl -s -F "file=@tests/fixtures/sample_5g_10rows.csv" \
		http://localhost:8000/predict/batch | python -m json.tool

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage dist build