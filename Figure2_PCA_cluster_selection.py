"""Figure 2: Frozen five-domain PCA retention and K=1--20 diagnostics. No reclustering or reselection.

Run: python Figure2_PCA_cluster_selection.py
Optional: --output-dir my_figures --csv Figure2_PCA_cluster_selection.csv
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

FIGURE_NUMBER = 2
FIGURE_NAME = 'Figure2_PCA_cluster_selection'
OUTPUT_RELATIVE_STEM = 'Figure2_PCA_cluster_selection'

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

# ----- plot_extended_data_pca_cluster_selection -----
RENDERERS['plot_extended_data_pca_cluster_selection'] = '''"""Plot the all-residential PCA-to-archetype-selection workflow.

The figure reuses frozen outputs from the 101,545-location, 124-variable,
five-domain analysis. It does not refit PCA or clustering and therefore cannot
silently change the estimands used in the manuscript.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "outputs" / "ALL_RESIDENTIAL_5DOMAIN_PM2016_2024_ARCHETYPES"
PCA_FILE = ANALYSIS / "domain_pca_summary.csv"
K_FILE = ANALYSIS / "k_selection_1_20" / "K1_20_complete_comparison.csv"
RESULTS_FILE = ANALYSIS / "k_selection_1_20" / "K1_20_selection_results.json"
OUT = ANALYSIS / "methods_pca_k_selection"
SOURCE = OUT / "source_data"
STEM = OUT / "ExtendedData_Figure1_PCA_and_cluster_selection_v6"


DOMAIN_COLOURS = {
    "Heat": "#C95D45",
    "Pollution": "#7567A8",
    "Greenery": "#2B9B73",
    "Park accessibility": "#4D8FB3",
    "Built environment": "#66737D",
}
GREY = "#9AA1A6"
DARK = "#263238"
LIGHT = "#E5E9EC"
PRIMARY = "#27628D"
INTERNAL = "#D28E2D"
FAIL = "#C4C9CD"


def setup_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
            "font.size": 7.0,
            "axes.titlesize": 8.2,
            "axes.labelsize": 7.2,
            "xtick.labelsize": 6.5,
            "ytick.labelsize": 6.5,
            "axes.linewidth": 0.65,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "xtick.major.width": 0.6,
            "ytick.major.width": 0.6,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
        }
    )


def panel_label(ax: plt.Axes, label: str, x: float = -0.08, y: float = 1.08) -> None:
    ax.text(
        x,
        y,
        label,
        transform=ax.transAxes,
        fontsize=9.2,
        fontweight="bold",
        va="top",
        ha="left",
        clip_on=False,
    )


def arrow(ax: plt.Axes, x0: float, x1: float, y: float) -> None:
    ax.add_patch(
        FancyArrowPatch(
            (x0, y),
            (x1, y),
            arrowstyle="-|>",
            mutation_scale=8,
            linewidth=0.7,
            color="#9CA5AB",
            transform=ax.transAxes,
            clip_on=False,
        )
    )


