"""Benchmark the C++ pick-path engine against the pure-Python reference.

Prints a markdown table (routes/second and speedup per instance size) plus a
solution-quality check against the exact Held-Karp optimum on small
instances. Run inside the Docker image or CI, where the native engine is
built:  python native/bench_pickpath.py
"""

import random
import statistics
import time

import pickpath

SIZES = [8, 15, 25, 40, 60]
INSTANCES_PER_SIZE = 20


def unique_bins(rng: random.Random, n: int, width: int = 60, height: int = 25) -> list:
    coords: set[tuple[int, int]] = set()
    while len(coords) < n:
        coords.add((rng.randint(0, width), rng.randint(0, height)))
    return sorted(coords)


def time_engine(engine: str, instances: list) -> float:
    """Mean milliseconds per route over all instances (3 timed repeats)."""
    runs = []
    for _ in range(3):
        started = time.perf_counter()
        for bins in instances:
            pickpath.optimize_route(bins, engine=engine)
        runs.append((time.perf_counter() - started) * 1000 / len(instances))
    return statistics.median(runs)


def main() -> None:
    if not pickpath.native_available():
        raise SystemExit("pickpath-native is not installed; build it first (see README)")

    rng = random.Random(1234)
    print("| Bins per order | Python (ms/route) | C++ (ms/route) | Speedup |")
    print("|---:|---:|---:|---:|")
    for size in SIZES:
        instances = [unique_bins(rng, size) for _ in range(INSTANCES_PER_SIZE)]
        for bins in instances[:2]:  # warm-up / JIT-free sanity pass
            pickpath.optimize_route(bins, engine="python")
            pickpath.optimize_route(bins, engine="native")
        python_ms = time_engine("python", instances)
        native_ms = time_engine("native", instances)
        print(f"| {size} | {python_ms:.3f} | {native_ms:.3f} | {python_ms / native_ms:.1f}x |")

    quality_rng = random.Random(99)
    ratios = []
    for _ in range(30):
        bins = unique_bins(quality_rng, quality_rng.randint(3, 9), width=20, height=20)
        exact = pickpath.held_karp_exact(bins)
        heuristic = pickpath.optimize_route(bins, engine="native").total_distance
        ratios.append(heuristic / exact if exact else 1.0)
    print()
    print(
        f"Solution quality vs exact optimum (n<=9, 30 instances): "
        f"mean {statistics.mean(ratios):.4f}, worst {max(ratios):.4f}"
    )


if __name__ == "__main__":
    main()
