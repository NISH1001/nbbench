def initial():
    return 1


def work(x, i):
    total = x
    for k in range(P["n"]):
        total = (total * 31 + k * k) % 1_000_003
    return total


def combine(xs):
    return sum(xs) % 1_000_003


def digest(x):
    return str(x)
