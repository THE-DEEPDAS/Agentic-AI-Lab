"""Aggregate traces into the result tables, statistics, figures and a traced failure case."""
import csv
import glob
import json
import os
from collections import Counter, defaultdict

import numpy as np

from .scoring import FAILURES

CORE = ["c05", "c20", "c50"]
ORDER = ["c05", "c20", "c50", "c50_goldfirst", "c50_goldlast", "c05_padded", "c05_sc"]
LABELS = {
    "c05": "5 tools", "c20": "20 tools", "c50": "50 tools",
    "c50_goldfirst": "50, gold first", "c50_goldlast": "50, gold last",
    "c05_padded": "5 tools + padding", "c05_sc": "5 tools, self-consistency",
}


def load_records(run_dir):
    recs = []
    for p in sorted(glob.glob(os.path.join(run_dir, "traces", "*", "run*.jsonl"))):
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        recs.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return recs


def _msd(x):
    x = np.asarray(x, dtype=float)
    return float(x.mean()), float(x.std(ddof=1)) if len(x) > 1 else float("nan")


def per_run_table(recs):
    """{cond: {run: {metric: value}}} with task-level means inside each run."""
    g = defaultdict(list)
    for r in recs:
        g[(r["condition"], r["run"])].append(r)
    out = defaultdict(dict)
    for (c, run), rs in g.items():
        n = len(rs)
        out[c][run] = {
            "n_tasks": n,
            "tool_acc": sum(r["score"]["tool_ok"] for r in rs) / n,
            "param_acc_given_tool": (sum(r["score"]["param_ok"] for r in rs) /
                                     max(1, sum(r["score"]["tool_ok"] for r in rs))),
            "ast_acc": sum(r["score"]["ast_ok"] for r in rs) / n,
            "api_error_rate": sum(r["score"]["failure"] == "api_error" for r in rs) / n,
            "input_tokens": float(np.mean([r["input_tokens"] for r in rs])),
            "output_tokens": float(np.mean([r["output_tokens"] for r in rs])),
            "model_calls": float(np.mean([r["model_calls"] for r in rs])),
            "latency_s": float(np.mean([r["latency_s"] for r in rs])),
        }
    return out


def condition_summary(runs):
    summ = {}
    for c, by_run in runs.items():
        ks = sorted(by_run)
        row = {"n_runs": len(ks), "n_tasks": by_run[ks[0]]["n_tasks"]}
        for m in ["tool_acc", "param_acc_given_tool", "ast_acc", "api_error_rate",
                  "input_tokens", "output_tokens", "model_calls", "latency_s"]:
            vals = [by_run[k][m] for k in ks]
            row[m] = {"mean": _msd(vals)[0], "sd": _msd(vals)[1], "runs": vals}
        tot = row["input_tokens"]["mean"] + row["output_tokens"]["mean"]
        row["tokens_per_correct"] = tot / row["ast_acc"]["mean"] if row["ast_acc"]["mean"] > 0 else None
        summ[c] = row
    return summ


def task_matrix(recs, cond, metric="ast_ok"):
    """task uuid -> mean of metric over runs for one condition."""
    d = defaultdict(list)
    for r in recs:
        if r["condition"] == cond:
            d[r["uuid"]].append(float(r["score"][metric]))
    return {k: float(np.mean(v)) for k, v in d.items()}


def paired_bootstrap(a, b, n_boot=10000, seed=7):
    """Paired bootstrap over tasks for mean(b - a) with a 95% percentile interval."""
    keys = sorted(set(a) & set(b))
    if not keys:
        return None
    diff = np.array([b[k] - a[k] for k in keys])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(diff), size=(n_boot, len(diff)))
    means = diff[idx].mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return {"n_tasks": len(keys), "mean_diff": float(diff.mean()), "ci95": [float(lo), float(hi)],
            "excludes_zero": bool(lo > 0 or hi < 0)}


