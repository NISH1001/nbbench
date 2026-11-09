import random
import sqlite3

_rng = random.Random(0)
ROWS = [(_rng.randrange(100), _rng.random() * 100) for _ in range(P["rows"])]


def initial():
    return [1.0] * 100


def work(x, i):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE sales (store INTEGER, amount REAL)")
    db.execute("CREATE TABLE weights (store INTEGER PRIMARY KEY, weight REAL)")
    db.executemany("INSERT INTO sales VALUES (?, ?)", ROWS)
    db.executemany("INSERT INTO weights VALUES (?, ?)", list(enumerate(x)))
    totals = dict(db.execute(
        "SELECT s.store, SUM(s.amount * w.weight) FROM sales s JOIN weights w USING (store) GROUP BY s.store"
    ).fetchall())
    db.close()
    top = max(totals.values())
    return [totals.get(store, 0.0) / top for store in range(100)]


def combine(xs):
    return [sum(column) / len(xs) for column in zip(*xs)]


def digest(x):
    return f"{sum(x):.6e}"
