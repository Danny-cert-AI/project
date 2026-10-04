"""Logging helpers: an operator log and a JSONL failure log, both under logs/.

The files are additive: stdout output is unchanged. If a log file cannot be
opened, the job carries on without it.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
MAX_BYTES = 5_000_000
BACKUPS = 3


def setup(name):
    """Return a logger writing to stdout and to logs/<name>.log."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    logger.addHandler(stream)

    try:
        LOG_DIR.mkdir(exist_ok=True)
        handler = RotatingFileHandler(LOG_DIR / f"{name}.log", maxBytes=MAX_BYTES, backupCount=BACKUPS)
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    except OSError as exc:
        logger.warning("operator log file unavailable: %s: %s", type(exc).__name__, exc)
    return logger


def failure_path(name):
    return LOG_DIR / f"{name}.failures.jsonl"


def log_failure(name, **fields):
    """Append one failure record (exception class and message, item id, and so on)."""
    record = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **fields}
    try:
        LOG_DIR.mkdir(exist_ok=True)
        with open(failure_path(name), "a") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError:
        pass
