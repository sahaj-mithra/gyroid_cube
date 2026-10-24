# Gyroid Heat-Exchange Structure — Design Report

ME3305 Manufacturing Technology II · Task 4: Generative-AI gyroid heat-exchange structure
**Revision 2 (refined design), 2026-10-25.** It supersedes revision 1 (6.67 mm cell / 0.8 mm wall); see §9.

## 1. Summary

A parametric sheet-gyroid generator was written in Python. It swept **30 designs** (5 cell sizes × 6 nominal wall thicknesses) in a 40 × 40 × 40 mm cube and filtered them with **measured** printability rules:
- as-built wall thickness;
- the channel bottleneck, i.e. the largest sphere that can pass through.

The feasible designs were then ranked on heat-transfer potential, pressure drop, material and stiffness.

**Selected design:** sheet gyroid with an **8 mm cell (5 cells across 40 mm)** and a **0.9 mm nominal wall** (as built: 1st percentile 0.85 mm, median 0.87 mm), **solid fraction 32.6 %**. The print-ready version adds **1.25 mm side walls**.

| Deliverable | File |
|---|---|
| **Recommended print:** lattice + 1.25 mm side walls on the x/y faces, open in flow direction z | `stl/gyroid_final_test_article.stl` |
| Final lattice only (geometry for the design comparison) | `stl/gyroid_final_core.stl` |
| Reference design for A/B testing (10 mm cell, 1.0 mm wall) | `stl/gyroid_reference_a10_w1.0.stl` |
| Print-readiness audit | `FINAL_PRINT_READINESS_AUDIT.md` |

> **How to read the numbers.** **[M] = measured** on the exported mesh or the design field (geometry only).
> **[E] = estimated** with first-order correlations, used **only to rank designs**.
> No thermal or hydraulic value here has been checked by CFD or experiment, no slicer toolpath check has been run, and no strength test has been done.

## 2. Geometry method

- **Level set:** g = sin X cos Y + sin Y cos Z + sin Z cos X, with X = 2πx/a.
- **Sheet gyroid:** the solid is every point within w/2 of g = 0, using the approximate signed distance g/|∇g|.
  - This gives **two separate, interlocked channel networks** with one uniform-thickness wall between them.
  - **w is a nominal value.** The first-order distance makes the as-built wall thinner: median 1.5 % thinner for the 10 mm cell, 4 % for 8 mm, 5 % for 6.67 mm. The audit measured the revision-1 design at w = 0.8 mm → median 0.76 mm. All printability rules therefore use the *measured* thickness (§3.2).
- **Meshing:** the field is intersected with the cube's distance field and meshed with marching cubes, so the cut faces lie exactly on the cube planes and the mesh is closed.
  - Grid nodes that fall exactly on the surface are shifted by 1e-3 × pitch.
  - The 1.25 mm skin is deliberately not a multiple of the 0.2 mm pitch. In revision 1, 1.2 mm put the skin plane on grid nodes and produced zero-area faces.
- **Mesh resolution** (`results/convergence.json`): 0.3 mm pitch for the sweep (≤ 0.5 % volume/area error) and 0.2 mm for the final parts (≈ 0.2 %).
- **Decimation:** final meshes were reduced to 600,000 triangles. A result is accepted only if it is watertight and single-body, changes volume and area by < 0.5 %, and passes the defect checks in §5. Accepted values:

| Part | ΔV | ΔA |
|---|---|---|
| Core | −0.05 % | +0.38 % |
| Test article | −0.03 % | +0.31 % |
| Reference | −0.06 % | +0.18 % |

## 3. Parameter choices and justification

### 3.1 Overall dimensions: 40 × 40 × 40 mm
- It is the size the task brief specifies.
- Five whole 8 mm cells fit across it.
- It prints in a few hours and uses about 32 g of PLA.

### 3.2 Sweep and constraints
- **Cell size a:** an integer number of cells across 40 mm, n = 3, 4, 5, 6, 8 (a = 13.3, 10, 8, 6.67, 5 mm), so every face shows identical geometry.
- **Nominal wall w:** 0.8, 0.9, 1.0, 1.2, 1.6, 2.0 mm.
- **Measured for each design** (`src/gyroid.py: lattice_stats`), on one periodic cell of the design field at 0.04–0.067 mm resolution:
  - the local wall-thickness distribution (2 × distance to surface at medial-axis voxels);
  - the **channel bottleneck** (largest sphere that percolates through a channel network).
