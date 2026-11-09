import numpy as np

SIGNAL = np.random.default_rng(0).random(P["n"])


def initial():
    return np.ones(1024)


def work(x, i):
    spectrum = np.abs(np.fft.rfft(SIGNAL * (1.0 + 1e-3 * x.mean())))
    head = spectrum[1:1025]
    return head / head.max()


def combine(xs):
    return np.mean(xs, axis=0)


def digest(x):
    return f"{float(x.sum()):.6e}"
