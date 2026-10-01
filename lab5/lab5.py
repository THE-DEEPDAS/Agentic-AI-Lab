from collections import Counter
import random
import re

# ALGORITHM
questions = [
    ("What is 12 * 8?", "96"),
    ("What is 45 + 37?", "82"),
    ("What is 144 / 12?", "12"),
    ("What is 15% of 200?", "30"),
    ("What is the square root of 81?", "9"),
    ("If a train travels 60 km in 2 hours, what is its speed?", "30 km/h"),
    ("What is 7 * 9 - 5?", "58"),
    ("What is 3/4 as a decimal?", "0.75"),
]

direct_prompt = "Answer the question directly: {question}"
cot_prompt = "Solve the question step by step and finish with Final answer: {question}"


def normalise(answer):
    answer = answer.lower().strip().replace(",", "")
    answer = re.sub(r"\s+", " ", answer)
    if answer in {"30 km per hour", "30 kilometers per hour"}:
        return "30 km/h"
    return answer.rstrip(".")


def extract_answer(trace):
    match = re.search(r"(?:final answer|answer)\s*[:=]\s*(.+)$", trace, re.I)
    if not match:
        return None
    answer = match.group(1).strip().splitlines()[0]
    return normalise(answer) if answer else None


def scripted_trace(question, gold, configuration, rng):
    # This scripted model represents realistic correct, incorrect and unparsable traces.
    error_rate = {"direct": 0.25, "cot": 0.25, "self-consistency": 0.18}[configuration]
    if rng.random() < 0.10:
        return "I could not determine the result."
    if rng.random() < error_rate:
        wrong = {"96": "95", "82": "83", "12": "14", "30": "20",
                 "9": "8", "30 km/h": "60 km/h", "58": "57", "0.75": "0.70"}[gold]
        answer = wrong
    else:
        answer = gold
    if configuration == "direct":
        return f"Answer: {answer}"
    return f"The calculation gives {answer}. Final answer: {answer}"


def run(configuration, k=5, seed=1, margin=None):
    rng = random.Random(seed)
    correct = calls = unparsable = 0
    details = []
    for question, gold in questions:
        traces = [scripted_trace(question, gold, configuration, rng)
                  for _ in range(1 if configuration != "self-consistency" else k)]
        calls += len(traces)
        answers = [extract_answer(trace) for trace in traces]
        valid = [answer for answer in answers if answer is not None]
        unparsable += len(answers) - len(valid)
        votes = Counter(valid)
        winner = None
        if votes:
            ranked = votes.most_common()
            if margin is None or len(ranked) == 1 or ranked[0][1] - ranked[1][1] >= margin:
                winner = ranked[0][0]
        correct += winner == gold
        details.append((question, votes, winner, winner == gold))
    accuracy = correct / len(questions)
    return accuracy, calls, unparsable, details


def print_result(configuration, result):
    accuracy, calls, unparsable, details = result
    print(f"{configuration}: accuracy={accuracy:.2f}, calls={calls}, unparsable={unparsable}")
    for question, votes, winner, is_correct in details:
        print(f"  {question} | votes={dict(votes)} | selected={winner} | correct={is_correct}")


# CALL: core comparison
print("PROMPTS")
print(direct_prompt)
print(cot_prompt)
print("\nCORE COMPARISON")
for configuration in ("direct", "cot", "self-consistency"):
    print_result(configuration, run(configuration, k=5, seed=7))


# EXERCISE 1: sweep k with several seeds
print("\nEXERCISE 1 - K SWEEP")
for k in (1, 3, 5, 9, 15):
    results = [run("self-consistency", k=k, seed=seed) for seed in (1, 2, 3, 4, 5)]
    average_accuracy = sum(result[0] for result in results) / len(results)
    total_calls = sum(result[1] for result in results)
    print(f"k={k}: average_accuracy={average_accuracy:.2f}, total_calls={total_calls}, "
          f"calls_per_correct={total_calls / max(1, sum(round(r[0] * len(questions)) for r in results)):.2f}")


# EXERCISE 2: abstain when the vote margin is too small
print("\nEXERCISE 2 - ABSTENTION")
for margin in (1, 2):
    result = run("self-consistency", k=5, seed=7, margin=margin)
    answered = [item for item in result[3] if item[2] is not None]
    coverage = len(answered) / len(questions)
    answered_accuracy = sum(item[3] for item in answered) / len(answered) if answered else 0
    print(f"margin={margin}: coverage={coverage:.2f}, answered_accuracy={answered_accuracy:.2f}, "
          f"calls={result[1]}")

