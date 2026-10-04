#!/usr/bin/env python3
"""Load the GBFS station status csvs from Google cloud Storage into a BigQuery table. """

import sys
from pathlib import Path

from google.api_core.exceptions import NotFound
from google.cloud import bigquery

sys.path.insert(0, str(Path(__file__).resolve().parent))
import logs

PROJECT = "setu-dhi-03"
LOCATION = "europe-west1"  
DATASET = "dublinbikes"
TABLE = f"{PROJECT}.{DATASET}.station_status_raw"
SOURCE_URI = "gs://setu-dhi-03-dublinbikes-raw/raw/dublin-bikes_station_status_*.csv"

SCHEMA = [
    bigquery.SchemaField("system_id", "STRING"),
    bigquery.SchemaField("last_reported", "TIMESTAMP"),
    bigquery.SchemaField("station_id", "STRING"),
    bigquery.SchemaField("num_bikes_available", "INTEGER"),
    bigquery.SchemaField("num_docks_available", "INTEGER"),
    bigquery.SchemaField("is_installed", "BOOLEAN"),
    bigquery.SchemaField("is_renting", "BOOLEAN"),
    bigquery.SchemaField("is_returning", "BOOLEAN"),
    bigquery.SchemaField("name", "STRING"),
    bigquery.SchemaField("short_name", "STRING"),
    bigquery.SchemaField("address", "STRING"),
    bigquery.SchemaField("lat", "FLOAT"),
    bigquery.SchemaField("lon", "FLOAT"),
    bigquery.SchemaField("region_id", "STRING"),
    bigquery.SchemaField("capacity", "INTEGER"),
]


def main():
    log = logs.setup("02-b-load-bigquery")
    client = bigquery.Client(project=PROJECT, location=LOCATION)

    dataset = bigquery.Dataset(f"{PROJECT}.{DATASET}")
    dataset.location = LOCATION
    client.create_dataset(dataset, exists_ok=True)

    config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        schema=SCHEMA,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )

    log.info("loading %s into %s", SOURCE_URI, TABLE)
    job = None
    try:
        job = client.load_table_from_uri(SOURCE_URI, TABLE, job_config=config)
        job.result()
    except Exception as exc:
        logs.log_failure("02-b-load-bigquery", error_class=type(exc).__name__, message=str(exc), source=SOURCE_URI)
        log.error("load failed: %s: %s", type(exc).__name__, exc)
        for err in (job.errors if job else None) or []:
            log.error("  %s", err)
        sys.exit(1)

    rows = client.get_table(TABLE).num_rows
    log.info("loaded %s rows into %s", f"{rows:,}", TABLE)


if __name__ == "__main__":
    main()
