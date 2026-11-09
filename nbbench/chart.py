"""Paper-ready figures and a summary page for one results folder.

    nbbench chart results/<name>

Reads `results.json` and writes one figure per file, per size preset present, as PDF (fonts
embedded, for LaTeX `subfigure`) and 300 dpi PNG. Figures carry no title: the caption says what
they show (see `CAPTIONS`, repeated in the folder's `README.md`). Legends sit above the axes, never
on the data.

  cost_per_cell_<size>        ms between cells per problem at the largest N (full width)
  slowdown_<size>             launch → last cell ÷ cells run back to back, against N (one column)
  memory_<size>               memory of each tool's process tree at the largest N (one column)
  efficiency_<bound>_<size>   best possible time ÷ span per shape, one file per bound (one column)
  per_problem_<size>          launch → last cell against N, one small panel per problem (full width)

Theme as gpython's benchmark charts: Okabe–Ito colours (checked with the dataviz validator:
CVD ΔE ≥ 8.6, normal-vision ΔE ≥ 18.4), a hatch and black outline per tool so every figure reads in
greyscale, serif type sized for a two-column paper (3.5 in column, 7.2 in page).
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

TOOLS = ("gpy", "gpy-concurrent", "jupyterlab", "marimo")
LABEL = {"gpy": "gpy", "gpy-concurrent": "gpy (concurrent)", "jupyterlab": "JupyterLab", "marimo": "marimo"}
COLOR = {"gpy": "#0072B2", "gpy-concurrent": "#56B4E9", "jupyterlab": "#E69F00", "marimo": "#009E73"}
HATCH = {"gpy": "///", "gpy-concurrent": "\\\\\\", "jupyterlab": "...", "marimo": "xx"}
MARKER = {"gpy": "o", "gpy-concurrent": "D", "jupyterlab": "s", "marimo": "^"}
LINESTYLE = {"gpy": "-", "gpy-concurrent": "--", "jupyterlab": "-", "marimo": "-"}
DOMAINS = ("micro", "datasci", "ml", "text", "viz")
BOUNDS = ("cpu", "disk", "net")
SIZES = ("s", "m", "l")
GRID = "#d9d9d9"
REFERENCE = "#7f7f7f"
PAGE = 7.2
COLUMN = 3.5

CAPTIONS = {
    "cost_per_cell": "Tool cost per cell: mean time between one work cell ending and the next starting, at {top} "
                     "{shape} cells. Error bars: {runs}. Problems grouped by domain. gpy (concurrent) is left out: its cells "
                     "overlap, so the gap is not defined.",
    "slowdown": "Launch until the last cell finishes, divided by the time the same cells take back to back with no "
                "tool, geometric mean over problems ({shape} cells). Error bars: {runs}, of that mean. 1 = no cost beyond the "
                "work; below 1 = faster than back to back.",
    "memory": "Memory of each tool's process tree when the last cell finished, {top} {shape} cells, mean over "
              "problems. Error bars: {runs}, of that mean.",
    "efficiency": "{bound}-bound problems at {top} cells: best possible time (the longer of the critical path and all "
                  "work spread over {cpus} CPUs) divided by the measured span, mean over problems. Error bars: {runs}, "
                  "of that mean. 1 = no schedule on this machine could be faster.",
    "per_problem": "Launch until the last cell finishes against N for each problem ({shape} cells, log–log). Error bars: {runs}. "
                   "Dotted: the cells back to back with no tool.",
}


def setup():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "font.family": "serif", "font.size": 8, "axes.labelsize": 8, "legend.fontsize": 7.5,
        "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "hatch.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42, "ps.fonttype": 42,
    })
    return plt


def geomean(values: list[float]) -> float | None:
    positive = [v for v in values if v and v > 0]
    return math.exp(statistics.mean(math.log(v) for v in positive)) if positive else None


def mean_sd(values: list[float]) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    return statistics.mean(values), statistics.stdev(values) if len(values) > 1 else 0.0


def save(fig, folder: Path, stem: str) -> str:
    for ext in ("pdf", "png"):
        fig.savefig(folder / f"{stem}.{ext}", dpi=300)
    import matplotlib.pyplot as plt

    plt.close(fig)
    return stem


def legend_above(fig, tools: list[str], kind: str = "bar", extra: list | None = None, narrow: bool = False) -> None:
    """One row of legend entries above the axes, outside the plotting area."""
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    if kind == "bar":
        handles = [Patch(facecolor=COLOR[t], hatch=HATCH[t], edgecolor="black", linewidth=0.5, label=LABEL[t])
                   for t in tools]
    else:
        handles = [Line2D([], [], color=COLOR[t], marker=MARKER[t], linestyle=LINESTYLE[t], markersize=3.5,
                          linewidth=1.2, label=LABEL[t]) for t in tools]
    handles += extra or []
    columns = 2 if narrow else (len(handles) if len(handles) <= 4 else math.ceil(len(handles) / 2))
    fig.legend(handles=handles, loc="outside upper center", ncol=columns, frameon=False, handlelength=1.8,
               columnspacing=1.2)


def plain_ticks(ax, axes: str = "xy") -> None:
    """Log axes labelled 0.5, 1, 2 rather than 5×10⁻¹, 10⁰, 2×10⁰."""
    from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter

    for name in axes:
        axis = ax.xaxis if name == "x" else ax.yaxis
        if name == "y":
            axis.set_major_locator(LogLocator(base=10, subs=(1, 2, 5)))
        axis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}"))
        axis.set_minor_formatter(NullFormatter())


def style(ax) -> None:
    ax.yaxis.grid(True, color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)


class Results:
    def __init__(self, report: dict):
        self.meta = report["meta"]
        self.rows = [row for row in report["rows"] if row.get("last") is not None]
        self.tools = [t for t in TOOLS if any(r["tool"] == t for r in self.rows)]
        self.sizes = [s for s in SIZES if any(r["size"] == s for r in self.rows)]

    def select(self, **match) -> list[dict]:
        return [r for r in self.rows if all(r.get(k) == v for k, v in match.items())]

    def one(self, **match) -> dict | None:
        found = self.select(**match)
        return found[0] if found else None

    def problems(self, size: str) -> list[str]:
        rows = self.select(size=size)
        domain = {r["problem"]: r["domain"] for r in rows}
        order = list(dict.fromkeys(r["problem"] for r in rows))
        return sorted(order, key=lambda p: (DOMAINS.index(domain[p]) if domain[p] in DOMAINS else 99, order.index(p)))

    def shapes(self, size: str) -> list[str]:
        return list(dict.fromkeys(r["shape"] for r in self.select(size=size)))

    def cells(self, size: str) -> list[int]:
        return sorted({r["n"] for r in self.select(size=size)})

    def main_shape(self, size: str) -> str:
        shapes = self.shapes(size)
        return "independent" if "independent" in shapes else shapes[0]


def best_possible_of(row: dict, cpus: int | None) -> float:
    from nbbench.run import best_possible

    return best_possible(row["reference"], cpus)


def efficiency_of(row: dict, cpus: int | None) -> float:
    """Best possible time (critical path, or all work over every CPU) over the measured span."""
    from nbbench.run import best_possible

    return best_possible(row["reference"], cpus) / row["span"]


def slowdown(row: dict) -> float:
    return row["last"] / row["reference"]["sequential_s"]


def good_runs(row: dict) -> list[dict]:
    return [run for run in row.get("runs", []) if "error" not in run]


def across_runs(rows: list[dict], measure, combine) -> tuple[float | None, float | None]:
    """Mean ± sd over repeated runs of a value combined over several rows.

    Run k of every row is combined first (e.g. a geometric mean over problems), so the error bar
    is the run-to-run spread of that combined value, not the spread between problems.
    """
    runs = min((len(good_runs(row)) for row in rows), default=0)
    if not rows or runs == 0:
        return None, None
    per_run = [combine([measure(row, good_runs(row)[k]) for row in rows]) for k in range(runs)]
    return mean_sd([value for value in per_run if value is not None])


def run_slowdown(row: dict, run: dict) -> float:
    return run["last"] / row["reference"]["sequential_s"]


def runs_label(results: "Results") -> str:
    counts = sorted({len(good_runs(row)) for row in results.rows})
    if counts == [1]:
        return "none (a single run)"
    spread = f"{counts[0]}" if len(counts) == 1 else f"{counts[0]}–{counts[-1]}"
    return f"± 1 sd over {spread} runs"


def bars(ax, groups, tools, value, labels, rotate=0) -> None:
    import numpy as np

    width = 0.8 / len(tools)
    x = np.arange(len(groups))
    for i, tool in enumerate(tools):
        pairs = [value(tool, group) for group in groups]
        means = [p[0] if p[0] is not None else 0 for p in pairs]
        errors = [p[1] or 0 for p in pairs]
        ax.bar(x + (i - (len(tools) - 1) / 2) * width, means, width * 0.92, yerr=errors, capsize=1.2,
               color=COLOR[tool], hatch=HATCH[tool], edgecolor="black", linewidth=0.5,
               error_kw={"elinewidth": 0.6, "capthick": 0.6})
    ax.set_xticks(x, labels, rotation=rotate, ha="right" if rotate else "center",
                  rotation_mode="anchor" if rotate else "default")
    style(ax)


def domain_bands(ax, problems, domain) -> None:
    """Domain names in a strip above the bars, inside headroom kept free for them, with thin rules between."""
    import matplotlib.transforms

    top = ax.get_ylim()[1]
    ax.set_ylim(0, top * 1.12)
    over = matplotlib.transforms.blended_transform_factory(ax.transData, ax.transAxes)
    start = 0
    for i in range(1, len(problems) + 1):
        if i < len(problems) and domain[problems[i]] == domain[problems[start]]:
            continue
        ax.text((start + i - 1) / 2, 0.985, domain[problems[start]], transform=over, ha="center", va="top",
                fontsize=7, fontweight="bold")
        if i < len(problems):
            ax.axvline(i - 0.5, color="#bdbdbd", linewidth=0.6, zorder=0)
        start = i


def cost_per_cell(results: Results, size: str, folder: Path) -> tuple[str, dict]:
    plt = setup()
    shape, top = results.main_shape(size), results.cells(size)[-1]
    problems = results.problems(size)
    domain = {r["problem"]: r["domain"] for r in results.select(size=size)}
    tools = [t for t in results.tools if t != "gpy-concurrent"]

    def gap(tool, problem):
        row = results.one(size=size, shape=shape, n=top, tool=tool, problem=problem)
        return (row["gap_ms"], row["gap_ms_std"]) if row and row.get("gap_ms") is not None else (None, None)

    fig, ax = plt.subplots(figsize=(PAGE, 2.7), layout="constrained")
    bars(ax, problems, tools, gap, problems, rotate=40)
    domain_bands(ax, problems, domain)
    ax.set_ylabel("ms between cells")
    legend_above(fig, tools)
    return save(fig, folder, f"cost_per_cell_{size}"), {"top": top, "shape": shape}


def slowdown_vs_n(results: Results, size: str, folder: Path) -> tuple[str, dict]:
    plt = setup()
    shape, cells = results.main_shape(size), results.cells(size)
    fig, ax = plt.subplots(figsize=(COLUMN, 2.5), layout="constrained")
    for tool in results.tools:
        pairs = [across_runs(results.select(size=size, shape=shape, n=n, tool=tool), run_slowdown, geomean)
                 for n in cells]
        shown = [(n, p) for n, p in zip(cells, pairs) if p[0] is not None]
        if not shown:
            continue
        ax.errorbar([n for n, _ in shown], [p[0] for _, p in shown], yerr=[p[1] or 0 for _, p in shown], color=COLOR[tool],
                    marker=MARKER[tool], linestyle=LINESTYLE[tool], markersize=3.5, linewidth=1.2, capsize=2,
                    elinewidth=0.7)
    ax.axhline(1.0, color=REFERENCE, linewidth=0.9, linestyle=":")
    ax.set_xscale("log")
    ax.set_yscale("log")
    plain_ticks(ax)
    ax.set_xticks(cells)
    ax.set_xlabel("cells (N)")
    ax.set_ylabel("× time of cells back to back")
    style(ax)
    legend_above(fig, results.tools, kind="line", narrow=True)
    return save(fig, folder, f"slowdown_{size}"), {"shape": shape}


def memory(results: Results, size: str, folder: Path) -> tuple[str, dict]:
    plt = setup()
    shape, top = results.main_shape(size), results.cells(size)[-1]
    fig, ax = plt.subplots(figsize=(COLUMN, 2.2), layout="constrained")
    for x, tool in enumerate(results.tools):
        mean, sd = across_runs(results.select(size=size, shape=shape, n=top, tool=tool),
                               lambda row, run: run["mem_mb"], statistics.mean)
        ax.bar(x, mean or 0, 0.7, yerr=sd or 0, capsize=2, color=COLOR[tool], hatch=HATCH[tool], edgecolor="black",
               linewidth=0.5, error_kw={"elinewidth": 0.6, "capthick": 0.6})
    ax.set_xticks(range(len(results.tools)), [LABEL[t].replace(" (", "\n(") for t in results.tools])
    ax.set_ylabel("MB")
    style(ax)
    return save(fig, folder, f"memory_{size}"), {"top": top, "shape": shape}


def efficiency(results: Results, size: str, folder: Path) -> list[tuple[str, dict]]:
    plt = setup()
    top, cpus = results.cells(size)[-1], results.meta.get("cpus")
    shapes = results.shapes(size)
    written = []
    for bound in BOUNDS:
        if not results.select(size=size, bound=bound):
            continue

        def value(tool, shape):
            return across_runs(results.select(size=size, shape=shape, n=top, tool=tool, bound=bound),
                               lambda row, run: best_possible_of(row, cpus) / run["span"], statistics.mean)

        fig, ax = plt.subplots(figsize=(COLUMN, 2.3), layout="constrained")
        bars(ax, shapes, results.tools, value, shapes)
        ax.axhline(1.0, color=REFERENCE, linewidth=0.9, linestyle=":")
        ax.set_ylim(0, 1.05)
        ax.set_ylabel("best possible ÷ span")
        legend_above(fig, results.tools, narrow=True)
        written.append((save(fig, folder, f"efficiency_{bound}_{size}"), {"bound": bound, "top": top, "cpus": cpus}))
    return written


def per_problem(results: Results, size: str, folder: Path) -> tuple[str, dict] | None:
    cells = results.cells(size)
    if len(cells) < 2:
        return None
    plt = setup()
    from matplotlib.lines import Line2D

    shape = results.main_shape(size)
    chosen = results.problems(size)
    cols = 4
    rows = math.ceil(len(chosen) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(PAGE, 1.45 * rows + 0.5), layout="constrained", sharex=True,
                             squeeze=False)
    for ax, problem in zip(axes.flat, chosen):
        for tool in results.tools:
            found = [(n, results.one(size=size, shape=shape, n=n, tool=tool, problem=problem)) for n in cells]
            ax.errorbar([n for n, r in found if r], [r["last"] for _, r in found if r],
                        yerr=[r.get("last_std") or 0 for _, r in found if r], color=COLOR[tool], marker=MARKER[tool],
                        linestyle=LINESTYLE[tool], markersize=2.5, linewidth=1.0, capsize=1.5, elinewidth=0.6)
        reference = [(n, results.one(size=size, shape=shape, n=n, problem=problem)) for n in cells]
        ax.plot([n for n, r in reference if r], [r["reference"]["sequential_s"] for _, r in reference if r],
                color=REFERENCE, linestyle=":", linewidth=0.9)
        ax.set_xscale("log")
        ax.set_yscale("log")
        plain_ticks(ax)
        ax.set_xticks(cells)
        ax.set_title(problem, fontsize=7.5, pad=2)
        ax.tick_params(labelbottom=True)
        style(ax)
    for ax in axes.flat[len(chosen):]:
        ax.axis("off")
    for ax in axes[:, 0]:
        ax.set_ylabel("s to last cell")
    for ax in axes[-1]:
        ax.set_xlabel("cells (N)")
    no_tool = Line2D([], [], color=REFERENCE, linestyle=":", linewidth=0.9, label="cells back to back, no tool")
    legend_above(fig, results.tools, kind="line", extra=[no_tool])
    return save(fig, folder, f"per_problem_{size}"), {"shape": shape}


def caption(stem: str, values: dict, runs: str) -> str:
    key = next(k for k in CAPTIONS if stem.startswith(k))
    return CAPTIONS[key].format(runs=runs, **values)


def summary(results: Results, figures: dict[str, list[tuple[str, dict]]]) -> str:
    meta = results.meta
    lines = [
        f"# nbbench results: {meta.get('date', '')}",
        "",
        f"nbbench {meta['nbbench']} on {meta['platform']} ({meta['cpus']} CPUs, load {meta['load'][0]:.1f} at start), "
        f"Python {meta['python'].split()[0]}.",
        "",
        "| package | version |",
        "|---|---|",
        *[f"| {name} | {version} |" for name, version in meta["packages"].items() if version],
        "",
    ]
    for size in results.sizes:
        shape, top = results.main_shape(size), results.cells(size)[-1]
        lines += [
            f"## Size {size}",
            "",
            f"At {top} {shape} cells over every problem. Slowdown: launch → last cell ÷ the cells back to back with "
            "no tool (geometric mean). Efficiency: best possible time ÷ span, mean over every shape and problem.",
            "",
            "| tool | slowdown | ms between cells | efficiency | memory MB | runs ok |",
            "|---|---|---|---|---|---|",
        ]
        for tool in results.tools:
            rows = results.select(size=size, shape=shape, n=top, tool=tool)
            every = [r for r in results.rows if r["tool"] == tool and r["size"] == size]
            gaps = [r["gap_ms"] for r in rows if r.get("gap_ms") is not None]
            eff = [efficiency_of(r, meta.get("cpus")) for r in every]
            lines.append(
                f"| {LABEL[tool]} | {geomean([slowdown(r) for r in rows]) or 0:.2f} | "
                f"{statistics.median(gaps) if gaps else float('nan'):.2f} | "
                f"{statistics.mean(eff) if eff else float('nan'):.2f} | "
                f"{statistics.mean(r['mem_mb'] for r in rows) if rows else float('nan'):.0f} | "
                f"{sum(1 for r in every if r['ok'])}/{len(every)} |"
            )
        lines.append("")
        for number, (stem, values) in enumerate(figures.get(size, []), start=1):
            lines += [f"**Figure {size}{number}.** {caption(stem, values, runs_label(results))} ([PDF]({stem}.pdf))", "",
                      f"![{stem}]({stem}.png)", ""]
    failed = [r for r in results.rows if not r["ok"]]
    if failed:
        lines += ["## Not ok", ""] + [f"- {r['problem']}-{r['size']}-{r['shape']}-n{r['n']} {r['tool']}" for r in failed]
    return "\n".join(lines) + "\n"


def draw(folder: Path) -> list[str]:
    results = Results(json.loads((folder / "results.json").read_text()))
    for stale in list(folder.glob("*.png")) + list(folder.glob("*.pdf")):
        stale.unlink()
    figures = {}
    for size in results.sizes:
        made = [cost_per_cell(results, size, folder), slowdown_vs_n(results, size, folder),
                memory(results, size, folder), *efficiency(results, size, folder), per_problem(results, size, folder)]
        figures[size] = [entry for entry in made if entry]
    (folder / "README.md").write_text(summary(results, figures))
    return [f"{stem}.{ext}" for entries in figures.values() for stem, _ in entries for ext in ("pdf", "png")] + ["README.md"]
