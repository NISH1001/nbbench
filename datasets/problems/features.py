import numpy as np
import pandas as pd

RAW = pd.DataFrame(
    np.random.default_rng(0).random((P["rows"], P["cols"])),
    columns=[f"f{k}" for k in range(P["cols"])],
)


def initial():
    return np.ones(P["cols"])


def work(x, i):
    weighted = RAW * x
    standard = (weighted - weighted.mean()) / weighted.std()
    logs = np.log1p(weighted).add_suffix("_log")
    pairs = pd.DataFrame({
        f"f{k}_x_f{k + 1}": standard[f"f{k}"] * standard[f"f{k + 1}"] for k in range(P["cols"] - 1)
    })
    table = pd.concat([standard, logs, pairs], axis=1)
    correlation = table.corr().to_numpy()[: P["cols"], P["cols"]:]
    scores = np.abs(correlation).mean(axis=1)
    return scores / scores.max()


def combine(xs):
    return np.mean(xs, axis=0)


def digest(x):
    return f"{float(x.sum()):.6e}"
