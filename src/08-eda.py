#!/usr/bin/env python3
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from google.cloud import bigquery

sys.path.insert(0, str(Path(__file__).resolve().parent))
import logs

NAME = "08-eda"
TABLE = "`setu-dhi-03.dublinbikes.station_status_features`"
SPLIT_TABLE = "`setu-dhi-03.dublinbikes.station_status_split`"
IMG_DIR = Path(__file__).resolve().parent.parent / "images" / "eda"

BLUE, ORANGE = "#2a6f97", "#e07a5f"

# (alias, expression, percentile) -> APPROX_QUANTILES(expression, 100)[OFFSET(percentile)]
OCCUPANCY = "SAFE_DIVIDE(num_bikes_available, capacity)"
QUANTILES = [
    ("bikes_min", "num_bikes_available", 0), ("bikes_p05", "num_bikes_available", 5),
    ("bikes_p50", "num_bikes_available", 50), ("bikes_p95", "num_bikes_available", 95),
    ("bikes_max", "num_bikes_available", 100),
    ("cap_min", "capacity", 0), ("cap_p50", "capacity", 50), ("cap_max", "capacity", 100),
    ("occ_p05", OCCUPANCY, 5), ("occ_p50", OCCUPANCY, 50), ("occ_p95", OCCUPANCY, 95),
    ("std60_p50", "bikes_std_60min", 50), ("std60_p95", "bikes_std_60min", 95),
    ("dist_p50", "metres_from_centre", 50), ("dist_max", "metres_from_centre", 100),
]


def query(client, sql):
    return client.query(sql).result().to_dataframe()


def save(fig, name, log):
    fig.tight_layout()
    fig.savefig(IMG_DIR / name, dpi=130)
    plt.close(fig)
    log.info("saved %s", name)


def quantiles(client, log):
    cols = ",\n".join(
        f"APPROX_QUANTILES({expr}, 100)[OFFSET({pct})] AS {alias}" for alias, expr, pct in QUANTILES
    )
    row = query(client, f"SELECT\n{cols}\nFROM {TABLE}").iloc[0]
    log.info("quantiles: %s", {k: round(float(v), 2) for k, v in row.items()})


def bikes_histogram(client, log):
    data = query(client, f"""
    SELECT CAST(num_bikes_available AS INT64) AS bikes, COUNT(*) AS n
    FROM {TABLE}
    WHERE num_bikes_available BETWEEN 0 AND 40
    GROUP BY bikes ORDER BY bikes
    """)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(data["bikes"], data["n"], color=BLUE)
    ax.set(xlabel="bikes available at a station (clipped to 0-40)", ylabel="reading count",
           title="Distribution of bikes available per reading")
    save(fig, "bikes_available_hist.png", log)


def target_by_hour(client, log):
    data = query(client, f"""
    SELECT hour, is_weekend,
           AVG(CAST(empty_t_plus_30 AS INT64)) AS empty_rate,
           AVG(num_bikes_available) AS mean_bikes
    FROM {TABLE}
    GROUP BY hour, is_weekend ORDER BY hour, is_weekend
    """)
    data["empty_pct"] = data["empty_rate"] * 100
    panels = [
        ("mean_bikes", "Mean bikes available by hour", "mean bikes available"),
        ("empty_pct", "P(station empty at t+30) by hour", "% readings empty 30 min later"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, (column, title, ylabel) in zip(axes, panels):
        for is_weekend, label, colour in [(False, "weekday", BLUE), (True, "weekend", ORANGE)]:
            sub = data[data["is_weekend"] == is_weekend]
            ax.plot(sub["hour"], sub[column], label=label, color=colour)
        ax.set(title=title, xlabel="hour (Europe/Dublin)", ylabel=ylabel)
        ax.legend()
    save(fig, "target_by_hour.png", log)
    peak = data[~data["is_weekend"]].nlargest(1, "empty_rate").iloc[0]
    log.info("weekday peak empty rate %.1f%% at hour %d", peak["empty_pct"], peak["hour"])


def station_level(client, log):
    data = query(client, f"""
    SELECT station_id, ANY_VALUE(lat) AS lat, ANY_VALUE(lon) AS lon,
           ANY_VALUE(capacity) AS capacity,
           AVG(CAST(empty_t_plus_30 AS INT64)) AS empty_rate
    FROM {TABLE}
    GROUP BY station_id
    """)
    fig, ax = plt.subplots(figsize=(6, 6))
    sca = ax.scatter(data["lon"], data["lat"], c=data["empty_rate"] * 100, cmap="OrRd",
                     s=data["capacity"] * 1.5, alpha=0.8, edgecolors="grey", linewidths=0.3)
    fig.colorbar(sca, ax=ax).set_label("% readings empty at t+30")
    ax.set(xlabel="longitude", ylabel="latitude",
           title="Stations: location, capacity (size), empty-rate (colour)")
    save(fig, "station_map.png", log)
    log.info("%d stations, empty-rate range %.1f%%-%.1f%%",
             len(data), data["empty_rate"].min() * 100, data["empty_rate"].max() * 100)
    worst = data.nlargest(3, "empty_rate")[["station_id", "capacity", "empty_rate"]]
    log.info("stations with the highest empty_t_plus_30 rate:\n%s", worst.to_string(index=False))


def split_balance(client, log):
    data = query(client, f"""
    SELECT split, COUNT(*) AS n, AVG(CAST(empty_t_plus_30 AS INT64)) AS empty_rate
    FROM {SPLIT_TABLE}
    GROUP BY split
    """)
    log.info("target balance per split (cross-check against MILESTONE1.md splits table): %s",
             data.to_dict(orient="records"))


def main():
    log = logs.setup(NAME)
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    client = bigquery.Client(project="setu-dhi-03", location="europe-west1")

    for step in (quantiles, bikes_histogram, target_by_hour, station_level, split_balance):
        step(client, log)

    log.info("done; plots in %s", IMG_DIR)


if __name__ == "__main__":
    main()
