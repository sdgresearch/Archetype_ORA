"""Figure 7: Location-weighted inequality, need-weighted Lorenz curves ranked by cooling/need, and row-specific housing ORA. Saved 499-planning-area-bootstrap pointwise intervals, all crossings retained.

Run: python Figure7_cooling_equity.py
Optional: --output-dir my_figures --csv Figure7_cooling_equity.csv
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

FIGURE_NUMBER = 7
FIGURE_NAME = 'Figure7_cooling_equity'
OUTPUT_RELATIVE_STEM = 'figures/Figure7_cooling_equity'

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

# ----- figure7_renderer -----
RENDERERS['figure7_renderer'] = '''from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from types import SimpleNamespace
OUT = Path(__file__).resolve().parents[1] / 'data'
HDB, OTHER = '#222222', '#6F8EA8'
ARCHETYPE_COLORS = ['#009E73', '#D55E00', '#0072B2', '#CC79A7']
CMAP = LinearSegmentedColormap.from_list('ora_v5', ['#356994', '#F1F0EC', '#B05838'])
ORA_CLIP = 0.50
ORA_NORM = TwoSlopeNorm(vmin=-ORA_CLIP, vcenter=0, vmax=ORA_CLIP)
NORM = ORA_NORM
ROWS = ['High socioeconomic vulnerability', 'Need-aligned service', 'Priority deficit']
ROW_LABELS = ['High socioeconomic\\nvulnerability',
              'Need-aligned service\\nHigh thermal load · higher cooling',
              'Priority deficit\\nHigh thermal load · low cooling']
helper = SimpleNamespace(GROUPS=[('HDB',1,HDB,'o'), ('Other residential',0,OTHER,'D')])
mpl.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','Helvetica','DejaVu Sans'],
    'font.size':7,'axes.labelsize':6.8,'xtick.labelsize':6.1,'ytick.labelsize':6.1,
    'axes.linewidth':.55,'axes.spines.top':False,'axes.spines.right':False,
    'legend.frameon':False,'legend.fontsize':6.2,'xtick.major.size':2.4,'ytick.major.size':2.4,
    'svg.fonttype':'none','pdf.fonttype':42,
    'savefig.facecolor':'white','figure.facecolor':'white','axes.facecolor':'white'})

def draw_curve_panel(ax, ranking, stats, point, bands):
    ax.set(xlim=(0, 100), ylim=(0, 100), xticks=[0, 25, 50, 75, 100], yticks=[0, 25, 50, 75, 100])
    reference_color = "#AEB6BC" if ranking == "Lorenz" else "#BBC2C7"
    reference_width = 0.95 if ranking == "Lorenz" else 0.82
    ax.plot([0, 100], [0, 100], color=reference_color, lw=reference_width, ls=(0, (1.6, 2.3)), zorder=1)
    ax.spines["left"].set_color("#62686C")
    ax.spines["bottom"].set_color("#62686C")
    ax.tick_params(colors="#303438", width=0.5)
    ax.set_ylabel("Cumulative accessible cooling (%)", labelpad=3)
    for group, color, linestyle, linewidth, alpha in (
        ("HDB", HDB, "-", 1.55, 0.075),
        ("Other residential", OTHER, (0, (4.5, 2.7)), 1.35, 0.15),
    ):
        q = point[(point.group.eq(group)) & (point.ranking.eq(ranking))]
        band = bands[(bands.group.eq(group)) & (bands.ranking.eq(ranking))]
        ax.fill_between(
            band.cumulative_weight.to_numpy() * 100,
            band.ci_low.to_numpy() * 100,
            band.ci_high.to_numpy() * 100,
            color=color, alpha=alpha, linewidth=0, zorder=2,
        )
        ax.plot(
            q.cumulative_weight.to_numpy() * 100,
            q.cumulative_cooling.to_numpy() * 100,
            color=color, lw=linewidth, ls=linestyle, zorder=4,
        )
    if ranking == "Lorenz":
        for group, color, marker, tx, ty in (
            ("HDB", HDB, "o", 78, 8.5),
            ("Other residential", OTHER, "D", 42, 16.5),
        ):
            row = stats.loc[group]
            p = row.unserved * 100
            ax.scatter(p, 0, s=18, marker=marker, facecolor=color if group == "HDB" else "white", edgecolor=color, linewidth=0.8, clip_on=False, zorder=6)
            ax.annotate(
                f"{p:.1f}%", xy=(p, 0.7), xytext=(tx, ty),
                color=color, fontsize=5.7, ha="center", va="center",
                arrowprops={"arrowstyle": "-", "color": color, "lw": 0.55, "shrinkA": 1, "shrinkB": 2}, zorder=7,
            )
        ax.text(0.035, 0.95, f"HDB: G = {stats.loc['HDB'].gini:.3f}\\n{stats.loc['HDB'].unserved*100:.1f}% unserved", transform=ax.transAxes, va="top", color=HDB, fontsize=6.15)
        ax.text(0.035, 0.74, f"Other residential: G = {stats.loc['Other residential'].gini:.3f}\\n{stats.loc['Other residential'].unserved*100:.1f}% unserved", transform=ax.transAxes, va="top", color=OTHER, fontsize=6.15)
        ax.set_xlabel("Cumulative residential locations (%)", labelpad=3)
    else:
        ax.text(0.035, 0.95, f"HDB: CI = {stats.loc['HDB'].concentration:+.3f}", transform=ax.transAxes, va="top", color=HDB, fontsize=6.15)
        ax.text(0.035, 0.83, f"Other residential: CI = {stats.loc['Other residential'].concentration:+.3f}", transform=ax.transAxes, va="top", color=OTHER, fontsize=6.15)
        ax.text(50, 96, "Above equality\\nLower-need concentration", color="#737A7F", fontsize=5.05, ha="center", va="top")
        ax.text(68, 18, "Below equality\\nHigher-need concentration", color="#737A7F", fontsize=5.05, ha="center", va="center")
        ax.set_xlabel("Residential locations ranked by thermal need (%)\\nLower need                                    Higher need", fontsize=6.15, labelpad=3)

def draw_lorenz_base(ax, stats, point, bands):
    """Reuse the accepted Lorenz panel and move the HDB unserved callout."""
    draw_curve_panel(ax, "Lorenz", stats, point, bands)
    for text in ax.texts:
        if text.get_text() == "63.3%":
            text.set_position((73.0, 15.0))
            text.set_horizontalalignment("center")
            text.set_verticalalignment("center")
            text.set_bbox({"facecolor": "white", "edgecolor": "none", "alpha": 0.86, "pad": 0.8})

def draw_lorenz(ax, stats, point, bands):
    """Draw the accepted Lorenz analysis with shorter labels and statistics."""
    draw_lorenz_base(ax, stats, point, bands)
    ax.set_xlabel("Cumulative locations (%)", labelpad=3)
    ax.set_ylabel("Cumulative accessible cooling (%)", labelpad=3)

    hdb = stats.loc["HDB"]
    other = stats.loc["Other residential"]
    for item in ax.texts:
        if item.get_text().startswith("HDB: G ="):
            item.set_text(f"HDB  G={hdb.gini:.3f} · {hdb.unserved * 100:.1f}% unserved")
            item.set_position((0.035, 0.945))
            item.set_fontsize(6.0)
        elif item.get_text().startswith("Other residential: G ="):
            item.set_text(f"Other  G={other.gini:.3f} · {other.unserved * 100:.1f}% unserved")
            item.set_position((0.035, 0.845))
            item.set_fontsize(6.0)

def share_size(pct):
    """Marker area is proportional to an identical 0-100% scale for all cells."""
    return 11.0 + 3.0 * max(float(pct), 0.0)

def panel_c_matrix(fig):
    data = pd.read_csv(OUT / "panel_c_mixed_scope_ORA.csv")
    ax = fig.add_axes([0.20, 0.175, 0.74, 0.245])
    ax.axhspan(-0.40, 0.40, color="#EEF2F5", lw=0, zorder=0)
    ax.axhline(0.50, color="#C7CDD1", lw=0.65, zorder=1)
    ax.axhspan(1.60, 2.40, color="#F7EEE9", lw=0, zorder=0)
    for separator in (1.5, 3.5, 5.5):
        ax.axvline(separator, color="#D8DDE0", lw=0.55, zorder=1)

    for archetype in range(1, 5):
        left = 2 * (archetype - 1)
        centre = left + 0.5
        colour = ARCHETYPE_COLORS[archetype - 1]
        ax.plot([left - 0.38, left + 1.38], [-0.88, -0.88], color=colour, lw=1.45, clip_on=False)
        ax.text(centre, -0.69, f"A{archetype}", color=colour, fontsize=6.8, fontweight="bold", ha="center", va="center")
        ax.text(left, -0.34, "HDB", color=HDB, fontsize=5.2, ha="center", va="center")
        ax.text(left + 1, -0.34, "Other", color=OTHER, fontsize=5.2, ha="center", va="center")

    for row, state in enumerate(ROWS):
        for archetype in range(1, 5):
            for housing, offset, marker in (("HDB", 0, "o"), ("Other residential", 1, "D")):
                q = data[
                    data.archetype.eq(archetype)
                    & data.state.eq(state)
                    & data.housing.eq(housing)
                ]
                if len(q) != 1:
                    raise RuntimeError(f"Expected one row for A{archetype}, {state}, {housing}; found {len(q)}")
                item = q.iloc[0]
                x = 2 * (archetype - 1) + offset
                if not np.isfinite(item.enrichment):
                    ax.text(x, row, "NA", ha="center", va="center", fontsize=5.2, color="#828C94")
                elif item.enrichment <= 0:
                    ax.scatter(x, row, s=15, marker="x", color="#71818C", linewidths=0.75, zorder=3)
                else:
                    colour = CMAP(NORM(np.clip(item.log2_enrichment, -2, 2)))
                    ax.scatter(
                        x, row, s=share_size(item.affected_share_pct), marker=marker,
                        c=[colour], edgecolors="#4F5C64", linewidth=0.60, zorder=3,
                    )

    ax.set(
        xlim=(-0.55, 7.55), ylim=(2.47, -0.98),
        xticks=[], yticks=range(3), yticklabels=ROW_LABELS,
    )
    ax.tick_params(axis="y", length=0, pad=5)
    ax.get_yticklabels()[2].set_fontweight("bold")
    ax.get_yticklabels()[2].set_color("#813D25")
    for spine in ax.spines.values():
        spine.set_visible(False)

def draw_panel_c(fig):
    panel_c_matrix(fig)
    ax = fig.axes[-1]
    ax.set_position([.20, .175, .74, .285])
    for item in ax.texts:
        if item.get_text() in {'HDB', 'Other'}:
            item.set_visible(False)

def draw_legends(fig):
    """Draw compact housing, affected-share and interpretable ORA legends."""
    key = fig.add_axes([0.20, 0.025, 0.46, 0.105])
    key.set(xlim=(0, 1), ylim=(0, 1))
    key.axis("off")

    key.text(0.00, 0.91, "Housing", fontsize=5.8, fontweight="bold", va="top")
    key.scatter(0.02, 0.52, s=29, marker="o", facecolor="#F1F0EC",
                edgecolor="#4F5C64", linewidth=0.75)
    key.text(0.07, 0.52, "HDB", fontsize=5.55, va="center")
    key.scatter(0.20, 0.52, s=29, marker="D", facecolor="#F1F0EC",
                edgecolor="#4F5C64", linewidth=0.75)
    key.text(0.255, 0.52, "Other residential", fontsize=5.55, va="center")

    key.text(0.50, 0.91, "Affected share (%)", fontsize=5.8,
             fontweight="bold", va="top")
    for x, value in zip((0.52, 0.66, 0.81, 0.96), (10, 25, 50, 75)):
        key.scatter(
            x, 0.48, s=share_size(value), marker="o",
            facecolor="#D9DDE0", edgecolor="#58666F", linewidth=0.7,
        )
        key.text(x, 0.09, f"{value}", fontsize=5.25, ha="center", va="center")

    cax = fig.add_axes([0.69, 0.068, 0.25, 0.014])
    cb = fig.colorbar(
        mpl.cm.ScalarMappable(norm=ORA_NORM, cmap=CMAP),
        cax=cax, orientation="horizontal",
    )
    cb.set_ticks(
        [-ORA_CLIP, 0, ORA_CLIP],
        labels=["\\u22640.7\\u00d7", "1", "\\u22651.4\\u00d7"],
    )
    cb.set_label("ORR", fontsize=5.75,
                 labelpad=1.5)
    cb.outline.set_visible(False)

def draw_b(ax,full,grid,draws,stats):
    ax.plot([0,100],[0,100],color='#AFB7BD',ls=(0,(1.6,2.3)),lw=.85,zorder=1)
    for g,(name,_,color,_) in enumerate(helper.GROUPS):
        lo,hi=draws[g]  # Actual saved pointwise 95% bootstrap limits
        ax.fill_between(grid*100,lo*100,hi*100,color=color,alpha=.075 if g==0 else .11,lw=0,zorder=2)
        x,y=full[g]
        ax.plot(x*100,y*100,color=color,lw=1.55 if g==0 else 1.35,
            ls='-' if g==0 else (0,(4.5,2.7)),zorder=4,
            label=f'{name}  D={stats.iloc[g].D:.3f}')
    ax.legend(loc='upper left',frameon=False,fontsize=6,handlelength=2.2,labelspacing=.45)
    ax.text(30,66,'Accessible cooling\\nproportional to need',fontsize=5.8,color='#60666A',ha='center',va='center')
    ax.annotate('',xy=(42,42),xytext=(31,58),arrowprops={'arrowstyle':'-','color':'#92989B','lw':.5})
    ax.set(xlim=(0,100),ylim=(0,100),xticks=[0,25,50,75,100],yticks=[0,25,50,75,100])
    ax.set_xlabel('Cumulative thermal need (%)',labelpad=3)
    ax.set_ylabel('Cumulative accessible cooling (%)',labelpad=3)
    ax.text(.5,-.235,'Lowest → highest accessible cooling per unit need',transform=ax.transAxes,
            ha='center',va='top',fontsize=5.5)
    ax.tick_params(length=2.5,width=.5,pad=2)

def render():
    vertices = pd.read_csv(OUT / 'need_weighted_lorenz_full_vertices.csv', float_precision='round_trip')
    bands = pd.read_csv(OUT / 'need_weighted_lorenz_pointwise_95.csv', float_precision='round_trip')
    stats = pd.read_csv(OUT / 'need_weighted_lorenz_statistics.csv', float_precision='round_trip')
    full, limits = [], []
    for group in ['HDB', 'Other residential']:
        point = vertices.loc[vertices.group.eq(group)]
        band = bands.loc[bands.group.eq(group)]
        full.append((point.need_share.to_numpy(), point.accessible_cooling_share.to_numpy()))
        limits.append(np.array([band.ci_low, band.ci_high]))
    grid = bands.loc[bands.group.eq('HDB'), 'need_share'].to_numpy()
    fig = plt.figure(figsize=(7.2, 4.65))
    fig.text(.025,.965,'a',fontsize=10,fontweight='bold',va='top')
    draw_lorenz(fig.add_axes([.10,.585,.37,.345]),
        pd.read_csv(OUT/'cumulative_curve_statistics.csv').set_index('group'),
        pd.read_csv(OUT/'cumulative_curve_source.csv'),
        pd.read_csv(OUT/'curve_bootstrap_pointwise_95.csv'))
    fig.text(.525,.965,'b',fontsize=10,fontweight='bold',va='top')
    draw_b(fig.add_axes([.60,.585,.37,.345]),full,grid,np.array(limits),stats)
    fig.text(.025,.505,'c',fontsize=10,fontweight='bold',va='top')
    draw_panel_c(fig)
    draw_legends(fig)
    output = OUT.parent / 'output/figures'
    output.mkdir(parents=True, exist_ok=True)
    stem = output / 'Figure7_cooling_equity'
    fig.savefig(stem.with_suffix('.svg'))
    fig.savefig(stem.with_suffix('.pdf'))
    fig.savefig(stem.with_suffix('.png'), dpi=600)
    fig.savefig(stem.with_suffix('.tiff'), dpi=600, pil_kwargs={'compression':'tiff_lzw'})
    plt.close(fig)
'''

ENTRY = '''from pathlib import Path
HERE = Path(__file__).resolve().parent
import figure7_renderer
figure7_renderer.render()
'''

if __name__ == "__main__":
    main()
