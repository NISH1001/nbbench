import ast
import json

import pytest

from nbbench import registry
from nbbench.generate import FORMATS, build, check, names, to_gpy, to_jupyter, to_marimo, write
from nbbench.shapes import critical_path, expected_critical_path, parents

PROBLEMS = list(registry.problems())
SHAPES = list(registry.shapes())


@pytest.mark.parametrize("problem", PROBLEMS)
@pytest.mark.parametrize("shape", SHAPES)
def test_every_problem_builds_in_every_shape(problem, shape):
    notebook = build(problem, "s", shape, 12)
    assert len(notebook.cells) == 14
    for source in (to_gpy(notebook.cells), to_marimo(notebook.cells)):
        ast.parse(source)
    json.loads(to_jupyter(notebook.cells))


@pytest.mark.parametrize("problem", PROBLEMS)
def test_problem_metadata_is_complete(problem):
    entry = registry.problems()[problem]
    assert entry.bound in {"cpu", "disk", "net", "mixed", "render"}
    assert entry.domain in {"micro", "datasci", "ml", "text", "viz"}
    assert set(entry.params) == set(registry.sizes())
    assert entry.params["l"].get("reps") == 10
    defined = names(entry.source)[0]
    assert {"initial", "work", "combine", "digest"} <= defined


@pytest.mark.parametrize("shape", SHAPES)
@pytest.mark.parametrize("n", [1, 2, 3, 10, 100])
def test_shape_critical_path(shape, n):
    graph = parents(shape, n)
    assert sorted(graph) == list(range(1, n + 1))
    assert all(p < i for i, ps in graph.items() for p in ps)
    assert critical_path(graph) == expected_critical_path(shape, n)


def test_dag_is_seeded():
    assert parents("dag", 50, seed=3) == parents("dag", 50, seed=3)
    assert parents("dag", 50, seed=3) != parents("dag", 50, seed=4)


def test_redefinition_is_rejected():
    with pytest.raises(ValueError, match="'a' is defined in cell 0 and cell 1"):
        check(["a = 1\n", "a = 2\n"])


def test_private_names_may_repeat():
    check(["_a = 1\n", "_a = 2\n"])


def test_large_size_feeds_work_back_into_itself():
    cell = build("pyloop", "l", "chain", 3).cells[2]
    assert "x2 = work(x1, 2)\nfor rep2 in range(1, 10):\n    x2 = work(x2, 2)\n" in cell


def test_fanin_combines_parents():
    cells = build("matmul", "s", "fanout", 5).cells
    assert "x5 = work(combine([x2, x3, x4]), 5)" in cells[5]


def test_async_problem_awaits_in_cell_and_marimo_cell_is_async():
    notebook = build("http_async", "s", "independent", 2)
    assert "x1 = await work(x0, 1)" in notebook.cells[1]
    marimo = to_marimo(notebook.cells)
    assert marimo.count("async def _(") == 2


def test_marimo_cells_take_only_what_they_read():
    marimo = to_marimo(build("matmul", "s", "chain", 3).cells)
    assert "def _(digest, time, work, x1):" in marimo
    assert "return (d2, span2, t0_2, x2,)" in marimo


def test_write_creates_every_format(tmp_path):
    folder = write(build("pyloop", "s", "dag", 20), tmp_path)
    meta = json.loads((folder / "meta.json").read_text())
    assert meta["critical_path_cells"] == 3
    for fmt in FORMATS:
        assert (folder / meta["files"][fmt]).exists()
