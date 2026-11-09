"""`nbbench list | generate | samples | reference | calibrate | serve`."""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import contextmanager
from pathlib import Path

from nbbench import registry, server
from nbbench.generate import FORMATS, build, write

SAMPLE_PROBLEM = "matmul"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="nbbench")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("list", help="problems and shapes in the dataset")

    generate = commands.add_parser("generate", help="write notebooks in every format")
    _grid(generate)
    generate.add_argument("--out", type=Path, default=Path("build"))
    generate.add_argument("--formats", default=",".join(FORMATS))
    generate.add_argument("--reference", action="store_true", help="also run each notebook and store its checksum")

    samples = commands.add_parser("samples", help="rewrite datasets/samples with reference checksums")
    samples.add_argument("--n", type=int, default=10)

    reference = commands.add_parser("reference", help="run notebooks without a tool; print checksum and critical path")
    _grid(reference)

    calibrate = commands.add_parser("calibrate", help="time one work call per problem and size")
    calibrate.add_argument("--problems", default="")
    calibrate.add_argument("--sizes", default="s,m,l")
    calibrate.add_argument("--repeats", type=int, default=5)

    serve = commands.add_parser("serve", help="run the local HTTP server for network problems")
    serve.add_argument("port", type=int)

    args = parser.parse_args(argv)
    {"list": _list, "generate": _generate, "samples": _samples, "reference": _reference,
     "calibrate": _calibrate, "serve": lambda a: server.serve(a.port)}[args.command](args)


def _grid(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--problems", default="", help="ids, legacy ids, bound:x or domain:x; all when empty")
    parser.add_argument("--sizes", default="s")
    parser.add_argument("--shapes", default="independent")
    parser.add_argument("--cells", default="10")


def _notebooks(args: argparse.Namespace):
    for problem in registry.select(args.problems):
        for size in args.sizes.split(","):
            for shape in args.shapes.split(","):
                for n in (int(value) for value in args.cells.split(",")):
                    yield build(problem, size, shape, n)


@contextmanager
def _network(needed: bool):
    if not needed:
        yield 0
        return
    proc, port = server.start()
    try:
        yield port
    finally:
        proc.kill()


def _needs_network(problems) -> bool:
    return any(problem.bound == "net" for problem in problems)


def _list(args: argparse.Namespace) -> None:
    print(f"{'id':12}{'legacy':8}{'bound':7}{'domain':9}title")
    for problem in registry.problems().values():
        print(f"{problem.id:12}{problem.legacy or '':8}{problem.bound:7}{problem.domain:9}{problem.title}")
    print("\nshapes:", ", ".join(registry.shapes()))


def _generate(args: argparse.Namespace) -> None:
    from nbbench import reference

    formats = tuple(args.formats.split(","))
    with _network(args.reference and _needs_network(registry.select(args.problems))) as port:
        for notebook in _notebooks(args):
            folder = write(notebook, args.out, formats)
            if args.reference:
                _store_reference(folder, reference.execute(notebook, port))
            print(folder)


def _store_reference(folder: Path, result: dict) -> None:
    meta = json.loads((folder / "meta.json").read_text())
    meta["expected"] = {"checksum": result["checksum"], "digests": result["digests"]}
    (folder / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")


def _samples(args: argparse.Namespace) -> None:
    from nbbench import reference

    root = registry.DATASETS / "samples"
    plan = [build(problem, "s", "independent", args.n) for problem in registry.problems().values()]
    plan += [build(SAMPLE_PROBLEM, "s", shape, args.n) for shape in registry.shapes() if shape != "independent"]
    with _network(True) as port:
        for notebook in plan:
            folder = write(notebook, root)
            _store_reference(folder, reference.execute(notebook, port))
            print(folder.relative_to(registry.DATASETS.parent))


def _reference(args: argparse.Namespace) -> None:
    from nbbench import reference

    print(f"{'notebook':40}{'checksum':>18}{'sequential s':>14}{'critical s':>12}")
    with _network(_needs_network(registry.select(args.problems))) as port:
        for notebook in _notebooks(args):
            result = reference.execute(notebook, port)
            print(f"{notebook.name:40}{result['checksum']:>18}{result['sequential_s']:14.3f}{result['critical_path_s']:12.3f}")


def _calibrate(args: argparse.Namespace) -> None:
    from nbbench import reference

    targets = registry.sizes()
    chosen = registry.select(args.problems)
    print(f"{'problem':12}{'size':>5}{'target ms':>11}{'median ms':>11}{'ratio':>7}  params")
    with _network(_needs_network(chosen)) as port:
        for problem in chosen:
            for size in args.sizes.split(","):
                timing = reference.time_work(problem, size, args.repeats, port)
                ratio = timing["median_ms"] / targets[size]
                flag = "  MUTATES INPUT" if timing["mutates_input"] else ""
                print(f"{problem.id:12}{size:>5}{targets[size]:11d}{timing['median_ms']:11.1f}{ratio:7.2f}  "
                      f"{problem.params[size]}{flag}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
