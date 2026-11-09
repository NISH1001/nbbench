"""Drive each notebook tool the way a user's "run all" does, and report when it got there.

Every adapter gets a work folder that already holds the notebook files, a `.venv` link to the
workload interpreter (gpy picks the kernel next to the notebook) and a `data/` folder that the
notebook's collector cell writes `result.json` into. Each tool runs with its own empty
`XDG_CONFIG_HOME`, so a user's settings never leak into a run.

  gpy             the `gpy` command in a pseudo-terminal; F5 (run all) once the first frame shows
  gpy-concurrent  the same with `concurrent = true` in gpy's config
  jupyterlab      `jupyter lab --no-browser`; a kernel over REST, every cell sent over its
                  WebSocket at once, as JupyterLab's "run all" does (browser rendering not counted)
  marimo          `marimo edit --headless`; the session WebSocket starts the kernel, then
                  instantiate with autoRun (browser rendering not counted)
"""

from __future__ import annotations

import asyncio
import fcntl
import json
import os
import pty
import re
import select
import shutil
import struct
import subprocess
import sys
import termios
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from nbbench.server import free_port

F5 = b"\x1b[15~"
DEVICE_ATTRIBUTES = b"\x1b[c"
DEVICE_ATTRIBUTES_REPLY = b"\x1b[?62;c"
FIRST_FRAME = b"tempfile"
TOOLS = ("gpy", "gpy-concurrent", "jupyterlab", "marimo")


@dataclass
class Launch:
    """What one launch measured: seconds from launch to the tool being ready, and its process."""

    t0: float
    ready: float | None
    pid: int
    fd: int | None = None


def result_path(workdir: Path) -> Path:
    return workdir / "data" / "result.json"


def gpy_command(gpy: str | None) -> list[str] | None:
    """`--gpy` as a command: a gpython checkout, an executable, or a name on PATH.

    Without `--gpy`, the gpy pinned in the `tools` extra (next to this interpreter) comes first.
    """
    pinned = Path(sys.prefix) / "bin" / "gpy"
    if gpy is None and pinned.exists():
        return [str(pinned)]
    candidate = gpy or "gpy"
    path = Path(candidate).expanduser()
    if path.is_dir():
        for inner in (path / ".venv" / "bin" / "gpy", path / "gpython"):
            if inner.exists():
                return [str(inner)]
        return None
    found = shutil.which(str(path))
    return [found] if found else None


def gpy_python(command: list[str]) -> str | None:
    """The interpreter gpy runs on, read from its launcher's shebang."""
    try:
        first = Path(command[0]).read_bytes()[:512].split(b"\n", 1)[0]
    except OSError:
        return None
    if not first.startswith(b"#!"):
        return None
    interpreter = first[2:].decode().strip().split()[0]
    return interpreter if Path(interpreter).exists() else None


def gpy_has_concurrency(command: list[str]) -> bool:
    """gpy releases up to 0.1.2 have no concurrent mode and silently ignore `concurrent = true`."""
    python = gpy_python(command)
    if python is None:
        return False
    probe = subprocess.run([python, "-c", "import gpython.concurrency"], capture_output=True, timeout=60)
    return probe.returncode == 0


def available(tool: str, gpy: str | None = None) -> str | None:
    """None when the tool can run here, else why not."""
    if tool in ("gpy", "gpy-concurrent"):
        command = gpy_command(gpy)
        if not command:
            return f"no gpy found (pass --gpy PATH or put gpy on PATH; got {gpy or 'gpy'})"
        if tool == "gpy-concurrent" and not gpy_has_concurrency(command):
            return f"{command[0]} has no concurrent mode (needs gpy with gpython.concurrency; pass --gpy CHECKOUT)"
        return None
    module = {"jupyterlab": "jupyterlab", "marimo": "marimo"}[tool]
    try:
        __import__(module)
    except ImportError:
        return f"{module} is not installed in {sys.prefix} (install nbbench[tools])"
    return None


