# ============================================================
# IA462 - Agentic AI
# Experiment 6
# Role-Based LLM Agent Design with Structured Message Passing
# ============================================================

import random


# ============================================================
# 1. DOCUMENT STORE
# ============================================================

documents = {
    "ModelA": {
        "title": "ModelA Benchmark Results",
        "model": "ModelA",
        "benchmark": "Bench-1",
        "accuracy": 91.2,
        "parameters": 7
    },

    "ModelB": {
        "title": "ModelB Benchmark Results",
        "model": "ModelB",
        "benchmark": "Bench-1",
        "accuracy": 89.5,
        "parameters": 8
    },

    # Nearly duplicate title
    "ModelA2": {
        "title": "ModelA Benchmark Result",
        "model": "ModelA",
        "benchmark": "Bench-2",
        "accuracy": 93.1,
        "parameters": 7
    },

    "ModelC": {
        "title": "ModelC Benchmark Results",
        "model": "ModelC",
        "benchmark": "Bench-2",
        "accuracy": 90.7,
        "parameters": 6
    },

    "ModelD": {
        "title": "ModelD Benchmark Results",
        "model": "ModelD",
        "benchmark": "Bench-3",
        "accuracy": 88.4,
        "parameters": 5
    },

    "ModelE": {
        "title": "ModelE Benchmark Results",
        "model": "ModelE",
        "benchmark": "Bench-3",
        "accuracy": 92.6,
        "parameters": 10
    },

    "ModelF": {
        "title": "ModelF Benchmark Results",
        "model": "ModelF",
        "benchmark": "Bench-4",
        "accuracy": 94.0,
        "parameters": 12
    },

    "ModelG": {
        "title": "ModelG Benchmark Results",
        "model": "ModelG",
        "benchmark": "Bench-4",
        "accuracy": 91.8,
        "parameters": 9
    }
}


# ============================================================
# COMPARISON TASKS
# ============================================================

tasks = [
    ("ModelA", "ModelB"),
    ("ModelA2", "ModelC"),
    ("ModelD", "ModelE"),
    ("ModelF", "ModelG"),
    ("ModelA", "ModelC"),
    ("ModelB", "ModelD"),
    ("ModelE", "ModelF"),
    ("ModelC", "ModelG")
]


# ============================================================
# 2. TOOLS
# ============================================================

def search(query):
    results = []

    query = query.lower()

    for doc_id, doc in documents.items():

        text = (
            doc["title"] + " " +
            doc["model"] + " " +
            doc["benchmark"]
        ).lower()

        if any(word in text for word in query.split()):
            results.append(doc_id)

    return results


def read_doc(doc_id):
    return documents.get(doc_id)


def calculator(a, b):

    if a > b:
        return {
            "winner": "first",
            "difference": round(a - b, 2)
        }

    elif b > a:
        return {
            "winner": "second",
            "difference": round(b - a, 2)
        }

    return {
        "winner": "tie",
        "difference": 0
    }


# ============================================================
# 3. ROLE SPECIFICATIONS
# ============================================================

ROLE_SPECS = {

    "Manager": {
        "responsibility":
            "Decomposes task, delegates work, routes revisions, "
            "and produces final answer.",
        "tools": [],
        "recipients":
            ["Researcher", "Writer", "Reviewer", "User"],
        "output":
            ["subtasks"]
    },

    "Researcher": {
        "responsibility":
            "Finds both entities, reads values and computes result.",
        "tools":
            ["search", "read_doc", "calculator"],
        "recipients":
            ["Manager"],
        "output":
            ["values", "sources", "result"]
    },

    "Writer": {
        "responsibility":
            "Turns finding into a cited answer of at most 60 words.",
        "tools":
            [],
        "recipients":
            ["Manager"],
        "output":
            ["draft", "citations"]
    },

    "Reviewer": {
        "responsibility":
            "Re-reads cited sources and checks values, winner and citations.",
        "tools":
            ["read_doc"],
        "recipients":
            ["Manager"],
        "output":
            ["verdict", "reasons"]
    }
}


def print_role_specs():

    print("\n" + "=" * 70)
    print("ROLE SPECIFICATIONS")
    print("=" * 70)

    for role, spec in ROLE_SPECS.items():

        print("\nROLE:", role)
        print("Responsibility:", spec["responsibility"])
        print("Permitted tools:", spec["tools"])
        print("Permitted recipients:", spec["recipients"])
        print("Required output:", spec["output"])


# ============================================================
# 4. VALIDATION
# ============================================================

