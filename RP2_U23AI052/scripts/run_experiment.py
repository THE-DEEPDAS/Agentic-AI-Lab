#!/usr/bin/env python3
"""Run the experiment.

Real run (after setting model.name / provider / base_url in configs/config.yaml and exporting the key):
    export LLM_API_KEY=...
    python scripts/run_experiment.py --tiers 1 2 3

Offline pipeline test (mock model, NOT a result):
    python scripts/run_experiment.py --provider mock --tiers 1 2 3

Interrupted runs resume where they stopped (same output directory).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rp2.common import load_config  # noqa: E402
from rp2.runner import Runner, default_out_dir  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None)
    ap.add_argument("--provider", default=None, help="override model.provider (e.g. mock)")
    ap.add_argument("--tiers", type=int, nargs="*", default=[1], help="condition tiers to run (1 core, 2 ablations, 3 matched budget)")
    ap.add_argument("--conditions", nargs="*", default=None, help="explicit condition ids (overrides --tiers)")
    ap.add_argument("--runs", type=int, default=None)
    ap.add_argument("--limit", type=int, default=None, help="only the first N tasks (smoke tests)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--rps", type=float, default=None)
    ap.add_argument("--max-jobs", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true", help="print the plan and the offline token estimate, call nothing")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.provider:
        cfg["model"]["provider"] = args.provider
    ids = args.conditions or [c["id"] for c in cfg["conditions"] if c.get("tier", 1) in args.tiers]
    out = args.out or default_out_dir(cfg)

    if args.dry_run:
        cfg_dry = dict(cfg, model=dict(cfg["model"], provider="mock"))
        r = Runner(cfg_dry, out, ids, runs=args.runs, limit=args.limit)
        est = r.estimate()
        print(f"{'condition':16s} {'calls':>7s} {'mean in-tokens/task':>20s} {'total in-tokens':>16s}")
        tot_calls = tot_tok = 0
        for cid, e in est.items():
            print(f"{cid:16s} {e['calls']:7d} {e['mean_input_tokens_per_task']:20.0f} {e['total_input_tokens']:16.0f}")
            tot_calls += e["calls"]
            tot_tok += e["total_input_tokens"]
        print(f"{'TOTAL':16s} {tot_calls:7d} {'':20s} {tot_tok:16.0f}   (chars/4 estimate, input tokens only)")
        return 0

    r = Runner(cfg, out, ids, runs=args.runs, limit=args.limit, workers=args.workers, rps=args.rps)
    summary = r.run(max_jobs=args.max_jobs)
    print(summary)
    print(f"traces and manifest in {out}\nnext: python scripts/aggregate.py --run-dir {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
