"""Figure 3: Frozen greenery correlations, cross-domain indicators and the SOM projection of consensus archetypes. No SOM retraining.

Run: python Figure3_exposome_rationale.py
Optional: --output-dir my_figures --csv Figure3_exposome_rationale.csv
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

FIGURE_NUMBER = 3
FIGURE_NAME = 'Figure3_exposome_rationale'
OUTPUT_RELATIVE_STEM = 'Figure3_exposome_rationale'

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

# ----- plot_figure2_multidimensional_archetype_landscape -----
RENDERERS['plot_figure2_multidimensional_archetype_landscape'] = '''"""Figure 2: multidimensional environmental structure and archetype compression."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "ALL_RESIDENTIAL_5DOMAIN_PM2016_2024_ARCHETYPES"
OUT = BASE / "multidimensional_archetype_landscape"
FIGDIR = OUT / "figures"
STEM = "Figure2_Multidimensional_archetype_landscape"

DOMAINS = ["Heat", "PM2.5", "Greenery", "Park access", "Built intensity"]
RAW_DOMAINS = ["Heat", "PM2.5", "Greenery", "Park access", "Built form"]
ARCHETYPE_NAMES = {
    1: "Low-green–Hot",
    2: "High-PM$_{2.5}$–Green",
    3: "Green–Cool",
    4: "Low-green–Low-PM$_{2.5}$",
}
COLORS = {1: "#009E73", 2: "#D55E00", 3: "#0072B2", 4: "#CC79A7"}

mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "font.size": 7,
        "axes.labelsize": 7,
        "axes.titlesize": 7,
        "xtick.labelsize": 6,
        "ytick.labelsize": 6,
        "axes.linewidth": 0.55,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "savefig.facecolor": "white",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    }
)


def grid(nodes: pd.DataFrame, column: str) -> np.ndarray:
    return (
        nodes.pivot(index="som_row", columns="som_column", values=column)
        .reindex(index=range(20), columns=range(20))
        .to_numpy(float)
    )


def clean_map_axis(ax: plt.Axes) -> None:
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


def draw_panel_a(
    fig: plt.Figure,
    region,
    greenery_correlation: pd.DataFrame,
    greenery_order: pd.DataFrame,
    greenery_metrics: dict,
) -> mpl.image.AxesImage:
    ax = fig.add_subplot(region)
    variables = greenery_order.sort_values("display_order")["variable"].tolist()
    matrix = greenery_correlation.loc[variables, variables].to_numpy(float)
    image = ax.imshow(matrix, cmap="Reds", vmin=0.75, vmax=1.00, interpolation="nearest", aspect="equal")
    groups = (
        greenery_order.sort_values("display_order")
        .groupby(["metric_family", "radius_m"], sort=False)
        .size()
        .reset_index(name="count")
    )
    starts = np.cumsum([0, *groups["count"].tolist()[:-1]])
    centers = starts + (groups["count"].to_numpy() - 1) / 2
    y_labels = [
        (
            f"Green area\\n{int(radius)} m"
            if family == "Green area"
            else f"Distance-\\nweighted\\n{int(radius)} m"
        )
        for family, radius in zip(groups["metric_family"], groups["radius_m"])
    ]
    x_labels = [
        ("Area" if family == "Green area" else "D-weighted") + f"\\n{int(radius)} m"
        for family, radius in zip(groups["metric_family"], groups["radius_m"])
    ]
    boundaries = np.cumsum(groups["count"].to_numpy())[:-1] - 0.5
    for boundary in boundaries:
        linewidth = 1.15 if np.isclose(boundary, 29.5) else 0.55
        ax.axvline(boundary, color="white", lw=linewidth)
        ax.axhline(boundary, color="white", lw=linewidth)
    ax.set_xticks(centers, x_labels, rotation=38, ha="right", rotation_mode="anchor")
    ax.set_yticks(centers, y_labels)
    ax.tick_params(length=0, pad=1.7, labelsize=5.0)
    ax.set_anchor("N")
    ax.text(
        0.0,
        1.025,
        f"median ρ = {greenery_metrics['median_spearman']:.2f}",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=5.2,
        color="#273238",
    )
    for spine in ax.spines.values():
        spine.set_visible(False)
    return image


