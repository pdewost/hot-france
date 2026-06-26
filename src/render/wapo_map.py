"""
wapo_map.py — WaPo/Ben-Noll-style world map renderer (generic reference country).

Renders a Robinson projection world map highlighting:
  - Grid cells STRICTLY hotter than the reference country's hottest grid cell
  - The reference country itself, temperature-coloured on the same continuous ramp
  - A crosshair marker at the hottest cell
  - Localized burnt-in title / date / stat text bands

Two theme variants: 'dark' / 'light'.
Two lang variants:  'en' / 'fr'.
Output: 1600×900 PNG.

No side effects on import.
"""
from __future__ import annotations

from datetime import date as _date
from pathlib import Path

# ---------------------------------------------------------------------------
# Theme palette
# ---------------------------------------------------------------------------
THEMES: dict[str, dict[str, str]] = {
    'dark': {
        'bg': '#1C1C1E',
        'ocean': '#23272F',
        'land': '#3C3C40',
        'coast': '#5A5A5E',
        'outline': '#3A3A3F',
        'ref_outline': '#E8E8EA',
        'title': '#F5F5F7',
        'sub': '#A1A1A6',
    },
    'light': {
        'bg': '#FFFFFF',
        'ocean': '#E8EDF5',
        'land': '#D4D6DD',
        'coast': '#B6B6BD',
        'outline': '#C8CCD4',
        'ref_outline': '#33343A',
        'title': '#1D1D1F',
        'sub': '#6E6E73',
    },
}

# ---------------------------------------------------------------------------
# Localisation helpers
# ---------------------------------------------------------------------------
_DAYS_EN   = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
_MONTHS_EN = ['January','February','March','April','May','June','July',
               'August','September','October','November','December']
_DAYS_FR   = ['lundi','mardi','mercredi','jeudi','vendredi','samedi','dimanche']
_MONTHS_FR = ['janvier','février','mars','avril','mai','juin','juillet',
               'août','septembre','octobre','novembre','décembre']

_CREDITS = {
    'en': 'ECMWF IFS forecast · independent reconstruction',
    'fr': 'Prévision IFS CEPMMT · reconstruction indépendante',
}


def _date_label(date_str: str, lang: str) -> str:
    d = _date.fromisoformat(date_str)
    if lang == 'fr':
        return f"{_DAYS_FR[d.weekday()]} {d.day} {_MONTHS_FR[d.month - 1]} {d.year}"
    return f"{_DAYS_EN[d.weekday()]} {d.day} {_MONTHS_EN[d.month - 1]} {d.year}"


def _title_line(ref_label_en: str, ref_label_fr: str, lang: str) -> str:
    if lang == 'fr':
        return f'Les seuls endroits plus chauds que {ref_label_fr}'
    return f'Only places hotter than {ref_label_en}'


