import random

N = 5
agent_location = 0
direction = 1
cumulative_reward = 0
env_state = {}

for i in range(N):
    env_state[i] = random.choice(["clean", "dirty"])

def percept(location):
    return {"location": location, "status": env_state[location]}

def execute(per):
    global agent_location
    global direction
    global cumulative_reward

    if per["status"] == "dirty":
        env_state[agent_location] = "clean"
        cumulative_reward -= 1
        return "Suck"

    next_location = agent_location + direction

    if next_location >= N:
        direction = -1
        next_location = N - 2

    elif next_location < 0:
        direction = 1
        next_location = 1

    agent_location = next_location
    cumulative_reward += 1
    return "Move"

for step in range(20):
    p = percept(agent_location)
    action = execute(p)

    print(f"Step {step+1}: Action={action}, Location={agent_location}, Reward={cumulative_reward}")