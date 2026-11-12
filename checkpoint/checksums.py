"""Checksums of the data that this repository does not publish.

Patient-level tables (the analysis-ready package and the benchmark cohorts) are rebuilt locally from
the open GDC files. The SHA-256 of each rebuilt file is compared with the value recorded when the
benchmark version was frozen, so anyone can confirm they are working with identical data.
"""
import gzip
import hashlib
import json
import os


def digest(path):
    opener = gzip.open if path.endswith(".gz") else open   # hash the content, not the gzip header
    with opener(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def record(paths, out_path):
    with open(out_path, "w") as fh:
        json.dump({p: digest(p) for p in sorted(paths)}, fh, indent=1)


def verify(checksum_path):
    """Return the files that are missing or differ from the recorded checksums."""
    with open(checksum_path) as fh:
        want = json.load(fh)
    return [p for p, h in want.items() if not os.path.exists(p) or digest(p) != h]
