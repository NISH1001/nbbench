"""Dependency shapes between work cells, as specified in `datasets/shapes.json`."""

from __future__ import annotations

import math
import random

from nbbench.registry import shapes


def parents(shape: str, n: int, width: int = 8, fanin: int = 2, seed: int = 0) -> dict[int, list[int]]:
    """Parents of every work cell 1..n; an empty list means the cell reads x0."""
    if shape not in shapes():
        raise KeyError(f"no shape {shape!r}; known: {', '.join(shapes())}")
    cells = range(1, n + 1)
    if shape == "independent":
        return {i: [] for i in cells}
    if shape == "chain":
        return {i: [i - 1] if i > 1 else [] for i in cells}
    if shape == "fanout":
        return {i: _fanout(i, n) for i in cells}
    return _dag(n, width, fanin, seed)


def _fanout(i: int, n: int) -> list[int]:
    if i == 1:
        return []
    if i < n or n < 3:
        return [1] if i < n else [n - 1]
    return list(range(2, n))


def _dag(n: int, width: int, fanin: int, seed: int) -> dict[int, list[int]]:
    found = {}
    for i in range(1, n + 1):
        layer = (i - 1) // width
        if layer == 0:
            found[i] = []
            continue
        previous = list(range((layer - 1) * width + 1, layer * width + 1))
        picked = random.Random(f"{seed}:{i}").sample(previous, min(fanin, len(previous)))
        found[i] = sorted(picked)
    return found


def critical_path(graph: dict[int, list[int]], cost: dict[int, float] | None = None) -> float:
    """Longest path through the graph, in cells, or in `cost` units when given."""
    longest: dict[int, float] = {}
    for i in sorted(graph):
        own = cost[i] if cost else 1
        longest[i] = own + max((longest[p] for p in graph[i]), default=0)
    return max(longest.values(), default=0)


def expected_critical_path(shape: str, n: int, width: int = 8) -> int:
    return {"independent": 1, "chain": n, "fanout": min(n, 3), "dag": math.ceil(n / width)}[shape]
