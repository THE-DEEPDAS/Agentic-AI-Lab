"""Tests for the pieces that decide whether a number in the report can be trusted.

Run:  python -m pytest -q tests
"""
import copy
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rp2.common import condition_map, load_config, load_pool, load_tasks  # noqa: E402
from rp2.context import accepted_names, build_context, make_filler, schema_chars  # noqa: E402
from rp2.runner import Runner  # noqa: E402
from rp2.scoring import FAILURES, score_call, values_match  # noqa: E402

CFG = load_config()
TASKS = load_tasks(CFG)
POOL = load_pool(CFG)
CMAP = condition_map(CFG)
SC = CFG["scoring"]


def ctx(task, cid):
    return build_context(task, CMAP[cid], POOL, CFG["experiment"]["design_seed"])


def call(name, args):
    return {"error": None, "text": "", "tool_calls": [{"name": name, "arguments": args}]}


# ---------------- data ----------------
def test_subset_shape():
    assert len(TASKS) == 200
    assert sorted({t["domain"] for t in TASKS}) == ["finance", "map", "search"]
    assert len({t["uuid"] for t in TASKS}) == 200
    assert len(POOL) == 87


# ---------------- context construction ----------------
@pytest.mark.parametrize("i", range(0, 200, 7))
def test_nested_design_and_gold_present(i):
    t = TASKS[i]
    c5, c20, c50 = ctx(t, "c05"), ctx(t, "c20"), ctx(t, "c50")
    n5, n20, n50 = ({x["name"] for x in c["tools"]} for c in (c5, c20, c50))
    assert n5 <= n20 <= n50, "going from 5 to 50 tools must only ADD tools"
    assert t["label"]["name"] in n5
    assert len(c50["tools"]) == 50 and len(c20["tools"]) == 20
    assert len(c5["tools"]) == 5
    assert len(n5) == len(c5["tools"]), "no duplicate tools in a context"


def test_context_deterministic():
    assert [x["name"] for x in ctx(TASKS[3], "c50")["tools"]] == [x["name"] for x in ctx(TASKS[3], "c50")["tools"]]


def test_position_arms_differ_only_in_order():
    t = TASKS[10]
    a, f, l = ctx(t, "c50"), ctx(t, "c50_goldfirst"), ctx(t, "c50_goldlast")
    assert {x["name"] for x in a["tools"]} == {x["name"] for x in f["tools"]} == {x["name"] for x in l["tools"]}
    assert f["gold_position"] == 0 and l["gold_position"] == 49


def test_prompts_identical_across_conditions():
    cfg = copy.deepcopy(CFG)
    cfg["model"]["provider"] = "mock"
    r = Runner(cfg, "/tmp/rp2_test_unused", ["c05", "c20", "c50", "c05_padded"], limit=3)
    t = r.tasks[0]
    base = r.system_for(t, "c05")
    assert base == r.system_for(t, "c20") == r.system_for(t, "c50")
    padded = r.system_for(t, "c05_padded")
    assert padded.startswith(base) and len(padded) > len(base)
    # padding matches the c50 context length for this task
    extra = schema_chars(r.context(t, "c50")["tools"]) - schema_chars(r.context(t, "c05_padded")["tools"])
    assert len(padded) - len(base) - len("\n\nBackground notes (not relevant to the task):\n") == extra


def test_filler_exact_length():
    corpus = "abc def "
    assert len(make_filler(1000, corpus)) == 1000 and make_filler(0, corpus) == ""


# ---------------- scorer: oracle and perturbations ----------------
def test_oracle_scores_100_percent():
    for t in TASKS:
        c = ctx(t, "c50")
        r = score_call(t, c, call(t["label"]["name"], dict(t["label"]["input"])), SC)
        assert r["ast_ok"], (t["uuid"], r)


def _first(domain):
    return next(t for t in TASKS if t["domain"] == domain)


def test_wrong_tool_cross_domain():
    t = _first("finance")
    c = ctx(t, "c50")
    other = next(x["name"] for x in c["tools"] if c["domains"][x["name"]] != "finance")
    r = score_call(t, c, call(other, {}), SC)
    assert not r["tool_ok"] and r["failure"] == "wrong_tool_cross_domain"


