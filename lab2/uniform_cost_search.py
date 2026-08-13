import heapq

grid = [
    "S....",
    ".##..",
    "...#.",
    ".#..G"
]

# Cost of entering each cell
cost = [
    [1, 2, 2, 2, 2],
    [1, 9, 9, 2, 2],
    [1, 1, 1, 9, 2],
    [1, 9, 1, 1, 1]
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

directions = [
    (-1, 0, 'U'),
    (1, 0, 'D'),
    (0, -1, 'L'),
    (0, 1, 'R')
]

INF = float('inf')

# Minimum cost to reach each cell
distance = [
    [INF for _ in range(cols)]
    for _ in range(rows)
]

parent = {}
move_taken = {}

# Priority queue: (cost, row, column)
pq = []

distance[start[0]][start[1]] = 0
heapq.heappush(pq, (0, start[0], start[1]))

# Uniform-Cost Search
while pq:

    current_cost, r, c = heapq.heappop(pq)

    if current_cost != distance[r][c]:
        continue

    if (r, c) == goal:
        break

    for dr, dc, move in directions:

        nr = r + dr
        nc = c + dc

        if (0 <= nr < rows and
            0 <= nc < cols and
            grid[nr][nc] != '#'):

            new_cost = current_cost + cost[nr][nc]

            if new_cost < distance[nr][nc]:

                distance[nr][nc] = new_cost

                parent[(nr, nc)] = (r, c)
                move_taken[(nr, nc)] = move

                heapq.heappush(
                    pq,
                    (new_cost, nr, nc)
                )


# Reconstruct path
plan = []
current = goal

while current != start:

    plan.append(move_taken[current])
    current = parent[current]

plan.reverse()

print("Optimal plan:", plan)
print("Minimum total cost:",
      distance[goal[0]][goal[1]])