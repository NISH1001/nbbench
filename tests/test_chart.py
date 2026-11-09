import json

from nbbench.chart import TOOLS, draw, geomean


def fake_report():
    rows = []
    for problem, domain, bound in (("matmul", "micro", "cpu"), ("pd_join", "datasci", "cpu"), ("io_csv", "datasci", "disk")):
        for shape in ("independent", "dag"):
            for n in (10, 100):
                for k, tool in enumerate(TOOLS):
                    sequential = n * 0.01
                    rows.append({
                        "problem": problem, "domain": domain, "bound": bound, "size": "s", "shape": shape, "n": n,
                        "tool": tool, "ok": True, "last": 0.5 + sequential * (1 + 0.1 * k), "span": sequential,
                        "gap_ms": 0.3 + k, "gap_ms_std": 0.05, "efficiency": 0.1 * (k + 1), "mem_mb": 150 + 20 * k,
                        "reference": {"sequential_s": sequential, "critical_path_s": 0.01, "checksum": "x"},
                        "runs": [{"last": 0.5 + sequential * (1 + 0.1 * k) + 0.01 * r, "span": sequential + 0.001 * r,
                                  "mem_mb": 150 + 20 * k + r, "ok": True} for r in range(3)],
                    })
    return {"meta": {"nbbench": "test", "date": "today", "platform": "test", "cpus": 4, "load": [0.1, 0, 0],
                     "python": "3.13.7 x", "packages": {"marimo": "0.25.2", "gpynb": None}}, "rows": rows}


def test_draw_writes_figures_and_summary(tmp_path):
    (tmp_path / "results.json").write_text(json.dumps(fake_report()))
    written = draw(tmp_path)
    for stem in ("cost_per_cell_s", "slowdown_s", "memory_s", "efficiency_cpu_s", "efficiency_disk_s", "per_problem_s"):
        assert (tmp_path / f"{stem}.pdf").stat().st_size > 1000
        assert (tmp_path / f"{stem}.png").stat().st_size > 1000
    summary = (tmp_path / "README.md").read_text()
    assert "| gpy (concurrent) |" in summary
    assert "![cost_per_cell_s](cost_per_cell_s.png)" in summary
    assert "**Figure s1.**" in summary
    assert "Error bars: ± 1 sd over 3 runs" in summary
    assert "gpynb" not in summary
    assert "README.md" in written


def test_geomean_ignores_missing():
    assert geomean([1.0, 4.0, None]) == 2.0
    assert geomean([]) is None
