# 01 — nbbench design

Date: 2026-11-09. Repo: `NISH1001/nbbench` (public, empty). Origin: gpy's workload eval
(`gpython/docs/plans/13-workload-eval.md`, `gpython/scripts/workbench.py`, `warmbench.py`).

## Why

There is no standard benchmark for notebook *tools* (pyperformance measures CPython, which is the
same in every tool). gpy's paper needs one, and gpy just gained concurrent execution of independent
cells, which the current eval (7 problems, independent cells only, ~10 ms each) cannot show.
nbbench is a tool-neutral, citable benchmark: anyone can add their notebook tool with an adapter.

Cost model it measures (from plan 13): `T(N) = start + Σᵢ (work_i + dispatch_i + render(output_i))`.
`work` is the user's code (identical interpreter in every tool: a control); `dispatch` and
`render` are the tool's cost. Concurrency adds a lower bound: a tool can never beat the
critical path of the cell dependency graph.

## Goals

- Workloads defined once, in nbbench's own neutral form (`datasets/`), and generated into each
  tool's format by the code in `src/nbbench/`.
- Four independent knobs per notebook: **problem**, **size**, **shape**, **N**.
- Problems tagged on two axes: `bound` (`cpu`, `disk`, `net`, `mixed`, `render`) and `domain`
  (`micro`, `datasci`, `ml`, `text`, `viz`). Breadth grows by adding registry entries.
- Tools at launch: `gpy` (sequential), `gpy-concurrent`, `jupyterlab`, `marimo`.
- Results reproducible and citable: pinned deps, raw per-run JSON, machine metadata, DOI.

## Non-goals

- Measuring CPython or library speed (`work` is a control).
- Browser rendering cost of JupyterLab/marimo (not counted, as in plan 13).
- Real-notebook replay (KGTorrent etc.) — possible later, not v0.1.
- GPUs, clusters, remote kernels.

## Anti-goals (failure even if it runs)

- Any workload authored *through* gpy or shaped to favour one tool.
- A tool looking fast by skipping, caching or reordering work incorrectly (every cell checks a
  checksum; wrong result = failed run).
- Generated notebooks that differ in semantics across formats.
- A dependency on the gpython package anywhere except the gpy adapter, which launches it as a
  process.

## The four knobs

