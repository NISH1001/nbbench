"""The sweep: every notebook of the grid, every tool, `runs` times, in a shuffled tool order.

Per notebook, the reference run (no tool) gives the expected checksum and the uncontended work of
every cell; the critical path over the shape uses that work, so a tool's efficiency is
`critical path / span` against a bound no tool can beat. Per tool run:

  ready        s from launch until the tool can take input (gpy: first frame; servers: HTTP)
  first, last  s from launch until the first work cell starts / the collector cell finishes
  span         first work cell start → last work cell end
  work_ms      mean time inside a work cell
  gap_ms       mean time between one cell ending and the next starting, in start order
               (negative when cells overlap)
  overlap      most work cells running at the same moment
  efficiency   best possible / span, where best possible = max(reference critical path,
               reference total work / CPUs) (1.0 = no schedule on this machine could do better)
  mem_mb       memory of the tool's process tree when the notebook finished
  ok           checksum equals the reference and the kernel ran in the workload interpreter
"""

from __future__ import annotations

import json
import os
import platform
import random
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from importlib import metadata
from pathlib import Path

from nbbench import __version__, adapters, reference
from nbbench.generate import Notebook, build, write
from nbbench.shapes import critical_path

BLAS_THREADS = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "MKL_NUM_THREADS")
METRICS = ("ready", "first", "last", "span", "work_ms", "gap_ms", "overlap", "efficiency", "mem_mb")


def overlap(spans: list[tuple[float, float]]) -> int:
    events = sorted([(start, 1) for start, _ in spans] + [(end, -1) for _, end in spans], key=lambda e: (e[0], e[1]))
    running = most = 0
    for _, step in events:
        running += step
        most = max(most, running)
    return most


def best_possible(reference: dict, cpus: int | None = None) -> float:
    """No schedule beats the longer of the critical path and all the work spread over every core."""
    return max(reference["critical_path_s"], reference["sequential_s"] / (cpus or os.cpu_count() or 1))


def measure(tool: str, notebook: Notebook, folder: Path, expected: dict, timeout: float, port: int,
            gpy: str | None) -> dict:
    workdir = Path(tempfile.mkdtemp(prefix=f"nbbench-{tool}-"))
    try:
        for item in folder.iterdir():
            shutil.copy(item, workdir / item.name)
        (workdir / "data").mkdir()
        (workdir / ".venv").symlink_to(sys.prefix)
        launch, memory = adapters.launch(tool, workdir, timeout, port, gpy)
        result = json.loads(adapters.result_path(workdir).read_text())
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    spans = [tuple(span) for span in result["spans"]]
    ordered = sorted(spans)
    starts = [start for start, _ in spans]
    span = max(end for _, end in spans) - min(starts)
    gaps = [ordered[k + 1][0] - ordered[k][1] for k in range(len(ordered) - 1)]
    same_kernel = os.path.realpath(result["prefix"]) == os.path.realpath(sys.prefix)
    return {
        "tool": tool,
        "ready": launch.ready,
        "first": min(starts) - launch.t0,
        "last": result["done"] - launch.t0,
        "span": span,
        "work_ms": 1000 * statistics.mean(end - start for start, end in spans),
        "gap_ms": 1000 * statistics.mean(gaps) if gaps else None,
        "overlap": overlap(spans),
        "efficiency": best_possible(expected) / span if span > 0 else None,
        "mem_mb": memory,
        "checksum": result["checksum"],
        "ok": result["checksum"] == expected["checksum"] and same_kernel,
        "same_kernel": same_kernel,
        "own_critical_path_s": critical_path(notebook.graph, {i: e - s for i, (s, e) in enumerate(spans, 1)}),
    }


def summarize(runs: list[dict]) -> dict:
    row = {}
    for key in METRICS:
        values = [run[key] for run in runs if run.get(key) is not None]
        row[key] = statistics.mean(values) if values else None
        row[f"{key}_std"] = statistics.stdev(values) if len(values) > 1 else (0.0 if values else None)
    row["ok"] = all(run["ok"] for run in runs)
    return row