- **Field accuracy:** the exported meshes follow this field to within ±0.014–0.019 mm, away from the skin junction.

| Constraint | Limit | Reason |
|---|---|---|
| **Measured** wall thickness, 1st percentile | ≥ 0.8 mm | Two lines with a 0.4 mm nozzle. Uses the as-built wall, not the nominal one. |
| **Channel bottleneck** | ≥ 2.5 mm | Clearance for FDM stringing and blobs, cleaning and inspection. Replaces revision 1's hydraulic-diameter rule, which over-stated the real opening (Dh 2.96 mm vs bottleneck 2.13 mm). |
| Cells across | ≥ 4 | Limits edge effects so the lattice behaves periodically. |
| Solid fraction (core) | 0.15 – 0.40 | Handling strength vs. material use and flow blockage. |
| Mesh | watertight, single body | Required for slicing. |

**Result:** 5 of 30 designs are feasible (`results/sweep_results.csv`, column `infeasible_reasons`). Why the rest fail:
- **Every 0.8 mm nominal wall** fails the measured-wall rule (1st percentile 0.73–0.78 mm).
- **Every 5 mm and 6.67 mm cell** fails the bottleneck rule (≤ 2.11 mm).
- **8 mm cells with walls ≥ 1.2 mm** fail the bottleneck rule.
- **Every 13.3 mm cell** fails the 4-cells rule.
- **10 mm cells with walls ≥ 1.6 mm** exceed 40 % solid.

### 3.3 Ranking criteria (all [E], ranking only)

**Test condition:** air at 20 °C, 1 m/s frontal velocity.

| Criterion | Index | Assumption |
|---|---|---|
| Heat-transfer potential | UA = U·A_wall, with 1/U = 2/h + t/k_PLA and h = Nu·k_air/Dh | Nu = 4 (constant, laminar); k_PLA = 0.13 W/m·K; t = measured median wall |
| Pressure drop | ΔP = 32 μ u L / Dh² | Straight-duct laminar **lower bound**. The real gyroid ΔP is higher. |
| Material | PLA mass | Measured volume × 1.24 g/cm³ |
| Structure | φ^1.5 | Gibson–Ashby-type scaling; exponent assumed |

**Scoring:**
1. Indices are min–max normalised over the feasible set.
2. Baseline weights: heat 0.40, ΔP 0.25, material 0.20, structure 0.15.
3. **Selection rule:** best mean rank across six weight sets (`results/weight_sensitivity.csv`), so the choice does not hinge on one subjective weighting.

| Design | φ | Wall 1st pct [M] | Bottleneck [M] | Area [M] | Baseline score | Mean rank | Wins |
|---|---|---|---|---|---|---|---|
| **a = 8, w = 0.9** | 0.324 | 0.850 mm | 2.58 mm | 47,600 mm² | **0.588** | **1.67** | baseline, heat-first, equal |
| a = 8, w = 1.0 | 0.356 | 0.926 mm | 2.54 mm | 47,100 mm² | 0.550 | 2.50 | strong |
| a = 10, w = 0.9 | 0.265 | 0.866 mm | 3.46 mm | 38,700 mm² | 0.450 | 2.67 | low-ΔP, light |
| a = 10, w = 1.0 | 0.292 | 0.964 mm | 3.35 mm | 38,400 mm² | 0.410 | 3.50 | — |
| a = 10, w = 1.2 | 0.344 | 1.131 mm | 3.17 mm | 37,800 mm² | 0.337 | 4.67 | — |

(Sweep values at 0.3 mm pitch. All five designs are Pareto-optimal on UA ↑, ΔP ↓, mass ↓.)

### 3.4 Why the selected parameters
- **Cell 8 mm:** the smallest cell that still passes the 2.5 mm bottleneck rule with a printable wall. Smaller cells give more wall area, but 6.67 mm cells leave a bottleneck of only 2.03 mm at w = 0.9.
- **Wall 0.9 mm nominal:** the thinnest nominal wall whose *as-built* thickness stays ≥ 0.8 mm (1st percentile 0.850 mm). Thinner walls win on area, mass and PLA conduction resistance (≈ 9 % of the total at this thickness [E]).
- **Solid fraction 32.6 % [M]** (core): a consequence of the two choices above.
- **Side walls 1.25 mm** (test article only):
  - They duct the test flow through the lattice.
  - They give one continuous first layer and a frame to hold and scrape.
  - They remove the thin wall tips at the cut side faces.
