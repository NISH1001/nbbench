import numpy as np
import pandas as pd

PRICES = pd.Series(
    np.random.default_rng(0).standard_normal(P["rows"]).cumsum(),
    index=pd.date_range("2020-01-01", periods=P["rows"], freq="min"),
)


def initial():
    return 1.0


def work(x, i):
    scaled = PRICES * x
    fast = scaled.rolling(P["window"]).mean()
    slow = scaled.rolling(P["window"] * 4).mean()
    hourly = (fast - slow).resample("h").std()
    return float(1.0 + hourly.mean() / (1.0 + hourly.max()))


def combine(xs):
    return sum(xs) / len(xs)


def digest(x):
    return f"{x:.6e}"
