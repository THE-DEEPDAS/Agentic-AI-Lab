# no internal state rakhvana 
# only percept and execute
# +1 for clean, -1 for dirty

env_state = {
    "location_A": "dirty",
    "location_B": "clean"
}

agent_location = "location_A"
cumulative_reward = 0

def percept(location):
    return {"location": location, "status": env_state[location]}

def execute(action):
    global agent_location
    global cumulative_reward

    if percept(agent_location)["status"] == "dirty":
        env_state[agent_location] = "clean"
        cumulative_reward -= 1
        return -1  # -1 for cleaning
    else:
        if agent_location == "location_A":
            agent_location = "location_B"
        else:
            agent_location = "location_A"
        cumulative_reward += 1
        return +1  # +1 for moving

# run the agent for 20 steps
for step in range(20):
    current_percept = percept(agent_location)
    action_result = execute(current_percept)
    print(f"Step {step + 1}: Location: {agent_location}, Status: {current_percept['status']}, Cumulative Reward: {cumulative_reward}")  