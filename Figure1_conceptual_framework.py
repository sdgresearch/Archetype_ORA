"""Figure 1: Illustrative conceptual geometry only: resources, cooling efficacy, accessibility and need alignment. Not observed data.

Run: python Figure1_conceptual_framework.py
Optional: --output-dir my_figures --csv Figure1_conceptual_framework.csv
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

FIGURE_NUMBER = 1
FIGURE_NAME = 'Figure1_conceptual_framework'
OUTPUT_RELATIVE_STEM = 'Figure1_conceptual_framework'

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

# ----- plot_intro_concept_v6 -----
RENDERERS['plot_intro_concept_v6'] = '''"""Draw a problem-setting CONCEPTUAL schematic; no study estimates are plotted.

Analytical curves and coordinates below are explicitly illustrative geometry.
They are not fitted data, empirical forecasts or named archetype responses.
This script is independent of all manuscript figure-generation pipelines.
"""
from pathlib import Path
import json
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, PathPatch
from matplotlib.path import Path as MPath
import numpy as np
from PIL import Image, ImageOps

OUT = Path(__file__).resolve().parents[1] / "output"
OUT.mkdir(parents=True, exist_ok=True)
STEM = "Figure1_conceptual_framework"
WIDTH_MM = 183
HEIGHT_MM = 80
DPI = 600
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 7.2,
    "axes.labelsize": 7.2,
    "xtick.labelsize": 6.5,
    "ytick.labelsize": 6.5,
    "axes.linewidth": 0.65,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
    "pdf.use14corefonts": False,
    "savefig.facecolor": "white",
    "figure.facecolor": "white",
})
INK = "#222222"
BLUE = "#427C9D"
BLUE_PALE = "#E2EDF3"
GREEN = "#47735A"
GREEN_PALE = "#D9E5DA"
GREY = "#81898F"
LIGHT = "#C7CDD1"
ORANGE_PALE = "#F7E9DE"


def add_text(fig, x, y, string, **kw):
    return fig.text(x, y, string, color=INK, **kw)


def house(ax, x, y, color, filled=False, size=0.043):
    verts = [(x-size, y-size*.7), (x+size, y-size*.7),
             (x+size, y+size*.55), (x, y+size*1.4),
             (x-size, y+size*.55)]
    ax.add_patch(Polygon(verts, closed=True, facecolor=color if filled else "white",
                         edgecolor=color, linewidth=1.0, zorder=8))
    ax.plot([x-size*.24, x-size*.24, x+size*.2, x+size*.2],
            [y-size*.7, y+size*.02, y+size*.02, y-size*.7],
            color="white" if filled else color, lw=.6, zorder=9)


fig = plt.figure(figsize=(WIDTH_MM/25.4, HEIGHT_MM/25.4))

# The conceptual provenance is documented in the companion caption.
# Only a-c remain on the canvas; no external framing band or question.
panels = [("a", "Cooling efficacy", .063), ("b", "Cooling accessibility", .389),
          ("c", "Need alignment", .736)]
for letter, heading, xpos in panels:
    add_text(fig, xpos-.027, .943, letter, fontsize=9, fontweight="bold", va="center")
    add_text(fig, xpos, .943, heading, fontsize=8.2, fontweight="bold", va="center")

# a: two hypothetical curves, no use of empirical A1-A4 identities.
ax = fig.add_axes([.068,.257,.245,.595])
import pandas as pd
curve = pd.read_csv(OUT.parent / "data/concept_curves.csv", float_precision="round_trip")
spec = json.loads((OUT.parent / "data/concept_spec.json").read_text(encoding="utf-8"))
g = curve.g.to_numpy()
response_x = curve.response_x.to_numpy()
response_y = curve.response_y.to_numpy()
ax.plot(g,response_x, color=BLUE, lw=1.75)
ax.plot(g,response_y, color=BLUE, lw=1.5, ls=(0,(4,2)))
common=spec["common"]
y1=.96*(1-np.exp(-3*common))
y2=.57*common**1.65
ax.plot([common,common],[0,y1],color=GREY,lw=.65,ls=(0,(1.5,2)))
ax.scatter([common],[y1],s=21,c=BLUE,zorder=4)
ax.scatter([common],[y2],s=21,facecolors="white",edgecolors=BLUE,lw=1,zorder=4)
ax.text(.78,.99,"Exposome X",color=BLUE,fontsize=6.8,ha="center",va="top")
ax.text(.79,.19,"Exposome Y",color=BLUE,fontsize=6.8,ha="center",va="center")
ax.set(xlim=(0,1.04),ylim=(0,1.02),xlabel="Green provision",ylabel="Cooling efficacy")
ax.set_xticks([0,1],labels=["Low","High"])
ax.set_yticks([0,1],labels=["Low","High"])
ax.tick_params(length=2.5,pad=3)
ax.spines[["bottom","left"]].set_color(GREY)
ax.text(common,-.045,"Same green",transform=ax.transData,ha="center",va="top",fontsize=6.3)

# b: spatial geometry is a schematic, not a geographic or empirical map.
bx = fig.add_axes([.378,.228,.299,.643])
bx.set(xlim=(0,1),ylim=(0,1),aspect="equal")
bx.axis("off")
# An asymmetric cooled footprint is intentionally not identical to the green patch.
verts = spec["cooling_footprint"]
codes = [MPath.MOVETO]+[MPath.CURVE4]*12
bx.add_patch(PathPatch(MPath(verts,codes),facecolor=BLUE_PALE,edgecolor=BLUE,
                       linewidth=.9,zorder=1))
green = spec["green_patch"]
bx.add_patch(Polygon(green,closed=True,facecolor=GREEN_PALE,edgecolor=GREEN,
                     linewidth=.9,zorder=2))
# Long dashed walking route vs short route to cooled cells.
bx.plot([.84,.84,.09,.09,.34,.52],[.19,.10,.10,.30,.30,.40],
        color=GREY,lw=1.1,ls=(0,(3,2)),zorder=3)
bx.plot([.86,.77,.67],[.68,.68,.60],color=BLUE,lw=1.4,zorder=3)
bx.scatter([.67],[.60],s=9,color=BLUE,zorder=6)
bx.scatter([.52],[.40],s=9,color=GREY,zorder=6)
house(bx,.87,.69,BLUE,filled=True)
house(bx,.84,.20,GREY,filled=False)
bx.text(.555,.555,"Cooled\\nfootprint",fontsize=6.7,color=BLUE,
        ha="center",va="center",zorder=10)
bx.text(.273,.605,"Green\\npatch",ha="center",va="center",color=GREEN,fontsize=7)
bx.text(.84,.80,"Within reach",ha="center",va="center",fontsize=6.5,color=INK)
bx.text(.80,.315,"Beyond reach",ha="center",va="center",fontsize=6.5,color=INK)
bx.text(.46,.015,"Walking-network routes",fontsize=6.2,ha="center",va="bottom",color=INK)

# c: cumulative need-service schematic; residential locations ranked HIGH to LOW
# thermal need. This is not a conventional service-ranked Lorenz curve.
# For an exact illustrative reversal of F_low(x)=2*x-x**2, F_high(x)=x**2.
# The geometry is hypothetical: NO empirical observations or study estimates.
# At any interior point, x-y is the ranked group's service-share shortfall
# relative to its need share. The common (1,1) endpoint is normalization only.
cx = fig.add_axes([.737,.257,.237,.595])
x=curve.g.to_numpy()
need_reference = curve.need_reference.to_numpy()
service=curve.service.to_numpy()
assert np.all(np.diff(service)>=0) and service[0]==0 and service[-1]==1
assert np.all(service<=need_reference+1e-12)
cx.fill_between(x,service,need_reference,color=ORANGE_PALE,zorder=1)
cx.plot(x,service,color=BLUE,lw=1.7,zorder=3)
cx.plot(x,need_reference,color=GREY,lw=1.0,ls=(0,(3,2)),zorder=2)
cx.text(.66,.82,"Need-proportional\\nreference",fontsize=6.5,color=INK,
        ha="center",va="center",rotation=40)
cx.text(.70,.19,"Accessible\\ncooling service",fontsize=6.7,color=BLUE,
        ha="center",va="center")
gap_x=spec["gap_x"]
gap_bottom=gap_x**2
cx.annotate("",xy=(gap_x,gap_x-.015),xytext=(gap_x,gap_bottom+.015),
            arrowprops=dict(arrowstyle="<->",color="#95633B",lw=.85,
                            shrinkA=0,shrinkB=0,mutation_scale=8),zorder=5)
cx.annotate("High-need\\nservice shortfall",xy=(gap_x-.025,(gap_x+gap_bottom)/2),
            xytext=(.045,.76),ha="left",va="center",fontsize=6.4,
            color="#95633B",arrowprops=dict(arrowstyle="-",color="#95633B",
            lw=.65,connectionstyle="angle,angleA=-90,angleB=150,rad=3"),zorder=5)
cx.set(xlim=(0,1.02),ylim=(0,1.02),
       xlabel="Cumulative thermal need (%)",ylabel="Cumulative accessible cooling (%)")
cx.set_xticks([0,1],labels=["0","100"])
cx.set_yticks([0,1],labels=["0","100"])
cx.tick_params(length=2.5,pad=3)
cx.spines[["bottom","left"]].set_color(GREY)
# Separate the smaller ranking cue from the primary axis title.
cx.xaxis.set_label_coords(.5,-.173)
cx.xaxis.label.set_verticalalignment("top")
add_text(fig,.8555,.185,"Highest → lowest need",ha="center",va="center",fontsize=5.6)

messages = [(.19,"Same greenery ≠\\nsame cooling efficacy"),
            (.529,"Nearby cooling ≠\\ncooling accessibility"),
            (.853,"Accessible service ≠\\nneed alignment")]
for xpos,message in messages:
    add_text(fig,xpos,.073,message,ha="center",va="center",fontsize=7.0,fontweight="bold")

fig.canvas.draw()
renderer=fig.canvas.get_renderer()
text_bounds=[]
outside=[]
for obj in fig.findobj(matplotlib.text.Text):
    if not obj.get_visible() or not obj.get_text():
        continue
    bb=obj.get_window_extent(renderer).transformed(fig.transFigure.inverted())
    item={"text":obj.get_text(),"box":[float(z) for z in bb.bounds]}
    text_bounds.append(item)
    if bb.x0<0 or bb.y0<0 or bb.x1>1 or bb.y1>1:
        outside.append(item)

fig.savefig(OUT/f"{STEM}.svg")
fig.savefig(OUT/f"{STEM}.pdf")
fig.savefig(OUT/f"{STEM}.png",dpi=DPI)
fig.savefig(OUT/f"{STEM}.tiff",dpi=600,pil_kwargs={"compression":"tiff_lzw"})
fig.savefig(OUT/f"{STEM}_page_width.png",dpi=300)
plt.close(fig)
im=Image.open(OUT/f"{STEM}_page_width.png")
ImageOps.grayscale(im).save(OUT/f"{STEM}_grayscale.png")
svg=ET.parse(OUT/f"{STEM}.svg")
svg_text=len(svg.findall('.//{http://www.w3.org/2000/svg}text'))
report={"type":"conceptual schematic, not a data analysis",
        "size_mm":[WIDTH_MM,HEIGHT_MM],"raster_dpi":DPI,
        "svg_editable_text_elements":svg_text,"outside_canvas_text":outside,
        "all_text_bounds":text_bounds,
        "uncertainty":"not applicable; no uncertainty or empirical curves represented",
        "preservation":"No existing manuscript or figure file modified."}
(OUT/"qa_report_v6.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps({k:v for k,v in report.items() if k!='all_text_bounds'},indent=2))
if outside:
    raise SystemExit("Text outside canvas; inspect QA report")
'''

ENTRY = '''from pathlib import Path
HERE = Path(__file__).resolve().parent
import plot_intro_concept_v6
'''

if __name__ == "__main__":
    main()
