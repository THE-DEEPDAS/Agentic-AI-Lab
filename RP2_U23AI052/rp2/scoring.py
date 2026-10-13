"""Deterministic AST-style scoring and failure taxonomy. No LLM judge is used.

Metrics for one task (all booleans):
    tool_ok   the (last) predicted tool is the labelled tool or one of its labelled similar_tools
    param_ok  tool_ok AND no required parameter missing AND every predicted parameter that also
              appears in the label agrees with it (parameters absent from the label are skipped,
              the same rule as the benchmark's judge prompt)
    ast_ok    = param_ok  (the benchmark's "AST accuracy": right tool with right parameters)

Failure taxonomy (exactly one label per failed task, first match wins):
    api_error                provider call failed after retries
    no_tool_call             model produced text and no tool call
    invalid_tool_name        called a tool that was not in the context (hallucinated name)
    malformed_arguments      arguments could not be parsed into a JSON object
    wrong_tool_same_domain   picked an in-context tool of the task's own domain that is not accepted
    wrong_tool_cross_domain  picked a distractor from another domain
    missing_required_param   right tool, a required parameter absent
    schema_violation         right tool, parameter wrong type / unknown / not allowed by the schema
    wrong_param_value        right tool, schema-valid, but a value disagrees with the label
"""
import json
import math
import re
import unicodedata

import jsonschema

from .context import accepted_names

FAILURES = [
    "api_error",
    "no_tool_call",
    "invalid_tool_name",
    "malformed_arguments",
    "wrong_tool_same_domain",
    "wrong_tool_cross_domain",
    "missing_required_param",
    "schema_violation",
    "wrong_param_value",
]

_LATLON = re.compile(r"(^|_)(lat|lon|lng|latitude|longitude)", re.I)
_PAIR = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")
_TOKEN = re.compile(r"[a-z0-9]+|[一-鿿]")


def _norm(s):
    s = unicodedata.normalize("NFKC", str(s)).casefold().strip()
    return re.sub(r"\s+", " ", s)


def _tokens(s):
    return _TOKEN.findall(_norm(s))


def _f1(a, b):
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 1.0 if ta == tb else 0.0
    from collections import Counter

    ca, cb = Counter(ta), Counter(tb)
    overlap = sum((ca & cb).values())
    if overlap == 0:
        return 0.0
    p, r = overlap / len(ta), overlap / len(tb)
    return 2 * p * r / (p + r)


def _num(x):
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        try:
            return float(x.strip())
        except ValueError:
            return None
    return None


def values_match(pred, gold, key, prop, thr, latlon_tol):
    """Compare one predicted parameter value with the label value."""
    if isinstance(gold, bool) or isinstance(pred, bool):
        return pred == gold
    if isinstance(gold, dict):
        if not isinstance(pred, dict):
            return False
        return all(values_match(pred[k], gold[k], k, (prop or {}).get("properties", {}).get(k), thr, latlon_tol)
                   for k in gold if k in pred)
    if isinstance(gold, list) or isinstance(pred, list):
        g = gold if isinstance(gold, list) else [gold]
        p = pred if isinstance(pred, list) else [pred]
        if len(g) != len(p):
            return False
        item_prop = (prop or {}).get("items") if isinstance(prop, dict) else None
        remaining = list(p)
        for ge in g:
            hit = next((pe for pe in remaining if values_match(pe, ge, key, item_prop, thr, latlon_tol)), None)
            if hit is None:
                return False
            remaining.remove(hit)
        return True
    gn, pn = _num(gold), _num(pred)
    if gn is not None and pn is not None:
        if _LATLON.search(key or ""):
            return abs(gn - pn) <= latlon_tol
        return math.isclose(gn, pn, rel_tol=1e-6, abs_tol=1e-9)
    if isinstance(gold, str) and isinstance(pred, str):
        mg, mp = _PAIR.match(gold), _PAIR.match(pred)
        if mg and mp:
            return all(abs(float(mg.group(i)) - float(mp.group(i))) <= latlon_tol for i in (1, 2))
        if prop and isinstance(prop, dict) and "enum" in prop:
            return _norm(gold) == _norm(pred)
        ng, np_ = _norm(gold), _norm(pred)
        if ng == np_:
            return True
        if len(ng) >= 3 and len(np_) >= 3 and (ng in np_ or np_ in ng):
            return True
        return _f1(gold, pred) >= thr
    return pred == gold


