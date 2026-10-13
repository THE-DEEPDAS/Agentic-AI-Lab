#!/usr/bin/env python3
"""Build the (at most) four-page report PDF.

    python scripts/make_report.py --run-dir results/<real run> --out report/RP2_report.pdf
    python scripts/make_report.py                                # no run yet: setup-only report, no numbers

Sections that depend on results are filled from <run-dir>/summary.json and failure_case.json.
Pointing it at the mock run produces a clearly stamped layout preview, never a result.
"""
import argparse
import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_LEFT  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.platypus import (Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,  # noqa: E402
                                TableStyle)

from rp2.aggregate import LABELS, ORDER  # noqa: E402
from rp2.common import ROOT, load_config, load_pool  # noqa: E402
from rp2.report_text import analysis, describe  # noqa: E402
from rp2.runner import Runner  # noqa: E402
from rp2.scoring import FAILURES  # noqa: E402

NAVY = colors.HexColor("#1f2a6b")
GREY = colors.HexColor("#f0f1f5")
RED = colors.HexColor("#b3261e")

ss = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=ss["BodyText"], fontName="Helvetica", fontSize=8.7, leading=11.0,
                      alignment=TA_LEFT, spaceAfter=3)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=7.6, leading=9.4, spaceAfter=1)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=7.4, leading=9.0, spaceAfter=0)
H1 = ParagraphStyle("h1", parent=BODY, fontName="Helvetica-Bold", fontSize=10.2, leading=12.5,
                    textColor=NAVY, spaceBefore=5, spaceAfter=2, keepWithNext=1)
TITLE = ParagraphStyle("title", parent=BODY, fontName="Helvetica-Bold", fontSize=14, leading=17, textColor=NAVY)
BUL = ParagraphStyle("bul", parent=BODY, leftIndent=9, bulletIndent=0, spaceAfter=1.5)


def P(t, s=BODY):
    return Paragraph(t, s)


def bullets(items, style=BUL):
    return [Paragraph(i, style, bulletText="•") for i in items]


def tbl(rows, widths, header=True, font=7.4, zebra=True):
    data = [[Paragraph(str(c), CELL) for c in r] for r in rows]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c8cad4")),
          ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
          ("TOPPADDING", (0, 0), (-1, -1), 1.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6)]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), GREY)]
    t.setStyle(TableStyle(st))
    return t


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def mean_sd(m, pct=True, d=1):
    k = 100 if pct else 1
    sd = "" if m["sd"] != m["sd"] else f" ± {m['sd'] * k:.{d}f}"
    return f"{m['mean'] * k:.{d}f}{sd}"


