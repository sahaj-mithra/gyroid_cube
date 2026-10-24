# Final Print-Readiness Audit — Gyroid Heat-Exchange Prototype

**Date:** 2026-10-25  **Scope:** FDM prototype in PLA, 0.4 mm nozzle (non-functional prototype; reliable printing and basic integrity take priority over thermal performance)
**Assignment:** *"Generate a gyroid-based compact structure using Generative AI to maximize surface area and heat/mass-transfer capability while controlling pressure drop and material usage. The structure must be printable and experimentally testable. Overall dimensions: 40 × 40 × 40 mm."*

## Decision

| File | Classification |
|---|---|
| **`stl/gyroid_final_test_article.stl`** (8 mm cell, 0.9 mm nominal wall, 1.25 mm side walls) | **READY WITH MINOR CAUTIONS** — recommended print |
| `stl/gyroid_final_core.stl` (same lattice, no side walls) | Printable, **not recommended**: fragmented first layer and thin tips at the cut faces (see §3) |
| `stl/gyroid_reference_a10_w1.0.stl` | Comparison part only; not the subject of this decision |

**Recommended STL (exact path):**
`D:\Academics\Semester 5\ME3305 - Manufacturing Technology II\Project\stl\gyroid_final_test_article.stl`
SHA-256 `560ca6e0efe887a6615152e20e21ce06e3222ce8c6d1b08c5b1a2adbe8d998e4` (30.0 MB, 600,000 triangles)

**Why "minor cautions" and not "ready":** every measured geometric and mesh check passes. However, three things remain open:
1. **No slicer toolpath check was performed:** no slicer is installed on this machine.
2. **About 15 % of the wall centreline is narrower than 0.86 mm.** A classic (non-Arachne) slicer needs roughly that width for two full 0.45 mm perimeters.
3. **Structural adequacy is unverified.** No physical test was done.

**Why not "not ready":** none of the measured findings is expected to cause a failed print.
- Every wall is at least 0.80 mm (as measured on the mesh).
- The part is a single body.
- The first layer is one continuous 516 mm² island.
- No layer contains an unsupported island.

## 1. What was and was not done

**Performed in this audit (read-only, on the files listed with their SHA-256 hashes):**
- **Verification suite:** `src/verify_outputs.py` (reads files only).
- **Topology and mesh quality:** duplicate faces, triangle quality, edge use, bounding boxes, surface accuracy against the design equation.
- **Layer-by-layer analysis:** an own scanline slicer at 0.2 mm layers and 0.025 mm pixels, 200 layers per file. Measured per layer: wall-width distribution, islands, first layer, unsupported islands, layer-to-layer overhang offset.
- **Results files reviewed:** `results/final_metrics.json`, `selection.json`, `sweep_results.csv`.

**Method checks** (from the earlier audit, same code):
- The width measurement reads a 0.8 mm plate as 0.791 mm and a 1.2 mm plate as 1.202 mm.
- The 3D thickness probe reads a 0.8 mm plate as 0.806 mm and a 0.9 mm plate as 0.922 mm. It can therefore **over-read by up to ~0.02 mm**.
- The self-intersection test finds 11 hits on overlapping boxes and 0 on a clean sphere.

**Not performed:**
- **No slicer analysis or toolpath preview.** No PrusaSlicer, Cura, OrcaSlicer, Bambu Studio or similar is installed, and installing one was outside this audit's read-only scope. The two-line wall assessment in §3 is an *inference from measured widths and typical slicer behaviour*, not an observed toolpath.
- **No physical print, strength, handling or drop test.**
- **No CFD, thermal or pressure-drop simulation or experiment.**
- **Original (pre-refinement) STLs could not be inspected.** The 6.67 mm / 0.8 mm files were overwritten by the authorized regeneration on 2026-10-24. Comparisons with them use the measurements recorded in the earlier audit of those files.

## 2. Geometry (measured)

