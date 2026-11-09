import marimo

__generated_with = "nbbench"
app = marimo.App()


@app.cell
def _():
    import os
    import sys
    import tempfile
    import time

    P = {'requests': 5, 'parallel': 4}
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


    import asyncio
    import hashlib


    async def fetch(path):
        reader, writer = await asyncio.open_connection(HOST, PORT)
        writer.write(f"GET /{path} HTTP/1.0\r\nHost: nbbench\r\n\r\n".encode())
        raw = await reader.read()
        writer.close()
        await writer.wait_closed()
        return raw.split(b"\r\n\r\n", 1)[1]


    def initial():
        return "0" * 16


    async def work(x, i):
        limit = asyncio.Semaphore(P["parallel"])

        async def bounded(path):
            async with limit:
                return await fetch(path)

        bodies = await asyncio.gather(*(bounded(f"{i}/{k}") for k in range(P["requests"])))
        result = hashlib.blake2b(x.encode())
        for body in bodies:
            result.update(body)
        return result.hexdigest()[:16]


    def combine(xs):
        return hashlib.blake2b("".join(xs).encode()).hexdigest()[:16]


    def digest(x):
        return x


    x0 = initial()
    print('setup', 'http_async')
    return (DIR, HOST, P, PORT, asyncio, combine, digest, fetch, finish, hashlib, initial, os, sys, tempfile, time, work, x0,)


@app.cell
async def _(digest, time, work, x0):
    t0_1 = time.time()
    x1 = await work(x0, 1)
    span1 = (t0_1, time.time())
    d1 = digest(x1)
    print(1, d1)
    return (d1, span1, t0_1, x1,)


@app.cell
async def _(digest, time, work, x0):
    t0_2 = time.time()
    x2 = await work(x0, 2)
    span2 = (t0_2, time.time())
    d2 = digest(x2)
    print(2, d2)
    return (d2, span2, t0_2, x2,)


@app.cell
async def _(digest, time, work, x0):
    t0_3 = time.time()
    x3 = await work(x0, 3)
    span3 = (t0_3, time.time())
    d3 = digest(x3)
    print(3, d3)
    return (d3, span3, t0_3, x3,)


@app.cell
async def _(digest, time, work, x0):
    t0_4 = time.time()
    x4 = await work(x0, 4)
    span4 = (t0_4, time.time())
    d4 = digest(x4)
    print(4, d4)
    return (d4, span4, t0_4, x4,)


@app.cell
async def _(digest, time, work, x0):
    t0_5 = time.time()
    x5 = await work(x0, 5)
    span5 = (t0_5, time.time())
    d5 = digest(x5)
    print(5, d5)
    return (d5, span5, t0_5, x5,)


@app.cell
async def _(digest, time, work, x0):
    t0_6 = time.time()
    x6 = await work(x0, 6)
    span6 = (t0_6, time.time())
    d6 = digest(x6)
    print(6, d6)
    return (d6, span6, t0_6, x6,)


@app.cell
async def _(digest, time, work, x0):
    t0_7 = time.time()
    x7 = await work(x0, 7)
    span7 = (t0_7, time.time())
    d7 = digest(x7)
    print(7, d7)
    return (d7, span7, t0_7, x7,)


@app.cell
async def _(digest, time, work, x0):
    t0_8 = time.time()
    x8 = await work(x0, 8)
    span8 = (t0_8, time.time())
    d8 = digest(x8)
    print(8, d8)
    return (d8, span8, t0_8, x8,)


@app.cell
async def _(digest, time, work, x0):
    t0_9 = time.time()
    x9 = await work(x0, 9)
    span9 = (t0_9, time.time())
    d9 = digest(x9)
    print(9, d9)
    return (d9, span9, t0_9, x9,)


@app.cell
async def _(digest, time, work, x0):
    t0_10 = time.time()
    x10 = await work(x0, 10)
    span10 = (t0_10, time.time())
    d10 = digest(x10)
    print(10, d10)
    return (d10, span10, t0_10, x10,)


@app.cell
def _(d1, d10, d2, d3, d4, d5, d6, d7, d8, d9, finish, span1, span10, span2, span3, span4, span5, span6, span7, span8, span9):
    finish([span1, span2, span3, span4, span5, span6, span7, span8, span9, span10], [d1, d2, d3, d4, d5, d6, d7, d8, d9, d10])
    return


if __name__ == "__main__":
    app.run()
