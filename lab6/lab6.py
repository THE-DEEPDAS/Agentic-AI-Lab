import random

documents = {
    "ModelA": {"title": "ModelA Benchmark Results", "model": "ModelA", "benchmark": "Bench-1", "accuracy": 91.2, "parameters": 7},
    "ModelB": {"title": "ModelB Benchmark Results", "model": "ModelB", "benchmark": "Bench-1", "accuracy": 89.5, "parameters": 8},
    "ModelA2": {"title": "ModelA Benchmark Result", "model": "ModelA2", "benchmark": "Bench-2", "accuracy": 93.1, "parameters": 7},
    "ModelC": {"title": "ModelC Benchmark Results", "model": "ModelC", "benchmark": "Bench-2", "accuracy": 90.7, "parameters": 6},
    "ModelD": {"title": "ModelD Benchmark Results", "model": "ModelD", "benchmark": "Bench-3", "accuracy": 88.4, "parameters": 5},
    "ModelE": {"title": "ModelE Benchmark Results", "model": "ModelE", "benchmark": "Bench-3", "accuracy": 92.6, "parameters": 10},
    "ModelF": {"title": "ModelF Benchmark Results", "model": "ModelF", "benchmark": "Bench-4", "accuracy": 94.0, "parameters": 12},
    "ModelG": {"title": "ModelG Benchmark Results", "model": "ModelG", "benchmark": "Bench-4", "accuracy": 91.8, "parameters": 9},
}

tasks = [
    ("ModelA", "ModelB"), ("ModelA2", "ModelC"), ("ModelD", "ModelE"), ("ModelF", "ModelG"),
    ("ModelA", "ModelC"), ("ModelB", "ModelD"), ("ModelE", "ModelF"), ("ModelC", "ModelG")
]

ROLES = {
    "Manager": {"resp": "Decompose, delegate, route, final answer", "tools": [], "to": ["Researcher", "Writer", "Reviewer", "User"], "out": ["subtasks"]},
    "Researcher": {"resp": "Find, read, calculate", "tools": ["search", "read_doc", "calculator"], "to": ["Manager"], "out": ["values", "sources", "result"]},
    "Writer": {"resp": "Write cited answer <=60 words", "tools": [], "to": ["Manager"], "out": ["draft", "citations"]},
    "Reviewer": {"resp": "Check values, winner, citations", "tools": ["read_doc"], "to": ["Manager"], "out": ["verdict", "reasons"]},
}

def specs():
    print("\nROLE SPECS")
    for r, s in ROLES.items():
        print(r, "|", s["resp"], "| tools", s["tools"], "| to", s["to"], "| out", s["out"])

def search(q):
    q = q.lower().split()
    out = []
    for k, v in documents.items():
        text = (v["title"] + " " + v["model"] + " " + v["benchmark"]).lower()
        if any(w in text for w in q):
            out.append(k)
    return out

def read_doc(i):
    return documents.get(i)

def calc(a, b):
    if a > b: return {"winner": "first", "diff": round(a - b, 2)}
    if b > a: return {"winner": "second", "diff": round(b - a, 2)}
    return {"winner": "tie", "diff": 0}

def validate(role, tool=None, to=None, msg=None, v=None):
    ok = True
    if tool is not None and tool not in ROLES[role]["tools"]:
        ok = False
        if v is not None: v.append(f"{role} bad tool {tool}")
    if to is not None and to not in ROLES[role]["to"]:
        ok = False
        if v is not None: v.append(f"{role} bad recipient {to}")
    if msg is not None:
        for f in ROLES[role]["out"]:
            if f not in msg:
                ok = False
                if v is not None: v.append(f"{role} missing {f}")
    return ok

def researcher(m1, m2, v):
    tr = [f"Researcher: compare {m1} and {m2}"]
    validate("Researcher", tool="search", v=v); search(m1); search(m2)
    validate("Researcher", tool="read_doc", v=v)
    d1, d2 = read_doc(m1), read_doc(m2)
    validate("Researcher", tool="calculator", v=v)
    c = calc(d1["accuracy"], d2["accuracy"])
    win = d1["model"] if c["winner"] == "first" else d2["model"] if c["winner"] == "second" else "Tie"
    res = {"model1": d1["model"], "model2": d2["model"], "accuracy1": d1["accuracy"], "accuracy2": d2["accuracy"], "winner": win, "difference": c["diff"]}
    msg = {"values": {m1: d1["accuracy"], m2: d2["accuracy"]}, "sources": [m1, m2], "result": res}
    validate("Researcher", to="Manager", msg=msg, v=v)
    tr += [f"Found {d1['accuracy']}% vs {d2['accuracy']}%", f"Winner {win}, diff {c['diff']}"]
    return msg, tr