def draw_panel_b(
    fig: plt.Figure,
    region,
    weak: pd.DataFrame,
    selection: pd.DataFrame,
) -> mpl.image.AxesImage:
    ax = fig.add_subplot(region)
    matrix = weak.loc[RAW_DOMAINS, RAW_DOMAINS].to_numpy(float)
    image = ax.imshow(matrix, cmap="RdBu_r", vmin=-1, vmax=1, aspect="equal")
    domain_ticks = ["Heat", "PM$_{2.5}$", "Green", "Park", "Built"]
    ax.set_xticks(range(5), domain_ticks, rotation=38, ha="right", rotation_mode="anchor")
    ax.set_yticks(range(5), domain_ticks)
    ax.tick_params(length=0, pad=1.8, labelsize=5.0)
    for row in range(5):
        for column in range(5):
            value = matrix[row, column]
            ax.text(
                column,
                row,
                f"{value:.2f}",
                ha="center",
                va="center",
                fontsize=5.0,
                color="white" if abs(value) > 0.48 else "#263238",
                fontweight="bold" if row == column else "normal",
            )
    ax.set_anchor("N")
    selected = selection.loc[selection["panel"].eq("a2_weakly_correlated")].iloc[0]
    ax.text(
        0.0,
        1.025,
        f"mean |ρ| = {selected['mean_abs_spearman']:.2f} · all pairs |ρ| < 0.10",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=5.2,
        color="#273238",
    )
    for spine in ax.spines.values():
        spine.set_visible(False)
    return image


def add_correlation_colorbar(
    fig: plt.Figure,
    slot,
    image: mpl.image.AxesImage,
    *,
    ticks: list[float],
    label: str,
) -> None:
    box = slot.get_position(fig)
    width = box.x1 - box.x0
    cax = fig.add_axes([box.x0 + 0.08 * width, box.y0 - 0.090, 0.84 * width, 0.012])
    colorbar = fig.colorbar(image, cax=cax, orientation="horizontal", ticks=ticks)
    colorbar.ax.tick_params(labelsize=5.2, length=2, pad=1)
    colorbar.set_label(label, fontsize=5.7, labelpad=1.5)


def draw_panel_c(
    fig: plt.Figure,
    region,
    nodes: pd.DataFrame,
    adjacency_summary: dict,
) -> None:
    ax = fig.add_subplot(region)
    values = grid(nodes, "u_matrix_distance")
    lower = float(np.nanmin(values))
    upper = float(np.nanquantile(values, 0.98))
    light_greys = mpl.colors.LinearSegmentedColormap.from_list(
        "light_greys",
        mpl.colormaps["Greys"](np.linspace(0.03, 0.72, 256)),
    )
    image = ax.imshow(
        values,
        cmap=light_greys,
        vmin=lower,
        vmax=upper,
        interpolation="nearest",
        aspect="equal",
    )
    occupied = nodes.loc[nodes["n_locations"].gt(0)].copy()
    ax.scatter(
        occupied["som_column"],
        occupied["som_row"],
        c=occupied["dominant_archetype"].astype(int).map(COLORS),
        s=10.5,
        marker="o",
        edgecolors="white",
        linewidths=0.18,
        zorder=3,
    )
    clean_map_axis(ax)
    ax.set_xlabel("SOM column", fontsize=5.8, labelpad=2.2)
    ax.set_ylabel("SOM row", fontsize=5.8, labelpad=2.2)
    ax.set_anchor("N")
    ax.text(
        0.0,
        1.025,
        (
            f"{adjacency_summary['percentage_same_dominant_archetype']:.1f}% adjacent-node "
            f"agreement ({adjacency_summary['n_same_dominant_archetype']}/"
            f"{adjacency_summary['n_adjacent_occupied_pairs']} pairs)"
        ),
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=5.2,
        color="#273238",
    )
    cax = ax.inset_axes([0.15, -0.12, 0.70, 0.030])
    colorbar = fig.colorbar(
        image,
        cax=cax,
        orientation="horizontal",
        ticks=np.linspace(lower, upper, 3),
    )
    colorbar.ax.set_xticklabels([f"{value:.2f}" for value in np.linspace(lower, upper, 3)])
    colorbar.ax.tick_params(labelsize=5.0, length=2, pad=1.2)
    colorbar.set_label(
        "Normalized U-matrix distance",
        fontsize=5.7,
        labelpad=1.3,
    )
    handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            linestyle="none",
            markerfacecolor=COLORS[k],
            markeredgecolor="white",
            markeredgewidth=0.2,
            markersize=4.0,
            label=f"A{k} {ARCHETYPE_NAMES[k]}",
        )
        for k in range(1, 5)
    ]
    ax.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.215),
        ncol=2,
        fontsize=5.0,
        handlelength=0.7,
        handletextpad=0.25,
        columnspacing=0.65,
        labelspacing=0.26,
    )


