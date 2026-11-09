"""Neutral form → notebook cells → JupyterLab `.ipynb`, marimo `.py` and gpy percent `.py`.

A notebook is one setup cell (prelude, the problem's source, `x0 = initial()`), N work cells
wired by a shape, and one collector cell that writes `result.json`. Every format gets the same
cell sources; only the wrapping differs.
"""

from __future__ import annotations

import ast
import builtins
import json
from dataclasses import dataclass, field
from pathlib import Path

from nbbench import __version__
from nbbench.registry import Problem, problems
from nbbench.shapes import critical_path, parents

FORMATS = ("jupyter", "marimo", "gpy")
FILES = {"jupyter": "nb.ipynb", "marimo": "nb_marimo.py", "gpy": "nb_gpy.py"}

PRELUDE = '''import os
import sys
import tempfile
import time

P = {params!r}
DIR = os.environ.get("NBBENCH_DIR") or tempfile.mkdtemp(prefix="nbbench-")
HOST = "127.0.0.1"
PORT = int(os.environ.get("NBBENCH_PORT", "0"))


def finish(spans, digests):
    import hashlib
    import json

    checksum = hashlib.blake2b("".join(digests).encode()).hexdigest()[:16]
    result = {{"prefix": sys.prefix, "spans": spans, "digests": digests, "checksum": checksum, "done": time.time()}}
    with open(os.path.join(DIR, "result.json"), "w") as out:
        json.dump(result, out)
    print("checksum", checksum)
'''


@dataclass
class Notebook:
    problem: Problem
    size: str
    shape: str
    n: int
    graph: dict[int, list[int]]
    cells: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return f"{self.problem.id}-{self.size}-{self.shape}-n{self.n}"

    def meta(self) -> dict:
        return {
            "nbbench": __version__,
            "problem": self.problem.id,
            "legacy": self.problem.legacy,
            "bound": self.problem.bound,
            "domain": self.problem.domain,
            "size": self.size,
            "params": self.problem.params[self.size],
            "shape": self.shape,
            "n": self.n,
            "cells": len(self.cells),
            "parents": {str(i): p for i, p in self.graph.items()},
            "critical_path_cells": critical_path(self.graph),
            "files": FILES,
        }


def build(problem: Problem | str, size: str = "s", shape: str = "independent", n: int = 10, **shape_args) -> Notebook:
    problem = problems()[problem] if isinstance(problem, str) else problem
    graph = parents(shape, n, **shape_args)
    notebook = Notebook(problem, size, shape, n, graph)
    reps = problem.params[size].get("reps", 1)
    notebook.cells = [setup_cell(problem, size)] + [work_cell(problem, i, graph[i], reps) for i in range(1, n + 1)]
    notebook.cells.append(collector_cell(n))
    check(notebook.cells)
    return notebook


def setup_cell(problem: Problem, size: str) -> str:
    prelude = PRELUDE.format(params=problem.params[size])
    return f"{prelude}\n\n{problem.source.rstrip()}\n\n\nx0 = initial()\nprint('setup', {problem.id!r})\n"


def work_cell(problem: Problem, i: int, sources: list[int], reps: int = 1) -> str:
    """One work cell; `reps` > 1 feeds the output back into `work` that many times (size `l`)."""
    if not sources:
        given = "x0"
    elif len(sources) == 1:
        given = f"x{sources[0]}"
    else:
        given = f"combine([{', '.join(f'x{p}' for p in sources)}])"
    awaited = "await " if problem.is_async else ""
    passes = f"x{i} = {awaited}work({given}, {i})\n"
    if reps > 1:
        passes += f"for rep{i} in range(1, {reps}):\n    x{i} = {awaited}work(x{i}, {i})\n"
    return (
        f"t0_{i} = time.time()\n"
        f"{passes}"
        f"span{i} = (t0_{i}, time.time())\n"
        f"d{i} = digest(x{i})\n"
        f"print({i}, d{i})\n"
    )


def collector_cell(n: int) -> str:
    spans = ", ".join(f"span{i}" for i in range(1, n + 1))
    digests = ", ".join(f"d{i}" for i in range(1, n + 1))
    return f"finish([{spans}], [{digests}])\n"


