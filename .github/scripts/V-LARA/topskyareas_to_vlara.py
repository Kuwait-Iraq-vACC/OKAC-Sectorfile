#!/usr/bin/env python3
"""
topskyareas_to_vlara.py
-----------------------
Converts TopSky area definition files (.txt) into a single GeoJSON
FeatureCollection for use with V-LARA.

Usage:
    python topskyareas_to_vlara.py \
        --input-dir ".data/TopSky Shared/Areas/Danger" \
        --input-dir ".data/TopSky Shared/Areas/Prohibited" \
        --input-dir ".data/TopSky Shared/Areas/Restricted" \
        --input-dir ".data/TopSky Shared/Areas/MOA" \
        --output ".data/V-LARA/okac.geojson" \
        --debug
"""

import argparse
import json
import re
import math
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Coordinate parsing
# ---------------------------------------------------------------------------

# Matches DMS tokens like N057.17.30.423 or W004.48.01.020
DMS_RE = re.compile(r'^([NSEW])(\d{1,3})\.(\d{1,2})\.(\d{1,2}(?:\.\d+)?)$')

# Matches bare coordinate lines like N032.20.28.000:E046.55.52.000
BARE_COORD_RE = re.compile(
    r'^([NSEW]\d{1,3}\.\d{1,2}\.\d{1,2}(?:\.\d+)?)'
    r':'
    r'([NSEW]\d{1,3}\.\d{1,2}\.\d{1,2}(?:\.\d+)?)$'
)


def dms_to_decimal(token: str) -> float:
    """Convert a DMS token (e.g. N052.28.00.000) to decimal degrees."""
    m = DMS_RE.match(token.strip())
    if not m:
        raise ValueError(f"Invalid coordinate format: {token!r}")
    hemi, d, mnt, sec = m.groups()
    val = int(d) + int(mnt) / 60.0 + float(sec) / 3600.0
    if hemi in ('S', 'W'):
        val = -val
    return val


def parse_coord_pair(lat_token: str, lon_token: str) -> List[float]:
    """Return [lon, lat] for GeoJSON (longitude first)."""
    return [dms_to_decimal(lon_token), dms_to_decimal(lat_token)]


# ---------------------------------------------------------------------------
# Circle approximation
# ---------------------------------------------------------------------------

EARTH_RADIUS_NM = 3440.065  # mean Earth radius in nautical miles


def _to_rad(d: float) -> float:
    return d * math.pi / 180.0


def _to_deg(r: float) -> float:
    return r * 180.0 / math.pi


def _dest_point(lat_deg: float, lon_deg: float, bearing_deg: float, dist_nm: float):
    """Compute destination point from origin, bearing and distance (spherical)."""
    lat1 = _to_rad(lat_deg)
    lon1 = _to_rad(lon_deg)
    brg  = _to_rad(bearing_deg)
    ang  = dist_nm / EARTH_RADIUS_NM

    sin1, cos1 = math.sin(lat1), math.cos(lat1)
    sin_a, cos_a = math.sin(ang), math.cos(ang)

    sin2 = sin1 * cos_a + cos1 * sin_a * math.cos(brg)
    lat2 = math.asin(sin2)
    lon2 = lon1 + math.atan2(math.sin(brg) * sin_a * cos1, cos_a - sin1 * sin2)
    lon2 = (lon2 + math.pi) % (2 * math.pi) - math.pi
    return _to_deg(lat2), _to_deg(lon2)


def _parse_latlon_token(token: str) -> float:
    """Accept either plain decimal or DMS format."""
    try:
        return float(token)
    except ValueError:
        return dms_to_decimal(token)


def _circle_ring(center_lat: float, center_lon: float,
                 radius_nm: float, spacing_deg: float) -> List[List[float]]:
    """Approximate a circle as a closed polygon ring."""
    if not (0.1 <= radius_nm <= 9999.9):
        raise ValueError(f"Radius out of bounds: {radius_nm}")
    if not (0.1 <= spacing_deg <= 120.0):
        raise ValueError(f"Spacing out of bounds: {spacing_deg}")

    n    = max(3, int(math.ceil(360.0 / spacing_deg)))
    step = 360.0 / n
    ring = []
    for i in range(n):
        lat, lon = _dest_point(center_lat, center_lon, i * step, radius_nm)
        ring.append([lon, lat])
    ring.append(ring[0])  # close the ring
    return ring


def parse_circle_line(line: str) -> List[List[float]]:
    """Parse a CIRCLE:Lat:Lon:Radius:Spacing line."""
    parts = [p.strip() for p in line.split(':')]
    if len(parts) != 5 or parts[0].upper() != 'CIRCLE':
        raise ValueError(f"Invalid CIRCLE line: {line!r}")
    lat        = _parse_latlon_token(parts[1])
    lon        = _parse_latlon_token(parts[2])
    radius_nm  = float(parts[3])
    spacing_deg = float(parts[4])
    return _circle_ring(lat, lon, radius_nm, spacing_deg)


# ---------------------------------------------------------------------------
# Altitude / FL helpers
# ---------------------------------------------------------------------------

def fl_value(s: str) -> int:
    """Convert a FL string, SFC or UNL to a numeric value."""
    s = s.strip().upper()
    if s in ('SFC', 'GND'):
        return 0
    if s in ('UNL', 'UNLIMITED'):
        return 999
    return int(s)


# ---------------------------------------------------------------------------
# File parser
# ---------------------------------------------------------------------------

