# file-integrity-monitor (fim)

A tiny Tripwire/AIDE-style file integrity monitor. It takes a **baseline** of a
directory tree — the content hash and size of every file — and later **verifies**
the tree against that baseline, telling you exactly which files were **added**,
**removed** or **modified**. Useful for noticing unexpected changes to a config
directory, a web root, or `/etc` on a small server.

Standard library only; no third-party dependencies.

## Quick start

```bash
# 1. record a baseline of a directory
PYTHONPATH=src python -m fim baseline /etc/nginx -o nginx.fim.json

# 2. later, check whether anything changed
PYTHONPATH=src python -m fim verify /etc/nginx -b nginx.fim.json
```

A clean tree:

```text
OK: 42 file(s) match the baseline.
```

A tampered tree (exit code 1, so it drops into cron or CI):

```text
  + added     sites-enabled/evil.conf
  - removed   conf.d/ssl.conf
  ~ modified  nginx.conf
CHANGED: 3 change(s) (1 added, 1 removed, 1 modified).
```

## Commands and options

```text
fim baseline PATH -o FILE   snapshot PATH into the baseline FILE
fim verify   PATH -b FILE   compare PATH against the baseline FILE
```

| Option | Applies to | Meaning |
|---|---|---|
| `--algo` | both | `sha256` (default), `sha1`, `md5`, `blake2b` |
| `--exclude GLOB` | both | Skip matching paths; repeatable, e.g. `--exclude '*.log'` |
| `-o, --output` | baseline | Where to write the baseline JSON |
| `-b, --baseline` | verify | Baseline JSON to compare against |

`verify` always re-hashes with the algorithm recorded in the baseline, so the
two scans are always comparable.

## How it works

- **Baseline** walks the tree in sorted order and stores
  `{relative/posix/path: {hash, size}}` plus the algorithm and root in a small
  JSON file. Sorted, relative, forward-slash paths make the file deterministic
  and portable across machines.
- **Verify** re-scans and diffs the two maps: keys only in the new scan are
  *added*, keys only in the baseline are *removed*, shared keys with a different
  hash are *modified*.
- Symlinks are recorded by their target (`symlink:...`) rather than followed,
  which avoids loops and keeps the hash to real file content.

```text
src/fim/
    core.py     hash_file, scan_tree, the Baseline and Report types, compare()
    cli.py      the `baseline` and `verify` subcommands
    __main__.py enables `python -m fim`
tests/
    test_core.py  hashing vs hashlib, scanning, excludes, symlinks, diffing
    test_cli.py   baseline -> tamper -> verify, exit codes, excludes
```

## A note on hashes

The default is **sha256**. `md5` and `sha1` are offered only for reading or
reproducing older baselines; they are not collision-resistant and should not be
relied on where an attacker could craft file contents.

## Tests

```bash
PYTHONPATH=src pytest --cov      # 15 tests, coverage gate 90% (actual ~96%)
```

## Licence

MIT. See [LICENSE](LICENSE).