def validate(
    role,
    tool=None,
    recipient=None,
    message=None,
    violations=None
):

    valid = True

    # Check tool permission
    if tool is not None:

        if tool not in ROLE_SPECS[role]["tools"]:

            msg = (
                f"{role} attempted unauthorized tool '{tool}'"
            )

            if violations is not None:
                violations.append(msg)

            valid = False

    # Check recipient permission
    if recipient is not None:

        if recipient not in ROLE_SPECS[role]["recipients"]:

            msg = (
                f"{role} attempted unauthorized recipient "
                f"'{recipient}'"
            )

            if violations is not None:
                violations.append(msg)

            valid = False

    # Check required output fields
    if message is not None:

        for field in ROLE_SPECS[role]["output"]:

            if field not in message:

                msg = (
                    f"{role} omitted required output "
                    f"field '{field}'"
                )

                if violations is not None:
                    violations.append(msg)

                valid = False

    return valid


# ============================================================
# 5. RESEARCHER
# ============================================================

def researcher(model1, model2, violations):

    trace = []

    trace.append(
        f"Researcher received task: compare {model1} and {model2}"
    )

    # Search
    validate(
        "Researcher",
        tool="search",
        violations=violations
    )

    search(model1)
    search(model2)

    # Read
    validate(
        "Researcher",
        tool="read_doc",
        violations=violations
    )

    doc1 = read_doc(model1)
    doc2 = read_doc(model2)

    # Calculate
    validate(
        "Researcher",
        tool="calculator",
        violations=violations
    )

    calculation = calculator(
        doc1["accuracy"],
        doc2["accuracy"]
    )

    if calculation["winner"] == "first":
        winner = doc1["model"]

    elif calculation["winner"] == "second":
        winner = doc2["model"]

    else:
        winner = "Tie"

    result = {
        "model1": doc1["model"],
        "model2": doc2["model"],
        "accuracy1": doc1["accuracy"],
        "accuracy2": doc2["accuracy"],
        "winner": winner,
        "difference": calculation["difference"]
    }

    message = {
        "values": {
            model1: doc1["accuracy"],
            model2: doc2["accuracy"]
        },

        "sources": [
            model1,
            model2
        ],

        "result": result
    }

    validate(
        "Researcher",
        recipient="Manager",
        message=message,
        violations=violations
    )

    trace.append(
        f"Researcher found {doc1['accuracy']}% for {doc1['model']} "
        f"and {doc2['accuracy']}% for {doc2['model']}"
    )

    trace.append(
        f"Researcher result: winner = {winner}, "
        f"difference = {calculation['difference']}"
    )

    return message, trace


# ============================================================
# 6. WRITER
# ============================================================

def writer(research):

    result = research["result"]

    draft = (
        f"{result['model1']} achieved {result['accuracy1']}% accuracy, "
        f"while {result['model2']} achieved {result['accuracy2']}%. "
        f"{result['winner']} performed better on the benchmark."
    )

    # Maximum 60 words
    words = draft.split()

    if len(words) > 60:
        draft = " ".join(words[:60])

    return {
        "draft": draft,
        "citations": research["sources"]
    }


# ============================================================
# 7. REVIEWER
# ============================================================

def reviewer(writer_message, research, violations):

    reasons = []

    # Reviewer reads cited documents
    validate(
        "Reviewer",
        tool="read_doc",
        violations=violations
    )

    for source in writer_message["citations"]:

        if read_doc(source) is None:

            reasons.append(
                f"Source {source} cannot be read."
            )

    result = research["result"]

    doc1 = read_doc(result["model1"])
    doc2 = read_doc(result["model2"])

    calculation = calculator(
        doc1["accuracy"],
        doc2["accuracy"]
    )

    if calculation["winner"] == "first":
        expected_winner = doc1["model"]

    elif calculation["winner"] == "second":
        expected_winner = doc2["model"]

    else:
        expected_winner = "Tie"

    # Check winner
    if result["winner"] != expected_winner:

        reasons.append(
            "Winner is incorrect."
        )

    # Check word count
    if len(writer_message["draft"].split()) > 60:

        reasons.append(
            "Draft exceeds 60 words."
        )

    # Check citations
    if set(writer_message["citations"]) != {
        result["model1"],
        result["model2"]
    }:

        reasons.append(
            "Both correct sources are not cited."
        )

    if len(reasons) == 0:

        verdict = "PASS"

        reasons.append(
            "Values, winner and citations are correct."
        )

    else:

        verdict = "REVISE"

    message = {
        "verdict": verdict,
        "reasons": reasons
    }

    validate(
        "Reviewer",
        recipient="Manager",
        message=message,
        violations=violations
    )

    return message