- **Problem**: what a cell does. Keep the 7 from plan 13 (C1–C3, D1, D2, N1, N2, now
  `domain: micro`) and add data-science ones, e.g. pandas groupby/join/pivot, feature engineering,
  scikit-learn fits (logistic regression, random forest, k-means), CSV/Parquet round-trips, SQLite
  queries, regex/JSON text processing, image transforms (Pillow), matplotlib figures
  (`bound: render`, covers plan 13's H3). All data synthetic from a seed: no downloads.
- **Size**: presets `s` ≈ 10 ms, `m` ≈ 100 ms (per-problem data size, `nbbench calibrate`),
  `l` = `m` with `reps: 10` (the cell feeds `work`'s output back in ten times) so memory stays
  bounded. `figure` has a ~30 ms floor at `s`.
- **Shape**: dependency structure between work cells:
  `independent` (all read setup only), `chain` (cell i reads cell i−1),
  `fanout` (load → k parallel branches → combine), `diamond`, `dag` (seeded random DAG with a
  given width). Each shape knows its critical path.
- **N**: 1, 10, 100, 500, 1000 work cells after one setup cell.

Full cross-product is too large; the runner takes a sweep file naming which knobs vary and which
are fixed (e.g. N × tool at shape=independent, size=s; shape × tool at N=100, size=m).

## Neutral form and generation

A problem is one module in `datasets/problems/` exposing: metadata (id, title, bound, domain,
libs, size parameter per preset), `setup` source, a cell template taking the cell's inputs and
producing one named output, and a checksum function. Problem code must obey marimo's rules
(every name defined in exactly one cell, no in-place mutation of another cell's objects); the
generator checks this and refuses to emit otherwise.

`nbbench generate (problem, size, shape, N, seed) →`
- `.ipynb` (nbformat 4, no outputs) for JupyterLab,
- marimo `.py` (cells as functions with explicit args/returns),
- Jupytext percent `.py` (`# %%`) for gpy.

Cross-check: `marimo convert` of our `.ipynb` must give the same cell graph as our marimo file;
the CI executes every problem at N=1 in each format and compares checksums.

Generated notebooks go to `build/` (git-ignored). Samples (N=10, size s, each problem ×
independent, plus matmul in every shape) are committed under `datasets/samples/`. Notebooks read
`NBBENCH_DIR` and `NBBENCH_PORT` from the environment, so the same file runs anywhere.

Instrumentation must not add dependencies between cells: plan 13's per-cell `open(SPANS, 'a')`
is a shared file write, so a conservative analyzer (gpy's treats it as `$fs`) would serialise
every cell. Instead each work cell defines its own `span_i = (t0, t1)` (absolute epoch times; a
definition only), and one final collector cell reads every `span_i` and writes the spans file and
the done mark. The collector is part of every notebook in every format, so it costs every tool the
same. `first`/`last` come from the absolute span times. Setup writes `sys.prefix` so the run proves
every tool used the same interpreter.

Dependencies carry real data: a cell's computation consumes its inputs. Heavy data lives in the
setup cell and is only read; what flows between cells is a compact state (a vector, a small
Series, centroids, a hash) of the same kind as `x0`, so the size preset holds for every shape and
1000 cells do not hold 1000 copies of a big frame. Every problem defines `combine(xs)` for fan-in.

## Adapters

One per tool, each a small module with `launch(notebook, workdir) → run handle`, `run_all()`,
`wait_done(n)`, `memory()`, `kill()`. Ported from `warmbench.py`:
- `gpy`: pty launch of the installed `gpy` binary, answer terminal queries, F5 on first frame.
  `gpy-concurrent` is the same with `XDG_CONFIG_HOME` pointing at a temp dir whose
  `gpython/config.toml` sets `concurrent = true`.
- `jupyterlab`: `jupyter lab --no-browser`, REST + kernel WebSocket, all cells sent at once.
- `marimo`: `marimo edit --headless`, session WebSocket, run all.

Tool versions are pinned in nbbench's `uv.lock` (gpy from a pinned git commit until concurrent
mode is on PyPI) and recorded in every result. gpy-concurrent runs with its defaults
(`concurrent_verify` on), with the group cap and core count recorded in the result metadata.

## Metrics

Per run: `ready`, `first`, `last` (s from launch), `work_ms`, `gap_ms` (end of a cell to the next
cell's start, sequential tools), `span` (first start → last end), `mem_mb`, plus
`critical_path` and `efficiency = critical_path / span` (1.0 = as fast as the graph allows), and
the number of concurrent cell overlaps observed. The critical path uses per-cell work from the
sequential gpy run of the same notebook, not the concurrent run's own spans (contention inflates
those and would flatter efficiency); a run reports both. Mean, std, and every raw run in JSON.

Controls carried over from plan 13: one interpreter for all kernels, BLAS pinned to one thread,
local HTTP server outside tool process trees, tool order shuffled per run, one discarded warm-up
launch per tool, 5 runs, machine/load metadata.

## Repo layout

`datasets/` is the tool-agnostic benchmark (what gets cited); `nbbench/` is the package that
turns it into notebooks per tool and runs them. The wheel bundles `datasets/` (except samples),
so `uvx --from "nbbench[workloads] @ git+…" nbbench …` works anywhere, including gpy's CI.

```
README.md AGENTS.md CITATION.cff LICENSE (MIT) LICENSE-data (CC BY 4.0)
datasets/
  problems.json      registry (id, legacy id, bound, domain, libs, s/m/l params)
  problems/          one file per problem: initial, work, combine, digest
  shapes.json        shape rules, stated precisely enough to reimplement
  samples/           24 generated notebooks (nb.ipynb, nb_marimo.py, nb_gpy.py, meta.json)
nbbench/
  cli.py             list | generate | samples | reference | calibrate | serve   (done)
  registry.py shapes.py generate.py reference.py server.py                     (done)
  adapters.py run.py   `nbbench run` for gpy, gpy-concurrent, jupyterlab, marimo   (done)
  chart.py                                                                     (next)
results/<version>/   raw JSON + meta per release
docs/plans/
tests/
```

## State (2026-11-09)

Done: 21 problems (plan 13's 7 + 14 data-science), 4 shapes, generator for three formats,
reference runner, calibration, samples, 184 tests. The tests run generated notebooks in marimo and
a Jupyter kernel and match the reference checksum.

Finding: gpy's concurrency analysis (`gpython/src/gpython/concurrency.py`) puts the independent
work cells in one group for only 4 of 21 problems (matmul, rfft, pyloop, text_json). The rest run
one at a time because of false writes: setup data passed to a library call (`model.fit(FEATURES)`,
`SALES.assign`), `$fs` for the disk problems, and aliasing through `digest`. A gpy improvement
target; nbbench does not change problems to suit it.

`nbbench run` done (192 tests; 1000-cell runs pass in all four tools). Next: charts, gpy CI job,
idle-machine sweep, a gpy release with concurrent cells to pin in the `tools` extra.

## Publishing

Public GitHub repo; GitHub→Zenodo integration mints a DOI per tagged release (v0.1 with the
paper). Optional Hugging Face mirror of `datasets/` and `results/`. Cite JunoBench
(arXiv 2510.18013) as related notebook-benchmark work.

## Left to the builder

Exact list and parameters of the new data-science problems (aim ≥ 8 in v0.1), size calibration
method, sweep-file format, chart design, CI setup, module internals.

The marimo rule stays strict (cross-format equivalence depends on it): problems use
non-mutating idioms (`df.assign`, new arrays). Builder's call.

## Unresolved

- Free-threaded 3.14t as a sweep factor, or 3.13 only (current `.python-version`)?
- Should `nbbench run` also report each tool's own "cells it could have run together" next to
  what it achieved (needs a tool-specific hook; gpy has `concurrency.report`)?
- Name and DOI timing: v0.1 tag with the paper, or earlier?