def draw_pca_panel(ax: plt.Axes, pca: pd.DataFrame) -> None:
    ax.set_axis_off()
    panel_label(ax, "a", x=-0.025, y=1.02)

    # Dedicated columns prevent long domain names from colliding with the bars.
    x_domain = 0.01
    x_raw_start, x_raw_count = 0.190, 0.325
    x_pc_start, x_pc_count = 0.405, 0.505
    x_var, x_bal = 0.635, 0.805
    headers = [
        (0.247, "Raw variables"),
        (0.448, "Retained PCs (≥80%)"),
        (x_var, "Variance retained"),
        (x_bal, "Clustering contribution"),
    ]
    for x, text in headers:
        ax.text(x, 0.91, text, transform=ax.transAxes, ha="center", va="bottom",
                fontsize=6.8, fontweight="bold", color=DARK)

    y_positions = np.linspace(0.77, 0.29, len(pca))
    max_raw = float(pca["input_variables"].max())
    max_pc = float(pca["retained_components"].max())
    for y, row in zip(y_positions, pca.itertuples(index=False)):
        colour = DOMAIN_COLOURS[row.domain]
        ax.text(x_domain, y, row.domain.replace("Pollution", "PM$_{2.5}$"),
                transform=ax.transAxes, ha="left", va="center",
                fontsize=7.0, color=colour, fontweight="bold")

        raw_width = 0.112 * row.input_variables / max_raw
        ax.add_patch(FancyBboxPatch(
            (x_raw_start, y - 0.021), raw_width, 0.042,
            boxstyle="round,pad=0.002,rounding_size=0.006",
            transform=ax.transAxes, facecolor=colour, edgecolor="none", alpha=0.88,
        ))
        ax.text(x_raw_count, y, f"{row.input_variables}", transform=ax.transAxes,
                ha="center", va="center", fontsize=6.7, color=DARK)

        pc_width = 0.070 * row.retained_components / max_pc
        ax.add_patch(FancyBboxPatch(
            (x_pc_start, y - 0.021), pc_width, 0.042,
            boxstyle="round,pad=0.002,rounding_size=0.006",
            transform=ax.transAxes, facecolor=colour, edgecolor="none", alpha=0.88,
        ))
        ax.text(x_pc_count, y, f"{row.retained_components}", transform=ax.transAxes,
                ha="center", va="center", fontsize=6.7, color=DARK)

        ax.text(x_var, y, f"{row.variance_explained_pct:.1f}%", transform=ax.transAxes,
                ha="center", va="center", fontsize=7.0, color=DARK)
        ax.text(x_bal, y, "20%", transform=ax.transAxes,
                ha="center", va="center", fontsize=7.0, color=DARK, fontweight="bold")

    arrow(ax, 0.346, 0.382, 0.53)
    arrow(ax, 0.535, 0.575, 0.53)
    arrow(ax, 0.702, 0.745, 0.53)

    ax.text(0.01, 0.065, "Transform and standardize", transform=ax.transAxes,
            ha="left", va="bottom", fontsize=6.2, color=DARK)
    ax.text(0.445, 0.065, "PCA within each domain", transform=ax.transAxes,
            ha="center", va="bottom", fontsize=6.2, color=DARK)
    ax.text(0.635, 0.065, "Whiten retained scores", transform=ax.transAxes,
            ha="center", va="bottom", fontsize=6.2, color=DARK)
    ax.text(0.805, 0.065, r"Scale by $1/\\sqrt{q_d}$", transform=ax.transAxes,
            ha="center", va="bottom", fontsize=6.2, color=DARK)

    ax.add_patch(FancyBboxPatch(
        (0.905, 0.27), 0.082, 0.50,
        boxstyle="round,pad=0.012,rounding_size=0.012",
        transform=ax.transAxes, facecolor="#F2F5F7", edgecolor="#AAB3B9", lw=0.7,
    ))
    ax.text(0.946, 0.60, "12-PC\\nbalanced\\nmatrix", transform=ax.transAxes,
            ha="center", va="center", fontsize=7.0, fontweight="bold", color=DARK)
    ax.text(0.946, 0.41, "23 partitions\\nper K", transform=ax.transAxes,
            ha="center", va="center", fontsize=6.4, color=DARK)
    ax.text(0.946, 0.31, "consensus", transform=ax.transAxes,
            ha="center", va="center", fontsize=6.4, color=PRIMARY, fontweight="bold")
    # Stop the connector before the box so the arrowhead remains fully visible.
    arrow(ax, 0.852, 0.890, 0.53)


def style_small_axis(ax: plt.Axes) -> None:
    ax.grid(axis="y", color="#E8EBED", linewidth=0.5, zorder=0)
    ax.tick_params(length=2.5, color="#6F777C")
    ax.spines["left"].set_color("#70777C")
    ax.spines["bottom"].set_color("#70777C")