# ============================================================
# ALGORITHM 1
# ROLE-BASED MULTI-AGENT TEAM
# ============================================================

def algorithm1(model1, model2, seed=0):

    random.seed(seed)

    trace = []
    violations = []

    model_calls = {
        "Manager": 1,
        "Researcher": 0,
        "Writer": 0,
        "Reviewer": 0
    }

    revisions = 0

    # --------------------------------------------------------
    # MANAGER -> RESEARCHER
    # --------------------------------------------------------

    trace.append(
        "Manager -> Researcher: find both models and compare values."
    )

    validate(
        "Manager",
        recipient="Researcher",
        message={
            "subtasks": [
                "Find first model",
                "Find second model",
                "Compare accuracies"
            ]
        },
        violations=violations
    )

    # --------------------------------------------------------
    # RESEARCHER
    # --------------------------------------------------------

    model_calls["Researcher"] += 1

    research, researcher_trace = researcher(
        model1,
        model2,
        violations
    )

    trace.extend(researcher_trace)

    trace.append(
        "Researcher -> Manager: finding sent."
    )

    # --------------------------------------------------------
    # MANAGER -> WRITER
    # --------------------------------------------------------

    validate(
        "Manager",
        recipient="Writer",
        violations=violations
    )

    trace.append(
        "Manager -> Writer: create cited answer."
    )

    model_calls["Writer"] += 1

    draft = writer(research)

    validate(
        "Writer",
        recipient="Manager",
        message=draft,
        violations=violations
    )

    trace.append(
        "Writer -> Manager: draft sent."
    )

    # --------------------------------------------------------
    # MANAGER -> REVIEWER
    # --------------------------------------------------------

    validate(
        "Manager",
        recipient="Reviewer",
        violations=violations
    )

    trace.append(
        "Manager -> Reviewer: check values, winner and citations."
    )

    model_calls["Reviewer"] += 1

    review = reviewer(
        draft,
        research,
        violations
    )

    trace.append(
        f"Reviewer -> Manager: {review['verdict']}"
    )

    # --------------------------------------------------------
    # REVISION LOOP
    # MAXIMUM 2 ROUNDS
    # --------------------------------------------------------

    while review["verdict"] == "REVISE" and revisions < 2:

        revisions += 1

        trace.append(
            f"Manager: revision round {revisions}"
        )

        trace.append(
            "Manager -> Writer: revise according to reviewer reasons."
        )

        model_calls["Writer"] += 1

        draft = writer(research)

        model_calls["Reviewer"] += 1

        review = reviewer(
            draft,
            research,
            violations
        )

        trace.append(
            f"Reviewer -> Manager: {review['verdict']}"
        )

    # --------------------------------------------------------
    # FINAL ANSWER
    # --------------------------------------------------------

    success = review["verdict"] == "PASS"

    trace.append(
        "Manager -> User: final answer delivered."
    )

    return {
        "success": success,
        "draft": draft,
        "trace": trace,
        "model_calls": model_calls,
        "violations": violations,
        "revisions": revisions
    }


# ============================================================
# 8. GENERALIST
# ============================================================

def generalist(model1, model2):

    # Generalist can use all tools.

    doc1 = read_doc(model1)
    doc2 = read_doc(model2)

    calculation = calculator(
        doc1["accuracy"],
        doc2["accuracy"]
    )

    if calculation["winner"] == "first":
        winner = doc1["model"]

    elif calculation["winner"] == "second":
        winner = doc2["model"]

    else:
        winner = "Tie"

    draft = (
        f"{doc1['model']} achieved {doc1['accuracy']}% accuracy, "
        f"while {doc2['model']} achieved {doc2['accuracy']}%. "
        f"{winner} performed better on the benchmark."
    )

    return {
        "success": (
            len(draft.split()) <= 60
            and len([model1, model2]) == 2
        ),
        "draft": draft,
        "citations": [model1, model2]
    }


# ============================================================
# ALGORITHM 2
# SINGLE GENERALIST AGENT
# ============================================================

def algorithm2(model1, model2):

    result = generalist(model1, model2)

    trace = [
        "Generalist receives complete task.",
        "Generalist searches and reads documents.",
        "Generalist calculates comparison.",
        "Generalist produces final cited answer."
    ]

    return {
        "success": result["success"],
        "draft": result["draft"],
        "trace": trace,
        "model_calls": {
            "Generalist": 1
        },
        "violations": [],
        "revisions": 0
    }


# ============================================================
# TRACE PRINTER
# ============================================================

def print_trace(trace):

    for i, message in enumerate(trace, 1):
        print(f"{i}. {message}")


