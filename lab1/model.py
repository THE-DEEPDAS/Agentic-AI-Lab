# Model Based Vacuum Agent
import copy

env_state = {
    "location_A": "dirty",
    "location_B": "clean"
}

agent_location = "location_A"
cumulative_reward = 0

# internal memory
model = {
    "location_A": "unknown",
    "location_B": "unknown"
}

def percept(location):
    return {"location": location, "status": env_state[location]}

def execute(per):
    global agent_location
    global cumulative_reward

    location = per["location"]
    status = per["status"]

    # update memory
    model[location] = status

    # if everything known clean -> NoOp
    if model["location_A"] == "clean" and model["location_B"] == "clean":
        cumulative_reward += 1
        return "NoOp"

    if status == "dirty":
        env_state[location] = "clean"
        model[location] = "clean"
        cumulative_reward -= 1
        return "Suck"

    if agent_location == "location_A":
        agent_location = "location_B"
    else:
        agent_location = "location_A"

    cumulative_reward += 1
    return "Move"

for step in range(20):
    p = percept(agent_location)
    action = execute(p)

    print(f"Step {step+1}: Action={action}, Location={agent_location}, Reward={cumulative_reward}")