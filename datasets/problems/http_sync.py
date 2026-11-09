import hashlib
import urllib.request


def initial():
    return "0" * 16


def work(x, i):
    result = hashlib.blake2b(x.encode())
    for k in range(P["requests"]):
        with urllib.request.urlopen(f"http://{HOST}:{PORT}/{i}/{k}") as response:
            result.update(response.read())
    return result.hexdigest()[:16]


def combine(xs):
    return hashlib.blake2b("".join(xs).encode()).hexdigest()[:16]


def digest(x):
    return x
