import numpy as np
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression

FEATURES, LABELS = make_classification(
    n_samples=P["rows"], n_features=P["cols"], n_informative=P["cols"] // 2, random_state=0
)


def initial():
    return np.ones(P["cols"])


def work(x, i):
    model = LogisticRegression(max_iter=P["iterations"], tol=1e-6)
    model.fit(FEATURES * x, LABELS)
    weights = np.abs(model.coef_[0])
    return 0.5 + weights / weights.max()


def combine(xs):
    return np.mean(xs, axis=0)


def digest(x):
    return f"{float(x.sum()):.4e}"
