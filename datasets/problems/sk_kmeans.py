import numpy as np
from sklearn.cluster import KMeans
from sklearn.datasets import make_blobs

POINTS, _ = make_blobs(n_samples=P["rows"], n_features=8, centers=P["clusters"], random_state=0)


def initial():
    return POINTS[: P["clusters"]].copy()


def work(x, i):
    model = KMeans(n_clusters=P["clusters"], init=x, n_init=1, max_iter=P["iterations"], tol=0.0)
    model.fit(POINTS)
    return model.cluster_centers_


def combine(xs):
    return np.mean(xs, axis=0)


def digest(x):
    return f"{float(np.sort(x, axis=0).sum()):.4e}"