| Property | Test article (recommended) | Core | Reference a10/w1.0 |
|---|---|---|---|
| Bounding box | 40.000 × 40.000 × 40.002 mm | 40.027 × 40.032 × 40.058 mm | 40.004 × 40.003 × 40.002 mm |
| Cell size / nominal wall | 8.0 mm (5 cells) / 0.9 mm | 8.0 mm / 0.9 mm | 10 mm / 1.0 mm |
| Wall thickness on mesh, interior: 1st percentile / min / median | **0.849 / 0.831 / 0.866 mm** | 0.849 / 0.800 / 0.866 mm | 0.964 / 0.927 / 0.985 mm |
| Wall thickness on mesh, corner incl. skin junction: 1st percentile / min | 0.854 / 0.831 mm | 0.849 / **0.640 mm** (thin tips at cut faces) | — |
| Side wall (skin), measured median | 1.30 mm (nominal 1.25; probe over-reads up to ~0.02–0.05) | — | — |
| Channel bottleneck (largest sphere that passes) ¹ | **2.58 mm** | 2.58 mm | 3.35 mm |
| Hydraulic diameter | 3.35 mm | 3.63 mm | 4.72 mm |
| Solid fraction / porosity | 0.407 / 0.593 | 0.326 / 0.674 | 0.293 / 0.707 |
| Wetted surface area | 45,300 mm² (708 m²/m³) | 47,600 mm² (744 m²/m³) | 38,310 mm² (599 m²/m³) |
| Solid volume → PLA mass at 1.24 g/cm³ ² | 26,072 mm³ → **32.3 g** | 20,846 mm³ → 25.9 g | 18,766 mm³ → 23.3 g |
| Surface deviation from the design equation | ≤ 0.014 mm away from the skin; ≤ 0.12 mm in the lattice–skin fillet (1.30–1.34 mm from the side faces, intended blend) | p0.1–p99.9: −0.013 / +0.011 mm | −0.009 / +0.008 mm |

¹ Measured on the design equation at 0.04 mm resolution; the mesh matches it to within ±0.014 mm away from the skin.
² Volume is measured; mass is an estimate. Real mass depends on extrusion width and flow.

- **Intended structure:** confirmed. The cross-sections (`results/cross_sections.png`) show a sheet gyroid of uniform-thickness walls separating two interlocked channel networks, with the 1.25 mm frame on the four x/y faces and open z faces.
- **Dimensions:** the test article is exact to ≤ 0.002 mm. The core overshoots by up to 0.058 mm, far below FDM tolerance.

## 3. Mesh integrity (measured, after reloading the STL from disk)

| Check | Test article | Core | Reference |
|---|---|---|---|
| Watertight / winding consistent / valid volume | yes / yes / yes | yes / yes / yes | yes / yes / yes |
| Connected bodies | 1 | 1 | 1 |
| Open edges / non-manifold edges | 0 / 0 | 0 / 0 | 0 / 0 |
| Self-intersections (edge through triangle) | **0** | 0 | 0 |
| Zero-area faces (< 1e-9 mm²) / faces < 1e-6 mm² | 0 / 0 | 0 / 0 | 0 / 0 |
| Duplicate faces | 0 | 0 | 0 |
| Smallest face / worst aspect ratio | 2.4e-5 mm² / 4,695 (a few slivers; not degenerate) | 2.7e-4 mm² / 111 | 1.6e-6 mm² / 722 |
| STL export → reload | passes all of the above | passes | passes |

**Compared with the audited original:** the test article's 8,140 zero-area faces and 2 self-intersections are gone.
- **Cause, verified:** the 1.25 mm skin no longer lands on grid nodes.
- **Cause, verified:** the iso-level nudge was raised to 1e-3 × pitch.
- **Prevention:** the build now rejects any mesh with defects, before export and after reload.

## 4. Printability (layer analysis = own slicing model, not a slicer)

| Measured per-layer result | Test article | Core |
|---|---|---|
| Slicing faults (unclosed outlines) | 0 | 0 |
| In-plane wall width, interior centreline: 1st pct / 5th pct / median / 95th pct | 0.802 / 0.838 / 0.982 / 1.58 mm | 0.802 / 0.838 / 0.971 / 1.55 mm |
| Share of wall centreline < 0.75 / < 0.80 / < 0.86 / < 0.90 mm | 0.16 / 0.41 / 14.9 / 28.2 % | 0.13 / 0.45 / 15.3 / 28.6 % |
| Share of wall centreline < 0.4 mm near the side faces (would be dropped by a slicer) | **0.03 %** | **8.2 %** |
| Islands per layer: median / max | **1 / 1** | 10 / 21 |
| First layer | **1 island, 516 mm² (32 % of footprint)** | 20 islands, 398 mm², 11 under 5 mm², smallest 0.16 mm² |
| Islands with nothing underneath (floating starts) | **0** | 9, each ≤ 0.004 mm² |
| Max layer-to-layer offset (interior) | 0.58 mm | 0.59 mm (2.83 mm right at the bare side faces) |
| Area offset > 0.4 mm from the layer below (one line width, i.e. printed in air) | 134 mm² over 200 layers, ≤ 6.9 mm² per layer | 169 mm², ≤ 8.8 mm² per layer |
| Down-facing area steeper than 45° / steeper than 70° | 10.6 % / 1.65 % | 11.6 % / 1.77 % |

