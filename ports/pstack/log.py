#!/usr/bin/env python3
"""Write one sanitized decision row. No provider or network access."""
import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path


def clean(value):
    value = value.replace("\t", " ").replace("\r", " ").replace("\n", " ")
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def append(path, phase, decision, why, evidence, result):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        if header:
            writer.writerow(["ts", "phase", "decision", "why", "evidence", "result"])
        writer.writerow([datetime.now(timezone.utc).isoformat()] + [
            clean(v) for v in (phase, decision, why, evidence, result)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True)
    for name in ("phase", "decision", "why", "evidence", "result"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    append(args.file, args.phase, args.decision, args.why, args.evidence, args.result)
