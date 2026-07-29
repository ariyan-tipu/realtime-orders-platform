# pickpath

Warehouse pick-path optimisation for order batching: given the bin locations of
an order's items, find a short route depot → all bins → depot under the
Manhattan (aisle-walking) metric. This is a travelling-salesman variant, so the
package uses a deterministic nearest-neighbour construction followed by
first-improvement 2-opt refinement, plus a Held-Karp exact solver for small
instances used as a test oracle.

Two interchangeable engines:

- `pickpath` (this package): the pure-Python reference implementation, runs anywhere.
- `pickpath-native` (sibling directory): the same algorithm in C++ via pybind11,
  releasing the GIL during optimisation. Installed automatically in the Docker
  image and CI; `pickpath.optimize_route` picks it up when present.

Both engines are deliberately deterministic (identical tie-breaking) so the test
suite can assert they return byte-identical routes.