# ============================================================
# MAIN EXPERIMENT
# ============================================================

def main_experiment():

    print("\n" + "#" * 70)
    print("IA462 EXPERIMENT 6")
    print("ROLE-BASED LLM AGENT DESIGN")
    print("#" * 70)

    # Print role specifications only once
    print_role_specs()

    print("\n" + "=" * 70)
    print("ALGORITHM 1 - ROLE-BASED MULTI-AGENT TEAM")
    print("=" * 70)

    print("\n" + "=" * 70)
    print("ALGORITHM 2 - SINGLE GENERALIST AGENT")
    print("=" * 70)

    print("\n" + "=" * 70)
    print("MAIN EXPERIMENT")
    print("=" * 70)

    seeds = list(range(10))

    team_success = 0
    generalist_success = 0

    total_team_calls = 0
    total_generalist_calls = 0

    total_violations = 0
    total_revisions = 0

    total_tasks = len(seeds) * len(tasks)

    # --------------------------------------------------------
    # SAME TASKS AND SAME SEEDS
    # --------------------------------------------------------

    for seed in seeds:

        print(f"\n\n*************** SEED {seed} ***************")

        for task_no, (model1, model2) in enumerate(tasks, 1):

            team = algorithm1(
                model1,
                model2,
                seed
            )

            general = algorithm2(
                model1,
                model2
            )

            if team["success"]:
                team_success += 1

            if general["success"]:
                generalist_success += 1

            total_team_calls += sum(
                team["model_calls"].values()
            )

            total_generalist_calls += 1

            total_violations += len(
                team["violations"]
            )

            total_revisions += team["revisions"]

            # ------------------------------------------------
            # FULL TRACE
            # ------------------------------------------------

            print("\n" + "-" * 70)

            print(
                f"TASK {task_no}: "
                f"{model1} vs {model2}"
            )

            print("\nROLE-BASED TEAM TRACE:")

            print_trace(team["trace"])

            print("\nGENERALIST TRACE:")

            print_trace(general["trace"])

            print("\nResults:")
            print("Team success:", team["success"])
            print("Generalist success:", general["success"])

            print(
                "Team model calls:",
                team["model_calls"]
            )

            print(
                "Role violations:",
                len(team["violations"])
            )

            print(
                "Revisions:",
                team["revisions"]
            )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print("\n\n" + "=" * 70)
    print("MAIN EXPERIMENT SUMMARY")
    print("=" * 70)

    print(
        "Total tasks:",
        total_tasks
    )

    print(
        "Role-based team success:",
        f"{team_success}/{total_tasks}"
    )

    print(
        "Generalist success:",
        f"{generalist_success}/{total_tasks}"
    )

    print(
        "Average team model calls:",
        round(total_team_calls / total_tasks, 2)
    )

    print(
        "Average generalist model calls:",
        round(total_generalist_calls / total_tasks, 2)
    )

    print(
        "Total role violations:",
        total_violations
    )

    print(
        "Average revisions:",
        round(total_revisions / total_tasks, 2)
    )


# ============================================================
# EXERCISE 1
# ABLATION STUDY
# ============================================================

def no_reviewer_team(model1, model2):

    """
    Reviewer removed.
    Researcher + Writer merged.
    """

    doc1 = read_doc(model1)
    doc2 = read_doc(model2)

    calculation = calculator(
        doc1["accuracy"],
        doc2["accuracy"]
    )

    if calculation["winner"] == "first":
        winner = doc1["model"]

    elif calculation["winner"] == "second":
        winner = doc2["model"]

    else:
        winner = "Tie"

    draft = (
        f"{doc1['model']} achieved {doc1['accuracy']}% accuracy, "
        f"while {doc2['model']} achieved {doc2['accuracy']}%. "
        f"{winner} performed better."
    )

    return {
        "success": (
            winner != "Tie"
            and len(draft.split()) <= 60
        ),
        "calls": 2,
        "violations": 0
    }


