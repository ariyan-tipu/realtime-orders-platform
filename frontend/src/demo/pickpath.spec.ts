import { describe, expect, it } from "vitest";

import { manhattan, optimiseRoute, routeDistance, type Point } from "./pickpath";

/** Brute-force optimum, the same oracle role Held-Karp plays in the Python
 * suite. Exhaustive is fine at these sizes and needs no dynamic programming. */
function bruteForce(bins: Point[], depot: Point = [0, 0]): number {
  const indices = bins.map((_, i) => i);
  let best = Infinity;
  const permute = (rest: number[], acc: number[]): void => {
    if (rest.length === 0) {
      best = Math.min(best, routeDistance(bins, depot, acc));
      return;
    }
    for (let i = 0; i < rest.length; i += 1) {
      permute([...rest.slice(0, i), ...rest.slice(i + 1)], [...acc, rest[i]]);
    }
  };
  permute(indices, []);
  return best;
}

describe("manhattan", () => {
  it("is the grid metric the warehouse uses", () => {
    expect(manhattan([0, 0], [3, 4])).toBe(7);
    expect(manhattan([5, 5], [5, 5])).toBe(0);
  });
});

describe("optimiseRoute", () => {
  it("returns nothing for an empty pick list", () => {
    expect(optimiseRoute([])).toEqual({ sequence: [], totalDistance: 0 });
  });

  it("visits every bin exactly once", () => {
    const bins: Point[] = [
      [3, 2],
      [8, 1],
      [14, 7],
      [21, 3],
      [27, 11],
    ];
    const { sequence } = optimiseRoute(bins);
    expect([...sequence].sort((a, b) => a - b)).toEqual([0, 1, 2, 3, 4]);
  });

  it("reports the distance of the sequence it returns", () => {
    const bins: Point[] = [
      [4, 4],
      [9, 1],
      [2, 7],
    ];
    const { sequence, totalDistance } = optimiseRoute(bins);
    expect(totalDistance).toBe(routeDistance(bins, [0, 0], sequence));
  });

  it("breaks distance ties on the lowest index, as the Python reference does", () => {
    // Both bins sit two steps from the depot; the reference picks index 0.
    const bins: Point[] = [
      [2, 0],
      [0, 2],
    ];
    expect(optimiseRoute(bins).sequence[0]).toBe(0);
  });

  it("stays within a few percent of the exact optimum", () => {
    const cases: Point[][] = [
      [
        [1, 1],
        [9, 2],
        [4, 8],
        [7, 5],
      ],
      [
        [12, 3],
        [2, 11],
        [8, 8],
        [15, 1],
        [5, 5],
      ],
      [
        [3, 2],
        [8, 1],
        [14, 7],
        [21, 3],
        [27, 11],
        [33, 5],
      ],
    ];
    for (const bins of cases) {
      const heuristic = optimiseRoute(bins).totalDistance;
      const optimal = bruteForce(bins);
      expect(heuristic).toBeGreaterThanOrEqual(optimal);
      expect(heuristic).toBeLessThanOrEqual(optimal * 1.1);
    }
  });

  it("is deterministic", () => {
    const bins: Point[] = [
      [6, 6],
      [1, 9],
      [13, 2],
      [4, 4],
    ];
    expect(optimiseRoute(bins)).toEqual(optimiseRoute(bins));
  });
});
