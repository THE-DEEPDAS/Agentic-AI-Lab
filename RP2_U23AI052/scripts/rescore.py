#!/usr/bin/env python3
"""Rescore saved traces after a change to rp2/scoring.py (no API calls).

    python scripts/rescore.py --run-dir results/<run>
    python scripts/aggregate.py --run-dir results/<run>
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rp2.common import condition_map, load_config, load_pool, load_tasks  # noqa: E402
from rp2.context import build_context  # noqa: E402
from rp2.scoring import score_call  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    a = ap.parse_args()
    cfg = load_config()
    tasks = {t["uuid"]: t for t in load_tasks(cfg)}
    pool, cmap = load_pool(cfg), condition_map(cfg)
    n = changed = 0
    for path in glob.glob(os.path.join(a.run_dir, "traces", "*", "run*.jsonl")):
        recs = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
        for r in recs:
            t = tasks[r["uuid"]]
            ctx = build_context(t, cmap[r["condition"]], pool, cfg["experiment"]["design_seed"])
            s = r["samples"][r["chosen_sample"]]
            new = score_call(t, ctx, {"error": s["error"], "text": s["text"], "tool_calls": s["tool_calls"]}, cfg["scoring"])
            changed += new != r["score"]
            r["score"] = new
            n += 1
        with open(path, "w", encoding="utf-8") as f:
            f.write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs))
    print(f"rescored {n} records, {changed} changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
