"""Reference execution: run a notebook's cells in order in this interpreter, no notebook tool.

It gives the expected checksum of a generated notebook and the per-cell work times that bound
what any tool can reach (the critical path). It is not one of the tools under test.
"""

from __future__ import annotations

import ast
import asyncio
import contextlib
import copy
import io
import json
import os
import statistics
import tempfile
from pathlib import Path

from nbbench.generate import Notebook, build, setup_cell
from nbbench.registry import Problem
from nbbench.shapes import critical_path

FLAGS = ast.PyCF_ALLOW_TOP_LEVEL_AWAIT


def run_cell(source: str, namespace: dict, name: str = "<cell>") -> None:
    code = compile(source, name, "exec", flags=FLAGS)
    pending = eval(code, namespace)
    if pending is not None:
        asyncio.run(pending)


def execute(notebook: Notebook, port: int = 0, quiet: bool = True) -> dict:
    """Run every cell; return result.json plus measured per-cell work and the critical path."""
    with tempfile.TemporaryDirectory(prefix="nbbench-ref-") as folder:
        env = {"NBBENCH_DIR": folder, "NBBENCH_PORT": str(port)}
        saved = {key: os.environ.get(key) for key in env}
        os.environ.update(env)
        namespace: dict = {"__name__": "__main__"}
        sink = io.StringIO() if quiet else None
        try:
            with contextlib.redirect_stdout(sink) if sink else contextlib.nullcontext():
                for index, source in enumerate(notebook.cells):
                    run_cell(source, namespace, f"<cell {index}>")
            result = json.loads((Path(folder) / "result.json").read_text())
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    work = {i: end - start for i, (start, end) in enumerate(result["spans"], start=1)}
    result["work_s"] = work
    result["critical_path_s"] = critical_path(notebook.graph, work)
    result["sequential_s"] = sum(work.values())
    return result


def time_work(problem: Problem, size: str, repeats: int = 5, port: int = 0) -> dict:
    """Median and spread of one `work(x0, i)` call, and whether work changed its input."""
    with tempfile.TemporaryDirectory(prefix="nbbench-cal-") as folder:
        os.environ["NBBENCH_DIR"] = folder
        os.environ["NBBENCH_PORT"] = str(port)
        namespace: dict = {"__name__": "__main__"}
        with contextlib.redirect_stdout(io.StringIO()):
            run_cell(setup_cell(problem, size), namespace)
        x0 = namespace["x0"]
        before = namespace["digest"](x0)
        pristine = copy.deepcopy(x0)
        times = []
        awaited = "await " if problem.is_async else ""
        reps = problem.params[size].get("reps", 1)
        for i in range(1, repeats + 1):
            source = (f"_t = time.time()\n_y = x0\nfor _rep in range({reps}):\n    _y = {awaited}work(_y, {i})\n"
                      "_elapsed = time.time() - _t\n")
            run_cell(source, namespace)
            times.append(namespace["_elapsed"])
        mutated = namespace["digest"](x0) != before or not _same(x0, pristine)
    return {"median_ms": 1000 * statistics.median(times), "min_ms": 1000 * min(times),
            "max_ms": 1000 * max(times), "mutates_input": mutated}


def _same(a: object, b: object) -> bool:
    try:
        import numpy as np

        if isinstance(a, np.ndarray):
            return bool(np.array_equal(a, b))
    except ImportError:
        pass
    if hasattr(a, "equals"):
        return bool(a.equals(b))
    return a == b


def checksum(problem: Problem | str, size: str, shape: str, n: int, port: int = 0) -> str:
    return execute(build(problem, size, shape, n), port)["checksum"]
