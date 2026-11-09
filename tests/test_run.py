"""The runner: metrics from spans, and real launches of each tool on a small notebook.

gpy is tested only when `NBBENCH_GPY` names a gpy command or gpython checkout.
"""

import os

import pytest

from nbbench import adapters, server
from nbbench.generate import build
from nbbench.run import overlap, summarize, sweep


def test_overlap_counts_cells_running_together():
    assert overlap([(0, 1), (1, 2), (2, 3)]) == 1
    assert overlap([(0, 3), (1, 2), (1.5, 4)]) == 3
    assert overlap([(0, 1), (0.5, 2), (3, 4)]) == 2


def test_summarize_skips_missing_values():
    row = summarize([{"ok": True, "last": 1.0, "gap_ms": None}, {"ok": True, "last": 3.0, "gap_ms": 2.0}])
    assert row["last"] == 2.0
    assert row["gap_ms"] == 2.0
    assert row["ok"]


def test_gpy_command_finds_a_checkout(tmp_path):
    binary = tmp_path / ".venv" / "bin" / "gpy"
    binary.parent.mkdir(parents=True)
    binary.write_text("")
    assert adapters.gpy_command(str(tmp_path)) == [str(binary)]
    assert adapters.gpy_command(str(tmp_path / "missing")) is None


def test_gpy_python_reads_direct_and_relocatable_launchers(tmp_path):
    import sys

    direct = tmp_path / "direct" / "gpy"
    direct.parent.mkdir()
    direct.write_text(f"#!{sys.executable}\nimport gpython\n")
    assert adapters.gpy_python([str(direct)]) == sys.executable

    relocatable = tmp_path / "uv" / "bin" / "gpy"
    relocatable.parent.mkdir(parents=True)
    relocatable.write_text("#!/bin/sh\n'''exec' \"$(dirname -- \"$(realpath -- \"$0\")\")\"/'python' \"$0\" \"$@\"\n' '''\n")
    (relocatable.parent / "python").symlink_to(sys.executable)
    assert adapters.gpy_python([str(relocatable)]) == str(relocatable.parent / "python")


def test_each_tool_gets_its_own_config(tmp_path):
    env = adapters.tool_env("gpy-concurrent", tmp_path, 1234)
    assert env["XDG_CONFIG_HOME"] == str(tmp_path / "config")
    assert (tmp_path / "config" / "gpython" / "config.toml").read_text() == "concurrent = true\n"
    assert env["NBBENCH_PORT"] == "1234"


TOOLS = ["jupyterlab", "marimo"] + (["gpy", "gpy-concurrent"] if os.environ.get("NBBENCH_GPY") else [])


@pytest.mark.parametrize("tool", TOOLS)
def test_tool_runs_a_notebook_and_matches_the_reference(tool):
    proc, port = server.start()
    try:
        notebooks = [build("matmul", "s", "fanout", 4), build("http_async", "s", "chain", 3)]
        report = sweep(notebooks, [tool], runs=1, timeout=180, port=port, gpy=os.environ.get("NBBENCH_GPY"),
                       out=None, log=lambda line: None)
    finally:
        proc.kill()
    for row in report["rows"]:
        assert row["ok"], row["runs"]
        assert row["last"] > row["span"] > 0
        assert 0 < row["efficiency"] <= 1.5
    assert report["meta"]["cpus"] == os.cpu_count()
