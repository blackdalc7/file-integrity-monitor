"""Tripwire-style file integrity monitor."""

from fim.core import Baseline, Report, compare, hash_file, scan_tree

__all__ = ["Baseline", "Report", "compare", "hash_file", "scan_tree"]
__version__ = "1.0.0"