def comparisons(recs, present):
    pairs = [("c05", "c20"), ("c20", "c50"), ("c05", "c50"), ("c50", "c50_goldfirst"),
             ("c50", "c50_goldlast"), ("c05", "c05_padded"), ("c05_sc", "c50"), ("c05", "c05_sc")]
    out = {}
    for a, b in pairs:
        if a in present and b in present:
            out[f"{a}->{b}"] = {m: paired_bootstrap(task_matrix(recs, a, m), task_matrix(recs, b, m))
                                for m in ("tool_ok", "ast_ok")}
    return out


def failure_table(recs):
    """{cond: {'n_tasks_scored', 'failed', counts{cat: n}}} over all runs."""
    out = {}
    g = defaultdict(list)
    for r in recs:
        g[r["condition"]].append(r)
    for c, rs in g.items():
        cnt = Counter(r["score"]["failure"] for r in rs if r["score"]["failure"])
        out[c] = {"n": len(rs), "failed": int(sum(cnt.values())),
                  "counts": {k: int(cnt.get(k, 0)) for k in FAILURES}}
    return out


def position_table(recs):
    """AST accuracy by position of the gold tool in the list (c50 family)."""
    bins = [(0, 16), (17, 33), (34, 49)]
    out = {}
    for c in ("c50", "c50_goldfirst", "c50_goldlast"):
        rs = [r for r in recs if r["condition"] == c]
        if not rs:
            continue
        row = {}
        for lo, hi in bins:
            sub = [r for r in rs if lo <= r["gold_position"] <= hi]
            row[f"{lo}-{hi}"] = {"n": len(sub),
                                 "ast_acc": (sum(r["score"]["ast_ok"] for r in sub) / len(sub)) if sub else None}
        out[c] = row
    return out


def domain_table(recs):
    g = defaultdict(list)
    for r in recs:
        g[(r["condition"], r["domain"])].append(r)
    out = defaultdict(dict)
    for (c, d), rs in g.items():
        out[c][d] = {"n": len(rs), "tool_acc": sum(r["score"]["tool_ok"] for r in rs) / len(rs),
                     "ast_acc": sum(r["score"]["ast_ok"] for r in rs) / len(rs)}
    return out


def pick_failure_case(recs):
    """Prefer a task that c05 always solves and c50 always fails (consistent, attributable to count)."""
    by = defaultdict(lambda: defaultdict(list))
    for r in recs:
        by[r["uuid"]][r["condition"]].append(r)
    cands = []
    for u, d in by.items():
        if d.get("c05") and d.get("c50"):
            ok5 = all(r["score"]["ast_ok"] for r in d["c05"])
            bad50 = all(not r["score"]["ast_ok"] for r in d["c50"])
            if ok5 and bad50:
                r = d["c50"][0]
                cands.append((0 if r["score"]["failure"].startswith("wrong_tool") else 1, r["task_idx"], u))
    if not cands:
        return None
    cands.sort()
    u = cands[0][2]
    return {"uuid": u, "c05": by[u]["c05"][0], "c50": by[u]["c50"][0]}


def _mock_banner(manifest):
    return "MOCK MODEL - NOT A RESULT" if manifest.get("mock_run") else None


