"""
Parameter sweep over cell size and wall thickness for a 40 mm sheet-gyroid cube.

Every geometric quantity below is MEASURED on the generated mesh.
Every thermal / hydraulic / structural quantity is a first-order ESTIMATE used only to
RANK designs against each other (columns prefixed est_). None of them has been
validated by CFD or experiment.
"""
import csv
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np

# trimesh computes centre of mass for zero-volume edge fragments before they are
# discarded; the resulting divide warning is harmless.
warnings.filterwarnings("ignore", message="invalid value encountered in divide")

sys.path.insert(0, str(Path(__file__).parent))
from gyroid import build_mesh, lattice_stats, measure  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"
RES.mkdir(exist_ok=True)

L = 40.0                     # mm, cube edge (task brief: 40 x 40 x 40 mm)
PITCH = 0.3                  # mm, voxel pitch (convergence study: <0.5 % error)
CELLS = [3, 4, 5, 6, 8]      # integer cells across L -> a = 13.3, 10, 8, 6.7, 5 mm
WALLS = [0.8, 0.9, 1.0, 1.2, 1.6, 2.0]  # nominal; as-built is measured (lattice_stats)

# --- Estimate assumptions (air test, 20 C) -----------------------------------------
K_AIR, MU_AIR, RHO_AIR = 0.0257, 1.81e-5, 1.204  # W/mK, Pa s, kg/m3
K_PLA = 0.13                 # W/mK, typical datasheet value for PLA
NU = 4.0                     # assumed constant laminar Nusselt number (ranking only)
U_SUP = 1.0                  # m/s, superficial (frontal) air velocity in test

# --- Feasibility constraints ---------------------------------------------------------
MIN_WALL = 0.8               # mm, MEASURED 1st-percentile wall: >= 2 lines with a 0.4 mm nozzle
MIN_BOTTLENECK = 2.5         # mm, largest sphere that passes a channel: stringing, cleaning, inspection
MIN_CELLS = 4                # cells across: limits edge effects, lattice-like behaviour
PHI_RANGE = (0.15, 0.40)     # solid fraction: handling strength vs. material / blockage

# --- Selection weights (sum = 1) -------------------------------------------------------
WEIGHTS = {"heat": 0.40, "dp": 0.25, "material": 0.20, "structure": 0.15}


def estimates(m, w):
    Dh = m["hydraulic_diameter_mm"] * 1e-3
    eps = m["porosity"]
    A1 = m["wall_area_one_side_mm2"] * 1e-6
    h = NU * K_AIR / Dh                               # W/m2K, each side
    U = 1.0 / (2.0 / h + (w * 1e-3) / K_PLA)          # fluid-wall-fluid, two networks
    u_int = U_SUP / eps
    Re = RHO_AIR * u_int * Dh / MU_AIR
    dP = 32 * MU_AIR * u_int * (L * 1e-3) / Dh ** 2   # straight-duct laminar, lower bound
    return {
        "est_h_W_m2K": h,
        "est_U_W_m2K": U,
        "est_UA_W_K": U * A1,
        "est_wall_resistance_share": ((w * 1e-3) / K_PLA) * U,
        "est_Re": Re,
        "est_dP_Pa_lower_bound": dP,
        "est_rel_stiffness": m["solid_fraction"] ** 1.5,  # Gibson-Ashby-type scaling
    }


def feasible(r):
    reasons = []
    if r["wall_p1_mm"] < MIN_WALL:
        reasons.append(f"measured wall p1<{MIN_WALL}")
    if r["bottleneck_mm"] < MIN_BOTTLENECK:
        reasons.append(f"bottleneck<{MIN_BOTTLENECK}")
    if r["cells_across"] < MIN_CELLS:
        reasons.append(f"cells<{MIN_CELLS}")
    if not (PHI_RANGE[0] <= r["solid_fraction"] <= PHI_RANGE[1]):
        reasons.append("phi out of range")
    if not (r["watertight"] and r["is_volume"]):
        reasons.append("mesh invalid")
    return reasons


