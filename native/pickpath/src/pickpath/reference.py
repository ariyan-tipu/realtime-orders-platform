"""Pure-Python reference implementation of the pick-path optimiser.

This module is the behavioural specification for the C++ engine: both follow
the same deterministic algorithm (nearest-neighbour construction with
lowest-index tie-breaking, then first-improvement 2-opt that restarts its scan
after every applied swap), so the two engines return identical routes and the
parity tests can assert exact equality rather than "close enough".
"""

from pickpath.types import Point, RouteResult

# Held-Karp is O(2^n * n^2); beyond ~12 bins it stops being a sensible oracle.
_EXACT_LIMIT = 12


def manhattan(a: Point, b: Point) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def route_distance(bins: list[Point], depot: Point, sequence: list[int]) -> int:
    """Total travel: depot -> bins[sequence[0]] -> ... -> depot."""
    if not sequence:
        return 0
    total = manhattan(depot, bins[sequence[0]])
    for prev, nxt in zip(sequence, sequence[1:], strict=False):
        total += manhattan(bins[prev], bins[nxt])
    total += manhattan(bins[sequence[-1]], depot)
    return total


def _nearest_neighbor(bins: list[Point], depot: Point) -> list[int]:
    unvisited = set(range(len(bins)))
    sequence: list[int] = []
    current = depot
    while unvisited:
        best = min(unvisited, key=lambda i: (manhattan(current, bins[i]), i))
        sequence.append(best)
        unvisited.remove(best)
        current = bins[best]
    return sequence


def _two_opt(bins: list[Point], depot: Point, sequence: list[int]) -> list[int]:
    """First-improvement 2-opt over the open tour anchored at the depot.

    Reversing sequence[i..j] only changes the two boundary edges, so each
    candidate move is evaluated in O(1). After applying a move the scan
    restarts, which keeps the search order (and therefore the result)
    identical across implementations.
    """
    n = len(sequence)
    improved = True
    while improved:
        improved = False
        for i in range(n - 1):
            prev_pt = depot if i == 0 else bins[sequence[i - 1]]
            for j in range(i + 1, n):
                next_pt = depot if j == n - 1 else bins[sequence[j + 1]]
                current_cost = manhattan(prev_pt, bins[sequence[i]]) + manhattan(
                    bins[sequence[j]], next_pt
                )
                candidate_cost = manhattan(prev_pt, bins[sequence[j]]) + manhattan(
                    bins[sequence[i]], next_pt
                )
                if candidate_cost < current_cost:
                    sequence[i : j + 1] = reversed(sequence[i : j + 1])
                    improved = True
                    break
            if improved:
                break
    return sequence


def optimize_route_py(bins: list[Point], depot: Point = (0, 0)) -> RouteResult:
    """Nearest-neighbour + 2-opt heuristic, pure-Python engine."""
    if not bins:
        return RouteResult(sequence=[], total_distance=0, engine="python")
    sequence = _two_opt(bins, depot, _nearest_neighbor(bins, depot))
    return RouteResult(
        sequence=sequence,
        total_distance=route_distance(bins, depot, sequence),
        engine="python",
    )


def held_karp_exact(bins: list[Point], depot: Point = (0, 0)) -> int:
    """Optimal tour length by Held-Karp dynamic programming (test oracle).

    Only the distance is returned; optimal sequences are not unique, so tests
    compare heuristic distances against this bound instead of sequences.
    """
    n = len(bins)
    if n == 0:
        return 0
    if n > _EXACT_LIMIT:
        raise ValueError(f"held_karp_exact is limited to {_EXACT_LIMIT} bins, got {n}")

    dist = [[manhattan(a, b) for b in bins] for a in bins]
    from_depot = [manhattan(depot, b) for b in bins]

    # dp[mask][i]: cheapest path from depot visiting exactly `mask`, ending at i.
    size = 1 << n
    inf = float("inf")
    dp = [[inf] * n for _ in range(size)]
    for i in range(n):
        dp[1 << i][i] = from_depot[i]
    for mask in range(size):
        for last in range(n):
            cost = dp[mask][last]
            if cost == inf:
                continue
            for nxt in range(n):
                if mask & (1 << nxt):
                    continue
                new_mask = mask | (1 << nxt)
                new_cost = cost + dist[last][nxt]
                if new_cost < dp[new_mask][nxt]:
                    dp[new_mask][nxt] = new_cost

    full = size - 1
    best = min(dp[full][i] + from_depot[i] for i in range(n))
    return int(best)
