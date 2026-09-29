#!/usr/bin/env python3
"""Verify the SHA256 checksums of the downloaded raw Dublin Bikes files.

The first run writes a manifest (datasets/raw.sha256) from whatever is on disk.
Every later run recomputes the checksums and compares them against that
manifest, reporting any file that is missing, extra or has changed.
"""

import argparse
import hashlib
import sys
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "datasets" / "raw"
MANIFEST = RAW_DIR.parent / "raw.sha256"

CHUNK_SIZE = 1024 * 1024


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path):
    checksums = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        checksum, name = line.split(None, 1)
        checksums[name.lstrip("*")] = checksum
    return checksums


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="write or refresh the manifest from the current files",
    )
    args = parser.parse_args()

    if not RAW_DIR.is_dir():
        sys.exit(f"raw directory not found: {RAW_DIR}")

    files = sorted(p for p in RAW_DIR.iterdir() if p.is_file())
    if not files:
        sys.exit(f"no files found in {RAW_DIR}")

    digests = {}
    for path in files:
        print(f"hash      {path.name}")
        digests[path.name] = sha256(path)

    if args.write or not MANIFEST.exists():
        if not args.write:
            print(f"manifest not found, writing {MANIFEST.name}")
        lines = [f"{digest}  {name}" for name, digest in sorted(digests.items())]
        MANIFEST.write_text("\n".join(lines) + "\n")
        print(f"wrote {len(lines)} checksums to {MANIFEST}")
        return

    expected = load_manifest(MANIFEST)
    ok = 0
    failed = 0

    for name, digest in sorted(digests.items()):
        if name not in expected:
            print(f"extra     {name}")
            failed += 1
        elif expected[name] != digest:
            print(f"MISMATCH  {name}")
            failed += 1
        else:
            ok += 1

    for name in sorted(set(expected) - set(digests)):
        print(f"missing   {name}")
        failed += 1

    print(f"\n{ok} ok, {failed} failed, {len(digests)} files checked")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