def norm(v, higher_better):
    v = np.asarray(v, float)
    s = (v - v.min()) / (v.max() - v.min()) if v.max() > v.min() else np.ones_like(v)
    return s if higher_better else 1 - s


def score(rows, weights):
    parts = {
        "heat": norm([r["est_UA_W_K"] for r in rows], True),
        "dp": norm([np.log(r["est_dP_Pa_lower_bound"]) for r in rows], False),
        "material": norm([r["pla_mass_g"] for r in rows], False),
        "structure": norm([r["est_rel_stiffness"] for r in rows], True),
    }
    return sum(weights[k] * parts[k] for k in weights)


def pareto(rows):
    """Non-dominated set on (UA up, dP down, mass down)."""
    out = []
    for r in rows:
        dominated = any(
            o["est_UA_W_K"] >= r["est_UA_W_K"] and o["est_dP_Pa_lower_bound"] <= r["est_dP_Pa_lower_bound"]
            and o["pla_mass_g"] <= r["pla_mass_g"] and o is not r
            and (o["est_UA_W_K"] > r["est_UA_W_K"] or o["est_dP_Pa_lower_bound"] < r["est_dP_Pa_lower_bound"]
                 or o["pla_mass_g"] < r["pla_mass_g"])
            for o in rows)
        out.append(not dominated)
    return out


