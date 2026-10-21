"""Load and validate config.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path("config.yaml")

Config = dict[str, Any]


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Config:
    """Read a YAML config file into a dict."""
    with Path(path).open() as f:
        cfg: Config = yaml.safe_load(f)
    return cfg


def parse_bbox(text: str) -> tuple[float, float, float, float]:
    """Parse 'minLon,minLat,maxLon,maxLat' into a validated tuple."""
    parts = [float(p) for p in text.split(",")]
    if len(parts) != 4:
        raise ValueError(f"bbox needs 4 comma-separated numbers, got {text!r}")
    min_lon, min_lat, max_lon, max_lat = parts
    if not (min_lon < max_lon and min_lat < max_lat):
        raise ValueError(f"bbox min must be < max: {text!r}")
    return min_lon, min_lat, max_lon, max_lat
