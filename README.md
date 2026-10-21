# court-finder

CLI that outputs a GeoJSON of tennis and pickleball courts for a bounding box, using OpenStreetMap + USDA NAIP imagery.
Full documentation lands in Phase 8; see `CLAUDE.md` for the build plan.

## Quick start
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
courtfinder --help
```

## Data & licensing (summary)
- OSM data: ODbL — "© OpenStreetMap contributors".
- Imagery: USDA NAIP via Microsoft Planetary Computer only. **No Google/Apple map imagery is accessed in code.**
- OpenCV: Apache-2.0. Ultralytics (optional): AGPL-3.0. DOTA-pretrained YOLO weights: **academic use only**.
- CourtFind / TennisCourtLocator (nseniow) inspired the line-matching approach. It has no license, so no code was copied; `lines.py` is an independent re-implementation.