def draw_internal_panel(fig: plt.Figure, spec, ktable: pd.DataFrame) -> None:
    # Three explicitly labelled vertical subpanels. Extra separation and upper
    # headroom keep near-perfect stability markers clear of adjacent axes.
    sub = spec.subgridspec(3, 1, hspace=0.20)
    metrics = [
        ("silhouette_mean", "Mean silhouette", None, (0.07, 0.19)),
        ("bootstrap_ari_mean", "Bootstrap ARI", 0.70, (0.60, 1.06)),
        ("clusterwise_jaccard_minimum", "Weakest-cluster Jaccard", 0.60, (0.0, 1.10)),
    ]
    axes = []
    for i, (column, ylabel, threshold, ylim) in enumerate(metrics):
        ax = fig.add_subplot(sub[i, 0])
        axes.append(ax)
        style_small_axis(ax)
        ax.text(
            0.00, 1.05, f"b{i + 1}", transform=ax.transAxes,
            fontsize=8.2, fontweight="bold", ha="left", va="bottom",
            clip_on=False,
        )
        values = pd.to_numeric(ktable[column], errors="coerce")
        ax.plot(ktable["k"], values, color=GREY, lw=1.0, marker="o", ms=2.3,
                mfc="white", mec=GREY, mew=0.7, zorder=2)
        for kval, colour, filled in [(4, PRIMARY, True), (5, INTERNAL, False)]:
            row = ktable.loc[ktable["k"].eq(kval)].iloc[0]
            ax.scatter(kval, row[column], s=30, facecolor=colour if filled else "white",
                       edgecolor=colour, linewidth=1.2, zorder=4)
        if threshold is not None:
            ax.axhline(threshold, color="#B6674C", lw=0.8, ls=(0, (3, 2)), zorder=1)
            ax.text(20.05, threshold, f" {threshold:.2f}", va="center", ha="left",
                    fontsize=5.8, color="#9A523C", clip_on=False)
        ax.set_ylim(*ylim)
        ax.set_xlim(1.7, 20.3)
        ax.set_ylabel(ylabel, labelpad=4)
        ax.set_xticks([2, 4, 6, 8, 10, 12, 14, 16, 18, 20])
        if i < 2:
            ax.set_xticklabels([])
        else:
            ax.set_xlabel("Number of archetypes, K")
    top = axes[0]
    k4 = ktable.loc[ktable["k"].eq(4), "silhouette_mean"].iloc[0]
    k5 = ktable.loc[ktable["k"].eq(5), "silhouette_mean"].iloc[0]
    top.annotate("K=4", xy=(4, k4), xytext=(3.05, 0.184), color=PRIMARY,
                 fontsize=5.9, fontweight="bold",
                 arrowprops=dict(arrowstyle="-", color=PRIMARY, lw=0.55))
    top.annotate("K=5 internal optimum", xy=(5, k5), xytext=(6.05, 0.184), color=INTERNAL,
                 fontsize=5.9, ha="left",
                 arrowprops=dict(arrowstyle="-", color=INTERNAL, lw=0.55))


def draw_viability_panel(ax: plt.Axes, ktable: pd.DataFrame) -> None:
    style_small_axis(ax)
    panel_label(ax, "c", x=-0.16, y=1.06)
    eligible = ktable["internal_viable"].astype(bool)
    colours = np.where(eligible, "#73858F", FAIL)
    ax.vlines(ktable["k"], 0.35, ktable["minimum_cluster_share_pct"],
              color=colours, lw=1.0, zorder=1)
    ax.scatter(ktable["k"], ktable["minimum_cluster_share_pct"], s=18,
               c=colours, edgecolors="white", linewidths=0.45, zorder=2)
    for kval, colour in [(4, PRIMARY), (5, INTERNAL)]:
        row = ktable.loc[ktable["k"].eq(kval)].iloc[0]
        ax.scatter(kval, row["minimum_cluster_share_pct"], s=48, facecolor=colour,
                   edgecolor="white", linewidth=0.8, zorder=4)
    ax.axhline(2.0, color="#B6674C", lw=0.9, ls=(0, (3, 2)))
    ax.text(19.9, 2.15, "2% gate", ha="right", va="bottom", color="#9A523C", fontsize=6.0)
    ax.set_yscale("log")
    ax.set_ylim(0.35, 70)
    ax.set_xlim(1.7, 20.3)
    ax.set_xticks([2, 4, 6, 8, 10, 12, 14, 16, 18, 20])
    ax.set_yticks([0.5, 1, 2, 5, 10, 20, 50])
    ax.get_yaxis().set_major_formatter(
        mpl.ticker.FuncFormatter(lambda value, _: f"{value:g}")
    )
    ax.set_xlabel("Number of archetypes, K")
    ax.set_ylabel("Minimum cluster share (%)")
    ax.text(0.98, 0.91, "K≥10 below 2%",
            transform=ax.transAxes, fontsize=6.1, color=DARK, ha="right")


