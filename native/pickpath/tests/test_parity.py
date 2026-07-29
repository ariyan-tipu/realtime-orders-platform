"""Engine parity: the C++ implementation must be behaviourally identical to
the pure-Python reference: same sequences, same distances, on the same
inputs. Both engines are deterministic by construction (identical
tie-breaking), which is what makes exact equality assertable."""

import random

import pytest

import pickpath

pytestmark = pytest.mark.skipif(
    not pickpath.native_available(), reason="native engine not built in this environment"
)


def test_native_matches_python_reference_exactly(unique_bins):
    rng = random.Random(2024)
    for _ in range(150):
        bins = unique_bins(rng, rng.randint(0, 40))
        py = pickpath.optimize_route(bins, engine="python")
        native = pickpath.optimize_route(bins, engine="native")

        assert native.sequence == py.sequence
        assert native.total_distance == py.total_distance
        # Belt and braces: the reported distance must equal the recomputed one.
        assert native.total_distance == pickpath.route_distance(bins, (0, 0), native.sequence)


def test_native_engine_reports_itself():
    result = pickpath.optimize_route([(4, 4), (1, 2)], engine="native")
    assert result.engine == "native"

    auto = pickpath.optimize_route([(4, 4), (1, 2)])
    assert auto.engine == "native"  # best-available selection prefers C++
