"""Typer CLI entry point for courtfinder."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Annotated, Optional

import typer

from courtfinder.config import DEFAULT_CONFIG_PATH, load_config, parse_bbox

app = typer.Typer(help="Find tennis and pickleball courts from OSM + NAIP imagery.", no_args_is_help=True)
log = logging.getLogger("courtfinder")

BboxOpt = Annotated[Optional[str], typer.Option(help="minLon,minLat,maxLon,maxLat (defaults to config.yaml)")]
ConfigOpt = Annotated[Path, typer.Option(help="Path to config.yaml")]

CLEAN_DIRS = ("chips", "tiles", "runs", "reference")


@app.callback()
def main(verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def _resolve(bbox: Optional[str], config: Path) -> tuple[dict, tuple[float, float, float, float]]:
    cfg = load_config(config)
    box = parse_bbox(bbox) if bbox else tuple(cfg["bbox"])
    return cfg, box  # type: ignore[return-value]


def _pending(phase: str) -> None:
    typer.echo(f"Not implemented yet ({phase}).", err=True)
    raise typer.Exit(code=2)


@app.command()
def run(bbox: BboxOpt = None, config: ConfigOpt = DEFAULT_CONFIG_PATH) -> None:
    """Chain osm -> fetch -> detect -> verify -> classify -> merge."""
    _pending("Phase 8")


@app.command()
def osm(bbox: BboxOpt = None, config: ConfigOpt = DEFAULT_CONFIG_PATH) -> None:
    """Harvest OSM tennis/pickleball pitches to outputs/osm_courts.geojson."""
    from courtfinder import osm as osm_mod

    cfg, box = _resolve(bbox, config)
    try:
        gdf = osm_mod.harvest(box, cfg)
    except RuntimeError as e:
        typer.echo(f"OSM harvest failed: {e} (cause: {e.__cause__!r})", err=True)
        raise typer.Exit(code=1) from e
    out = osm_mod.write_geojson(gdf, Path("outputs/osm_courts.geojson"))
    counts = gdf.groupby(["sport", gdf.geom_type]).size() if len(gdf) else {}
    typer.echo(f"bbox={box}  total={len(gdf)}  -> {out}")
    for (sport, gtype), n in dict(counts).items():
        typer.echo(f"  {sport:<10} {gtype:<10} {n}")


@app.command()
def fetch(bbox: BboxOpt = None, config: ConfigOpt = DEFAULT_CONFIG_PATH) -> None:
    """Fetch NAIP imagery for the bbox and tile it into chips."""
    _pending("Phase 2-3")


@app.command()
def detect(bbox: BboxOpt = None, config: ConfigOpt = DEFAULT_CONFIG_PATH) -> None:
    """Pass 1 candidate detection (OpenCV, optional YOLO-OBB)."""
    _pending("Phase 4")


@app.command()
def verify(bbox: BboxOpt = None, config: ConfigOpt = DEFAULT_CONFIG_PATH) -> None:
    """Pass 2 line-pattern verification on licensed high-res imagery."""
    _pending("Phase 4c")


@app.command()
def classify(bbox: BboxOpt = None, config: ConfigOpt = DEFAULT_CONFIG_PATH) -> None:
    """Classify candidates as tennis / pickleball / shared / ambiguous."""
    _pending("Phase 5")


@app.command()
def merge(bbox: BboxOpt = None, config: ConfigOpt = DEFAULT_CONFIG_PATH) -> None:
    """Merge detections with OSM and export dated GeoJSON."""
    _pending("Phase 6")


@app.command("train-labels")
def train_labels(bbox: BboxOpt = None, config: ConfigOpt = DEFAULT_CONFIG_PATH) -> None:
    """Build YOLO-OBB training labels from OSM polygons."""
    _pending("Phase 7")


@app.command()
def clean(
    root: Annotated[Path, typer.Option(help="Repo root")] = Path("."),
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
) -> None:
    """Delete chips/, tiles/, runs/, and reference/. Keeps outputs/ and weights."""
    targets = [root / d for d in CLEAN_DIRS if (root / d).exists()]
    if not targets:
        typer.echo("Nothing to clean.")
        return
    if not yes:
        typer.confirm(f"Delete {', '.join(str(t) for t in targets)}?", abort=True)
    for t in targets:
        shutil.rmtree(t)
        typer.echo(f"removed {t}")


if __name__ == "__main__":
    app()