def main() -> None:
    FIGDIR.mkdir(parents=True, exist_ok=True)
    indicators = pd.read_csv(
        BASE / "postcode_domain_indicators.csv",
        dtype={"postal_code": "string"},
        usecols=["postal_code", *DOMAINS],
        low_memory=False,
    )
    nodes = pd.read_csv(OUT / "som_node_landscape.csv")
    u_matrix_observed_min = float(nodes["u_matrix_distance"].min())
    u_matrix_observed_max = float(nodes["u_matrix_distance"].max())
    u_matrix_display_upper = float(nodes["u_matrix_distance"].quantile(0.98))
    som_summary = json.loads((OUT / "som_summary.json").read_text(encoding="utf-8"))
    adjacency_summary = som_summary["occupied_node_adjacency"]
    raw_correlation = pd.read_csv(OUT / "raw_variable_spearman_correlations.csv", index_col=0)
    greenery_correlation = pd.read_csv(OUT / "greenery_raw_spearman_correlations.csv", index_col=0)
    greenery_order = pd.read_csv(OUT / "greenery_variable_order.csv")
    greenery_metrics = json.loads((OUT / "greenery_correlation_summary.json").read_text(encoding="utf-8"))
    weak = pd.read_csv(OUT / "a2_weakly_correlated_spearman_correlations.csv", index_col=0)
    selection = pd.read_csv(OUT / "panel_a_indicator_selection.csv")
    if len(indicators) != som_summary["n_residential_locations"]:
        raise ValueError("Indicator and SOM cohort sizes differ")
    if raw_correlation.shape != (124, 124):
        raise ValueError("Panel-a raw-variable correlation contract is not 124 × 124")
    if greenery_correlation.shape != (60, 60) or len(greenery_order) != 60:
        raise ValueError("Panel-a greenery correlation contract is not 60 × 60")
    if weak.shape != (5, 5):
        raise ValueError("Panel-b cross-domain correlation contract is not 5 × 5")
    if len(selection) != 10 or selection.groupby("panel")["domain"].nunique().ne(5).any():
        raise ValueError("Panel-a indicator selection does not contain one indicator per domain")

    fig = plt.figure(figsize=(7.2, 3.45))
    outer = fig.add_gridspec(
        1,
        3,
        width_ratios=[1, 1, 1],
        left=0.077,
        right=0.985,
        bottom=0.22,
        top=0.84,
        wspace=0.16,
    )
    panel_a_image = draw_panel_a(
        fig, outer[0, 0], greenery_correlation, greenery_order, greenery_metrics
    )
    panel_b_image = draw_panel_b(fig, outer[0, 1], weak, selection)
    add_correlation_colorbar(
        fig,
        outer[0, 0],
        panel_a_image,
        ticks=[0.75, 0.80, 0.90, 1.00],
        label="Within-greenery Spearman ρ",
    )
    add_correlation_colorbar(
        fig,
        outer[0, 1],
        panel_b_image,
        ticks=[-1.0, 0.0, 1.0],
        label="Cross-domain Spearman ρ",
    )
    draw_panel_c(fig, outer[0, 2], nodes, adjacency_summary)

    for letter, slot in zip("abc", [outer[0, 0], outer[0, 1], outer[0, 2]]):
        box = slot.get_position(fig)
        fig.text(box.x0 - 0.027, 0.935, letter, fontsize=10.0, fontweight="bold", ha="left", va="top")

    target = FIGDIR / STEM
    fig.savefig(target.with_suffix(".svg"), bbox_inches=None)
    fig.savefig(target.with_suffix(".pdf"), bbox_inches=None)
    fig.savefig(target.with_suffix(".png"), dpi=600, bbox_inches=None)
    fig.savefig(target.with_suffix(".tiff"), dpi=600, bbox_inches=None, pil_kwargs={"compression": "tiff_lzw"})
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    outside = []
    for item in fig.findobj(mpl.text.Text):
        if not item.get_visible() or not item.get_text().strip():
            continue
        box = item.get_window_extent(renderer)
        if box.x0 < -0.5 or box.y0 < -0.5 or box.x1 > fig.bbox.width + 0.5 or box.y1 > fig.bbox.height + 0.5:
            outside.append(item.get_text())
    preflight = {
        "width_mm": fig.get_figwidth() * 25.4,
        "height_mm": fig.get_figheight() * 25.4,
        "dpi": 600,
        "outside_canvas_text": outside,
        "n_residential_locations": int(len(indicators)),
        "raw_variable_correlation_shape": list(raw_correlation.shape),
        "panel_a_greenery_correlation_shape": list(greenery_correlation.shape),
        "panel_a_greenery_metrics": greenery_metrics,
        "panel_a_color_scale": [0.75, 1.00],
        "panel_b_mean_absolute_spearman": float(
            selection.loc[selection["panel"].eq("a2_weakly_correlated"), "mean_abs_spearman"].iloc[0]
        ),
        "panel_b_color_scale": [-1.0, 1.0],
        "occupied_node_purity": som_summary["occupied_node_purity"],
        "occupied_node_adjacency": adjacency_summary,
        "combined_som_overlay": True,
        "u_matrix_color_scale": [u_matrix_observed_min, u_matrix_display_upper],
        "u_matrix_colormap_fraction": [0.03, 0.72],
        "u_matrix_observed_range": [
            u_matrix_observed_min,
            u_matrix_observed_max,
        ],
        "correlation_missing_values": int(raw_correlation.isna().sum().sum()),
    }
    (OUT / f"{STEM}_preflight.json").write_text(json.dumps(preflight, indent=2), encoding="utf-8")
    plt.close(fig)

    with Image.open(target.with_suffix(".png")) as image:
        for width in (1440, 720):
            preview = image.resize((width, round(image.height * width / image.width)), Image.Resampling.LANCZOS)
            preview.save(FIGDIR / f"{STEM}_preview_{width}.png")

    def selected_indicator_text(panel: str) -> str:
        rows = selection.loc[selection["panel"].eq(panel)].set_index("domain").loc[RAW_DOMAINS]
        return "; ".join(rows["display_label"].tolist())

    weak_indicators = selected_indicator_text("a2_weakly_correlated")
    purity_stats = som_summary["occupied_node_purity"]
    (OUT / f"{STEM}_caption.md").write_text(
        "**Figure 2 | Multidimensional environmental structure resolves into recurrent residential urban-exposome archetypes.** "
        f"**a,** Within-domain Spearman correlations among all 60 greenery variables: green area and distance-weighted green exposure at 400, 800 and 1,000 m, measured annually from 2016–2025. Individual variables are unlabeled; short outer labels identify six metric-by-radius groups, white lines separate groups and the thicker central separator distinguishes the two metric families. Years run from 2016 to 2025 within each block. Across the {greenery_metrics['n_unique_pairs']} unique variable pairs, median ρ was {greenery_metrics['median_spearman']:.2f} (IQR {greenery_metrics['q1_spearman']:.2f}–{greenery_metrics['q3_spearman']:.2f}), demonstrating the redundancy that motivated within-domain PCA. Panel a uses a sequential ρ scale from 0.75 to 1.00, which contains the complete observed range without clipping. "
        f"**b,** A five-indicator cross-domain combination selected to minimize mean absolute correlation after excluding the earlier high-correlation exemplar in each domain (mean |ρ| = 0.03; all pairs |ρ| < 0.10): {weak_indicators}. This shows that distinct environmental domains can also carry largely independent information. "
        f"**c,** Neighbour-distance (U-matrix) surface of the 20 × 20 self-organizing map fitted to the exact 12-component domain-balanced PCA matrix, overlaid with the dominant independently derived consensus archetype at each occupied node. The numeric colourbar reports the original normalized U-matrix distance display ({u_matrix_observed_min:.2f}–{u_matrix_display_upper:.2f}; the upper 2% is clipped for visual contrast), where lower values identify locally similar multidomain profiles and higher values mark transition zones. Coloured circles show that the consensus archetypes occupy coherent regions of the continuous topology: {adjacency_summary['percentage_same_dominant_archetype']:.1f}% of {adjacency_summary['n_adjacent_occupied_pairs']} horizontal or vertical edge-sharing occupied node pairs had the same dominant archetype. The SOM did not derive K or the archetype labels. Of {purity_stats['n_occupied_nodes']} occupied nodes, median dominant-archetype purity was {purity_stats['median']:.2f} (IQR {purity_stats['q1']:.2f}–{purity_stats['q3']:.2f}); {purity_stats['percentage_ge_0_70']:.1f}%, {purity_stats['percentage_ge_0_80']:.1f}% and {purity_stats['percentage_ge_0_90']:.1f}% had purity ≥0.70, ≥0.80 and ≥0.90, respectively. Final A1–A4 labels remain those assigned by consensus of K-means, Gaussian mixture and partitioning-around-medoids solutions.\\n",
        encoding="utf-8",
    )
    (OUT / "QA_NOTES.md").write_text(
        "# Figure contract and QA\\n\\n"
        "- Core conclusion: within-domain redundancy motivates PCA, cross-domain complementarity motivates multidomain retention, and coherent archetype regions in continuous exposome space motivate clustering as an interpretable summary.\\n"
        "- Evidence chain: a, high redundancy among all 60 multiscale greenery variables motivates within-domain PCA; b, a weakly correlated five-domain set demonstrates complementary cross-domain information; c, consensus archetypes occupy coherent regions of the SOM dissimilarity landscape.\\n"
        "- Figure archetype: three-panel quantitative evidence sequence with a combined SOM topology-and-archetype hero panel.\\n"
        "- Data unit: 101,545 residential postcode/address locations; no sampling or row exclusion.\\n"
        "- Inputs: all 60 greenery variables in a; all 124 clustering variables in the cross-domain selection procedure for b; exact 12-component balanced clustering matrix and independent consensus labels in c.\\n"
        "- Panels a and b: Spearman correlations use all 101,545 locations. Panel a includes every greenery variable without selection. Panel b retains the previously defined disjoint minimum-correlation set, with one indicator per domain.\\n"
        "- Colour-scale integrity: panel a uses a sequential 0.75–1.00 scale because its complete observed range is 0.789–0.995; panel b uses an independent diverging −1 to +1 scale. Separate labelled colour bars prevent cross-panel colour-value equivalence from being implied. No correlations are clipped in panel a.\\n"
        "- SOM role: descriptive visualization only; it does not derive K=4 or replace consensus clustering. Panel c combines the U-matrix background and consensus-label overlay on one unchanged lattice.\\n"
        "- Panel-heading policy: no figure-wide title or descriptive panel headings are drawn; interpretation is carried by the caption, panel letters, quantitative annotations and legends.\\n"
        f"- U-matrix styling: panel c retains the original normalized U-matrix display (observed range {u_matrix_observed_min:.3f}–{u_matrix_observed_max:.3f}; display limits {u_matrix_observed_min:.3f}–{u_matrix_display_upper:.3f}, with the upper 2% clipped). Only the colourbar presentation was revised to show numeric distance values; topology and archetype colours are unchanged.\\n"
        "- Statistical reporting: n is the complete set of residential postcode/address locations; there are no biological or technical replicates, inferential tests or multiple-comparison procedures in this descriptive figure. Panel-a summary is the median and interquartile range across 1,770 unique pairwise correlations.\\n"
        "- SOM reporting: the 20 × 20 SOM used 75,000 iterations and fixed seed 20260909; it is neither a train/test model nor the source of the consensus labels. Node purity is descriptive and source data are saved in som_occupied_node_purity.csv.\\n"
        "- Source data: greenery_raw_spearman_correlations.csv, greenery_variable_order.csv, a2_weakly_correlated_spearman_correlations.csv, panel_a_indicator_selection.csv, som_node_landscape.csv, som_occupied_node_purity.csv and som_adjacent_occupied_node_pairs.csv.\\n"
        "- Backend: Python/matplotlib; 183-mm vector and 600-dpi raster exports.\\n",
        encoding="utf-8",
    )
    print(json.dumps(preflight, indent=2))


if __name__ == "__main__":
    main()
'''

ENTRY = '''
"""Reproduce Figure 3 from processed correlation and SOM tables."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'code'))
import plot_figure2_multidimensional_archetype_landscape as renderer

renderer.ROOT = HERE
renderer.BASE = HERE / 'data'
renderer.OUT = HERE / 'data'
renderer.FIGDIR = HERE / 'output'
renderer.STEM = 'Figure3_exposome_rationale'
renderer.main()
'''

if __name__ == "__main__":
    main()