def _schema_errors(args, schema):
    """Return (missing_required, other_violations) for args against the tool's input schema."""
    missing, other = [], []
    try:
        v = jsonschema.Draft7Validator(schema)
        for e in v.iter_errors(args):
            (missing if e.validator == "required" else other).append(e.message)
    except Exception:
        return [], []
    props = schema.get("properties")
    if isinstance(props, dict):
        for k in args:
            if k not in props:
                other.append(f"unknown parameter {k}")
    return missing, other


def score_call(task, ctx, result, cfg_scoring):
    """Score one model response. `result` = {'error','text','tool_calls':[{'name','arguments'}]}."""
    thr = cfg_scoring.get("fuzzy_f1_threshold", 0.5)
    tol = 0.1 if cfg_scoring.get("latlon_decimals", 1) == 1 else 10 ** -cfg_scoring.get("latlon_decimals", 1)
    out = {"tool_ok": False, "param_ok": False, "ast_ok": False, "failure": None,
           "pred_name": None, "pred_args": None, "n_calls": 0, "extra_calls": 0, "detail": ""}

    if result.get("error"):
        out.update(failure="api_error", detail=str(result["error"])[:300])
        return out
    calls = result.get("tool_calls") or []
    out["n_calls"] = len(calls)
    out["extra_calls"] = max(0, len(calls) - 1)
    if not calls:
        out.update(failure="no_tool_call", detail=(result.get("text") or "")[:300])
        return out

    call = calls[-1]  # benchmark rule: only the last call is judged
    name, args = call.get("name"), call.get("arguments")
    out["pred_name"] = name
    in_ctx = {t["name"]: t for t in ctx["tools"]}
    if name not in in_ctx:
        out.update(failure="invalid_tool_name", detail=f"{name!r} not in context")
        return out
    if isinstance(args, str):
        try:
            args = json.loads(args) if args.strip() else {}
        except json.JSONDecodeError as e:
            out.update(failure="malformed_arguments", detail=str(e)[:200])
            return out
    if not isinstance(args, dict):
        out.update(failure="malformed_arguments", detail=f"arguments are {type(args).__name__}")
        return out
    out["pred_args"] = args

    accepted = accepted_names(task)
    if name not in accepted:
        same = ctx["domains"].get(name) == task["domain"]
        out.update(failure="wrong_tool_same_domain" if same else "wrong_tool_cross_domain",
                   detail=f"picked {name}, expected {sorted(accepted)}")
        return out
    out["tool_ok"] = True

    schema = in_ctx[name].get("input_schema") or {}
    missing, other = _schema_errors(args, schema)
    label_in = task["label"].get("input", {})
    props = schema.get("properties", {}) if isinstance(schema, dict) else {}
    mismatched = [k for k in args if k in label_in
                  and not values_match(args[k], label_in[k], k, props.get(k), thr, tol)]
    if missing:
        out.update(failure="missing_required_param", detail="; ".join(missing)[:300])
    elif mismatched:
        # schema problems on the mismatching keys take precedence as the more specific cause
        bad = [m for m in other if any(k in m for k in mismatched)]
        out.update(failure="schema_violation" if bad else "wrong_param_value",
                   detail=(bad[0] if bad else f"differs from label on {mismatched}")[:300])
    else:
        out["param_ok"] = True
        out["ast_ok"] = True
        out["detail"] = ("schema notes: " + "; ".join(other)[:200]) if other else ""
    return out
