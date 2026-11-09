import numpy as np
import pandas as pd

_rng = np.random.default_rng(0)
ORDERS = pd.DataFrame({
    "customer": _rng.integers(0, P["customers"], P["rows"]),
    "amount": _rng.random(P["rows"]) * 50,
})
CUSTOMERS = pd.DataFrame({
    "customer": np.arange(P["customers"]),
    "region": _rng.integers(0, 50, P["customers"]),
})


def initial():
    return pd.Series(1.0, index=pd.RangeIndex(50, name="region"))


def work(x, i):
    joined = ORDERS.merge(CUSTOMERS, on="customer", how="inner")
    joined = joined.assign(weighted=joined["amount"] * joined["region"].map(x).to_numpy())
    by_region = joined.groupby("region")["weighted"].sum()
    return (by_region / by_region.max()).reindex(x.index, fill_value=0.0)


def combine(xs):
    return pd.concat(xs, axis=1).mean(axis=1)


def digest(x):
    return f"{float(x.sum()):.6e}"
