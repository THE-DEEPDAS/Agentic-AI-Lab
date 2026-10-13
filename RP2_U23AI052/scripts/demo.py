#!/usr/bin/env python3
"""Live demonstration: ONE benchmark task under 5, 20 and 50 tools, same model, same prompts.

    python scripts/demo.py                      # first task, conditions c05 c20 c50
    python scripts/demo.py --task-index 17 --conditions c05 c50
    python scripts/demo.py --provider mock      # offline rehearsal (not a result)

Shows what the experiment measures: the exact request, the tool the model called, the score,
the failure label, tokens and latency. Traces go to results/demo/ and can be opened afterwards.
"""
import argparse
import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rp2.common import ROOT, load_config  # noqa: E402
from rp2.runner import Runner  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-index", type=int, default=0)
    ap.add_argument("--domain", choices=["search", "map", "finance"], default=None,
                    help="pick the first task of this domain instead of --task-index")
    ap.add_argument("--conditions", nargs="+", default=["c05", "c20", "c50"])
    ap.add_argument("--provider", default=None)
    ap.add_argument("--run", type=int, default=1)
    args = ap.parse_args()

    cfg = load_config()
    if args.provider:
        cfg["model"]["provider"] = args.provider
    out = os.path.join(ROOT, "results", "demo")
    r = Runner(copy.deepcopy(cfg), out, args.conditions, runs=1, workers=1, rps=None)
    idx = args.task_index
    if args.domain:
        idx = next(i for i, t in enumerate(r.tasks) if t["domain"] == args.domain)
    task = r.tasks[idx]

    os.makedirs(out, exist_ok=True)
    r._load_done()
    r._write_contexts()
    print("=" * 78)
    print(f"model      : {cfg['model']['name'] or cfg['model']['provider']}   temperature={cfg['model']['temperature']}")
    print(f"task       : #{idx} [{task['domain']}]  {task['uuid']}")
    print(f"query      : {task['query']}")
    print(f"gold tool  : {task['label']['name']}   gold args: {json.dumps(task['label']['input'], ensure_ascii=False)}")
    print(f"accepted   : {sorted({task['label']['name']} | {s['name'] for s in task['label'].get('similar_tools', [])})}")
    print("=" * 78)
    if r.is_mock:
        print("MOCK MODEL: offline rehearsal, these outputs are NOT results\n")
    for cid in args.conditions:
        r.done_keys.discard((cid, args.run, task["uuid"]))
        rec = r._job(args.run, idx, cid)
        s = rec["score"]
        smp = rec["samples"][rec["chosen_sample"]]
        print(f"--- {cid}: {rec['n_tools']} tools in context (gold at position {rec['gold_position']}) ---")
        print(f"  called     : {s['pred_name']}  {json.dumps(s['pred_args'], ensure_ascii=False) if s['pred_args'] is not None else ''}")
        verdict = "PASS" if s["ast_ok"] else f"FAIL ({s['failure']})"
        print(f"  tool_ok={s['tool_ok']}  param_ok={s['param_ok']}  ->  {verdict}")
        if s["detail"]:
            print(f"  detail     : {s['detail']}")
        print(f"  cost       : {rec['input_tokens']} in / {rec['output_tokens']} out tokens, "
              f"{rec['model_calls']} call(s), {rec['latency_s']:.2f}s wall-clock  (model string: {smp['model_returned']})")
    print("=" * 78)
    print(f"full traces: {out}/traces/<condition>/run{args.run}.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