def test_wrong_tool_same_domain():
    t = next(t for t in TASKS if t["domain"] == "map")
    c = ctx(t, "c50")
    acc = accepted_names(t)
    same = next(x["name"] for x in c["tools"] if c["domains"][x["name"]] == "map" and x["name"] not in acc)
    r = score_call(t, c, call(same, {}), SC)
    assert r["failure"] == "wrong_tool_same_domain"


def test_invalid_name_no_call_malformed_and_api_error():
    t = TASKS[0]
    c = ctx(t, "c05")
    assert score_call(t, c, call("does_not_exist", {}), SC)["failure"] == "invalid_tool_name"
    assert score_call(t, c, {"error": None, "text": "I think...", "tool_calls": []}, SC)["failure"] == "no_tool_call"
    assert score_call(t, c, call(t["label"]["name"], "{not json"), SC)["failure"] == "malformed_arguments"
    assert score_call(t, c, {"error": "RateLimit", "text": "", "tool_calls": []}, SC)["failure"] == "api_error"


def test_missing_required_and_wrong_value():
    t = _first("finance")
    c = ctx(t, "c05")
    good = dict(t["label"]["input"])
    r = score_call(t, c, call(t["label"]["name"], {k: v for k, v in good.items() if k != "symbol_list"}), SC)
    assert r["failure"] == "missing_required_param"
    bad = dict(good, symbol_list=["ZZZZ"])
    r = score_call(t, c, call(t["label"]["name"], bad), SC)
    assert r["tool_ok"] and not r["ast_ok"] and r["failure"] == "wrong_param_value"


def test_last_call_is_judged_and_extra_calls_recorded():
    t = _first("finance")
    c = ctx(t, "c05")
    res = {"error": None, "text": "", "tool_calls": [
        {"name": "wrong", "arguments": {}}, {"name": t["label"]["name"], "arguments": dict(t["label"]["input"])}]}
    r = score_call(t, c, res, SC)
    assert r["ast_ok"] and r["extra_calls"] == 1


def test_every_failure_label_is_reachable():
    assert len(set(FAILURES)) == len(FAILURES) == 9


# ---------------- parameter comparison rules ----------------
@pytest.mark.parametrize("pred,gold,key,prop,ok", [
    ("48.86", "48.8566", "latitude", None, True),      # within 0.1
    ("49.5", "48.8566", "latitude", None, False),
    ("48.86,2.35", "48.8566,2.3522", "location", None, True),
    ("advanced", "basic", "search_depth", {"enum": ["basic", "advanced"]}, False),
    ("Basic", "basic", "search_depth", {"enum": ["basic", "advanced"]}, True),
    ("latest healthcare reforms UK", "healthcare reforms", "query", None, True),
    ("pizza recipes", "healthcare reforms", "query", None, False),
    (["ABBV"], ["ABBV"], "symbol_list", None, True),
    (["abbv", "MSFT"], ["ABBV"], "symbol_list", None, False),
    (7, 7.0, "days", None, True),
    (True, False, "include_images", None, False),
    ("北京", "北京市", "address", None, True),
])
def test_values_match(pred, gold, key, prop, ok):
    assert values_match(pred, gold, key, prop, 0.5, 0.1) is ok


# ---------------- runner: end to end, resume, error handling ----------------
def _run(provider, tmp_path, limit=12, runs=2, conds=("c05", "c50")):
    cfg = copy.deepcopy(CFG)
    cfg["model"]["provider"] = provider
    r = Runner(cfg, str(tmp_path), list(conds), runs=runs, limit=limit, workers=4, rps=0)
    return r, r.run(progress_every=10**9)


def test_runner_oracle_perfect_and_resume(tmp_path):
    r, s = _run("mock_oracle", tmp_path)
    assert s["jobs"] == 12 * 2 * 2 and s["failed"] == 0
    recs = [json.loads(l) for p in tmp_path.glob("traces/*/run*.jsonl") for l in open(p)]
    assert len(recs) == 48 and all(x["score"]["ast_ok"] for x in recs)
    assert all(x["mock"] for x in recs)
    man = json.load(open(tmp_path / "manifest.json"))
    assert man["NOT_A_RESULT"] is True
    # resume: nothing left to do, nothing duplicated
    _, s2 = _run("mock_oracle", tmp_path)
    assert s2["jobs"] == 0
    assert len([1 for p in tmp_path.glob("traces/*/run*.jsonl") for _ in open(p)]) == 48


