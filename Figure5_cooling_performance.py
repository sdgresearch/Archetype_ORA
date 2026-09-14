"""Figure 5: Frozen cooling outputs: 800-m accessible cooling for maps/associations; 400-m green exposure and service for nonlinear panels. All saved CIs reused.

Run: python Figure5_cooling_performance.py
Optional: --output-dir my_figures --csv Figure5_cooling_performance.csv
Outputs: 600-dpi PNG/TIFF and vector PDF/SVG; existing outputs are not overwritten.
Requires Python 3.12+ and: numpy pandas scipy matplotlib Pillow statsmodels
geopandas rasterio scikit-learn threadpoolctl shapely pyproj pyogrio.
Install once: python -m pip install numpy pandas scipy matplotlib Pillow statsmodels geopandas rasterio scikit-learn threadpoolctl shapely pyproj pyogrio

This standalone file includes the original plotting functions in named renderer
sections below. They load in memory: no separate helper scripts are needed.
Only the matching CSV is read. Temporary tables/map arrays are reconstructed
for the established readers and removed automatically after rendering.
No original workspace path, raw data download or model rerun is required.

CSV schema: _dataset identifies a processed table; _kind='header' stores its
ordered columns in _payload; _kind='row' stores ordinary named data columns.
Geography and rasters use explicit JSON coordinates/numeric row arrays in
_payload, with CRS/transform metadata. No encoded PNG/PDF images are used.
Missing values and postal-code strings are preserved. The same CSV stores
figure provenance/definition metadata. Figure 1 is illustrative, not empirical.
This is a plotting package, not the full upstream analysis or raw-data release.
Redistribution licenses must be confirmed by the authors before public deposit.
"""

FIGURE_NUMBER = 5
FIGURE_NAME = 'Figure5_cooling_performance'
OUTPUT_RELATIVE_STEM = 'Figure2_Archetype_cooling_performance'

import argparse
import csv
import importlib.abc
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def unpack_csv(csv_path, root):
    """Reconstitute processed tables/map arrays in an isolated temporary folder.

    Original readers are retained to preserve numerical parsing and rendering.
    No external datasets, network connections or local helper scripts are used.
    """
    csv.field_size_limit(64 * 1024 * 1024)
    handles, writers, rasters, geographies, paths = {}, {}, {}, {}, {}
    try:
        with csv_path.open(encoding='utf-8-sig', newline='') as handle:
            for row in csv.DictReader(handle):
                name, kind = row['_dataset'], row['_kind']
                if kind == 'metadata':
                    continue
                if name not in paths:
                    dest = (root / name).resolve()
                    if not dest.is_relative_to(root.resolve()):
                        raise ValueError('CSV contains an invalid dataset path')
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    paths[name] = dest
                dest = paths[name]
                if kind == 'header':
                    columns = json.loads(row['_payload'])
                    handles[name] = dest.open('w', encoding='utf-8', newline='')
                    writers[name] = (csv.writer(handles[name], lineterminator='\n'), columns)
                    writers[name][0].writerow(columns)
                elif kind == 'row':
                    writer, columns = writers[name]
                    writer.writerow([row[c] for c in columns])
                elif kind == 'json':
                    dest.write_text(json.dumps(json.loads(row['_payload']), ensure_ascii=False), encoding='utf-8')
                elif kind == 'raster_header':
                    profile = json.loads(row['_payload'])
                    rasters[name] = (profile, np.empty((profile['count'], profile['height'], profile['width']), dtype=profile['dtype']))
                elif kind == 'raster_row':
                    band, r = map(int, row['_index'].split(':'))
                    rasters[name][1][band, r] = json.loads(row['_payload'])
                elif kind == 'geojson_header':
                    geographies[name] = {**json.loads(row['_payload']), 'features': []}
                elif kind == 'geojson_feature':
                    geographies[name]['features'].append(json.loads(row['_payload']))
                else:
                    raise ValueError(f'Unknown CSV record kind: {kind}')
    finally:
        for f in handles.values():
            f.close()
    for name, (profile, values) in rasters.items():
        import rasterio
        from affine import Affine
        profile['transform'] = Affine(*profile['transform'])
        with rasterio.open(root / name, 'w', **profile) as dst:
            dst.write(values)
    for name, geography in geographies.items():
        (root / name).write_text(json.dumps(geography), encoding='utf-8')


class InMemoryRenderers(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Load renderer sections embedded below without any helper .py files."""
    def __init__(self, root):
        self.root = root

    def find_spec(self, fullname, path=None, target=None):
        if fullname in RENDERERS:
            return importlib.util.spec_from_loader(fullname, self)
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        module.__file__ = str(self.root / 'Figure/code' / (module.__name__ + '.py'))
        exec(compile(RENDERERS[module.__name__], module.__file__, 'exec'), module.__dict__)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--csv', type=Path, default=Path(__file__).with_suffix('.csv'))
    parser.add_argument('--output-dir', type=Path, default=Path(__file__).resolve().parent / 'rendered')
    args = parser.parse_args()
    csv_path, output = args.csv.resolve(), args.output_dir.resolve()
    if not csv_path.is_file():
        parser.error(f'Matching CSV not found: {csv_path}')
    output.mkdir(parents=True, exist_ok=True)
    for suffix in ('.png', '.pdf', '.svg', '.tiff'):
        if (output / (FIGURE_NAME + suffix)).exists():
            parser.error(f'Output already exists. Choose a new --output-dir: {output}')
    with tempfile.TemporaryDirectory(prefix=f'figure{FIGURE_NUMBER}_') as temporary:
        root = Path(temporary).resolve()
        unpack_csv(csv_path, root)
        (root / 'Figure/code').mkdir(parents=True, exist_ok=True)
        (root / 'Figure/output/source_data').mkdir(parents=True, exist_ok=True)
        loader = InMemoryRenderers(root)
        sys.meta_path.insert(0, loader)
        # Prevent package imports from leaving extra .pyc files beside the scripts.
        sys.dont_write_bytecode = True
        try:
            entry = ENTRY.replace('HERE = Path(__file__).resolve().parent', 'HERE = RUNTIME_ROOT / "Figure"')
            exec(compile(entry, str(root / 'Figure/entry.py'), 'exec'),
                 {'__name__': '__main__', '__file__': str(root / 'Figure/entry.py'), 'RUNTIME_ROOT': root})
            stem = root / 'Figure/output' / OUTPUT_RELATIVE_STEM
            for suffix in ('.png', '.pdf', '.svg', '.tiff'):
                source = stem.with_suffix(suffix)
                if not source.is_file():
                    raise RuntimeError(f'Renderer did not produce {source.name}')
                shutil.copyfile(source, output / (FIGURE_NAME + suffix))
        finally:
            sys.meta_path.remove(loader)
            plt.close('all')
    print(f'Figure {FIGURE_NUMBER}: rendered from {csv_path.name}')
    print(f'PNG (600 dpi), PDF, SVG and TIFF: {output / FIGURE_NAME}')


# Preserved plotting source sections. Edit styles in the relevant section.
RENDERERS = {}

# ----- plot_accessible_cooling_trial_figure2 -----
RENDERERS['plot_accessible_cooling_trial_figure2'] = '''"""Create a comparison-only Figure 2 using accessible cooling potential.

The existing Figure 2 is not modified.  The trial replaces straight-line
proximity in panels b/d with a proximity-weighted cooling-magnitude metric:

    nearest cooled-footprint source cooling × 2 ** (-distance / 400 m)

Larger positive values therefore indicate stronger and/or nearer modelled
cooling service.  The quantity is an ecological accessibility potential, not
experienced indoor cooling or a causal intervention effect.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from matplotlib.lines import Line2D
from scipy.spatial import cKDTree

from plot_residential_green_cooling_paper_figures import (
    ANALYSIS,
    ARCH_COLORS,
    BIVARIATE_COLORS,
    add_bivariate_key,
    add_panel_label,
    add_primary_archetype_labels,
    add_scale_bar,
    bivariate_cooling_hdb,
    draw_archetype_split_map,
    hdb_density_surface,
    map_background,
    planning_boundary,
    read_raster,
    smooth_masked,
    strip_axes,
)

# Restate the publication settings locally so the trial script is independently
# auditable even though it imports the established Figure 2 visual system.
mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
    }
)


TRIAL = ANALYSIS / "accessible_cooling_trial"
OUT = ANALYSIS / "figures" / "trials"
SOURCE = OUT / "source_data"
OUT.mkdir(parents=True, exist_ok=True)
SOURCE.mkdir(parents=True, exist_ok=True)
STEM = "Figure2_Cooling_efficacy_and_accessible_cooling_TRIAL"


def bivariate_accessible_hdb(accessible, hdb_density):
    """Classify accessible cooling potential and HDB dwelling density.

    Accessible cooling classes are <0.05, 0.05 to <0.15, and >=0.15 °C.
    HDB density classes match the retained Figure 2a thresholds.
    """
    valid = np.isfinite(accessible)
    access_class = np.zeros(accessible.shape, dtype=np.int8)
    access_class[(accessible >= 0.05) & (accessible < 0.15)] = 1
    access_class[accessible >= 0.15] = 2
    density_class = np.zeros(hdb_density.shape, dtype=np.int8)
    density_class[(hdb_density >= 1000) & (hdb_density < 3000)] = 1
    density_class[hdb_density >= 3000] = 2
    rgba = np.ones((*accessible.shape, 4), dtype=float)
    for ai in range(3):
        for di in range(3):
            mask = valid & (access_class == ai) & (density_class == di)
            rgba[mask, :3] = mpl.colors.to_rgb(BIVARIATE_COLORS[ai, di])
    rgba[~valid, 3] = 0.0
    return rgba, access_class, density_class


def postcode_metric_surface(postcode_metric: pd.DataFrame):
    """Nearest-postcode interpolation on the existing residential support."""
    support, extent, crs, transform = read_raster(
        "cooling_service_access_distance_surface_100m.tif"
    )
    valid = np.isfinite(support)
    rows, cols = np.where(valid)
    xs, ys = rasterio.transform.xy(transform, rows, cols, offset="center")
    query = np.column_stack([np.asarray(xs), np.asarray(ys)])
    tree = cKDTree(postcode_metric[["x_m", "y_m"]].to_numpy(float))
    _, nearest = tree.query(query, k=1)
    values = postcode_metric["accessible_cooling_potential_c"].to_numpy(float)[nearest]
    surface = np.full(support.shape, np.nan, dtype=float)
    surface[rows, cols] = values
    surface = np.where(valid, smooth_masked(surface, sigma=1.1), np.nan)

    raster_path = TRIAL / "accessible_cooling_potential_surface_100m_trial.tif"
    with rasterio.open(ANALYSIS / "cooling_service_access_distance_surface_100m.tif") as src:
        profile = src.profile.copy()
    profile.update(dtype="float32", nodata=-9999.0, compress="deflate")
    with rasterio.open(raster_path, "w", **profile) as dst:
        dst.write(np.where(np.isfinite(surface), surface, -9999.0).astype("float32"), 1)
    return surface, extent, crs


def plot_association_panel(
    ax,
    data,
    panel_label,
    title,
    outcome,
    xlabel,
    note,
    housing_legend=False,
    components_per_archetype=4,
    subtitle=None,
    xlim=None,
    xticks=None,
    direction_label=None,
    wide_ci_fraction=None,
    plain_crop_rows=None,
):
    data = data.loc[data["outcome"].eq(outcome)].copy()
    data = data.sort_values(["archetype", "selection_rank", "housing_group"]).reset_index(drop=True)
    expected_rows = 4 * components_per_archetype * 2
    if len(data) != expected_rows:
        raise ValueError(
            f"Expected {expected_rows} selected {outcome} rows; found {len(data)}"
        )
    rows = data.drop_duplicates(["archetype", "component_id"]).sort_values(
        ["archetype", "selection_rank"]
    ).reset_index(drop=True)
    expected_components = 4 * components_per_archetype
    if len(rows) != expected_components:
        raise ValueError(
            f"Expected {expected_components} selected {outcome} components; found {len(rows)}"
        )
    yy = np.arange(len(rows))[::-1]
    if xlim is None:
        limit = 1.08 * float(np.nanmax(np.abs(data[["ci_low", "ci_high"]].to_numpy(float))))
        xlim = (-limit, limit)
    xmin, xmax = map(float, xlim)
    ax.set_xlim(xmin, xmax)
    if xticks is not None:
        ax.set_xticks(xticks)
    ax.set_ylim(-1.18 if direction_label else -0.60, len(rows) - 0.40)
    ax.axvline(0, color="#5E666C", lw=0.72, zorder=1)
    plain_crop_rows = set() if plain_crop_rows is None else set(plain_crop_rows)
    flagged_rows = set()
    for y, row in zip(yy, rows.itertuples(index=False)):
        parent = int(row.archetype)
        color = ARCH_COLORS[parent]
        ax.axhspan(y - 0.47, y + 0.47, color=mpl.colors.to_rgba(color, 0.045), lw=0, zorder=0)
        pair = data.loc[
            data["archetype"].eq(parent) & data["component_id"].eq(row.component_id)
        ]
        estimates = dict(zip(pair["housing_group"], pair["estimate"].astype(float)))
        ax.plot(
            [estimates["Non-HDB"], estimates["HDB"]],
            [y - 0.12, y + 0.12],
            color=mpl.colors.to_rgba(color, 0.38), lw=0.65, zorder=2,
        )
        for housing_group, y_offset, marker, filled in (
            ("HDB", 0.12, "o", True),
            ("Non-HDB", -0.12, "D", False),
        ):
            estimate = pair.loc[pair["housing_group"].eq(housing_group)].iloc[0]
            ci_low = float(estimate.ci_low)
            ci_high = float(estimate.ci_high)
            plain_crop = (parent, row.component_id) in plain_crop_rows
            interval_fraction = (ci_high - ci_low) / (xmax - xmin)
            interval_flag = bool(
                not plain_crop
                and (
                    ci_low < xmin
                    or ci_high > xmax
                    or (
                        wide_ci_fraction is not None
                        and interval_fraction >= float(wide_ci_fraction)
                    )
                )
            )
            if interval_flag:
                flagged_rows.add((parent, row.component_id))
            clipped_low = max(ci_low, xmin)
            clipped_high = min(ci_high, xmax)
            if clipped_low <= clipped_high:
                ax.plot(
                    [clipped_low, clipped_high],
                    [y + y_offset, y + y_offset],
                    color=color,
                    lw=0.62 if interval_flag else 0.85,
                    alpha=0.48 if interval_flag else 0.82,
                    linestyle=(0, (2.0, 1.6)) if interval_flag else "-",
                    solid_capstyle="round", zorder=3,
                )
            if ci_low < xmin and not plain_crop:
                ax.scatter(
                    xmin, y + y_offset, s=9, marker="<", facecolor="white",
                    edgecolor=color, lw=0.65, zorder=5, clip_on=False,
                )
            if ci_high > xmax and not plain_crop:
                ax.scatter(
                    xmax, y + y_offset, s=9, marker=">", facecolor="white",
                    edgecolor=color, lw=0.65, zorder=5, clip_on=False,
                )
            point = float(estimate.estimate)
            point_marker = marker
            point_x = point
            if point < xmin:
                point_x, point_marker = xmin, "<"
            elif point > xmax:
                point_x, point_marker = xmax, ">"
            ax.scatter(
                point_x, y + y_offset,
                s=16 if filled else 15, marker=point_marker,
                facecolor=color if filled else "white", edgecolor=color, lw=0.8, zorder=4,
                clip_on=False,
            )
    boundaries = [
        len(rows) - components_per_archetype * group - 0.5
        for group in range(1, 4)
    ]
    for boundary_y in boundaries:
        ax.axhline(boundary_y, color="white", lw=2.0, zorder=1)
        ax.axhline(boundary_y, color="#D7DDE1", lw=0.45, zorder=1)
    labels = []
    for row in rows.itertuples(index=False):
        label = str(row.academic_label).replace("PM₂.₅", r"PM$_{2.5}$")
        if (int(row.archetype), row.component_id) in flagged_rows:
            label += r"$^{\\dagger}$"
        labels.append(f"A{int(row.archetype)}  {label}" if int(row.selection_rank) == 1 else f"      {label}")
    ax.set_yticks(yy, labels)
    for tick, row in zip(ax.get_yticklabels(), rows.itertuples(index=False)):
        tick.set_color(ARCH_COLORS[int(row.archetype)])
        tick.set_fontweight("bold" if int(row.selection_rank) == 1 else "normal")
        tick.set_fontsize(5.0)
    axis_label = xlabel if not note else f"{xlabel}\\n{note}"
    ax.set_xlabel(axis_label, fontsize=5.1, labelpad=4)
    strip_axes(ax)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0, pad=2)
    ax.tick_params(axis="x", labelsize=5.0)
    if direction_label:
        ax.text(
            0, -0.78, direction_label,
            ha="center", va="center", fontsize=5.05, color="#4F5B63",
        )
    add_panel_label(ax, panel_label)
    if title:
        ax.set_title(
            title, loc="left", fontweight="bold",
            pad=7 if not subtitle else 15, fontsize=6.8,
        )
    if subtitle:
        ax.text(
            0, 1.018, subtitle,
            transform=ax.transAxes, color="#68737D", fontsize=5.0, va="bottom",
        )
    if housing_legend:
        housing_handles = [
            Line2D(
                [0], [0], marker="o", linestyle="none", label="HDB",
                markerfacecolor="#39434A", markeredgecolor="#39434A",
                markeredgewidth=0.9, markersize=5.0,
            ),
            Line2D(
                [0], [0], marker="D", linestyle="none",
                label="Other residential", markerfacecolor="white",
                markeredgecolor="#39434A", markeredgewidth=1.0,
                markersize=4.8,
            ),
        ]
        ax.legend(
            handles=housing_handles, loc="upper center",
            bbox_to_anchor=(0.5, -0.145), ncol=2, frameon=False,
            fontsize=5.6, handletextpad=0.45, columnspacing=1.5,
            borderaxespad=0,
        )


def export(fig):
    fig.savefig(OUT / f"{STEM}.svg", bbox_inches="tight")
    fig.savefig(OUT / f"{STEM}.pdf", bbox_inches="tight")
    fig.savefig(OUT / f"{STEM}.png", dpi=600, bbox_inches="tight")
    fig.savefig(
        OUT / f"{STEM}.tiff", dpi=600, bbox_inches="tight",
        pil_kwargs={"compression": "tiff_lzw"},
    )
    plt.close(fig)


def export_comparison_montage():
    """Create a screen-review montage; this is not a submission figure."""
    original_path = ANALYSIS / "figures" / "Figure2_Cooling_efficacy_and_service_footprints.png"
    trial_path = OUT / f"{STEM}.png"
    if not original_path.exists() or not trial_path.exists():
        return
    original = plt.imread(original_path)
    trial = plt.imread(trial_path)
    fig, axes = plt.subplots(1, 2, figsize=(7.2047, 3.35), constrained_layout=True)
    for ax, image, title in (
        (axes[0], original, "Current — efficacy + proximity"),
        (axes[1], trial, "Trial — efficacy + accessible cooling"),
    ):
        ax.imshow(image)
        ax.set_axis_off()
        ax.set_title(title, loc="left", fontsize=13, fontweight="bold", pad=8)
    fig.savefig(OUT / "Figure2_CURRENT_vs_ACCESSIBLE_COOLING_TRIAL.png", dpi=300)
    plt.close(fig)


