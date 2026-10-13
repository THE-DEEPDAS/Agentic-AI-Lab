#!/usr/bin/env python3
"""Check the automatic scorer against YOUR OWN labels on 20 tasks (replaces the LLM judge).

    python scripts/label_audit.py export --run-dir results/<run> --out results/<run>/audit.csv
        -> open audit.csv, fill human_tool_ok and human_param_ok with 1 or 0 for every row
           (judge each row from query / gold / prediction only; ignore the scorer columns)
    python scripts/label_audit.py score --csv results/<run>/audit.csv
        -> agreement % and Cohen's kappa between your labels and the scorer

The sample is stratified: ten rows the scorer passed and ten it failed, drawn from c05 and c50.
"""
import argparse
import csv
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rp2.aggregate import load_records  # noqa: E402


def kappa(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pa1, pb1 = sum(a) / n, sum(b) / n
    pe = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def export(run_dir, out, n=20, seed=11):
    recs = [r for r in load_records(run_dir) if r["condition"] in ("c05", "c50") and r["run"] == 1
            and r["score"]["failure"] != "api_error"]
    rng = random.Random(seed)
    passed = [r for r in recs if r["score"]["ast_ok"]]
    failed = [r for r in recs if not r["score"]["ast_ok"]]
    rng.shuffle(passed)
    rng.shuffle(failed)
    pick = passed[: n // 2] + failed[: n - len(passed[: n // 2])]
    if len(pick) < n:
        pick += [r for r in (passed[n // 2:] + failed[n - n // 2:]) if r not in pick][: n - len(pick)]
    rng.shuffle(pick)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["condition", "uuid", "query", "gold_tool", "accepted_similar_tools", "gold_args",
                    "pred_tool", "pred_args", "human_tool_ok", "human_param_ok", "scorer_tool_ok", "scorer_param_ok"])
        for r in pick:
            s = r["score"]
            w.writerow([r["condition"], r["uuid"], r["user"], r["label"]["name"], "|".join(r["label"]["similar"]),
                        json.dumps(r["label"]["input"], ensure_ascii=False),
                        s["pred_name"], json.dumps(s["pred_args"], ensure_ascii=False),
                        "", "", int(s["tool_ok"]), int(s["param_ok"])])
    print(f"wrote {len(pick)} rows to {out}; fill human_tool_ok / human_param_ok, then run 'score'")


def score(csv_path):
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    if len(rows) < 20:
        print(f"warning: only {len(rows)} rows, the project requires at least 20")
    res = {}
    for m in ("tool", "param"):
        h = [int(r[f"human_{m}_ok"]) for r in rows if r[f"human_{m}_ok"] != ""]
        s = [int(r[f"scorer_{m}_ok"]) for r in rows if r[f"human_{m}_ok"] != ""]
        if not h:
            raise SystemExit(f"human_{m}_ok is empty")
        res[m] = {"n": len(h), "agreement": sum(x == y for x, y in zip(h, s)) / len(h), "cohen_kappa": kappa(h, s)}
        print(f"{m:5s}: n={len(h)} agreement={res[m]['agreement'] * 100:.1f}%  kappa={res[m]['cohen_kappa']:.2f}")
    out = os.path.splitext(csv_path)[0] + "_agreement.json"
    json.dump(res, open(out, "w"), indent=2)
    print("wrote", out)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--run-dir", required=True)
    e.add_argument("--out", required=True)
    s = sub.add_parser("score")
    s.add_argument("--csv", required=True)
    a = ap.parse_args()
    export(a.run_dir, a.out) if a.cmd == "export" else score(a.csv)


if __name__ == "__main__":
    sys.exit(main())
