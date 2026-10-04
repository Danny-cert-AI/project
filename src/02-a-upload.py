#!/usr/bin/env python3
""" Upload the raw csvs to the bucket """
import subprocess

subprocess.run(["gcloud", "storage", "rsync", "--checksums-only",
                "datasets/raw", "gs://setu-dhi-03-dublinbikes-raw/raw"], check=True)