def make_figures(run_dir, summ, fails, pos, manifest):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    banner = _mock_banner(manifest)
    figs = {}
    conds = [c for c in ORDER if c in summ]

    def stamp(ax):
        if banner:
            ax.text(0.5, 0.5, banner, transform=ax.transAxes, ha="center", va="center", fontsize=22,
                    color="red", alpha=0.25, rotation=25)

    core = [c for c in CORE if c in summ]
    if core:
        fig, ax = plt.subplots(figsize=(5.2, 3.2), dpi=200)
        x = np.arange(len(core))
        w = 0.36
        for i, (m, lab) in enumerate([("tool_acc", "tool selection"), ("ast_acc", "AST (tool + parameters)")]):
            ax.bar(x + (i - 0.5) * w, [summ[c][m]["mean"] for c in core], w,
                   yerr=[0 if np.isnan(summ[c][m]["sd"]) else summ[c][m]["sd"] for c in core],
                   capsize=3, label=lab)
        ax.set_xticks(x, [LABELS[c] for c in core])
        ax.set_ylim(0, 1.05)
        ax.set_ylabel("accuracy (mean ± SD over runs)")
        ax.legend(frameon=False, fontsize=8, loc="lower left")
        ax.spines[["top", "right"]].set_visible(False)
        stamp(ax)
        fig.tight_layout()
        p = os.path.join(run_dir, "fig_accuracy.png")
        fig.savefig(p)
        plt.close(fig)
        figs["accuracy"] = p

    if conds:
        fig, ax = plt.subplots(figsize=(5.2, 3.2), dpi=200)
        for c in conds:
            tok = summ[c]["input_tokens"]["mean"] + summ[c]["output_tokens"]["mean"]
            ax.errorbar(tok, summ[c]["ast_acc"]["mean"],
                        yerr=0 if np.isnan(summ[c]["ast_acc"]["sd"]) else summ[c]["ast_acc"]["sd"], fmt="o", capsize=3)
            ax.annotate(LABELS[c], (tok, summ[c]["ast_acc"]["mean"]), textcoords="offset points",
                        xytext=(5, 5), fontsize=7)
        ax.set_xlabel("tokens per task (input + output, all samples)")
        ax.set_ylabel("AST accuracy")
        ax.set_ylim(0, 1.05)
        ax.spines[["top", "right"]].set_visible(False)
        stamp(ax)
        fig.tight_layout()
        p = os.path.join(run_dir, "fig_cost.png")
        fig.savefig(p)
        plt.close(fig)
        figs["cost"] = p

    fc = [c for c in conds if c in fails and fails[c]["failed"] > 0]
    if fc:
        fig, ax = plt.subplots(figsize=(5.6, 3.4), dpi=200)
        bottom = np.zeros(len(fc))
        for cat in FAILURES:
            vals = np.array([fails[c]["counts"][cat] / fails[c]["n"] for c in fc])
            if vals.sum() == 0:
                continue
            ax.bar([LABELS[c] for c in fc], vals, bottom=bottom, label=cat.replace("_", " "))
            bottom += vals
        ax.set_ylabel("share of all task attempts")
        ax.tick_params(axis="x", labelrotation=30, labelsize=7)
        ax.legend(frameon=False, fontsize=6, loc="upper left", bbox_to_anchor=(1, 1))
        ax.spines[["top", "right"]].set_visible(False)
        stamp(ax)
        fig.tight_layout()
        p = os.path.join(run_dir, "fig_failures.png")
        fig.savefig(p)
        plt.close(fig)
        figs["failures"] = p
    return figs


def fmt(m, pct=True, digits=1):
    if m is None or m["mean"] is None:
        return "n/a"
    sd = "" if np.isnan(m["sd"]) else f" ± {m['sd'] * (100 if pct else 1):.{digits}f}"
    return f"{m['mean'] * (100 if pct else 1):.{digits}f}{sd}"


