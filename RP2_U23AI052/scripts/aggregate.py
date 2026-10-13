#!/usr/bin/env python3
"""Regenerate every table and figure from the traces of one run directory.

    python scripts/aggregate.py --run-dir results/<run>
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rp2.aggregate import aggregate  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    a = ap.parse_args()
    s = aggregate(a.run_dir)
    print(open(os.path.join(a.run_dir, "tables.md"), encoding="utf-8").read())
    print("wrote summary.json, tables.md, per_task.csv, figures in", a.run_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
