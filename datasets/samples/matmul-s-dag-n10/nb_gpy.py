# %%
import os
import sys
import tempfile
import time

P = {'n': 1180}
DIR = os.environ.get("NBBENCH_DIR") or tempfile.mkdtemp(prefix="nbbench-")
HOST = "127.0.0.1"
PORT = int(os.environ.get("NBBENCH_PORT", "0"))


def finish(spans, digests):
    import hashlib
    import json

    checksum = hashlib.blake2b("".join(digests).encode()).hexdigest()[:16]
    result = {"prefix": sys.prefix, "spans": spans, "digests": digests, "checksum": checksum, "done": time.time()}
    with open(os.path.join(DIR, "result.json"), "w") as out:
        json.dump(result, out)
    print("checksum", checksum)


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


x0 = initial()
print('setup', 'matmul')

# %%
t0_1 = time.time()
x1 = work(x0, 1)
span1 = (t0_1, time.time())
d1 = digest(x1)
print(1, d1)

# %%
t0_2 = time.time()
x2 = work(x0, 2)
span2 = (t0_2, time.time())
d2 = digest(x2)
print(2, d2)

# %%
t0_3 = time.time()
x3 = work(x0, 3)
span3 = (t0_3, time.time())
d3 = digest(x3)
print(3, d3)

# %%
t0_4 = time.time()
x4 = work(x0, 4)
span4 = (t0_4, time.time())
d4 = digest(x4)
print(4, d4)

# %%
t0_5 = time.time()
x5 = work(x0, 5)
span5 = (t0_5, time.time())
d5 = digest(x5)
print(5, d5)

# %%
t0_6 = time.time()
x6 = work(x0, 6)
span6 = (t0_6, time.time())
d6 = digest(x6)
print(6, d6)

# %%
t0_7 = time.time()
x7 = work(x0, 7)
span7 = (t0_7, time.time())
d7 = digest(x7)
print(7, d7)

# %%
t0_8 = time.time()
x8 = work(x0, 8)
span8 = (t0_8, time.time())
d8 = digest(x8)
print(8, d8)

# %%
t0_9 = time.time()
x9 = work(combine([x2, x6]), 9)
span9 = (t0_9, time.time())
d9 = digest(x9)
print(9, d9)

# %%
t0_10 = time.time()
x10 = work(combine([x3, x7]), 10)
span10 = (t0_10, time.time())
d10 = digest(x10)
print(10, d10)

# %%
finish([span1, span2, span3, span4, span5, span6, span7, span8, span9, span10], [d1, d2, d3, d4, d5, d6, d7, d8, d9, d10])
