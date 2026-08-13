from collections import deque

grid = [
    list("S...."),
    list(".##.."),
    list("...#."),
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
# BFS PLANNER
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
                (nr, nc) not in visited):

                visited.add((nr, nc))

                parent[(nr, nc)] = (r, c)
                move_taken[(nr, nc)] = move

                queue.append((nr, nc))

    # No path
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
# GET NEXT POSITION
# -------------------------------------------------

def get_next_position(current, action):

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

plan = bfs(grid, start, goal)

print("Initial plan:", plan)


# -------------------------------------------------
# WORLD CHANGES
# -------------------------------------------------

# Block a cell
grid[3][2] = '#'

print("\nCell (3, 2) has been blocked.")


# -------------------------------------------------
# EXECUTION + RE-PLANNING
# -------------------------------------------------

current = start

while current != goal:

    if not plan:
        print("No plan available!")
        break

    action = plan.pop(0)

    next_position = get_next_position(
        current,
        action
    )

    # Check whether action is possible
    if grid[next_position[0]][next_position[1]] == '#':

        print(
            f"\nExecution failure at "
            f"{next_position}"
        )

        print("Re-planning...")

        plan = bfs(
            grid,
            current,
            goal
        )

        if not plan:
            print("No alternative path exists.")
            break

        print("New plan:", plan)

        continue

    # Execute action
    current = next_position

    print(
        f"Executed {action} -> {current}"
    )


if current == goal:
    print("\nGoal reached after re-planning!")