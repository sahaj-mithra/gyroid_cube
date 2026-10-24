"""
Build, decimate, export and re-verify the selected design (from results/selection.json).

Outputs (stl/):
  gyroid_final_core.stl          selected lattice only, 40 mm cube (geometry reported in the comparison)
  gyroid_final_test_article.stl  same lattice + 1.25 mm side walls on x/y faces, open in z
                                 (ducts the test air through the lattice; print-ready)
  gyroid_reference_a10_w1.0.stl  reference design (10 mm cell, 1.0 mm wall), for A/B testing

A mesh is exported only if it is watertight, single-body and free of zero-area faces,
open/non-manifold edges and self-intersections (src/mesh_checks.py), both before export
and after reloading the written file.
"""
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).parent))
from gyroid import build_mesh, lattice_stats, measure  # noqa: E402
from mesh_checks import defect_free, defects  # noqa: E402
from sweep import L, estimates  # noqa: E402

warnings.filterwarnings("ignore", category=RuntimeWarning, module="trimesh")
ROOT = Path(__file__).resolve().parent.parent
STL = ROOT / "stl"
STL.mkdir(exist_ok=True)
PITCH = 0.2            # mm; convergence study: ~0.2 % from the finest mesh
TARGET_FACES = [600_000, 900_000, 1_300_000, 1_800_000]  # tried in order
SKIN = 1.25            # mm, 3 lines at ~0.42 mm; NOT a multiple of PITCH (1.2 put the skin
                       # plane on grid nodes and produced zero-area faces, see audit)
MAX_DEV = 0.5          # %, max allowed volume/area change from decimation

sel = json.loads((ROOT / "results" / "selection.json").read_text())["selected"]
jobs = [
    ("gyroid_final_core", sel["cell_mm"], sel["wall_mm"], 0.0),
    ("gyroid_final_test_article", sel["cell_mm"], sel["wall_mm"], SKIN),
    ("gyroid_reference_a10_w1.0", 10.0, 1.0, 0.0),
]


def sanitize(m):
    """Mimic the STL round trip (float32 vertices) and drop the zero-area
    back-to-back triangle pairs that quadric decimation occasionally leaves."""
    m = trimesh.Trimesh(vertices=m.vertices.astype(np.float32).astype(np.float64),
                        faces=m.faces, process=True)
    # The degenerate pairs share edges with the main surface, so deleting faces
    # opens holes; splitting by face adjacency isolates them as zero-volume bodies.
    parts = m.split(only_watertight=False)
    return max(parts, key=lambda p: len(p.faces)) if len(parts) > 1 else m


def acceptable(m, ref=None):
    """Return (ok, measurements, defect counts). Cheap checks first."""
    mm = measure(m, L, 0)
    if not (mm["watertight"] and mm["is_volume"] and len(m.split(only_watertight=False)) == 1):
        return False, mm, None
    if ref is not None:
        dv = 100 * (mm["solid_volume_mm3"] / ref["solid_volume_mm3"] - 1)
        da = 100 * (mm["wetted_area_mm2"] / ref["wetted_area_mm2"] - 1)
        if abs(dv) >= MAX_DEV or abs(da) >= MAX_DEV:
            return False, mm, None
    d = defects(m)
    return defect_free(d), mm, d


report = {"selected": sel, "pitch_mm": PITCH, "skin_mm": SKIN, "parts": {}}
for name, a, w, skin in jobs:
    print(f"== {name}: a={a} w={w} skin={skin}", flush=True)
    mesh, info = build_mesh(L, a, w, PITCH, skin=skin)
    mesh = sanitize(mesh)
    full = measure(mesh, L, w)
    print(f"   full-res: tris={full['triangles']} watertight={full['watertight']} "
          f"bodies_raw={info['bodies_raw']}", flush=True)

    # Smallest face budget whose decimated mesh passes every check and stays within
    # MAX_DEV % of the full-resolution volume and wetted area.
    chosen, faces, dv, da = None, None, 0.0, 0.0
    for target in TARGET_FACES:
        if target >= len(mesh.faces):
            break
        dec = sanitize(mesh.simplify_quadric_decimation(face_count=target))
        if dec.volume < 0:
            dec.invert()
        ok, dm, d = acceptable(dec, full)
        dv = 100 * (dm["solid_volume_mm3"] / full["solid_volume_mm3"] - 1)
        da = 100 * (dm["wetted_area_mm2"] / full["wetted_area_mm2"] - 1)
        print(f"   decimate->{target}: dV={dv:+.3f}% dA={da:+.3f}% defects={d} "
              f"{'ACCEPT' if ok else 'reject'}", flush=True)
        if ok:
            chosen, faces = dec, target
            break
    if chosen is None:
        ok, _, d = acceptable(mesh)
        print(f"   full-res fallback defects={d} {'ACCEPT' if ok else 'REJECT'}", flush=True)
        if not ok:
            raise SystemExit(f"{name}: no mesh passed the acceptance checks")
        chosen, faces, dv, da = mesh, len(mesh.faces), 0.0, 0.0

    path = STL / f"{name}.stl"
    chosen.export(path)

    # Re-verify from the file on disk, not from memory.
    back = trimesh.load(path, force="mesh")
    m = measure(back, L, w)
    m["bodies"] = len(back.split(only_watertight=False))
    m["bbox_mm"] = back.bounds.tolist()
    m["file_bytes"] = path.stat().st_size
    m["defects"] = defects(back)
    if not (m["watertight"] and m["is_volume"] and m["bodies"] == 1 and defect_free(m["defects"])):
        raise SystemExit(f"{path.name} failed re-verification after export: "
                         f"watertight={m['watertight']} bodies={m['bodies']} defects={m['defects']}")
    ls = lattice_stats(a, w)
    report["parts"][name] = {
        "cell_mm": a, "wall_nominal_mm": w, "skin_mm": skin, "file": str(path),
        "mesh_build": info,
        "lattice_measured": ls,
        "full_res_measured": full,
        "decimation": {"face_budget": faces, "vol_change_pct": dv, "area_change_pct": da},
        "exported_file_measured": m,
        "estimates_UNVERIFIED": estimates(full, ls["wall_median_mm"]),
    }
    print(f"   file {path.name}: {m['file_bytes']/1e6:.1f} MB, tris={m['triangles']}, "
          f"watertight={m['watertight']}, bodies={m['bodies']}, defects={m['defects']}, "
          f"V={m['solid_volume_mm3']:.0f} mm3, phi={m['solid_fraction']:.3f}, mass={m['pla_mass_g']:.1f} g",
          flush=True)

(ROOT / "results" / "final_metrics.json").write_text(json.dumps(report, indent=2))
print("wrote results/final_metrics.json")
