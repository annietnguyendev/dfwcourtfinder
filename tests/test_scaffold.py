"""Phase 0 smoke tests: imports, config, CLI wiring."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from courtfinder.cli import app
from courtfinder.config import load_config, parse_bbox

ROOT = Path(__file__).resolve().parents[1]


def test_core_imports() -> None:
    import cv2, geopandas, rasterio  # noqa: F401,E401


def test_config_loads() -> None:
    cfg = load_config(ROOT / "config.yaml")
    assert cfg["bbox"] == [-96.85, 33.0, -96.65, 33.12]
    assert cfg["hires"]["license_confirmed"] is False


def test_parse_bbox() -> None:
    assert parse_bbox("-96.85,33.0,-96.65,33.12") == (-96.85, 33.0, -96.65, 33.12)
    with pytest.raises(ValueError):
        parse_bbox("-96.65,33.0,-96.85,33.12")


def test_cli_lists_all_commands() -> None:
    out = CliRunner().invoke(app, ["--help"]).output
    for cmd in ("run", "osm", "fetch", "detect", "verify", "classify", "merge", "train-labels", "clean"):
        assert cmd in out
