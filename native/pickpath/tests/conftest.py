import random

import pytest


@pytest.fixture
def unique_bins():
    def _make(rng: random.Random, n: int, width: int = 60, height: int = 25) -> list:
        coords: set[tuple[int, int]] = set()
        while len(coords) < n:
            coords.add((rng.randint(0, width), rng.randint(0, height)))
        return sorted(coords)  # deterministic input order for reproducible routes

    return _make
