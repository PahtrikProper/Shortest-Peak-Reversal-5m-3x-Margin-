"""Shared filesystem paths for the Short Trade Margin Call package."""

from __future__ import annotations

from pathlib import Path

# Package location: /workspace/.../src/ada_short_trade_margin_call
PACKAGE_ROOT = Path(__file__).resolve().parent
# Repository root lives one level above the src directory.
REPO_ROOT = PACKAGE_ROOT.parents[1]
# Keep ADA artifacts isolated from the SOL runner.
DATA_DIR = REPO_ROOT / "data" / "ada"

# Ensure the data directory always exists for JSON artifacts created at runtime.
DATA_DIR.mkdir(parents=True, exist_ok=True)
