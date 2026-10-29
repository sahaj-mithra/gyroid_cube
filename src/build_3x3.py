"""
Revision 3: gyroid cube with 3 see-through openings along each of X, Y and Z.

Why a = 26.67 mm (1.5 periods), not 3 periods
---------------------------------------------
Viewed along any cube axis, the sheet gyroid g = sin X cos Y + sin Y cos Z + sin Z cos X
has 4 line-of-sight openings per period^2, on a square grid with spacing a/2 (measured, see
results/3x3/design_study.json). So the number of openings across a face of size L is 2L/a:
  original a = 8 mm      -> 10 x 10 openings per face (each ~1 mm clear),
  3 periods, a = 13.3 mm ->  6 x  6 openings per face,
  a = 2L/3 = 26.67 mm    ->  3 x  3 openings per face  <- this design.
The phase (where the cube faces cut the lattice) decides whether those openings are whole or
cut by the cube edges. Shifting the lattice by a/8 on all three axes gives exactly 9 whole,
uncut openings on every face for all three viewing directions; shifts of 0 or a/4 give 6 whole
+ 6 edge-cut. The cube stays 40 x 40 x 40 mm.

Outputs: stl/gyroid_3x3_40mm.stl, results/3x3/*.json
"""
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import trimesh
from scipy import ndimage as ndi
from skimage.morphology import skeletonize

sys.path.insert(0, str(Path(__file__).parent))
import mesh_checks  # noqa: E402
from gyroid import build_mesh, lattice_stats, measure  # noqa: E402
from mesh_checks import defect_free, defects, sanitize  # noqa: E402
from openings import bottleneck, face_mouths, grid_arrangement, see_through, voxelize_field, voxelize_mesh  # noqa: E402
from printability import layer_analysis  # noqa: E402

warnings.filterwarnings("ignore", category=RuntimeWarning, module="trimesh")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "3x3"
OUT.mkdir(parents=True, exist_ok=True)

L = 40.0                  # mm, unchanged external size
OPENINGS_PER_AXIS = 3
A = 2 * L / OPENINGS_PER_AXIS   # 26.667 mm gyroid period (openings repeat every A/2)
SHIFT = A / 8             # phase that centres a full 3 x 3 grid of openings on every face
W = 1.6                   # mm nominal wall: 4 lines at 0.4 mm (see design study)
PITCH = 0.2               # mm marching-cubes pitch (convergence study: ~0.2 %)
TARGET_FACES = [400_000, 600_000, 900_000]
MAX_DEV = 0.5             # % allowed volume/area change from decimation
RHO_PLA = 1.24            # g/cm3
STL_PATH = ROOT / "stl" / "gyroid_3x3_40mm.stl"


