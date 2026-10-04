#!/usr/bin/env python3
"""Download the historical Dublin Bikes station csv files from data.gov.ie.
"""

import json
import shutil
from pathlib import Path
from urllib.request import urlopen

CATALOGUE_URL = "https://data.gov.ie/api/3/action/package_show?id=dublinbikes-api"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "datasets" / "raw"

FILE_PATTERNS = ["dublinbike-historical-data-", "dublin-bikes_station_status_"]

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    resources = json.load(urlopen(CATALOGUE_URL, timeout=60))["result"]["resources"]
    urls = [r["url"] for r in resources if any(p in r["url"] for p in FILE_PATTERNS)]

    for url in urls:
        path = OUTPUT_DIR / url.rsplit("/", 1)[-1]
        if path.exists():
            print(f"skip      {path.name}")
            continue

        print(f"download  {path.name}")
        part = path.with_suffix(".part")

        with urlopen(url, timeout=120) as response, open(part, "wb") as file:
            shutil.copyfileobj(response, file)
        part.rename(path)


if __name__ == "__main__":
    main()