### Wall compatibility with a 0.4 mm nozzle (inference, not a slicer result)

- **Measured widths:** practically all wall centreline is ≥ 0.80 mm wide in-plane, and the 3D wall is ≥ 0.83 mm. Only 0.41 % is below 0.80 mm, and the in-plane 1st percentile is 0.802 mm.
- **Variable-width (Arachne) slicers** (PrusaSlicer ≥ 2.6 default, Cura 5, OrcaSlicer, Bambu Studio): 0.80–0.98 mm walls would normally be split into **two lines of roughly 0.40–0.49 mm**. Continuous two-line walls are expected.
- **Classic fixed-width perimeters** at 0.45 mm need about 0.86 mm for two full lines. About 15 % of the centreline is narrower, where the slicer may overlap the two passes or add gap fill. **Use Arachne, or set the line width to 0.40 mm.**
- **Thin regions:** with the side walls, only 0.03 % of the near-face centreline is below 0.4 mm, so nothing significant will be omitted. On the bare core, 8.2 % would be dropped, leaving ragged edges at the cut faces.
- **Overhangs:** supports are not needed.
  - The most-offset regions are the gyroid's near-flat saddle "ceilings": at most 0.58 mm shift per layer, ≤ 6.9 mm² per layer printed beyond one line width.
  - Expect slight drooping and rough down-facing surfaces there, not failure.
- **Unsupported islands:** none in the test article.

## 5. Structural integrity — engineering assessment, NOT verified strength

No strength or handling test has been done, so **no claim of structural safety is made**. These observations come from measured geometry:

- **During printing:** the part is one continuous body.
  - Each layer is a single island, so there are no isolated thin towers.
  - The first layer is one 516 mm² island tied together by the frame.
  - The thinnest wall anywhere is ≥ 0.83 mm (3D) and 0.80 mm in-plane, i.e. two lines.
  - Wobble or detachment of individual walls is unlikely.
- **Removal from the build plate:** a scraper acts on the 1.25 mm frame and the 516 mm² contact area, not on individual 0.9 mm walls.
  - A 5 mm brim adds adhesion, but it must be peeled carefully; prying at a single lattice wall could crack it.
- **Normal handling:** weak points are inferred, not tested.
  1. **Layer bonds (z direction):** two-line PLA walls are weakest along layer lines. Squeezing the open top and bottom faces stresses them.
  2. **Exposed wall ends** on the open z faces (≈ 0.85 mm edges) could chip if dropped.
  3. **Frame-to-lattice junctions** are filleted; no thinning was measured there (minimum 0.831 mm).
- **Estimate only:** relative-stiffness index φ^1.5 = 0.26 (Gibson–Ashby-type scaling, exponent assumed).
- **Suggested basic checks after printing:** weigh the part (~32 g expected), inspect the walls for gaps against light, then apply a gentle hand squeeze on each axis.

## 6. Assignment compliance

| Requirement | Status | Evidence type |
|---|---|---|
| 40 × 40 × 40 mm | Met: 40.000 × 40.000 × 40.002 mm | Measured |
| Gyroid-based compact structure | Met: sheet gyroid, 5 cells per side | Measured (geometry) |
| Maximize surface area | Partly. 47,600 mm² for the core: +24 % over the 10 mm reference (38,310 mm²) for +11 % mass. This is 16 % less than the superseded 6.67 mm design (56,765 mm²), the price of the wall and channel fixes. Maximized only within the sweep grid and constraints. | Measured |
| Control material usage | Met within constraints: solid fraction 0.326 core / 0.407 with frame; 25.9 / 32.3 g | Volume measured; mass estimated |
| Heat/mass-transfer vs pressure-drop trade-off | **Ranking-level only.** Estimated UA 0.31 vs 0.19 W/K and laminar lower-bound ΔP 2.6 vs 1.5 Pa (core vs reference, 1 m/s air). **No thermal or hydraulic optimization is demonstrated.** | Estimated, unverified |
| "Using Generative AI" | **Not met in the strict sense.** The design comes from an automated, criteria-driven parametric search with a robust ranking rule. No generative or ML model is used. | Code inspection (`src/sweep.py`) |
| Printable | Ready with minor cautions (§4) | Measured geometry + inference; no slicer |
| Experimentally testable | Partly. The frame ducts flow through the lattice along z, but no inlet/outlet manifold, sealing face or sensor ports are designed. | Geometry |