def exercise1():

    print("\n\n" + "#" * 70)
    print("EXERCISE 1 - ABLATION STUDY")
    print("#" * 70)

    seeds = list(range(10))

    total = len(seeds) * len(tasks)

    full_success = 0
    ablation_success = 0
    generalist_success = 0

    full_calls = 0
    ablation_calls = 0
    generalist_calls = 0

    full_violations = 0
    ablation_violations = 0

    for seed in seeds:

        for model1, model2 in tasks:

            # Full team
            full = algorithm1(
                model1,
                model2,
                seed
            )

            # Reviewer removed +
            # Researcher and Writer merged
            ablation = no_reviewer_team(
                model1,
                model2
            )

            # Generalist
            general = algorithm2(
                model1,
                model2
            )

            if full["success"]:
                full_success += 1

            if ablation["success"]:
                ablation_success += 1

            if general["success"]:
                generalist_success += 1

            full_calls += sum(
                full["model_calls"].values()
            )

            ablation_calls += ablation["calls"]
            generalist_calls += 1

            full_violations += len(
                full["violations"]
            )

            ablation_violations += ablation["violations"]

    print("\n" + "-" * 70)
    print("ABLATION RESULTS")
    print("-" * 70)

    print(
        "Full team:",
        f"{full_success}/{total}",
        "| Average calls:",
        round(full_calls / total, 2),
        "| Violations:",
        full_violations
    )

    print(
        "No Reviewer + Researcher/Writer merged:",
        f"{ablation_success}/{total}",
        "| Average calls:",
        round(ablation_calls / total, 2),
        "| Violations:",
        ablation_violations
    )

    print(
        "Generalist:",
        f"{generalist_success}/{total}",
        "| Average calls:",
        round(generalist_calls / total, 2)
    )


# ============================================================
# EXERCISE 2
# ROLE VIOLATION / PROMPT INJECTION
# ============================================================

def exercise2():

    print("\n\n" + "#" * 70)
    print("EXERCISE 2 - ROLE VIOLATION TESTS")
    print("#" * 70)

    cases = [
        (
            1,
            "Writer is told to search.",
            "Writer",
            "tool"
        ),

        (
            2,
            "Document tells Researcher to send finding directly to User.",
            "Researcher",
            "recipient"
        ),

        (
            3,
            "Reviewer is told to fix the draft itself.",
            "Reviewer",
            "recipient"
        ),

        (
            4,
            "Document tells Researcher to report a false value.",
            "Researcher",
            "false_value"
        ),

        (
            5,
            "Assignment tells Researcher to omit sources.",
            "Researcher",
            "missing_output"
        )
    ]

    # --------------------------------------------------------
    # PROMPT-ONLY
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("A. PERMISSIONS ONLY IN PROMPTS")
    print("=" * 70)

    for number, description, role, action in cases:

        print(f"\nCase {number}: {description}")

        print(
            "Result: instruction is not blocked by an "
            "external permission validator."
        )

    # --------------------------------------------------------
    # VALIDATION ENABLED
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("B. VALIDATE() ENFORCED")
    print("=" * 70)

    for number, description, role, action in cases:

        violations = []

        print(f"\nCase {number}: {description}")

        # Case 1:
        # Writer cannot use search
        if number == 1:

            allowed = validate(
                "Writer",
                tool="search",
                violations=violations
            )

        # Case 2:
        # Researcher can only send to Manager
        elif number == 2:

            allowed = validate(
                "Researcher",
                recipient="User",
                violations=violations
            )

        # Case 3:
        # Reviewer cannot send to Writer
        elif number == 3:

            allowed = validate(
                "Reviewer",
                recipient="Writer",
                violations=violations
            )

        # Case 4:
        # False value has correct output structure.
        # validate() alone cannot know the value is false.
        elif number == 4:

            message = {
                "values": {
                    "ModelA": 999.0
                },

                "sources": [
                    "ModelA",
                    "ModelB"
                ],

                "result": {
                    "model1": "ModelA",
                    "model2": "ModelB",
                    "accuracy1": 999.0,
                    "accuracy2": 89.5,
                    "winner": "ModelA"
                }
            }

            allowed = validate(
                "Researcher",
                message=message,
                violations=violations
            )

            print(
                "Important: validate() cannot detect a false "
                "value when the message structure is valid."
            )

        # Case 5:
        # Researcher must provide sources
        elif number == 5:

            message = {
                "values": {
                    "ModelA": 91.2,
                    "ModelB": 89.5
                },

                "result": {
                    "model1": "ModelA",
                    "model2": "ModelB",
                    "winner": "ModelA"
                }
            }

            allowed = validate(
                "Researcher",
                message=message,
                violations=violations
            )

        else:
            allowed = True

        if allowed:
            print("Result: NOT BLOCKED")
        else:
            print("Result: BLOCKED")

        print(
            "Violations logged:",
            len(violations)
        )


# ============================================================
# PROGRAM START
# ============================================================

if __name__ == "__main__":

    # --------------------------------------------------------
    # MAIN EXPERIMENT
    # --------------------------------------------------------

    main_experiment()

    # --------------------------------------------------------
    # EXERCISE 1
    # --------------------------------------------------------

    exercise1()

    # --------------------------------------------------------
    # EXERCISE 2
    # --------------------------------------------------------

    exercise2()