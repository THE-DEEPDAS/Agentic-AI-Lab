"""Tool-count manipulation. This is the ONLY thing that differs between conditions.

For a task and a condition the context is:
    core        = the gold tool + up to MAX_SIMILAR_IN_CORE of the benchmark's labelled
                  `similar_tools` (they are the task's natural confusable alternatives)
    distractors = tools drawn from the pool of all 87 benchmark tools (all six categories)
    members     = core + first (n_tools - len(core)) distractors

Distractors come from ONE seeded permutation per task, so the n=5 distractors are a prefix
of the n=20 distractors, which are a prefix of the n=50 distractors (nested design): going
from 5 to 50 only ADDS tools, nothing is swapped out. Order within the list is a seeded
shuffle (or gold-first / gold-last for the position-control ablation).
"""
import json
import random

MAX_SIMILAR_IN_CORE = 2


def accepted_names(task):
    label = task["label"]
    return {label["name"]} | {s["name"] for s in label.get("similar_tools", [])}


def _native_by_name(task):
    return {t["name"]: t for t in task["native_tools"]}


def build_context(task, cond, pool, design_seed):
    """Return {'tools': [tool dicts], 'gold': name, 'n_actual': int, 'domains': {name: domain}}."""
    native = _native_by_name(task)
    gold = task["label"]["name"]
    core = [native[gold]]
    for s in task["label"].get("similar_tools", []):
        if len(core) - 1 >= MAX_SIMILAR_IN_CORE:
            break
        if s["name"] in native and s["name"] != gold:
            core.append(native[s["name"]])
    core_names = {t["name"] for t in core}

    candidates = [p for p in pool if p["name"] not in core_names]
    rng_d = random.Random(f"{design_seed}:{task['uuid']}:distractors")
    rng_d.shuffle(candidates)
    n_fill = max(0, cond["n_tools"] - len(core))
    members = core + [p["tool"] for p in candidates[:n_fill]]

    rng_o = random.Random(f"{design_seed}:{task['uuid']}:{cond['n_tools']}:{cond.get('order', 'shuffle')}")
    rng_o.shuffle(members)
    order = cond.get("order", "shuffle")
    if order in ("gold_first", "gold_last"):
        idx = next(i for i, t in enumerate(members) if t["name"] == gold)
        g = members.pop(idx)
        members.insert(0 if order == "gold_first" else len(members), g)

    domains = {p["name"]: p["domain"] for p in pool}
    return {
        "tools": members,
        "gold": gold,
        "n_actual": len(members),
        "gold_position": next(i for i, t in enumerate(members) if t["name"] == gold),
        "domains": domains,
    }


def schema_chars(tools):
    return len(json.dumps(tools, ensure_ascii=False))


def make_filler(n_chars, filler_corpus):
    """Neutral text of exactly n_chars characters (tiled corpus), for the length-control arm."""
    if n_chars <= 0:
        return ""
    reps = n_chars // len(filler_corpus) + 1
    return (filler_corpus * reps)[:n_chars]
