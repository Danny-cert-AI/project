#!/usr/bin/env python3
"""Store each shard from 06-shard.py as Parquet files in Cloud Storage.

Layout: gs://setu-dhi-03-dublinbikes-raw/processed/split=<split>/year_month=<YYYY-MM>/
The split is in the folder name, so it is left out of the files. Each shard's
folder is emptied before its export, because EXPORT DATA's overwrite only
replaces files with the same names and a rerun can write a different number.
Afterwards an external table over the files is counted per split and must
match the split table.

    ./src/07-store.py
"""

import json
import subprocess
import sys
from pathlib import Path

from google.cloud import bigquery

sys.path.insert(0, str(Path(__file__).resolve().parent))
import logs

NAME = "07-store"
PROJECT = "setu-dhi-03"
LOCATION = "europe-west1"
SPLIT = f"`{PROJECT}.dublinbikes.station_status_split`"
STORED = f"`{PROJECT}.dublinbikes.station_status_processed`"
STORE = "gs://setu-dhi-03-dublinbikes-raw/processed"
MANIFEST = logs.LOG_DIR / "06-shard.manifest.json"

EXPORT = """EXPORT DATA OPTIONS (uri = '{uri}', format = 'PARQUET', overwrite = true) AS
SELECT * EXCEPT (split) FROM {table}
WHERE split = '{split}' AND FORMAT_TIMESTAMP('%Y-%m', last_reported) = '{year_month}'
ORDER BY station_id, last_reported"""  # sorting makes BigQuery write one file instead of dozens of empty ones

READ_BACK = f"""CREATE OR REPLACE EXTERNAL TABLE {STORED}
WITH PARTITION COLUMNS (split STRING, year_month STRING)
OPTIONS (format = 'PARQUET', uris = ['{STORE}/*'], hive_partition_uri_prefix = '{STORE}')"""

COUNTS = "SELECT split, COUNT(*) AS rows_n FROM {table} GROUP BY split"


def counts(client, table):
    return {r["split"]: r["rows_n"] for r in client.query(COUNTS.format(table=table)).result()}


def main():
    log = logs.setup(NAME)
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    shards = json.loads(MANIFEST.read_text())

    failed = 0
    for n, s in enumerate(shards, 1):
        folder = s["uri"].rsplit("/", 1)[0]
        # "matched no objects" on a first run is expected; leftovers are caught by the read-back check
        subprocess.run(["gcloud", "storage", "rm", "--quiet", f"{folder}/**"], capture_output=True)
        try:
            client.query(EXPORT.format(table=SPLIT, **s)).result()
        except Exception as exc:
            failed += 1
            logs.log_failure(NAME, check="export", shard=f"{s['split']}/{s['year_month']}",
                             error_class=type(exc).__name__, message=str(exc))
            log.error("%s/%s export failed: %s: %s", s["split"], s["year_month"], type(exc).__name__, exc)
            continue
        log.info("%s/%s shards done (%s/%s, %s rows)", n, len(shards), s["split"], s["year_month"],
                 f"{s['rows_n']:,}")
    if failed:
        log.error("%s of %s shards failed", failed, len(shards))
        sys.exit(1)

    client.query(READ_BACK).result()
    stored, expected = counts(client, STORED), counts(client, SPLIT)
    for split in ("train", "validate", "test"):
        log.info("  %-8s stored %s rows, split table %s", split,
                 f"{stored.get(split, 0):,}", f"{expected.get(split, 0):,}")
    if stored != expected:
        logs.log_failure(NAME, check="read_back", stored=stored, expected=expected)
        log.error("stored row counts do not match the split table")
        sys.exit(1)
    log.info("check passed: Parquet files in %s match %s", STORE, SPLIT)


if __name__ == "__main__":
    main()
