"""
normalize.py — coordinate and unit normalization for ECMWF GRIB fields.

Converts a raw xr.DataArray from ECMWF conventions (latitude/longitude 0..360, Kelvin)
to analysis conventions (lat/lon -180..180 sorted ascending, degC).
"""
import xarray as xr


def normalize(da: xr.DataArray) -> xr.DataArray:
    """Standardize an ECMWF xr.DataArray for analysis.

    Steps:
    1. Rename 'latitude' -> 'lat' and 'longitude' -> 'lon' (if present under those names).
    2. Shift longitude from 0..360 to -180..180 and sort ascending.
    3. Sort latitude ascending (ECMWF files are typically N->S; we want S->N).
    4. Convert temperature from Kelvin to degC (subtract 273.15).
    5. Set attrs['units'] = 'degC'.

    Parameters
    ----------
    da : xr.DataArray
        Raw DataArray with dims/coords possibly named 'latitude'/'longitude',
        lon values in 0..360, temperature values in Kelvin.

    Returns
    -------
    xr.DataArray
        Standardized DataArray with dims lat/lon in -180..180 sorted ascending,
        values in degC.
    """
    # Step 1: rename latitude/longitude -> lat/lon (defensive — skip if already named)
    rename_map = {}
    if "latitude" in da.dims or "latitude" in da.coords:
        rename_map["latitude"] = "lat"
    if "longitude" in da.dims or "longitude" in da.coords:
        rename_map["longitude"] = "lon"
    if rename_map:
        da = da.rename(rename_map)

    # Step 2: shift lon 0..360 -> -180..180 and sort ascending
    da = da.assign_coords(lon=(((da.lon + 180) % 360) - 180))
    da = da.sortby("lon")

    # Step 3: sort lat ascending (S->N)
    da = da.sortby("lat")

    # Step 4: Kelvin -> degC
    da = da - 273.15

    # Step 5: annotate units
    da.attrs["units"] = "degC"

    return da
