"""
wapo_map.py — WaPo/Ben-Noll-style world map renderer for Hotter-Than-France.

Renders a clean world map (Robinson projection) highlighting ONLY the grid cells
that are STRICTLY hotter than France's hottest grid cell on a given day.

Two theme variants:
  'dark'  — #1C1C1E background, muted dark land, for the site's night mode.
  'light' — #FFFFFF background, muted light land, for day mode.

No title/axis text is emitted — the website provides all labels/stats overlaid.
Output: 1600x900 PNG (12.8 x 7.2 in @ 125 dpi).

No side effects on import.
"""
from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Theme palette
# ---------------------------------------------------------------------------
THEMES: dict[str, dict[str, str]] = {
    'dark': {
        'bg': '#1C1C1E',       # card background = out-of-globe area
        'ocean': '#23272F',    # globe interior; distinct from bg so the Robinson globe reads
        'land': '#3C3C40',
        'coast': '#5A5A5E',
        'outline': '#3A3A3F',  # faint Robinson globe boundary
    },
    'light': {
        'bg': '#FFFFFF',
        'ocean': '#E8EDF5',
        'land': '#D4D6DD',
        'coast': '#B6B6BD',
        'outline': '#C8CCD4',
    },
}


def render_map(date_str: str, theme: str, out_path: str | Path) -> dict:
    """Render a single WaPo-style world map and save it as PNG.

    Parameters
    ----------
    date_str : str
        Date in 'YYYY-MM-DD' format, e.g. '2026-06-22'. A matching GRIB file
        must already exist in <project_root>/data/.
    theme : str
        'dark' or 'light' — selects the colour palette from THEMES.
    out_path : str or Path
        Full path (including filename) where the PNG will be written.
        Parent directories are created automatically.

    Returns
    -------
    dict with keys:
        threshold_c  : float — France's max temperature (degC) used as threshold.
        width        : int   — image width in pixels.
        height       : int   — image height in pixels.
        hot_cell_pct : float — % of global 0.25° grid cells where daily-max > threshold
                               (UNWEIGHTED grid-cell fraction — a rough sanity proxy; the
                               cos-lat AREA-weighted figure is computed in Phase 2 calibration).
    """
    if theme not in THEMES:
        raise ValueError(f"Unknown theme {theme!r}. Use 'dark' or 'light'.")

    tc = THEMES[theme]
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. Load data and compute threshold
    # ------------------------------------------------------------------
    import sys as _sys
    _project_root = Path(__file__).resolve().parent.parent.parent
    if str(_project_root) not in _sys.path:
        _sys.path.insert(0, str(_project_root))

    from src.loaders.ecmwf_opendata import load_daily_tmax
    from src.core.france import metropolitan_france_mask
    from src.core.threshold import france_threshold

    da = load_daily_tmax(date_str)
    mask = metropolitan_france_mask(da, verbose=False)
    thr = france_threshold(da, mask, method='max')

    # Cells STRICTLY greater than France's max — France itself (== thr) → NaN
    hotter = da.where(da > thr)

    # ------------------------------------------------------------------
    # 2. Matplotlib + Cartopy setup
    # ------------------------------------------------------------------
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    import numpy as np
    from cartopy.util import add_cyclic_point

    fig = plt.figure(figsize=(12.8, 7.2), dpi=125)
    fig.patch.set_facecolor(tc['bg'])

    ax = fig.add_axes([0, 0.04, 1, 0.92], projection=ccrs.Robinson())
    ax.set_global()
    # ocean = globe interior, distinct from the figure bg so the Robinson globe reads as a globe
    ax.patch.set_facecolor(tc['ocean'])
    # faint outline around the Robinson globe for definition
    ax.spines['geo'].set_visible(True)
    ax.spines['geo'].set_edgecolor(tc['outline'])
    ax.spines['geo'].set_linewidth(0.8)

    # ------------------------------------------------------------------
    # 3. Base map: 110m land polygons (already cached — no SSL risk)
    #    Use NaturalEarthFeature directly; cartopy will find the cached shp.
    # ------------------------------------------------------------------
    land_feature = cfeature.NaturalEarthFeature(
        'physical', 'land', '110m',
        facecolor=tc['land'],
        edgecolor='none',
    )
    ax.add_feature(land_feature, zorder=1)

    # ------------------------------------------------------------------
    # 4. Coastlines — use the cached 110m coastline shapefile.
    #    ax.coastlines() calls natural_earth(…'coastline'…) which would
    #    trigger an SSL download if not cached.  We've pre-fetched it via
    #    certifi, so it should load from cache now.  As a belt-and-suspenders
    #    fallback we wrap it in a try/except and skip coastlines on failure
    #    rather than letting an SSL error abort the whole render.
    # ------------------------------------------------------------------
    try:
        ax.coastlines(linewidth=0.4, color=tc['coast'], zorder=2)
    except Exception as _exc:
        print(f"[render_map] coastlines() failed ({_exc!r}), "
              "drawing outline from land polygons instead.")
        land_outline = cfeature.NaturalEarthFeature(
            'physical', 'land', '110m',
            facecolor='none',
            edgecolor=tc['coast'],
        )
        ax.add_feature(land_outline, linewidth=0.4, zorder=2)

    # ------------------------------------------------------------------
    # 5. Hot overlay via pcolormesh
    #    add_cyclic_point prevents the antimeridian seam (white gap at 180°).
    # ------------------------------------------------------------------
    import numpy as np

    hot_vals = hotter.values          # shape (nlat, nlon), NaN where not hot
    lons_arr = da.lon.values          # (-180 .. 179.75)
    lats_arr = da.lat.values          # (-90 .. 90)

    data_cyclic, lon_cyclic = add_cyclic_point(hot_vals, coord=lons_arr)

    ax.pcolormesh(
        lon_cyclic,
        lats_arr,
        data_cyclic,
        transform=ccrs.PlateCarree(),
        cmap='YlOrRd',
        vmin=thr,
        vmax=52,
        shading='auto',
        zorder=3,
    )

    # ------------------------------------------------------------------
    # 6. Save
    # ------------------------------------------------------------------
    plt.savefig(str(out_path), facecolor=tc['bg'], dpi=125, bbox_inches=None)
    plt.close(fig)

    # ------------------------------------------------------------------
    # 7. Measure output
    # ------------------------------------------------------------------
    from PIL import Image
    import numpy as np

    img = Image.open(out_path).convert('RGBA')
    w, h = img.size

    # Sanity proxy: fraction of global 0.25° grid cells strictly hotter than France
    # (UNWEIGHTED — not the cos-lat area-weighted figure; that lives in Phase 2).
    n_hot_cells = int((~hotter.isnull()).sum())
    n_total_cells = hotter.size
    hot_cell_pct = 100.0 * n_hot_cells / n_total_cells

    return {
        'threshold_c': round(thr, 2),
        'width': w,
        'height': h,
        'hot_cell_pct': round(hot_cell_pct, 3),
    }