def main():
    post = pd.read_csv(ANALYSIS / "postcode_cooling_production_and_service.csv", low_memory=False)
    metric = pd.read_csv(TRIAL / "postcode_accessible_cooling_trial.csv", low_memory=False)
    efficacy_pc = pd.read_csv(
        ANALYSIS / "pc_cooling_associations" / "selected_top4_pc_associations.csv"
    )
    accessible_pc = pd.read_csv(TRIAL / "selected_top4_pc_accessible_cooling.csv")
    efficacy, extent, crs, _ = read_raster("cooling_efficacy_surface_100m.tif")
    arch, _, _, _ = read_raster("archetype_surface_100m.tif")
    accessible, accessible_extent, accessible_crs = postcode_metric_surface(metric)
    if extent != accessible_extent or crs != accessible_crs:
        raise RuntimeError("Accessible-cooling raster is not aligned to Figure 2")
    boundary = planning_boundary(crs)

    fig = plt.figure(figsize=(7.2047, 7.0866))
    gs = fig.add_gridspec(
        2, 2, width_ratios=[1.82, 0.58], height_ratios=[1, 1],
        left=0.035, right=0.985, bottom=0.125, top=0.895,
        hspace=0.50, wspace=0.20,
    )
    map_top = gs[0, 0].subgridspec(1, 2, width_ratios=[1.12, 0.68], wspace=-0.08)
    map_bottom = gs[1, 0].subgridspec(1, 2, width_ratios=[1.12, 0.68], wspace=-0.08)
    ax1, ax2 = fig.add_subplot(map_top[0, 0]), fig.add_subplot(map_bottom[0, 0])
    loc_top = map_top[0, 1].subgridspec(4, 1, hspace=0.015)
    loc_bottom = map_bottom[0, 1].subgridspec(4, 1, hspace=0.015)
    loc_axes_top = {k: fig.add_subplot(loc_top[k - 1, 0]) for k in range(1, 5)}
    loc_axes_bottom = {k: fig.add_subplot(loc_bottom[k - 1, 0]) for k in range(1, 5)}
    ax3, ax4 = fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[1, 1])
    for locator_ax in (*loc_axes_top.values(), *loc_axes_bottom.values()):
        pos = locator_ax.get_position()
        locator_ax.set_position([pos.x0 + 0.038, pos.y0, pos.width, pos.height])
    panel_a = fig.add_subplot(gs[0, 0], frameon=False)
    panel_b = fig.add_subplot(gs[1, 0], frameon=False)
    for frame in (panel_a, panel_b):
        frame.set_axis_off()
        frame.set_zorder(20)

    hdb_density, hdb_cells = hdb_density_surface(post, efficacy.shape)
    efficacy_support = np.isfinite(efficacy)
    eff = np.where(efficacy_support, smooth_masked(efficacy), np.nan)
    biv_eff, eff_class, density_class = bivariate_cooling_hdb(eff, hdb_density)
    ax1.imshow(biv_eff, origin="upper", extent=extent, interpolation="nearest")
    map_background(ax1, boundary, outline_only=True)
    ax1.set_anchor("E")
    add_primary_archetype_labels(ax1, arch, extent, support=efficacy_support)
    add_scale_bar(ax1, extent, x_fraction=0.05)
    panel_a.text(-0.045, 1.025, "a1", transform=panel_a.transAxes, fontsize=9, fontweight="bold", va="bottom")
    panel_a.text(0, 1.025, "Cooling efficacy relative to HDB concentration", transform=panel_a.transAxes, fontsize=7.2, fontweight="bold", va="bottom")
    panel_a.text(0, 0.985, "Efficacy per +10 pp greenery × HDB dwelling density", transform=panel_a.transAxes, color="#68737D", va="top")
    add_bivariate_key(ax1, ["≤0", "0–0.10", "≥0.10"], "Cooling efficacy\\n(°C per +10 pp)", "Bivariate legend")
    for k in range(1, 5):
        draw_archetype_split_map(loc_axes_top[k], arch, biv_eff, extent, k, f"a{k + 1}", show_scale_bar=(k == 4))

    accessible_support = np.isfinite(accessible)
    biv_access, access_class, _ = bivariate_accessible_hdb(accessible, hdb_density)
    ax2.imshow(biv_access, origin="upper", extent=extent, interpolation="nearest")
    map_background(ax2, boundary, outline_only=True)
    ax2.set_anchor("E")
    add_primary_archetype_labels(ax2, arch, extent, support=accessible_support)
    add_scale_bar(ax2, extent, x_fraction=0.05)
    panel_b.text(-0.045, 1.025, "b1", transform=panel_b.transAxes, fontsize=9, fontweight="bold", va="bottom")
    panel_b.text(0, 1.025, "Accessible cooling relative to HDB concentration", transform=panel_b.transAxes, fontsize=7.2, fontweight="bold", va="bottom")
    panel_b.text(0, 0.985, "Nearest-footprint cooling magnitude × distance-decay accessibility", transform=panel_b.transAxes, color="#68737D", va="top")
    add_bivariate_key(ax2, ["<0.05", "0.05–0.15", "≥0.15"], "Accessible cooling\\npotential (°C)", "Bivariate legend")
    for k in range(1, 5):
        draw_archetype_split_map(loc_axes_bottom[k], arch, biv_access, extent, k, f"b{k + 1}", show_scale_bar=(k == 4))

    plot_association_panel(
        ax3,
        efficacy_pc,
        "c",
        "Exposome associations with cooling efficacy",
        "cooling_efficacy",
        "Within-archetype IQR association with cooling efficacy (°C per +10 pp greenery)",
        "positive = greater modelled efficacy",
    )
    plot_association_panel(
        ax4,
        accessible_pc,
        "d",
        "Exposome associations with accessible cooling",
        "accessible_cooling",
        "Within-archetype IQR association with accessible cooling (°C)",
        "positive = greater proximity-weighted cooling service",
    )

    key = [
        Line2D([0], [0], marker="o", color="#555555", markerfacecolor="#555555", lw=0, label="HDB"),
        Line2D([0], [0], marker="D", color="#555555", markerfacecolor="white", lw=0, label="Non-HDB"),
    ]
    fig.legend(handles=key, loc="lower right", ncol=2, frameon=False, bbox_to_anchor=(0.987, 0.052), fontsize=5.0)
    fig.text(
        0.035, 0.032,
        "Accessible cooling = nearest-footprint source cooling × 2^(−distance / 400 m); 400 m is the prespecified half-distance. Lines are planning-area-clustered 95% CIs.",
        color="#68737D", fontsize=5.0,
    )
    fig.text(
        0.035, 0.014,
        "Models adjust for housing group, coordinates and planning-area fixed effects. Associations are ecological and descriptive; accessible cooling is a modelled potential, not experienced or causal cooling.",
        color="#68737D", fontsize=5.0,
    )
    fig.suptitle(
        "Urban exposome context differentiates cooling efficacy and accessible cooling",
        x=0.01, y=0.988, ha="left", fontsize=9.2, fontweight="bold",
    )
    export(fig)
    export_comparison_montage()

    hdb_cells.to_csv(SOURCE / "Figure2ab_HDB_dwelling_cells_for_density_surface.csv", index=False)
    metric.to_csv(SOURCE / "Figure2b_postcode_accessible_cooling_trial.csv", index=False)
    efficacy_pc.loc[efficacy_pc["outcome"].eq("cooling_efficacy")].to_csv(
        SOURCE / "Figure2c_top4_pc_cooling_efficacy.csv", index=False
    )
    accessible_pc.to_csv(SOURCE / "Figure2d_top4_pc_accessible_cooling.csv", index=False)
    pd.DataFrame(
        [
            {"panel": "a", "dimension": "cooling efficacy", "class": "low_or_none", "criterion": "<=0 °C per +10 pp greenery"},
            {"panel": "a", "dimension": "cooling efficacy", "class": "moderate", "criterion": ">0 to <0.10 °C per +10 pp greenery"},
            {"panel": "a", "dimension": "cooling efficacy", "class": "high", "criterion": ">=0.10 °C per +10 pp greenery"},
            {"panel": "b", "dimension": "accessible cooling potential", "class": "low", "criterion": "<0.05 °C"},
            {"panel": "b", "dimension": "accessible cooling potential", "class": "moderate", "criterion": "0.05 to <0.15 °C"},
            {"panel": "b", "dimension": "accessible cooling potential", "class": "high", "criterion": ">=0.15 °C"},
            {"panel": "both", "dimension": "HDB dwelling density", "class": "low", "criterion": "<1000 units km-2"},
            {"panel": "both", "dimension": "HDB dwelling density", "class": "medium", "criterion": "1000 to <3000 units km-2"},
            {"panel": "both", "dimension": "HDB dwelling density", "class": "high", "criterion": ">=3000 units km-2"},
        ]
    ).to_csv(SOURCE / "Figure2ab_bivariate_classification_key.csv", index=False)

    qa = json.loads((TRIAL / "accessible_cooling_trial_qa.json").read_text(encoding="utf-8"))
    figure_qa = {
        "analysis_qa_pass": bool(qa["pass"]),
        "n_postcodes": int(len(metric)),
        "accessible_surface_cells": int(accessible_support.sum()),
        "efficacy_surface_cells": int(efficacy_support.sum()),
        "selected_efficacy_rows": int(len(efficacy_pc.loc[efficacy_pc["outcome"].eq("cooling_efficacy")])),
        "selected_accessible_cooling_rows": int(len(accessible_pc)),
        "outputs": [f"{STEM}.{ext}" for ext in ("svg", "pdf", "png", "tiff")],
    }
    figure_qa["pass"] = bool(
        figure_qa["analysis_qa_pass"]
        and figure_qa["n_postcodes"] == 101_545
        and figure_qa["accessible_surface_cells"] > 0
        and figure_qa["selected_efficacy_rows"] == 32
        and figure_qa["selected_accessible_cooling_rows"] == 32
    )
    (OUT / "Figure2_accessible_cooling_trial_QA.json").write_text(
        json.dumps(figure_qa, indent=2), encoding="utf-8"
    )
    if not figure_qa["pass"]:
        raise RuntimeError(f"Trial Figure 2 QA failed: {figure_qa}")
    print(json.dumps(figure_qa, indent=2))
    print(f"Trial figure written to {OUT}")


if __name__ == "__main__":
    main()
'''

# ----- plot_figure2_official -----
RENDERERS['plot_figure2_official'] = '''"""Render the formal Figure 2 selected for the manuscript.

Panels b and d use the 800-m accessible-cooling specification. Panels e and f
use 400-m green exposure, reachability and accessible cooling volume. A1-A4
mini-map insets retain residential-cell bivariate colours.
"""

from __future__ import annotations

import plot_network_integrated_accessible_cooling_figure2 as figure2


ANALYSIS = figure2.ANALYSIS
RADIUS_800 = ANALYSIS / "accessible_cooling_radius_sensitivity_trial" / "800m"
PANEL_E_400 = ANALYSIS / "accessible_cooling_integral_trial" / "panelE400_volume"
OUT = ANALYSIS / "figures"


def main() -> None:
    source = OUT / "source_data" / "Figure2_Archetype_cooling_performance"
    source.mkdir(parents=True, exist_ok=True)
    figure2.TRIAL = RADIUS_800
    figure2.NONLINEAR = PANEL_E_400
    figure2.OUT = OUT
    figure2.SOURCE = source
    figure2.STEM = "Figure2_Archetype_cooling_performance"
    figure2.QA_FILENAME = "Figure2_Archetype_cooling_performance_QA.json"
    figure2.CREATE_COMPARISON_MONTAGE = False
    figure2.MINIMAP_ARCHETYPE_MEAN_COLOR = False
    figure2.SHOW_FIGURE_TITLE = False
    figure2.SHOW_NAVIGATIONAL_HEADINGS = False
    figure2.SIMPLE_PANEL_LABELS = True
    figure2.METRIC = "accessible_cooling_index_800m_c"
    figure2.ACCESS_RADIUS_M = 800
    figure2.PANEL_E_ACCESS_RADIUS_M = 400
    figure2.GREEN_RADIUS_M = 400
    figure2.REACHABILITY_YLIM = (0, 72)
    figure2.REACHABILITY_YTICKS = [0, 20, 40, 60]
    figure2.PANEL_E_MAGNITUDE_TITLE = (
        "Accessible cooling volume within 400 m, where reachable"
    )
    figure2.PANEL_E_MAGNITUDE_LABEL = "Accessible cooling volume (°C·ha)"
    figure2.PANEL_E_MAGNITUDE_YLIM = (0, 2.5)
    figure2.PANEL_E_MAGNITUDE_YTICKS = [0, 0.5, 1.0, 1.5, 2.0, 2.5]
    figure2.PANEL_D_PLAIN_CROP_ROWS = {
        (archetype, pc)
        for archetype in range(1, 5)
        for pc in figure2.DOMAIN_REPRESENTATIVES
    }
    figure2.main()


if __name__ == "__main__":
    main()
