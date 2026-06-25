"""
wapo_map.py — WaPo/Ben-Noll-style world map renderer for Hotter-Than-France.

Renders a clean world map (Robinson projection) highlighting:
  - Grid cells STRICTLY hotter than France's hottest grid cell (world_hot layer)
  - Metropolitan France itself, temperature-coloured on the SAME continuous ramp
  - A crosshair marker at France's hottest cell
  - Localized burnt-in title / date / stat text bands

Two theme variants:
  'dark'  — #1C1C1E background, muted dark land, for the site's night mode.
  'light' — #FFFFFF background, muted light land, for day mode.

Two lang variants: 'en' (English) / 'fr' (French).

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
        'france_outline': '#E8E8EA',  # high-contrast France polygon border
        'title': '#F5F5F7',
        'sub': '#A1A1A6',
    },
    'light': {
        'bg': '#FFFFFF',
        'ocean': '#E8EDF5',
        'land': '#D4D6DD',
        'coast': '#B6B6BD',
        'outline': '#C8CCD4',
        'france_outline': '#33343A',  # high-contrast France polygon border
        'title': '#1D1D1F',
        'sub': '#6E6E73',
    },
}

# ---------------------------------------------------------------------------
# Localised strings
# ---------------------------------------------------------------------------
_TITLES = {
    'en': 'Only places hotter than France',
    'fr': 'Seuls les endroits plus chauds que la France',
}

_CREDITS = {
    'en': 'ECMWF IFS forecast · independent reconstruction',
    'fr': 'Prévision IFS CEPMMT · reconstruction indépendante',
}

_DATE_LABELS: dict[tuple[str, str], str] = {
    ('2026-06-22', 'en'): 'Monday 22 June 2026',
    ('2026-06-22', 'fr'): 'lundi 22 juin 2026',
    ('2026-06-23', 'en'): 'Tuesday 23 June 2026',
    ('2026-06-23', 'fr'): 'mardi 23 juin 2026',
    ('2026-06-24', 'en'): 'Wednesday 24 June 2026',
    ('2026-06-24', 'fr'): 'mercredi 24 juin 2026',
}


def _stat_line(thr: float, pct: float, lang: str) -> str:
    """Build the stat string for a given threshold + fraction."""
    T = f'{thr:.1f}'
    P = f'{pct:.2f}'
    if lang == 'fr':
        T = T.replace('.', ',')
        P = P.replace('.', ',')
        return f'Maximum France {T} °C  ·  {P} % de la planète plus chaude'
    else:
        return f"France's hottest {T}°C  ·  {P}% of the planet was hotter"


def render_map(date_str: str, theme: str, lang: str, out_path: str | Path) -> dict:
    """Render a single WaPo-style world map and save it as PNG.

    Parameters
    ----------
    date_str : str
        Date in 'YYYY-MM-DD' format, e.g. '2026-06-22'. A matching GRIB file
        must already exist in <project_root>/data/.
    theme : str
        'dark' or 'light' — selects the colour palette from THEMES.
    lang : str
        'en' or 'fr' — selects the text language for the burnt-in labels.
    out_path : str or Path
        Full path (including filename) where the PNG will be written.
        Parent directories are created automatically.

    Returns
    -------
    dict with keys:
        threshold_c    : float — France's max temperature (degC) used as threshold.
        france_min_c   : float — France's minimum temperature within the mask (degC).
        crosshair_lat  : float — latitude of France's hottest grid cell.
        crosshair_lon  : float — longitude of France's hottest grid cell.
        width          : int   — image width in pixels.
        height         : int   — image height in pixels.
        hot_cell_pct   : float — % of global 0.25° grid cells where daily-max > threshold
                                 (UNWEIGHTED grid-cell fraction — rough sanity proxy).
    """
    if theme not in THEMES:
        raise ValueError(f"Unknown theme {theme!r}. Use 'dark' or 'light'.")
    if lang not in ('en', 'fr'):
        raise ValueError(f"Unknown lang {lang!r}. Use 'en' or 'fr'.")

    tc = THEMES[theme]
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. Load data and compute threshold / France temps
    # ------------------------------------------------------------------
    import sys as _sys
    _project_root = Path(__file__).resolve().parent.parent.parent
    if str(_project_root) not in _sys.path:
        _sys.path.insert(0, str(_project_root))

    from src.loaders.ecmwf_opendata import load_daily_tmax
    from src.core.france import metropolitan_france_mask, metropolitan_france_geometry
    from src.core.threshold import france_threshold, planet_fraction_hotter

    da = load_daily_tmax(date_str)
    mask = metropolitan_france_mask(da, verbose=False)
    thr = france_threshold(da, mask, method='max')

    france_temps = da.where(mask)          # NaN outside France
    france_min = float(france_temps.min())

    # World cells STRICTLY hotter than France
    world_hot = da.where(da > thr)

    # Continuous colour scale: France occupies [base..thr], world-hotter [thr..52]
    base = max(25.0, float(__import__('numpy').floor(france_min)))

    # Planet fraction (cos-lat weighted)
    pct = planet_fraction_hotter(da, thr, domain='all')

    # ------------------------------------------------------------------
    # 2. Find France's hottest cell for crosshair
    # ------------------------------------------------------------------
    import numpy as np

    am = france_temps.argmax(dim=['lat', 'lon'])
    crosshair_lat = float(da.lat[am['lat']])
    crosshair_lon = float(da.lon[am['lon']])

    # ------------------------------------------------------------------
    # 3. Matplotlib + Cartopy setup
    # ------------------------------------------------------------------
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    import matplotlib.patheffects as pe
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    from cartopy.util import add_cyclic_point

    fig = plt.figure(figsize=(12.8, 7.2), dpi=125)
    fig.patch.set_facecolor(tc['bg'])

    # Shrink map axes to leave top + bottom bands for text
    ax = fig.add_axes([0, 0.10, 1, 0.78], projection=ccrs.Robinson())
    ax.set_global()
    ax.patch.set_facecolor(tc['ocean'])
    ax.spines['geo'].set_visible(True)
    ax.spines['geo'].set_edgecolor(tc['outline'])
    ax.spines['geo'].set_linewidth(0.8)

    # ------------------------------------------------------------------
    # 4. Base map: 110m land polygons
    # ------------------------------------------------------------------
    land_feature = cfeature.NaturalEarthFeature(
        'physical', 'land', '110m',
        facecolor=tc['land'],
        edgecolor='none',
    )
    ax.add_feature(land_feature, zorder=1)

    # ------------------------------------------------------------------
    # 5. Coastlines
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
    # 6. Continuous colour norm shared by France fill + world-hot overlay
    # ------------------------------------------------------------------
    norm = mcolors.Normalize(vmin=base, vmax=52)
    cmap_name = 'YlOrRd'

    # --- World-hot overlay (add_cyclic_point prevents antimeridian seam) ---
    lons_arr = da.lon.values
    lats_arr = da.lat.values

    hot_vals = world_hot.values
    data_cyclic, lon_cyclic = add_cyclic_point(hot_vals, coord=lons_arr)

    ax.pcolormesh(
        lon_cyclic,
        lats_arr,
        data_cyclic,
        transform=ccrs.PlateCarree(),
        cmap=cmap_name,
        norm=norm,
        shading='auto',
        zorder=3,
    )

    # --- France temperature fill ---
    fr_vals = france_temps.values
    fr_cyclic, _ = add_cyclic_point(fr_vals, coord=lons_arr)

    ax.pcolormesh(
        lon_cyclic,
        lats_arr,
        fr_cyclic,
        transform=ccrs.PlateCarree(),
        cmap=cmap_name,
        norm=norm,
        shading='auto',
        zorder=3,
    )

    # ------------------------------------------------------------------
    # 7. France outline polygon
    # ------------------------------------------------------------------
    france_geom = metropolitan_france_geometry()
    ax.add_geometries(
        [france_geom],
        crs=ccrs.PlateCarree(),
        facecolor='none',
        edgecolor=tc['france_outline'],
        linewidth=0.9,
        zorder=5,
    )

    # ------------------------------------------------------------------
    # 8. Crosshair at France's hottest cell
    #    White core + dark halo so it's readable on warm fill in both themes
    # ------------------------------------------------------------------
    halo_stroke = pe.withStroke(linewidth=3.0, foreground='#111111')

    ax.plot(
        crosshair_lon, crosshair_lat,
        '+',
        color='white',
        markersize=15,
        markeredgewidth=1.8,
        transform=ccrs.PlateCarree(),
        zorder=6,
        path_effects=[halo_stroke],
    )
    ax.plot(
        crosshair_lon, crosshair_lat,
        'o',
        color='none',
        markersize=11,
        markeredgecolor='white',
        markeredgewidth=1.4,
        markerfacecolor='none',
        transform=ccrs.PlateCarree(),
        zorder=6,
        path_effects=[halo_stroke],
    )

    # ------------------------------------------------------------------
    # 9. Burnt-in text labels
    # ------------------------------------------------------------------
    title_text = _TITLES[lang]
    date_label = _DATE_LABELS.get((date_str, lang), date_str)
    stat_text = _stat_line(thr, pct, lang)
    credit_text = _CREDITS[lang]

    # Title — top-left, bold ~17pt
    fig.text(
        0.025, 0.95,
        title_text,
        fontsize=17,
        fontweight='bold',
        color=tc['title'],
        ha='left',
        va='top',
    )

    # Date — just below title, ~11pt, sub colour
    fig.text(
        0.025, 0.905,
        date_label,
        fontsize=11,
        color=tc['sub'],
        ha='left',
        va='top',
    )

    # Stat — bottom-left, ~11pt
    fig.text(
        0.025, 0.055,
        stat_text,
        fontsize=11,
        color=tc['title'],
        ha='left',
        va='bottom',
    )

    # Credit — bottom-right, ~9pt, sub colour
    fig.text(
        0.975, 0.045,
        credit_text,
        fontsize=9,
        color=tc['sub'],
        ha='right',
        va='bottom',
    )

    # ------------------------------------------------------------------
    # 10. Save
    # ------------------------------------------------------------------
    plt.savefig(str(out_path), facecolor=tc['bg'], dpi=125, bbox_inches=None)
    plt.close(fig)

    # ------------------------------------------------------------------
    # 11. Measure output
    # ------------------------------------------------------------------
    from PIL import Image

    img = Image.open(out_path).convert('RGBA')
    w, h = img.size

    # Sanity proxy: fraction of global 0.25° grid cells strictly hotter than France
    # (UNWEIGHTED — not the cos-lat area-weighted figure; that lives in Phase 2).
    n_hot_cells = int((~world_hot.isnull()).sum())
    n_total_cells = world_hot.size
    hot_cell_pct = 100.0 * n_hot_cells / n_total_cells

    return {
        'threshold_c': round(thr, 2),
        'france_min_c': round(france_min, 2),
        'crosshair_lat': round(crosshair_lat, 4),
        'crosshair_lon': round(crosshair_lon, 4),
        'width': w,
        'height': h,
        'hot_cell_pct': round(hot_cell_pct, 3),
    }
