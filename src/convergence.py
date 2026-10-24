"""Mesh-resolution convergence study: how fine must the voxel pitch be for the
measured volume / area to be trustworthy? Run on the thinnest-wall case (worst case)."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gyroid import build_mesh, measure  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
L, a, w = 40.0, 8.0, 0.8
rows = []
for h in [0.5, 0.4, 0.3, 0.2, 0.15]:
    t0 = time.time()
    mesh, info = build_mesh(L, a, w, h)
    m = measure(mesh, L, w)
    rows.append({"pitch_mm": h, "seconds": round(time.time() - t0, 1), **info,
                 **{k: m[k] for k in ["solid_volume_mm3", "wetted_area_mm2",
                                       "mean_wall_thickness_mm", "triangles", "watertight"]}})
    print(rows[-1], flush=True)

ref = rows[-1]
for r in rows:
    r["vol_err_vs_finest_pct"] = 100 * (r["solid_volume_mm3"] / ref["solid_volume_mm3"] - 1)
    r["area_err_vs_finest_pct"] = 100 * (r["wetted_area_mm2"] / ref["wetted_area_mm2"] - 1)
(ROOT / "results").mkdir(exist_ok=True)
(ROOT / "results" / "convergence.json").write_text(json.dumps(rows, indent=2))
for r in rows:
    print(f"h={r['pitch_mm']}: dV={r['vol_err_vs_finest_pct']:+.2f}%  dA={r['area_err_vs_finest_pct']:+.2f}%  t={r['seconds']}s  tris={r['triangles']}")