'''

# ----- plot_network_integrated_accessible_cooling_figure2 -----
RENDERERS['plot_network_integrated_accessible_cooling_figure2'] = '''"""Production Figure 2 using network-integrated accessible cooling.

Panel b maps the reference-area-normalised integral of every positive modelled
cooling cell reachable within 400 m on the walking network. Panels c and d use
the same five prespecified exposome PCs as Figure 1 so that the two figures form
one coherent analytical sequence.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd
import rasterio
from scipy.spatial import cKDTree
from scipy.stats import chi2_contingency

from plot_accessible_cooling_trial_figure2 import plot_association_panel
from plot_residential_green_cooling_paper_figures import (
    ANALYSIS, ARCH_COLORS,
    add_primary_archetype_labels, add_scale_bar,
    draw_archetype_split_map, hdb_density_surface, map_background,
    planning_boundary, read_raster, smooth_masked,
)


mpl.rcParams.update(
    {"font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
     "svg.fonttype": "none", "pdf.fonttype": 42}
)

TRIAL = ANALYSIS / "accessible_cooling_integral_trial"
NONLINEAR = TRIAL / "nonlinear_green_service"
OUT = ANALYSIS / "figures"
SOURCE = OUT / "source_data" / "Figure2_Archetype_cooling_performance"
OUT.mkdir(parents=True, exist_ok=True)
SOURCE.mkdir(parents=True, exist_ok=True)
STEM = "Figure2_Archetype_cooling_performance"
QA_FILENAME = "Figure2_Archetype_cooling_performance_QA.json"
CREATE_COMPARISON_MONTAGE = False
MINIMAP_ARCHETYPE_MEAN_COLOR = False
SHOW_FIGURE_TITLE = True
SHOW_NAVIGATIONAL_HEADINGS = True
SIMPLE_PANEL_LABELS = False
PANEL_D_PLAIN_CROP_ROWS = {
    (3, "greenery_pc1"),
    (3, "pollution_pc2"),
}
METRIC = "accessible_cooling_index_400m_c"
ACCESS_RADIUS_M = 400
PANEL_E_ACCESS_RADIUS_M = 400
GREEN_RADIUS_M = 400
REACHABILITY_YLIM = (0, 72)
REACHABILITY_YTICKS = [0, 20, 40, 60]
PANEL_E_MAGNITUDE_TITLE = "Accessible cooling where reachable"
PANEL_E_MAGNITUDE_LABEL = "Accessible cooling (°C-equivalent)"
PANEL_E_MAGNITUDE_YLIM = (0, 0.105)
PANEL_E_MAGNITUDE_YTICKS = [0, 0.03, 0.06, 0.09]

# Five prespecified contextual axes are shown in panels c and d. These are the
# same five PCs used for the local contrasts in Figure 1. All 12 balanced PCs
# remain inputs to the archetype clustering.
DOMAIN_REPRESENTATIVES = {
    "greenery_pc1": (1, "Green provision"),
    "park_accessibility_pc1": (2, "Park accessibility"),
    "built_environment_pc2": (3, "Horizontal built intensity"),
    "heat_pc2": (4, "Thermal baseline"),
    "pollution_pc2": (5, "PM\\u2082.\\u2085 trend"),
}
EXPECTED_EXACT_PC_LABELS = {
    "greenery_pc1": "Multiscale Green Provision",
    "park_accessibility_pc1": "Multimodal Park Access",
    "built_environment_pc2": "Horizontal Built Intensity",
    "heat_pc2": "Thermal Floor Contrast",
    "pollution_pc2": "Temporal PM\\u2082.\\u2085 Contrast",
}

# Original high-contrast bivariate palette requested by the user. Rows increase
# in cooling; columns increase in HDB density. Data-derived thresholds are kept
# so the colour contrast does not rely on the earlier arbitrary fixed classes.
BALANCED_BIVARIATE_COLORS = np.array(
    [
        ["#D0D0D0", "#F6B26B", "#E66101"],
        ["#9ECAE1", "#B08AA5", "#C35A6B"],
        ["#2C7FB8", "#6574B7", "#6A3D9A"],
    ]
)


def bivariate_balanced(
    cooling: np.ndarray,
    hdb_density: np.ndarray,
    positive_q75: float,
    density_breaks: tuple[float, float],
):
    """Map zero/lower-positive/upper-quartile cooling against HDB tertiles."""
    lower_density, upper_density = density_breaks
    valid = np.isfinite(cooling)
    cool_class = np.zeros(cooling.shape, dtype=np.int8)
    cool_class[(cooling > 0) & (cooling < positive_q75)] = 1
    cool_class[cooling >= positive_q75] = 2
    density_class = np.zeros(hdb_density.shape, dtype=np.int8)
    density_class[(hdb_density >= lower_density) & (hdb_density < upper_density)] = 1
    density_class[hdb_density >= upper_density] = 2
    rgba = np.ones((*cooling.shape, 4), dtype=float)
    for cooling_class in range(3):
        for density in range(3):
            mask = valid & (cool_class == cooling_class) & (density_class == density)
            rgba[mask, :3] = mpl.colors.to_rgb(
                BALANCED_BIVARIATE_COLORS[cooling_class, density]
            )
    rgba[~valid, 3] = 0
    return rgba, cool_class, density_class


def archetype_mean_bivariate_summary(
    metric_surface: np.ndarray,
    hdb_density: np.ndarray,
    archetype_surface: np.ndarray,
    positive_q75: float,
    density_breaks: tuple[float, float],
    panel: str,
) -> pd.DataFrame:
    """Classify each archetype from its area-weighted mean metric and HDB density."""
    lower_density, upper_density = density_breaks
    rows = []
    for archetype in range(1, 5):
        mask = (
            np.isclose(archetype_surface, archetype)
            & np.isfinite(metric_surface)
            & np.isfinite(hdb_density)
        )
        mean_metric = float(np.mean(metric_surface[mask]))
        mean_density = float(np.mean(hdb_density[mask]))
        metric_class = 0 if mean_metric <= 0 else (2 if mean_metric >= positive_q75 else 1)
        density_class = (
            0 if mean_density < lower_density
            else (2 if mean_density >= upper_density else 1)
        )
        rows.append(
            {
                "panel": panel,
                "archetype": f"A{archetype}",
                "n_residential_cells": int(mask.sum()),
                "mean_cooling_metric": mean_metric,
                "mean_hdb_density_units_km2": mean_density,
                "cooling_class": metric_class,
                "hdb_density_class": density_class,
                "bivariate_colour": BALANCED_BIVARIATE_COLORS[metric_class, density_class],
            }
        )
    return pd.DataFrame(rows)


def add_balanced_bivariate_key(
    parent_ax: plt.Axes,
    yticklabels: list[str],
    metric_title: str,
    metric_unit: str,
    density_breaks: tuple[float, float],
    bounds=(0.65, 0.010, 0.32, 0.27),
) -> None:
    """Direct-reading bivariate key with concise level and unit labels."""
    lower, upper = density_breaks
    key = parent_ax.inset_axes(bounds)
    for yi in range(3):
        for xi in range(3):
            key.add_patch(
                Rectangle(
                    (xi, yi), 1, 1,
                    facecolor=BALANCED_BIVARIATE_COLORS[yi, xi],
                    edgecolor="white", linewidth=0.55,
                )
            )
    key.set_xlim(0, 3); key.set_ylim(0, 3); key.set_aspect("equal")
    key.set_xticks(
        [0.5, 1.5, 2.5],
        ["Low", "Mid", "High"],
    )
    key.set_yticks([0.5, 1.5, 2.5], yticklabels)
    key.set_xlabel(
        "HDB concentration\\n"
        f"<{lower / 1000:.1f}k | {lower / 1000:.1f}–{upper / 1000:.1f}k | "
        f"≥{upper / 1000:.1f}k units km$^{{-2}}$",
        labelpad=1.4, fontsize=5.0,
    )
    key.tick_params(length=0, pad=1.1, labelsize=5.0)
    for spine in key.spines.values():
        spine.set_visible(False)
    key.set_title(f"{metric_title}\\n({metric_unit})", loc="left",
                  fontsize=5.2, fontweight="bold", pad=2.0)


def bivariate_integrated_accessible_hdb(
    accessible: np.ndarray,
    hdb_density: np.ndarray,
    positive_q75: float,
    density_breaks: tuple[float, float],
):
    """Compatibility wrapper for the balanced accessible-cooling encoding."""
    return bivariate_balanced(accessible, hdb_density, positive_q75, density_breaks)


def postcode_metric_surface(postcode_metric: pd.DataFrame):
    """Assign each 100-m residential support cell its nearest postcode value."""
    support, extent, crs, transform = read_raster("cooling_service_access_distance_surface_100m.tif")
    valid = np.isfinite(support)
    rows, cols = np.where(valid)
    xs, ys = rasterio.transform.xy(transform, rows, cols, offset="center")
    tree = cKDTree(postcode_metric[["x_m", "y_m"]].to_numpy(float))
    _, nearest = tree.query(np.column_stack([np.asarray(xs), np.asarray(ys)]), k=1)
    surface = np.full(support.shape, np.nan, dtype=float)
    surface[rows, cols] = postcode_metric[METRIC].to_numpy(float)[nearest]
    raster_path = TRIAL / f"accessible_cooling_index_{ACCESS_RADIUS_M}m_surface_100m_trial.tif"
    with rasterio.open(ANALYSIS / "cooling_service_access_distance_surface_100m.tif") as src:
        profile = src.profile.copy()
    profile.update(dtype="float32", nodata=-9999.0, compress="deflate")
    with rasterio.open(raster_path, "w", **profile) as dst:
        dst.write(np.where(np.isfinite(surface), surface, -9999.0).astype("float32"), 1)
    return surface, extent, crs


def export(fig: plt.Figure) -> None:
    fig.savefig(OUT / f"{STEM}.svg", bbox_inches="tight")
    fig.savefig(OUT / f"{STEM}.pdf", bbox_inches="tight")
    fig.savefig(OUT / f"{STEM}.png", dpi=600, bbox_inches="tight")
    fig.savefig(OUT / f"{STEM}.tiff", dpi=600, bbox_inches="tight",
                pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)


def select_five_domain_axes(data: pd.DataFrame) -> pd.DataFrame:
    """Select the prespecified PCs displayed in association panels c and d."""
    selected = data.loc[data["component_id"].isin(DOMAIN_REPRESENTATIVES)].copy()
    selected["selection_rank"] = selected["component_id"].map(
        {key: value[0] for key, value in DOMAIN_REPRESENTATIVES.items()}
    )
    selected["display_label"] = selected["component_id"].map(
        {key: value[1] for key, value in DOMAIN_REPRESENTATIVES.items()}
    )
    observed_labels = (
        selected[["component_id", "academic_label"]]
        .drop_duplicates()
        .set_index("component_id")["academic_label"]
        .to_dict()
    )
    if observed_labels != EXPECTED_EXACT_PC_LABELS:
        raise ValueError(
            "Prespecified PC identities changed: "
            f"expected {EXPECTED_EXACT_PC_LABELS}; observed {observed_labels}"
        )
    expected = 4 * len(DOMAIN_REPRESENTATIVES) * 2
    if len(selected) != expected:
        raise ValueError(
            f"Expected {expected} displayed association rows; found {len(selected)}"
        )
    return selected


def with_short_display_labels(data: pd.DataFrame) -> pd.DataFrame:
    """Return plotting copy while retaining exact PC names in source data."""
    display = data.copy()
    display["academic_label"] = display["display_label"]
    return display


def comparison_montage() -> None:
    current = ANALYSIS / "figures" / "Figure2_Cooling_efficacy_and_service_footprints.png"
    previous = ANALYSIS / "figures" / "trials" / "Figure2_Cooling_efficacy_and_accessible_cooling_TRIAL.png"
    integrated = OUT / f"{STEM}.png"
    existing = [(p, title) for p, title in (
        (current, "Current: efficacy + proximity"),
        (previous, "Earlier trial: nearest-patch proxy"),
        (integrated, "New trial: network-integrated accessible cooling"),
    ) if p.exists()]
    fig, axes = plt.subplots(1, len(existing), figsize=(3.55 * len(existing), 3.45),
                             constrained_layout=True)
    axes = np.atleast_1d(axes)
    for ax, (path, title) in zip(axes, existing):
        ax.imshow(plt.imread(path))
        ax.set_axis_off()
        ax.set_title(title, loc="left", fontsize=10, fontweight="bold")
    fig.savefig(OUT / "Figure2_three_definition_comparison.png", dpi=300)
    plt.close(fig)


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054):
    """Wilson 95% interval for a binomial proportion."""
    proportion = successes / total
    denominator = 1 + z**2 / total
    centre = (proportion + z**2 / (2 * total)) / denominator
    half = z * np.sqrt(proportion * (1 - proportion) / total + z**2 / (4 * total**2)) / denominator
    return proportion, centre - half, centre + half


def archetype_performance_summary(metric: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """Coverage plus positive-service magnitude for each archetype."""
    rows = []
    for archetype in range(1, 5):
        values = metric.loc[metric["archetype"].eq(archetype), METRIC].astype(float)
        positive = values.loc[values > 0]
        proportion, ci_low, ci_high = wilson_interval(len(positive), len(values))
        q10, q25, median, q75, q90 = positive.quantile([0.10, 0.25, 0.50, 0.75, 0.90])
        rows.append(
            {
                "archetype": archetype,
                "n_postcodes": len(values),
                "n_with_reachable_cooling": len(positive),
                "service_share": proportion,
                "service_share_ci_low": ci_low,
                "service_share_ci_high": ci_high,
                "positive_q10_c": q10,
                "positive_q25_c": q25,
                "positive_median_c": median,
                "positive_q75_c": q75,
                "positive_q90_c": q90,
            }
        )
    summary = pd.DataFrame(rows)
    contingency = pd.crosstab(metric["archetype"], metric[METRIC].gt(0))
    chi2, _, _, _ = chi2_contingency(contingency)
    cramers_v = np.sqrt(chi2 / (len(metric) * min(contingency.shape[0] - 1, contingency.shape[1] - 1)))
    return summary, float(cramers_v)


def plot_archetype_summary(
    ax_coverage: plt.Axes,
    ax_magnitude: plt.Axes,
    summary: pd.DataFrame,
    cramers_v: float,
) -> None:
    """Compact panel e: service coverage and conditional magnitude."""
    y = np.arange(4)[::-1]
    for position, row in zip(y, summary.itertuples(index=False)):
        color = ARCH_COLORS[int(row.archetype)]
        share = 100 * float(row.service_share)
        low = 100 * float(row.service_share_ci_low)
        high = 100 * float(row.service_share_ci_high)
        ax_coverage.plot([low, high], [position, position], color=color, lw=1.1,
                         solid_capstyle="round", zorder=2)
        ax_coverage.scatter(share, position, s=28, color=color, edgecolor="white",
                            linewidth=0.55, zorder=3)
        ax_coverage.text(share + 1.15, position, f"{share:.1f}%", color=color,
                         fontsize=5.4, va="center", fontweight="bold")

        ax_magnitude.plot([row.positive_q10_c, row.positive_q90_c], [position, position],
                          color=mpl.colors.to_rgba(color, 0.52), lw=0.8,
                          solid_capstyle="round", zorder=2)
        ax_magnitude.plot([row.positive_q25_c, row.positive_q75_c], [position, position],
                          color=color, lw=3.4, solid_capstyle="round", zorder=3)
        ax_magnitude.scatter(row.positive_median_c, position, s=25, color=color,
                             edgecolor="white", linewidth=0.55, zorder=4)
        ax_magnitude.text(row.positive_q90_c + 0.0015, position,
                          f"median {row.positive_median_c:.3f}", color=color,
                          fontsize=5.1, va="center")

    labels = [
        f"A{int(row.archetype)}   n={int(row.n_postcodes):,}"
        for row in summary.itertuples(index=False)
    ]
    ax_coverage.set_yticks(y, labels)
    for tick, row in zip(ax_coverage.get_yticklabels(), summary.itertuples(index=False)):
        tick.set_color(ARCH_COLORS[int(row.archetype)])
        tick.set_fontweight("bold")
        tick.set_fontsize(5.5)
    ax_magnitude.set_yticks(y, [
        f"n={int(row.n_with_reachable_cooling):,} served"
        for row in summary.itertuples(index=False)
    ])
    ax_magnitude.tick_params(axis="y", labelsize=5.0, colors="#68737D")
    for ax in (ax_coverage, ax_magnitude):
        ax.set_ylim(-0.65, 3.65)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.tick_params(axis="y", length=0, pad=3)
        ax.tick_params(axis="x", labelsize=5.2)
        ax.grid(axis="x", color="#E3E7EA", lw=0.45, zorder=0)
        ax.set_axisbelow(True)
    ax_coverage.set_xlim(0, 50)
    ax_coverage.set_xticks([0, 10, 20, 30, 40, 50])
    ax_coverage.set_xlabel("Postcodes with reachable cooling within 400 m (%)\\npoint and Wilson 95% CI",
                           fontsize=5.3, labelpad=3)
    ax_coverage.set_title("Service coverage", loc="left", fontsize=6.3,
                          fontweight="bold", pad=5)
    ax_coverage.text(1, 1.02, f"Cramér’s V = {cramers_v:.2f}", transform=ax_coverage.transAxes,
                     ha="right", va="bottom", fontsize=5.2, color="#68737D")
    ax_magnitude.set_xlim(0, 0.058)
    ax_magnitude.set_xticks([0, 0.02, 0.04, 0.06])
    ax_magnitude.set_xlabel("Accessible cooling among served postcodes (°C)\\npoint = median; thick = IQR; thin = 10th–90th percentile",
                            fontsize=5.3, labelpad=3)
    ax_magnitude.set_title("Service magnitude conditional on access", loc="left",
                           fontsize=6.3, fontweight="bold", pad=5)


def plot_nonlinear_service_panel(
    ax_probability: plt.Axes,
    ax_magnitude: plt.Axes,
    curves: pd.DataFrame,
    bins: pd.DataFrame,
) -> None:
    """Panel e: two-part restricted-cubic-spline green-service models."""
    specifications = [
        (
            ax_probability, "service_probability",
            f"Cooling reachability within {PANEL_E_ACCESS_RADIUS_M:,} m", 100.0,
            "Postcodes with reachable cooling (%)", REACHABILITY_YLIM,
            REACHABILITY_YTICKS,
        ),
        (
            ax_magnitude, "positive_magnitude",
            PANEL_E_MAGNITUDE_TITLE, 1.0,
            PANEL_E_MAGNITUDE_LABEL, PANEL_E_MAGNITUDE_YLIM,
            PANEL_E_MAGNITUDE_YTICKS,
        ),
    ]
    legend_handles = []
    for ax, outcome, title, scale, ylabel, ylim, yticks in specifications:
        for archetype in range(1, 5):
            color = ARCH_COLORS[archetype]
            curve = curves.loc[
                curves["outcome"].eq(outcome) & curves["archetype"].eq(archetype)
            ].sort_values("green_percent")
            support_low = float(curve["green_percent"].min())
            support_high = float(curve["green_percent"].max())
            empirical = bins.loc[
                bins["outcome"].eq(outcome) & bins["archetype"].eq(archetype)
                & bins["green_percent"].between(support_low, support_high)
            ]
            ax.fill_between(
                curve["green_percent"], scale * curve["ci_low"],
                scale * curve["ci_high"], color=color, alpha=0.085,
                linewidth=0, zorder=1,
            )
            line, = ax.plot(
                curve["green_percent"], scale * curve["estimate"],
                color=color, lw=1.25, solid_capstyle="round", zorder=3,
                label=f"A{archetype}",
            )
            ax.scatter(
                empirical["green_percent"], scale * empirical["empirical_mean"],
                s=7, facecolor=mpl.colors.to_rgba(color, 0.32),
                edgecolor="white", linewidth=0.25, zorder=4,
            )
            if ax is ax_probability:
                legend_handles.append(line)
        ax.set_xlim(5, 76)
        ax.set_ylim(*ylim)
        ax.set_yticks(yticks)
        ax.set_xlabel(
            f"Green area within {GREEN_RADIUS_M:,} m (%)", fontsize=5.6, labelpad=2
        )
        ax.set_ylabel(ylabel, fontsize=5.6, labelpad=3)
        if SHOW_NAVIGATIONAL_HEADINGS:
            ax.set_title(title, loc="left", fontsize=6.35, fontweight="bold", pad=5)
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines[["left", "bottom"]].set_color("#AAB2B8")
        ax.spines[["left", "bottom"]].set_linewidth(0.55)
        ax.tick_params(axis="both", labelsize=5.2, width=0.45, length=2.3)
        ax.grid(axis="y", color="#E6E9EB", lw=0.42, zorder=0)
        ax.set_axisbelow(True)

    ax_probability.legend(
        handles=legend_handles, labels=["A1", "A2", "A3", "A4"],
        loc="upper left", bbox_to_anchor=(0.0, 1.02), ncol=4,
        frameon=False, handlelength=1.4, columnspacing=1.2,
        handletextpad=0.35, borderaxespad=0, fontsize=5.2,
    )


def main() -> None:
    post = pd.read_csv(ANALYSIS / "postcode_cooling_production_and_service.csv", low_memory=False)
    metric = pd.read_csv(TRIAL / "postcode_network_integrated_accessible_cooling.csv", low_memory=False)
    cooling_pc = pd.read_csv(
        ANALYSIS / "pc_cooling_associations" / "all_12_pc_associations_by_archetype_and_housing.csv"
    )
    accessible_pc_all = pd.read_csv(
        TRIAL / "all_12_pc_accessible_cooling_integral_associations.csv"
    )
    efficacy_pc = select_five_domain_axes(
        cooling_pc.loc[cooling_pc["outcome"].eq("cooling_efficacy")]
    )
    accessible_pc = select_five_domain_axes(
        accessible_pc_all.loc[
            accessible_pc_all["outcome"].eq("accessible_cooling_integral")
        ]
    )
    components_per_archetype = len(DOMAIN_REPRESENTATIVES)
    nonlinear_curves = pd.read_csv(NONLINEAR / "archetype_nonlinear_green_service_predictions.csv")
    nonlinear_bins = pd.read_csv(NONLINEAR / "archetype_green_service_empirical_bins.csv")
    nonlinear_tests = pd.read_csv(NONLINEAR / "archetype_nonlinearity_tests.csv")
    nonlinear_heterogeneity = pd.read_csv(
        NONLINEAR / "archetype_green_response_heterogeneity_tests.csv"
    )
    efficacy, extent, crs, _ = read_raster("cooling_efficacy_surface_100m.tif")
    archetype, _, _, _ = read_raster("archetype_surface_100m.tif")
    accessible, accessible_extent, accessible_crs = postcode_metric_surface(metric)
    if extent != accessible_extent or crs != accessible_crs:
        raise RuntimeError("Integrated accessible-cooling raster is not aligned to Figure 2")
    boundary = planning_boundary(crs)

    fig = plt.figure(figsize=(7.2047, 7.85))
    figure_top = 0.970 if not SHOW_FIGURE_TITLE else 0.910
    figure_hspace = 0.32 if not SHOW_NAVIGATIONAL_HEADINGS else 0.46
    gs = fig.add_gridspec(
        3, 2, width_ratios=[1.82, 0.58], height_ratios=[1, 1, 0.68],
        left=0.035, right=0.985, bottom=0.080, top=figure_top,
        hspace=figure_hspace, wspace=0.025,
    )
    map_top = gs[0, 0].subgridspec(1, 2, width_ratios=[1.12, 0.68], wspace=-0.08)
    map_bottom = gs[1, 0].subgridspec(1, 2, width_ratios=[1.12, 0.68], wspace=-0.08)
    ax1, ax2 = fig.add_subplot(map_top[0, 0]), fig.add_subplot(map_bottom[0, 0])
    mini_top = map_top[0, 1].subgridspec(4, 1, hspace=0.015)
    mini_bottom = map_bottom[0, 1].subgridspec(4, 1, hspace=0.015)
    mini_axes_top = {k: fig.add_subplot(mini_top[k - 1, 0]) for k in range(1, 5)}
    mini_axes_bottom = {k: fig.add_subplot(mini_bottom[k - 1, 0]) for k in range(1, 5)}
    ax3, ax4 = fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[1, 1])
    summary_grid = gs[2, :].subgridspec(1, 2, width_ratios=[1, 1], wspace=0.16)
    ax5_coverage = fig.add_subplot(summary_grid[0, 0])
    ax5_magnitude = fig.add_subplot(summary_grid[0, 1])
    panel_e = fig.add_subplot(gs[2, :], frameon=False)
    panel_e.set_axis_off(); panel_e.set_zorder(20)
    for mini in (*mini_axes_top.values(), *mini_axes_bottom.values()):
        pos = mini.get_position()
        mini.set_position([pos.x0 + 0.038, pos.y0, pos.width, pos.height])
    frame_a, frame_b = fig.add_subplot(gs[0, 0], frameon=False), fig.add_subplot(gs[1, 0], frameon=False)
    for frame in (frame_a, frame_b):
        frame.set_axis_off(); frame.set_zorder(20)

    hdb_density, hdb_cells = hdb_density_surface(post, efficacy.shape)
    efficacy_support = np.isfinite(efficacy)
    efficacy_display = np.where(efficacy_support, smooth_masked(efficacy), np.nan)
    density_quantiles = np.quantile(
        hdb_density[efficacy_support], [1 / 3, 2 / 3]
    )
    density_breaks = (float(density_quantiles[0]), float(density_quantiles[1]))
    efficacy_positive_q75 = float(
        np.quantile(efficacy_display[efficacy_support & (efficacy_display > 0)], 0.75)
    )
    accessible_positive_q75 = float(
        metric.loc[metric[METRIC].gt(0), METRIC].quantile(0.75)
    )
    bivariate_eff, efficacy_class, density_class_a = bivariate_balanced(
        efficacy_display, hdb_density, efficacy_positive_q75, density_breaks
    )
    mean_eff = archetype_mean_bivariate_summary(
        efficacy_display, hdb_density, archetype, efficacy_positive_q75,
        density_breaks, panel="a: cooling efficacy",
    )
    mean_eff_colors = {
        int(row.archetype[1:]): row.bivariate_colour
        for row in mean_eff.itertuples(index=False)
    }
    ax1.imshow(bivariate_eff, origin="upper", extent=extent, interpolation="nearest")
    map_background(ax1, boundary, outline_only=True); ax1.set_anchor("E")
    add_primary_archetype_labels(ax1, archetype, extent, support=efficacy_support)
    add_scale_bar(ax1, extent, x_fraction=0.05)
    frame_a.text(-0.045, 1.025, "a" if SIMPLE_PANEL_LABELS else "a1",
                 transform=frame_a.transAxes, fontsize=9,
                 fontweight="bold", va="bottom")
    if SHOW_NAVIGATIONAL_HEADINGS:
        frame_a.text(0, 1.025, "Cooling efficacy relative to HDB concentration",
                     transform=frame_a.transAxes, fontsize=7.2,
                     fontweight="bold", va="bottom")
    add_balanced_bivariate_key(
        ax1,
        ["No/negative\\n≤0", "Moderate\\n>0", f"High\\n≥{efficacy_positive_q75:.2f}"],
        "Cooling efficacy", "°C per +10 pp green", density_breaks,
    )
    for k in range(1, 5):
        draw_archetype_split_map(mini_axes_top[k], archetype, bivariate_eff, extent, k,
                                 None if SIMPLE_PANEL_LABELS else f"a{k + 1}",
                                 show_scale_bar=(k == 4),
                                 uniform_color=(
                                     mean_eff_colors[k]
                                     if MINIMAP_ARCHETYPE_MEAN_COLOR else None
                                 ))

    accessible_support = np.isfinite(accessible)
    bivariate_access, accessible_class, density_class_b = bivariate_integrated_accessible_hdb(
        accessible, hdb_density, accessible_positive_q75, density_breaks
    )
    mean_access = archetype_mean_bivariate_summary(
        accessible, hdb_density, archetype, accessible_positive_q75,
        density_breaks, panel="b: accessible cooling",
    )
    mean_access_colors = {
        int(row.archetype[1:]): row.bivariate_colour
        for row in mean_access.itertuples(index=False)
    }
    ax2.imshow(bivariate_access, origin="upper", extent=extent, interpolation="nearest")
    map_background(ax2, boundary, outline_only=True); ax2.set_anchor("E")
    add_primary_archetype_labels(ax2, archetype, extent, support=accessible_support)
    add_scale_bar(ax2, extent, x_fraction=0.05)
    frame_b.text(-0.045, 1.025, "b" if SIMPLE_PANEL_LABELS else "b1",
                 transform=frame_b.transAxes, fontsize=9,
                 fontweight="bold", va="bottom")
    if SHOW_NAVIGATIONAL_HEADINGS:
        frame_b.text(0, 1.025, "Accessible cooling relative to HDB concentration",
                     transform=frame_b.transAxes, fontsize=7.2,
                     fontweight="bold", va="bottom")
    add_balanced_bivariate_key(
        ax2,
        ["None\\n0", "Moderate\\n>0", f"High\\n≥{accessible_positive_q75:.3f}"],
        "Accessible cooling", "°C-equivalent", density_breaks,
    )
    for k in range(1, 5):
        draw_archetype_split_map(mini_axes_bottom[k], archetype, bivariate_access, extent, k,
                                 None if SIMPLE_PANEL_LABELS else f"b{k + 1}",
                                 show_scale_bar=(k == 4),
                                 uniform_color=(
                                     mean_access_colors[k]
                                     if MINIMAP_ARCHETYPE_MEAN_COLOR else None
                                 ))

    if MINIMAP_ARCHETYPE_MEAN_COLOR:
        pd.concat([mean_eff, mean_access], ignore_index=True).to_csv(
            SOURCE / "Figure2_minimap_archetype_mean_colour_classes.csv", index=False
        )

    plot_association_panel(
        ax3, with_short_display_labels(efficacy_pc), "c",
        ("Archetype exposome associations with cooling efficacy"
         if SHOW_NAVIGATIONAL_HEADINGS else ""),
        "cooling_efficacy",
        "Cooling efficacy contrast (°C per +10 pp greenery)",
        None,
        housing_legend=True,
        components_per_archetype=components_per_archetype,
        subtitle=None,
        xlim=(-0.20, 0.20),
        xticks=[-0.10, 0, 0.10],
        direction_label=None,
        wide_ci_fraction=0.75,
    )
    plot_association_panel(
        ax4, with_short_display_labels(accessible_pc), "d",
        ("Archetype exposome associations with accessible cooling"
         if SHOW_NAVIGATIONAL_HEADINGS else ""),
        "accessible_cooling_integral",
        "Accessible cooling contrast (°C)",
        None,
        housing_legend=True,
        components_per_archetype=components_per_archetype,
        subtitle=None,
        xlim=(-0.015, 0.015),
        xticks=[-0.015, -0.010, -0.005, 0, 0.005, 0.010, 0.015],
        direction_label=None,
        wide_ci_fraction=0.75,
        plain_crop_rows=PANEL_D_PLAIN_CROP_ROWS,
    )
    plot_nonlinear_service_panel(
        ax5_coverage, ax5_magnitude, nonlinear_curves, nonlinear_bins,
    )
    ax5_coverage.text(-0.075, 1.035, "e" if SIMPLE_PANEL_LABELS else "e1",
                      transform=ax5_coverage.transAxes,
                      fontsize=8.5, fontweight="bold", ha="right", va="bottom")
    ax5_magnitude.text(-0.075, 1.035, "f" if SIMPLE_PANEL_LABELS else "e2",
                       transform=ax5_magnitude.transAxes,
                       fontsize=8.5, fontweight="bold", ha="right", va="bottom")
    if SHOW_NAVIGATIONAL_HEADINGS:
        panel_e.text(-0.020, 1.160,
                     "Nonlinearity emerges at different cooling-service stages across archetypes",
                     transform=panel_e.transAxes, fontsize=7.2,
                     fontweight="bold", va="bottom")
    if SHOW_FIGURE_TITLE:
        fig.suptitle(
            "Urban exposome context differentiates cooling efficacy and accessible cooling",
            x=0.01, y=0.988, ha="left", fontsize=9.2, fontweight="bold",
        )
    export(fig)
    if CREATE_COMPARISON_MONTAGE:
        comparison_montage()

    hdb_cells.to_csv(SOURCE / "Figure2ab_HDB_dwelling_cells.csv", index=False)
    metric.to_csv(SOURCE / "Figure2b_postcode_network_integrated_accessible_cooling.csv", index=False)
    efficacy_pc.loc[efficacy_pc["outcome"].eq("cooling_efficacy")].to_csv(
        SOURCE / "Figure2c_prespecified_domain_pc_cooling_efficacy.csv", index=False)
    accessible_pc.to_csv(
        SOURCE / "Figure2d_prespecified_domain_pc_accessible_cooling.csv", index=False)
    nonlinear_curves.to_csv(SOURCE / "Figure2e_nonlinear_green_service_curves.csv", index=False)
    nonlinear_bins.to_csv(SOURCE / "Figure2e_nonlinear_green_service_empirical_bins.csv", index=False)
    nonlinear_tests.to_csv(SOURCE / "Figure2e_nonlinearity_tests.csv", index=False)
    nonlinear_heterogeneity.to_csv(
        SOURCE / "Figure2e_archetype_green_response_heterogeneity_tests.csv", index=False
    )
    classes = pd.DataFrame([
        {"panel": "a", "dimension": "cooling efficacy", "class": "non-positive", "criterion": "<=0 C per +10 pp green"},
        {"panel": "a", "dimension": "cooling efficacy", "class": "lower positive", "criterion": f">0 to <positive-cell Q75 ({efficacy_positive_q75:.8f} C per +10 pp green)"},
        {"panel": "a", "dimension": "cooling efficacy", "class": "upper positive quartile", "criterion": f">=positive-cell Q75 ({efficacy_positive_q75:.8f} C per +10 pp green)"},
        {"panel": "b", "dimension": "network-integrated cooling service", "class": "none", "criterion": "0 C-equivalent"},
        {"panel": "b", "dimension": "network-integrated cooling service", "class": "lower positive", "criterion": f">0 to <served-postcode Q75 ({accessible_positive_q75:.8f} C-equivalent)"},
        {"panel": "b", "dimension": "network-integrated cooling service", "class": "upper positive quartile", "criterion": f">=served-postcode Q75 ({accessible_positive_q75:.8f} C-equivalent)"},
        {"panel": "a,b", "dimension": "HDB dwelling density", "class": "lower residential-cell tertile", "criterion": f"<{density_breaks[0]:.6f} units km-2"},
        {"panel": "a,b", "dimension": "HDB dwelling density", "class": "middle residential-cell tertile", "criterion": f">={density_breaks[0]:.6f} to <{density_breaks[1]:.6f} units km-2"},
        {"panel": "a,b", "dimension": "HDB dwelling density", "class": "upper residential-cell tertile", "criterion": f">={density_breaks[1]:.6f} units km-2"},
    ])
    classes.to_csv(SOURCE / "Figure2ab_balanced_bivariate_classification_key.csv", index=False)
    qa = json.loads((TRIAL / "network_integrated_accessible_cooling_qa.json").read_text())
    cooling_pc_qa = json.loads(
        (ANALYSIS / "pc_cooling_associations" / "pc_association_qa.json").read_text()
    )
    figure_qa = {
        "analysis_qa_pass": qa["pass"], "n_postcodes": len(metric),
        "minimap_encoding": (
            "archetype area-weighted mean bivariate class"
            if MINIMAP_ARCHETYPE_MEAN_COLOR
            else "residential-cell bivariate class"
        ),
        "separate_pc_analysis_qa_pass": bool(cooling_pc_qa["pass"] and qa["pass"]),
        "pc_model_specification": "each prespecified PC fitted separately within archetype",
        "residential_support_cells": int(accessible_support.sum()),
        "accessible_zero_share": float(metric[METRIC].eq(0).mean()),
        "selected_efficacy_rows": int(len(efficacy_pc.loc[efficacy_pc["outcome"].eq("cooling_efficacy")])),
        "selected_accessible_rows": int(len(accessible_pc)),
        "panel_e_curve_rows": int(len(nonlinear_curves)),
        "panel_e_empirical_bin_rows": int(len(nonlinear_bins)),
        "panel_e_nonlinearity_test_rows": int(len(nonlinear_tests)),
        "panel_e_heterogeneity_test_rows": int(len(nonlinear_heterogeneity)),
        "panel_e_service_heterogeneity_p": float(
            nonlinear_heterogeneity.loc[
                nonlinear_heterogeneity["outcome"].eq("service_probability"),
                "archetype_by_green_response_p",
            ].iloc[0]
        ),
        "panel_e_magnitude_heterogeneity_p": float(
            nonlinear_heterogeneity.loc[
                nonlinear_heterogeneity["outcome"].eq("positive_magnitude"),
                "archetype_by_green_response_p",
            ].iloc[0]
        ),
        "balanced_bivariate_thresholds": {
            "efficacy_positive_q75_c_per_10pp": efficacy_positive_q75,
            "accessible_service_positive_q75_c_equivalent": accessible_positive_q75,
            "hdb_density_tertile_1_units_km2": density_breaks[0],
            "hdb_density_tertile_2_units_km2": density_breaks[1],
        },
        "panel_a_class_shares": {
            f"cooling_{cool}_hdb_{density}": float(
                np.mean((efficacy_class[efficacy_support] == cool)
                        & (density_class_a[efficacy_support] == density))
            )
            for cool in range(3) for density in range(3)
        },
        "panel_b_class_shares": {
            f"cooling_{cool}_hdb_{density}": float(
                np.mean((accessible_class[accessible_support] == cool)
                        & (density_class_b[accessible_support] == density))
            )
            for cool in range(3) for density in range(3)
        },
        "outputs": [f"{STEM}.{ext}" for ext in ("svg", "pdf", "png", "tiff")],
    }
    figure_qa["pass"] = bool(
        figure_qa["analysis_qa_pass"]
        and figure_qa["separate_pc_analysis_qa_pass"]
        and figure_qa["n_postcodes"] == 101_545
        and figure_qa["residential_support_cells"] > 0
        and figure_qa["selected_efficacy_rows"] == 4 * components_per_archetype * 2
        and figure_qa["selected_accessible_rows"] == 4 * components_per_archetype * 2
        and figure_qa["panel_e_curve_rows"] == 960
        and figure_qa["panel_e_empirical_bin_rows"] == 128
        and figure_qa["panel_e_nonlinearity_test_rows"] == 8
        and figure_qa["panel_e_heterogeneity_test_rows"] == 2
    )
    (OUT / QA_FILENAME).write_text(
        json.dumps(figure_qa, indent=2), encoding="utf-8")
    if not figure_qa["pass"]:
        raise RuntimeError(figure_qa)
    print(json.dumps(figure_qa, indent=2))


if __name__ == "__main__":
    main()
'''

# ----- plot_residential_green_cooling_paper_figures -----
RENDERERS['plot_residential_green_cooling_paper_figures'] = '''"""Publication figures for the all-residential Singapore green-cooling study.

