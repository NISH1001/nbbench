import numpy as np
import pandas as pd

_rng = np.random.default_rng(0)
SALES = pd.DataFrame({
    "store": _rng.integers(0, P["groups"], P["rows"]),
    "units": _rng.integers(1, 20, P["rows"]),
    "price": _rng.random(P["rows"]) * 100,
})


def initial():
    return pd.Series(1.0, index=pd.RangeIndex(P["groups"], name="store"))


def work(x, i):
    priced = SALES.assign(revenue=SALES["units"] * SALES["price"] * SALES["store"].map(x).to_numpy())
    summary = priced.groupby("store").agg(revenue=("revenue", "sum"), orders=("units", "count"))
    per_order = summary["revenue"] / summary["orders"]
    return (per_order / per_order.max()).reindex(x.index, fill_value=0.0)


def combine(xs):
    return pd.concat(xs, axis=1).mean(axis=1)


def digest(x):
    return f"{float(x.sum()):.6e}"
