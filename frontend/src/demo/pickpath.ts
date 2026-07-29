/** The pick-path heuristic, ported to TypeScript for the replay build.
 *
 * This is a third implementation of the algorithm that `native/pickpath`
 * specifies and `native/pickpath-native` reimplements in C++17: nearest
 * neighbour with lowest-index tie-breaking, then first-improvement 2-opt
 * that restarts its scan after every applied swap. The tie-breaking rules
 * are copied deliberately, so the routes drawn in the published demo are
 * the routes the real engines would return for the same bins rather than
 * something that merely looks plausible.
 *
 * It exists only because the demo has no backend to ask. The service path
 * is unchanged: a real deployment still calls the C++ engine.
 */

export type Point = [number, number];

export function manhattan(a: Point, b: Point): number {
  return Math.abs(a[0] - b[0]) + Math.abs(a[1] - b[1]);
}

export function routeDistance(bins: Point[], depot: Point, sequence: number[]): number {
  if (sequence.length === 0) {
    return 0;
  }
  let total = manhattan(depot, bins[sequence[0]]);
  for (let k = 0; k + 1 < sequence.length; k += 1) {
    total += manhattan(bins[sequence[k]], bins[sequence[k + 1]]);
  }
  return total + manhattan(bins[sequence[sequence.length - 1]], depot);
}

function nearestNeighbour(bins: Point[], depot: Point): number[] {
  const visited = new Array<boolean>(bins.length).fill(false);
  const sequence: number[] = [];
  let current = depot;

  for (let step = 0; step < bins.length; step += 1) {
    let best = -1;
    let bestDistance = 0;
    // Ascending scan with a strict '<' keeps the lowest index on a tie,
    // matching the Python reference's (distance, index) ordering.
    for (let i = 0; i < bins.length; i += 1) {
      if (visited[i]) {
        continue;
      }
      const d = manhattan(current, bins[i]);
      if (best === -1 || d < bestDistance) {
        best = i;
        bestDistance = d;
      }
    }
    visited[best] = true;
    sequence.push(best);
    current = bins[best];
  }
  return sequence;
}

function twoOptOnce(bins: Point[], depot: Point, sequence: number[]): boolean {
  const n = sequence.length;
  for (let i = 0; i + 1 < n; i += 1) {
    const prev = i === 0 ? depot : bins[sequence[i - 1]];
    for (let j = i + 1; j < n; j += 1) {
      const next = j === n - 1 ? depot : bins[sequence[j + 1]];
      // Reversing sequence[i..j] only touches the two boundary edges.
      const currentCost = manhattan(prev, bins[sequence[i]]) + manhattan(bins[sequence[j]], next);
      const candidateCost = manhattan(prev, bins[sequence[j]]) + manhattan(bins[sequence[i]], next);
      if (candidateCost < currentCost) {
        const slice = sequence.slice(i, j + 1).reverse();
        sequence.splice(i, slice.length, ...slice);
        return true;
      }
    }
  }
  return false;
}

export function optimiseRoute(
  bins: Point[],
  depot: Point = [0, 0],
): { sequence: number[]; totalDistance: number } {
  if (bins.length === 0) {
    return { sequence: [], totalDistance: 0 };
  }
  const sequence = nearestNeighbour(bins, depot);
  while (twoOptOnce(bins, depot, sequence)) {
    /* keep improving until no single swap helps */
  }
  return { sequence, totalDistance: routeDistance(bins, depot, sequence) };
}