def build(run_dir, out):
    cfg = load_config()
    pool = load_pool(cfg)
    summary = manifest = fcase = None
    if run_dir and os.path.exists(os.path.join(run_dir, "summary.json")):
        summary = json.load(open(os.path.join(run_dir, "summary.json"), encoding="utf-8"))
        manifest = json.load(open(os.path.join(run_dir, "manifest.json"), encoding="utf-8"))
        fp = os.path.join(run_dir, "failure_case.json")
        fcase = json.load(open(fp, encoding="utf-8")) if os.path.exists(fp) else None
    mock = bool(summary and summary["mock_run"])
    audit = None
    if run_dir and os.path.exists(os.path.join(run_dir, "audit_agreement.json")):
        audit = json.load(open(os.path.join(run_dir, "audit_agreement.json"), encoding="utf-8"))
    n_loc = 0
    for d in ("rp2", "scripts", "tests"):
        for f in os.listdir(os.path.join(ROOT, d)):
            if f.endswith(".py"):
                n_loc += sum(1 for _ in open(os.path.join(ROOT, d, f), encoding="utf-8"))
    audit_txt = ("agreement with the author's own labels on 20 tasks is measured by <font face='Courier'>scripts/label_audit.py</font> (not yet done)"
                 if not audit else
                 f"agreement with the author's own labels on {audit['tool']['n']} tasks: tool {audit['tool']['agreement'] * 100:.0f}% "
                 f"(kappa {audit['tool']['cohen_kappa']:.2f}), parameters {audit['param']['agreement'] * 100:.0f}% (kappa {audit['param']['cohen_kappa']:.2f})")

    W = A4[0] - 3.0 * cm
    story = []

    def watermark(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.grey)
        canvas.drawString(1.5 * cm, 0.9 * cm, "AI465 Agentic AI - Research Project Phase 2 - U23AI052")
        canvas.drawRightString(A4[0] - 1.5 * cm, 0.9 * cm, f"Page {doc.page}")
        if mock:
            canvas.setFont("Helvetica-Bold", 38)
            canvas.setFillColor(colors.Color(0.8, 0.1, 0.1, alpha=0.13))
            canvas.translate(A4[0] / 2, A4[1] / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, "MOCK MODEL - NOT A RESULT")
        canvas.restoreState()

    story.append(P("Effect of Tool-Count Context on MCP Tool Selection", TITLE))
    story.append(P("MCPToolBench++ subset, 5 vs 20 vs 50 tools in context. AI465 Agentic AI, SVNIT Surat, Semester VII. "
                   "Research Project Phase 2 report. Roll no. U23AI052 (individual work).", SMALL))
    if summary is None:
        story.append(Spacer(1, 3))
        story.append(tbl([[f"<b>Status: experiment not yet run.</b> This version contains the objective, deviations, "
                           f"implementation and setup. Sections 4 and 5 are filled automatically from the saved traces "
                           f"once the run is done: <font face='Courier'>python scripts/make_report.py --run-dir "
                           f"results/&lt;run&gt;</font>. No number in this document comes from a model run."]],
                         [W], header=False))

    # ---------------- 1. objective ----------------
    story.append(P("1. Objective and declared deviations", H1))
    story.append(P(
        "<b>Approved objective (Phase 1).</b> Evaluate the effect of tool-count context on MCP tool-selection accuracy and "
        "failure composition for single-step and multi-step tool-calling tasks on a 200-task stratified subset of "
        "MCPToolBench++ (search, map, finance), at a matched tool-count budget (5 vs 20 vs 50 tools in context), measured by "
        "AST accuracy, AST DAG accuracy, tokens per task, model calls per task and wall-clock latency per task. "
        "It targets three gaps in the paper (Fan et al., 2025, arXiv:2508.07575): no cost or latency, no variance, no failure taxonomy."))
    dev = [
        ["#", "Deviation from the approved objective", "Reason"],
        ["D1", "Subset is 200 <b>single-step</b> tasks (67 search, 67 map, 66 finance); no multi-step tasks, so AST DAG accuracy is not reported.",
         "The public repository (commit 2bd35e5) ships single-step data for these domains; map has only 2 multi-step items out of 500. "
         "Scope reduction, reported as allowed."],
        ["D2", "No execution-based Pass@K.", "It needs live MCP servers with third-party credentials. It was not in the approved metric list."],
        ["D3", "The benchmark's GPT-4o judge is replaced by a deterministic scorer (<font face='Courier'>rp2/scoring.py</font>).",
         "Removes judge/model circularity and cost. Checked by an oracle test (the 200 gold labels score 100%), the unit-test suite, and "
         + audit_txt + "."],
        ["D4", "20- and 50-tool contexts add <b>distractors from a pool of 87 tools</b> taken from all six benchmark categories.",
         "A task's native list is 1 (finance), 5 (search) or 32 (map) tools. Gold tool plus at most 2 labelled similar tools are always present; "
         "contexts are nested (5 is a subset of 20 is a subset of 50)."],
        ["D5", "\"Matched budget\" is implemented as (a) equal prompts across conditions and (b) a 5-tool baseline given k=8 samples with majority vote "
               "so its token spend is close to the 50-tool condition.", "Rubric item 2.4: a method that costs more must be compared against a baseline given the same budget."],
        ["D6", "A missing required parameter counts as a parameter error.", "Stricter than the benchmark judge, which only checks parameters that were predicted."],
    ]
    story.append(tbl(dev, [0.8 * cm, 8.4 * cm, W - 9.2 * cm]))

    # ---------------- 2. implemented ----------------
    story.append(P("2. What was implemented", H1))
    story += bullets([
        "<b>Data</b> (<font face='Courier'>scripts/build_subset.py</font>): seeded stratified sample from the benchmark clone, saved to <font face='Courier'>data/subset_200.json</font> with the 87-tool pool; the checkout is self-contained.",
        "<b>Condition builder</b> (<font face='Courier'>rp2/context.py</font>): the only thing that differs between conditions is the tool list. One seeded permutation of the pool per task gives the nested design; order is a seeded shuffle.",
        "<b>Prompts</b> are files (<font face='Courier'>prompts/</font>), identical across conditions; a test asserts this. The padding arm appends neutral text of exactly the length difference between that task's 50- and 5-tool contexts.",
        "<b>Runner</b> (<font face='Courier'>rp2/runner.py</font>): provider adapters for Anthropic and OpenAI-compatible endpoints, retries with backoff, global rate limit, resume, jobs interleaved across conditions within each run so model drift hits every condition equally. A failed call becomes an <font face='Courier'>api_error</font> record, never a crash.",
        "<b>Scorer and taxonomy</b>: tool_ok (gold or a labelled similar tool), param_ok (gold values compared with numeric, enum, lat/lon (0.1) and token-F1 &ge; 0.5 rules, as in the judge prompt), and nine mutually exclusive failure labels.",
        "<b>Analysis</b>: mean ± SD over runs, paired bootstrap over tasks (10,000 resamples), tokens per correct task, domain and position breakdowns, and an automatically selected traced failure case.",
        "<b>Ablations</b> (each isolates one factor): position of the gold tool (first / last / shuffled at 50 tools); context length (5 tools padded to the 50-tool length); budget (5 tools with self-consistency).",
        f"<b>Own vs borrowed.</b> About {n_loc:,} lines of Python written for this project (runner, conditions, scorer, statistics, report, slides, tests). Borrowed: the benchmark's task data and labels "
        "(github.com/mcp-tool-bench/mcptoolbenchpp, commit 2bd35e5) and the parameter-matching rules from its judge prompt, re-implemented. No benchmark code is imported.",
    ])

    # ---------------- 3. setup ----------------
    story.append(P("3. Experimental setup (pinned)", H1))
    m = cfg["model"]
    if manifest:
        dec = manifest["decoding"]
        models = ", ".join(f"{k} (x{v})" for k, v in (manifest.get("model_strings_returned_by_api") or {}).items()) or "n/a"
        setup = [
            ["Model requested", esc(manifest["model_requested"] or "mock-keyword-v1"), "Model string returned by API", esc(models)],
            ["Provider", esc(manifest["provider"]), "Dates of runs (UTC)", f"{esc(manifest['started_utc'])} to {esc(manifest.get('finished_utc'))}"],
            ["Temperature / top-p", f"{dec['temperature']} / {esc(dec['top_p'])}", "Seed", esc(dec["seed"])],
            ["Runs per condition", f"{manifest['n_runs']} full passes over {manifest['n_tasks']} tasks", "max_tokens", str(dec["max_tokens"])],
            ["Data hash (subset)", manifest["data_sha256"]["subset"][:16], "Repo commit", esc((manifest.get("repo_git_head") or "")[:12] or "not a git checkout")],
        ]
    else:
        setup = [
            ["Model requested", "to be set in configs/config.yaml (exact version string)", "Model string returned by API", "recorded per call in the traces"],
            ["Provider", "anthropic or openai_compat (free-tier or local endpoint)", "Dates of runs", "recorded in manifest.json"],
            ["Temperature / top-p", f"{m['temperature']} / {m['top_p']}", "Seed", "base 1000 + run*100000 + task index, where the provider supports seeds"],
            ["Runs per condition", f"{cfg['experiment']['n_runs']} full passes over 200 tasks", "max_tokens", str(m["max_tokens"])],
        ]
    story.append(tbl(setup, [3.0 * cm, 5.4 * cm, 3.6 * cm, W - 12.0 * cm], header=False))
    cfg_mock = copy.deepcopy(cfg)
    cfg_mock["model"]["provider"] = "mock"
    est = Runner(cfg_mock, "/tmp/rp2_report_est", [c["id"] for c in cfg["conditions"]]).estimate()
    t1 = sum(est[c]["total_input_tokens"] for c in ("c05", "c20", "c50"))
    t_all = sum(e["total_input_tokens"] for e in est.values())
    story.append(P(
        f"Task metric: AST accuracy (tool and parameters correct) and tool-selection accuracy. Cost: model calls, prompt and completion tokens "
        f"(provider-reported) and wall-clock latency per task. Every run writes a full trace (prompts, tool list, raw response, usage, score) to "
        f"<font face='Courier'>traces/</font>; <font face='Courier'>python scripts/aggregate.py</font> regenerates every table from them. "
        f"Planned cost (chars/4 estimate, input tokens): about {t1 / 1e6:.1f}M for the three core conditions and {t_all / 1e6:.1f}M with all ablations over 3 runs.", SMALL))

    # ---------------- 4. results ----------------
    story.append(P("4. Results", H1))
    if summary is None:
        story.append(tbl([["<b>Pending.</b> Results table, accuracy plot, cost plot and failure-composition plot are generated by "
                           "<font face='Courier'>scripts/aggregate.py</font> and inserted here by <font face='Courier'>scripts/make_report.py</font>."]],
                         [W], header=False))
    else:
        S = summary["conditions"]
        rows = [["Condition", "Tool acc %", "AST acc %", "Param acc % | tool", "In tok / task", "Calls / task", "Latency s", "Tok / correct"]]
        for c in [c for c in ORDER if c in S]:
            s = S[c]
            rows.append([LABELS[c], mean_sd(s["tool_acc"]), mean_sd(s["ast_acc"]), mean_sd(s["param_acc_given_tool"]),
                         mean_sd(s["input_tokens"], False, 0), mean_sd(s["model_calls"], False, 1),
                         mean_sd(s["latency_s"], False, 2),
                         "n/a" if not s["tokens_per_correct"] else f"{s['tokens_per_correct']:.0f}"])
        story.append(tbl(rows, [3.7 * cm, 1.9 * cm, 1.9 * cm, 2.3 * cm, 2.1 * cm, 1.6 * cm, 1.6 * cm, W - 15.1 * cm]))
        n_runs = max(s["n_runs"] for s in S.values())
        story.append(P(f"Mean ± SD over {n_runs} runs of the 200-task subset. SD is across runs; uncertainty across tasks is in the paired bootstrap intervals below.", SMALL))
        imgs = []
        for k in ("accuracy", "failures"):
            fp = summary["figures"].get(k)
            if fp:
                imgs.append(Image(os.path.join(run_dir, fp), width=W / 2 - 0.2 * cm, height=(W / 2 - 0.2 * cm) * (3.4 / 5.6 if k == "failures" else 3.2 / 5.2)))
        if imgs:
            story.append(Table([imgs], colWidths=[W / 2] * len(imgs)))

    # ---------------- 5. analysis ----------------
    story.append(P("5. Analysis", H1))
    if summary is None:
        story.append(tbl([["<b>Pending.</b> Findings (effect sizes with bootstrap intervals, cost, failure composition, ablations, matched budget) are "
                           "computed from the saved results; at least one failure case is read from its trace and shown here."]], [W], header=False))
    else:
        find, interp = analysis(summary)
        story += bullets([esc(f) for f in find])
        if interp:
            story.append(P("<b>Reading of the evidence</b> (rule-based from the numbers above; verify against the traces):", BODY))
            story += bullets([esc(i) for i in interp])
        if fcase:
            a, b = fcase["c05_success"], fcase["c50_failure"]
            sb = b["score"]
            call = b["samples"][0]["tool_calls"][0] if b["samples"][0]["tool_calls"] else None
            picked = sb["pred_name"]
            lines = [
                f"<b>Traced failure case</b> (task {a['uuid'][:8]}, {a['domain']}; solved in every 5-tool run, failed in every 50-tool run).",
                f"Query: <i>{esc(b['user'])}</i>. Gold tool: <font face='Courier'>{esc(b['label']['name'])}</font>, "
                f"gold arguments <font face='Courier'>{esc(json.dumps(b['label']['input'], ensure_ascii=False))[:160]}</font>.",
                f"50-tool run {b['run']}: called <font face='Courier'>{esc(picked)}</font> "
                f"with <font face='Courier'>{esc(json.dumps(sb['pred_args'], ensure_ascii=False))[:140]}</font>; failure label "
                f"<b>{esc(sb['failure'])}</b>, gold tool at position {b['gold_position']} of {b['n_tools']}. {esc(sb['detail'])}",
            ]
            if picked:
                lines.append(f"Description of the tool it picked: <i>{esc(describe(pool, picked))}</i>")
            lines.append(f"Description of the gold tool: <i>{esc(describe(pool, b['label']['name']))}</i>")
            lines.append("<b>Cause (write after reading the trace):</b> ______________________________________________")
            story.append(KeepTogether([tbl([[l] for l in lines], [W], header=False, zebra=False)]))

    # ---------------- 6. limitations ----------------
    story.append(P("6. Limitations and four more weeks", H1))
    story += bullets([
        "One model and one temperature: conclusions are about this model on this date, not about tool count in general. Single-step tasks only; no Pass@K or live MCP execution.",
        "Labels are the benchmark's. A \"wrong tool in the same domain\" may be a valid alternative that the labelled <font face='Courier'>similar_tools</font> list misses, which inflates same-domain errors; the traced case and the 20-task audit are the guard.",
        "Distractors come from other domains and are mostly easy to dismiss, so the 50-tool condition is gentler than a marketplace of near-duplicate tools. Parameter matching is lenient (containment and token F1), as in the benchmark. The public benchmark may be in the model's training data.",
        "<b>With four more weeks:</b> several models and sizes; distractors chosen by embedding similarity to the gold tool; a retrieval baseline that shows the top-k tools; multi-step chains built by composing the labelled calls; live MCP execution for Pass@K; failure labels audited by a second person.",
    ])

    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.3 * cm,
                            bottomMargin=1.5 * cm, title="RP2 report U23AI052", author="U23AI052")
    doc.build(story, onFirstPage=watermark, onLaterPages=watermark)
    from pypdf import PdfReader
    n = len(PdfReader(out).pages)
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", default=None)
    ap.add_argument("--out", default=os.path.join(ROOT, "report", "RP2_report.pdf"))
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    n = build(a.run_dir, a.out)
    print(f"wrote {a.out}: {n} page(s)" + ("  (OVER the 4-page limit!)" if n > 4 else ""))
    return 0 if n <= 4 else 1


if __name__ == "__main__":
    sys.exit(main())
