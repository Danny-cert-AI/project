#!/usr/bin/env python3
"""Split the feature table into train, validate and test by date.

The split is chronological so the model is always tested on data later than it
was trained on. Rows in the last 30 minutes before a boundary are dropped,
because their target lies in the next split. Boundaries are midnight UTC.

    ./src/05-splits.py
"""

import sys
from pathlib import Path

from google.cloud import bigquery

sys.path.insert(0, str(Path(__file__).resolve().parent))
import logs

NAME = "05-splits"
PROJECT = "setu-dhi-03"
LOCATION = "europe-west1"
FEATURES = f"`{PROJECT}.dublinbikes.station_status_features`"
SPLIT = f"`{PROJECT}.dublinbikes.station_status_split`"

HORIZON_MINUTES = 30  # must match 04-features.py
VALIDATE_START = "2026-01-01"
TEST_START = "2026-04-01"

SPLIT_OF = f"""CASE WHEN last_reported < TIMESTAMP '{VALIDATE_START}' THEN 'train'
                    WHEN last_reported < TIMESTAMP '{TEST_START}' THEN 'validate'
                    ELSE 'test' END"""
SPLIT_END = f"""CASE split WHEN 'train' THEN TIMESTAMP '{VALIDATE_START}'
                           WHEN 'validate' THEN TIMESTAMP '{TEST_START}' END"""


def target_crosses(boundary):
    return (f"last_reported >= TIMESTAMP_SUB(TIMESTAMP '{boundary}', INTERVAL {HORIZON_MINUTES} MINUTE) "
            f"AND last_reported < TIMESTAMP '{boundary}'")


BUILD = f"""CREATE OR REPLACE TABLE {SPLIT}
PARTITION BY DATE_TRUNC(last_reported, MONTH)
CLUSTER BY split, station_id AS
SELECT *, {SPLIT_OF} AS split
FROM {FEATURES}
WHERE NOT ({target_crosses(VALIDATE_START)})
  AND NOT ({target_crosses(TEST_START)})"""

STATS = f"""SELECT split, COUNT(*) AS rows_n,
                   MIN(last_reported) AS first_ts, MAX(last_reported) AS last_ts,
                   COUNT(DISTINCT station_id) AS stations,
                   COUNTIF(empty_t_plus_{HORIZON_MINUTES}) AS empty_targets,
                   COUNTIF(TIMESTAMP_ADD(last_reported, INTERVAL {HORIZON_MINUTES} MINUTE) >= {SPLIT_END})
                       AS targets_past_split_end
            FROM {SPLIT} GROUP BY split ORDER BY first_ts"""


def main():
    log = logs.setup(NAME)
    client = bigquery.Client(project=PROJECT, location=LOCATION)

    rows_in = client.get_table(FEATURES.strip("`")).num_rows
    log.info("building %s from %s rows in %s", SPLIT, f"{rows_in:,}", FEATURES)
    try:
        client.query(BUILD).result()
    except Exception as exc:
        logs.log_failure(NAME, check="build", error_class=type(exc).__name__, message=str(exc))
        log.error("build failed: %s: %s", type(exc).__name__, exc)
        sys.exit(1)

    splits = [dict(r) for r in client.query(STATS).result()]
    rows_out = sum(s["rows_n"] for s in splits)
    log.info("rows out %s; dropped %s whose target crosses a split boundary",
             f"{rows_out:,}", f"{rows_in - rows_out:,}")
    for s in splits:
        log.info("%-8s %s rows (%.2f%%), %s to %s, %s stations, empty at t+%s min %.2f%%",
                 s["split"], f"{s['rows_n']:,}", 100 * s["rows_n"] / rows_out, s["first_ts"], s["last_ts"],
                 s["stations"], HORIZON_MINUTES, 100 * s["empty_targets"] / s["rows_n"])

    problems = {}
    if [s["split"] for s in splits] != ["train", "validate", "test"]:
        problems["splits_found"] = [s["split"] for s in splits]
    if any(a["last_ts"] >= b["first_ts"] for a, b in zip(splits, splits[1:])):
        problems["overlapping_dates"] = True
    crossing = sum(s["targets_past_split_end"] for s in splits)
    if crossing:
        problems["targets_past_split_end"] = crossing
    if problems:
        logs.log_failure(NAME, check="split_check", problems=problems)
        log.error("split check failed: %s", problems)
        sys.exit(1)
    log.info("check passed: three splits, no overlapping dates, no target past its split's end")


if __name__ == "__main__":
    main()