All quantitative panels are generated from stored analysis outputs. The script
does not refit models. Positive cooling quantities always mean greater benefit.
"""

from __future__ import annotations

import json
import math
import re
import textwrap
from pathlib import Path

import geopandas as gpd
import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
import numpy as np
import pandas as pd
import rasterio
from matplotlib.colors import BoundaryNorm, ListedColormap, TwoSlopeNorm
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, Rectangle
from scipy.ndimage import distance_transform_edt, gaussian_filter, label as ndi_label
from scipy.signal import convolve2d


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "ALL_RESIDENTIAL_5DOMAIN_PM2016_2024_ARCHETYPES"
ANALYSIS = BASE / "cooling_propagation_all_residential"
OUT = ANALYSIS / "figures"
SOURCE = OUT / "source_data"
OUT.mkdir(parents=True, exist_ok=True)
SOURCE.mkdir(parents=True, exist_ok=True)

ARCH_COLORS = {1: "#009E73", 2: "#D55E00", 3: "#0072B2", 4: "#CC79A7"}
ARCH_NAMES = {
    1: "Low-green–Hot",
    2: "High-PM2.5–Green",
    3: "Green–Cool",
    4: "Low-green–Low-PM2.5",
}

# Five prespecified exposome dimensions shared with Figure 2. All 12 balanced
# PCs remain inputs to clustering; this subset is used only for the local
# explanatory maps in Figure 1c-f.
FIGURE1_SHARED_COMPONENT_IDS = [
    "greenery_pc1",
    "park_accessibility_pc1",
    "built_environment_pc2",
    "heat_pc2",
    "pollution_pc2",
]
FIGURE1_SHORT_PC_LABELS = {
    "greenery_pc1": "Green provision",
    "park_accessibility_pc1": "Park accessibility",
    "built_environment_pc2": "Horizontal built intensity",
    "heat_pc2": "Thermal baseline",
    "pollution_pc2": "PM₂.₅ trend",
}
FIGURE1_PANEL_B_SHORT_LABELS = {
    **FIGURE1_SHORT_PC_LABELS,
    "heat_pc1": "Persistent thermal burden",
    "pollution_pc1": "Persistent PM₂.₅ burden",
    "park_accessibility_pc2": "Modal park contrast",
    "built_environment_pc1": "Vertical built intensity",
    "built_environment_pc3": "Open heat form",
    "built_environment_pc4": "Elevated heat form",
    "built_environment_pc5": "Reflective open form",
}
FIGURE1_PANEL_B_COMPONENT_ORDER = FIGURE1_SHARED_COMPONENT_IDS + [
    "heat_pc1",
    "pollution_pc1",
    "park_accessibility_pc2",
    "built_environment_pc1",
    "built_environment_pc3",
    "built_environment_pc4",
    "built_environment_pc5",
]
FIGURE1_SHOW_NAVIGATIONAL_HEADINGS = False
# Shared bivariate palette for Figure 2. Rows increase in modelled cooling;
# columns increase in HDB dwelling density. The low-low corner is neutral,
# high-density/low-cooling is warm, low-density/high-cooling is blue, and the
# high-high corner is dark purple. Both maps use the same thresholds and hues.
BIVARIATE_COLORS = np.array(
    [
        ["#D0D0D0", "#F6B26B", "#E66101"],
        ["#9ECAE1", "#B08AA5", "#C35A6B"],
        ["#2C7FB8", "#6574B7", "#6A3D9A"],
    ]
)

mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 6.5,
        "axes.titlesize": 7.2,
        "axes.labelsize": 6.5,
        "xtick.labelsize": 5.8,
        "ytick.labelsize": 5.8,
        "legend.fontsize": 5.7,
        "axes.linewidth": 0.6,
        "lines.linewidth": 1.0,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "savefig.facecolor": "white",
        "figure.facecolor": "white",
    }
)


def read_raster(name: str):
    with rasterio.open(ANALYSIS / name) as src:
        arr = src.read(1).astype(float)
        nodata = src.nodata
        if nodata is not None:
            arr[arr == nodata] = np.nan
        bounds = src.bounds
        extent = [bounds.left, bounds.right, bounds.bottom, bounds.top]
        crs = src.crs
        transform = src.transform
    return arr, extent, crs, transform


def smooth_masked(arr: np.ndarray, sigma: float = 1.1) -> np.ndarray:
    valid = np.isfinite(arr)
    num = gaussian_filter(np.where(valid, arr, 0.0), sigma=sigma)
    den = gaussian_filter(valid.astype(float), sigma=sigma)
    out = np.full(arr.shape, np.nan)
    np.divide(num, den, out=out, where=den > 0.12)
    return out


def add_panel_label(ax, label: str):
    ax.text(-0.105, 1.025, label, transform=ax.transAxes, fontsize=9, fontweight="bold", va="bottom")


def strip_axes(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(length=2, width=0.5)


def add_scale_bar(ax, extent, km=5, x_fraction=0.74, y_fraction=0.055):
    x0 = extent[0] + x_fraction * (extent[1] - extent[0])
    y0 = extent[2] + y_fraction * (extent[3] - extent[2])
    length = km * 1000
    ax.plot([x0, x0 + length], [y0, y0], color="#222222", lw=1.5, solid_capstyle="butt", zorder=20)
    ax.text(x0 + length / 2, y0 + 800, f"{km} km", ha="center", va="bottom", fontsize=5.5)


def planning_boundary(crs):
    path = ROOT / "Data" / "Primary" / "8-Landuse" / "MasterPlan2019PlanningAreaBoundaryNoSea" / "MasterPlan2019PlanningAreaBoundaryNoSea.geojson"
    return gpd.read_file(path).to_crs(crs)


def hdb_density_surface(post: pd.DataFrame, shape, sigma_cells=4.0):
    """Return a 400-m-smoothed HDB dwelling density surface and raw grid cells.

    The input raster is 100 m, so multiplying the Gaussian-smoothed cell totals
    by 100 expresses the result as recorded dwelling units per km2. Only HDB
    All HDB postcodes with recorded dwelling units enter the overlay so that
    the density layer has the same complete residential scope as both maps.
    """
    h = post[post["housing_group"] == "HDB"].copy()
    cells = h.groupby(["row", "col"], as_index=False)["hdb_dwelling_units"].sum()
    cells = cells[cells.hdb_dwelling_units > 0].copy()
    raw = np.zeros(shape, dtype=float)
    valid = (
        cells["row"].between(0, shape[0] - 1)
        & cells["col"].between(0, shape[1] - 1)
    )
    cells = cells.loc[valid].copy()
    raw[cells["row"].astype(int), cells["col"].astype(int)] = cells["hdb_dwelling_units"].to_numpy(float)
    density = gaussian_filter(raw, sigma=sigma_cells, mode="constant") * 100.0
    return density, cells


def bivariate_cooling_hdb(cooling, hdb_density):
    """Map cooling and HDB density to the shared 3 x 3 Figure 2 palette.

    Cooling classes are <=0, >0 to <0.10, and >=0.10 degrees C. HDB density
    classes are <1,000, 1,000 to <3,000, and >=3,000 recorded units per km2.
    """
    valid = np.isfinite(cooling)
    cool_class = np.zeros(cooling.shape, dtype=np.int8)
    cool_class[(cooling > 0) & (cooling < 0.10)] = 1
    cool_class[cooling >= 0.10] = 2
    density_class = np.zeros(hdb_density.shape, dtype=np.int8)
    density_class[(hdb_density >= 1000) & (hdb_density < 3000)] = 1
    density_class[hdb_density >= 3000] = 2

    rgba = np.ones((*cooling.shape, 4), dtype=float)
    for ci in range(3):
        for di in range(3):
            mask = valid & (cool_class == ci) & (density_class == di)
            rgba[mask, :3] = mpl.colors.to_rgb(BIVARIATE_COLORS[ci, di])
    rgba[~valid, 3] = 0.0
    return rgba, cool_class, density_class


def bivariate_access_hdb(access_distance, hdb_density):
    """Map postcode cooling proximity and HDB density to the 3 x 3 palette.

    Proximity is high at <=400 m, moderate at >400-800 m and limited at >800 m
    straight-line distance to the nearest modelled cooled footprint.
    """
    valid = np.isfinite(access_distance)
    access_class = np.zeros(access_distance.shape, dtype=np.int8)
    access_class[(access_distance > 400) & (access_distance <= 800)] = 1
    access_class[access_distance <= 400] = 2
    density_class = np.zeros(hdb_density.shape, dtype=np.int8)
    density_class[(hdb_density >= 1000) & (hdb_density < 3000)] = 1
    density_class[hdb_density >= 3000] = 2
    rgba = np.ones((*access_distance.shape, 4), dtype=float)
    for ai in range(3):
        for di in range(3):
            mask = valid & (access_class == ai) & (density_class == di)
            rgba[mask, :3] = mpl.colors.to_rgb(BIVARIATE_COLORS[ai, di])
    rgba[~valid, 3] = 0.0
    return rgba, access_class, density_class


def add_bivariate_key(parent_ax, yticklabels, ylabel, title, bounds=(0.70, 0.025, 0.235, 0.235)):
    """Add a compact, panel-specific 3 x 3 key inside a map's white space."""
    key = parent_ax.inset_axes(bounds)
    for yi in range(3):
        for xi in range(3):
            key.add_patch(
                Rectangle(
                    (xi, yi),
                    1,
                    1,
                    facecolor=BIVARIATE_COLORS[yi, xi],
                    edgecolor="white",
                    linewidth=0.55,
                )
            )
    key.set_xlim(0, 3)
    key.set_ylim(0, 3)
    key.set_aspect("equal")
    key.set_xticks([0.5, 1.5, 2.5], ["<1k", "1–3k", "≥3k"])
    key.set_yticks([0.5, 1.5, 2.5], yticklabels)
    key.set_xlabel("HDB dwelling density\\n(units km$^{-2}$)", labelpad=1.2)
    key.set_ylabel(ylabel, labelpad=1.0)
    key.tick_params(length=0, pad=0.8, labelsize=5.0)
    for spine in key.spines.values():
        spine.set_visible(False)
    key.set_title(title, fontsize=5.0, fontweight="bold", pad=1.0)
    return key


def add_compact_scale_bar(ax, km=5):
    """Add a scale bar using the mini-map's displayed coordinate limits."""
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    x0 = xmin + 0.07 * (xmax - xmin)
    y0 = ymin + 0.08 * (ymax - ymin)
    length = km * 1000
    ax.plot([x0, x0 + length], [y0, y0], color="#242424", lw=0.85, solid_capstyle="butt", zorder=10)
    ax.text(
        x0 + length / 2,
        y0 + 0.035 * (ymax - ymin),
        f"{km} km",
        ha="center",
        va="bottom",
        fontsize=5.0,
        color="#242424",
        zorder=10,
    )


def draw_arch_boundaries(ax, arch, extent, lw=0.45, alpha=0.75):
    """Draw the legacy coloured archetype outlines used outside Figure 2."""
    for k, color in ARCH_COLORS.items():
        mask = np.where(arch == k, 1.0, 0.0)
        ax.contour(mask, levels=[0.5], origin="upper", extent=extent, colors=[color], linewidths=lw, alpha=alpha, zorder=7)


