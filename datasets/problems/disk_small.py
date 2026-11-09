import hashlib
import os
import random

SMALL = random.Random(0).randbytes(4096)


def initial():
    return "0" * 16


def work(x, i):
    folder = os.path.join(DIR, f"small{i}")
    os.makedirs(folder, exist_ok=True)
    for k in range(P["files"]):
        with open(os.path.join(folder, str(k)), "wb") as out:
            out.write(SMALL)
            out.write(x.encode())
    result = hashlib.blake2b()
    for k in range(P["files"]):
        path = os.path.join(folder, str(k))
        with open(path, "rb") as back:
            result.update(back.read())
        os.remove(path)
    os.rmdir(folder)
    return result.hexdigest()[:16]


def combine(xs):
    return hashlib.blake2b("".join(xs).encode()).hexdigest()[:16]


def digest(x):
    return x