def parse_area_file(path: Path, fallback_type: str) -> Optional[Dict[str, Any]]:
    """
    Parse a single TopSky area .txt file.

    Returns None if the file could not be parsed, otherwise a dict with keys:
        name, type, lowerFL, upperFL, coords, activePermanent
    """
    name            = None
    a_type          = None
    lower_fl        = None
    upper_fl        = None
    coords: List[List[float]]        = []
    circle_coords: List[List[float]] = []
    saw_coords      = False
    saw_circle      = False
    active_permanent = False

    try:
        with path.open('r', encoding='utf-8', errors='ignore') as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith(';'):
                    continue

                if line.startswith('AREA:'):
                    parts = line.split(':')
                    if len(parts) >= 3:
                        name = parts[-1].strip()

                elif line.startswith('CATEGORY:'):
                    _, val = line.split(':', 1)
                    a_type = val.strip()

                elif line.startswith('LIMITS:'):
                    parts = line.split(':')
                    if len(parts) >= 3:
                        lower_fl = fl_value(parts[1])
                        upper_fl = fl_value(parts[2])

                elif line.startswith('COORD:'):
                    if saw_circle:
                        raise ValueError(f"{path}: mixed CIRCLE and COORD lines are not allowed")
                    parts = line.split(':')
                    if len(parts) >= 3:
                        coords.append(parse_coord_pair(parts[1].strip(), parts[2].strip()))
                        saw_coords = True

                elif line.startswith('CIRCLE:'):
                    if saw_coords:
                        raise ValueError(f"{path}: mixed COORD and CIRCLE lines are not allowed")
                    circle_coords = parse_circle_line(line)
                    saw_circle = True

                elif line.startswith('ACTIVE:'):
                    _, val = line.split(':', 1)
                    if val.strip() == '1':
                        active_permanent = True

                else:
                    # Bare coordinate line: N032.20.28.000:E046.55.52.000
                    # Used by MOA files (no COORD: prefix)
                    bare = BARE_COORD_RE.match(line)
                    if bare:
                        if saw_circle:
                            raise ValueError(
                                f"{path.name}: cannot mix CIRCLE and bare coordinate lines"
                            )
                        coords.append(parse_coord_pair(bare.group(1), bare.group(2)))
                        saw_coords = True

    except Exception as exc:
        print(f"WARNING: Error while parsing {path}: {exc}", file=sys.stderr)
        traceback.print_exc()
        # Don't emit a half-parsed polygon — a truncated ring would still
        # pass validation once auto-closed, and silently show wrong airspace.
        return None

    if saw_circle:
        final_coords = circle_coords
    else:
        final_coords = coords
        # Close the ring if not already closed
        if final_coords and final_coords[0] != final_coords[-1]:
            final_coords.append(final_coords[0])

    return {
        "name":            name or path.stem,
        "type":            a_type or fallback_type,
        "lowerFL":         lower_fl if lower_fl is not None else 0,
        "upperFL":         upper_fl if upper_fl is not None else 999,
        "coords":          final_coords,
        "activePermanent": active_permanent,
    }


# ---------------------------------------------------------------------------
# Directory walker
# ---------------------------------------------------------------------------

def collect_files(input_dirs: List[str]) -> List[Path]:
    """Recursively collect all .txt files from the given directories."""
    files: List[Path] = []
    for d in input_dirs:
        p = Path(d)
        if not p.exists():
            print(f"⚠️  Skipping missing directory: {p}", file=sys.stderr)
            continue
        files.extend(sorted(p.rglob('*.txt')))
    return files


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compile TopSky area files into a single V-LARA GeoJSON."
    )
    parser.add_argument(
        '--input-dir', action='append', required=True,
        help='Input directory (repeat for multiple directories).'
    )
    parser.add_argument('--output', required=True, help='Output GeoJSON path.')
    parser.add_argument('--debug', action='store_true', help='Verbose output.')
    args = parser.parse_args()

    features: List[Dict[str, Any]] = []
    failed: List[Path] = []
    input_files = collect_files(args.input_dir)

    if args.debug:
        print(f"Located {len(input_files)} source file(s).")

    for file_path in input_files:
        fallback_type = file_path.parent.name
        area = parse_area_file(file_path, fallback_type)

        if area is None:
            failed.append(file_path)
            continue

        if area['activePermanent']:
            if args.debug:
                print(f"Skipping {file_path.name} — marked as permanently active.")
            continue

        if not area['coords']:
            if args.debug:
                print(f"Skipping {file_path.name} — no coordinates found.")
            continue

        features.append({
            "type": "Feature",
            "properties": {
                "name":    area["name"],
                "type":    area["type"],
                "lowerFL": area["lowerFL"],
                "upperFL": area["upperFL"],
            },
            "geometry": {
                "type":        "Polygon",
                "coordinates": [area["coords"]],
            },
        })

    feature_collection = {"type": "FeatureCollection", "features": features}

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with out_path.open('w', encoding='utf-8') as fh:
            json.dump(feature_collection, fh, ensure_ascii=False, indent=2)
        print(f"GeoJSON written to {out_path} — {len(features)} feature(s) included.")
        if failed:
            print(f"⚠️  {len(failed)} file(s) skipped due to parse errors:", file=sys.stderr)
            for p in failed:
                print(f"::warning file={p}::Failed to parse area file — not included in GeoJSON")
    except Exception as exc:
        print(f"ERROR: Could not write output file: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()