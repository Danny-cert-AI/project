#!/usr/bin/env python3
""" Check the sha hashes of each file """
import subprocess

subprocess.run(["shasum", "-a", "256", "-c", "../raw.sha256"], cwd="datasets/raw", check=True)