def draw_spatial_panel(ax: plt.Axes, ktable: pd.DataFrame) -> None:
    style_small_axis(ax)
    panel_label(ax, "d", x=-0.16, y=1.06)
    spatial = ktable.loc[ktable["mean_blocked_ari"].notna()].copy()
    sizes = 20 + 3.0 * np.sqrt(spatial["minimum_cluster_share_pct"].clip(lower=0))
    for (_, row), size in zip(spatial.iterrows(), sizes):
        kval = int(row["k"])
        if kval == 4:
            face, edge, lw = PRIMARY, PRIMARY, 1.1
        elif kval == 5:
            face, edge, lw = "white", INTERNAL, 1.4
        elif bool(row["strict_pass"]):
            face, edge, lw = "#6F7F89", "#6F7F89", 0.8
        else:
            face, edge, lw = "white", "#A7AFB4", 1.0
        ax.scatter(row["mean_blocked_ari"], row["minimum_pooled_class_recall"],
                   s=float(size), facecolor=face, edgecolor=edge, linewidth=lw, zorder=3)
        dx, dy = (0.007, 0.012)
        if kval == 4:
            ax.text(row["mean_blocked_ari"] - 0.062,
                    row["minimum_pooled_class_recall"] + 0.014,
                    "K=4 primary", fontsize=5.8, color=edge, fontweight="bold")
        elif kval == 5:
            ax.annotate(
                "K=5 internal optimum",
                xy=(row["mean_blocked_ari"], row["minimum_pooled_class_recall"]),
                xytext=(0.705, 0.765),
                fontsize=5.8, color=edge, fontweight="bold", ha="left",
                arrowprops=dict(arrowstyle="-", color=edge, lw=0.55),
            )
        else:
            ax.text(row["mean_blocked_ari"] + dx,
                    row["minimum_pooled_class_recall"] + dy,
                    str(kval), fontsize=5.8, color=edge)
    ax.axvline(0.50, color="#B6674C", lw=0.8, ls=(0, (3, 2)))
    ax.axhline(0.60, color="#B6674C", lw=0.8, ls=(0, (3, 2)))
    ax.set_xlim(0.48, 0.86)
    ax.set_ylim(0.55, 0.96)
    ax.set_xlabel("Mean blocked ARI")
    ax.set_ylabel("Weakest pooled cluster recall")

    selected = spatial.loc[spatial["k"].eq(4)].iloc[0]
    text = (
        "K=4 retained\\n"
        f"mean blocked ARI  {selected['mean_blocked_ari']:.3f}\\n"
        f"minimum-fold ARI  {selected['minimum_fold_blocked_ari']:.3f}\\n"
        f"weakest recall  {selected['minimum_pooled_class_recall']:.3f}"
    )
    ax.text(0.03, 0.30, text, transform=ax.transAxes, va="bottom", ha="left",
            fontsize=6.1, linespacing=1.25, color=DARK,
            bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="#C7CDD1", lw=0.6))

def save_outputs(fig: plt.Figure) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(STEM.with_suffix(".svg"), bbox_inches="tight", facecolor="white")
    fig.savefig(STEM.with_suffix(".pdf"), bbox_inches="tight", facecolor="white")
    fig.savefig(STEM.with_suffix(".png"), dpi=600, bbox_inches="tight", facecolor="white")
    fig.savefig(STEM.with_suffix(".tiff"), dpi=600, bbox_inches="tight", facecolor="white",
                pil_kwargs={"compression": "tiff_lzw"})