def tool_env(tool: str, workdir: Path, port: int) -> dict[str, str]:
    config = workdir / "config"
    (config / "gpython").mkdir(parents=True, exist_ok=True)
    if tool == "gpy-concurrent":
        (config / "gpython" / "config.toml").write_text("concurrent = true\n")
    elif tool == "gpy":
        (config / "gpython" / "config.toml").write_text("concurrent = false\n")
    return {
        **os.environ,
        "NBBENCH_DIR": str(workdir / "data"),
        "NBBENCH_PORT": str(port),
        "XDG_CONFIG_HOME": str(config),
        "TERM": "xterm-256color",
    }


def wait_for_result(workdir: Path, t0: float, timeout: float, tool: str, alive) -> None:
    target = result_path(workdir)
    while not target.exists():
        if time.time() - t0 > timeout:
            raise TimeoutError(f"{tool} did not finish within {timeout:.0f} s")
        if not alive():
            raise RuntimeError(f"{tool} exited before the notebook finished")
        time.sleep(0.005)
    while True:
        try:
            json.loads(target.read_text())
            return
        except (json.JSONDecodeError, OSError):
            time.sleep(0.002)


def run_gpy(workdir: Path, notebook: Path, timeout: float, env: dict[str, str], gpy: str | None) -> Launch:
    command = gpy_command(gpy)
    t0 = time.time()
    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(workdir)
        os.execve(command[0], [*command, str(notebook)], env)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 45, 140, 0, 0))
    launch = Launch(t0, None, pid)
    screen = b""
    target = result_path(workdir)
    try:
        while not target.exists():
            if time.time() - t0 > timeout:
                raise TimeoutError(f"gpy did not finish within {timeout:.0f} s (first frame seen: {launch.ready is not None})")
            readable, _, _ = select.select([fd], [], [], 0.005)
            if not readable:
                continue
            try:
                data = os.read(fd, 65536)
            except OSError:
                raise RuntimeError("gpy exited before the notebook finished") from None
            if DEVICE_ATTRIBUTES in data:
                os.write(fd, DEVICE_ATTRIBUTES_REPLY)
            if launch.ready is None:
                screen += data
                if FIRST_FRAME in screen:
                    launch.ready = time.time() - t0
                    os.write(fd, F5)
        wait_for_result(workdir, t0, timeout, "gpy", lambda: True)
        launch.fd = fd
        return launch
    except BaseException:
        finish(launch)
        os.close(fd)
        raise


async def _wait_http(url: str, timeout: float, headers: dict[str, str] | None = None) -> None:
    from tornado.httpclient import AsyncHTTPClient, HTTPClientError

    start = time.time()
    while True:
        try:
            await AsyncHTTPClient().fetch(url, headers=headers)
            return
        except HTTPClientError:
            return
        except OSError:
            if time.time() - start > timeout:
                raise
            await asyncio.sleep(0.02)


def _execute_request(session: str, code: str) -> str:
    return json.dumps({
        "header": {"msg_id": uuid.uuid4().hex, "msg_type": "execute_request", "username": "nbbench",
                   "session": session, "date": "", "version": "5.3"},
        "parent_header": {}, "metadata": {}, "channel": "shell", "buffers": [],
        "content": {"code": code, "silent": False, "store_history": True, "user_expressions": {},
                    "allow_stdin": False, "stop_on_error": True},
    })