def add_primary_archetype_labels(ax, arch, extent, support=None):
    """Add direct A1-A4 labels without any archetype boundary or fill layer."""
    valid_arch = np.isfinite(arch)
    if support is None:
        support = valid_arch
    else:
        support = np.asarray(support, dtype=bool) & valid_arch

    nrows, ncols = arch.shape
    x_step = (extent[1] - extent[0]) / ncols
    y_step = (extent[3] - extent[2]) / nrows
    structure = np.ones((3, 3), dtype=np.int8)

    for k in range(1, 5):
        primary = valid_arch & np.isclose(arch, k)
        if not primary.any():
            continue
        label_mask = primary & support
        if not label_mask.any():
            label_mask = primary
        components, n_components = ndi_label(label_mask, structure=structure)
        if n_components == 0:
            continue
        sizes = np.bincount(components.ravel())
        sizes[0] = 0
        largest = components == int(np.argmax(sizes))
        interior_distance = distance_transform_edt(largest)
        if k == 3:
            # Place A3 within the upper portion of its largest contiguous area,
            # while retaining an interior supported cell rather than applying
            # an arbitrary cartographic text offset.
            component_rows = np.where(largest)[0]
            upper_cutoff = np.quantile(component_rows, 0.35)
            row_grid = np.indices(largest.shape)[0]
            upper_interior = largest & (row_grid <= upper_cutoff)
            score = np.where(upper_interior, interior_distance, -1.0)
            row, col = np.unravel_index(np.argmax(score), score.shape)
        else:
            row, col = np.unravel_index(np.argmax(interior_distance), interior_distance.shape)
        x = extent[0] + (col + 0.5) * x_step
        y = extent[3] - (row + 0.5) * y_step
        ax.text(
            x,
            y,
            f"A{k}",
            color=ARCH_COLORS[k],
            fontsize=6.1,
            fontweight="bold",
            ha="center",
            va="center",
            zorder=12,
            path_effects=[path_effects.withStroke(linewidth=1.5, foreground="white")],
        )


def map_background(ax, boundary, outline_only=False):
    geography = boundary.dissolve().boundary if outline_only else boundary.boundary
    geography.plot(ax=ax, color="#B8C0C5", linewidth=0.32 if outline_only else 0.25, zorder=6)
    ax.set_aspect("equal")
    ax.set_axis_off()


def draw_archetype_split_map(
    ax,
    arch,
    bivariate_rgba,
    extent,
    archetype,
    facet_label,
    show_scale_bar=False,
    uniform_color=None,
):
    """Show one archetype on the common all-residential spatial frame."""
    valid = np.isfinite(arch)
    primary = valid & np.isclose(arch, archetype)
    selected = primary & (bivariate_rgba[..., 3] > 0)
    ax.imshow(
        np.ma.masked_where(~valid, np.ones_like(arch)),
        origin="upper",
        extent=extent,
        cmap=ListedColormap(["#E4E8EA"]),
        vmin=0,
        vmax=1,
        interpolation="nearest",
        zorder=1,
    )
    split_rgba = np.array(bivariate_rgba, copy=True)
    split_rgba[~selected, 3] = 0.0
    if uniform_color is not None:
        split_rgba[selected, :3] = mpl.colors.to_rgb(uniform_color)
        split_rgba[selected, 3] = 1.0
    ax.imshow(
        split_rgba,
        origin="upper",
        extent=extent,
        interpolation="nearest",
        zorder=2,
    )
    ax.set_aspect("equal")
    ax.set_axis_off()

    # Use one identical frame for all four mini-maps: the complete residential
    # footprint rather than Singapore's full national land extent. This keeps
    # locations directly comparable while using the available panel area well.
    rows, cols = np.where(valid)
    nrows, ncols = arch.shape
    x_step = (extent[1] - extent[0]) / ncols
    y_step = (extent[3] - extent[2]) / nrows
    margin_m = 600.0
    x_left = max(extent[0], extent[0] + cols.min() * x_step - margin_m)
    x_right = min(extent[1], extent[0] + (cols.max() + 1) * x_step + margin_m)
    y_top = min(extent[3], extent[3] - rows.min() * y_step + margin_m)
    y_bottom = max(extent[2], extent[3] - (rows.max() + 1) * y_step - margin_m)
    ax.set_xlim(x_left, x_right)
    ax.set_ylim(y_bottom, y_top)
    ax.set_anchor("W")
    if show_scale_bar:
        add_compact_scale_bar(ax, km=5)
    # Optional subpanel identifier. The manuscript version treats these maps as
    # A1-A4 insets, so only the archetype identifier is drawn there.
    if facet_label:
        ax.text(
            -0.25,
            0.92,
            facet_label,
            transform=ax.transAxes,
            color="#202428",
            fontsize=5.2,
            fontweight="bold",
            ha="right",
            va="top",
            path_effects=[path_effects.withStroke(linewidth=1.15, foreground="white")],
            zorder=8,
        )
    ax.text(
        -0.03 if facet_label else -0.10,
        0.92,
        f"A{archetype}",
        transform=ax.transAxes,
        color=ARCH_COLORS[archetype],
        fontsize=5.2,
        fontweight="bold",
        ha="right",
        va="top",
        path_effects=[path_effects.withStroke(linewidth=1.15, foreground="white")],
        zorder=8,
    )


def export(fig, stem: str):
    fig.savefig(OUT / f"{stem}.svg", bbox_inches="tight")
    fig.savefig(OUT / f"{stem}.pdf", bbox_inches="tight")
    fig.savefig(OUT / f"{stem}.png", dpi=600, bbox_inches="tight")
    fig.savefig(OUT / f"{stem}.tiff", dpi=600, bbox_inches="tight", pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)


def _rectangles_overlap(first, second):
    return not (
        first[1] <= second[0]
        or second[1] <= first[0]
        or first[3] <= second[2]
        or second[3] <= first[2]
    )


def select_figure1_zoom_regions(
    data, width_m=4000.0, height_m=4000.0, representative_columns=None
):
    """Select representative 4-km windows; A3 is matched to its 12-PC centroid."""
    selected = []
    x = data["x_m"].to_numpy(float)
    y = data["y_m"].to_numpy(float)
    archetype = data["archetype"].to_numpy(int)
    for k in range(1, 5):
        target = data.loc[data["archetype"].eq(k)]
        candidates = []
        if k == 3:
            if not representative_columns:
                raise ValueError("A3 zoom selection requires the clustering-space PC columns")
            target_centroid = target[representative_columns].mean().to_numpy(float)
            cell_m = 100.0
            x_edges = np.arange(
                np.floor(data["x_m"].min() / cell_m) * cell_m,
                np.ceil(data["x_m"].max() / cell_m) * cell_m + 2 * cell_m,
                cell_m,
            )
            y_edges = np.arange(
                np.floor(data["y_m"].min() / cell_m) * cell_m,
                np.ceil(data["y_m"].max() / cell_m) * cell_m + 2 * cell_m,
                cell_m,
            )
            all_grid = np.histogram2d(y, x, bins=(y_edges, x_edges))[0]
            target_grid = np.histogram2d(
                target["y_m"], target["x_m"], bins=(y_edges, x_edges)
            )[0]
            kernel = np.ones(
                (int(round(height_m / cell_m)), int(round(width_m / cell_m)))
            )
            approximate_all = convolve2d(all_grid, kernel, mode="valid")
            approximate_target = convolve2d(target_grid, kernel, mode="valid")
            profile_distance = np.zeros_like(approximate_target, dtype=float)
            supported = approximate_target > 0
            for score_column, centroid_value in zip(representative_columns, target_centroid):
                weighted_grid = np.histogram2d(
                    target["y_m"], target["x_m"], bins=(y_edges, x_edges),
                    weights=target[score_column],
                )[0]
                weighted_sum = convolve2d(weighted_grid, kernel, mode="valid")
                window_mean = np.divide(
                    weighted_sum,
                    approximate_target,
                    out=np.zeros_like(weighted_sum, dtype=float),
                    where=supported,
                )
                profile_distance[supported] += (window_mean[supported] - centroid_value) ** 2
            profile_distance[supported] = np.sqrt(profile_distance[supported])
            profile_distance[~supported] = np.inf
            approximate_purity = np.divide(
                approximate_target,
                approximate_all,
                out=np.zeros_like(approximate_target, dtype=float),
                where=approximate_all > 0,
            )
            candidate_cells = np.flatnonzero(
                (approximate_target.ravel() >= 800)
                & (approximate_all.ravel() >= 500)
                & (approximate_purity.ravel() >= 0.90)
                & np.isfinite(profile_distance.ravel())
            )
            candidate_cells = candidate_cells[
                np.argsort(profile_distance.ravel()[candidate_cells])
            ][:2500]
            for flat_index in candidate_cells:
                iy, ix = np.unravel_index(flat_index, approximate_target.shape)
                box = (
                    float(x_edges[ix]),
                    float(x_edges[ix] + width_m),
                    float(y_edges[iy]),
                    float(y_edges[iy] + height_m),
                )
                if any(
                    _rectangles_overlap(
                        box,
                        (prior["x_min"], prior["x_max"], prior["y_min"], prior["y_max"]),
                    )
                    for prior in selected
                ):
                    continue
                inside = (
                    (x >= box[0]) & (x <= box[1]) & (y >= box[2]) & (y <= box[3])
                )
                focal_inside = inside & (archetype == k)
                n_total = int(inside.sum())
                n_target = int(focal_inside.sum())
                focal_rows = data.loc[focal_inside]
                if (
                    n_total < 500 or n_target < 800 or focal_rows.empty
                    or n_target / n_total < 0.90
                ):
                    continue
                centroid_distance = float(np.linalg.norm(
                    focal_rows[representative_columns].mean().to_numpy(float) - target_centroid
                ))
                dominant = (
                    focal_rows.groupby(["planning_area", "subzone"], dropna=False)
                    .size()
                    .sort_values(ascending=False)
                    .index[0]
                )
                candidates.append(
                    {
                        "archetype": k,
                        "planning_area": str(dominant[0]),
                        "subzone": str(dominant[1]),
                        "x_min": box[0],
                        "x_max": box[1],
                        "y_min": box[2],
                        "y_max": box[3],
                        "n_total": n_total,
                        "n_target": n_target,
                        "purity_pct": 100 * n_target / n_total,
                        "selection_method": "100-m exhaustive grid; minimum 12-PC centroid distance",
                        "selection_score": -centroid_distance,
                        "pc_centroid_distance": centroid_distance,
                    }
                )
            candidates.sort(
                key=lambda item: (
                    item["pc_centroid_distance"], -item["n_target"], -item["purity_pct"]
                )
            )
        else:
            for (planning_area, subzone), group in target.groupby(
                ["planning_area", "subzone"], dropna=False
            ):
                if len(group) < 300:
                    continue
                base_x = float(group["x_m"].median())
                base_y = float(group["y_m"].median())
                for offset_x in (-500.0, 0.0, 500.0):
                    for offset_y in (-500.0, 0.0, 500.0):
                        centre_x = base_x + offset_x
                        centre_y = base_y + offset_y
                        box = (
                            centre_x - width_m / 2,
                            centre_x + width_m / 2,
                            centre_y - height_m / 2,
                            centre_y + height_m / 2,
                        )
                        inside = (
                            (x >= box[0])
                            & (x <= box[1])
                            & (y >= box[2])
                            & (y <= box[3])
                        )
                        n_total = int(inside.sum())
                        n_target = int((inside & (archetype == k)).sum())
                        if n_total < 500 or n_target < 400:
                            continue
                        purity = n_target / n_total
                        candidates.append(
                            {
                                "archetype": k,
                                "planning_area": str(planning_area),
                                "subzone": str(subzone),
                                "x_min": box[0],
                                "x_max": box[1],
                                "y_min": box[2],
                                "y_max": box[3],
                                "n_total": n_total,
                                "n_target": n_target,
                                "purity_pct": 100 * purity,
                                "selection_method": "subzone-centred candidates; count-purity score",
                                "selection_score": n_target * purity**6,
                            }
                        )
            candidates.sort(key=lambda item: item["selection_score"], reverse=True)
        available = [
            candidate
            for candidate in candidates
            if not any(
                _rectangles_overlap(
                    (candidate["x_min"], candidate["x_max"], candidate["y_min"], candidate["y_max"]),
                    (prior["x_min"], prior["x_max"], prior["y_min"], prior["y_max"]),
                )
                for prior in selected
            )
        ]
        if not available:
            raise ValueError(f"No non-overlapping Figure 1 zoom region found for A{k}")
        selected.append(available[0])
    return pd.DataFrame(selected)


def smooth_postcode_display_values(data, score_column, cell_m=100.0, sigma_m=300.0):
    """Return display-only Gaussian-smoothed scores sampled at postcode points."""
    x = data["x_m"].to_numpy(float)
    y = data["y_m"].to_numpy(float)
    values = data[score_column].to_numpy(float)
    x0 = np.floor(x.min() / cell_m) * cell_m
    y0 = np.floor(y.min() / cell_m) * cell_m
    nx = int(np.ceil((x.max() - x0) / cell_m)) + 1
    ny = int(np.ceil((y.max() - y0) / cell_m)) + 1
    col = np.clip(((x - x0) / cell_m).astype(int), 0, nx - 1)
    row = np.clip(((y - y0) / cell_m).astype(int), 0, ny - 1)
    counts = np.zeros((ny, nx), dtype=float)
    weighted = np.zeros((ny, nx), dtype=float)
    np.add.at(counts, (row, col), 1.0)
    np.add.at(weighted, (row, col), values)
    sigma_cells = sigma_m / cell_m
    smooth_counts = gaussian_filter(counts, sigma=sigma_cells, mode="constant")
    smooth_weighted = gaussian_filter(weighted, sigma=sigma_cells, mode="constant")
    surface = np.divide(
        smooth_weighted,
        smooth_counts,
        out=np.full_like(smooth_weighted, np.nan),
        where=smooth_counts > 1e-8,
    )
    sampled = surface[row, col]
    return np.where(np.isfinite(sampled), sampled, values)


def rank_figure1_components(data, dictionary, top_n=5):
    """Rank balanced PCA axes by descriptive between-archetype separation."""
    info = dictionary.sort_values("matrix_column_index_zero_based").reset_index(drop=True).copy()
    score_columns = info["score_column"].tolist()
    if len(score_columns) != 12 or not set(score_columns).issubset(data.columns):
        raise ValueError("Figure 1 requires all 12 balanced clustering-PC scores")
    x = data[score_columns].to_numpy(float)
    y = data["archetype"].to_numpy(int)
    grand = x.mean(axis=0)
    total_ss = ((x - grand) ** 2).sum(axis=0)
    between_ss = np.zeros(x.shape[1], dtype=float)
    for archetype in range(1, 5):
        subset = x[y == archetype]
        between_ss += len(subset) * (subset.mean(axis=0) - grand) ** 2
    info["archetype_eta_squared"] = between_ss / total_ss
    info["between_archetype_separation_share_pct"] = 100 * between_ss / between_ss.sum()
    counts = info.groupby("domain")["component_id"].transform("count")
    info["nominal_clustering_geometry_share_pct"] = 100 / (5 * counts)
    info = info.sort_values(
        "between_archetype_separation_share_pct", ascending=False
    ).reset_index(drop=True)
    info["separation_rank"] = np.arange(1, len(info) + 1)
    return info, info.head(top_n).copy()


def rank_figure1_archetype_contrasts(data, dictionary, top_n=5):
    """Rank PCs that most distinguish each archetype from all other postcodes.

    Rankings use the absolute one-versus-rest pooled-standard-deviation effect
    size. The sign is retained so that positive values mean higher balanced PC
    scores in the focal archetype and negative values mean lower scores.
    """
    ordered = dictionary.sort_values("matrix_column_index_zero_based").reset_index(drop=True)
    records = []
    for archetype in range(1, 5):
        focal = data.loc[data["archetype"].eq(archetype)]
        other = data.loc[~data["archetype"].eq(archetype)]
        for component in ordered.itertuples(index=False):
            column = component.score_column
            n_focal = len(focal)
            n_other = len(other)
            pooled_sd = np.sqrt(
                (
                    (n_focal - 1) * focal[column].var(ddof=1)
                    + (n_other - 1) * other[column].var(ddof=1)
                )
                / (n_focal + n_other - 2)
            )
            effect_size = (focal[column].mean() - other[column].mean()) / pooled_sd
            records.append(
                {
                    **component._asdict(),
                    "archetype": archetype,
                    "focal_n": n_focal,
                    "other_n": n_other,
                    "focal_mean": float(focal[column].mean()),
                    "other_mean": float(other[column].mean()),
                    "pooled_sd": float(pooled_sd),
                    "standardized_mean_difference": float(effect_size),
                    "absolute_standardized_mean_difference": float(abs(effect_size)),
                    "contrast_direction": "higher" if effect_size >= 0 else "lower",
                }
            )
    contrasts = pd.DataFrame(records)
    contrasts["contrast_rank"] = contrasts.groupby("archetype")[
        "absolute_standardized_mean_difference"
    ].rank(method="first", ascending=False).astype(int)
    contrasts = contrasts.sort_values(["archetype", "contrast_rank"]).reset_index(drop=True)
    return contrasts, contrasts.loc[contrasts["contrast_rank"].le(top_n)].copy()


def _figure1_heatmap_label(label):
    """Use mathtext for PM2.5 subscripts so all export formats render them."""
    return label.replace("PM₂.₅", r"PM$_{2.5}$")


def _draw_zoom_background(ax, boundary, region, border_color="#C9D0D4", border_width=0.45):
    boundary.boundary.plot(ax=ax, color="#C5CCD0", linewidth=0.22, zorder=1)
    ax.set_xlim(region.x_min, region.x_max)
    ax.set_ylim(region.y_min, region.y_max)
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.add_patch(
        Rectangle(
            (region.x_min, region.y_min),
            region.x_max - region.x_min,
            region.y_max - region.y_min,
            fill=False,
            edgecolor=border_color,
            linewidth=border_width,
            zorder=8,
        )
    )


def _add_local_scale_bar(ax, region, km=1):
    x0 = region.x_min + 0.10 * (region.x_max - region.x_min)
    y0 = region.y_min + 0.09 * (region.y_max - region.y_min)
    scale_line, = ax.plot([x0, x0 + km * 1000], [y0, y0], color="#202428", lw=1.0, zorder=10)
    scale_line.set_path_effects([path_effects.withStroke(linewidth=2.5, foreground="white")])
    ax.text(
        x0 + km * 500, y0 + 150, f"{km} km", ha="center", va="bottom", fontsize=5.0, zorder=10,
        path_effects=[path_effects.withStroke(linewidth=1.5, foreground="white")],
    )


