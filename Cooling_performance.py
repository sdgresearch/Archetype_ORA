"""

Usage (from the project root)::

    python scripts/generate_figure5_cooling_performance_R400m.py
    python scripts/generate_figure5_cooling_performance_R400m.py --recalculate

The default uses the already fitted, official-postcode 400-m network analysis.
``--recalculate`` independently recomputes the 400-m network integral, the
within-archetype PC associations, and the two-part green-service models from
the frozen cooling surface. Neither mode changes the accepted 800-m Figure 5.

For postcode i and positively cooled 100-m cell j, with pedestrian-network
distance d_ij (including the cooling-cell connector), the metric is

    ACV_i(400) = sum_{d_ij <= 400} C_j A_j exp[-ln(5) (d_ij/400)^2]
    ACI_i(400) = ACV_i(400) / [pi * 400^2 * 0.8 / (ln(5) * 10000)]

ACV has units degrees C hectare; ACI has units degrees C equivalent. The
postcode-to-network connector is excluded, matching the accepted analysis.
Green provision in panels e/f remains the 400-m mean for 2016--2024.
All figure associations are postcode-level; this is modelled potential access,
not observed visits or personal cooling. See network metric contract for detail.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyse_network_integrated_accessible_cooling as network
import analyse_nonlinear_green_accessible_cooling as nonlinear
import plot_network_integrated_accessible_cooling_figure2 as renderer
import plot_residential_green_cooling_paper_figures as maps
import run_official_residential_cooling_pipeline as official

matplotlib.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 6,
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
})


ROOT = Path(__file__).resolve().parents[1]
BASE = official.BASE
COOLING = official.COOLING
ESTABLISHED = COOLING / "accessible_cooling_integral_trial"
RADIUS = 400
N_POSTCODES = 94_076
GREEN = "green_share_400m_mean_2016_2024"
METRIC = "accessible_cooling_index_400m_c"
VOLUME = "accessible_cooling_volume_400m_c_ha"
# Keep the versioned branch shallow enough for standard Windows path handling.
OUTPUT = ROOT / "manuscript" / "Figure5_R400m_20260924"
ACCEPTED = (
    ROOT / "manuscript" / "Urban_Exposome_Cooling_Equity_Singapore_20260907"
    / "Urban_Exposome_Cooling_Equity_Overleaf_v12_OfficialPostcodes"
    / "figures" / "Figure5_cooling_performance.png"
)
REQUIRED_NONLINEAR = (
    "archetype_green_response_heterogeneity_tests.csv",
    "archetype_green_service_empirical_bins.csv",
    "archetype_nonlinear_green_service_predictions.csv",
    "archetype_nonlinearity_tests.csv",
    "nonlinear_green_service_qa.json",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stage_established_400m(target: Path) -> dict[str, str]:
    """Copy only the genuine 400-m inputs so plotting cannot alter sources."""
    target.mkdir(parents=True, exist_ok=True)
    nonlinear_target = target / "nonlinear_green_service"
    nonlinear_target.mkdir(exist_ok=True)
    copied: dict[str, str] = {}
    for name in (
        "postcode_network_integrated_accessible_cooling.csv",
        "all_12_pc_accessible_cooling_integral_associations.csv",
        "network_integrated_accessible_cooling_qa.json",
    ):
        source = ESTABLISHED / name
        if not source.is_file():
            raise FileNotFoundError(source)
        shutil.copyfile(source, target / name)
        copied[name] = sha256(source)
    for name in REQUIRED_NONLINEAR:
        source = ESTABLISHED / "panelE400_volume" / name
        if not source.is_file():
            raise FileNotFoundError(source)
        shutil.copyfile(source, nonlinear_target / name)
        copied[f"nonlinear_green_service/{name}"] = sha256(source)
    return copied


def recalculate_400m(target: Path) -> None:
    """Refit the 400-m estimands into this versioned output branch only."""
    target.mkdir(parents=True, exist_ok=True)
    official.configure_network(network)
    network.OUT = target
    network.RADII_M = (RADIUS,)
    network.PRIMARY_RADIUS_M = RADIUS
    network.main()

    nonlinear.BASE = BASE
    nonlinear.COOLING = COOLING
    nonlinear.TRIAL = target
    nonlinear.SERVICE = COOLING / "postcode_cooling_production_and_service.csv"
    nonlinear.METRIC_FILE = target / "postcode_network_integrated_accessible_cooling.csv"
    nonlinear.OUT = target / "nonlinear_green_service"
    nonlinear.METRIC = VOLUME
    nonlinear.GREEN = GREEN
    nonlinear.ACCESS_RADIUS_M = RADIUS
    nonlinear.GREEN_RADIUS_M = RADIUS
    nonlinear.MAGNITUDE_ESTIMAND = (
        "Mean distance-weighted accessible cooling volume among served postcodes"
    )
    nonlinear.MAGNITUDE_UNIT = "degrees C hectare"
    nonlinear.EXPECTED_N = N_POSTCODES
    nonlinear.EXPECTED_SERVED_N = None
    nonlinear.main()


def validate_400m(target: Path) -> dict:
    """Guard against an 800-m field being relabelled as a 400-m result."""
    qa = json.loads((target / "network_integrated_accessible_cooling_qa.json").read_text())
    if not qa.get("pass") or qa.get("primary_radius_m") != RADIUS:
        raise ValueError("Network QA does not verify a 400-m calculation")
    data = pd.read_csv(
        target / "postcode_network_integrated_accessible_cooling.csv",
        dtype={"postal_code": "string"},
        usecols=["postal_code", METRIC, VOLUME, "has_reachable_cooling_400m"],
        low_memory=False,
    )
    if len(data) != N_POSTCODES or data.postal_code.nunique() != N_POSTCODES:
        raise ValueError("The 400-m data do not cover the full official postcode cohort")
    area_ha = math.pi * RADIUS**2 * 0.8 / (math.log(5) * 10_000)
    aci = data[METRIC].to_numpy(float)
    acv = data[VOLUME].to_numpy(float)
    if not (np.isfinite(aci).all() and np.isfinite(acv).all()
            and np.all(aci >= 0) and np.all(acv >= 0)):
        raise ValueError("400-m accessible-cooling values are invalid")
    np.testing.assert_allclose(aci, acv / area_ha, atol=1e-12, rtol=1e-10)
    served = data["has_reachable_cooling_400m"].astype(str).str.lower().isin(("true", "1"))
    if not np.array_equal(served.to_numpy(), aci > 0):
        raise ValueError("400-m reachability flags disagree with accessible cooling")
    effects = pd.read_csv(target / "all_12_pc_accessible_cooling_integral_associations.csv")
    if len(effects) != 96 or effects.component_id.nunique() != 12:
        raise ValueError("The 400-m PC-association table is incomplete")
    model_qa = json.loads((target / "nonlinear_green_service" / "nonlinear_green_service_qa.json").read_text()) if (target / "nonlinear_green_service" / "nonlinear_green_service_qa.json").exists() else None
    if model_qa is not None and (not model_qa.get("pass") or model_qa.get("n_postcodes") != N_POSTCODES):
        raise ValueError("The 400-m nonlinear model QA failed")
    return {
        "radius_m": RADIUS,
        "reference_weighted_area_ha": area_ha,
        "n_postcodes": len(data),
        "n_served_postcodes": int(served.sum()),
        "served_postcodes_percent": 100 * float(served.mean()),
        "metric": METRIC,
        "nonlinear_positive_outcome": VOLUME,
        "green_predictor": GREEN,
        "network_qa_pass": True,
        "nonlinear_qa_pass": None if model_qa is None else model_qa["pass"],
    }


def draw_figure(target: Path, out: Path) -> None:
    """Keep Figure 5 styling and efficacy panels; use 400 m in b/d/e/f."""
    figure_dir = out / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    renderer.ANALYSIS = COOLING
    renderer.TRIAL = target
    renderer.NONLINEAR = target / "nonlinear_green_service"
    renderer.OUT = figure_dir
    renderer.SOURCE = out / "source_data"
    renderer.SOURCE.mkdir(parents=True, exist_ok=True)
    renderer.STEM = "Figure5_cooling_performance_R400m"
    renderer.QA_FILENAME = renderer.STEM + "_QA.json"
    renderer.CREATE_COMPARISON_MONTAGE = False
    renderer.MINIMAP_ARCHETYPE_MEAN_COLOR = False
    renderer.SHOW_FIGURE_TITLE = False
    renderer.SHOW_NAVIGATIONAL_HEADINGS = False
    renderer.SIMPLE_PANEL_LABELS = True
    renderer.METRIC = METRIC
    renderer.ACCESS_RADIUS_M = RADIUS
    renderer.PANEL_E_ACCESS_RADIUS_M = RADIUS
    renderer.GREEN_RADIUS_M = RADIUS
    renderer.REACHABILITY_YLIM = (0, 72)
    renderer.REACHABILITY_YTICKS = [0, 20, 40, 60]
    renderer.PANEL_E_MAGNITUDE_TITLE = "Accessible cooling volume within 400 m, where reachable"
    renderer.PANEL_E_MAGNITUDE_LABEL = "Accessible cooling volume (°C·ha)"
    renderer.PANEL_E_MAGNITUDE_YLIM = (0, 2.5)
    renderer.PANEL_E_MAGNITUDE_YTICKS = [0, 0.5, 1.0, 1.5, 2.0, 2.5]
    renderer.PANEL_D_PLAIN_CROP_ROWS = {
        (archetype, pc)
        for archetype in range(1, 5)
        for pc in renderer.DOMAIN_REPRESENTATIVES
    }
    renderer.EXPECTED_POSTCODES = N_POSTCODES

    def export_400m(fig: plt.Figure) -> None:
        fig.set_size_inches(7.2047, 7.85)
        stem = figure_dir / renderer.STEM
        fig.savefig(stem.with_suffix(".svg"), bbox_inches="tight")
        fig.savefig(stem.with_suffix(".pdf"), bbox_inches="tight")
        fig.savefig(stem.with_suffix(".png"), dpi=600, bbox_inches="tight")
        fig.savefig(stem.with_suffix(".tiff"), dpi=600, bbox_inches="tight",
                    pil_kwargs={"compression": "tiff_lzw"})
        plt.close(fig)

    renderer.export = export_400m
    maps.BASE = BASE
    maps.ANALYSIS = COOLING
    maps.OUT = figure_dir
    maps.SOURCE = renderer.SOURCE
    renderer.main()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recalculate", action="store_true",
                        help="Recompute 400-m network cooling and refit the associated models")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT,
                        help="Separate output folder; the accepted 800-m figure is never changed")
    args = parser.parse_args()
    out = args.output_dir.resolve()
    accepted_before = sha256(ACCEPTED)
    target = out / "inputs_400m"
    source_hashes = {}
    if args.recalculate:
        recalculate_400m(target)
    else:
        source_hashes = stage_established_400m(target)
    checks = validate_400m(target)
    draw_figure(target, out)
    figure_qa = json.loads((out / "figures" / "Figure5_cooling_performance_R400m_QA.json").read_text())
    if not figure_qa.get("pass"):
        raise RuntimeError("Figure 5 400-m render failed its source-data checks")
    accepted_unchanged = sha256(ACCEPTED) == accepted_before
    if not accepted_unchanged:
        raise RuntimeError("The accepted 800-m Figure 5 changed during rendering")
    report = {**checks, "recalculated": args.recalculate,
              "input_sha256": source_hashes,
              "accepted_800m_figure_unchanged": accepted_unchanged,
              "figure_qa_pass": True}
    (out / "Figure5_R400m_contract_and_QA.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2), flush=True)
    print(f"400-m figure: {out / 'figures' / 'Figure5_cooling_performance_R400m.pdf'}", flush=True)


if __name__ == "__main__":
    main()