- **Closest alternatives:** 8 mm / 1.0 mm (stiffer, more margin on wall thickness) and 10 mm / 0.9 mm (lower ΔP and mass, bottleneck 3.46 mm).

## 4. Measured geometry of the exported STLs [M]

Re-measured from the files on disk (`results/final_metrics.json`, `FINAL_PRINT_READINESS_AUDIT.md`).

| Property | Test article (recommended) | Final core | Reference (a10, w1.0) |
|---|---|---|---|
| Bounding box | 40.000 × 40.000 × 40.002 mm | 40.027 × 40.032 × 40.058 mm | 40.004 × 40.003 × 40.002 mm |
| Wall on mesh, interior: 1st pct / min / median | 0.849 / 0.831 / 0.866 mm | 0.849 / 0.800 / 0.866 mm | 0.964 / 0.927 / 0.985 mm |
| Channel bottleneck | 2.58 mm | 2.58 mm | 3.35 mm |
| Hydraulic diameter | 3.35 mm | 3.63 mm | 4.72 mm |
| Solid volume | 26,072 mm³ | 20,846 mm³ | 18,766 mm³ |
| Solid fraction / porosity | 0.407 ¹ / 0.593 | 0.326 / 0.674 | 0.293 / 0.707 |
| Wetted area (both networks) | 45,300 mm² | 47,600 mm² | 38,310 mm² |
| Specific surface | 708 m²/m³ | 744 m²/m³ | 599 m²/m³ |
| Estimated PLA mass (1.24 g/cm³) | **32.3 g** | 25.9 g | 23.3 g |
| Down-facing area steeper than 45° / 70° | 10.6 % / 1.65 % | 11.6 % / 1.77 % | 11.7 % / 1.66 % |
| Bed contact area | 427 mm² | 314 mm² | 306 mm² |
| Triangles / file size | 600,000 / 30 MB | 600,000 / 30 MB | 600,000 / 30 MB |

¹ Includes the side walls, which push φ above the 0.40 limit applied to the lattice core.

### Final core vs reference

**Measured:**
- **+24 %** wetted area
- **+11 %** mass
- **+12 %** area per gram
- **−23 %** hydraulic diameter
- **−23 %** bottleneck

**Estimated only, not verified:**
- UA: 0.31 vs 0.19 W/K (≈ 1.6×)
- Laminar lower-bound ΔP at 1 m/s: 2.6 vs 1.5 Pa (≈ 1.8×)
- Re ≈ 360 (laminar)

The refined design is expected to transfer more heat at the cost of a higher pressure drop. **Neither effect is demonstrated** until it is simulated or measured.

## 5. Mesh-quality acceptance

`src/mesh_checks.py` adds the following checks:
- zero-area faces;
- open and non-manifold edges;
- edge–triangle self-intersections (validated on overlapping boxes, which give hits, and a clean sphere, which gives none);
- a wall-thickness probe that runs on the *exported mesh*.

`src/build_final.py` exports a mesh only if every check passes, and repeats the checks after reloading the written file. `src/verify_outputs.py` additionally requires a mesh-measured 1st-percentile wall ≥ 0.8 mm and a bottleneck ≥ 2.5 mm.

**Result for all three STLs:**
- watertight, one body;
- 0 open or non-manifold edges;
- 0 self-intersections;
- 0 zero-area faces;
- 0 duplicate faces.

## 6. Print-readiness audit (summary of `FINAL_PRINT_READINESS_AUDIT.md`)

**Decision:** `stl/gyroid_final_test_article.stl` is **ready with minor cautions**. The bare core is printable but not recommended.

**Measured in the audit** (own layer-by-layer slicing model at 0.2 mm layers; **not a real slicer**):
- **Walls:** in-plane wall width 1st percentile 0.802 mm; 0.41 % of the centreline is below 0.80 mm.
- **Islands:** one island per layer, no unsupported islands.
- **First layer:** one continuous 516 mm² island.
- **Overhangs:** at most 0.58 mm shift per layer at the near-flat saddle ceilings.
- **Edges:** only 0.03 % of the near-face wall centreline is under 0.4 mm.
- **Core, for comparison:**
  - 20 first-layer islands;
  - 8.2 % of the near-face centreline under 0.4 mm;
  - thinnest point 0.64 mm, at the corners.