def main():
    rows = []
    for n in CELLS:
        a = L / n
        for w in WALLS:
            t0 = time.time()
            mesh, info = build_mesh(L, a, w, PITCH)
            m = measure(mesh, L, w)
            ls = lattice_stats(a, w)
            r = {"design": f"a{a:.2f}_w{w:.1f}", "cells_across": n, "cell_mm": round(a, 3),
                 "wall_mm": w, **info, **m, **ls, **estimates(m, ls["wall_median_mm"])}
            rows.append(r)
            print(f"{r['design']:>12}  phi={m['solid_fraction']:.3f}  wall p1={ls['wall_p1_mm']:.3f}  "
                  f"bottleneck={ls['bottleneck_mm']:.2f}  Dh={m['hydraulic_diameter_mm']:.2f}  "
                  f"mass={m['pla_mass_g']:.1f} g  wt={m['watertight']}  "
                  f"({time.time() - t0:.1f}s)", flush=True)

    for r in rows:
        r["infeasible_reasons"] = ";".join(feasible(r))
        r["feasible"] = r["infeasible_reasons"] == ""
    feas = [r for r in rows if r["feasible"]]
    for r, s in zip(feas, score(feas, WEIGHTS)):
        r["score"] = float(s)
    for r, p in zip(feas, pareto(feas)):
        r["pareto"] = bool(p)
    feas.sort(key=lambda r: -r["score"])

    # Weight sensitivity: does the winner survive reasonable changes of priorities?
    weight_sets = {
        "baseline": WEIGHTS,
        "heat_first": {"heat": 0.55, "dp": 0.20, "material": 0.15, "structure": 0.10},
        "low_dp": {"heat": 0.30, "dp": 0.40, "material": 0.15, "structure": 0.15},
        "light": {"heat": 0.30, "dp": 0.20, "material": 0.35, "structure": 0.15},
        "strong": {"heat": 0.30, "dp": 0.20, "material": 0.15, "structure": 0.35},
        "equal": {"heat": 0.25, "dp": 0.25, "material": 0.25, "structure": 0.25},
    }
    sens = []
    ranks = np.zeros((len(weight_sets), len(feas)))
    for i, (name, ws) in enumerate(weight_sets.items()):
        s = score(feas, ws)
        order = np.argsort(-s)
        ranks[i, order] = np.arange(1, len(feas) + 1)
        sens.append({"weights": name, **ws,
                     "winner": feas[order[0]]["design"], "runner_up": feas[order[1]]["design"]})

    # Final selection rule: best MEAN rank over all weight sets (robust to the
    # subjective weights); ties broken by worst-case rank, then baseline score.
    for j, r in enumerate(feas):
        r["mean_rank"] = float(ranks[:, j].mean())
        r["worst_rank"] = int(ranks[:, j].max())
    selected = min(feas, key=lambda r: (r["mean_rank"], r["worst_rank"], -r["score"]))

    keys = list(rows[0].keys()) + ["score", "pareto", "mean_rank", "worst_rank"]
    with open(RES / "sweep_results.csv", "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        wr.writeheader()
        for r in sorted(rows, key=lambda r: (r["cells_across"], r["wall_mm"])):
            wr.writerow(r)
    with open(RES / "weight_sensitivity.csv", "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(sens[0].keys()))
        wr.writeheader()
        wr.writerows(sens)
    (RES / "selection.json").write_text(json.dumps({
        "constraints": {"min_measured_wall_p1_mm": MIN_WALL, "min_bottleneck_mm": MIN_BOTTLENECK,
                        "min_cells": MIN_CELLS, "solid_fraction_range": PHI_RANGE},
        "weights": WEIGHTS,
        "selection_rule": "best mean rank across all weight sets; ties -> worst-case rank, then baseline score",
        "selected": {"design": selected["design"], "cell_mm": selected["cell_mm"],
                     "cells_across": selected["cells_across"], "wall_mm": selected["wall_mm"]},
        "ranking": [{k: r[k] for k in ["design", "score", "mean_rank", "worst_rank", "pareto", "solid_fraction",
                                       "wall_p1_mm", "wall_median_mm", "bottleneck_mm",
                                       "hydraulic_diameter_mm", "wetted_area_mm2", "pla_mass_g",
                                       "est_UA_W_K", "est_dP_Pa_lower_bound"]} for r in feas],
        "sensitivity": sens,
    }, indent=2))
    plot(rows)
    print("\nFeasible ranking:")
    for r in feas:
        print(f"  {r['design']:>12} score={r['score']:.3f} mean_rank={r['mean_rank']:.2f} "
              f"worst={r['worst_rank']} pareto={r['pareto']}")
    print("\nSensitivity:")
    for s in sens:
        print(f"  {s['weights']:>10}: winner {s['winner']}, runner-up {s['runner_up']}")
    print(f"\nSELECTED: {selected['design']}")


def plot(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(1, 2, figsize=(12, 4.8))
    for r in rows:
        c = "tab:blue" if r["feasible"] else "lightgray"
        ax[0].scatter(r["est_dP_Pa_lower_bound"], r["est_UA_W_K"], s=20 + 400 * r["solid_fraction"],
                      c=c, edgecolors="k", linewidths=0.4)
        ax[0].annotate(r["design"], (r["est_dP_Pa_lower_bound"], r["est_UA_W_K"]), fontsize=6)
        ax[1].scatter(r["bottleneck_mm"], r["wall_p1_mm"], c=c, edgecolors="k", linewidths=0.4)
        ax[1].annotate(r["design"], (r["bottleneck_mm"], r["wall_p1_mm"]), fontsize=6)
    ax[0].set_xscale("log")
    ax[0].set_xlabel("Estimated pressure drop, laminar lower bound [Pa] @ 1 m/s")
    ax[0].set_ylabel("Estimated wall conductance UA [W/K]")
    ax[0].set_title("Estimated trade-off (marker size ~ solid fraction)")
    ax[1].axvline(MIN_BOTTLENECK, ls="--", c="r", lw=0.8)
    ax[1].axhline(MIN_WALL, ls="--", c="r", lw=0.8)
    ax[1].set_yscale("log")
    ax[1].set_xlabel("Measured channel bottleneck (largest passing sphere) [mm]")
    ax[1].set_ylabel("Measured as-built wall, 1st percentile [mm]")
    ax[1].set_title("Printability constraints (grey = infeasible)")
    fig.tight_layout()
    fig.savefig(RES / "sweep_tradeoff.png", dpi=150)


if __name__ == "__main__":
    main()
