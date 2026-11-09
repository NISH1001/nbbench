import random
import re
from collections import Counter

_rng = random.Random(0)
_words = ["".join(_rng.choices("abcdefghijklmnopqrstuvwxyz", k=_rng.randint(3, 9))) for _ in range(2000)]
DOCUMENTS = [
    " ".join(_rng.choices(_words, k=40)) + f" user{_rng.randrange(1000)}@example.org #{_rng.randrange(50)}"
    for _ in range(P["documents"])
]
TOKEN = re.compile(r"[a-z]{4,}")
EMAIL = re.compile(r"\b(\w+)@(\w+)\.org\b")
TAG = re.compile(r"#(\d+)")


def initial():
    return 0


def work(x, i):
    letter = "abcdefghijklmnopqrstuvwxyz"[x % 26]
    counts = Counter()
    users = set()
    tags = Counter()
    for document in DOCUMENTS:
        counts.update(token for token in TOKEN.findall(document) if token.startswith(letter))
        users.update(match.group(1) for match in EMAIL.finditer(document))
        tags.update(TAG.findall(document))
    return (sum(counts.values()) + len(users) + sum(int(tag) for tag in tags)) % 1_000_003


def combine(xs):
    return sum(xs) % 1_000_003


def digest(x):
    return str(x)
