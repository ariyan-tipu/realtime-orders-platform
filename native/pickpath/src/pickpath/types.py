from dataclasses import dataclass

Point = tuple[int, int]


@dataclass(frozen=True, slots=True)
class RouteResult:
    """Optimised visiting order for a set of warehouse bins.

    `sequence` holds indices into the caller's bin list, not coordinates, so a
    route computed by either engine can be compared or replayed exactly.
    `total_distance` is Manhattan distance including the depot→first and
    last→depot legs.
    """

    sequence: list[int]
    total_distance: int
    engine: str
