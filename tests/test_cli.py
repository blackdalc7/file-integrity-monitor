"""End-to-end tests for the fim command line."""

from __future__ import annotations

import pytest

from fim.cli import main


@pytest.fixture
def tree(tmp_path):
    # Scan a subdirectory so the baseline file (written to tmp_path) stays
    # outside the tree being monitored.
    root = tmp_path / "data"
    root.mkdir()
    (root / "a.txt").write_text("hello")
    (root / "b.txt").write_text("world")
    return root


def test_baseline_then_verify_clean(tree, tmp_path, capsys):
    base = tmp_path / "base.json"
    assert main(["baseline", str(tree), "-o", str(base)]) == 0
    assert "Wrote baseline of 2 file(s)" in capsys.readouterr().out

    assert main(["verify", str(tree), "-b", str(base)]) == 0
    assert "OK:" in capsys.readouterr().out


def test_verify_detects_changes(tree, tmp_path, capsys):
    base = tmp_path / "base.json"
    main(["baseline", str(tree), "-o", str(base)])
    capsys.readouterr()

    (tree / "a.txt").write_text("tampered")   # modify
    (tree / "b.txt").unlink()                   # remove
    (tree / "c.txt").write_text("brand new")    # add

    rc = main(["verify", str(tree), "-b", str(base)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "+ added     c.txt" in out
    assert "- removed   b.txt" in out
    assert "~ modified  a.txt" in out
    assert "3 change(s)" in out


def test_exclude_is_honoured(tree, tmp_path, capsys):
    base = tmp_path / "base.json"
    main(["baseline", str(tree), "-o", str(base), "--exclude", "*.txt"])
    out = capsys.readouterr().out
    assert "Wrote baseline of 0 file(s)" in out


def test_missing_baseline_file_errors(tree, tmp_path, capsys):
    rc = main(["verify", str(tree), "-b", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "fim:" in capsys.readouterr().err