def figure1(post, domain_indicators, pc_scores, pc_dictionary, arch, extent, boundary):
    local_data = post[["postal_code", "x_m", "y_m", "archetype", "housing_group"]].merge(
        domain_indicators[["postal_code", "planning_area", "subzone"]],
        on="postal_code",
        how="inner",
        validate="one_to_one",
    )
    local_data = local_data.merge(pc_scores, on="postal_code", how="inner", validate="one_to_one")
    if len(local_data) != len(post):
        raise ValueError(f"Figure 1 PC merge retained {len(local_data):,} of {len(post):,} postcodes")
    pc_importance, _ = rank_figure1_components(local_data, pc_dictionary)
    dictionary_by_id = pc_dictionary.set_index("component_id", drop=False)
    missing_ids = set(FIGURE1_PANEL_B_COMPONENT_ORDER) - set(dictionary_by_id.index)
    if missing_ids:
        raise ValueError(f"Figure 1 is missing required PC definitions: {sorted(missing_ids)}")
    ordered_components = dictionary_by_id.loc[FIGURE1_PANEL_B_COMPONENT_ORDER].reset_index(drop=True)
    all_columns = ordered_components["score_column"].tolist()
    all_labels = ordered_components["academic_label"].tolist()
    all_display_labels = [
        FIGURE1_PANEL_B_SHORT_LABELS.get(component_id, academic_label)
        for component_id, academic_label in zip(
            ordered_components["component_id"], ordered_components["academic_label"]
        )
    ]
    archetype_contrasts, _ = rank_figure1_archetype_contrasts(
        local_data, pc_dictionary
    )
    displayed_pc_contrasts = archetype_contrasts.loc[
        archetype_contrasts["component_id"].isin(FIGURE1_SHARED_COMPONENT_IDS)
    ].copy()
    display_order = {component_id: rank for rank, component_id in enumerate(FIGURE1_SHARED_COMPONENT_IDS, 1)}
    displayed_pc_contrasts["display_rank"] = displayed_pc_contrasts["component_id"].map(display_order).astype(int)
    displayed_pc_contrasts["short_label"] = displayed_pc_contrasts["component_id"].map(FIGURE1_SHORT_PC_LABELS)
    displayed_pc_contrasts = displayed_pc_contrasts.sort_values(
        ["archetype", "display_rank"]
    ).reset_index(drop=True)
    zooms = select_figure1_zoom_regions(
        local_data, representative_columns=all_columns
    )

    figure1_height = 8.75 if not FIGURE1_SHOW_NAVIGATIONAL_HEADINGS else 9.0157
    header_height = 0.06 if not FIGURE1_SHOW_NAVIGATIONAL_HEADINGS else 0.16
    figure1_hspace = 0.30 if not FIGURE1_SHOW_NAVIGATIONAL_HEADINGS else 0.36
    fig = plt.figure(figsize=(7.2047, figure1_height))
    gs = fig.add_gridspec(
        7, 6, height_ratios=[2.25, header_height, 1, 1, 1, 1, 0.10],
        left=0.035, right=0.985, bottom=0.065,
        top=0.980 if not FIGURE1_SHOW_NAVIGATIONAL_HEADINGS else 0.965,
        hspace=figure1_hspace, wspace=0.08,
    )
    archetype_cmap = ListedColormap([ARCH_COLORS[i] for i in range(1, 5)])
    archetype_norm = BoundaryNorm([0.5, 1.5, 2.5, 3.5, 4.5], 4)
    pc_norm = TwoSlopeNorm(vmin=-2, vcenter=0, vmax=2)
    pc_cmap = mpl.colors.LinearSegmentedColormap.from_list(
        "domain_blue_neutral_red",
        ["#2166AC", "#F2F2F2", "#B2182B"],
        N=256,
    )

    axm = fig.add_subplot(gs[0, :4])
    axm.imshow(
        np.ma.masked_invalid(arch), origin="upper", extent=extent,
        cmap=archetype_cmap, norm=archetype_norm, interpolation="nearest",
    )
    map_background(axm, boundary)
    for region in zooms.itertuples(index=False):
        frame = Rectangle(
            (region.x_min, region.y_min), region.x_max - region.x_min, region.y_max - region.y_min,
            fill=False, edgecolor=ARCH_COLORS[int(region.archetype)], linewidth=0.9, zorder=10,
        )
        frame.set_path_effects([
            path_effects.withStroke(linewidth=3.0, foreground="white"),
            path_effects.Normal(),
        ])
        axm.add_patch(frame)
    axm.text(-0.025, 1.035 if not FIGURE1_SHOW_NAVIGATIONAL_HEADINGS else 1.085,
             "a", transform=axm.transAxes, fontsize=9, fontweight="bold", va="bottom")
    if FIGURE1_SHOW_NAVIGATIONAL_HEADINGS:
        axm.set_title(
            "Residential urban-exposome contexts and data-selected zoom regions",
            loc="left", fontweight="bold", pad=20,
        )
    axm.text(
        0.0, 1.012 if not FIGURE1_SHOW_NAVIGATIONAL_HEADINGS else 1.035,
        "n = 101,545 residential-proxy postcodes", transform=axm.transAxes,
        color="#68737D", va="bottom",
    )
    add_scale_bar(axm, extent, km=5, x_fraction=0.02, y_fraction=0.13)
    handles = [
        Line2D([0], [0], marker="o", lw=0, markerfacecolor=ARCH_COLORS[k], markeredgecolor="none", label=f"A{k}")
        for k in range(1, 5)
    ]
    axm.legend(
        handles=handles, loc="lower center", bbox_to_anchor=(0.58, -0.02), frameon=False,
        ncol=4, handletextpad=0.35, columnspacing=1.0, labelspacing=0.45,
    )

    axh = fig.add_subplot(gs[0, 4:])
    profile_matrix = local_data.groupby("archetype")[all_columns].mean().loc[range(1, 5)].to_numpy(float)
    axh.imshow(profile_matrix.T, cmap=pc_cmap, norm=pc_norm, aspect="auto")
    axh.set_xticks(range(4), [f"A{k}" for k in range(1, 5)])
    axh.set_yticks(range(len(all_columns)), [_figure1_heatmap_label(label) for label in all_display_labels])
    axh.tick_params(length=0, axis="both", labelsize=5.0, pad=1.4)
    axh.set_xticks(np.arange(-0.5, 4, 1), minor=True)
    axh.set_yticks(np.arange(-0.5, len(all_columns), 1), minor=True)
    axh.grid(which="minor", color="white", linewidth=1.0)
    axh.tick_params(which="minor", bottom=False, left=False)
    for k, tick in enumerate(axh.get_xticklabels(), start=1):
        tick.set_color(ARCH_COLORS[k])
        tick.set_fontweight("bold")
    for i in range(len(all_columns)):
        for j in range(4):
            value = profile_matrix[j, i]
            axh.text(
                j, i, f"{value:+.2f}", ha="center", va="center", fontsize=5.0,
                color="white" if abs(value) > 0.55 else "#202428",
            )
    for spine in axh.spines.values():
        spine.set_color("white")
        spine.set_linewidth(1.2)
    if FIGURE1_SHOW_NAVIGATIONAL_HEADINGS:
        axh.set_title(
            "All 12 balanced PCs used for clustering", loc="left",
            fontweight="bold", pad=20,
        )
    axh.text(
        -0.05, 1.035 if not FIGURE1_SHOW_NAVIGATIONAL_HEADINGS else 1.085,
        "b", transform=axh.transAxes, fontsize=9, fontweight="bold", va="bottom",
    )
    if FIGURE1_SHOW_NAVIGATIONAL_HEADINGS:
        axh.text(
            0.0, 1.035, "Archetype centroids in the common clustering space",
            transform=axh.transAxes, color="#68737D", va="bottom",
        )

    local_header = fig.add_subplot(gs[1, 0])
    local_header.set_axis_off()
    if FIGURE1_SHOW_NAVIGATIONAL_HEADINGS:
        local_header.text(
            0.0, 0.20, "Local archetype", transform=local_header.transAxes,
            fontweight="bold", fontsize=5.5, va="bottom",
        )
    contrast_header = fig.add_subplot(gs[1, 1:])
    contrast_header.set_axis_off()
    if FIGURE1_SHOW_NAVIGATIONAL_HEADINGS:
        contrast_header.text(
            0.0, 0.20, "Five shared exposome dimensions",
            transform=contrast_header.transAxes, ha="left", va="bottom",
            color="#202428", fontweight="bold", fontsize=5.5,
        )

    zoom_postcodes = []
    zoom_pc_display_rows = []
    summary_rows = []
    panel_labels = ["c", "d", "e", "f"]
    for row_index, region in enumerate(zooms.itertuples(index=False), start=1):
        grid_row = row_index + 1
        k = int(region.archetype)
        local = local_data.loc[
            local_data["x_m"].between(region.x_min, region.x_max)
            & local_data["y_m"].between(region.y_min, region.y_max)
        ].copy()
        local["zoom_archetype"] = k
        local["zoom_planning_area"] = region.planning_area
        local["zoom_subzone"] = region.subzone
        selected_local = local.loc[local["archetype"].eq(k)]
        zoom_postcodes.append(selected_local)
        row_components = displayed_pc_contrasts.loc[
            displayed_pc_contrasts["archetype"].eq(k)
        ].sort_values("display_rank")
        row_columns = row_components["score_column"].tolist()
        pc_means = {column: float(selected_local[column].mean()) for column in row_columns}
        summary_rows.append({**region._asdict(), **{f"mean_{column}": value for column, value in pc_means.items()}})

        local_ax = fig.add_subplot(gs[grid_row, 0])
        local_ax.scatter(
            selected_local["x_m"], selected_local["y_m"],
            c=ARCH_COLORS[k],
            s=1.15, linewidth=0, rasterized=True, zorder=3,
        )
        _draw_zoom_background(local_ax, boundary, region, border_color=ARCH_COLORS[k], border_width=0.8)
        _add_local_scale_bar(local_ax, region)
        local_ax.text(-0.18, 1.14, panel_labels[row_index - 1], transform=local_ax.transAxes, fontweight="bold", fontsize=9, va="bottom")
        local_ax.text(
            0.0, 1.14, f"A{k} · {ARCH_NAMES[k]}", transform=local_ax.transAxes,
            color=ARCH_COLORS[k], fontweight="bold", fontsize=5.7, va="bottom",
        )
        local_ax.text(
            0.0, 1.05, str(region.planning_area), transform=local_ax.transAxes,
            color="#202428", fontsize=5.0, va="bottom",
        )
        for column_index, component in enumerate(row_components.itertuples(index=False), start=1):
            score_column = component.score_column
            academic_label = component.academic_label
            short_label = component.short_label
            ax = fig.add_subplot(gs[grid_row, column_index])
            raw_values = selected_local[score_column].to_numpy(float)
            smoothing_applied = component.domain == "Pollution"
            display_values = (
                smooth_postcode_display_values(selected_local, score_column)
                if smoothing_applied
                else raw_values
            )
            ax.scatter(
                selected_local["x_m"], selected_local["y_m"],
                c=np.clip(display_values, -2, 2),
                cmap=pc_cmap, norm=pc_norm, s=1.15, linewidth=0, rasterized=True, zorder=3,
            )
            display_source = selected_local[["postal_code", "x_m", "y_m"]].copy()
            display_source["archetype"] = k
            display_source["component_id"] = component.component_id
            display_source["academic_label"] = academic_label
            display_source["display_rank"] = int(component.display_rank)
            display_source["one_vs_rest_contrast_rank"] = int(component.contrast_rank)
            display_source["short_label"] = short_label
            display_source["raw_balanced_pc_score"] = raw_values
            display_source["display_balanced_pc_score"] = display_values
            display_source["display_smoothing"] = (
                "Gaussian sigma=300 m; visualization only" if smoothing_applied else "none"
            )
            zoom_pc_display_rows.append(display_source)
            _draw_zoom_background(ax, boundary, region)
            display_label = textwrap.fill(_figure1_heatmap_label(short_label), width=17)
            if row_index == 1:
                ax.text(
                    0.5, 1.17, display_label,
                    transform=ax.transAxes, ha="center", va="bottom", fontweight="bold", fontsize=5.0,
                )
            ax.text(
                0.97, 0.04, f"mean {pc_means[score_column]:+.2f}", transform=ax.transAxes,
                ha="right", va="bottom", fontsize=5.0, color="#202428",
                path_effects=[path_effects.withStroke(linewidth=1.25, foreground="white")], zorder=9,
            )

    cax = fig.add_subplot(gs[6, 2:5])
    cb = fig.colorbar(mpl.cm.ScalarMappable(norm=pc_norm, cmap=pc_cmap), cax=cax, orientation="horizontal", ticks=[-2, -1, 0, 1, 2])
    cb.set_label("Balanced PC score (0 = citywide mean; values clipped at ±2)", labelpad=2)
    export(fig, "Figure1_Residential_urban_exposome_contexts")

    zoom_summary = pd.DataFrame(summary_rows)
    zoom_detail = pd.concat(zoom_postcodes, ignore_index=True)
    zoom_pc_display = pd.concat(zoom_pc_display_rows, ignore_index=True)
    zoom_summary.to_csv(SOURCE / "Figure1_zoom_region_summary.csv", index=False)
    zoom_detail.to_csv(SOURCE / "Figure1_zoom_region_postcodes.csv", index=False)
    zoom_pc_display.to_csv(SOURCE / "Figure1_zoom_PC_display_values.csv", index=False)
    pc_importance.to_csv(SOURCE / "Figure1_all_PC_archetype_separation.csv", index=False)
    archetype_contrasts.to_csv(SOURCE / "Figure1_all_archetype_PC_contrasts.csv", index=False)
    displayed_pc_contrasts.to_csv(SOURCE / "Figure1_prespecified5_PC_contrasts.csv", index=False)
    pd.DataFrame(profile_matrix, index=[f"A{k}" for k in range(1, 5)], columns=all_labels).to_csv(
        SOURCE / "Figure1_all12_PC_archetype_profiles.csv"
    )
    for obsolete in (
        "Figure1_top5_PC_selection.csv",
        "Figure1_top5_PC_archetype_profiles.csv",
        "Figure1_archetype_specific_top5_PC_contrasts.csv",
    ):
        (SOURCE / obsolete).unlink(missing_ok=True)
    zoom_list = list(zooms.itertuples(index=False))
    zoom_qa = {
        "postcode_rows": int(len(local_data)),
        "zoom_regions": int(len(zoom_summary)),
        "archetypes": zoom_summary["archetype"].astype(int).tolist(),
        "minimum_zoom_postcodes": int(zoom_summary["n_total"].min()),
        "minimum_archetype_purity_pct": float(zoom_summary["purity_pct"].min()),
        "all_zoom_widths_m": (zoom_summary["x_max"] - zoom_summary["x_min"]).astype(float).tolist(),
        "all_zoom_heights_m": (zoom_summary["y_max"] - zoom_summary["y_min"]).astype(float).tolist(),
        "a3_target_postcodes": int(
            zoom_summary.loc[zoom_summary["archetype"].eq(3), "n_target"].iloc[0]
        ),
        "a3_selection_method": str(
            zoom_summary.loc[zoom_summary["archetype"].eq(3), "selection_method"].iloc[0]
        ),
        "a3_pc_centroid_distance": float(
            zoom_summary.loc[zoom_summary["archetype"].eq(3), "pc_centroid_distance"].iloc[0]
        ),
        "displayed_postcode_rows": int(len(zoom_detail)),
        "all_displayed_postcodes_match_focal_archetype": bool(
            (zoom_detail["archetype"].astype(int) == zoom_detail["zoom_archetype"].astype(int)).all()
        ),
        "pm_display_smoothing": sorted(
            zoom_pc_display.loc[
                zoom_pc_display["component_id"].str.startswith("pollution_"), "display_smoothing"
            ].unique().tolist()
        ),
        "all_pc_component_ids": ordered_components["component_id"].tolist(),
        "panel_b_component_order": ordered_components["component_id"].tolist(),
        "archetype_displayed_component_ids": {
            str(k): displayed_pc_contrasts.loc[
                displayed_pc_contrasts["archetype"].eq(k), "component_id"
            ].tolist()
            for k in range(1, 5)
        },
        "all_regions_non_overlapping": bool(all(
            not _rectangles_overlap(
                (first.x_min, first.x_max, first.y_min, first.y_max),
                (second.x_min, second.x_max, second.y_min, second.y_max),
            )
            for i, first in enumerate(zoom_list)
            for second in zoom_list[i + 1 :]
        )),
    }
    zoom_qa["pass"] = bool(
        zoom_qa["postcode_rows"] == 101545 and zoom_qa["zoom_regions"] == 4
        and zoom_qa["archetypes"] == [1, 2, 3, 4] and zoom_qa["minimum_zoom_postcodes"] >= 500
        and zoom_qa["minimum_archetype_purity_pct"] >= 90 and zoom_qa["all_regions_non_overlapping"]
        and all(np.isclose(value, 4000.0) for value in zoom_qa["all_zoom_widths_m"])
        and all(np.isclose(value, 4000.0) for value in zoom_qa["all_zoom_heights_m"])
        and zoom_qa["a3_target_postcodes"] >= 800
        and zoom_qa["a3_selection_method"] == "100-m exhaustive grid; minimum 12-PC centroid distance"
        and zoom_qa["a3_pc_centroid_distance"] < 0.60
        and zoom_qa["displayed_postcode_rows"] == int(zoom_summary["n_target"].sum())
        and zoom_qa["all_displayed_postcodes_match_focal_archetype"]
        and zoom_qa["pm_display_smoothing"] == ["Gaussian sigma=300 m; visualization only"]
        and len(zoom_qa["all_pc_component_ids"]) == 12
        and zoom_qa["panel_b_component_order"] == FIGURE1_PANEL_B_COMPONENT_ORDER
        and zoom_qa["archetype_displayed_component_ids"] == {
            str(k): FIGURE1_SHARED_COMPONENT_IDS for k in range(1, 5)
        }
    )
    (OUT / "Figure1_zoom_region_QA.json").write_text(json.dumps(zoom_qa, indent=2), encoding="utf-8")
    if not zoom_qa["pass"]:
        raise RuntimeError(f"Figure 1 zoom-region QA failed: {zoom_qa}")


