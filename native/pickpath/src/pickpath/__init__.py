"""Warehouse pick-path optimisation with a pluggable engine.

`optimize_route` transparently uses the C++ extension (`pickpath-native`) when
it is installed and falls back to the pure-Python reference implementation
otherwise, so the core service works in any environment and gets the fast
engine wherever it has been built (Docker image, CI).
"""

from pickpath.reference import held_karp_exact, manhattan, optimize_route_py, route_distance
from pickpath.types import Point, RouteResult

try:
    import pickpath_native as _native
except ImportError:  # pure-Python environments (e.g. no compiler on host)
    _native = None

__all__ = [
    "Point",
    "RouteResult",
    "held_karp_exact",
    "manhattan",
    "native_available",
    "optimize_route",
    "optimize_route_py",
    "route_distance",
]


def native_available() -> bool:
    return _native is not None


def optimize_route(
    bins: list[Point],
    depot: Point = (0, 0),
    engine: str | None = None,
) -> RouteResult:
    """Optimise the visiting order for `bins`.

    engine: None picks the fastest available; "native" or "python" force a
    specific implementation (used by the parity tests and benchmarks).
    """
    if engine not in (None, "native", "python"):
        raise ValueError(f"unknown engine {engine!r}")
    use_native = _native is not None if engine is None else engine == "native"
    if use_native:
        if _native is None:
            raise RuntimeError("pickpath-native is not installed in this environment")
        sequence, distance = _native.optimize_route(list(bins), tuple(depot))
        return RouteResult(sequence=list(sequence), total_distance=int(distance), engine="native")
    return optimize_route_py(list(bins), depot)
