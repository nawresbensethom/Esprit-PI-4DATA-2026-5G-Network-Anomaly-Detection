"""
Prometheus metrics shared across MoE IDS microservices.

All metric objects are module-level singletons, so each service that imports
them exports its own `/metrics` endpoint with the same schema. Prometheus
scrapes each service independently — labels identify which service the
sample came from.
"""

from __future__ import annotations

from prometheus_client import REGISTRY, Counter, Gauge, Histogram, generate_latest

REQUEST_COUNT = Counter(
    "moe_ids_requests_total",
    "Total prediction requests",
    ["schema", "status"],
)

REQUEST_LATENCY = Histogram(
    "moe_ids_request_duration_seconds",
    "End-to-end request latency in seconds",
    ["schema"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

ROWS_PROCESSED = Counter(
    "moe_ids_rows_processed_total",
    "Total rows run through the model",
    ["schema"],
)

ATTACK_PREDICTIONS = Counter(
    "moe_ids_attack_predictions_total",
    "Total rows predicted as attack",
    ["schema"],
)

ATTACK_RATE_GAUGE = Gauge(
    "moe_ids_attack_rate_last_batch",
    "Attack rate (0-1) of the most recent batch",
    ["schema"],
)

MODEL_RELOAD_COUNT = Counter(
    "moe_ids_model_reloads_total",
    "Number of hot model reloads via /admin/reload",
)

TRAINING_RUNS = Counter(
    "moe_ids_training_runs_total",
    "Number of training runs triggered",
    ["status"],
)

DRIFT_CHECKS = Counter(
    "moe_ids_drift_checks_total",
    "Number of drift checks executed",
    ["result"],
)

LAST_DRIFT_PSI = Gauge(
    "moe_ids_last_drift_psi",
    "PSI of attack rate from the most recent drift check",
)


def prometheus_response() -> bytes:
    return generate_latest(REGISTRY)
