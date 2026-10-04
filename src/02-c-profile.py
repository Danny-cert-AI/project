#!/usr/bin/env python3
"""Profile data quality of the BigQuery station status table (read-only).

Nothing is cleaned or changed here; this is the evidence that the raw data is
imperfect. 
"""

import sys
from pathlib import Path
from google.cloud import bigquery

sys.path.insert(0, str(Path(__file__).resolve().parent))
import logs

NAME = "02-c-profile"
TABLE = "`setu-dhi-03.dublinbikes.station_status_raw`"
MIN_SAMPLES = 10_000
EXPECTED_FIRST_MONTH = "2024-05-01"
EXPECTED_LAST_MONTH = "2026-06-01"
GAP_MINUTES = 15  

# per-station minutes since the previous reading
GAPS = f"""WITH g AS (
  SELECT station_id, last_reported,
         TIMESTAMP_DIFF(last_reported, LAG(last_reported) OVER (PARTITION BY station_id ORDER BY last_reported), MINUTE) AS gap
  FROM {TABLE})"""

# (check name, SQL returning one row of counts, SQL returning example rows or None)
CHECKS = [
    ("null_values",
     f"""SELECT COUNTIF(last_reported IS NULL) AS null_ts,
                COUNTIF(station_id IS NULL) AS null_station,
                COUNTIF(num_bikes_available IS NULL) AS null_bikes,
                COUNTIF(num_docks_available IS NULL) AS null_docks,
                COUNTIF(capacity IS NULL) AS null_capacity
         FROM {TABLE}""", None),
    ("negative_counts",
     f"""SELECT COUNTIF(num_bikes_available < 0) AS negative_bikes,
                COUNTIF(num_docks_available < 0) AS negative_docks
         FROM {TABLE}""",
     f"SELECT * FROM {TABLE} WHERE num_bikes_available < 0 OR num_docks_available < 0 LIMIT 3"),
    ("bikes_plus_docks_vs_capacity",
     f"""SELECT COUNTIF(num_bikes_available + num_docks_available != capacity) AS mismatch_any,
                COUNTIF(ABS(num_bikes_available + num_docks_available - capacity) > 10) AS mismatch_over_10,
                COUNTIF(num_bikes_available + num_docks_available = 0) AS bikes_and_docks_both_zero
         FROM {TABLE}""",
     f"""SELECT * FROM {TABLE}
         WHERE ABS(num_bikes_available + num_docks_available - capacity) > 10 LIMIT 3"""),
    ("missing_months",
     f"""SELECT COUNT(*) AS missing_months, STRING_AGG(FORMAT_DATE('%Y-%m', m)) AS which
         FROM UNNEST(GENERATE_DATE_ARRAY(DATE '{EXPECTED_FIRST_MONTH}', DATE '{EXPECTED_LAST_MONTH}', INTERVAL 1 MONTH)) AS m
         WHERE m NOT IN (SELECT DISTINCT DATE_TRUNC(DATE(last_reported), MONTH) FROM {TABLE})""", None),
    # a month can be present but mostly empty, so check every day between the first and last reading (UTC)
    ("missing_days",
     f"""WITH days AS (SELECT DISTINCT DATE(last_reported) AS d FROM {TABLE})
         SELECT COUNT(*) AS missing_days, STRING_AGG(FORMAT_DATE('%Y-%m-%d', d) ORDER BY d) AS which
         FROM UNNEST(GENERATE_DATE_ARRAY((SELECT MIN(d) FROM days), (SELECT MAX(d) FROM days))) AS d
         WHERE d NOT IN (SELECT d FROM days)""", None),
    ("station_sampling_gaps",
     f"""{GAPS}
         SELECT COUNTIF(gap > {GAP_MINUTES}) AS gaps_over_{GAP_MINUTES}_min,
                MAX(gap) AS longest_gap_minutes,
                APPROX_QUANTILES(gap, 100)[OFFSET(50)] AS median_gap_minutes
         FROM g""",
     f"""{GAPS}
         SELECT station_id, last_reported, gap AS gap_minutes FROM g ORDER BY gap DESC LIMIT 3"""),
]

OVERVIEW = f"""SELECT COUNT(*) AS rows_total, COUNT(DISTINCT station_id) AS stations,
                      MIN(last_reported) AS first_reported, MAX(last_reported) AS last_reported
               FROM {TABLE}"""


def rows(client, sql):
    return [dict(r) for r in client.query(sql).result()]


def main():
    log = logs.setup(NAME)
    client = bigquery.Client(project="setu-dhi-03", location="europe-west1")

    overview = rows(client, OVERVIEW)[0]
    log.info("overview: %s", overview)
    total = overview["rows_total"]
    log.info("learning samples %s vs minimum %s: %s", f"{total:,}", f"{MIN_SAMPLES:,}",
             "OK" if total >= MIN_SAMPLES else "TOO FEW")

    for name, count_sql, example_sql in CHECKS:
        try:
            result = rows(client, count_sql)[0]
        except Exception as exc:
            logs.log_failure(NAME, check=name, error_class=type(exc).__name__, message=str(exc))
            log.error("%s: query failed: %s: %s", name, type(exc).__name__, exc)
            continue
        log.info("%s: %s", name, result)
        # every numeric count except summary statistics is a problem count when non-zero
        problems = {k: v for k, v in result.items()
                    if isinstance(v, int) and v and not k.startswith(("median", "longest"))}
        if problems:
            examples = [{k: str(v) for k, v in r.items()} for r in rows(client, example_sql)] if example_sql else []
            details = {k: v for k, v in result.items() if isinstance(v, str)}  # for example the list of missing dates
            logs.log_failure(NAME, check=name, counts=problems, examples=examples, details=details, share_of_rows=
                             {k: round(v / total, 4) for k, v in problems.items()})

    log.info("done; per-check detail in %s", logs.failure_path(NAME))


if __name__ == "__main__":
    main()
