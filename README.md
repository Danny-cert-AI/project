# Assignment pipeline

Running notes on what each numbered script in `src/` does and how to run it,
mapped to the M1 deliverables in `docs/01 Assignments.pdf` and
`docs/M1_Implementation_Plan.md`. One section per script, added as each is built.

## Setup (venv)

Run once, from the project root:
```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Activate the venv (`source .venv/bin/activate`) before running any script
below. Deactivate with `deactivate` when done. `.venv/` is gitignored.

## 01 — Download (`src/01-download.py`)

**Purpose**: pull the historical Dublin Bikes station CSVs from data.gov.ie.

**What it does**:
- Queries the CKAN catalogue: `package_show?id=dublinbikes-api`.
- Filters the resource list to files matching `dublinbike-historical-data-*` and
  `dublin-bikes_station_status_*`.
- Streams each matching file to `datasets/raw/` (relative to the project root),
  skipping any file already downloaded.

**Run**:
```sh
python3 src/01-download.py
```

**Requirements**: `requests` (see `requirements.txt`).

**Output**: raw CSVs land in `datasets/raw/` (gitignored). Re-running is
idempotent — already-downloaded files are skipped, not re-fetched.

**Not yet handled here** (see `docs/M1_Implementation_Plan.md` for the fuller
design): GCS upload, `raw_files` manifest tracking, resumability beyond "file
already exists on disk".

## Verifying raw files

`datasets/raw.sha256` records the SHA256 of each downloaded file. It is in the
standard `shasum` format, so no custom tooling is needed:

```sh
make verify   # recompute and compare against the manifest
make hash     # regenerate the manifest from the files on disk
```

`verify` only checks files listed in the manifest; it will not flag new or
extra files. Run it from the project root with the venv active, and note it
hashes the full ~2.4GB set.

## 02 — Storage

*Not yet implemented.* Upload raw files to GCS (`setu-dhi-03-dublinbikes-raw`
bucket) and record the `raw_files` manifest in MariaDB.

## 03 — Filtering

*Not yet implemented.* Drop rows with invalid values
(`num_bikes_available`/`num_docks_available` negative or inconsistent with
`capacity`) at load time.

## 04 — Feature extraction

*Not yet implemented.* Lag/rolling/calendar/station features and targets,
written to monthly Parquet shards (`build_features.py`).

## 05 — Train/dev/test splits

*Not yet implemented.* Chronological split boundaries and walk-forward CV
folds (`make_splits.py`).

## 06 — Sharding

*Not yet implemented.* Monthly station-partitioned Parquet output
(`data/features/dt=YYYY-MM/part.parquet`).

## 07 — Store preprocessed data

*Not yet implemented.* The feature Parquet shards from 06 are the
preprocessed/training-ready store.