def writer(r, fault=False):
    x = r["result"]
    cites = list(r["sources"])
    if fault and len(cites) > 1: cites = cites[:1]   # FAULT: drop one citation
    draft = f"{x['model1']} achieved {x['accuracy1']}% accuracy, while {x['model2']} achieved {x['accuracy2']}%. {x['winner']} performed better on the benchmark."
    return {"draft": " ".join(draft.split()[:60]), "citations": cites}

def reviewer(w, r, v):
    reasons = []
    validate("Reviewer", tool="read_doc", v=v)
    for s in w["citations"]:
        if read_doc(s) is None: reasons.append(f"Bad source {s}")
    x = r["result"]
    d1, d2 = read_doc(x["model1"]), read_doc(x["model2"])
    c = calc(d1["accuracy"], d2["accuracy"])
    exp = d1["model"] if c["winner"] == "first" else d2["model"] if c["winner"] == "second" else "Tie"
    if x["winner"] != exp: reasons.append("Winner wrong")
    if len(w["draft"].split()) > 60: reasons.append("Over 60 words")
    if set(w["citations"]) != {x["model1"], x["model2"]}: reasons.append("Citations wrong")
    verdict = "PASS" if not reasons else "REVISE"
    if verdict == "PASS": reasons = ["Values, winner and citations correct."]
    msg = {"verdict": verdict, "reasons": reasons}
    validate("Reviewer", to="Manager", msg=msg, v=v)
    return msg

def algorithm1(m1, m2, seed=0):
    random.seed(seed)
    v, tr = [], [] # violations, trace
    calls = {"Manager": 1, "Researcher": 0, "Writer": 0, "Reviewer": 0}
    revs = 0
    validate("Manager", to="Researcher", msg={"subtasks": ["find", "read", "compare"]}, v=v)
    tr.append("Manager -> Researcher: find both models and compare.")
    calls["Researcher"] += 1
    research, rt = researcher(m1, m2, v); tr += rt; tr.append("Researcher -> Manager: finding sent.")
    validate("Manager", to="Writer", v=v); tr.append("Manager -> Writer: create cited answer.")
    calls["Writer"] += 1
    draft = writer(research, fault=(m1 == "ModelA2" or m2 == "ModelA2"))
    validate("Writer", to="Manager", msg=draft, v=v); tr.append("Writer -> Manager: draft sent.")
    validate("Manager", to="Reviewer", v=v); tr.append("Manager -> Reviewer: check values, winner, citations.")
    calls["Reviewer"] += 1
    review = reviewer(draft, research, v); tr.append(f"Reviewer -> Manager: {review['verdict']}")
    while review["verdict"] == "REVISE" and revs < 2:
        revs += 1
        tr.append(f"Manager: revision round {revs} -> Writer")
        calls["Writer"] += 1
        draft = writer(research, fault=False)
        validate("Writer", to="Manager", msg=draft, v=v)
        calls["Reviewer"] += 1
        review = reviewer(draft, research, v)
        tr.append(f"Reviewer -> Manager: {review['verdict']}")
    tr.append("Manager -> User: final answer delivered.")
    return {"success": review["verdict"] == "PASS", "draft": draft, "trace": tr, "calls": calls, "violations": v, "revisions": revs}

def generalist(m1, m2):
    d1, d2 = read_doc(m1), read_doc(m2)
    c = calc(d1["accuracy"], d2["accuracy"])
    win = d1["model"] if c["winner"] == "first" else d2["model"] if c["winner"] == "second" else "Tie"
    draft = f"{d1['model']} achieved {d1['accuracy']}% accuracy, while {d2['model']} achieved {d2['accuracy']}%. {win} performed better on the benchmark."
    return {"success": len(draft.split()) <= 60, "draft": draft, "citations": [m1, m2]}

def algorithm2(m1, m2):
    r = generalist(m1, m2)
    tr = ["Generalist receives complete task.", "Generalist searches/reads/calculates.", "Generalist produces final cited answer."]
    return {"success": r["success"], "draft": r["draft"], "trace": tr, "calls": {"Generalist": 1}, "violations": [], "revisions": 0}

def print_trace(t):
    for i, x in enumerate(t, 1): print(f"{i}. {x}")

