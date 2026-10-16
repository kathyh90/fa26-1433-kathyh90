import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "code"))

from config import DERIVED, OUTPUT, RAW, ROOT


def test_root_is_repo_root():
    assert (ROOT / "pyproject.toml").is_file()


def test_paths_are_inside_root():
    for path in (RAW, DERIVED, OUTPUT):
        assert path.is_relative_to(ROOT)
