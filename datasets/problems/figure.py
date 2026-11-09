import io

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

_rng = np.random.default_rng(0)
POINTS = _rng.standard_normal((P["points"], 2))
SERIES = _rng.standard_normal(P["points"]).cumsum()


def initial():
    return 1.0


def work(x, i):
    figure = Figure(figsize=(6, 4), dpi=P["dpi"])
    FigureCanvasAgg(figure)
    left, right = figure.subplots(1, 2)
    left.scatter(POINTS[:, 0] * x, POINTS[:, 1], s=2, alpha=0.5)
    right.plot(SERIES * x, linewidth=0.8)
    right.hist(SERIES, bins=40, alpha=0.3)
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png")
    return 1.0 + (len(buffer.getvalue()) % 1000) / 1000.0


def combine(xs):
    return sum(xs) / len(xs)


def digest(x):
    return f"{x:.3f}"