def jsonable(o):
    if isinstance(o, dict):
        return {k: jsonable(v) for k, v in o.items() if k != "map"}
    if isinstance(o, list):
        return [jsonable(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    return o


def opening_summary(st):
    s = {}
    for ax, v in st.items():
        full = [h for h in v["openings"] if not h["edge_cut"]]
        rows_cols = grid_arrangement([h["centre_mm"] for h in full]) if full else (0, 0)
        s[ax] = {"full": v["full_openings"], "edge_cut": v["edge_cut_openings"],
                 "grid_cols_rows": rows_cols,
                 "min_clear_diameter_mm": round(v["min_clear_diameter_mm"], 2),
                 "open_area_pct": round(100 * v["open_area_fraction"], 1)}
    return s


def design_study():
    """Field-level comparison: original, naive 3-period and the 1.5-period (3-opening) layout."""
    cases = [("original (printed) a=8, w=0.9, shift 0", 8.0, 0.9, 0.0),
             ("naive 3 periods a=13.33, w=1.6, shift a/8", L / 3, 1.6, L / 3 / 8),
             ("3 openings a=26.67, w=0.9, shift a/8", A, 0.9, SHIFT),
             ("3 openings a=26.67, w=1.2, shift a/8", A, 1.2, SHIFT),
             ("3 openings a=26.67, w=1.6, shift a/8 [selected]", A, 1.6, SHIFT),
             ("3 openings a=26.67, w=2.0, shift a/8", A, 2.0, SHIFT),
             ("3 openings a=26.67, w=1.6, shift 0 (wrong phase)", A, 1.6, 0.0)]
    rows = []
    for name, a, w, sh in cases:
        vol = voxelize_field(L, a, w, sh, px=0.1)
        st = opening_summary(see_through(vol, 0.1))
        ls = lattice_stats(a, w)
        rows.append({"case": name, "period_mm": round(a, 3), "periods_per_axis": round(L / a, 3),
                     "wall_nominal_mm": w, "shift_mm": round(sh, 3), "openings": st,
                     "wall_p1_mm": round(ls["wall_p1_mm"], 3), "wall_median_mm": round(ls["wall_median_mm"], 3),
                     "bottleneck_mm": round(ls["bottleneck_mm"], 2),
                     "solid_fraction_est": round(float(vol.mean()), 3),
                     "mass_g_est": round(float(vol.mean()) * L ** 3 / 1000 * RHO_PLA, 1)})
        z = st["z"]
        print(f"  {name:52s} openings/face {z['full']} whole + {z['edge_cut']} cut, "
              f"clear d {z['min_clear_diameter_mm']:.2f} mm, wall p1 {ls['wall_p1_mm']:.2f}, "
              f"bottleneck {ls['bottleneck_mm']:.2f}, ~{rows[-1]['mass_g_est']} g", flush=True)
    return rows


def wall_thickness_from_voxels(vol, px, band=1.0):
    """Local 3D wall thickness at medial voxels more than `band` mm from any face.
    (Next to a face the distance transform measures the distance to the face plane, not
    the wall, so the faces are assessed separately with face_strip_widths.)"""
    dt = ndi.distance_transform_edt(np.pad(vol, 1))[1:-1, 1:-1, 1:-1] * px
    med = vol & (dt >= ndi.maximum_filter(dt, size=3) - 1e-9)
    z, y, x = np.nonzero(med)
    t = 2 * dt[z, y, x]
    n = vol.shape[0]
    dface = np.minimum.reduce([z, y, x, n - 1 - z, n - 1 - y, n - 1 - x]) * px + px / 2
    ti = t[dface > band]
    q = lambda v, p: float(np.percentile(v, p))
    return {"min": float(ti.min()), "p1": q(ti, 1), "p5": q(ti, 5), "median": q(ti, 50),
            "max": float(ti.max()), "excluded_band_mm": band, "voxel_mm": px}


def face_strip_widths(vol, px):
    """Width of the solid strips printed on each of the six cube faces (2 x distance
    transform on the strip centreline). Thin values are knife edges where a wall meets a
    face at a grazing angle; tips within 0.3 mm of a cube edge are excluded."""
    faces = [vol[:, :, 0], vol[:, :, -1], vol[:, 0, :], vol[:, -1, :], vol[0], vol[-1]]
    widths = []
    for s in faces:
        dt = ndi.distance_transform_edt(np.pad(s, 1))[1:-1, 1:-1] * px
        sk = skeletonize(s)
        e = int(round(0.3 / px))
        sk[:e] = sk[-e:] = False
        sk[:, :e] = sk[:, -e:] = False
        widths.append(2 * dt[sk])
    w = np.concatenate(widths)
    return {"p1": float(np.percentile(w, 1)), "p5": float(np.percentile(w, 5)),
            "median": float(np.median(w)), "share_below_0.4mm": float((w < 0.4).mean()),
            "share_below_0.8mm": float((w < 0.8).mean())}


def main(validate_only=False):
    t0 = time.time()
    if validate_only:
        # Re-validate the existing STL; keep the build records of the run that wrote it.
        prev = json.loads((OUT / "validation.json").read_text())
        info, dv, da = prev["mesh_build"], prev["decimation"]["vol_change_pct"], prev["decimation"]["area_change_pct"]
    else:
        info, dv, da = build()
    validate(info, dv, da)
    print(f"done in {time.time() - t0:.0f}s")


def build():
    print("Design study (design field, 0.1 mm voxels):", flush=True)
    study = design_study()
    (OUT / "design_study.json").write_text(json.dumps(jsonable(study), indent=2))

    print(f"\nBuilding a={A:.3f} mm, w={W} mm, shift={SHIFT:.3f} mm, pitch {PITCH} mm", flush=True)
    mesh, info = build_mesh(L, A, W, PITCH, shift=SHIFT)
    mesh = sanitize(mesh)
    full = measure(mesh, L, W)
    chosen, dv, da = None, 0.0, 0.0
    for target in TARGET_FACES:
        if target >= len(mesh.faces):
            break
        dec = sanitize(mesh.simplify_quadric_decimation(face_count=target))
        if dec.volume < 0:
            dec.invert()
        dm = measure(dec, L, W)
        dv = 100 * (dm["solid_volume_mm3"] / full["solid_volume_mm3"] - 1)
        da = 100 * (dm["wetted_area_mm2"] / full["wetted_area_mm2"] - 1)
        ok = (dm["watertight"] and dm["is_volume"] and len(dec.split(only_watertight=False)) == 1
              and abs(dv) < MAX_DEV and abs(da) < MAX_DEV)
        d = defects(dec) if ok else None
        ok = ok and defect_free(d)
        print(f"  decimate->{target}: dV={dv:+.3f}% dA={da:+.3f}% defects={d} {'ACCEPT' if ok else 'reject'}", flush=True)
        if ok:
            chosen = dec
            break
    if chosen is None:
        if not defect_free(defects(mesh)):
            raise SystemExit("no mesh passed the acceptance checks")
        chosen, dv, da = mesh, 0.0, 0.0
    chosen.export(STL_PATH)
    return info, dv, da


def validate(info, dv, da):
    """Everything here is measured on the STL file as written to disk."""
    m = trimesh.load(STL_PATH, force="mesh")
    geo = measure(m, L, W)
    geo["bodies"] = len(m.split(only_watertight=False))
    geo["defects"] = defects(m)
    geo["bounds_mm"] = m.bounds.tolist()
    geo["size_mm"] = (m.bounds[1] - m.bounds[0]).tolist()
    geo["file_bytes"] = STL_PATH.stat().st_size
    if not (geo["watertight"] and geo["is_volume"] and geo["bodies"] == 1 and defect_free(geo["defects"])):
        raise SystemExit(f"exported STL failed re-verification: {geo}")
    print(f"  exported {STL_PATH.name}: {geo['triangles']} tris, {geo['file_bytes']/1e6:.1f} MB, "
          f"size {np.round(geo['size_mm'], 3).tolist()}, defects {geo['defects']}", flush=True)

    vol = voxelize_mesh(m, L, px=0.1)
    st = see_through(vol, 0.1)
    np.savez_compressed(OUT / "see_through_maps.npz", **{ax: st[ax]["map"] for ax in st})
    validation = {
        "parameters": {"L_mm": L, "period_mm": A, "periods_per_axis": L / A, "openings_per_axis": OPENINGS_PER_AXIS,
                       "shift_mm": SHIFT, "wall_nominal_mm": W, "mc_pitch_mm": PITCH,
                       "equation": "sin(X)cos(Y)+sin(Y)cos(Z)+sin(Z)cos(X), X=2*pi*(x+shift)/a; solid |g/|grad g|| <= w/2"},
        "mesh_build": info,
        "decimation": {"faces": int(len(m.faces)), "vol_change_pct": dv, "area_change_pct": da},
        "geometry": geo,
        "pla_mass_g": geo["solid_volume_mm3"] / 1000 * RHO_PLA,
        "see_through": opening_summary(st),
        "see_through_detail": {ax: st[ax]["openings"] for ax in st},
        "voxelizer_rows_repaired": mesh_checks.ODD_ROWS["repaired"],
        "face_mouths": face_mouths(vol, 0.1),
        "wall_thickness_on_mesh": wall_thickness_from_voxels(vol, 0.1),
        "face_strip_widths": face_strip_widths(vol, 0.1),
        "bottleneck_on_mesh_mm": bottleneck(voxelize_mesh(m, L, px=0.2), 0.2),
        "lattice_field": lattice_stats(A, W),
    }
    del vol
    print("  openings:", validation["see_through"], flush=True)
    print("  walls:", validation["wall_thickness_on_mesh"], flush=True)
    print("  bottleneck:", validation["bottleneck_on_mesh_mm"], flush=True)
    print("  layer analysis ...", flush=True)
    validation["printability"] = layer_analysis(m, L)
    (OUT / "validation.json").write_text(json.dumps(jsonable(validation), indent=2))
    pa = validation["printability"]
    print(f"  first layer {pa['first_layer']['islands']} islands / {pa['first_layer']['area_mm2']:.0f} mm2; "
          f"islands/layer {pa['islands_per_layer']}; floating {pa['floating_islands']['total']}; "
          f"overhang {pa['overhang']['max_reach_per_layer_mm']:.2f} mm max reach", flush=True)

    # Original printed design, same opening + layer analysis, for the before/after comparison
    print("\nOriginal design (for comparison):", flush=True)
    orig = {}
    for f in ["gyroid_final_test_article", "gyroid_final_core"]:
        mo = trimesh.load(ROOT / "stl" / f"{f}.stl", force="mesh")
        vo = voxelize_mesh(mo, L, px=0.1)
        orig[f] = {"see_through": opening_summary(see_through(vo, 0.1)),
                   "face_mouths": face_mouths(vo, 0.1)}
        print(f"  {f}: {orig[f]['see_through']}", flush=True)
    orig["gyroid_final_test_article"]["printability"] = layer_analysis(
        trimesh.load(ROOT / "stl" / "gyroid_final_test_article.stl", force="mesh"), L)
    (OUT / "original_comparison.json").write_text(json.dumps(jsonable(orig), indent=2))


if __name__ == "__main__":
    main(validate_only="--validate-only" in sys.argv)