def figure2(
    post,
    exposome_selected,
    arch,
    efficacy,
    access_distance,
    extent,
    boundary,
    *,
    output_stem="Figure2_Cooling_efficacy_and_service_footprints",
    association_source_name="Figure2cd_top4_pc_associations.csv",
    component_note="Top four PCs per archetype, ranked by mean |association|",
    footer_note=(
        "PCs are ranked by mean absolute HDB/non-HDB Q75−Q25 association; "
        "lines are planning-area-clustered 95% CIs. A4 efficacy associations "
        "are all <0.001 °C per component IQR."
    ),
):
    fig = plt.figure(figsize=(7.2047, 7.0866))  # 183 x 180 mm
    gs = fig.add_gridspec(
        2,
        2,
        width_ratios=[1.82, 0.58],
        height_ratios=[1, 1],
        left=0.035,
        right=0.985,
        bottom=0.125,
        top=0.895,
        hspace=0.50,
        wspace=0.20,
    )
    map_top = gs[0, 0].subgridspec(1, 2, width_ratios=[1.12, 0.68], wspace=-0.08)
    map_bottom = gs[1, 0].subgridspec(1, 2, width_ratios=[1.12, 0.68], wspace=-0.08)
    ax1, ax2 = fig.add_subplot(map_top[0, 0]), fig.add_subplot(map_bottom[0, 0])
    locator_top = map_top[0, 1].subgridspec(4, 1, hspace=0.015)
    locator_bottom = map_bottom[0, 1].subgridspec(4, 1, hspace=0.015)
    locator_axes_top = {k: fig.add_subplot(locator_top[k - 1, 0]) for k in range(1, 5)}
    locator_axes_bottom = {k: fig.add_subplot(locator_bottom[k - 1, 0]) for k in range(1, 5)}
    ax3, ax4 = fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[1, 1])
    # Centre the locator columns in the visual gutter between the main maps
    # and the analytical panels without changing their size or shared extent.
    mini_map_shift = 0.038
    for locator_ax in (*locator_axes_top.values(), *locator_axes_bottom.values()):
        pos = locator_ax.get_position()
        locator_ax.set_position([pos.x0 + mini_map_shift, pos.y0, pos.width, pos.height])
    panel_a_frame = fig.add_subplot(gs[0, 0], frameon=False)
    panel_b_frame = fig.add_subplot(gs[1, 0], frameon=False)
    for frame_ax in (panel_a_frame, panel_b_frame):
        frame_ax.set_axis_off()
        frame_ax.set_zorder(20)
    hdb_density, hdb_cells = hdb_density_surface(post, efficacy.shape)

    # Smooth values only within their original analytical support.  Reapplying
    # the mask prevents Gaussian smoothing from visually extending coverage
    # into neighbouring cells that were not assessed.
    efficacy_support = np.isfinite(efficacy)
    eff = np.where(efficacy_support, smooth_masked(efficacy), np.nan)
    biv_eff, eff_class, density_class = bivariate_cooling_hdb(eff, hdb_density)
    ax1.imshow(biv_eff, origin="upper", extent=extent, interpolation="nearest")
    map_background(ax1, boundary, outline_only=True)
    ax1.set_anchor("E")
    add_primary_archetype_labels(ax1, arch, extent, support=efficacy_support)
    add_scale_bar(ax1, extent, x_fraction=0.05)
    panel_a_frame.text(-0.045, 1.025, "a1", transform=panel_a_frame.transAxes, fontsize=9, fontweight="bold", va="bottom")
    panel_a_frame.text(0, 1.025, "Cooling efficacy relative to HDB concentration", transform=panel_a_frame.transAxes, fontsize=7.2, fontweight="bold", va="bottom")
    panel_a_frame.text(0, 0.985, "Efficacy per +10 pp greenery × HDB dwelling density", transform=panel_a_frame.transAxes, color="#68737D", va="top")
    add_bivariate_key(
        ax1,
        ["≤0", "0–0.10", "≥0.10"],
        "Cooling efficacy\\n(°C per +10 pp)",
        "Bivariate legend",
    )
    for k in range(1, 5):
        draw_archetype_split_map(
            locator_axes_top[k],
            arch,
            biv_eff,
            extent,
            k,
            f"a{k + 1}",
            show_scale_bar=(k == 4),
        )

    access_support = np.isfinite(access_distance)
    biv_access, access_class, _ = bivariate_access_hdb(access_distance, hdb_density)
    ax2.imshow(biv_access, origin="upper", extent=extent, interpolation="nearest")
    map_background(ax2, boundary, outline_only=True)
    ax2.set_anchor("E")
    add_primary_archetype_labels(ax2, arch, extent, support=access_support)
    add_scale_bar(ax2, extent, x_fraction=0.05)
    panel_b_frame.text(-0.045, 1.025, "b1", transform=panel_b_frame.transAxes, fontsize=9, fontweight="bold", va="bottom")
    panel_b_frame.text(0, 1.025, "Cooling proximity relative to HDB concentration", transform=panel_b_frame.transAxes, fontsize=7.2, fontweight="bold", va="bottom")
    panel_b_frame.text(0, 0.985, "Proximity to nearest modelled cooled footprint × HDB density", transform=panel_b_frame.transAxes, color="#68737D", va="top")
    add_bivariate_key(
        ax2,
        [">800", "400–800", "≤400"],
        "Cooling proximity\\n(distance, m)",
        "Bivariate legend",
    )
    for k in range(1, 5):
        draw_archetype_split_map(
            locator_axes_bottom[k],
            arch,
            biv_access,
            extent,
            k,
            f"b{k + 1}",
            show_scale_bar=(k == 4),
        )

    component_counts = (
        exposome_selected.drop_duplicates(["outcome", "archetype", "component_id"])
        .groupby(["outcome", "archetype"])
        .size()
    )
    if component_counts.empty or component_counts.nunique() != 1:
        raise ValueError(
            "Figure 2 requires the same number of PCA components for every archetype and outcome"
        )
    components_per_archetype = int(component_counts.iloc[0])
    expected_total = 4 * 2 * 2 * components_per_archetype
    if len(exposome_selected) != expected_total:
        raise ValueError(
            f"Expected {expected_total} PCA-component associations; found {len(exposome_selected)}"
        )
    outcomes = [
        (
            ax3,
            "c",
            "Exposome associations with cooling efficacy",
            "cooling_efficacy",
            "Within-archetype IQR association with cooling efficacy (°C per +10 pp greenery)",
            "positive = greater modelled efficacy",
        ),
        (
            ax4,
            "d",
            "Exposome associations with cooling proximity",
            "cooling_proximity",
            "Within-archetype IQR association with cooling proximity (m)",
            "positive = closer to a cooled footprint",
        ),
    ]
    for ax, panel_label, panel_title, outcome, xlabel, direction_note in outcomes:
        data = exposome_selected.loc[exposome_selected["outcome"].eq(outcome)].copy()
        data = data.sort_values(["archetype", "selection_rank", "housing_group"]).reset_index(drop=True)
        expected_outcome_rows = 4 * 2 * components_per_archetype
        if len(data) != expected_outcome_rows:
            raise ValueError(
                f"Expected {expected_outcome_rows} selected {outcome} housing-specific rows; "
                f"found {len(data)}"
            )
        rows = data.drop_duplicates(["archetype", "component_id"]).sort_values(
            ["archetype", "selection_rank"]
        ).reset_index(drop=True)
        expected_plot_rows = 4 * components_per_archetype
        if len(rows) != expected_plot_rows:
            raise ValueError(
                f"Expected {expected_plot_rows} selected {outcome} PCA components; found {len(rows)}"
            )
        yy = np.arange(len(rows))[::-1]
        limit = 1.08 * float(np.nanmax(np.abs(data[["ci_low", "ci_high"]].to_numpy(float))))
        ax.set_xlim(-limit, limit)
        ax.set_ylim(-0.60, len(rows) - 0.40)
        ax.axvline(0, color="#5E666C", lw=0.72, zorder=1)
        for y, row in zip(yy, rows.itertuples(index=False)):
            parent = int(row.archetype)
            color = ARCH_COLORS[parent]
            ax.axhspan(
                y - 0.47,
                y + 0.47,
                color=mpl.colors.to_rgba(color, 0.045),
                lw=0,
                zorder=0,
            )
            pair = data.loc[
                data["archetype"].eq(parent)
                & data["component_id"].eq(row.component_id)
            ]
            if set(pair["housing_group"]) != {"HDB", "Non-HDB"}:
                raise ValueError(f"Missing paired housing estimates for A{parent} {row.component_id}")
            estimates = dict(zip(pair["housing_group"], pair["estimate"].astype(float)))
            ax.plot(
                [estimates["Non-HDB"], estimates["HDB"]],
                [y - 0.12, y + 0.12],
                color=mpl.colors.to_rgba(color, 0.38),
                lw=0.65,
                zorder=2,
            )
            for housing_group, y_offset, marker, filled in (
                ("HDB", 0.12, "o", True),
                ("Non-HDB", -0.12, "D", False),
            ):
                estimate = pair.loc[pair["housing_group"].eq(housing_group)].iloc[0]
                ax.plot(
                    [float(estimate.ci_low), float(estimate.ci_high)],
                    [y + y_offset, y + y_offset],
                    color=color,
                    lw=0.85,
                    alpha=0.82,
                    solid_capstyle="round",
                    zorder=3,
                )
                ax.scatter(
                    float(estimate.estimate),
                    y + y_offset,
                    s=16 if filled else 15,
                    marker=marker,
                    facecolor=color if filled else "white",
                    edgecolor=color,
                    lw=0.8,
                    zorder=4,
                )
        for group_index in range(1, 4):
            boundary_y = len(rows) - components_per_archetype * group_index - 0.5
            ax.axhline(boundary_y, color="white", lw=2.0, zorder=1)
            ax.axhline(boundary_y, color="#D7DDE1", lw=0.45, zorder=1)
        tick_labels = []
        for row in rows.itertuples(index=False):
            label = str(getattr(row, "figure_label", row.academic_label)).replace(
                "PM₂.₅", r"PM$_{2.5}$"
            )
            tick_labels.append(
                f"A{int(row.archetype)}  {label}"
                if int(row.selection_rank) == 1
                else f"      {label}"
            )
        ax.set_yticks(yy, tick_labels)
        for tick, row in zip(ax.get_yticklabels(), rows.itertuples(index=False)):
            parent = int(row.archetype)
            tick.set_color(ARCH_COLORS[parent])
            tick.set_fontweight("bold" if int(row.selection_rank) == 1 else "normal")
            tick.set_fontsize(5.0)
        ax.set_xlabel(f"{xlabel}\\n{direction_note}", fontsize=5.1, labelpad=4)
        strip_axes(ax)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0, pad=2)
        ax.tick_params(axis="x", labelsize=5.0)
        add_panel_label(ax, panel_label)
        ax.set_title(panel_title, loc="left", fontweight="bold", pad=15, fontsize=6.8)
        ax.text(
            0,
            1.018,
            component_note,
            transform=ax.transAxes,
            color="#68737D",
            fontsize=5.0,
            va="bottom",
        )
    housing_key = [
        Line2D([0], [0], marker="o", color="#555555", markerfacecolor="#555555", lw=0, label="HDB"),
        Line2D([0], [0], marker="D", color="#555555", markerfacecolor="white", lw=0, label="Non-HDB"),
    ]
    fig.legend(handles=housing_key, loc="lower right", ncol=2, frameon=False, bbox_to_anchor=(0.987, 0.052), fontsize=5.0)
    fig.text(0.035, 0.032, footer_note, color="#68737D", fontsize=5.0)
    fig.text(0.035, 0.014, "Models adjust for housing group, coordinates and planning-area fixed effects. Joint FDR q values are reported in Source Data. Associations are ecological and descriptive, not independent or causal effects.", color="#68737D", fontsize=5.0)
    fig.suptitle("Urban exposome context differentiates residential cooling performance", x=0.01, y=0.988, ha="left", fontsize=9.2, fontweight="bold")
    export(fig, output_stem)
    hdb_cells.to_csv(SOURCE / "Figure2ab_HDB_dwelling_cells_for_density_surface.csv", index=False)
    post[
        [
            "postal_code",
            "housing_group",
            "archetype",
            "nested_subtype",
            "distance_to_nearest_cooling_service_footprint_m",
            "cooling_service_access_level",
            "cooling_service_access_class",
            "hdb_dwelling_units",
        ]
    ].rename(
        columns={
            "cooling_service_access_level": "cooling_proximity_level",
            "cooling_service_access_class": "cooling_proximity_class",
        }
    ).to_csv(SOURCE / "Figure2b_postcode_cooling_proximity.csv", index=False)
    pd.DataFrame(
        [
            {
                "panel": "Figure 1a",
                "surface": "all-residential archetype support",
                "n_100m_cells": int(np.isfinite(arch).sum()),
            },
            {
                "panel": "Figure 2a",
                "surface": "cooling-efficacy support",
                "n_100m_cells": int(efficacy_support.sum()),
            },
            {
                "panel": "Figure 2b",
                "surface": "all-residential postcode proximity support",
                "n_100m_cells": int(access_support.sum()),
            },
        ]
    ).to_csv(SOURCE / "Figure1a_Figure2ab_spatial_coverage_audit.csv", index=False)
    pd.DataFrame(
        [
            {"panel": "both", "dimension": "HDB dwelling density", "class": "low", "criterion": "<1000 units km-2"},
            {"panel": "both", "dimension": "HDB dwelling density", "class": "medium", "criterion": "1000 to <3000 units km-2"},
            {"panel": "both", "dimension": "HDB dwelling density", "class": "high", "criterion": ">=3000 units km-2"},
            {"panel": "Figure 2a", "dimension": "cooling efficacy", "class": "low_or_none", "criterion": "<=0 degrees C per +10 percentage points greenery"},
            {"panel": "Figure 2a", "dimension": "cooling efficacy", "class": "moderate", "criterion": ">0 to <0.10 degrees C per +10 percentage points greenery"},
            {"panel": "Figure 2a", "dimension": "cooling efficacy", "class": "high", "criterion": ">=0.10 degrees C per +10 percentage points greenery"},
            {"panel": "Figure 2b", "dimension": "postcode proximity to cooled footprint", "class": "limited", "criterion": ">800 m straight-line distance"},
            {"panel": "Figure 2b", "dimension": "postcode proximity to cooled footprint", "class": "moderate", "criterion": ">400 to 800 m straight-line distance"},
            {"panel": "Figure 2b", "dimension": "postcode proximity to cooled footprint", "class": "high", "criterion": "<=400 m straight-line distance, including postcodes inside a footprint"},
        ]
    ).to_csv(SOURCE / "Figure2ab_bivariate_classification_key.csv", index=False)
    exposome_selected.to_csv(SOURCE / association_source_name, index=False)


def figure2_trial_five_pcs(
    post, all_pc_associations, arch, efficacy, access_distance, extent, boundary
):
    """Render a non-destructive Figure 2 trial using Figure 1's five shared PCs."""
    trial = all_pc_associations.loc[
        all_pc_associations["component_id"].isin(FIGURE1_SHARED_COMPONENT_IDS)
    ].copy()
    rank_map = {
        component_id: rank
        for rank, component_id in enumerate(FIGURE1_SHARED_COMPONENT_IDS, start=1)
    }
    trial["selection_rank"] = trial["component_id"].map(rank_map)
    trial["figure_label"] = trial["component_id"].map(FIGURE1_SHORT_PC_LABELS)
    trial = trial.sort_values(
        ["outcome", "archetype", "selection_rank", "housing_group"]
    ).reset_index(drop=True)
    if len(trial) != 80 or trial["figure_label"].isna().any():
        raise ValueError(
            f"Expected 80 complete prespecified five-PC association rows; found {len(trial)}"
        )
    figure2(
        post,
        trial,
        arch,
        efficacy,
        access_distance,
        extent,
        boundary,
        output_stem="Figure2_TRIAL_Prespecified_five_PCs",
        association_source_name="Figure2cd_TRIAL_prespecified_five_pc_associations.csv",
        component_note="Five prespecified PCs shared with Figure 1",
        footer_note=(
            "Five prespecified PCs match Figure 1; each PC is fitted separately. "
            "Estimates are within-archetype HDB/non-HDB Q75−Q25 contrasts; lines "
            "are planning-area-clustered 95% CIs."
        ),
    )


def weighted_quantile(values, quantiles, weights):
    values = np.asarray(values, float)
    weights = np.asarray(weights, float)
    order = np.argsort(values)
    values, weights = values[order], weights[order]
    cdf = np.cumsum(weights) - 0.5 * weights
    cdf = cdf / weights.sum()
    return np.interp(quantiles, cdf, values)


def figure3(post, decay, patch):
    fig = plt.figure(figsize=(7.2047, 4.6457))  # 183 x 118 mm
    gs = fig.add_gridspec(1, 3, width_ratios=[1.25, 0.85, 0.95], wspace=0.42)
    ax = fig.add_subplot(gs[0, 0])
    d = decay[(decay.context_level == "archetype")].copy()
    for k in range(1, 5):
        q = d[np.isclose(pd.to_numeric(d.context, errors="coerce"), k)].sort_values("distance_bin_mid_m")
        ax.fill_between(q.distance_bin_mid_m, q.ci_low_c, q.ci_high_c, color=ARCH_COLORS[k], alpha=0.12, lw=0)
        ax.plot(q.distance_bin_mid_m, q.mean_cooling_c, color=ARCH_COLORS[k], label=f"A{k}")
        ax.scatter(q.distance_bin_mid_m, q.median_cooling_c, color=ARCH_COLORS[k], s=6, alpha=0.75)
    ax.axhline(0, color="#555555", lw=0.65)
    ax.axhline(0.10, color="#8F8F8F", lw=0.6, ls="--")
    ax.axvspan(-50, 50, color="#DDE4E8", alpha=0.55, zorder=-1)
    ax.text(0, ax.get_ylim()[1], "source patch", ha="center", va="top", fontsize=5.2, color="#68737D")
    ax.set_xlabel("Distance from green-source edge (m)")
    ax.set_ylabel("Morphology-adjusted cooling contrast (°C)")
    ax.set_title("No archetype has a uniform\\nexternal cooling halo", loc="left", fontweight="bold", pad=7)
    ax.legend(frameon=False, ncol=4, loc="upper right")
    strip_axes(ax)
    add_panel_label(ax, "a")

    ax2 = fig.add_subplot(gs[0, 1])
    pp = patch.copy()
    pp["archetype"] = pp.archetype.astype(int)
    for k in range(1, 5):
        vals = pp.loc[pp.archetype == k, "external_footprint_radius_m"].astype(float).to_numpy()
        # Deterministic display-only jitter prevents coincident patch markers.
        jitter = 0.055 * np.sin(np.arange(len(vals)) * 2.399963)
        ax2.scatter(np.full(len(vals), k) + jitter, vals, s=7, color=ARCH_COLORS[k], alpha=0.42, edgecolor="none")
        q = np.quantile(vals, [0.25, 0.5, 0.75])
        ax2.plot([k - 0.16, k + 0.16], [q[1], q[1]], color="#20252A", lw=1.2)
        ax2.plot([k, k], [q[0], q[2]], color="#20252A", lw=2.2)
    ax2.axhline(0, color="#777777", lw=0.6)
    ax2.set_xticks(range(1, 5), [f"A{k}" for k in range(1, 5)])
    for t, k in zip(ax2.get_xticklabels(), range(1, 5)):
        t.set_color(ARCH_COLORS[k]); t.set_fontweight("bold")
    ax2.set_ylabel("Patch-specific external footprint radius (m)")
    ax2.set_title("Only a subset of patches\\npropagates cooling", loc="left", fontweight="bold", pad=7)
    strip_axes(ax2)
    add_panel_label(ax2, "b")

    ax3 = fig.add_subplot(gs[0, 2])
    supported = post[post.cooling_service_supported.astype(bool)].copy()
    supported["service"] = supported.cooling_service_received_c.astype(float)
    rows = []
    y = np.arange(4)[::-1]
    for i, k in enumerate(range(1, 5)):
        vals = supported.loc[supported.archetype.astype(int) == k, "service"].to_numpy()
        vals = vals[np.isfinite(vals)]
        vp = ax3.violinplot(vals, positions=[y[i]], orientation="horizontal", widths=0.72, showextrema=False, points=200)
        for body in vp["bodies"]:
            body.set_facecolor(ARCH_COLORS[k]); body.set_edgecolor("none"); body.set_alpha(0.42)
        q = np.quantile(vals, [0.05, 0.25, 0.5, 0.75, 0.95])
        ax3.plot([q[0], q[4]], [y[i], y[i]], color=ARCH_COLORS[k], lw=0.7)
        ax3.plot([q[1], q[3]], [y[i], y[i]], color=ARCH_COLORS[k], lw=2.4)
        ax3.scatter(q[2], y[i], s=12, color=ARCH_COLORS[k], edgecolor="white", lw=0.4, zorder=4)
        rows.append({"archetype": k, "n": len(vals), "p05": q[0], "p25": q[1], "median": q[2], "p75": q[3], "p95": q[4]})
    ax3.axvline(0, color="#666666", lw=0.6)
    ax3.set_yticks(y, [f"A{k}" for k in range(1, 5)])
    for t, k in zip(ax3.get_yticklabels(), range(1, 5)):
        t.set_color(ARCH_COLORS[k]); t.set_fontweight("bold")
    ax3.set_xlabel("Cooling service received (°C)")
    ax3.set_title("Residential cooling receipt\\nremains heterogeneous", loc="left", fontweight="bold", pad=7)
    strip_axes(ax3)
    add_panel_label(ax3, "c")
    fig.suptitle("Cooling propagation is patch-specific rather than an archetype-wide constant", x=0.01, y=0.995, ha="left", fontsize=9.2, fontweight="bold")
    fig.text(0.01, 0.015, "Curves show patch-bootstrap means and 95% intervals; 0.10 °C is the primary footprint threshold. Footprints are descriptive model-based service boundaries, not causal intervention effects.", fontsize=5.4, color="#68737D")
    export(fig, "Figure3_Patch_specific_cooling_propagation")
    decay.to_csv(SOURCE / "Figure3a_cooling_distance_decay.csv", index=False)
    patch.to_csv(SOURCE / "Figure3b_patch_cooling_footprints.csv", index=False)
    pd.DataFrame(rows).to_csv(SOURCE / "Figure3c_cooling_service_distributions.csv", index=False)


