"""
france.py — Metropolitan France boolean mask aligned to an ECMWF analysis grid.

Uses the Natural Earth 10m admin_0_map_units layer, selecting the single unit
where GEOUNIT == 'France' (the map_units layer separates overseas départements
as their own units, so this selects ONLY metropolitan France incl. Corsica).

The polygon is rasterized onto the data grid via shapely.vectorized.contains
with a bounding-box pre-filter for speed, then ANDed with the metropolitan
bbox as a belt-and-suspenders guard.

Belt-and-suspenders metropolitan bbox
--------------------------------------
lat: [41.0, 52.0]  lon: [-6.0, 10.5]
Any cell outside this box is forced False regardless of polygon test result.
This prevents a mis-tagged overseas unit from leaking in (e.g. Réunion ~-21S,
French Guiana ~5N/-53E).
"""
from __future__ import annotations

import numpy as np
import xarray as xr

# Metropolitan France bounding box (belt-and-suspenders guard)
_METRO_LAT_MIN = 41.0
_METRO_LAT_MAX = 52.0
_METRO_LON_MIN = -6.0
_METRO_LON_MAX = 10.5

# Module-level cache for the metropolitan France geometry
_METRO_FRANCE_GEOM = None


def metropolitan_france_geometry():
    """Return the unioned shapely geometry of metropolitan France.

    Uses the Natural Earth 10m admin_0_map_units layer (GEOUNIT=='France'),
    intersected with the metropolitan bounding box so DOM territories are
    excluded.

    The result is cached module-level; subsequent calls are free.

    Returns
    -------
    shapely geometry
        Unioned (Multi)Polygon of metropolitan France incl. Corsica.
    """
    global _METRO_FRANCE_GEOM
    if _METRO_FRANCE_GEOM is not None:
        return _METRO_FRANCE_GEOM

    import cartopy.io.shapereader as shpreader
    from shapely.ops import unary_union
    from shapely.geometry import box as shapely_box

    shpfile = shpreader.natural_earth(
        resolution='10m', category='cultural', name='admin_0_map_units'
    )
    reader = shpreader.Reader(shpfile)
    france_geoms = [
        r.geometry for r in reader.records()
        if r.attributes.get('GEOUNIT', '') == 'France'
    ]
    if not france_geoms:
        raise RuntimeError(
            "No record with GEOUNIT='France' found in Natural Earth map_units."
            " Check the shapefile or update the filter criterion."
        )

    # Intersect with metropolitan bbox to strip any overseas slivers
    metro_bbox = shapely_box(_METRO_LON_MIN, _METRO_LAT_MIN, _METRO_LON_MAX, _METRO_LAT_MAX)
    metro_geom = unary_union(france_geoms).intersection(metro_bbox)

    _METRO_FRANCE_GEOM = metro_geom
    return _METRO_FRANCE_GEOM