async def _run_lab(workdir: Path, notebook: Path, timeout: float, env: dict[str, str]) -> Launch:
    from tornado.httpclient import AsyncHTTPClient
    from tornado.websocket import websocket_connect

    cells = ["".join(cell["source"]) for cell in json.loads(notebook.read_text())["cells"]]
    port, token = free_port(), uuid.uuid4().hex
    auth = {"Authorization": f"token {token}"}
    t0 = time.time()
    proc = subprocess.Popen(
        [sys.executable, "-m", "jupyterlab", "--no-browser", f"--port={port}", f"--IdentityProvider.token={token}",
         f"--ServerApp.root_dir={workdir}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, cwd=workdir,
    )
    launch = Launch(t0, None, proc.pid)
    try:
        await _wait_http(f"http://127.0.0.1:{port}/api/status", timeout, auth)
        launch.ready = time.time() - t0
        response = await AsyncHTTPClient().fetch(
            f"http://127.0.0.1:{port}/api/kernels", method="POST", headers=auth, body=json.dumps({"name": "python3"})
        )
        kernel = json.loads(response.body)["id"]
        ws = await websocket_connect(f"ws://127.0.0.1:{port}/api/kernels/{kernel}/channels?token={token}")
        session = uuid.uuid4().hex
        for source in cells:
            ws.write_message(_execute_request(session, source))
        await asyncio.to_thread(wait_for_result, workdir, t0, timeout, "jupyterlab", lambda: proc.poll() is None)
        ws.close()
        return launch
    except BaseException:
        finish(launch)
        raise


async def _run_marimo(workdir: Path, notebook: Path, timeout: float, env: dict[str, str]) -> Launch:
    from tornado.httpclient import AsyncHTTPClient
    from tornado.websocket import websocket_connect

    port = free_port()
    t0 = time.time()
    proc = subprocess.Popen(
        [sys.executable, "-m", "marimo", "edit", str(notebook), "--headless", "--no-token", "-p", str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, cwd=workdir,
    )
    launch = Launch(t0, None, proc.pid)
    try:
        await _wait_http(f"http://127.0.0.1:{port}/health", timeout)
        launch.ready = time.time() - t0
        page = (await AsyncHTTPClient().fetch(f"http://127.0.0.1:{port}/")).body.decode()
        found = re.search(r'data-token="([^"]+)"', page) or re.search(r'"serverToken":\s*"([^"]+)"', page)
        server_token = found.group(1) if found else ""
        session = uuid.uuid4().hex
        ws = await websocket_connect(f"ws://127.0.0.1:{port}/ws?session_id={session}")
        while True:
            message = await ws.read_message()
            if message is None or '"kernel-ready"' in message:
                break
        await AsyncHTTPClient().fetch(
            f"http://127.0.0.1:{port}/api/kernel/instantiate", method="POST",
            headers={"Marimo-Session-Id": session, "Marimo-Server-Token": server_token,
                     "Content-Type": "application/json"},
            body=json.dumps({"objectIds": [], "values": [], "autoRun": True}),
        )

        async def drain() -> None:
            while await ws.read_message() is not None:
                pass

        reader = asyncio.create_task(drain())
        await asyncio.to_thread(wait_for_result, workdir, t0, timeout, "marimo", lambda: proc.poll() is None)
        reader.cancel()
        ws.close()
        return launch
    except BaseException:
        finish(launch)
        raise


def tree_mb(pid: int) -> float:
    import psutil

    try:
        root = psutil.Process(pid)
        procs = [root] + root.children(recursive=True)
    except psutil.Error:
        return 0.0
    total = 0
    for proc in procs:
        try:
            total += proc.memory_info().rss
        except psutil.Error:
            pass
    return total / 2**20


def finish(launch: Launch) -> None:
    """Kill the tool's whole process tree and reap it."""
    import psutil

    try:
        root = psutil.Process(launch.pid)
        procs = root.children(recursive=True) + [root]
    except psutil.Error:
        procs = []
    for proc in procs:
        try:
            proc.kill()
        except psutil.Error:
            pass
    psutil.wait_procs(procs, timeout=5)
    fd = getattr(launch, "fd", None)
    if fd is not None:
        try:
            os.close(fd)
        except OSError:
            pass
        launch.fd = None


NOTEBOOK = {"gpy": "nb_gpy.py", "gpy-concurrent": "nb_gpy.py", "jupyterlab": "nb.ipynb", "marimo": "nb_marimo.py"}


def launch(tool: str, workdir: Path, timeout: float, port: int, gpy: str | None = None) -> tuple[Launch, float]:
    """Run the notebook in `workdir` with `tool`; return the launch and the tree's memory in MB at the end."""
    env = tool_env(tool, workdir, port)
    notebook = workdir / NOTEBOOK[tool]
    if tool in ("gpy", "gpy-concurrent"):
        started = run_gpy(workdir, notebook, timeout, env, gpy)
    elif tool == "jupyterlab":
        started = asyncio.run(_run_lab(workdir, notebook, timeout, env))
    else:
        started = asyncio.run(_run_marimo(workdir, notebook, timeout, env))
    memory = tree_mb(started.pid)
    finish(started)
    return started, memory
