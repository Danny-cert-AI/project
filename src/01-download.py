#!/usr/bin/env python3
"""Download the historical Dublin Bikes station CSV files from data.gov.ie.
"""

from pathlib import Path
import requests

CATALOGUE_URL = "https://data.gov.ie/api/3/action/package_show?id=dublinbikes-api"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "datasets" / "raw"

FILE_PATTERNS = ["dublinbike-historical-data-", "dublin-bikes_station_status_"]

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    catalogue = requests.get(CATALOGUE_URL, timeout=60).json()
    urls = [r["url"] for r in catalogue["result"]["resources"]]
    urls = [u for u in urls if any(p in u for p in FILE_PATTERNS)]

    for url in urls:
        path = OUTPUT_DIR / url.rsplit("/", 1)[-1]
        if path.exists():
            print(f"skip      {path.name}")
            continue

        print(f"download  {path.name}")
        with requests.get(url, stream=True, timeout=120) as response:
            response.raise_for_status()
            with open(path, "wb") as file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    file.write(chunk)


if __name__ == "__main__":
    main()