def metropolitan_france_mask(da: xr.DataArray, verbose: bool = True) -> xr.DataArray:
    """Build a boolean mask for metropolitan France on the grid of *da*.

    Parameters
    ----------
    da : xr.DataArray
        DataArray with dims/coords 'lat' and 'lon' (S->N ascending,
        -180..180 ascending) as produced by normalize().
    verbose : bool
        If True, print diagnostics: number of True cells, lat/lon extent of
        True cells, and a DOM-leak check.

    Returns
    -------
    xr.DataArray
        Boolean DataArray with the same lat/lon coordinates as *da*.
        True = the cell centre is inside metropolitan France.
    """
    import shapely.vectorized as sv

    # ------------------------------------------------------------------
    # 1. Load and select the metropolitan France geometry (cached)
    # ------------------------------------------------------------------
    france_geom = metropolitan_france_geometry()

    # ------------------------------------------------------------------
    # 2. Build coordinate arrays and bbox pre-filter
    # ------------------------------------------------------------------
    lats = da.coords['lat'].values  # shape (nlat,)
    lons = da.coords['lon'].values  # shape (nlon,)

    # Metropolitan bbox mask — belt-and-suspenders
    lat_in_bbox = (lats >= _METRO_LAT_MIN) & (lats <= _METRO_LAT_MAX)  # (nlat,)
    lon_in_bbox = (lons >= _METRO_LON_MIN) & (lons <= _METRO_LON_MAX)  # (nlon,)

    # Candidate indices within the bbox
    lat_idx = np.where(lat_in_bbox)[0]
    lon_idx = np.where(lon_in_bbox)[0]

    # ------------------------------------------------------------------
    # 3. Rasterize: test polygon containment on candidate grid cells
    # ------------------------------------------------------------------
    mask_values = np.zeros((len(lats), len(lons)), dtype=bool)

    if lat_idx.size > 0 and lon_idx.size > 0:
        # Build meshgrid over the bbox-filtered candidate cells
        cand_lats = lats[lat_idx]       # (n_lat_cand,)
        cand_lons = lons[lon_idx]       # (n_lon_cand,)
        lon_grid, lat_grid = np.meshgrid(cand_lons, cand_lats)  # (n_lat_cand, n_lon_cand)

        # shapely.vectorized.contains: polygon.contains(x=lon, y=lat) pointwise
        inside = sv.contains(france_geom, lon_grid.ravel(), lat_grid.ravel())
        inside = inside.reshape(len(cand_lats), len(cand_lons))

        # Write results into the full mask grid (belt-and-suspenders already
        # guaranteed: we only fill cells within the metropolitan bbox)
        mask_values[np.ix_(lat_idx, lon_idx)] = inside

    # ------------------------------------------------------------------
    # 4. Belt-and-suspenders: force False outside the metropolitan bbox
    #    (redundant given step 2's pre-filter, but explicit and safe)
    # ------------------------------------------------------------------
    bbox_2d = np.outer(lat_in_bbox, lon_in_bbox)  # (nlat, nlon)
    mask_values = mask_values & bbox_2d

    # ------------------------------------------------------------------
    # 5. Wrap as DataArray
    # ------------------------------------------------------------------
    mask_da = xr.DataArray(
        mask_values,
        coords={'lat': da.coords['lat'], 'lon': da.coords['lon']},
        dims=['lat', 'lon'],
        attrs={'description': 'Metropolitan France boolean mask (GEOUNIT=France, 10m NE)'},
    )

    # ------------------------------------------------------------------
    # 6. Diagnostics
    # ------------------------------------------------------------------
    if verbose:
        n_true = int(mask_values.sum())
        if n_true > 0:
            true_lats = lats[mask_values.any(axis=1)]
            true_lons = lons[mask_values.any(axis=0)]
            lat_min_true = float(true_lats.min())
            lat_max_true = float(true_lats.max())
            lon_min_true = float(true_lons.min())
            lon_max_true = float(true_lons.max())
        else:
            lat_min_true = lat_max_true = lon_min_true = lon_max_true = float('nan')

        print(f"[france_mask] True cells : {n_true}")
        print(f"[france_mask] Lat extent : {lat_min_true:.2f} .. {lat_max_true:.2f}")
        print(f"[france_mask] Lon extent : {lon_min_true:.2f} .. {lon_max_true:.2f}")

        # DOM-leak checks
        dom_leak = False
        if n_true > 0:
            if lat_min_true < 20.0:
                print(f"[france_mask] WARNING: DOM-LEAK? lat_min={lat_min_true:.2f} < 20 "
                      f"(Guyane ~5N, Réunion ~-21S)")
                dom_leak = True
            if lon_min_true < -20.0:
                print(f"[france_mask] WARNING: DOM-LEAK? lon_min={lon_min_true:.2f} < -20 "
                      f"(Antilles ~-61E, Guyane ~-53E)")
                dom_leak = True
            if lon_max_true > 20.0:
                print(f"[france_mask] WARNING: DOM-LEAK? lon_max={lon_max_true:.2f} > 20 "
                      f"(Réunion ~55E, Mayotte ~45E)")
                dom_leak = True
            if not dom_leak:
                print("[france_mask] DOM-leak check: PASS (no overseas territory detected)")

    return mask_da
