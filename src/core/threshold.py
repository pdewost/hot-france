"""
threshold.py — France temperature threshold and global fraction-hotter computation.

Two public functions:
  france_threshold(da, mask, method='max', q=0.95) -> float
    Returns the threshold temperature (degC) for France — either the grid max
    (method='max', faithful primary) or a high percentile (method='percentile').

  planet_fraction_hotter(da, threshold, domain='all', land_mask=None) -> float
    Returns the cos-latitude area-weighted fraction (%) of the planet where
    daily-max 2m temperature is STRICTLY greater than *threshold*.

Area weighting rationale
------------------------
Each grid cell subtends a solid angle proportional to cos(lat). At the poles
cos(lat) → 0 so polar cells are near-zero weight; at the equator cos(lat) = 1.
Using cos-latitude weights is the standard first-order approximation for equal
area on a sphere when cells have constant Δlat × Δlon spacing (as in IFS 0.25°).
"""
from __future__ import annotations

import numpy as np
import xarray as xr


def france_threshold(
    da: xr.DataArray,
    mask: xr.DataArray,
    method: str = 'max',
    q: float = 0.95,
) -> float:
    """Compute France's temperature threshold from the masked daily-max field.

    Parameters
    ----------
    da : xr.DataArray
        Daily-max 2m temperature in degC, dims lat/lon.
    mask : xr.DataArray
        Boolean mask for metropolitan France (same lat/lon coords as *da*).
    method : str
        'max'        — return the single hottest grid cell within France.
        'percentile' — return the *q*-quantile of France grid cells.
    q : float
        Quantile level for method='percentile' (default 0.95).

    Returns
    -------
    float
        Temperature threshold in degC.
    """
    masked = da.where(mask)  # NaN outside France
    if method == 'max':
        return float(masked.max())
    elif method == 'percentile':
        # xarray quantile: skip NaN by default (skipna=True)
        return float(masked.quantile(q))
    else:
        raise ValueError(f"Unknown method {method!r}. Use 'max' or 'percentile'.")


def planet_fraction_hotter(
    da: xr.DataArray,
    threshold: float,
    domain: str = 'all',
    land_mask: xr.DataArray | None = None,
) -> float:
    """Cos-latitude area-weighted fraction of the planet hotter than *threshold*.

    Parameters
    ----------
    da : xr.DataArray
        Daily-max 2m temperature in degC, dims lat/lon.
    threshold : float
        Temperature threshold in degC. Cells STRICTLY > threshold are counted.
    domain : str
        'all'  — all grid cells (ocean + land + ice).
        'land' — only land cells; requires *land_mask*. Returns -1.0 if
                 *land_mask* is None (not computed).
    land_mask : xr.DataArray or None
        Boolean DataArray (True = land) on the same lat/lon grid as *da*.
        Only used when domain='land'.

    Returns
    -------
    float
        Area-weighted percentage of the domain with daily-max > threshold.
        Returns -1.0 if domain='land' and land_mask is None.
    """
    if domain == 'land' and land_mask is None:
        return -1.0

    # Cos-latitude weights: shape (nlat,) broadcast over (nlat, nlon)
    lat_rad = np.deg2rad(da.coords['lat'].values)
    cos_lat = np.cos(lat_rad)                   # (nlat,)
    # Broadcast to (nlat, nlon) matching da's shape
    weights = xr.DataArray(
        np.broadcast_to(cos_lat[:, np.newaxis], da.shape),
        coords=da.coords,
        dims=da.dims,
    )

    # Domain mask
    if domain == 'land':
        domain_mask = land_mask.fillna(False).astype(bool)
        weights = weights.where(domain_mask, other=0.0)
    # else domain='all' — keep all weights

    # Hotter-than mask: STRICTLY greater
    hotter = da > threshold  # bool DataArray

    # Area-weighted fraction
    weight_hotter = float((weights * hotter).sum())
    weight_total = float(weights.sum())

    if weight_total == 0.0:
        return float('nan')

    return 100.0 * weight_hotter / weight_total


def build_land_mask(da: xr.DataArray) -> xr.DataArray | None:
    """Attempt to build a land mask from Natural Earth 'physical/land' via cartopy.

    This is optional and may be slow (~10-30 s for global 0.25° rasterization).
    Returns None on any error (caller should pass land_mask=None to
    planet_fraction_hotter, which returns -1.0).

    Parameters
    ----------
    da : xr.DataArray
        Reference DataArray (lat/lon coords only used for grid shape).

    Returns
    -------
    xr.DataArray or None
        Boolean land mask, or None if unavailable.
    """
    try:
        import cartopy.io.shapereader as shpreader
        import shapely.vectorized as sv
        from shapely.ops import unary_union

        shpfile = shpreader.natural_earth(
            resolution='110m', category='physical', name='land'
        )
        reader = shpreader.Reader(shpfile)
        land_geom = unary_union([r.geometry for r in reader.records()])

        lats = da.coords['lat'].values
        lons = da.coords['lon'].values
        lon_grid, lat_grid = np.meshgrid(lons, lats)

        is_land = sv.contains(land_geom, lon_grid.ravel(), lat_grid.ravel())
        is_land = is_land.reshape(len(lats), len(lons))

        return xr.DataArray(
            is_land,
            coords={'lat': da.coords['lat'], 'lon': da.coords['lon']},
            dims=['lat', 'lon'],
            attrs={'description': 'Natural Earth 110m land mask'},
        )
    except Exception as exc:
        print(f"[land_mask] Could not build land mask: {exc}")
        return None