**Cautions** (why not simply "ready"):
1. **No real slicer was available.** Two-line walls are *expected* from variable-width (Arachne) slicers. About 15 % of the centreline is narrower than the ~0.86 mm a classic 0.45 mm two-perimeter setup needs. Check the slicer preview before printing.
2. **Structural adequacy for printing, plate removal and handling is unverified** (no physical tests). The likely weak points are layer bonds and the exposed wall edges on the open z faces.
3. **The bottleneck margin is small:** 2.58 mm against the 2.5 mm rule.

**Recommended settings** (full table in the audit):
- Arachne walls, 0.40–0.42 mm line width;
- 0.2 mm layers, 2 walls;
- no supports, 5 mm brim, 100 % fan;
- "avoid crossing walls" on.

## 7. Assignment compliance

| Requirement | Status |
|---|---|
| 40 × 40 × 40 mm | Met [M] |
| Gyroid-based compact structure | Met [M] |
| Maximize surface area | Within constraints: +24 % over the reference [M]. 16 % below revision 1, the price of the wall and channel fixes. |
| Control material usage | Met within constraints: 32.6 % solid core, 32.3 g test article [M volume, E mass] |
| Heat/mass-transfer vs pressure-drop trade-off | Ranking-level estimates only [E]. No optimization is demonstrated. |
| "Using Generative AI" | **Not met in the strict sense.** The design comes from an automated, criteria-driven parametric search with a robust ranking rule, not a generative or ML model. Extension: train a surrogate on the 30 sweep designs (plus CFD) and optimize graded cells or walls with Bayesian optimization or NSGA-II. |
| Printable | Ready with minor cautions (§6) |
| Experimentally testable | Partly: the side walls duct flow through the lattice, but no inlet/outlet manifolds, seals or sensor ports are designed yet. |

## 8. Limitations
- **Thermal and hydraulic indices are for ranking only.** Constant Nu ignores entrance effects and gyroid mixing; the ΔP formula ignores tortuosity and form drag.
- **The structural index is a scaling law with an assumed exponent.** No FEA or physical test was done.
- **The thickness and bottleneck values come from the design field**, which the mesh follows within ±0.02 mm. The mesh probe can over-read by up to ~0.02 mm, smaller than the 0.05 mm margin above the 0.8 mm rule.
- **The sweep is discrete**, and the selection depends on the chosen criteria (mitigated by the mean-rank rule).
- **Single-fluid test only:** in the test article both channel networks run in parallel along z.
- **No slicer toolpath, print trial or handling test has been performed.**

## 9. Revision history

| | Revision 1 (superseded, 2026-10-24) | Revision 2 (this report) |
|---|---|---|
| Design | 6.67 mm cell, 0.8 mm nominal wall, 1.2 mm skin | 8 mm cell, 0.9 mm nominal wall, 1.25 mm skin |
| Sweep | 25 designs | 30 designs (added 0.9 mm walls) |
| Wall rule | Nominal w ≥ 0.8 mm | **Measured** 1st-percentile wall ≥ 0.8 mm |
| Channel rule | Hydraulic diameter ≥ 2.5 mm | **Bottleneck sphere** ≥ 2.5 mm |
| Mesh acceptance | Watertight, single body | + zero-area faces, open/non-manifold edges, self-intersections, mesh-measured wall |

**Audit findings that led to revision 2** (measured on the revision-1 files):
- The 0.8 mm nominal walls were 0.73–0.80 mm as built (median 0.76 mm).
- The true channel bottleneck was 2.13 mm.
- The test article had 8,140 zero-area faces and 2 self-intersections at the skin junction.

The revision-1 STLs were overwritten by the regeneration and no longer exist.

## 10. Reproducing the results
From the project folder, PowerShell:

```
python -m venv .venv
.venv\Scripts\python -m pip install --only-binary=:all: -r requirements.txt
.venv\Scripts\python src\convergence.py      # ~1.5 min
.venv\Scripts\python src\sweep.py            # ~10 min, writes results/
.venv\Scripts\python src\build_final.py      # ~10 min, writes stl/ + final_metrics.json
.venv\Scripts\python src\render_sections.py
.venv\Scripts\python src\verify_outputs.py   # ~5 min, checks every deliverable
```

**Environment note:** a first install attempt without `--only-binary` hung with no output (cause not isolated). With prebuilt wheels it finished in about 50 s on Python 3.14.3.
