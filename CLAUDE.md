# CLAUDE.md — Court Finder: Tennis & Pickleball Detection from Aerial Imagery

## How to use this file
Place this file at the root of an empty repo and run `claude` in that directory. Then prompt:

> Read CLAUDE.md and execute Phase 0 through Phase 8 in order. Stop at each verification gate, show me the evidence, and wait for my "go" before starting the next phase.

---

## 1. Mission
Build a CLI tool that, given a bounding box, outputs a GeoJSON of **tennis courts** and **pickleball courts**. It works in three layers:

1. **OSM harvest:** collect courts already mapped in OpenStreetMap.
2. **Pass 1 – candidate detection on NAIP (0.6 m):** use OpenCV to find blobs of court-colored surface, then classify each as tennis or pickleball by size measured in meters. YOLO-OBB is an optional fallback.
3. **Pass 2 – line-pattern verification on high-res imagery (≤15 cm, optional):** use Canny edges and Hough lines to match painted court line layouts. This separates tennis, pickleball, and shared tennis+pickleball courts.

Default test area is Plano, TX: `--bbox -96.85,33.0,-96.65,33.12` (minLon, minLat, maxLon, maxLat).

## 2. Hard constraints (non-negotiable)
- **NEVER** download, scrape, screenshot, cache, or programmatically access Google Maps, Google Earth, Google Static Maps API, or Apple Maps imagery or tiles. Their terms prohibit using map content for ML training/testing/validation and prohibit tracing or digitizing features from satellite imagery. These sources are for **manual human spot-checks only**, never in code.
- Allowed imagery and data:
  - OSM via the Overpass API. The data is ODbL; attribute "© OpenStreetMap contributors" in outputs.
  - USDA NAIP via the Microsoft Planetary Computer STAC API (collection `naip`) or the AWS NAIP buckets.
  - Optional high-res county or state orthoimagery, **only after the user confirms its license** in writing in `config.yaml` (`hires.license_confirmed: true`).
- **DOTA-pretrained YOLO weights are for academic use only.** Flag this in the README. Any commercial use requires the self-trained model from Phase 7.
- Ultralytics is AGPL-3.0. OpenCV is Apache-2.0. Note both in the README.
- No secrets in the repo. If any key is ever needed, use `.env` and add it to `.gitignore`.

## 3. Reference implementation: CourtFind (study, don't copy blindly)
- Devpost: https://devpost.com/software/courtfind
- GitHub: https://github.com/nseniow/TennisCourtLocator
- It was a 2021 hackathon tool that detected tennis courts with OpenCV using Canny edge detection, Hough line transforms, and geometric matching of the detected lines to a tennis court shape. Its authors reported that template matching and homography failed.
- **It used the Google Static Maps API for imagery. That violates constraint §2, so do not reuse its imagery code.**
- Tasks for Claude Code:
  1. Clone it into `reference/` (git-ignored) and read the line-detection and shape-matching logic.
  2. **Check its LICENSE file first.** If there is no license, or it is incompatible, re-implement the algorithm from scratch in `src/courtfinder/lines.py`. If it is permissive, porting code is allowed with attribution in the README.
  3. Extend the logic to pickleball line patterns (see §4).

## 4. Domain facts the code must encode
| Item | Value |
|---|---|
| Pickleball court (lines) | 20 × 44 ft = 6.10 × 13.41 m (880 sq ft) |
| Pickleball non-volley ("kitchen") line | 7 ft (2.13 m) from net, each side |
| Pickleball min. playing surface (USA Pickleball) | 30 × 64 ft ≈ 9.1 × 19.5 m |
| Tennis court, doubles (lines) | 36 × 78 ft = 10.97 × 23.77 m (2,808 sq ft) |
| Tennis service line | 21 ft (6.40 m) from net, each side |
| Tennis singles sidelines | 27 ft (8.23 m) apart |
| Line width | 2 in (5.08 cm) — **invisible at NAIP 0.6 m**, needs ≤15 cm imagery |
| NAIP ground sample distance | ~0.6 m/px (older years may be 1.0 m) |
| OSM tags | `leisure=pitch` + `sport=tennis` or `sport=pickleball` (sport may be semicolon-separated, e.g. `tennis;pickleball`) |
| DOTA class IDs (Ultralytics) | 4 = tennis court, 5 = basketball court |

