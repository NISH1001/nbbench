"""Paper-ready figures and a summary page for one results folder.

    nbbench chart results/<name>

Reads `results.json` and writes, per size preset present, PDF (fonts embedded) and 300 dpi PNG:

  overhead_<size>   (a) ms between cells per problem at the largest N, problems grouped by domain
                    (b) launch → last cell over the reference sequential time, against N
                        (geometric mean over problems; below 1 = faster than running the cells
                        back to back, above 1 = the tool's own cost)
                    (c) memory of the tool's process tree at the largest N
  shapes_<size>     efficiency (reference critical path / span) per shape, one panel per bound
  problems_<size>   launch → last cell against N, one panel per problem, reference grey dotted

and `README.md` with the machine, versions, a summary table and the figures.

Theme as gpython's benchmark charts: Okabe–Ito colours (checked with the dataviz validator:
CVD ΔE ≥ 8.6, normal-vision ΔE ≥ 18.4), a hatch and black outline per tool so every figure reads in
greyscale, serif type sized for a two-column paper at 7.2 in wide.
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
WIDTH = 7.2


def setup():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "font.family": "serif", "font.size": 8.5, "axes.titlesize": 9, "axes.labelsize": 8.5,
        "legend.fontsize": 7.5, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "hatch.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42, "ps.fonttype": 42,
    })
    return plt


def geomean(values: list[float]) -> float | None:
    positive = [v for v in values if v and v > 0]
    return math.exp(statistics.mean(math.log(v) for v in positive)) if positive else None


def save(fig, folder: Path, stem: str) -> list[str]:
    names = []
    for ext in ("pdf", "png"):
        fig.savefig(folder / f"{stem}.{ext}", dpi=300)
        names.append(f"{stem}.{ext}")
    return names


class Results:
    def __init__(self, report: dict):
        self.meta = report["meta"]
        self.rows = [row for row in report["rows"] if row.get("last") is not None]
        self.tools = [t for t in TOOLS if any(r["tool"] == t for r in self.rows)]
        self.sizes = [s for s in SIZES if any(r["size"] == s for r in self.rows)]

    def select(self, **match) -> list[dict]:
        return [r for r in self.rows if all(r.get(k) == v for k, v in match.items())]

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

    def one(self, **match) -> dict | None:
        found = self.select(**match)
        return found[0] if found else None


def efficiency_of(row: dict, cpus: int | None) -> float:
    """Best possible time (critical path, or all work over every CPU) over the measured span."""
    from nbbench.run import best_possible

    return best_possible(row["reference"], cpus) / row["span"]


def slowdown(row: dict) -> float:
    return row["last"] / row["reference"]["sequential_s"]


def grouped_bars(ax, groups, tools, value, labels, rotate=0):
    import numpy as np

    width = 0.8 / len(tools)
    x = np.arange(len(groups))
    for i, tool in enumerate(tools):
        pairs = [value(tool, group) for group in groups]
        means = [p[0] if p[0] is not None else 0 for p in pairs]
        errors = [p[1] or 0 for p in pairs]
        ax.bar(x + (i - (len(tools) - 1) / 2) * width, means, width * 0.92, yerr=errors, capsize=1.2,
               color=COLOR[tool], hatch=HATCH[tool], edgecolor="black", linewidth=0.5, label=LABEL[tool],
               error_kw={"elinewidth": 0.6, "capthick": 0.6})
    ax.set_xticks(x, labels, rotation=rotate, ha="right" if rotate else "center")
    ax.yaxis.grid(True, color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)


def label_domains(ax, problems, domain):
    import matplotlib.transforms

    below = matplotlib.transforms.blended_transform_factory(ax.transData, ax.transAxes)
    start = 0
    for i in range(1, len(problems) + 1):
        if i < len(problems) and domain[problems[i]] == domain[problems[start]]:
            continue
        ax.text((start + i - 1) / 2, 1.0, domain[problems[start]], transform=below, ha="center", va="bottom",
                fontsize=7, fontweight="bold")
        if i < len(problems):
            ax.axvline(i - 0.5, color="#bdbdbd", linewidth=0.6, zorder=0)
        start = i


def overhead(results: Results, size: str, folder: Path) -> list[str]:
    plt = setup()
    shape = results.main_shape(size)
    problems = results.problems(size)
    cells = results.cells(size)
    top = cells[-1]
    domain = {r["problem"]: r["domain"] for r in results.select(size=size)}
    sequential = [t for t in results.tools if t != "gpy-concurrent"]
    fig = plt.figure(figsize=(WIDTH, 4.6), constrained_layout=True)
    grid = fig.add_gridspec(2, 2, height_ratios=[1.15, 1], width_ratios=[1.6, 1])
    a, b, c = fig.add_subplot(grid[0, :]), fig.add_subplot(grid[1, 0]), fig.add_subplot(grid[1, 1])

    def gap(tool, problem):
        row = results.one(size=size, shape=shape, n=top, tool=tool, problem=problem)
        return (row["gap_ms"], row["gap_ms_std"]) if row and row.get("gap_ms") is not None else (None, None)

    grouped_bars(a, problems, sequential, gap, problems, rotate=35)
    label_domains(a, problems, domain)
    a.set_ylabel("ms between cells")
    a.set_title(f"(a) Tool cost per cell, {top} {shape} cells, size {size}", pad=12)
    a.legend(frameon=False, loc="upper left", ncol=len(sequential))
    if "gpy-concurrent" in results.tools:
        a.text(1.0, 1.0, "gpy (concurrent) not shown: its cells overlap", transform=a.transAxes, ha="right",
               va="top", fontsize=6.5, color=REFERENCE)

    for tool in results.tools:
        points = []
        for n in cells:
            ratios = [slowdown(r) for r in results.select(size=size, shape=shape, n=n, tool=tool)]
            points.append(geomean(ratios))
        b.plot(cells, points, color=COLOR[tool], marker=MARKER[tool], linestyle=LINESTYLE[tool], markersize=3.5,
               linewidth=1.2, label=LABEL[tool])
    b.axhline(1.0, color=REFERENCE, linewidth=0.9, linestyle=":")
    b.set_xscale("log")
    plain_ticks(b)
    b.set_xlabel("cells (N)")
    b.set_ylabel("time ÷ cells run back to back")
    b.set_title("(b) Launch → last cell, geometric mean")
    b.yaxis.grid(True, color=GRID, linewidth=0.5)
    b.legend(frameon=False, fontsize=6.5)

    def memory(tool, _):
        values = [r["mem_mb"] for r in results.select(size=size, shape=shape, n=top, tool=tool)]
        return (statistics.mean(values), statistics.stdev(values) if len(values) > 1 else 0) if values else (None, None)

    grouped_bars(c, ["all"], results.tools, memory, [""])
    c.set_ylabel("MB")
    c.set_title(f"(c) Memory, {top} cells, mean ± sd")
    c.set_xticks([])
    names = save(fig, folder, f"overhead_{size}")
    plt.close(fig)
    return names


def shapes(results: Results, size: str, folder: Path) -> list[str]:
    plt = setup()
    cells = results.cells(size)
    top = cells[-1]
    bounds = [b for b in BOUNDS if results.select(size=size, bound=b)]
    shape_list = results.shapes(size)
    fig, axes = plt.subplots(1, len(bounds), figsize=(WIDTH, 2.4), constrained_layout=True, sharey=True,
                             squeeze=False)
    for ax, bound in zip(axes[0], bounds):
        def efficiency(tool, shape):
            values = [efficiency_of(r, results.meta.get("cpus")) for r in
                      results.select(size=size, shape=shape, n=top, tool=tool, bound=bound)]
            if not values:
                return (None, None)
            return (statistics.mean(values), statistics.stdev(values) if len(values) > 1 else 0)

        grouped_bars(ax, shape_list, results.tools, efficiency, shape_list)
        ax.axhline(1.0, color=REFERENCE, linewidth=0.9, linestyle=":")
        ax.set_title(f"{bound}-bound, {top} cells")
    axes[0][0].set_ylabel("best possible ÷ span")
    axes[0][-1].legend(frameon=False, fontsize=6.5, loc="upper right")
    fig.suptitle(f"Efficiency: best possible time (critical path, or all work over {results.meta.get('cpus')} CPUs) "
                 f"÷ span, size {size}; 1 = optimal", fontsize=9)
    names = save(fig, folder, f"shapes_{size}")
    plt.close(fig)
    return names


def plain_ticks(ax) -> None:
    """Log axes labelled 0.5, 1, 2 rather than 5×10⁻¹, 10⁰, 2×10⁰."""
    from matplotlib.ticker import FuncFormatter, NullFormatter

    for axis in (ax.xaxis, ax.yaxis):
        axis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}"))
        axis.set_minor_formatter(NullFormatter())


def problems(results: Results, size: str, folder: Path) -> list[str]:
    cells = results.cells(size)
    if len(cells) < 2:
        return []
    plt = setup()
    shape = results.main_shape(size)
    chosen = results.problems(size)
    cols = 4
    rows = math.ceil((len(chosen) + 1) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(WIDTH, 1.55 * rows + 0.4), constrained_layout=True, sharex=True,
                             squeeze=False)
    for ax, problem in zip(axes.flat, chosen):
        for tool in results.tools:
            found = [results.one(size=size, shape=shape, n=n, tool=tool, problem=problem) for n in cells]
            ax.plot([n for n, r in zip(cells, found) if r], [r["last"] for r in found if r], color=COLOR[tool],
                    marker=MARKER[tool], linestyle=LINESTYLE[tool], markersize=2.5, linewidth=1.0, label=LABEL[tool])
        reference = [results.one(size=size, shape=shape, n=n, problem=problem) for n in cells]
        ax.plot([n for n, r in zip(cells, reference) if r], [r["reference"]["sequential_s"] for r in reference if r],
                color=REFERENCE, linestyle=":", linewidth=0.9, label="cells back to back, no tool")
        ax.set_xscale("log")
        ax.set_yscale("log")
        plain_ticks(ax)
        ax.set_title(problem, fontsize=7.5)
        ax.yaxis.grid(True, color="#e5e5e5", linewidth=0.5)
    for ax in axes.flat[len(chosen):]:
        ax.axis("off")
    handles, labels = axes.flat[0].get_legend_handles_labels()
    axes.flat[len(chosen)].legend(handles, labels, frameon=False, loc="center", fontsize=6.5)
    for ax in axes[:, 0]:
        ax.set_ylabel("s to last cell")
    for ax in axes[-1]:
        ax.set_xlabel("cells (N)")
    names = save(fig, folder, f"problems_{size}")
    plt.close(fig)
    return names


def summary(results: Results, figures: dict[str, list[str]]) -> str:
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
        shape = results.main_shape(size)
        top = results.cells(size)[-1]
        lines += [
            f"## Size {size}",
            "",
            f"Over every problem at {top} {shape} cells. Slowdown: launch → last cell ÷ the cells run back to back "
            "without a tool (geometric mean). Efficiency: best possible time ÷ span, where best possible is the "
            "longer of the critical path and all work spread over every CPU (mean over every shape).",
            "",
            "| tool | slowdown | ms between cells | efficiency | memory MB | runs ok |",
            "|---|---|---|---|---|---|",
        ]
        for tool in results.tools:
            rows = results.select(size=size, shape=shape, n=top, tool=tool)
            every = [r for r in results.rows if r["tool"] == tool and r["size"] == size]
            gaps = [r["gap_ms"] for r in rows if r.get("gap_ms") is not None]
            efficiency = [efficiency_of(r, meta.get("cpus")) for r in every]
            ok = sum(1 for r in every if r["ok"])
            lines.append(
                f"| {LABEL[tool]} | {geomean([slowdown(r) for r in rows]) or 0:.2f} | "
                f"{statistics.median(gaps) if gaps else float('nan'):.2f} | "
                f"{statistics.mean(efficiency) if efficiency else float('nan'):.2f} | "
                f"{statistics.mean(r['mem_mb'] for r in rows) if rows else float('nan'):.0f} | {ok}/{len(every)} |"
            )
        lines.append("")
        for name in figures.get(size, []):
            if name.endswith(".png"):
                lines += [f"![{name}]({name})", ""]
    failed = [r for r in results.rows if not r["ok"]]
    if failed:
        lines += ["## Not ok", ""] + [f"- {r['problem']}-{r['size']}-{r['shape']}-n{r['n']} {r['tool']}" for r in failed]
    return "\n".join(lines) + "\n"


def draw(folder: Path) -> list[str]:
    results = Results(json.loads((folder / "results.json").read_text()))
    figures = {}
    for size in results.sizes:
        figures[size] = overhead(results, size, folder) + shapes(results, size, folder) + problems(results, size, folder)
    (folder / "README.md").write_text(summary(results, figures))
    return [name for names in figures.values() for name in names] + ["README.md"]
