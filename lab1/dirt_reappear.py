import random

env_state = {
    "location_A": "dirty",
    "location_B": "clean"
}

agent_location = "location_A"
cumulative_reward = 0

def percept(location):
    return {"location": location, "status": env_state[location]}

def add_new_dirt():
    for room in env_state:
        if env_state[room] == "clean":
            if random.random() < 0.1:
                env_state[room] = "dirty"

def execute(per):
    global agent_location
    global cumulative_reward

    if per["status"] == "dirty":
        env_state[agent_location] = "clean"
        cumulative_reward -= 1
        action = "Suck"
    else:
        if agent_location == "location_A":
            agent_location = "location_B"
        else:
            agent_location = "location_A"

        cumulative_reward += 1
        action = "Move"

    add_new_dirt()
    return action

for step in range(20):
    p = percept(agent_location)
    action = execute(p)

    print(f"Step {step+1}: Action={action}, Location={agent_location}, Reward={cumulative_reward}, State={env_state}")