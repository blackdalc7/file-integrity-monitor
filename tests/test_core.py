"""Tests for the hashing, scanning and comparison logic."""

from __future__ import annotations

import hashlib

import pytest

from fim.core import Baseline, compare, hash_file, scan_tree


@pytest.fixture
def tree(tmp_path):
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("world")
    (tmp_path / "sub" / "c.log").write_text("noise")
    return tmp_path


def test_hash_file_matches_hashlib(tmp_path):
    f = tmp_path / "x"
    f.write_bytes(b"abc123")
    assert hash_file(f, "sha256") == hashlib.sha256(b"abc123").hexdigest()
    assert hash_file(f, "md5") == hashlib.md5(b"abc123").hexdigest()


def test_hash_file_rejects_unknown_algo(tmp_path):
    f = tmp_path / "x"
    f.write_text("y")
    with pytest.raises(ValueError):
        hash_file(f, "crc32")


def test_scan_tree_records_relative_posix_paths(tree):
    files = scan_tree(tree)
    assert set(files) == {"a.txt", "sub/b.txt", "sub/c.log"}
    assert files["a.txt"]["size"] == 5
    assert files["a.txt"]["hash"] == hashlib.sha256(b"hello").hexdigest()


def test_scan_tree_excludes(tree):
    files = scan_tree(tree, excludes=["*.log"])
    assert "sub/c.log" not in files
    assert "a.txt" in files


def test_scan_tree_requires_directory(tmp_path):
    f = tmp_path / "file"
    f.write_text("z")
    with pytest.raises(NotADirectoryError):
        scan_tree(f)


def test_scan_tree_records_symlink_target(tmp_path):
    (tmp_path / "real.txt").write_text("data")
    link = tmp_path / "link.txt"
    link.symlink_to("real.txt")
    files = scan_tree(tmp_path)
    assert files["link.txt"]["hash"].startswith("symlink:")


def test_compare_detects_all_change_kinds():
    base = {
        "keep.txt": {"hash": "aaa", "size": 1},
        "gone.txt": {"hash": "bbb", "size": 1},
        "change.txt": {"hash": "ccc", "size": 1},
    }
    cur = {
        "keep.txt": {"hash": "aaa", "size": 1},
        "change.txt": {"hash": "zzz", "size": 2},
        "new.txt": {"hash": "ddd", "size": 1},
    }
    report = compare(base, cur)
    assert report.added == ["new.txt"]
    assert report.removed == ["gone.txt"]
    assert report.modified == ["change.txt"]
    assert not report.clean
    assert report.total_changes == 3


def test_compare_clean():
    same = {"a": {"hash": "x", "size": 1}}
    report = compare(same, dict(same))
    assert report.clean
    assert report.total_changes == 0


def test_baseline_roundtrip(tree):
    baseline = Baseline.create(tree)
    restored = Baseline.from_json(baseline.to_json())
    assert restored.algo == "sha256"
    assert restored.files == baseline.files


def test_baseline_save_load(tree, tmp_path):
    out = tmp_path / "base.json"
    Baseline.create(tree).save(out)
    loaded = Baseline.load(out)
    assert set(loaded.files) == {"a.txt", "sub/b.txt", "sub/c.log"}


def test_baseline_rejects_bad_version(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"version": 99, "algo": "sha256", "root": ".", "files": {}}')
    with pytest.raises(ValueError):
        Baseline.load(bad)
