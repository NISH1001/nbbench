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
