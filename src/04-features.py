#!/usr/bin/env python3
"""Build the feature table from the clean station status table.

One row per station per reading. The targets are the bikes available exactly
30 minutes later and whether the station is empty then; rows with no reading at
t+30 are dropped. Every other column uses only the reading itself or earlier
readings. Stations usually report every 10 minutes, so a lag of k minutes is the
latest reading between k and k+10 minutes earlier; it is NULL when there is none.

    ./src/04-features.py
"""

import sys
from pathlib import Path

import holidays
from google.cloud import bigquery

sys.path.insert(0, str(Path(__file__).resolve().parent))
import logs

NAME = "04-features"
PROJECT = "setu-dhi-03"
LOCATION = "europe-west1"
CLEAN = f"`{PROJECT}.dublinbikes.station_status_clean`"
FEATURES = f"`{PROJECT}.dublinbikes.station_status_features`"

HORIZON_MINUTES = 30
LAG_MINUTES = [5, 10, 15, 30, 60, 180, 360, 720, 1440]
LAG_LOOKBACK_MINUTES = 10  # how much older than t-k a lag reading may be
ROLLING_MINUTES = [60, 360]
CITY_CENTRE = (-6.2591, 53.3473)  # O'Connell Bridge, (lon, lat)
HOLIDAYS = sorted(holidays.Ireland(years=range(2024, 2027)))

LAG_COLUMNS = [f"bikes_t_minus_{m}" for m in LAG_MINUTES]

LAGS = ",\n".join(
    f"LAST_VALUE(num_bikes_available) OVER (w RANGE BETWEEN {60 * (m + LAG_LOOKBACK_MINUTES)} PRECEDING "
    f"AND {60 * m} PRECEDING) AS bikes_t_minus_{m}"
    for m in LAG_MINUTES)
ROLLING = ",\n".join(
    f"{fn}(num_bikes_available) OVER (w RANGE BETWEEN {60 * m} PRECEDING AND CURRENT ROW) AS bikes_{name}_{m}min"
    for m in ROLLING_MINUTES for fn, name in [("AVG", "mean"), ("STDDEV", "std")])
HOLIDAY_DATES = ", ".join(f"DATE '{d}'" for d in HOLIDAYS)

BUILD = f"""CREATE OR REPLACE TABLE {FEATURES}
PARTITION BY DATE_TRUNC(last_reported, MONTH)
CLUSTER BY station_id AS
WITH f AS (
  SELECT station_id, last_reported, num_bikes_available, num_docks_available, capacity, lat, lon,
         MAX(num_bikes_available) OVER (w RANGE BETWEEN {60 * HORIZON_MINUTES} FOLLOWING
                                                  AND {60 * HORIZON_MINUTES} FOLLOWING) AS bikes_t_plus_{HORIZON_MINUTES},
         {LAGS},
         {ROLLING},
         DATETIME(last_reported, 'Europe/Dublin') AS local_time
  FROM {CLEAN}
  WINDOW w AS (PARTITION BY station_id ORDER BY UNIX_SECONDS(last_reported)))
SELECT * EXCEPT (local_time),
       bikes_t_plus_{HORIZON_MINUTES} = 0 AS empty_t_plus_{HORIZON_MINUTES},
       EXTRACT(HOUR FROM local_time) AS hour,
       EXTRACT(DAYOFWEEK FROM local_time) AS day_of_week,  -- 1 = Sunday
       EXTRACT(DAYOFWEEK FROM local_time) IN (1, 7) AS is_weekend,
       EXTRACT(MONTH FROM local_time) AS month,
       DATE(local_time) IN ({HOLIDAY_DATES}) AS is_public_holiday,
       ST_DISTANCE(ST_GEOGPOINT(lon, lat), ST_GEOGPOINT{CITY_CENTRE}) AS metres_from_centre
FROM f
WHERE bikes_t_plus_{HORIZON_MINUTES} IS NOT NULL"""

STATS = f"""SELECT COUNT(*) AS rows_out,
                   COUNTIF(bikes_t_plus_{HORIZON_MINUTES} IS NULL) AS null_targets,
                   COUNTIF(empty_t_plus_{HORIZON_MINUTES}) AS empty_targets,
                   COUNTIF({' AND '.join(f'{c} IS NOT NULL' for c in LAG_COLUMNS)}) AS rows_with_every_lag,
                   {', '.join(f'COUNTIF({c} IS NULL) AS {c}_nulls' for c in LAG_COLUMNS)}
            FROM {FEATURES}"""


def main():
    log = logs.setup(NAME)
    client = bigquery.Client(project=PROJECT, location=LOCATION)

    rows_in = client.get_table(CLEAN.strip("`")).num_rows
    log.info("building %s from %s rows in %s", FEATURES, f"{rows_in:,}", CLEAN)
    try:
        client.query(BUILD).result()
    except Exception as exc:
        logs.log_failure(NAME, check="build", error_class=type(exc).__name__, message=str(exc))
        log.error("build failed: %s: %s", type(exc).__name__, exc)
        sys.exit(1)

    stats = dict(next(iter(client.query(STATS).result())))
    rows_out = stats["rows_out"]
    log.info("rows out %s; dropped %s with no reading at t+%s min",
             f"{rows_out:,}", f"{rows_in - rows_out:,}", HORIZON_MINUTES)
    log.info("empty at t+%s min: %s (%.2f%%)", HORIZON_MINUTES, f"{stats['empty_targets']:,}",
             100 * stats["empty_targets"] / rows_out)
    log.info("rows with every lag present: %s (%.2f%%)", f"{stats['rows_with_every_lag']:,}",
             100 * stats["rows_with_every_lag"] / rows_out)
    for c in LAG_COLUMNS:
        log.info("  %-20s missing %s (%.2f%%)", c, f"{stats[c + '_nulls']:,}", 100 * stats[c + "_nulls"] / rows_out)

    if stats["null_targets"]:
        logs.log_failure(NAME, check="null_targets", count=stats["null_targets"])
        log.error("%s rows have no target", f"{stats['null_targets']:,}")
        sys.exit(1)
    log.info("done")


if __name__ == "__main__":
    main()
