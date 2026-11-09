import hashlib
import os
import random

BLOB = random.Random(0).randbytes(P["mb"] << 20)


def initial():
    return "0" * 16


def work(x, i):
    path = os.path.join(DIR, f"big{i}")
    with open(path, "wb") as out:
        out.write(BLOB)
        out.write(x.encode())
        out.flush()
        os.fsync(out.fileno())
    with open(path, "rb") as back:
        result = hashlib.blake2b(back.read()).hexdigest()[:16]
    os.remove(path)
    return result


def combine(xs):
    return hashlib.blake2b("".join(xs).encode()).hexdigest()[:16]


def digest(x):
    return x
