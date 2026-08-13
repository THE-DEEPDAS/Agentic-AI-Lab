from collections import deque

grid = [
    "S..#...",
    ".#.#...",
    ".#...#.",
    "...#..G"
]

rows = len(grid)
cols = len(grid[0])

# Find S and G
for r in range(rows):
    for c in range(cols):
        if grid[r][c] == 'S':
            start = (r, c)
        elif grid[r][c] == 'G':
            goal = (r, c)

# Directions
directions = [
    (-1, 0, 'U'),
    (1, 0, 'D'),
    (0, -1, 'L'),
    (0, 1, 'R')
]

# BFS
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


# Reconstruct path
plan = []
current = goal

while current != start:
    plan.append(move_taken[current])
    current = parent[current]

plan.reverse()

print("Planned actions:", plan)
print("Number of steps:", len(plan))


# Execute plan
current = start

print("\nExecution:")

for action in plan:

    r, c = current

    if action == 'U':
        r -= 1
    elif action == 'D':
        r += 1
    elif action == 'L':
        c -= 1
    elif action == 'R':
        c += 1

    current = (r, c)

    print(f"Action {action} -> {current}")


if current == goal:
    print("\nGoal reached successfully!")
else:
    print("\nGoal not reached.")