"""Phase 1 tests: query building, sport normalization, geometry conversion, retry.

The Overpass payload below is a hand-built synthetic fixture, not real OSM data.
"""

import json
from pathlib import Path

import overpy
import pytest

from courtfinder import OSM_ATTRIBUTION
from courtfinder.osm import build_query, normalize_sport, query_with_retry, result_to_gdf, write_geojson

BBOX = (-96.85, 33.0, -96.65, 33.12)


def _synthetic_result() -> overpy.Result:
    sq = [(1, 33.05, -96.75), (2, 33.05, -96.7499), (3, 33.0502, -96.7499), (4, 33.0502, -96.75)]
    nodes = [{"type": "node", "id": i, "lat": la, "lon": lo} for i, la, lo in sq]
    data = {
        "elements": [
            {"type": "way", "id": 100, "nodes": [1, 2, 3, 4, 1],
             "tags": {"leisure": "pitch", "sport": "tennis", "surface": "hard"}},
            {"type": "way", "id": 101, "nodes": [1, 2, 3, 4, 1],
             "tags": {"leisure": "pitch", "sport": "Tennis;Pickleball"}},
            {"type": "way", "id": 102, "nodes": [1, 2, 3],
             "tags": {"leisure": "pitch", "sport": "pickleball"}},
            {"type": "way", "id": 103, "nodes": [1, 2, 3, 4, 1],
             "tags": {"leisure": "pitch", "sport": "table_tennis"}},
            {"type": "node", "id": 200, "lat": 33.1, "lon": -96.7,
             "tags": {"leisure": "pitch", "sport": "pickleball", "name": "Synthetic Pad"}},
            *nodes,
        ]
    }
    return overpy.Result.from_json(data)


def test_build_query_uses_south_west_north_east() -> None:
    q = build_query(BBOX, 180)
    assert "(33.0,-96.85,33.12,-96.65)" in q
    assert q.count('["leisure"="pitch"]') == 2
    assert "[timeout:180]" in q


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("tennis", "tennis"),
        ("pickleball", "pickleball"),
        ("tennis;pickleball", "both"),
        (" Pickleball ; TENNIS ", "both"),
        ("tennis;basketball", "tennis"),
        ("table_tennis", None),
        ("soccer", None),
        (None, None),
        ("", None),
    ],
)
def test_normalize_sport(raw: str | None, expected: str | None) -> None:
    assert normalize_sport(raw) == expected


def test_result_to_gdf() -> None:
    gdf = result_to_gdf(_synthetic_result()).set_index("osm_id")
    assert gdf.crs.to_epsg() == 4326
    assert set(gdf.index) == {100, 101, 102, 200}  # 103 table_tennis dropped, skeleton nodes dropped
    assert gdf.loc[100, "sport"] == "tennis" and gdf.geometry[100].geom_type == "Polygon"
    assert gdf.loc[101, "sport"] == "both"
    assert gdf.geometry[102].geom_type == "LineString"  # unclosed way kept, flagged in log
    assert gdf.loc[200, "sport"] == "pickleball" and gdf.geometry[200].geom_type == "Point"
    assert (gdf["attribution"] == OSM_ATTRIBUTION).all()


def test_write_geojson_has_attribution(tmp_path: Path) -> None:
    out = write_geojson(result_to_gdf(_synthetic_result()), tmp_path / "o.geojson")
    fc = json.loads(out.read_text())
    assert fc["attribution"] == OSM_ATTRIBUTION
    assert len(fc["features"]) == 4


def test_retry_rotates_mirrors_and_backs_off() -> None:
    calls: list[str] = []
    sleeps: list[float] = []
    ok = _synthetic_result()

    class FakeApi:
        def __init__(self, url: str) -> None:
            self.url = url

        def query(self, q: str) -> overpy.Result:
            calls.append(self.url)
            if len(calls) < 3:
                raise overpy.exception.OverpassTooManyRequests()
            return ok

    res = query_with_retry("q", ["a", "b"], 5, 2.0, 3.0, api_factory=FakeApi, sleep=sleeps.append)
    assert res is ok
    assert calls == ["a", "b", "a"]
    assert sleeps == [2.0, 3.0]  # 2*2**1=4 capped at max 3


def test_retry_gives_up() -> None:
    class Down:
        def __init__(self, url: str) -> None: ...

        def query(self, q: str) -> overpy.Result:
            raise overpy.exception.OverpassGatewayTimeout()

    with pytest.raises(RuntimeError, match="after 3 attempts"):
        query_with_retry("q", ["a"], 2, 0.0, 0.0, api_factory=Down, sleep=lambda s: None)
