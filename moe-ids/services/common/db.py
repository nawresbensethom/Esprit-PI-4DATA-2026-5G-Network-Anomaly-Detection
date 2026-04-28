"""
PostgreSQL prediction log writer. Used by the inference service to persist
one row per batch request, and by the monitoring service to read them back
for drift analysis.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

_conn_lock = threading.Lock()
_conn: Any = None

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS prediction_log (
    id              SERIAL PRIMARY KEY,
    request_id      TEXT        NOT NULL,
    ts              TIMESTAMPTZ NOT NULL DEFAULT now(),
    model_version   TEXT,
    schema          TEXT,
    n_rows          INTEGER,
    n_attack        INTEGER,
    n_benign        INTEGER,
    mean_probability FLOAT,
    attack_rate     FLOAT
);
"""

INSERT_SQL = """
INSERT INTO prediction_log
    (request_id, model_version, schema, n_rows, n_attack, n_benign, mean_probability, attack_rate)
VALUES
    (%(request_id)s, %(model_version)s, %(schema)s, %(n_rows)s,
     %(n_attack)s, %(n_benign)s, %(mean_probability)s, %(attack_rate)s);
"""


def _get_conn(db_url: str) -> Any:
    global _conn
    try:
        import psycopg2

        with _conn_lock:
            if _conn is None or _conn.closed:
                _conn = psycopg2.connect(db_url)
                _conn.autocommit = True
                with _conn.cursor() as cur:
                    cur.execute(CREATE_TABLE_SQL)
    except Exception as exc:
        logger.warning("DB unavailable, prediction logging disabled: %s", exc)
        _conn = None
    return _conn


def log_prediction(db_url: str | None, record: dict) -> None:
    if not db_url:
        return
    try:
        conn = _get_conn(db_url)
        if conn is None:
            return
        with conn.cursor() as cur:
            cur.execute(INSERT_SQL, record)
    except Exception as exc:
        logger.debug("Failed to write prediction log to DB: %s", exc)
        global _conn
        _conn = None


def read_recent_predictions(db_url: str | None, window_days: int = 7) -> list[dict]:
    """Read prediction_log rows from the last N days — used by monitoring."""
    if not db_url:
        return []
    try:
        conn = _get_conn(db_url)
        if conn is None:
            return []
        with conn.cursor() as cur:
            cur.execute(
                "SELECT request_id, ts, model_version, schema, n_rows, n_attack, "
                "n_benign, mean_probability, attack_rate "
                "FROM prediction_log "
                "WHERE ts >= now() - (%s || ' days')::interval "
                "ORDER BY ts DESC",
                (str(window_days),),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as exc:
        logger.debug("Failed to read prediction log: %s", exc)
        return []
