"""Pass 2: Canny + Hough line-pattern matching against tennis/pickleball templates (Phase 4c).

Re-implemented from scratch. The reference project (nseniow/TennisCourtLocator) ships no
license, so none of its code is reused; only the general approach (Canny -> HoughLinesP ->
pair parallel long lines -> confirm perpendicular connectors) informed the design.
"""
