"""Shared project paths. Scripts in code/ import from here: `from config import RAW`."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
DERIVED = ROOT / "data" / "derived"
OUTPUT = ROOT / "output"