Detected pads usually include runoff and fencing, so they will be larger than the line dimensions. Size thresholds must be **tunable config values**, calibrated in Phase 6. Do not hardcode them.

## 5. Tech stack
- Python 3.11+, managed with a `venv`
- Packages: `opencv-python-headless overpy pystac-client planetary-computer rasterio shapely geopandas pyproj numpy pillow typer pyyaml pytest`
- Optional fallback (Phase 4b/7): `ultralytics`
- CLI built with `typer`; configuration in `config.yaml`
- Output: GeoJSON in EPSG:4326

## 6. Target repo layout
```
court-finder/
├── CLAUDE.md
├── README.md
├── config.yaml
├── requirements.txt
├── .gitignore            # chips/, tiles/, runs/, reference/, caches, .env
├── reference/            # cloned TennisCourtLocator (git-ignored, read-only)
├── src/courtfinder/
│   ├── __init__.py
│   ├── cli.py            # typer: run, osm, fetch, detect, verify, classify, merge, train-labels, clean
│   ├── osm.py            # Overpass harvest -> GeoDataFrame
│   ├── naip.py           # STAC search + windowed COG reads
│   ├── hires.py          # optional licensed high-res ortho loader
│   ├── chips.py          # tiling with overlap, georef sidecars
│   ├── detect_cv.py      # Pass 1: OpenCV HSV mask -> contours -> minAreaRect
│   ├── detect_yolo.py    # Pass 1 fallback: YOLO-OBB (optional)
│   ├── lines.py          # Pass 2: Canny + Hough line-pattern matching
│   ├── classify.py       # geometry rules -> tennis/pickleball/shared/ambiguous
│   ├── merge.py          # union with OSM, dedupe, source tagging
│   └── labels.py         # OSM polygons -> training labels (Phase 7)
├── tests/
└── outputs/
```

## 7. config.yaml (initial values — tune in Phase 6)
```yaml
bbox: [-96.85, 33.0, -96.65, 33.12]
naip:
  datetime: "2022/2026"
  prefer_latest: true
hires:
  enabled: false
  path: null               # local GeoTIFF/COG or URL
  license_confirmed: false # must be true before any use
  max_gsd_m: 0.15
chips:
  size_px: 512
  overlap_px: 64
  upsample: 2
detect_cv:
  hsv_ranges:              # court surface colors; tune per imagery year
    green_blue: [[35, 40, 40], [130, 255, 220]]
    red_clay:   [[0, 60, 60], [15, 255, 220]]
  morph_kernel_px: 5
  min_fill_ratio: 0.80     # contour area / minAreaRect area
  exclude_ndvi_above: 0.3  # NAIP NIR band: drop grass/turf fields
detect_yolo:
  enabled: false
  weights: yolo11s-obb.pt
  imgsz: 1024
  conf: 0.15
  classes: [4, 5]
lines:
  canny: [50, 150]
  hough_threshold: 40
  min_line_len_m: 4.0
  max_line_gap_m: 0.5
  angle_tol_deg: 3
  spacing_tol_m: 0.4
classify:
  tennis_long_m: [20, 40]
  pickleball_long_m: [11, 21]
  aspect_ratio: [1.6, 2.6]
  pickleball_cluster_min: 4
merge:
  buffer_m: 10
```

---

## 8. Execution phases

Each phase ends with a **GATE**. Do not proceed until the gate passes and the user approves.

