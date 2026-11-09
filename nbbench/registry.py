"""The dataset on disk: `datasets/problems.json`, `datasets/problems/*.py`, `datasets/shapes.json`."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

def _datasets() -> Path:
    """`NBBENCH_DATASETS`, else the repo's `datasets/` in a checkout, else the copy bundled in the wheel."""
    if "NBBENCH_DATASETS" in os.environ:
        return Path(os.environ["NBBENCH_DATASETS"])
    here = Path(__file__).resolve().parent
    checkout = here.parent / "datasets"
    return checkout if (checkout / "problems.json").exists() else here / "datasets"


DATASETS = _datasets()


@dataclass(frozen=True)
class Problem:
    id: str
    title: str
    bound: str
    domain: str
    libs: tuple[str, ...]
    params: dict[str, dict[str, int]] = field(hash=False)
    legacy: str | None = None
    is_async: bool = False

    @property
    def source(self) -> str:
        return (DATASETS / "problems" / f"{self.id}.py").read_text()


@cache
def catalog() -> dict:
    return json.loads((DATASETS / "problems.json").read_text())


@cache
def problems() -> dict[str, Problem]:
    found = {}
    for entry in catalog()["problems"]:
        found[entry["id"]] = Problem(
            id=entry["id"],
            title=entry["title"],
            bound=entry["bound"],
            domain=entry["domain"],
            libs=tuple(entry["libs"]),
            params=entry["params"],
            legacy=entry.get("legacy"),
            is_async=entry.get("async", False),
        )
    return found


def sizes() -> dict[str, int]:
    """Target milliseconds of work per cell for each size preset."""
    return catalog()["sizes"]


@cache
def shapes() -> dict[str, dict]:
    return {shape["id"]: shape for shape in json.loads((DATASETS / "shapes.json").read_text())["shapes"]}


def select(spec: str | None) -> list[Problem]:
    """Problems by comma-separated id, legacy id, `bound:x` or `domain:x`; all when empty."""
    every = problems()
    if not spec:
        return list(every.values())
    chosen = []
    for term in spec.split(","):
        key, _, value = term.partition(":")
        if value and key in ("bound", "domain"):
            chosen += [p for p in every.values() if getattr(p, key) == value]
        else:
            chosen += [p for p in every.values() if term in (p.id, p.legacy)] or _unknown(term)
    return list(dict.fromkeys(chosen))


def _unknown(term: str) -> list[Problem]:
    raise KeyError(f"no problem {term!r}; known: {', '.join(problems())}")
