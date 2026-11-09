import os

import numpy as np
import pandas as pd

TABLE = pd.DataFrame(
    np.random.default_rng(0).random((P["rows"], 8)),
    columns=[f"c{k}" for k in range(8)],
)


def initial():
    return np.ones(8)


def work(x, i):
    path = os.path.join(DIR, f"table{i}.parquet")
    (TABLE * x).to_parquet(path, index=False)
    back = pd.read_parquet(path)
    os.remove(path)
    means = back.mean().to_numpy()
    return means / means.max()


def combine(xs):
    return np.mean(xs, axis=0)


def digest(x):
    return f"{float(x.sum()):.6e}"
