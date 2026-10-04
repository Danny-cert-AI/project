#!/usr/bin/env python3
"""Plan the shards of the split table: one shard per split per calendar month.

Split boundaries fall on month starts, so no shard spans two splits. Writes
logs/06-shard.manifest.json, which 07-store.py reads, and checks that the shard
row counts add up to the table's row count.

    ./src/06-shard.py
"""

import json
import sys
from pathlib import Path

from google.cloud import bigquery

sys.path.insert(0, str(Path(__file__).resolve().parent))
import logs

NAME = "06-shard"
PROJECT = "setu-dhi-03"
LOCATION = "europe-west1"
SPLIT = f"{PROJECT}.dublinbikes.station_status_split"
STORE = "gs://setu-dhi-03-dublinbikes-raw/processed"
MANIFEST = logs.LOG_DIR / "06-shard.manifest.json"

SHARDS = f"""SELECT split, FORMAT_TIMESTAMP('%Y-%m', last_reported) AS year_month, COUNT(*) AS rows_n
             FROM `{SPLIT}` GROUP BY 1, 2 ORDER BY MIN(last_reported)"""


def main():
    log = logs.setup(NAME)
    client = bigquery.Client(project=PROJECT, location=LOCATION)

    shards = [dict(r) for r in client.query(SHARDS).result()]
    for s in shards:
        s["uri"] = f"{STORE}/split={s['split']}/year_month={s['year_month']}/part-*.parquet"

    total = client.get_table(SPLIT).num_rows
    shard_rows = sum(s["rows_n"] for s in shards)
    smallest = min(shards, key=lambda s: s["rows_n"])
    largest = max(shards, key=lambda s: s["rows_n"])
    log.info("%s shards from %s rows in %s", len(shards), f"{shard_rows:,}", SPLIT)
    for split in ("train", "validate", "test"):
        log.info("  %-8s %s shards", split, sum(s["split"] == split for s in shards))
    log.info("smallest %s/%s %s rows; largest %s/%s %s rows",
             smallest["split"], smallest["year_month"], f"{smallest['rows_n']:,}",
             largest["split"], largest["year_month"], f"{largest['rows_n']:,}")

    if shard_rows != total:
        logs.log_failure(NAME, check="row_total", expected=total, got=shard_rows)
        log.error("shard rows %s != table rows %s", f"{shard_rows:,}", f"{total:,}")
        sys.exit(1)

    MANIFEST.parent.mkdir(exist_ok=True)
    MANIFEST.write_text(json.dumps(shards, indent=1) + "\n")
    log.info("wrote %s", MANIFEST)


if __name__ == "__main__":
    main()
