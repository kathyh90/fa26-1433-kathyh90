"""Checks that the shared paths in code/config.py point inside the repository."""

import sys
from pathlib import Path

# Make code/ importable so tests can `import config` like the scripts do.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "code"))

from config import DERIVED, OUTPUT, RAW, ROOT


def test_root_is_repo_root():
    """ROOT is the directory that holds pyproject.toml."""
    assert (ROOT / "pyproject.toml").is_file()


def test_paths_are_inside_root():
    """RAW, DERIVED, and OUTPUT all live under ROOT."""
    for path in (RAW, DERIVED, OUTPUT):
        assert path.is_relative_to(ROOT)
