// C++ engine for warehouse pick-path optimisation.
//
// This is a line-for-line behavioural twin of pickpath/reference.py:
// nearest-neighbour construction with lowest-index tie-breaking, then
// first-improvement 2-opt that restarts its scan after every applied swap.
// Keeping the two engines deterministic and identical is what lets the test
// suite assert exact sequence equality between them.
//
// Why C++ here at all: route optimisation is a pure CPU-bound inner loop
// (O(n^2) per 2-opt pass, many passes) called on the request path for every
// pick-list. The pybind11 wrapper releases the GIL while optimising, so a
// busy core service keeps serving other requests.

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <cstdint>
#include <utility>
#include <vector>

namespace {

using Point = std::pair<std::int64_t, std::int64_t>;

std::int64_t manhattan(const Point& a, const Point& b) {
    const std::int64_t dx = a.first > b.first ? a.first - b.first : b.first - a.first;
    const std::int64_t dy = a.second > b.second ? a.second - b.second : b.second - a.second;
    return dx + dy;
}

std::int64_t route_distance(const std::vector<Point>& bins, const Point& depot,
                            const std::vector<std::size_t>& sequence) {
    if (sequence.empty()) {
        return 0;
    }
    std::int64_t total = manhattan(depot, bins[sequence.front()]);
    for (std::size_t k = 0; k + 1 < sequence.size(); ++k) {
        total += manhattan(bins[sequence[k]], bins[sequence[k + 1]]);
    }
    total += manhattan(bins[sequence.back()], depot);
    return total;
}

std::vector<std::size_t> nearest_neighbor(const std::vector<Point>& bins, const Point& depot) {
    const std::size_t n = bins.size();
    std::vector<bool> visited(n, false);
    std::vector<std::size_t> sequence;
    sequence.reserve(n);

    Point current = depot;
    for (std::size_t step = 0; step < n; ++step) {
        std::size_t best = n;
        std::int64_t best_distance = 0;
        // Ascending scan + strict '<' keeps the lowest index on distance ties,
        // matching the Python reference's (distance, index) ordering.
        for (std::size_t i = 0; i < n; ++i) {
            if (visited[i]) {
                continue;
            }
            const std::int64_t d = manhattan(current, bins[i]);
            if (best == n || d < best_distance) {
                best = i;
                best_distance = d;
            }
        }
        visited[best] = true;
        sequence.push_back(best);
        current = bins[best];
    }
    return sequence;
}

bool two_opt_single_improvement(const std::vector<Point>& bins, const Point& depot,
                                std::vector<std::size_t>& sequence) {
    const std::size_t n = sequence.size();
    for (std::size_t i = 0; i + 1 < n; ++i) {
        const Point& prev = (i == 0) ? depot : bins[sequence[i - 1]];
        for (std::size_t j = i + 1; j < n; ++j) {
            const Point& next = (j == n - 1) ? depot : bins[sequence[j + 1]];
            // Reversing sequence[i..j] only touches the two boundary edges.
            const std::int64_t current_cost =
                manhattan(prev, bins[sequence[i]]) + manhattan(bins[sequence[j]], next);
            const std::int64_t candidate_cost =
                manhattan(prev, bins[sequence[j]]) + manhattan(bins[sequence[i]], next);
            if (candidate_cost < current_cost) {
                std::reverse(sequence.begin() + static_cast<std::ptrdiff_t>(i),
                             sequence.begin() + static_cast<std::ptrdiff_t>(j) + 1);
                return true;
            }
        }
    }
    return false;
}

std::pair<std::vector<std::size_t>, std::int64_t> optimize(const std::vector<Point>& bins,
                                                           const Point& depot) {
    if (bins.empty()) {
        return {{}, 0};
    }
    std::vector<std::size_t> sequence = nearest_neighbor(bins, depot);
    while (two_opt_single_improvement(bins, depot, sequence)) {
    }
    return {sequence, route_distance(bins, depot, sequence)};
}

}  // namespace

PYBIND11_MODULE(pickpath_native, m) {
    m.doc() = "C++ pick-path optimiser (behavioural twin of pickpath.reference)";
    m.def(
        "optimize_route",
        [](const std::vector<Point>& bins, const Point& depot) {
            pybind11::gil_scoped_release release;  // pure CPU work from here on
            return optimize(bins, depot);
        },
        pybind11::arg("bins"), pybind11::arg("depot") = Point{0, 0});
}