class _TopLevel(ast.NodeVisitor):
    """Names a cell defines at its top level and every name it loads anywhere."""

    def __init__(self) -> None:
        self.defs: set[str] = set()
        self.loads: set[str] = set()
        self.depth = 0

    def _scoped(self, node: ast.AST) -> None:
        self.depth += 1
        self.generic_visit(node)
        self.depth -= 1

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if self.depth == 0:
            self.defs.add(node.name)
        for decorator in node.decorator_list:
            self.visit(decorator)
        self._scoped(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if self.depth == 0:
            self.defs.add(node.name)
        self._scoped(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self._scoped(node)

    def visit_ListComp(self, node: ast.AST) -> None:
        self._scoped(node)

    visit_SetComp = visit_DictComp = visit_GeneratorExp = visit_ListComp

    def visit_Import(self, node: ast.Import | ast.ImportFrom) -> None:
        if self.depth == 0:
            self.defs.update((alias.asname or alias.name).split(".")[0] for alias in node.names)

    visit_ImportFrom = visit_Import

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self.loads.add(node.id)
        elif self.depth == 0:
            self.defs.add(node.id)


def names(source: str) -> tuple[set[str], set[str]]:
    """(top-level definitions, loaded names) of one cell, ignoring cell-private `_names`."""
    visitor = _TopLevel()
    visitor.visit(ast.parse(source))
    public = {name for name in visitor.defs if not name.startswith("_")}
    return public, visitor.loads - set(dir(builtins))


def check(cells: list[str]) -> None:
    """The marimo rule: every public name is defined in exactly one cell."""
    owner: dict[str, int] = {}
    for index, source in enumerate(cells):
        for name in names(source)[0]:
            if name in owner:
                raise ValueError(f"{name!r} is defined in cell {owner[name]} and cell {index}")
            owner[name] = index


def to_gpy(cells: list[str]) -> str:
    return "\n\n".join(f"# %%\n{source.rstrip()}" for source in cells) + "\n"


def to_jupyter(cells: list[str]) -> str:
    notebook = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
            "language_info": {"name": "python"},
        },
        "cells": [
            {
                "cell_type": "code",
                "id": f"cell-{index}",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": source.rstrip().splitlines(keepends=True),
            }
            for index, source in enumerate(cells)
        ],
    }
    return json.dumps(notebook, indent=1) + "\n"


def to_marimo(cells: list[str]) -> str:
    """Each cell becomes a function taking the names it reads from other cells and returning its own."""
    found = [names(source) for source in cells]
    defined = {name: index for index, (defs, _) in enumerate(found) for name in defs}
    parts = ["import marimo\n\n__generated_with = \"nbbench\"\napp = marimo.App()\n\n"]
    for index, source in enumerate(cells):
        defs, loads = found[index]
        args = sorted(name for name in loads if name in defined and defined[name] != index)
        kind = "async def" if _awaits(source) else "def"
        body = "".join(f"    {line}\n" if line.strip() else "\n" for line in source.rstrip().splitlines())
        returns = f"    return ({', '.join(sorted(defs))},)\n" if defs else "    return\n"
        parts.append(f"\n@app.cell\n{kind} _({', '.join(args)}):\n{body}{returns}\n")
    parts.append("\nif __name__ == \"__main__\":\n    app.run()\n")
    return "".join(parts)


def _awaits(source: str) -> bool:
    tree = ast.parse(source)
    outer = [node for node in ast.walk(tree) if isinstance(node, ast.Await)]
    inner = {
        id(node)
        for function in ast.walk(tree)
        if isinstance(function, ast.AsyncFunctionDef)
        for node in ast.walk(function)
        if isinstance(node, ast.Await)
    }
    return any(id(node) not in inner for node in outer)


WRITERS = {"jupyter": to_jupyter, "marimo": to_marimo, "gpy": to_gpy}


def write(notebook: Notebook, root: Path, formats: tuple[str, ...] = FORMATS) -> Path:
    folder = root / notebook.name
    folder.mkdir(parents=True, exist_ok=True)
    for fmt in formats:
        (folder / FILES[fmt]).write_text(WRITERS[fmt](notebook.cells))
    (folder / "meta.json").write_text(json.dumps(notebook.meta(), indent=1) + "\n")
    return folder