def test_runner_survives_provider_failures(tmp_path):
    cfg = copy.deepcopy(CFG)
    cfg["model"].update(provider="mock_flaky", max_retries=0)
    r = Runner(cfg, str(tmp_path), ["c05"], runs=1, limit=40, workers=4, rps=0)
    s = r.run(progress_every=10**9)
    recs = [json.loads(l) for p in tmp_path.glob("traces/*/run*.jsonl") for l in open(p)]
    assert len(recs) == 40, "a failed call must still produce a trace record"
    errs = [x for x in recs if x["score"]["failure"] == "api_error"]
    assert 0 < len(errs) < 40 and all(not x["score"]["ast_ok"] for x in errs)


def test_self_consistency_budget_accounting(tmp_path):
    r, _ = _run("mock", tmp_path, limit=5, runs=1, conds=("c05", "c05_sc"))
    recs = {(x["condition"], x["uuid"]): x for p in tmp_path.glob("traces/*/run*.jsonl")
            for x in map(json.loads, open(p))}
    sc = next(v for k, v in recs.items() if k[0] == "c05_sc")
    k = CMAP["c05_sc"]["self_consistency_k"]
    assert sc["model_calls"] == k and len(sc["samples"]) == k
    base = recs[("c05", sc["uuid"])]
    assert sc["input_tokens"] == pytest.approx(base["input_tokens"] * k, rel=0.05)


# ---------------- provider adapters (parsing paths, no network) ----------------
def test_anthropic_adapter_parses_tool_use_and_usage():
    from types import SimpleNamespace as NS
    from rp2.models import AnthropicProvider
    seen = {}

    def create(**kw):
        seen.update(kw)
        return NS(content=[NS(type="text", text="ok"), NS(type="tool_use", name="search", input={"query": "x"})],
                  usage=NS(input_tokens=123, output_tokens=7), model="claude-test-1")

    p = AnthropicProvider.__new__(AnthropicProvider)
    p.model, p.client = "claude-test-1", NS(messages=NS(create=create))
    tools = [{"name": "search", "description": "d", "input_schema": {"type": "object", "properties": {}}}]
    r = p.chat("sys", "usr", tools, 0.7, 1.0, None, 64)
    assert r["tool_calls"] == [{"name": "search", "arguments": {"query": "x"}}]
    assert r["usage"] == {"input_tokens": 123, "output_tokens": 7, "estimated": False}
    assert "top_p" not in seen and seen["temperature"] == 0.7 and seen["tools"][0]["name"] == "search"


def test_openai_adapter_parses_tool_calls_and_sends_seed():
    from types import SimpleNamespace as NS
    from rp2.models import OpenAICompatProvider
    seen = {}

    def create(**kw):
        seen.update(kw)
        call = NS(function=NS(name="search", arguments='{"query": "x"}'))
        return NS(choices=[NS(message=NS(content=None, tool_calls=[call]))],
                  usage=NS(prompt_tokens=200, completion_tokens=9), model="gpt-test-2")

    p = OpenAICompatProvider.__new__(OpenAICompatProvider)
    p.model, p.client = "gpt-test-2", NS(chat=NS(completions=NS(create=create)))
    tools = [{"name": "search", "description": "d", "input_schema": {"type": "object", "properties": {}}}]
    r = p.chat("sys", "usr", tools, 0.7, 1.0, 1234, 64)
    assert r["tool_calls"] == [{"name": "search", "arguments": '{"query": "x"}'}]
    assert seen["seed"] == 1234 and seen["top_p"] == 1.0 and seen["tools"][0]["function"]["name"] == "search"
    # string arguments are parsed by the scorer
    t = _first("search")
    c = ctx(t, "c05")
    good = score_call(t, c, {"error": None, "text": "", "tool_calls": [
        {"name": t["label"]["name"], "arguments": json.dumps(t["label"]["input"])}]}, SC)
    assert good["ast_ok"]


def test_real_provider_refuses_without_model_name():
    from rp2.models import make_provider
    with pytest.raises(SystemExit):
        make_provider({"provider": "openai_compat", "name": None})
