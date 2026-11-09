"""Generated notebooks run, give the reference checksum, and give the same checksum in every format."""

import json
import os
import subprocess
import sys

import pytest

from nbbench import reference, registry, server
from nbbench.generate import build, write


@pytest.fixture(scope="module")
def port():
    proc, port = server.start()
    yield port
    proc.kill()


@pytest.mark.parametrize("problem", list(registry.problems()))
def test_reference_run_is_deterministic(problem, port):
    first = reference.execute(build(problem, "s", "dag", 10, width=4), port)
    second = reference.execute(build(problem, "s", "dag", 10, width=4), port)
    assert first["checksum"] == second["checksum"]
    assert len(first["spans"]) == 10
    assert first["critical_path_s"] <= first["sequential_s"]


@pytest.mark.parametrize("problem", list(registry.problems()))
def test_work_does_not_change_its_input(problem, port):
    assert not reference.time_work(registry.problems()[problem], "s", repeats=1, port=port)["mutates_input"]


CROSS = [("matmul", "chain"), ("pd_groupby", "fanout"), ("http_async", "dag"), ("text_regex", "independent")]


def _env(folder, port):
    return {**os.environ, "NBBENCH_DIR": str(folder), "NBBENCH_PORT": str(port)}


@pytest.mark.parametrize("problem,shape", CROSS)
def test_marimo_runs_the_generated_app(problem, shape, port, tmp_path):
    notebook = build(problem, "s", shape, 6)
    expected = reference.execute(notebook, port)["checksum"]
    folder = write(notebook, tmp_path / "nb")
    subprocess.run([sys.executable, str(folder / "nb_marimo.py")], env=_env(tmp_path, port), check=True,
                   capture_output=True, timeout=300)
    assert json.loads((tmp_path / "result.json").read_text())["checksum"] == expected


@pytest.mark.parametrize("problem,shape", CROSS)
def test_jupyter_kernel_runs_the_generated_notebook(problem, shape, port, tmp_path, monkeypatch):
    import nbformat
    from nbclient import NotebookClient

    notebook = build(problem, "s", shape, 6)
    expected = reference.execute(notebook, port)["checksum"]
    folder = write(notebook, tmp_path / "nb")
    for key, value in _env(tmp_path, port).items():
        monkeypatch.setenv(key, value)
    document = nbformat.read(folder / "nb.ipynb", as_version=4)
    nbformat.validate(document)
    NotebookClient(document, timeout=300, kernel_name="python3").execute()
    assert json.loads((tmp_path / "result.json").read_text())["checksum"] == expected


def test_gpy_file_is_the_cells_in_percent_format(tmp_path):
    notebook = build("sqlite", "s", "chain", 4)
    text = (write(notebook, tmp_path) / "nb_gpy.py").read_text()
    cells = [part.strip() for part in text.split("# %%\n") if part.strip()]
    assert cells == [source.strip() for source in notebook.cells]
