"""Overpass harvest of leisure=pitch tennis/pickleball features -> GeoDataFrame (Phase 1).

Ways become polygons, nodes become points. ``sport`` is normalized to one of
{tennis, pickleball, both}. Data is ODbL: every output carries OSM attribution.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any
from urllib.error import URLError

import geopandas as gpd
import overpy
from shapely.geometry import LineString, Point, Polygon

from courtfinder import OSM_ATTRIBUTION
from courtfinder.config import Config

log = logging.getLogger(__name__)

Bbox = tuple[float, float, float, float]

COLUMNS = ["osm_id", "osm_type", "sport", "sport_raw", "name", "surface", "attribution", "geometry"]

RETRYABLE: tuple[type[BaseException], ...] = (
    overpy.exception.OverpassTooManyRequests,
    overpy.exception.OverpassGatewayTimeout,
    overpy.exception.OverpassUnknownHTTPStatusCode,
    URLError,
    TimeoutError,
    ConnectionError,
)


def build_query(bbox: Bbox, timeout_s: int) -> str:
    """Overpass QL for tennis/pickleball pitches. Overpass bbox order is (S, W, N, E)."""
    min_lon, min_lat, max_lon, max_lat = bbox
    b = f"{min_lat},{min_lon},{max_lat},{max_lon}"
    flt = '["leisure"="pitch"]["sport"~"tennis|pickleball",i]'
    return (
        f"[out:json][timeout:{timeout_s}];\n"
        f"(\n  way{flt}({b});\n  node{flt}({b});\n);\n"
        "out body;\n>;\nout skel qt;\n"
    )


def normalize_sport(raw: str | None) -> str | None:
    """Map an OSM sport value (possibly ';'-separated) to tennis | pickleball | both."""
    if not raw:
        return None
    sports = {s.strip().lower() for s in raw.split(";")}
    has_t, has_p = "tennis" in sports, "pickleball" in sports
    if has_t and has_p:
        return "both"
    if has_t:
        return "tennis"
    if has_p:
        return "pickleball"
    return None


def _way_geometry(way: overpy.Way) -> Polygon | LineString | None:
    coords = [(float(n.lon), float(n.lat)) for n in way.nodes]
    if len(coords) >= 4 and coords[0] == coords[-1]:
        return Polygon(coords)
    if len(coords) >= 2:
        log.warning("way %s is not closed; keeping as LineString", way.id)
        return LineString(coords)
    return None


def _row(osm_type: str, osm_id: int, tags: dict[str, str], geom: Any) -> dict[str, Any] | None:
    sport = normalize_sport(tags.get("sport"))
    if sport is None or geom is None:
        return None
    return {
        "osm_id": osm_id,
        "osm_type": osm_type,
        "sport": sport,
        "sport_raw": tags.get("sport"),
        "name": tags.get("name"),
        "surface": tags.get("surface"),
        "attribution": OSM_ATTRIBUTION,
        "geometry": geom,
    }


def result_to_gdf(result: overpy.Result) -> gpd.GeoDataFrame:
    """Convert an Overpass result into an EPSG:4326 GeoDataFrame."""
    rows: list[dict[str, Any]] = []
    for way in result.ways:
        if way.tags.get("leisure") != "pitch":
            continue
        r = _row("way", way.id, way.tags, _way_geometry(way))
        if r:
            rows.append(r)
    for node in result.nodes:
        if node.tags.get("leisure") != "pitch":  # skip skeleton nodes of ways
            continue
        r = _row("node", node.id, node.tags, Point(float(node.lon), float(node.lat)))
        if r:
            rows.append(r)
    return gpd.GeoDataFrame(rows, columns=COLUMNS, geometry="geometry", crs="EPSG:4326")


def query_with_retry(
    query: str,
    urls: Sequence[str],
    max_retries: int,
    backoff_base_s: float,
    backoff_max_s: float,
    api_factory: Callable[[str], overpy.Overpass] = lambda url: overpy.Overpass(url=url),
    sleep: Callable[[float], None] = time.sleep,
) -> overpy.Result:
    """Run a query, rotating mirrors with exponential backoff on retryable errors."""
    last: BaseException | None = None
    for attempt in range(max_retries + 1):
        url = urls[attempt % len(urls)]
        try:
            log.info("Overpass query (attempt %d/%d) -> %s", attempt + 1, max_retries + 1, url)
            return api_factory(url).query(query)
        except RETRYABLE as e:
            last = e
            if attempt == max_retries:
                break
            delay = min(backoff_base_s * 2**attempt, backoff_max_s)
            log.warning("Overpass %s failed (%s: %s); retrying in %.1fs", url, type(e).__name__, e, delay)
            sleep(delay)
    raise RuntimeError(f"Overpass failed after {max_retries + 1} attempts") from last


def harvest(bbox: Bbox, cfg: Config) -> gpd.GeoDataFrame:
    """Fetch OSM tennis/pickleball courts within bbox."""
    o = cfg["osm"]
    result = query_with_retry(
        build_query(bbox, o["query_timeout_s"]),
        o["overpass_urls"],
        o["max_retries"],
        o["backoff_base_s"],
        o["backoff_max_s"],
    )
    gdf = result_to_gdf(result)
    log.info("OSM harvest: %d features", len(gdf))
    return gdf


def write_geojson(gdf: gpd.GeoDataFrame, path: Path) -> Path:
    """Write a FeatureCollection with a top-level attribution member."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fc = json.loads(gdf.to_json(drop_id=True))
    fc["attribution"] = OSM_ATTRIBUTION
    path.write_text(json.dumps(fc))
    log.info("wrote %s (%d features)", path, len(gdf))
    return path
