# Data Handling and Infrastructure — Dublin Bikes Pipeline

Assignment project for the SETU "Data Handling and Infrastructure" module.
The goal is to take the Dublin Bikes historical dataset end-to-end — raw
data, through a data pipeline, to a ML model — across four milestones, each building on the one before.

## Setup

Run once, from the project root:
```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Activate the venv (`source .venv/bin/activate`) before running any script.
Deactivate with `deactivate` when done. `.venv/` is gitignored.

## Project layout

- `src/` — numbered pipeline scripts, run in order from the project root (letters split a step into sub-steps):
  - [`src/01-a-download.py`](src/01-a-download.py) — download the raw CSVs from data.gov.ie
  - [`src/01-b-verify.py`](src/01-b-verify.py) — check the SHA256 of each raw file
  - [`src/02-a-upload.py`](src/02-a-upload.py) — upload the raw CSVs to Cloud Storage
  - [`src/02-b-load-bigquery.py`](src/02-b-load-bigquery.py) — load the station status CSVs into BigQuery
  - [`src/02-c-profile.py`](src/02-c-profile.py) — data quality checks on the raw BigQuery table
  - [`src/03-filter.py`](src/03-filter.py) — remove invalid rows into a clean BigQuery table
  - [`src/04-features.py`](src/04-features.py) — build the feature table (targets, rolling, calendar, station)
  - [`src/05-splits.py`](src/05-splits.py) — split the feature table by date into train, validate and test
  - [`src/06-shard.py`](src/06-shard.py) — plan one shard per split per month
  - [`src/07-store.py`](src/07-store.py) — export each shard as Parquet to Cloud Storage and check it reads back
  - [`src/logs.py`](src/logs.py) — shared logging helper, imported by the scripts above
- `datasets/` — downloaded and processed data (gitignored)
- `images/` — screenshots referenced markdown files.
- `logs/` — operator and failure logs written by the scripts (gitignored)

## Milestone write-ups

One per milestone, documenting what each pipeline stage does and how to run it:

- [MILESTONE1.md](MILESTONE1.md) — Data source, task, splits, and storage
- MILESTONE2.md — Data analysis and data pipeline *(not yet written)*
- MILESTONE3.md — ML pipeline, MLOps, and first models *(not yet written)*
- MILESTONE4.md — Scalable inference and continued deployment *(not yet written)*

