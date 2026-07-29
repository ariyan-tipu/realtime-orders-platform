import random

import pytest

import pickpath
from pickpath import held_karp_exact, manhattan, optimize_route, optimize_route_py, route_distance
from pickpath.reference import _nearest_neighbor


def test_manhattan_distance():
    assert manhattan((0, 0), (3, 4)) == 7
    assert manhattan((5, 5), (5, 5)) == 0


def test_empty_order_is_a_zero_route():
    result = optimize_route([])
    assert result.sequence == []
    assert result.total_distance == 0


def test_single_bin_is_out_and_back():
    result = optimize_route([(3, 4)])
    assert result.sequence == [0]
    assert result.total_distance == 14  # 7 out + 7 back


def test_route_distance_includes_both_depot_legs():
    bins = [(0, 5), (5, 5)]
    assert route_distance(bins, (0, 0), [0, 1]) == 5 + 5 + 10


def test_sequence_is_a_permutation_of_all_bins(unique_bins):
    rng = random.Random(11)
    bins = unique_bins(rng, 25)
    result = optimize_route_py(bins)
    assert sorted(result.sequence) == list(range(25))


def test_two_opt_never_worse_than_greedy_construction(unique_bins):
    rng = random.Random(3)
    for n in [5, 10, 20, 35]:
        bins = unique_bins(rng, n)
        greedy_distance = route_distance(bins, (0, 0), _nearest_neighbor(bins, (0, 0)))
        assert optimize_route_py(bins).total_distance <= greedy_distance


def test_heuristic_against_exact_oracle(unique_bins):
    """Held-Karp gives the true optimum for small instances. The heuristic can
    never beat it (sanity) and, over this fixed-seed suite, stays within 5% of
    it on average (quality). Deterministic, so never flaky."""
    rng = random.Random(7)
    ratios = []
    for _ in range(40):
        bins = unique_bins(rng, rng.randint(1, 8), width=20, height=20)
        exact = held_karp_exact(bins)
        heuristic = optimize_route_py(bins).total_distance
        assert heuristic >= exact
        ratios.append(heuristic / exact if exact else 1.0)
    assert sum(ratios) / len(ratios) <= 1.05


def test_deterministic_across_runs(unique_bins):
    rng = random.Random(99)
    bins = unique_bins(rng, 30)
    first = optimize_route_py(list(bins))
    second = optimize_route_py(list(bins))
    assert first.sequence == second.sequence
    assert first.total_distance == second.total_distance


def test_held_karp_rejects_large_instances(unique_bins):
    rng = random.Random(1)
    with pytest.raises(ValueError, match="limited to 12"):
        held_karp_exact(unique_bins(rng, 13))


def test_forcing_missing_native_engine_raises():
    if pickpath.native_available():
        pytest.skip("native engine installed; failure path not reachable")
    with pytest.raises(RuntimeError, match="not installed"):
        optimize_route([(1, 1)], engine="native")


def test_unknown_engine_rejected():
    with pytest.raises(ValueError, match="unknown engine"):
        optimize_route([(1, 1)], engine="fortran")
