# CourtFind / TennisCourtLocator — algorithm notes (study only)

Repo: https://github.com/nseniow/TennisCourtLocator. The **LICENSE is absent in all 60+ commits**, so it is all-rights-reserved. Do not copy code.
HEAD (`11e1b32`) has only a README: the code was removed in `fb6c8c1` when the project went closed-source as "Topografind".
Last commit containing code: `44593b4`. Its imagery came from `map_downloader.py` (Google Static Maps), which violates §2 and was not read.

## Approach (`find_tennis_court_hough_analysis`)
1. Grayscale, then `Canny(200, 200)`.
2. `HoughLinesP(rho=1, theta=1°, threshold=15, minLineLength=25 px, maxLineGap=12 px)`.
3. Bucket segments by **pixel** length: short 40–55 px (baselines), long 100–120 px (sidelines). This only worked at one fixed Google zoom level.
4. Sort the long lines by angle. Pair them as parallel (|Δθ| < 6°) when both endpoint pairs are 40–65 px apart.
5. For each parallel pair, find two short "connector" lines perpendicular to it (|cos Δθ| < 0.1) whose endpoints lie within 15 px of the pair's endpoints at each end. That forms a closed rectangle, which counts as a court.
6. Template matching (`TM_CCOEFF_NORMED` ≥ 0.9) was tried and abandoned.

## Gaps our re-implementation must fix
- Thresholds are fixed in pixels. Ours must use **meters**, derived from GSD (`min_line_len_m`, `spacing_tol_m`).
- It checks only the outer rectangle. Ours adds interior lines (singles sidelines 8.23 m, service lines ±6.40 m, kitchen ±2.13 m) to tell tennis, pickleball and shared courts apart.
- It does no rotation normalization. Ours rotates each crop to the candidate's `minAreaRect` angle first, so the lines become axis-aligned and spacing can be matched with 1-D projections.
