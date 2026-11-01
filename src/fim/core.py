"""Core logic for the file integrity monitor.

A *baseline* is a snapshot of a directory tree: for every file, its content
hash and size. *Verifying* re-scans the tree and reports what has been added,
removed or modified since the baseline was taken. This is the idea behind tools
like Tripwire and AIDE, in miniature.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

SUPPORTED_ALGOS = ("sha256", "sha1", "md5", "blake2b")
_CHUNK = 65536


def hash_file(path: str | os.PathLike[str], algo: str = "sha256") -> str:
    """Return the hex digest of a file, reading it in chunks.

    md5 and sha1 are offered for comparing against legacy baselines only; they
    are not collision-resistant and sha256 (the default) should be preferred.
    """
    if algo not in SUPPORTED_ALGOS:
        raise ValueError(f"unsupported algorithm {algo!r}; choose from {SUPPORTED_ALGOS}")
    digest = hashlib.new(algo)
    with open(path, "rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _excluded(relpath: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(relpath, pat) for pat in patterns)


def scan_tree(
    root: str | os.PathLike[str],
    algo: str = "sha256",
    excludes: Iterable[str] | None = None,
) -> dict[str, dict[str, object]]:
    """Walk ``root`` and return ``{relative_path: {"hash", "size"}}``.

    Paths are stored relative to ``root`` with forward slashes, so a baseline is
    portable across machines and operating systems. Symlinks are recorded by the
    path they point at rather than followed, which avoids loops and keeps the
    scan to real files.
    """
    root_path = Path(root)
    if not root_path.is_dir():
        raise NotADirectoryError(f"{root!r} is not a directory")
    patterns = tuple(excludes or ())
    entries: dict[str, dict[str, object]] = {}

    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames.sort()
        for name in sorted(filenames):
            full = Path(dirpath) / name
            rel = full.relative_to(root_path).as_posix()
            if _excluded(rel, patterns):
                continue
            if full.is_symlink():
                entries[rel] = {"hash": "symlink:" + os.readlink(full), "size": 0}
                continue
            entries[rel] = {"hash": hash_file(full, algo), "size": full.stat().st_size}
    return entries


@dataclass
class Baseline:
    """A stored snapshot: metadata plus the per-file records."""

    algo: str
    root: str
    files: dict[str, dict[str, object]]

    @classmethod
    def create(
        cls,
        root: str | os.PathLike[str],
        algo: str = "sha256",
        excludes: Iterable[str] | None = None,
    ) -> Baseline:
        return cls(algo=algo, root=str(root), files=scan_tree(root, algo, excludes))

    def to_json(self) -> str:
        payload = {"version": 1, "algo": self.algo, "root": self.root, "files": self.files}
        return json.dumps(payload, indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> Baseline:
        data = json.loads(text)
        if data.get("version") != 1:
            raise ValueError("unrecognised baseline version")
        return cls(algo=data["algo"], root=data["root"], files=data["files"])

    def save(self, path: str | os.PathLike[str]) -> None:
        Path(path).write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> Baseline:
        return cls.from_json(Path(path).read_text(encoding="utf-8"))


@dataclass
class Report:
    """The difference between a baseline and a later scan."""

    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not (self.added or self.removed or self.modified)

    @property
    def total_changes(self) -> int:
        return len(self.added) + len(self.removed) + len(self.modified)


def compare(
    baseline: dict[str, dict[str, object]],
    current: dict[str, dict[str, object]],
) -> Report:
    """Compare two ``{path: record}`` maps and classify the differences."""
    base_keys = set(baseline)
    cur_keys = set(current)

    report = Report()
    report.added = sorted(cur_keys - base_keys)
    report.removed = sorted(base_keys - cur_keys)
    report.modified = sorted(
        path for path in base_keys & cur_keys if baseline[path]["hash"] != current[path]["hash"]
    )
    return report