def main() -> None:
    setup_style()
    OUT.mkdir(parents=True, exist_ok=True)
    SOURCE.mkdir(parents=True, exist_ok=True)
    pca = pd.read_csv(PCA_FILE)
    ktable = pd.read_csv(K_FILE)
    results = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))

    required_pca = {
        "domain", "input_variables", "retained_components",
        "variance_explained_pct", "domain_weight",
    }
    required_k = {
        "k", "silhouette_mean", "bootstrap_ari_mean",
        "clusterwise_jaccard_minimum", "minimum_cluster_share_pct",
        "internal_viable", "mean_blocked_ari", "minimum_fold_blocked_ari",
        "minimum_pooled_class_recall", "strict_pass",
    }
    if not required_pca.issubset(pca.columns):
        raise ValueError(f"Missing PCA fields: {sorted(required_pca - set(pca.columns))}")
    if not required_k.issubset(ktable.columns):
        raise ValueError(f"Missing K-selection fields: {sorted(required_k - set(ktable.columns))}")
    if int(pca["input_variables"].sum()) != 124:
        raise ValueError("The frozen PCA contract no longer sums to 124 variables")
    if int(pca["retained_components"].sum()) != 12:
        raise ValueError("The frozen PCA contract no longer sums to 12 retained PCs")
    if results["selected_primary_k"] != 4 or results["statistical_optimum_k"] != 5:
        raise ValueError("The frozen K-selection decision has changed")

    pca.to_csv(SOURCE / "panel_a_domain_pca_summary.csv", index=False)
    plotted_columns = [
        "k", "silhouette_mean", "bootstrap_ari_mean",
        "clusterwise_jaccard_minimum", "minimum_cluster_share_pct",
        "internal_viable", "mean_blocked_ari", "minimum_fold_blocked_ari",
        "minimum_pooled_class_recall", "strict_pass", "statistical_optimum",
        "selected_primary",
    ]
    ktable[plotted_columns].to_csv(SOURCE / "panels_bcd_k_selection_metrics.csv", index=False)

    fig = plt.figure(figsize=(7.20, 5.45), constrained_layout=False)
    outer = fig.add_gridspec(
        2, 3,
        height_ratios=[0.70, 1.50],
        width_ratios=[1.16, 0.86, 1.03],
        hspace=0.24, wspace=0.34,
        left=0.075, right=0.975, top=0.965, bottom=0.095,
    )
    ax_a = fig.add_subplot(outer[0, :])
    draw_pca_panel(ax_a, pca)
    draw_internal_panel(fig, outer[1, 0], ktable.loc[ktable["k"].ge(2)])
    ax_c = fig.add_subplot(outer[1, 1])
    draw_viability_panel(ax_c, ktable.loc[ktable["k"].ge(2)])
    ax_d = fig.add_subplot(outer[1, 2])
    draw_spatial_panel(ax_d, ktable)
    save_outputs(fig)
    plt.close(fig)

    selected = ktable.loc[ktable["k"].eq(4)].iloc[0]
    internal = ktable.loc[ktable["k"].eq(5)].iloc[0]
    qa = {
        "figure_contract": {
            "core_conclusion": (
                "Within-domain PCA prevents high-dimensional domains from dominating, "
                "and K=4 is retained because it combines internal reproducibility with "
                "the strongest planning-area-blocked recovery among strict candidates."
            ),
            "archetype": "asymmetric mixed-modality figure",
            "population": "101,545 all-residential-proxy postcodes",
            "raw_variables": 124,
            "retained_components": 12,
            "domain_contribution_pct": 20,
            "candidate_partitions": "K=2–20; K=1 unpartitioned reference",
        },
        "selection": {
            "selected_primary_k": 4,
            "statistical_internal_optimum_k": 5,
            "k4": {
                "minimum_cluster_share_pct": float(selected["minimum_cluster_share_pct"]),
                "bootstrap_ari": float(selected["bootstrap_ari_mean"]),
                "weakest_jaccard": float(selected["clusterwise_jaccard_minimum"]),
                "mean_blocked_ari": float(selected["mean_blocked_ari"]),
                "minimum_fold_blocked_ari": float(selected["minimum_fold_blocked_ari"]),
                "weakest_pooled_recall": float(selected["minimum_pooled_class_recall"]),
            },
            "k5": {
                "minimum_cluster_share_pct": float(internal["minimum_cluster_share_pct"]),
                "bootstrap_ari": float(internal["bootstrap_ari_mean"]),
                "weakest_jaccard": float(internal["clusterwise_jaccard_minimum"]),
                "mean_blocked_ari": float(internal["mean_blocked_ari"]),
                "minimum_fold_blocked_ari": float(internal["minimum_fold_blocked_ari"]),
                "weakest_pooled_recall": float(internal["minimum_pooled_class_recall"]),
            },
        },
        "exclusions": "None; all K=2–20 internal metrics and every spatially advanced solution are shown.",
        "outputs": [str(STEM.with_suffix(ext)) for ext in (".svg", ".pdf", ".png", ".tiff")],
    }
    (OUT / "ExtendedData_Figure1_PCA_and_cluster_selection_v6_QA.json").write_text(
        json.dumps(qa, indent=2), encoding="utf-8"
    )
    print(json.dumps(qa, indent=2))


if __name__ == "__main__":
    main()
'''

ENTRY = '''
"""Reproduce Figure 2 from processed PCA and K=1--20 diagnostics."""
from pathlib import Path
import sys
import matplotlib as mpl
mpl.use('Agg')

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'code'))
import plot_extended_data_pca_cluster_selection as renderer

renderer.ROOT = HERE
renderer.ANALYSIS = HERE / 'data'
renderer.PCA_FILE = renderer.ANALYSIS / 'domain_pca_summary.csv'
renderer.K_FILE = renderer.ANALYSIS / 'K1_20_complete_comparison.csv'
renderer.RESULTS_FILE = renderer.ANALYSIS / 'K1_20_selection_results.json'
renderer.OUT = HERE / 'output'
renderer.SOURCE = renderer.OUT / 'source_data'
renderer.STEM = renderer.OUT / 'Figure2_PCA_cluster_selection'
renderer.main()
'''

if __name__ == "__main__":
    main()