def tables_markdown(summ, fails, comps, pos, manifest):
    L = []
    if manifest.get("mock_run"):
        L.append("> **MOCK MODEL - NOT A RESULT.** Produced by the offline keyword mock to test the pipeline.\n")
    L.append("| Condition | Tool acc % | Param acc % (given tool) | AST acc % | In tok/task | Out tok/task | Calls/task | Latency s/task | Tok per correct |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for c in [c for c in ORDER if c in summ]:
        s = summ[c]
        tpc = s["tokens_per_correct"]
        L.append(f"| {LABELS[c]} | {fmt(s['tool_acc'])} | {fmt(s['param_acc_given_tool'])} | {fmt(s['ast_acc'])} | "
                 f"{fmt(s['input_tokens'], False, 0)} | {fmt(s['output_tokens'], False, 0)} | "
                 f"{fmt(s['model_calls'], False, 2)} | {fmt(s['latency_s'], False, 2)} | "
                 f"{'n/a' if not tpc else f'{tpc:.0f}'} |")
    L.append(f"\nMean ± SD over {max(s['n_runs'] for s in summ.values())} runs of the {max(s['n_tasks'] for s in summ.values())}-task subset.\n")
    L.append("| Paired comparison (task level) | metric | mean diff (pp) | 95% bootstrap CI (pp) | CI excludes 0 |")
    L.append("|---|---|---|---|---|")
    for k, d in comps.items():
        for m, v in d.items():
            if v:
                L.append(f"| {k} | {m} | {v['mean_diff'] * 100:+.1f} | [{v['ci95'][0] * 100:+.1f}, {v['ci95'][1] * 100:+.1f}] | {'yes' if v['excludes_zero'] else 'no'} |")
    L.append("\n| Condition | failed attempts | " + " | ".join(f.replace("_", " ") for f in FAILURES) + " |")
    L.append("|---|---|" + "---|" * len(FAILURES))
    for c in [c for c in ORDER if c in fails]:
        f = fails[c]
        L.append(f"| {LABELS[c]} | {f['failed']}/{f['n']} | " + " | ".join(str(f["counts"][k]) for k in FAILURES) + " |")
    if pos:
        L.append("\n| Gold-tool position | " + " | ".join(next(iter(pos.values())).keys()) + " |")
        L.append("|---|" + "---|" * len(next(iter(pos.values()))))
        for c, row in pos.items():
            L.append(f"| {LABELS[c]} | " + " | ".join("n/a" if v["ast_acc"] is None else f"{v['ast_acc'] * 100:.1f}% (n={v['n']})" for v in row.values()) + " |")
    return "\n".join(L) + "\n"


def aggregate(run_dir):
    recs = load_records(run_dir)
    if not recs:
        raise SystemExit(f"no traces found under {run_dir}/traces")
    mpath = os.path.join(run_dir, "manifest.json")
    manifest = json.load(open(mpath, encoding="utf-8")) if os.path.exists(mpath) else {}
    runs = per_run_table(recs)
    summ = condition_summary(runs)
    present = set(summ)
    comps = comparisons(recs, present)
    fails = failure_table(recs)
    pos = position_table(recs)
    dom = domain_table(recs)
    fc = pick_failure_case(recs)
    figs = make_figures(run_dir, summ, fails, pos, manifest)

    summary = {
        "run_dir": os.path.basename(run_dir.rstrip("/")),
        "mock_run": manifest.get("mock_run", False),
        "model_requested": manifest.get("model_requested"),
        "model_strings_returned_by_api": manifest.get("model_strings_returned_by_api"),
        "started_utc": manifest.get("started_utc"), "finished_utc": manifest.get("finished_utc"),
        "decoding": manifest.get("decoding"),
        "conditions": summ, "comparisons": comps, "failures": fails, "position": pos, "domains": dom,
        "failure_case_uuid": fc["uuid"] if fc else None,
        "figures": {k: os.path.basename(v) for k, v in figs.items()},
    }
    with open(os.path.join(run_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    with open(os.path.join(run_dir, "tables.md"), "w", encoding="utf-8") as f:
        f.write(tables_markdown(summ, fails, comps, pos, manifest))
    with open(os.path.join(run_dir, "per_task.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["condition", "run", "uuid", "domain", "n_tools", "gold_position", "tool_ok", "param_ok",
                    "ast_ok", "failure", "pred_name", "gold_name", "input_tokens", "output_tokens",
                    "model_calls", "latency_s"])
        for r in sorted(recs, key=lambda r: (r["condition"], r["run"], r["task_idx"])):
            s = r["score"]
            w.writerow([r["condition"], r["run"], r["uuid"], r["domain"], r["n_tools"], r["gold_position"],
                        int(s["tool_ok"]), int(s["param_ok"]), int(s["ast_ok"]), s["failure"] or "",
                        s["pred_name"] or "", r["label"]["name"], r["input_tokens"], r["output_tokens"],
                        r["model_calls"], r["latency_s"]])
    if fc:
        def slim(r):
            return {k: r[k] for k in ("uuid", "domain", "condition", "run", "n_tools", "gold_position", "user",
                                       "label", "samples", "input_tokens", "output_tokens", "latency_s", "score")} | \
                   {"tool_names_head": r["tool_names"][:60]}
        with open(os.path.join(run_dir, "failure_case.json"), "w", encoding="utf-8") as f:
            json.dump({"c05_success": slim(fc["c05"]), "c50_failure": slim(fc["c50"])}, f, indent=2, ensure_ascii=False)
    return summary