def main_experiment():
    print("#" * 70)
    print("IA462 EXPERIMENT 6 - ROLE-BASED LLM AGENT DESIGN")
    print("#" * 70)
    specs()

    seeds = list(range(10))
    total = len(seeds) * len(tasks)

    # --- run silently to collect stats ---
    ts = gs = tc = gc = tv = tr = 0
    for seed in seeds:
        for m1, m2 in tasks:
            team = algorithm1(m1, m2, seed)
            gen = algorithm2(m1, m2)
            ts += team["success"]; gs += gen["success"]
            tc += sum(team["calls"].values()); gc += 1
            tv += len(team["violations"]); tr += team["revisions"]

    # --- print one representative trace with a revision ---
    print("\n" + "=" * 70)
    print("REPRESENTATIVE TRACE WITH REVISION (Task: ModelA2 vs ModelC, seed=0)")
    print("=" * 70)
    team = algorithm1("ModelA2", "ModelC", seed=0)
    print("ROLE-BASED TEAM TRACE:")
    print_trace(team["trace"])
    print("\nResult: success =", team["success"], "| calls =", team["calls"], "| violations =", len(team["violations"]), "| revisions =", team["revisions"])

    # also show generalist for same task (no revision)
    gen = algorithm2("ModelA2", "ModelC")
    print("\nGENERALIST TRACE:")
    print_trace(gen["trace"])
    print("Result: success =", gen["success"], "| calls =", gen["calls"])

    # --- final summary ---
    print("\n" + "=" * 70)
    print("MAIN SUMMARY (over 10 seeds x 8 tasks = 80 tasks)")
    print("=" * 70)
    print("Total tasks:", total)
    print("Team success:", f"{ts}/{total}")
    print("Generalist success:", f"{gs}/{total}")
    print("Avg team calls:", round(tc / total, 2))
    print("Avg generalist calls:", round(gc / total, 2))
    print("Total violations:", tv)
    print("Avg revisions:", round(tr / total, 2))

def no_reviewer_team(m1, m2):
    d1, d2 = read_doc(m1), read_doc(m2)
    c = calc(d1["accuracy"], d2["accuracy"])
    win = d1["model"] if c["winner"] == "first" else d2["model"] if c["winner"] == "second" else "Tie"
    draft = f"{d1['model']} achieved {d1['accuracy']}% accuracy, while {d2['model']} achieved {d2['accuracy']}%. {win} performed better."
    return {"success": win != "Tie" and len(draft.split()) <= 60, "calls": 2, "violations": 0}

def exercise1():
    print("\n" + "#" * 70)
    print("EXERCISE 1 - ABLATION STUDY")
    print("#" * 70)
    seeds = list(range(10))
    total = len(seeds) * len(tasks)
    fs = ab = gs = fc = ac = gc = fv = av = 0
    for seed in seeds:
        for m1, m2 in tasks:
            full = algorithm1(m1, m2, seed)
            abl = no_reviewer_team(m1, m2)
            gen = algorithm2(m1, m2)
            fs += full["success"]; ab += abl["success"]; gs += gen["success"]
            fc += sum(full["calls"].values()); ac += abl["calls"]; gc += 1
            fv += len(full["violations"]); av += abl["violations"]
    print("Full team:", f"{fs}/{total}", "| avg calls", round(fc / total, 2), "| violations", fv)
    print("No Reviewer + merged Researcher/Writer:", f"{ab}/{total}", "| avg calls", round(ac / total, 2), "| violations", av)
    print("Generalist:", f"{gs}/{total}", "| avg calls", round(gc / total, 2))

def exercise2():
    print("\n" + "#" * 70)
    print("EXERCISE 2 - ROLE VIOLATION / INJECTION")
    print("#" * 70)
    cases = [
        (1, "Writer told to search"),
        (2, "Researcher told to send to User"),
        (3, "Reviewer told to fix draft itself"),
        (4, "Researcher told to report false value"),
        (5, "Researcher told to omit sources"),
    ]
    print("\nA. PERMISSIONS ONLY IN PROMPTS")
    for n, d in cases:
        print(f"Case {n}: {d} | blocked=0 | took effect=1")
    print("\nB. validate() ENFORCED")
    for n, d in cases:
        v = []
        if n == 1:
            blocked = not validate("Writer", tool="search", v=v)
        elif n == 2:
            blocked = not validate("Researcher", to="User", v=v)
        elif n == 3:
            blocked = not validate("Reviewer", to="Writer", v=v)
        elif n == 4:
            msg = {"values": {"ModelA": 99.0}, "sources": ["ModelA", "ModelB"], "result": {"model1": "ModelA", "model2": "ModelB", "winner": "ModelA"}}
            blocked = not validate("Researcher", msg=msg, v=v)
        else:
            msg = {"values": {"ModelA": 91.2, "ModelB": 89.5}, "result": {"model1": "ModelA", "model2": "ModelB", "winner": "ModelA"}}
            blocked = not validate("Researcher", msg=msg, v=v)
        print(f"Case {n}: {d} | blocked={blocked} | took effect={not blocked} | violations={v}")
    print("Note: validate() cannot stop Case 4 if the false value has a valid schema.")

if __name__ == "__main__":
    main_experiment()
    exercise1()
    exercise2()