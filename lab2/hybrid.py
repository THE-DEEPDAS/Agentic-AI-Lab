from collections import deque

grid = [
    list("S...."),
    list(".#P.."),
    list("....."),
    list(".#..G")
]

rows = len(grid)
cols = len(grid[0])

start = (0, 0)
goal = (3, 4)

directions = [
    (-1, 0, 'U'),
    (1, 0, 'D'),
    (0, -1, 'L'),
    (0, 1, 'R')
]


# -------------------------------------------------
# DELIBERATIVE PLANNER
# -------------------------------------------------

def bfs(grid, start, goal):

    queue = deque([start])
    visited = {start}

    parent = {}
    move_taken = {}

    while queue:

        r, c = queue.popleft()

        if (r, c) == goal:
            break

        for dr, dc, move in directions:

            nr = r + dr
            nc = c + dc

            if (0 <= nr < rows and
                0 <= nc < cols and
                grid[nr][nc] != '#' and
                grid[nr][nc] != 'P' and
                (nr, nc) not in visited):

                visited.add((nr, nc))

                parent[(nr, nc)] = (r, c)
                move_taken[(nr, nc)] = move

                queue.append((nr, nc))

    if goal not in visited:
        return []

    # Reconstruct path
    plan = []
    current = goal

    while current != start:

        plan.append(move_taken[current])
        current = parent[current]

    plan.reverse()

    return plan


# -------------------------------------------------
# REACTIVE SAFETY RULE
# -------------------------------------------------

def is_safe(grid, r, c):

    pit_directions = [
        (-1, 0),
        (1, 0),
        (0, -1),
        (0, 1)
    ]

    for dr, dc in pit_directions:

        nr = r + dr
        nc = c + dc

        if (0 <= nr < rows and
            0 <= nc < cols and
            grid[nr][nc] == 'P'):

            return False

    return True


# -------------------------------------------------
# GET NEXT POSITION
# -------------------------------------------------

def next_position(current, action):

    r, c = current

    if action == 'U':
        r -= 1
    elif action == 'D':
        r += 1
    elif action == 'L':
        c -= 1
    elif action == 'R':
        c += 1

    return (r, c)


# -------------------------------------------------
# INITIAL PLANNING
# -------------------------------------------------

current = start

plan = bfs(grid, current, goal)

print("Initial plan:", plan)


# -------------------------------------------------
# HYBRID EXECUTION + RE-PLANNING
# -------------------------------------------------

print("\nExecution:")

while current != goal:

    # If current plan is finished but goal not reached
    if not plan:

        print("No valid plan exists.")
        break

    action = plan.pop(0)

    next_pos = next_position(current, action)

    # -------------------------------------------------
    # REACTIVE RULE BLOCKS THE ACTION
    # -------------------------------------------------

    if not is_safe(
        grid,
        next_pos[0],
        next_pos[1]
    ):

        print(
            f"\nReactive rule BLOCKED action "
            f"{action} -> {next_pos}"
        )

        print(
            "Reason: next cell is adjacent to a pit."
        )

        # -------------------------------------------------
        # UPDATE INTERNAL MODEL
        # -------------------------------------------------

        grid[next_pos[0]][next_pos[1]] = '#'

        print(
            f"Cell {next_pos} marked as BLOCKED (#)"
        )

        # -------------------------------------------------
        # RE-PLAN FROM CURRENT POSITION
        # -------------------------------------------------

        plan = bfs(
            grid,
            current,
            goal
        )

        print(
            "New plan from current position:",
            plan
        )

        # Do NOT move.
        # Try the new plan.
        continue

    # -------------------------------------------------
    # EXECUTE SAFE ACTION
    # -------------------------------------------------

    current = next_pos

    print(
        f"Executed {action} -> {current}"
    )


# -------------------------------------------------
# FINAL RESULT
# -------------------------------------------------

if current == goal:
    print("\nGoal reached safely!")
else:
    print("\nGoal could not be reached.")