def _version(package: str) -> str | None:
    """The installed version, with the git commit when it was installed from git."""
    try:
        found = metadata.distribution(package)
    except metadata.PackageNotFoundError:
        return None
    origin = json.loads(found.read_text("direct_url.json") or "{}")
    commit = origin.get("vcs_info", {}).get("commit_id")
    return f"{found.version}+{commit[:12]}" if commit else found.version


def machine(tools: list[str], gpy: str | None) -> dict:
    """Where and with what the sweep ran, written next to the results."""
    gpy_version = None
    command = adapters.gpy_command(gpy)
    if command and any(tool.startswith("gpy") for tool in tools):
        try:
            gpy_version = subprocess.run([*command, "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            gpy_version = None
    return {
        "nbbench": __version__,
        "date": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpus": os.cpu_count(),
        "load": os.getloadavg(),
        "python": sys.version,
        "prefix": sys.prefix,
        "gpy": {"command": command, "version": gpy_version},
        "packages": {name: _version(name) for name in
                     ("gpynb", "jupyterlab", "jupyter-server", "ipykernel", "marimo", "numpy", "pandas", "scikit-learn", "pyarrow", "pillow",
                      "matplotlib")},
        "blas_threads": {name: os.environ.get(name) for name in BLAS_THREADS},
    }


def warn_if_busy() -> None:
    load, cores = os.getloadavg()[0], os.cpu_count() or 1
    if load > cores / 2:
        print(f"warning: load average {load:.1f} on {cores} cores; results will be slow and noisy", file=sys.stderr)


def sweep(notebooks: list[Notebook], tools: list[str], runs: int, timeout: float, port: int, gpy: str | None,
          out: Path | None, seed: int = 0, log=print) -> dict:
    for name in BLAS_THREADS:
        os.environ[name] = "1"
    warn_if_busy()
    report = {"meta": machine(tools, gpy), "rows": []}
    shuffle = random.Random(seed)
    root = Path(tempfile.mkdtemp(prefix="nbbench-build-"))
    try:
        warmup = build("pyloop", "s", "independent", 1)
        warm_folder = write(warmup, root)
        warm_expected = reference.execute(warmup, port)
        for tool in tools:
            measure(tool, warmup, warm_folder, warm_expected, timeout, port, gpy)
        log(f"{'notebook':34}{'tool':16}" + "".join(f"{m:>12}" for m in ("last", "span", "gap_ms", "overlap", "effic", "mem_mb")) + "  ok")
        for notebook in notebooks:
            folder = write(notebook, root)
            expected = reference.execute(notebook, port)
            measured = {tool: [] for tool in tools}
            for _ in range(runs):
                order = tools[:]
                shuffle.shuffle(order)
                for tool in order:
                    try:
                        measured[tool].append(measure(tool, notebook, folder, expected, timeout, port, gpy))
                    except (TimeoutError, RuntimeError) as error:
                        measured[tool].append({"tool": tool, "ok": False, "error": str(error)})
            for tool in tools:
                good = [run for run in measured[tool] if "error" not in run]
                row = {**notebook.meta(), "tool": tool, "reference": {
                    "checksum": expected["checksum"], "critical_path_s": expected["critical_path_s"],
                    "sequential_s": expected["sequential_s"]}, "runs": measured[tool],
                    **summarize(good), "ok": bool(good) and len(good) == len(measured[tool]) and summarize(good)["ok"]}
                report["rows"].append(row)
                log(_line(notebook.name, tool, row))
            if out:
                out.write_text(json.dumps(report, indent=1) + "\n")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return report


def _line(name: str, tool: str, row: dict) -> str:
    def cell(key: str, digits: int) -> str:
        value = row.get(key)
        return f"{value:12.{digits}f}" if value is not None else f"{'—':>12}"

    return (f"{name:34}{tool:16}{cell('last', 3)}{cell('span', 3)}{cell('gap_ms', 2)}{cell('overlap', 1)}"
            f"{cell('efficiency', 2)}{cell('mem_mb', 0)}  {'yes' if row['ok'] else 'NO'}")