**Documentation gap:** `REPORT.md` still describes the superseded design (6.67 mm cell, 0.8 mm wall, 1.2 mm skin, 25-design sweep, Dh-based clearance rule). The results files and STLs are consistent with each other and with the refined design (8 mm / 0.9 mm / 1.25 mm, 30 designs, measured-thickness and bottleneck rules), but the report is not.

## 7. Remaining issues and proposed fixes (none applied)

| # | Issue | Severity | Evidence | Proposed fix |
|---|---|---|---|---|
| 1 | Two-line walls not confirmed by a real slicer | Medium (unverified) | No slicer installed; 14.9 % of the centreline < 0.86 mm | Slice the recommended STL in an Arachne slicer and check in the preview that the walls show two lines and no gaps before printing |
| 2 | `REPORT.md` out of date | Medium (documentation) | Lines 9, 14, 53, 84, 94–105, 128 describe the old design | Update the report to the refined design and add the audit results (needs your authorization) |
| 3 | "Generative AI" requirement only loosely met | Medium (assignment) | Parametric search, no generative model | Either present the work honestly as automated design exploration, or add a surrogate model trained on the 30 sweep designs with Bayesian or NSGA-II optimization |
| 4 | Thin bottleneck margin: 2.58 mm against the 2.5 mm rule | Low | 0.08 mm margin; stringing could narrow it locally | Use retraction and "avoid crossing walls"; if needed, a 10 mm / 0.9 mm variant gives 3.46 mm |
| 5 | Saddle-ceiling droop | Low | ≤ 0.58 mm/layer offset, ≤ 6.9 mm²/layer beyond one line width | 100 % fan, slower overhangs; no supports |
| 6 | No test fixture (manifolds, seals, sensor ports) | Low for printing, relevant for testing | Open z faces only | Design snap-on or clamped inlet/outlet adapters as separate parts |
| 7 | Bare core not recommended | Info | 20 first-layer islands; 8.2 % of near-face centreline < 0.4 mm; corner minimum 0.64 mm | Print the test article instead |
| 8 | Sliver triangles in the test article (smallest 2.4e-5 mm², aspect up to 4,695) | Info | Not degenerate; no defects | None needed for slicing |

## 8. Recommended slicer settings (PLA, 0.4 mm nozzle)

| Setting | Value |
|---|---|
| File / orientation | `gyroid_final_test_article.stl` as exported: flow axis z vertical, one open face on the bed |
| Wall generator | **Arachne / variable line width** (default in PrusaSlicer ≥ 2.6, Cura 5, OrcaSlicer, Bambu Studio) |
| Line width | 0.40–0.42 mm (perimeters); first layer 0.45–0.50 mm |
| Layer height | 0.2 mm (0.16 mm for better saddle ceilings) |
| Walls / perimeters | 2 (the frame will get 3 automatically) |
| Infill / top & bottom layers | Defaults are fine. Lattice walls are too narrow for infill (two lines fill them); only the frame corners and near-flat saddles may receive small solid-fill patches. |
| Supports | **None** |
| Brim | **5 mm**, outer only |
| Cooling | 100 % fan after layer 2 |
| Speed | Outer wall ≤ 30 mm/s; overhang slow-down on |
| Travel | Retraction tuned; "avoid crossing walls" on |
| Expected result | ≈ 32 g (measured volume × 1.24 g/cm³) |

**In the slicer preview, before printing, check:**
- two lines in the lattice walls at several heights;
- no missing wall segments near the frame;
- channels visibly open through the top and bottom faces;
- a single continuous first layer.

## 9. Audited files (SHA-256, first 16 hex characters)

The STLs, results and code were hashed before the audit and re-checked after it; this document is the only file the audit created.

`stl/gyroid_final_test_article.stl 560ca6e0efe887a6` · `stl/gyroid_final_core.stl f85e1ab54d0c22d5` · `stl/gyroid_reference_a10_w1.0.stl 5b25b236720312bc` · `src/gyroid.py 853c25612eb4dbf8` · `src/mesh_checks.py e4fa79f7c0e07cf3` · `src/sweep.py 1bfdad346a5e56fc` · `src/build_final.py d4357a7b2ee8a282` · `src/verify_outputs.py 4c07d4a3f5231617` · `results/final_metrics.json c360684b3497979c` · `results/selection.json 7f92f168c3f1822b` · `results/sweep_results.csv 9072a2a0f56b5fcb` · `REPORT.md 83efd18c3abf4bdc`