def _stat_line(thr: float, pct: float, lang: str,
               ref_label_en: str, ref_label_fr: str) -> str:
    T = f'{thr:.1f}'
    P = f'{pct:.2f}'
    if lang == 'fr':
        T = T.replace('.', ',')
        P = P.replace('.', ',')
        return f'Maximum {ref_label_fr} {T} °C  ·  {P} % de la planète plus chaude'
    return f"{ref_label_en}'s hottest {T}°C  ·  {P}% of the planet was hotter"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_map(
    date_str: str,
    theme: str,
    lang: str,
    out_path: str | Path,
    *,
    ref_iso3: str = 'FRA',
    ref_bbox: tuple | None = None,
    ref_label_en: str = 'France',
    ref_label_fr: str = 'la France',
) -> dict:
    """Render a single WaPo-style world map and save it as PNG.

    Parameters
    ----------
    date_str : str
        Date 'YYYY-MM-DD'. A GRIB cache file must exist in <project_root>/data/.
    theme : str
        'dark' or 'light'.
    lang : str
        'en' or 'fr'.
    out_path : str or Path
        Full PNG output path (parent dirs created automatically).
    ref_iso3 : str
        ISO 3166-1 alpha-3 code for the reference country (default 'FRA').
        'FRA' triggers the metropolitan_france_* helpers (overseas-safe).
        Any other code uses the generic country_mask / country_geometry.
    ref_bbox : tuple or None
        (lon_min, lat_min, lon_max, lat_max) clip applied to the reference
        country geometry — useful to exclude island territories.
    ref_label_en : str
        English display name for the reference country (e.g. 'Morocco').
    ref_label_fr : str
        French display name including article (e.g. 'le Maroc').

    Returns
    -------
    dict with keys:
        threshold_c   : float — ref country's max temperature (°C).
        ref_min_c     : float — ref country's minimum temperature (°C).
        crosshair_lat : float — latitude of the hottest grid cell.
        crosshair_lon : float — longitude of the hottest grid cell.
        width         : int   — image width in pixels.
        height        : int   — image height in pixels.
        hot_cell_pct  : float — unweighted grid-cell fraction where T > threshold
                                (sanity proxy; not the cos-lat area-weighted figure).
    """
    if theme not in THEMES:
        raise ValueError(f"Unknown theme {theme!r}. Use 'dark' or 'light'.")
    if lang not in ('en', 'fr'):
        raise ValueError(f"Unknown lang {lang!r}. Use 'en' or 'fr'.")

    tc = THEMES[theme]
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 0. Imports
    # ------------------------------------------------------------------
    import sys as _sys
    _project_root = Path(__file__).resolve().parent.parent.parent
    if str(_project_root) not in _sys.path:
        _sys.path.insert(0, str(_project_root))

    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    import matplotlib.patheffects as pe
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    from cartopy.util import add_cyclic_point

    from src.loaders.ecmwf_opendata import load_daily_tmax
    from src.core.threshold import france_threshold, planet_fraction_hotter

    # ------------------------------------------------------------------
    # 1. Load grid
    # ------------------------------------------------------------------
    da = load_daily_tmax(date_str)

    # ------------------------------------------------------------------
    # 2. Build reference-country mask + geometry
    # ------------------------------------------------------------------
    if ref_iso3.upper() == 'FRA':
        from src.core.france import metropolitan_france_mask, metropolitan_france_geometry
        mask   = metropolitan_france_mask(da, verbose=False)
        ref_geom = metropolitan_france_geometry()
    else:
        from src.core.country import country_mask, country_geometry
        mask   = country_mask(da, ref_iso3.upper(), ref_bbox)
        ref_geom = country_geometry(ref_iso3.upper(), ref_bbox)

    # ------------------------------------------------------------------
    # 3. Compute stats
    # ------------------------------------------------------------------
    thr = france_threshold(da, mask, method='max')   # works for any mask

    ref_temps = da.where(mask)                         # NaN outside ref country
    ref_min   = float(ref_temps.min())
    world_hot = da.where(da > thr)

    base = max(25.0, float(np.floor(ref_min)))
    pct  = planet_fraction_hotter(da, thr, domain='all')

    # Crosshair — hottest cell inside ref country
    am = ref_temps.argmax(dim=['lat', 'lon'])
    crosshair_lat = float(da.lat[am['lat']])
    crosshair_lon = float(da.lon[am['lon']])

    # ------------------------------------------------------------------
    # 4. Figure + axes
    # ------------------------------------------------------------------
    fig = plt.figure(figsize=(12.8, 7.2), dpi=125)
    fig.patch.set_facecolor(tc['bg'])

    ax = fig.add_axes([0, 0.10, 1, 0.78], projection=ccrs.Robinson())
    ax.set_global()
    ax.patch.set_facecolor(tc['ocean'])
    ax.spines['geo'].set_visible(True)
    ax.spines['geo'].set_edgecolor(tc['outline'])
    ax.spines['geo'].set_linewidth(0.8)

    # Base land + coastlines
    land_feature = cfeature.NaturalEarthFeature(
        'physical', 'land', '110m', facecolor=tc['land'], edgecolor='none')
    ax.add_feature(land_feature, zorder=1)
    try:
        ax.coastlines(linewidth=0.4, color=tc['coast'], zorder=2)
    except Exception:
        land_outline = cfeature.NaturalEarthFeature(
            'physical', 'land', '110m', facecolor='none', edgecolor=tc['coast'])
        ax.add_feature(land_outline, linewidth=0.4, zorder=2)

    # ------------------------------------------------------------------
    # 5. Temperature layers (shared colour norm)
    # ------------------------------------------------------------------
    norm = mcolors.Normalize(vmin=base, vmax=52)
    cmap_name = 'YlOrRd'

    lons_arr = da.lon.values
    lats_arr = da.lat.values

    # World-hot overlay
    hot_vals = world_hot.values
    data_cyclic, lon_cyclic = add_cyclic_point(hot_vals, coord=lons_arr)
    ax.pcolormesh(lon_cyclic, lats_arr, data_cyclic,
                  transform=ccrs.PlateCarree(), cmap=cmap_name, norm=norm,
                  shading='auto', zorder=3)

    # Reference-country temperature fill
    ref_cyclic, _ = add_cyclic_point(ref_temps.values, coord=lons_arr)
    ax.pcolormesh(lon_cyclic, lats_arr, ref_cyclic,
                  transform=ccrs.PlateCarree(), cmap=cmap_name, norm=norm,
                  shading='auto', zorder=3)

    # ------------------------------------------------------------------
    # 6. Reference-country outline
    # ------------------------------------------------------------------
    if ref_geom is not None and not ref_geom.is_empty:
        ax.add_geometries([ref_geom], crs=ccrs.PlateCarree(),
                          facecolor='none', edgecolor=tc['ref_outline'],
                          linewidth=0.9, zorder=5)

    # ------------------------------------------------------------------
    # 7. Crosshair
    # ------------------------------------------------------------------
    halo = pe.withStroke(linewidth=3.0, foreground='#111111')
    ax.plot(crosshair_lon, crosshair_lat, '+', color='white',
            markersize=15, markeredgewidth=1.8, transform=ccrs.PlateCarree(),
            zorder=6, path_effects=[halo])
    ax.plot(crosshair_lon, crosshair_lat, 'o', color='none',
            markersize=11, markeredgecolor='white', markeredgewidth=1.4,
            markerfacecolor='none', transform=ccrs.PlateCarree(),
            zorder=6, path_effects=[halo])

    # ------------------------------------------------------------------
    # 7b. France secondary overlay (when France is not the reference)
    #     Shows France at its actual temperature colour — no crosshair, dashed outline.
    # ------------------------------------------------------------------
    if ref_iso3.upper() != 'FRA':
        from src.core.france import metropolitan_france_mask, metropolitan_france_geometry
        fra_mask  = metropolitan_france_mask(da, verbose=False)
        fra_temps = da.where(fra_mask)
        fra_cyclic, _ = add_cyclic_point(fra_temps.values, coord=lons_arr)
        ax.pcolormesh(lon_cyclic, lats_arr, fra_cyclic,
                      transform=ccrs.PlateCarree(), cmap=cmap_name, norm=norm,
                      shading='auto', zorder=3)
        fra_geom = metropolitan_france_geometry()
        if fra_geom is not None and not fra_geom.is_empty:
            fra_outline = '#F5A623' if theme == 'dark' else '#C07800'
            ax.add_geometries([fra_geom], crs=ccrs.PlateCarree(),
                              facecolor='none', edgecolor=fra_outline,
                              linewidth=0.8, linestyle=(0, (4, 3)), zorder=5)

    # ------------------------------------------------------------------
    # 8. Burnt-in text
    # ------------------------------------------------------------------
    fig.text(0.025, 0.95,
             _title_line(ref_label_en, ref_label_fr, lang),
             fontsize=17, fontweight='bold', color=tc['title'], ha='left', va='top')

    fig.text(0.025, 0.905,
             _date_label(date_str, lang),
             fontsize=11, color=tc['sub'], ha='left', va='top')

    fig.text(0.025, 0.055,
             _stat_line(thr, pct, lang, ref_label_en, ref_label_fr),
             fontsize=11, color=tc['title'], ha='left', va='bottom')

    fig.text(0.975, 0.045,
             _CREDITS[lang],
             fontsize=9, color=tc['sub'], ha='right', va='bottom')

    # ------------------------------------------------------------------
    # 9. Save + measure
    # ------------------------------------------------------------------
    plt.savefig(str(out_path), facecolor=tc['bg'], dpi=125, bbox_inches=None)
    plt.close(fig)

    from PIL import Image
    img = Image.open(out_path).convert('RGBA')
    w, h = img.size

    n_hot_cells   = int((~world_hot.isnull()).sum())
    hot_cell_pct  = 100.0 * n_hot_cells / world_hot.size

    return {
        'threshold_c':   round(thr, 2),
        'ref_min_c':     round(ref_min, 2),
        'crosshair_lat': round(crosshair_lat, 4),
        'crosshair_lon': round(crosshair_lon, 4),
        'width':         w,
        'height':        h,
        'hot_cell_pct':  round(hot_cell_pct, 3),
    }
