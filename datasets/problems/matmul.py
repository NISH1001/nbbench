import numpy as np

A = np.random.default_rng(0).random((P["n"], P["n"]))
B = np.random.default_rng(1).random((P["n"], P["n"]))


def initial():
    return np.ones(P["n"])


def work(x, i):
    y = ((A * x[:, None]) @ B).mean(axis=0)
    return y / np.abs(y).max()


def combine(xs):
    return np.mean(xs, axis=0)


def digest(x):
    return f"{float(x.sum()):.6e}"
