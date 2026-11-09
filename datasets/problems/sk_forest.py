import numpy as np
from sklearn.datasets import make_classification
from sklearn.ensemble import RandomForestClassifier

FEATURES, LABELS = make_classification(
    n_samples=P["rows"], n_features=16, n_informative=8, random_state=0
)


def initial():
    return np.ones(16)


def work(x, i):
    model = RandomForestClassifier(n_estimators=P["trees"], max_depth=8, random_state=i, n_jobs=1)
    model.fit(FEATURES * x, LABELS)
    importance = model.feature_importances_
    return 0.5 + importance / importance.max()


def combine(xs):
    return np.mean(xs, axis=0)


def digest(x):
    return f"{float(x.sum()):.4e}"
