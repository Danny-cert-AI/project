#!/usr/bin/env python3
"""Filter invalid rows out of the raw station status table into a clean table.

A row is dropped when any of these rules fails:
  - capacity: num_bikes_available + num_docks_available must equal capacity
  - status:   is_installed, is_renting and is_returning must all be true
  - duplicate: only the first row per (station_id, last_reported) is kept

The raw table is never modified; the clean table is rebuilt from it on every run.

"""

import sys
from pathlib import Path

from google.cloud import bigquery

sys.path.insert(0, str(Path(__file__).resolve().parent))
import logs

NAME = "03-filter"
PROJECT = "setu-dhi-03"
LOCATION = "europe-west1"
RAW = f"`{PROJECT}.dublinbikes.station_status_raw`"
CLEAN = f"`{PROJECT}.dublinbikes.station_status_clean`"

CAPACITY_FAILS = "COALESCE(num_bikes_available + num_docks_available != capacity, TRUE)"
STATUS_FAILS = "NOT COALESCE(is_installed AND is_renting AND is_returning, FALSE)"
DUPLICATE_FAILS = "ROW_NUMBER() OVER (PARTITION BY station_id, last_reported ORDER BY name) > 1"

def rule_counts_sql(table):
    return f"""WITH r AS (
                 SELECT {CAPACITY_FAILS} AS capacity, {STATUS_FAILS} AS status,
                        {DUPLICATE_FAILS} AS duplicate
                 FROM {table})
               SELECT COUNT(*) AS rows_in,
                      COUNTIF(capacity) AS capacity_fails,
                      COUNTIF(status) AS status_fails,
                      COUNTIF(duplicate) AS duplicate_fails,
                      COUNTIF(CAST(capacity AS INT64) + CAST(status AS INT64) + CAST(duplicate AS INT64) > 1)
                          AS fails_more_than_one_rule,
                      COUNTIF(NOT (capacity OR status OR duplicate)) AS rows_kept
               FROM r"""


EXAMPLES = {
    "capacity_fails": f"SELECT * FROM {RAW} WHERE {CAPACITY_FAILS} LIMIT 3",
    "status_fails": f"SELECT * FROM {RAW} WHERE {STATUS_FAILS} LIMIT 3",
    "duplicate_fails": f"SELECT * FROM {RAW} QUALIFY {DUPLICATE_FAILS} LIMIT 3",
}

BUILD = f"""CREATE OR REPLACE TABLE {CLEAN}
            PARTITION BY DATE_TRUNC(last_reported, MONTH)
            CLUSTER BY station_id AS
            SELECT * EXCEPT (fails_capacity, fails_status, fails_duplicate)
            FROM (SELECT *, {CAPACITY_FAILS} AS fails_capacity, {STATUS_FAILS} AS fails_status,
                         {DUPLICATE_FAILS} AS fails_duplicate
                  FROM {RAW})
            WHERE NOT (fails_capacity OR fails_status OR fails_duplicate)"""


def rows(client, sql):
    return [dict(r) for r in client.query(sql).result()]


def main():
    log = logs.setup(NAME)
    client = bigquery.Client(project=PROJECT, location=LOCATION)

    before = rows(client, rule_counts_sql(RAW))[0]
    total = before["rows_in"]
    log.info("raw: %s", {k: f"{v:,}" for k, v in before.items()})
    log.info("dropping %s of %s rows (%.2f%%)", f"{total - before['rows_kept']:,}", f"{total:,}",
             100 * (total - before["rows_kept"]) / total)

    for check, sql in EXAMPLES.items():
        if before[check]:
            examples = [{k: str(v) for k, v in r.items()} for r in rows(client, sql)]
            logs.log_failure(NAME, check=check, count=before[check],
                             share_of_rows=round(before[check] / total, 4), examples=examples)

    log.info("building %s", CLEAN)
    try:
        client.query(BUILD).result()
    except Exception as exc:
        logs.log_failure(NAME, check="build", error_class=type(exc).__name__, message=str(exc))
        log.error("build failed: %s: %s", type(exc).__name__, exc)
        sys.exit(1)

    after = rows(client, rule_counts_sql(CLEAN))[0]
    log.info("clean: %s", {k: f"{v:,}" for k, v in after.items()})
    problems = {k: v for k, v in after.items() if k.endswith("_fails") and v}
    if after["rows_in"] != before["rows_kept"]:
        problems["row_count_mismatch"] = {"expected": before["rows_kept"], "got": after["rows_in"]}
    if problems:
        logs.log_failure(NAME, check="clean_table_check", problems=problems)
        log.error("clean table check failed: %s", problems)
        sys.exit(1)

    log.info("check passed: %s rows in %s, no rule failures", f"{after['rows_in']:,}", CLEAN)
    log.info("done; per-rule detail in %s", logs.failure_path(NAME))


if __name__ == "__main__":
    main()