### Phase 0 — Scaffold
- Create the layout above.
- Create the venv, write `requirements.txt`, and install the packages.
- Add `.gitignore`, then `git init` and make an initial commit.
- Clone the reference repo into `reference/` and report its LICENSE status.
- **GATE:** `python -c "import cv2, rasterio, geopandas"` exits 0, `courtfinder --help` prints the commands, and the reference LICENSE status is reported.

### Phase 1 — OSM harvest (`osm.py`)
- Run an Overpass query for `way` and `node` elements with `leisure=pitch` and `sport~"tennis|pickleball"` within the bbox.
- Return ways as polygons and nodes as points.
- Normalize `sport` to one of {tennis, pickleball, both}.
- Write `outputs/osm_courts.geojson`.
- Add retry with backoff for Overpass rate limits.
- **GATE:** Print counts by sport, and show that the feature count is > 0 for Plano.

### Phase 2 — NAIP fetch (`naip.py`)
- Search the STAC collection `naip` for the bbox and date range; select the most recent year that covers the full area.
- Read the COGs with windows (all 4 bands, including NIR).
- Log the acquisition year and GSD.
- **GATE:** Show the number of items found, the year selected, and the GSD. Write one small RGB preview PNG.

### Phase 3 — Chipping (`chips.py`)
- Tile to 512 px with 64 px overlap and apply 2× upsampling.
- Save each chip as a PNG plus a JSON sidecar holding the affine transform, CRS, upsample factor, and source GSD.
- **GATE:** Add a test that converts a chip pixel back to lon/lat within 2 m of the source raster. Write `outputs/chip_footprints.geojson`.

### Phase 4 — Pass 1 detection, OpenCV primary (`detect_cv.py`)
Pipeline per chip:
1. Convert to HSV and apply `inRange` for each configured color range; OR the masks together.
2. Compute NDVI from the NIR band and zero out pixels above `exclude_ndvi_above`. This removes grass and turf fields that pass the green threshold.
3. Morphological close, then open.
4. `findContours` (external), then `minAreaRect`.
5. Keep contours where `fill = contourArea / rect_area ≥ min_fill_ratio` and the aspect ratio is in range.
6. Convert to meters using chip GSD ÷ upsample, emit map-CRS polygons, and apply NMS across overlaps.

- **GATE:**
  - Report the % of OSM tennis polygons hit (target ≥ 70%) and the false-positive count on 20 random chips.
  - Save 10 annotated debug chips.
  - List the false-positive types (pools, roofs, lots).

### Phase 4b — YOLO-OBB fallback (`detect_yolo.py`, optional)
- Run this only if Phase 4 recall is < 0.8 on OSM courts, or if the user requests it.
- Run DOTA-pretrained `yolo11s-obb.pt` with classes [4, 5], then union the results with the Phase 4 candidates.
- **GATE:** Recall improves over Phase 4 alone, and the academic-only license warning is printed at runtime.

### Phase 4c — Pass 2 line-pattern verification (`lines.py`, high-res only)
- Run only when `hires.enabled: true` **and** `hires.license_confirmed: true`. Otherwise skip this phase and log it.
- For each Pass 1 candidate, crop the high-res ortho with a 3 m buffer and rotate it to the candidate's `minAreaRect` angle.
- Run Canny, then `HoughLinesP`. Group lines as parallel or perpendicular within `angle_tol_deg`.
- Match the line spacing in meters against templates:
  - **Tennis:** sidelines 10.97 m and 8.23 m apart; baselines 23.77 m apart; service lines 6.40 m either side of center.
  - **Pickleball:** sidelines 6.10 m apart; baselines 13.41 m apart; kitchen lines 2.13 m either side of center.
  - **Shared:** tennis template matched **and** an additional pickleball kitchen or sideline set found inside it.
- Output `line_match ∈ {tennis, pickleball, shared, none}` with a score.
- Port or re-implement the CourtFind shape-matching logic per §3, and extend it with the pickleball and shared templates.
- **GATE:** On ≥ 20 hand-labeled high-res candidates, line_match accuracy is ≥ 0.85, with a confusion matrix shown.

