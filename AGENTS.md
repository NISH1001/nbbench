# nbbench

A tool-neutral benchmark for notebook tools. `datasets/` is the benchmark (what gets cited);
`nbbench/` is the package that turns it into notebooks per tool (JupyterLab `.ipynb`, marimo `.py`,
gpy percent `.py`) and runs them. Design and decisions: `docs/plans/01-nbbench-design.md`.

`uv sync --extra workloads` once; `uv run pytest -q` runs the tests (about 15 s, they execute
notebooks in marimo and a Jupyter kernel). `uv run nbbench calibrate` times every problem; never
run it or any timing sweep while the tests or anything heavy runs.

## Rules for every agent

- **Neutrality comes first.** No problem, template or harness change may be shaped to favour a
  tool, including gpy (the project this came from). If a tool handles a natural workload badly,
  that is a result to report, not something to work around in `datasets/`.
- **Every format means the same thing.** Each public name is defined in exactly one cell (marimo's
  rule, enforced by `generate.check`); `work(x, i)` never changes `x` or setup data; a run is valid
  only when its checksum equals `nbbench reference`'s. Instrumentation must not add shared writes
  between cells: no shared file appends from work cells, no helper that receives `work` as an
  argument. Cell-level names are unique per cell (`t0_3`, `span3`, `rep3`).
- **The dataset stands alone.** Problem files in `datasets/problems/` never import `nbbench`; they
  read only `P`, `DIR`, `HOST`, `PORT` from the prelude. Data is synthetic from fixed seeds; no
  downloads. Changing a problem or the generator means rerunning `uv run nbbench samples` and
  committing the diff in `datasets/samples/`.
- **Sizes are calibrated, not guessed.** After adding or changing a problem, run
  `uv run nbbench calibrate --problems <id>` and keep `s` ≈ 10 ms, `m` ≈ 100 ms; `l` is always
  `m` + `"reps": 10`.
- No comments in code: no `#` comments in Python. Explain with names, small functions and
  docstrings; anything longer goes in `docs/plans/`.
- Always `uv run python3` / `uv run nbbench`.
- Import heavy libraries (numpy, pandas, nbformat, marimo) where they are used, not at module
  level in `nbbench/`; the package itself depends only on the standard library.
- Plans go in `docs/plans/NN-<topic>.md`: extremely concise, ending with unresolved questions.
- Results live in `results/<name>/` (tracked): `results.json`, figures, `README.md`, all written by
  `nbbench run` / `nbbench chart`; never edit them by hand. Results for the paper come from an
  idle machine; label anything else `dev` in its folder name. CI numbers are for correctness only.
- Tool versions are pinned in the `tools` extra (gpy by gpython commit); bump them on purpose and
  say so in the commit.
- Figures follow the theme in `nbbench/chart.py` (Okabe–Ito, a hatch and outline per tool, serif,
  7.2 in wide, PDF with embedded fonts + 300 dpi PNG). A new tool gets the next colour and its
  own hatch; re-run the palette validator.
