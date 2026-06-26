"""
country.py — Generic country boolean mask aligned to an ECMWF analysis grid.

Uses Natural Earth 10m admin_0_countries, filtered by ISO_A3 / ADM0_A3 code,
with an optional bbox clip to exclude overseas territories.

For France specifically, use metropolitan_france_mask() from france.py which
handles the overseas-département exclusion via map_units (more precise).

Pattern is identical to france.py: bbox pre-filter → shapely.vectorized.contains
→ DataArray, so speed characteristics match.
"""
from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
import xarray as xr

BBox = Optional[Tuple[float, float, float, float]]  # (lon_min, lat_min, lon_max, lat_max)

# Module-level geometry cache keyed by (iso3, bbox)
_GEOM_CACHE: dict = {}


def country_geometry(iso3: str, bbox: BBox = None):
    """Return the unioned shapely geometry for a country.

    Parameters
    ----------
    iso3 : str
        ISO 3166-1 alpha-3 code (e.g. 'ESP').  ADM0_A3 is tried as fallback.
    bbox : (lon_min, lat_min, lon_max, lat_max) or None
        If given, the geometry is intersected with this box before returning
        (useful to exclude island territories far from the mainland).

    Returns
    -------
    shapely geometry  — (Multi)Polygon, or None if iso3 not found.
    """
    cache_key = (iso3, bbox)
    if cache_key in _GEOM_CACHE:
        return _GEOM_CACHE[cache_key]

    import cartopy.io.shapereader as shpreader
    from shapely.ops import unary_union
    from shapely.geometry import box as shapely_box

    shpfile = shpreader.natural_earth(
        resolution='10m', category='cultural', name='admin_0_countries'
    )
    reader = shpreader.Reader(shpfile)

    geoms = [
        r.geometry for r in reader.records()
        if (r.attributes.get('ISO_A3', '') == iso3
            or r.attributes.get('ADM0_A3', '') == iso3)
    ]

    if not geoms:
        _GEOM_CACHE[cache_key] = None
        return None

    geom = unary_union(geoms)

    if bbox is not None:
        lon_min, lat_min, lon_max, lat_max = bbox
        geom = geom.intersection(shapely_box(lon_min, lat_min, lon_max, lat_max))

    _GEOM_CACHE[cache_key] = geom
    return geom


def country_mask(da: xr.DataArray, iso3: str, bbox: BBox = None) -> xr.DataArray:
    """Build a boolean mask for a country on the grid of *da*.

    Parameters
    ----------
    da : xr.DataArray
        DataArray with dims/coords 'lat' and 'lon' as produced by normalize().
    iso3 : str
        ISO 3166-1 alpha-3 country code.
    bbox : (lon_min, lat_min, lon_max, lat_max) or None
        Optional bbox clip (see country_geometry).

    Returns
    -------
    xr.DataArray
        Boolean DataArray with the same lat/lon coordinates as *da*.
    """
    import shapely.vectorized as sv

    geom = country_geometry(iso3, bbox)
    if geom is None or geom.is_empty:
        raise ValueError(f"No geometry found for ISO3={iso3!r}")

    lats = da.coords['lat'].values
    lons = da.coords['lon'].values

    # Bbox pre-filter derived from geometry bounds (+ small buffer)
    lon_min_g, lat_min_g, lon_max_g, lat_max_g = geom.bounds
    buf = 0.5
    lat_in_bbox = (lats >= lat_min_g - buf) & (lats <= lat_max_g + buf)
    lon_in_bbox = (lons >= lon_min_g - buf) & (lons <= lon_max_g + buf)

    lat_idx = np.where(lat_in_bbox)[0]
    lon_idx = np.where(lon_in_bbox)[0]

    mask_values = np.zeros((len(lats), len(lons)), dtype=bool)

    if lat_idx.size > 0 and lon_idx.size > 0:
        cand_lats = lats[lat_idx]
        cand_lons = lons[lon_idx]
        lon_grid, lat_grid = np.meshgrid(cand_lons, cand_lats)

        inside = sv.contains(geom, lon_grid.ravel(), lat_grid.ravel())
        inside = inside.reshape(len(cand_lats), len(cand_lons))
        mask_values[np.ix_(lat_idx, lon_idx)] = inside

    return xr.DataArray(
        mask_values,
        coords={'lat': da.coords['lat'], 'lon': da.coords['lon']},
        dims=['lat', 'lon'],
        attrs={'description': f'Country boolean mask (ISO3={iso3}, NE 10m admin_0_countries)'},
    )
