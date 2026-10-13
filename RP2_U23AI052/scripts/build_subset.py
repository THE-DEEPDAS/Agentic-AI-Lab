#!/usr/bin/env python3
"""Build the stratified 200-task subset and the tool pool from a clone of MCPToolBench++.

    git clone https://github.com/mcp-tool-bench/mcptoolbenchpp /path/to/mcptoolbenchpp
    python scripts/build_subset.py --bench /path/to/mcptoolbenchpp

The outputs (data/subset_200.json, data/tool_pool.json) are committed, so a reader does
not need the clone to reproduce the experiment. This script documents how they were made.

Scope note: the public release contains single-step tasks only for search/map/finance
(map has two multi-step items), so the subset is 200 single-step tasks, 67/67/66 per domain.
"""
import argparse
import json
import os
import random
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SOURCES = {
    "search": "data/search/search_0725_single_v2.json",
    "map": "data/map/map_0717_single_multi_lang_500.json",
    "finance": "data/finance/finance_0724_single_v3.json",
}
POOL_SOURCES = {
    "search": "data/search/search_0725_single_v2.json",
    "map": "data/map/map_0717_single_multi_lang_500.json",
    "finance": "data/finance/finance_0724_single_v3.json",
    "browser": "data/browser/browser_0724_single_v3.json",
    "filesystem": "data/file_system/filesystem_0723_single.json",
    "pay": "data/pay/pay_0723_single.json",
}
PER_DOMAIN = {"search": 67, "map": 67, "finance": 66}


def eligible(task):
    label = task.get("function_call_label")
    return (
        task.get("call_type") == "single"
        and isinstance(label, list)
        and len(label) == 1
        and isinstance(label[0].get("input"), dict)
        and any(t["name"] == label[0]["name"] for t in task.get("tools", []))
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", required=True, help="path to the MCPToolBench++ clone")
    ap.add_argument("--seed", type=int, default=1234)
    args = ap.parse_args()

    commit = subprocess.run(
        ["git", "-C", args.bench, "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()

    rng = random.Random(args.seed)
    subset, dropped = [], {}
    for domain, rel in SOURCES.items():
        tasks = json.load(open(os.path.join(args.bench, rel), encoding="utf-8"))
        ok = [t for t in tasks if eligible(t)]
        dropped[domain] = len(tasks) - len(ok)
        rng.shuffle(ok)
        for t in ok[: PER_DOMAIN[domain]]:
            subset.append(
                {
                    "uuid": t["uuid"],
                    "domain": domain,
                    "query": t["query"],
                    "label": t["function_call_label"][0],  # name, input, similar_tools, mcp_server
                    "native_tools": t["tools"],
                }
            )
    # tool pool: every distinct tool schema in the benchmark, tagged with its domain
    pool = {}
    for domain, rel in POOL_SOURCES.items():
        tasks = json.load(open(os.path.join(args.bench, rel), encoding="utf-8"))
        for t in tasks:
            for tool in t.get("tools", []):
                key = tool["name"]
                if key in pool and pool[key]["domain"] != domain:
                    # same name in two domains would make 'cross-domain' ambiguous
                    raise SystemExit(f"tool name collision across domains: {key}")
                pool.setdefault(key, {"domain": domain, "tool": tool})
    pool_list = [dict(name=k, **v) for k, v in sorted(pool.items())]

    meta = {
        "benchmark_repo": "https://github.com/mcp-tool-bench/mcptoolbenchpp",
        "benchmark_commit": commit,
        "selection_seed": args.seed,
        "per_domain": PER_DOMAIN,
        "ineligible_dropped_per_domain": dropped,
    }
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    with open(os.path.join(ROOT, "data/subset_200.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "tasks": subset}, f, ensure_ascii=False)
    with open(os.path.join(ROOT, "data/tool_pool.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "tools": pool_list}, f, ensure_ascii=False)
    print(f"subset: {len(subset)} tasks; pool: {len(pool_list)} tools; commit {commit}")


if __name__ == "__main__":
    sys.exit(main())