### Phase 5 — Classification (`classify.py`)
- For each candidate, compute `long_m`, `short_m`, `aspect`, and `area_m2` in a UTM projection.
- Priority order:
  1. A `line_match` from Phase 4c, if present, wins.
  2. YOLO class 5 (basketball) → `other`, unless its size fits the pickleball range **and** it sits in a cluster ≥ `pickleball_cluster_min`.
  3. `long_m` in the tennis range → `tennis`.
  4. `long_m` in the pickleball range and aspect in range → `pickleball`.
  5. Otherwise → `ambiguous`.
- Clustering: when ≥ N small adjacent pads share one footprint, mark them `pickleball_complex`.
- **GATE:** Print a confusion matrix against the OSM-labeled courts.

### Phase 6 — Merge, calibrate, export (`merge.py`)
- Union detections with OSM features using `buffer_m`.
- Tag each feature with `source ∈ {osm, cv, yolo, both}` and `verified_by_lines: bool`.
- Output `outputs/courts_<bbox>_<date>.geojson` with the OSM attribution in its properties.
- Calibrate thresholds by fitting the OSM-matched length and HSV distributions per class, then write a suggested `config.tuned.yaml`.
- **GATE:** At least 60% of OSM features are tagged `both` (a lower value indicates a CRS bug), and tennis precision is ≥ 0.85.

### Phase 7 — Self-trained model (optional; needed only if YOLO is used commercially) (`labels.py`)
- Rasterize OSM tennis and pickleball polygons onto NAIP chips to produce YOLO-OBB labels.
- Classes: `0 tennis`, `1 pickleball`, `2 basketball_negative`.
- Split 80/10/10 by geographic tile to avoid spatial leakage.
- Train with `yolo obb train data=courts.yaml model=yolo11s-obb.yaml epochs=100 imgsz=1024`. Use the scratch config, not DOTA weights.
- **GATE:** Pickleball recall on the holdout improves over the Phase 5 baseline. Report mAP50 per class.

### Phase 8 — Automation & cleanup
- Add `courtfinder run --bbox ...` to chain Phases 1→6, skipping 4b, 4c, and 7 per config.
- Add a GitHub Actions workflow (or cron example) that runs monthly and commits dated GeoJSON.
- Add `courtfinder clean` to delete `chips/`, `tiles/`, `runs/`, and `reference/`.
- README must cover the data-source constraints, the licenses (ODbL, Apache-2.0, AGPL-3.0, DOTA academic-only), CourtFind attribution, usage examples, and known limits.
- **GATE:** Run `run` end-to-end from a fresh clone, then `clean` leaves only outputs and weights.

---

## 9. Known limitations (document in README)
- NAIP refreshes roughly every 2–3 years, so new courts may be missing.
- At 0.6 m, painted lines are invisible. Tennis courts with pickleball lines painted on classify as tennis unless high-res imagery (Phase 4c) is available.
- HSV thresholds drift by imagery year and season. Recalibrate them per NAIP vintage.
- Gray, faded, or tree-shaded courts are the weakest case for OpenCV. Use Phase 4b if recall suffers.
- Indoor and covered courts are invisible from above.

## 10. Coding conventions for Claude Code
- Use type hints throughout, give each module a docstring, and use `logging` (not print) in library code.
- Keep every threshold in `config.yaml`; no magic numbers.
- Write `pytest` tests for CRS round-trips, pixel→meter conversion, rectangle measurement, HSV masking on synthetic images, and line-spacing template matching on synthetic court drawings.
- Commit after each passing gate with the message `phase N: <summary>`.
- If a gate fails, diagnose and propose a fix. Do not silently loosen thresholds.
- Never add code that calls Google or Apple map endpoints, even "temporarily for testing."
