"""Data-driven sentences for the report and slides.

Everything here is computed from summary.json; nothing is hard-coded about outcomes. The
interpretation rules are explicit so the author can check each one against the traces and edit
the wording before submitting.
"""
from .scoring import FAILURES

LAB = {"c05": "5 tools", "c20": "20 tools", "c50": "50 tools"}
TOOL_ERR = ("wrong_tool_same_domain", "wrong_tool_cross_domain", "invalid_tool_name", "no_tool_call")


def pp(x):
    return f"{x * 100:+.1f} pp"


def pct(m):
    return f"{m['mean'] * 100:.1f}%"


def sd(m):
    return "n/a" if m["sd"] != m["sd"] else f"{m['sd'] * 100:.1f}"


def _cmp(summary, key, metric="ast_ok"):
    c = summary["comparisons"].get(key)
    return c[metric] if c and c.get(metric) else None


def _ci_text(c):
    lo, hi = c["ci95"]
    return f"{pp(c['mean_diff'])}, 95% CI [{lo * 100:+.1f}, {hi * 100:+.1f}]"


def failure_share(fail_row, cats):
    if not fail_row or fail_row["failed"] == 0:
        return 0.0
    return sum(fail_row["counts"][c] for c in cats) / fail_row["failed"]


def analysis(summary):
    """Return (findings, interpretation) as lists of strings."""
    S, F = summary["conditions"], summary["failures"]
    find, interp = [], []

    if all(c in S for c in ("c05", "c20", "c50")):
        a = [S[c]["ast_acc"] for c in ("c05", "c20", "c50")]
        t = [S[c]["tool_acc"] for c in ("c05", "c20", "c50")]
        find.append(
            f"AST accuracy over 5 / 20 / 50 tools: {pct(a[0])} / {pct(a[1])} / {pct(a[2])} "
            f"(run-to-run SD {sd(a[0])} / {sd(a[1])} / {sd(a[2])} pp); tool-selection accuracy "
            f"{pct(t[0])} / {pct(t[1])} / {pct(t[2])}.")
        c = _cmp(summary, "c05->c50")
        if c:
            verdict = ("larger than task-level sampling noise" if c["excludes_zero"]
                       else "not distinguishable from task-level sampling noise")
            find.append(f"5 to 50 tools changes AST accuracy by {_ci_text(c)} (paired bootstrap over "
                        f"{c['n_tasks']} tasks): {verdict}.")
        c2 = _cmp(summary, "c05->c20")
        c3 = _cmp(summary, "c20->c50")
        if c2 and c3:
            find.append(f"Step 5 to 20: {_ci_text(c2)}. Step 20 to 50: {_ci_text(c3)}.")
        tok = [S[c]["input_tokens"]["mean"] for c in ("c05", "c20", "c50")]
        tpc = [S[c]["tokens_per_correct"] for c in ("c05", "c20", "c50")]
        find.append(
            f"Cost: mean input tokens per task {tok[0]:.0f} / {tok[1]:.0f} / {tok[2]:.0f} "
            f"(x{tok[2] / tok[0]:.1f} from 5 to 50 tools); tokens per correct task "
            f"{tpc[0]:.0f} / {tpc[1]:.0f} / {tpc[2]:.0f}." if all(tpc) else
            f"Cost: mean input tokens per task {tok[0]:.0f} / {tok[1]:.0f} / {tok[2]:.0f}.")
        lat = [S[c]["latency_s"]["mean"] for c in ("c05", "c20", "c50")]
        find.append(f"Latency per task {lat[0]:.2f}s / {lat[1]:.2f}s / {lat[2]:.2f}s; "
                    f"model calls per task {S['c05']['model_calls']['mean']:.2f} in every core condition.")

        s5, s50 = failure_share(F.get("c05"), TOOL_ERR), failure_share(F.get("c50"), TOOL_ERR)
        top = {}
        for cnd in ("c05", "c50"):
            row = F.get(cnd)
            if row and row["failed"]:
                k = max(FAILURES, key=lambda f: row["counts"][f])
                top[cnd] = (k, row["counts"][k] / row["failed"])
        if len(top) == 2:
            find.append(
                f"Failure composition: tool-selection errors are {s5 * 100:.0f}% of failures at 5 tools and "
                f"{s50 * 100:.0f}% at 50. Most common failure: {top['c05'][0].replace('_', ' ')} "
                f"({top['c05'][1] * 100:.0f}%) at 5 tools, {top['c50'][0].replace('_', ' ')} "
                f"({top['c50'][1] * 100:.0f}%) at 50.")
        # interpretation rules
        if c and c["excludes_zero"] and c["mean_diff"] < 0:
            interp.append("Adding tools lowered accuracy by more than sampling noise. Whether that is the number of "
                          "choices or the extra context length is decided by the padding arm below.")
        elif c and c["excludes_zero"] and c["mean_diff"] > 0:
            interp.append("Accuracy rose with more tools, against the hypothesis. Check the traces for a labelling "
                          "or distractor artefact before reporting this as a finding.")
        elif c:
            interp.append("No effect of tool count was detected at this sample size; with 200 tasks only large "
                          "effects are visible, so this is evidence of a small effect, not of none.")
        if s50 - s5 > 0.10:
            interp.append("The failure mix shifts towards choosing the wrong tool as the list grows, i.e. the loss is "
                          "selection, not argument filling.")
        elif s5 - s50 > 0.10:
            interp.append("The failure mix shifts towards argument errors as the list grows.")

    for key, name in (("c50->c50_goldfirst", "gold tool first"), ("c50->c50_goldlast", "gold tool last")):
        c = _cmp(summary, key)
        if c:
            find.append(f"Position control, 50 tools with {name} vs shuffled: {_ci_text(c)}.")
    cg, cl = _cmp(summary, "c50->c50_goldfirst"), _cmp(summary, "c50->c50_goldlast")
    if cg and cl:
        if not cg["excludes_zero"] and not cl["excludes_zero"]:
            interp.append("Position of the correct tool does not explain the 50-tool result (both position arms are "
                          "within noise of the shuffled order).")
        else:
            interp.append("Position of the correct tool matters: at least one position arm differs from the shuffled "
                          "order beyond noise, so part of the drop is a position effect.")
    cp = _cmp(summary, "c05->c05_padded")
    if cp:
        find.append(f"Length control, 5 tools padded with neutral text to the 50-tool length vs plain 5 tools: {_ci_text(cp)}.")
        c05v50 = _cmp(summary, "c05->c50")
        if c05v50 and c05v50["excludes_zero"] and c05v50["mean_diff"] < 0:
            if not cp["excludes_zero"] or cp["mean_diff"] > c05v50["mean_diff"] / 2:
                interp.append("Padding alone costs much less than adding tools, so the drop is mostly the number of "
                              "competing tools rather than raw context length.")
            else:
                interp.append("Padding alone costs about as much as adding tools, so context length rather than "
                              "tool count may drive the drop.")
    if "c05_sc" in S and "c50" in S:
        tsc = S["c05_sc"]["input_tokens"]["mean"] + S["c05_sc"]["output_tokens"]["mean"]
        t50 = S["c50"]["input_tokens"]["mean"] + S["c50"]["output_tokens"]["mean"]
        find.append(f"Matched budget: 5 tools with self-consistency (k={S['c05_sc']['model_calls']['mean']:.0f}) uses "
                    f"{tsc:.0f} tokens per task against {t50:.0f} for 50 tools (ratio {tsc / t50:.2f}); "
                    f"AST accuracy {pct(S['c05_sc']['ast_acc'])} vs {pct(S['c50']['ast_acc'])}.")
        cc = _cmp(summary, "c05_sc->c50")
        if cc:
            find.append(f"Self-consistency (5 tools) to 50 tools at similar spend: {_ci_text(cc)}.")
    dom = summary.get("domains", {})
    if "c05" in dom and "c50" in dom:
        parts = []
        for d in ("search", "map", "finance"):
            if d in dom["c05"] and d in dom["c50"]:
                parts.append(f"{d} {dom['c05'][d]['ast_acc'] * 100:.0f}% to {dom['c50'][d]['ast_acc'] * 100:.0f}%")
        if parts:
            find.append("AST accuracy by domain, 5 to 50 tools: " + "; ".join(parts) + ".")
    return find, interp


def describe(pool, name, n=170):
    for p in pool:
        if p["name"] == name:
            d = " ".join(p["tool"]["description"].split())
            return d[:n] + ("..." if len(d) > n else "")
    return ""