def figure4(post, housing, arch, service, extent, boundary):
    fig = plt.figure(figsize=(7.2047, 4.4094))  # 183 x 112 mm
    gs = fig.add_gridspec(1, 3, width_ratios=[0.86, 0.86, 1.35], wspace=0.38)
    groups = ["HDB", "Non-HDB residential proxy"]
    marks = {"HDB": ("o", "filled"), "Non-HDB residential proxy": ("D", "open")}

    ax1 = fig.add_subplot(gs[0, 0])
    hh = housing[housing.context_level == "archetype"].copy()
    for k in range(1, 5):
        for gi, group in enumerate(groups):
            r = hh[(hh.context.astype(str) == str(k)) & (hh.housing_group == group)].iloc[0]
            marker, fill = marks[group]
            x = r.footprint_coverage_pct
            ax1.scatter(x, k + (0.10 if gi == 0 else -0.10), s=24, marker=marker, facecolor=(ARCH_COLORS[k] if fill == "filled" else "white"), edgecolor=ARCH_COLORS[k], lw=0.8)
        hval = float(hh[(hh.context.astype(str) == str(k)) & (hh.housing_group == "HDB")].footprint_coverage_pct.iloc[0])
        oval = float(hh[(hh.context.astype(str) == str(k)) & (hh.housing_group == "Non-HDB residential proxy")].footprint_coverage_pct.iloc[0])
        ax1.plot([hval, oval], [k, k], color=ARCH_COLORS[k], lw=0.7, alpha=0.65)
    ax1.set_yticks(range(1, 5), [f"A{k}" for k in range(1, 5)])
    for t, k in zip(ax1.get_yticklabels(), range(1, 5)):
        t.set_color(ARCH_COLORS[k]); t.set_fontweight("bold")
    ax1.invert_yaxis()
    ax1.set_xlabel("Postcodes inside cooling footprint (%)")
    ax1.set_title("Cooling-footprint coverage", loc="left", fontweight="bold", pad=8)
    strip_axes(ax1); ax1.spines["left"].set_visible(False); ax1.tick_params(axis="y", length=0)
    add_panel_label(ax1, "a")

    ax2 = fig.add_subplot(gs[0, 1])
    s = post[post.cooling_service_supported.astype(bool)].copy()
    for k in range(1, 5):
        for gi, group in enumerate(groups):
            vals = s[(s.archetype.astype(int) == k) & (s.housing_group == group)].cooling_service_received_c.astype(float).to_numpy()
            vals = vals[np.isfinite(vals)]
            q = np.quantile(vals, [0.05, 0.25, 0.5, 0.75, 0.95])
            y = k + (0.11 if gi == 0 else -0.11)
            marker, fill = marks[group]
            ax2.plot([q[0], q[4]], [y, y], color=ARCH_COLORS[k], lw=0.6)
            ax2.plot([q[1], q[3]], [y, y], color=ARCH_COLORS[k], lw=2.1)
            ax2.scatter(q[2], y, s=18, marker=marker, facecolor=(ARCH_COLORS[k] if fill == "filled" else "white"), edgecolor=ARCH_COLORS[k], lw=0.7, zorder=3)
    ax2.axvline(0, color="#777777", lw=0.6)
    ax2.set_yticks(range(1, 5), [f"A{k}" for k in range(1, 5)])
    for t, k in zip(ax2.get_yticklabels(), range(1, 5)):
        t.set_color(ARCH_COLORS[k]); t.set_fontweight("bold")
    ax2.invert_yaxis()
    ax2.set_xlabel("Cooling service received (°C)")
    ax2.set_title("Cooling-service magnitude", loc="left", fontweight="bold", pad=8)
    strip_axes(ax2); ax2.spines["left"].set_visible(False); ax2.tick_params(axis="y", length=0)
    legend = [Line2D([0], [0], marker="o", color="#333", markerfacecolor="#333", lw=0, label="HDB"), Line2D([0], [0], marker="D", color="#333", markerfacecolor="white", lw=0, label="Other residential proxy")]
    add_panel_label(ax2, "b")

    ax3 = fig.add_subplot(gs[0, 2])
    priority = np.zeros_like(service, dtype=float)
    h = post[(post.housing_group == "HDB") & post.cooling_service_supported.astype(bool) & (post.hdb_dwelling_units > 0)].copy()
    h["outside"] = ~h.within_cooling_service_footprint.astype(bool)
    hh = h[h.outside].groupby(["row", "col"], as_index=False).hdb_dwelling_units.sum()
    for r in hh.itertuples():
        if 0 <= int(r.row) < priority.shape[0] and 0 <= int(r.col) < priority.shape[1]:
            priority[int(r.row), int(r.col)] = float(r.hdb_dwelling_units)
    pos = priority[priority > 0]
    vmax = np.percentile(pos, 98) if len(pos) else 1
    im = ax3.imshow(np.ma.masked_where(priority <= 0, priority), origin="upper", extent=extent, cmap="magma_r", vmin=0, vmax=vmax, interpolation="nearest")
    draw_arch_boundaries(ax3, arch, extent, lw=0.4)
    map_background(ax3, boundary)
    add_scale_bar(ax3, extent)
    cb = fig.colorbar(im, ax=ax3, orientation="horizontal", fraction=0.045, pad=0.015)
    cb.set_label("HDB dwelling units outside modelled footprint (100-m cell)")
    ax3.set_title("Spatial concentration of unserved HDB dwellings", loc="left", fontweight="bold", pad=8)
    add_panel_label(ax3, "c")
    fig.legend(handles=legend, frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.39, 0.90))
    fig.suptitle("Residential access to green cooling is context-dependent rather than uniformly distributed", x=0.01, y=0.995, ha="left", fontsize=9.2, fontweight="bold")
    fig.text(0.01, 0.015, "HDB symbols and map intensities represent dwelling units, not residents. Other residential locations are unweighted address proxies because comparable private-housing population counts were unavailable.", fontsize=5.4, color="#68737D")
    export(fig, "Figure4_Context_dependent_residential_cooling_access")
    hh.to_csv(SOURCE / "Figure4c_HDB_dwelling_units_outside_footprints.csv", index=False)


def extended_morphology(morph):
    m = morph[(morph.context_level == "archetype") & (morph.weighting == "postcode")].copy()
    outcomes = ["cooling_efficacy_c_per_10pp", "cooling_service_reach_m", "cooling_service_received_c"]
    titles = ["Cooling efficacy", "Service reach", "Service received"]
    fig, axes = plt.subplots(1, 3, figsize=(7.2047, 2.8346), gridspec_kw={"wspace": 0.36})  # 183 x 72 mm
    for ax, outcome, title in zip(axes, outcomes, titles):
        q = m[m.outcome == outcome]
        for k in range(1, 5):
            for gi, group in enumerate(["HDB", "Non-HDB residential proxy"]):
                r = q[(q.context.astype(str) == str(k)) & (q.housing_group == group)].iloc[0]
                y = k + (0.10 if gi == 0 else -0.10)
                marker = "o" if gi == 0 else "D"
                face = ARCH_COLORS[k] if gi == 0 else "white"
                ax.plot([r.ci_low, r.ci_high], [y, y], color=ARCH_COLORS[k], lw=0.8)
                ax.scatter(r.estimate, y, s=18, marker=marker, facecolor=face, edgecolor=ARCH_COLORS[k], lw=0.7)
        ax.axvline(0, color="#777", lw=0.6)
        ax.set_yticks(range(1, 5), [f"A{k}" for k in range(1, 5)] if ax is axes[0] else [])
        ax.invert_yaxis(); strip_axes(ax); ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0)
        ax.set_title(title, fontweight="bold")
        ax.set_xlabel("Morphology amplification")
    add_panel_label(axes[0], "a")
    fig.suptitle("Extended Data Fig. 1 | Urban morphology modifies green-cooling production and propagation", x=0.01, y=0.995, ha="left", fontsize=8.5, fontweight="bold")
    export(fig, "ExtendedData_Figure1_Morphology_modifies_green_cooling")


def extended_built_form_screen(screen, support):
    """Complete context-by-housing screen of five built-form associations."""
    context_labels = [
        "A1", "  S1*", "  S2*", "  S3*", "  S4*",
        "A2", "  S1", "  S2",
        "A3", "  S1", "  S2", "  S3",
        "A4", "  S1", "  S2",
    ]
    context_parents = [1, 1, 1, 1, 1, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4]
    parent_rows = {0, 5, 8, 12}
    variables = ["bcr", "far", "height_mean", "height_std", "svf"]
    variable_labels = [
        "Building\\ncoverage",
        "Floor-area\\nintensity",
        "Mean\\nheight",
        "Height\\nvariability",
        "Sky-view\\nfactor",
    ]
    panels = [
        ("HDB", "cooling_efficacy", "a", "HDB: cooling efficacy"),
        ("HDB", "cooling_proximity", "b", "HDB: cooling proximity"),
        ("Non-HDB residential proxy", "cooling_efficacy", "c", "Other residential: cooling efficacy"),
        ("Non-HDB residential proxy", "cooling_proximity", "d", "Other residential: cooling proximity"),
    ]
    cmap = mpl.colors.LinearSegmentedColormap.from_list(
        "morphology_association", ["#2C7FB8", "#F7F7F7", "#D55E00"]
    )
    cmap.set_bad("#F0F2F3")
    norm = mpl.colors.TwoSlopeNorm(vmin=-4, vcenter=0, vmax=4)
    fig, axes = plt.subplots(
        2,
        2,
        figsize=(7.2047, 7.0079),  # 183 x 178 mm
        gridspec_kw={"left": 0.16, "right": 0.975, "bottom": 0.23, "top": 0.90, "wspace": 0.17, "hspace": 0.22},
    )
    last_im = None
    for panel_index, (ax, (housing, outcome, panel_label, title)) in enumerate(zip(axes.ravel(), panels)):
        subset = screen.loc[
            screen["housing_group"].eq(housing) & screen["outcome"].eq(outcome)
        ].copy()
        matrix = np.full((15, 5), np.nan)
        significant = np.zeros((15, 5), dtype=bool)
        for row in subset.itertuples():
            i = int(row.context_index)
            j = variables.index(row.variable)
            matrix[i, j] = float(row.signed_z)
            significant[i, j] = bool(row.p_fdr_bh < 0.05)
        last_im = ax.imshow(matrix, cmap=cmap, norm=norm, aspect="auto", interpolation="nearest")
        sig_y, sig_x = np.where(significant)
        ax.scatter(sig_x, sig_y, s=8, color="#171717", marker="o", linewidth=0, zorder=3)

        unsupported = support.loc[
            support["housing_group"].eq(housing) & ~support["eligible"].astype(bool)
        ]
        for row in unsupported.itertuples():
            i = int(row.context_index)
            for j in range(len(variables)):
                ax.scatter(j, i, s=12, marker="x", color="#7D858B", lw=0.65, zorder=4)

        ax.set_xticks(range(5), variable_labels if panel_index >= 2 else [])
        ax.tick_params(axis="x", length=0, pad=3)
        ax.set_yticks(range(15), context_labels if panel_index % 2 == 0 else [])
        ax.tick_params(axis="y", length=0, pad=4)
        if panel_index % 2 == 0:
            for i, (tick, parent) in enumerate(zip(ax.get_yticklabels(), context_parents)):
                tick.set_color(ARCH_COLORS[parent])
                tick.set_fontweight("bold" if i in parent_rows else "normal")
                tick.set_fontsize(5.6 if i in parent_rows else 5.0)
        for boundary_y in [4.5, 7.5, 11.5]:
            ax.axhline(boundary_y, color="white", lw=1.3)
        ax.set_title(title, loc="left", fontweight="bold", pad=7)
        add_panel_label(ax, panel_label)
        for spine in ax.spines.values():
            spine.set_visible(False)

    cax = fig.add_axes([0.31, 0.105, 0.42, 0.018])
    cb = fig.colorbar(last_im, cax=cax, orientation="horizontal", ticks=[-4, -2, 0, 2, 4])
    cb.set_label("Signed association statistic (estimate / clustered SE; clipped at ±4)")
    fig.text(0.16, 0.175, "Negative: weaker efficacy / farther", color="#2C7FB8", fontsize=5.3)
    fig.text(0.975, 0.175, "Positive: stronger efficacy / closer", color="#D55E00", fontsize=5.3, ha="right")
    fig.text(0.16, 0.025, "Black dot: FDR q<0.05 across 290 supported tests. ×: insufficient spatial support. *A1 subtypes are exploratory/spatially weak. Exact estimates, 95% CIs, q values and sample sizes are provided in Source Data.", color="#68737D", fontsize=5.2)
    fig.suptitle("Extended Data Fig. 2 | Built-form associations vary across cooling function, context and housing", x=0.01, y=0.975, ha="left", fontsize=8.5, fontweight="bold")
    export(fig, "ExtendedData_Figure2_All_built_form_associations")
    screen.to_csv(SOURCE / "ExtendedData_Figure2_all_built_form_associations.csv", index=False)
    support.to_csv(SOURCE / "ExtendedData_Figure2_support_audit.csv", index=False)


def qa(
    post,
    patch,
    decay,
    morph,
    modifier_screen,
    modifier_support,
    green_built_modifier,
    green_built_scale,
    exposome_selected,
):
    supported = post.cooling_service_supported.astype(bool)
    footprint = post.within_cooling_service_footprint.astype(bool)
    checks = {
        "postcode_rows": int(len(post)),
        "unique_postcodes": int(post.postal_code.nunique()),
        "duplicate_postcodes": int(post.postal_code.duplicated().sum()),
        "supported_postcodes": int(supported.sum()),
        "supported_share_pct": float(100 * supported.mean()),
        "footprint_share_among_supported_pct": float(100 * footprint[supported].mean()),
        "negative_service_values": int((post.cooling_service_received_c.astype(float) < -1e-12).sum()),
        "missing_access_distances": int(post.distance_to_nearest_cooling_service_footprint_m.isna().sum()),
        "negative_access_distances": int((post.distance_to_nearest_cooling_service_footprint_m.astype(float) < 0).sum()),
        "patches": int(patch.patch_id.nunique()),
        "positive_halo_patches_primary": int((patch.external_footprint_radius_m.astype(float) > 0).sum()),
        "invalid_patch_radius_count": int((~patch.external_footprint_radius_m.astype(float).isin(np.arange(0, 701, 100))).sum()),
        "decay_duplicate_rows": int(decay.duplicated(["context_level", "context", "distance_bin_mid_m"]).sum()),
        "morphology_contexts": int(morph[["context_level", "context"]].drop_duplicates().shape[0]),
        "all_morphology_intervals_ordered": bool(((morph.ci_low.astype(float) <= morph.estimate.astype(float)) & (morph.estimate.astype(float) <= morph.ci_high.astype(float))).all()),
        "modifier_screen_rows": int(len(modifier_screen)),
        "modifier_variables": int(modifier_screen.variable.nunique()),
        "modifier_supported_strata": int(modifier_support.eligible.astype(bool).sum()),
        "modifier_total_strata": int(len(modifier_support)),
        "modifier_intervals_ordered": bool(((modifier_screen.ci_low.astype(float) <= modifier_screen.estimate.astype(float)) & (modifier_screen.estimate.astype(float) <= modifier_screen.ci_high.astype(float))).all()),
        "green_built_modifier_rows": int(len(green_built_modifier)),
        "green_built_modifier_archetypes": int(green_built_modifier.archetype.nunique()),
        "green_built_modifier_variables": int(green_built_modifier.variable.nunique()),
        "green_built_housing_groups": int(green_built_modifier.housing_group.nunique()),
        "green_built_rows_per_outcome": green_built_modifier.groupby("outcome").size().astype(int).to_dict(),
        "green_built_intervals_ordered": bool(((green_built_modifier.ci_low.astype(float) <= green_built_modifier.estimate.astype(float)) & (green_built_modifier.estimate.astype(float) <= green_built_modifier.ci_high.astype(float))).all()),
        "green_built_incremental_r2_nonnegative": bool((green_built_modifier.incremental_r_squared.astype(float) >= 0).all()),
        "green_built_directional_r2_finite": bool(np.isfinite(green_built_modifier.directional_incremental_r2_pct.astype(float)).all()),
        "green_built_scaling_rows": int(len(green_built_scale)),
        "green_built_scaling_positive_iqr": bool((green_built_scale.raw_iqr.astype(float) > 0).all()),
        "pc_selected_rows": int(len(exposome_selected)),
        "pc_selected_archetypes": int(exposome_selected.archetype.nunique()),
        "pc_selected_outcomes": int(exposome_selected.outcome.nunique()),
        "pc_selected_components": int(exposome_selected.component_id.nunique()),
        "pc_selected_housing_groups": sorted(exposome_selected.housing_group.unique().tolist()),
        "pc_selected_rows_per_group": exposome_selected.groupby(["archetype", "outcome"]).size().astype(int).tolist(),
        "pc_selected_intervals_ordered": bool(((exposome_selected.ci_low.astype(float) <= exposome_selected.estimate.astype(float)) & (exposome_selected.estimate.astype(float) <= exposome_selected.ci_high.astype(float))).all()),
        "pc_selection_ranks": sorted(exposome_selected.selection_rank.astype(int).unique().tolist()),
    }
    checks["pass"] = bool(
        checks["postcode_rows"] == checks["unique_postcodes"]
        and checks["negative_service_values"] == 0
        and checks["missing_access_distances"] == 0
        and checks["negative_access_distances"] == 0
        and checks["invalid_patch_radius_count"] == 0
        and checks["decay_duplicate_rows"] == 0
        and checks["all_morphology_intervals_ordered"]
        and checks["modifier_screen_rows"] == 290
        and checks["modifier_variables"] == 5
        and checks["modifier_supported_strata"] == 29
        and checks["modifier_total_strata"] == 30
        and checks["modifier_intervals_ordered"]
        and checks["green_built_modifier_rows"] == 64
        and checks["green_built_modifier_archetypes"] == 4
        and checks["green_built_modifier_variables"] == 4
        and checks["green_built_housing_groups"] == 2
        and checks["green_built_rows_per_outcome"] == {"cooling_efficacy": 32, "cooling_proximity": 32}
        and checks["green_built_intervals_ordered"]
        and checks["green_built_incremental_r2_nonnegative"]
        and checks["green_built_directional_r2_finite"]
        and checks["green_built_scaling_rows"] == 16
        and checks["green_built_scaling_positive_iqr"]
        and checks["pc_selected_rows"] == 64
        and checks["pc_selected_archetypes"] == 4
        and checks["pc_selected_outcomes"] == 2
        and checks["pc_selected_components"] <= 12
        and checks["pc_selected_housing_groups"] == ["HDB", "Non-HDB"]
        and checks["pc_selected_rows_per_group"] == [8] * 8
        and checks["pc_selected_intervals_ordered"]
        and checks["pc_selection_ranks"] == [1, 2, 3, 4]
    )
    (ANALYSIS / "analysis_qa.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
    return checks


def main():
    post = pd.read_csv(ANALYSIS / "postcode_cooling_production_and_service.csv", low_memory=False)
    domain_indicators = pd.read_csv(BASE / "postcode_domain_indicators.csv", low_memory=False)
    pc_scores = pd.read_csv(
        ANALYSIS / "pc_cooling_associations" / "postcode_balanced_pca_component_scores.csv",
    )
    pc_dictionary = pd.read_csv(
        ANALYSIS / "pc_cooling_associations" / "pca_component_dictionary.csv"
    )
    morph = pd.read_csv(ANALYSIS / "morphology_amplification_summary.csv")
    modifier = pd.read_csv(
        ANALYSIS
        / "green_built_structure_modifiers"
        / "archetype_green_built_structure_associations.csv"
    )
    modifier_screen = pd.read_csv(
        ANALYSIS / "interpretable_morphology" / "morphology_context_housing_screen.csv"
    )
    modifier_support = pd.read_csv(
        ANALYSIS / "interpretable_morphology" / "morphology_context_housing_support.csv"
    )
    modifier_scale = pd.read_csv(
        ANALYSIS
        / "green_built_structure_modifiers"
        / "green_built_characteristic_iqr_scaling.csv"
    )
    exposome_selected = pd.read_csv(
        ANALYSIS
        / "pc_cooling_associations"
        / "selected_top4_pc_associations.csv"
    )
    decay = pd.read_csv(ANALYSIS / "cooling_distance_decay_by_context.csv")
    patch = pd.read_csv(ANALYSIS / "green_patch_cooling_footprints.csv")
    housing = pd.read_csv(ANALYSIS / "housing_cooling_receipt_summary.csv")
    efficacy, extent, crs, _ = read_raster("cooling_efficacy_surface_100m.tif")
    service, _, _, _ = read_raster("cooling_service_surface_100m.tif")
    access_distance, _, _, _ = read_raster(
        "cooling_service_access_distance_surface_100m.tif"
    )
    arch, _, _, _ = read_raster("archetype_surface_100m.tif")
    boundary = planning_boundary(crs)
    checks = qa(
        post,
        patch,
        decay,
        morph,
        modifier_screen,
        modifier_support,
        modifier,
        modifier_scale,
        exposome_selected,
    )
    if not checks["pass"]:
        raise RuntimeError(f"Analysis QA failed: {checks}")
    figure1(post, domain_indicators, pc_scores, pc_dictionary, arch, extent, boundary)
    figure2(post, exposome_selected, arch, efficacy, access_distance, extent, boundary)
    figure3(post, decay, patch)
    figure4(post, housing, arch, service, extent, boundary)
    extended_morphology(morph)
    extended_built_form_screen(modifier_screen, modifier_support)
    print(json.dumps(checks, indent=2))
    print(f"Figures written to {OUT}")


if __name__ == "__main__":
    main()
'''

ENTRY = '''
"""Reproduce Figure 5 from compact cooling-service processed outputs."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'code'))
import plot_figure2_official as official
import plot_network_integrated_accessible_cooling_figure2 as renderer
import plot_residential_green_cooling_paper_figures as maps

DATA = HERE / 'data/analysis'
OUT = HERE / 'output'
R800 = DATA / 'accessible_cooling_radius_sensitivity_trial/800m'
P400 = DATA / 'accessible_cooling_integral_trial/panelE400_volume'
renderer.ROOT = HERE.parent
renderer.ANALYSIS = DATA
renderer.OUT = OUT
renderer.TRIAL = R800
renderer.NONLINEAR = P400
renderer.SOURCE = OUT / 'source_data'
maps.ROOT = HERE.parent
maps.ANALYSIS = DATA
boundary_file = HERE.parent / 'shared_data/MasterPlan2019PlanningAreaBoundaryNoSea.geojson'
maps.planning_boundary = lambda crs: maps.gpd.read_file(boundary_file).to_crs(crs)
renderer.planning_boundary = maps.planning_boundary
official.ANALYSIS = DATA
official.RADIUS_800 = R800
official.PANEL_E_400 = P400
official.OUT = OUT
# Keep the accepted manuscript settings, including 800-m access and 400-m panel-e analyses.
official.main()
'''

if __name__ == "__main__":
    main()
