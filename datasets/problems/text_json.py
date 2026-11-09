import json
import random

_rng = random.Random(0)
RECORDS = [
    {
        "id": k,
        "user": {"name": f"user{k}", "tags": [_rng.randrange(100) for _ in range(5)]},
        "events": [{"t": _rng.random(), "kind": _rng.choice("abc")} for _ in range(8)],
    }
    for k in range(P["records"])
]


def initial():
    return 1.0


def work(x, i):
    text = json.dumps({"scale": x, "records": RECORDS})
    back = json.loads(text)
    scale = back["scale"]
    total = sum(event["t"] * scale for record in back["records"] for event in record["events"] if event["kind"] == "a")
    return 1.0 + total / (1.0 + total)


def combine(xs):
    return sum(xs) / len(xs)


def digest(x):
    return f"{x:.6e}"
