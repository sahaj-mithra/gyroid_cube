"""Check that every deliverable exists, is non-empty and is valid. Exit code 1 on failure."""
import csv
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from mesh_checks import defect_free, defects, mesh_wall_thickness  # noqa: E402

warnings.filterwarnings("ignore", category=RuntimeWarning, module="trimesh")
ROOT = Path(__file__).resolve().parent.parent
L = 40.0
MIN_WALL = 0.8        # mm, 1st percentile of wall thickness measured on the exported mesh
MIN_BOTTLENECK = 2.5  # mm
fails = []


def check(cond, msg):
    print(("  OK   " if cond else "  FAIL ") + msg)
    if not cond:
        fails.append(msg)


files = ["requirements.txt", "REPORT.md", "src/gyroid.py", "src/mesh_checks.py", "src/convergence.py",
         "src/sweep.py", "src/build_final.py", "src/render_sections.py", "src/verify_outputs.py",
         "results/convergence.json", "results/sweep_results.csv", "results/weight_sensitivity.csv",
         "results/selection.json", "results/final_metrics.json",
         "results/sweep_tradeoff.png", "results/cross_sections.png",
         "stl/gyroid_final_core.stl", "stl/gyroid_final_test_article.stl",
         "stl/gyroid_reference_a10_w1.0.stl"]
print("Files:")
for f in files:
    p = ROOT / f
    check(p.is_file() and p.stat().st_size > 0, f"{p}  ({p.stat().st_size if p.exists() else 0} bytes)")

print("Data:")
rows = list(csv.DictReader(open(ROOT / "results/sweep_results.csv")))
check(len(rows) == 30, f"sweep_results.csv has {len(rows)} designs (expect 30)")
check(all(r["watertight"] == "True" for r in rows), "all sweep meshes watertight")
sel = json.loads((ROOT / "results/selection.json").read_text())["selected"]
srow = next((r for r in rows if r["design"] == sel["design"]), None)
check(srow is not None and srow["feasible"] == "True",
      f"selected design {sel['design']} is in the sweep and feasible")
if srow is not None:
    check(float(srow["wall_p1_mm"]) >= MIN_WALL,
          f"selected design measured wall p1 {float(srow['wall_p1_mm']):.3f} mm >= {MIN_WALL}")
    check(float(srow["bottleneck_mm"]) >= MIN_BOTTLENECK,
          f"selected design channel bottleneck {float(srow['bottleneck_mm']):.2f} mm >= {MIN_BOTTLENECK}")
json.loads((ROOT / "results/final_metrics.json").read_text())
json.loads((ROOT / "results/convergence.json").read_text())
for png in ["results/sweep_tradeoff.png", "results/cross_sections.png"]:
    with Image.open(ROOT / png) as im:
        im.verify()
    check(True, f"{png} is a valid image")

print("STL files (reloaded from disk):")
for f in files:
    if not f.endswith(".stl"):
        continue
    m = trimesh.load(ROOT / f, force="mesh")
    b = m.bounds
    bodies = len(m.split(only_watertight=False))
    size_ok = all(abs(b[0][i]) < 0.1 and abs(b[1][i] - L) < 0.1 for i in range(3))
    check(m.is_watertight and m.is_winding_consistent and m.is_volume and bodies == 1 and size_ok,
          f"{f}: watertight={m.is_watertight} volume={m.is_volume} bodies={bodies} "
          f"bbox={b[1] - b[0]} V={m.volume:.0f} mm3")
    d = defects(m)
    check(defect_free(d), f"{f}: {d}")

    # Wall thickness measured on the exported mesh (not the design field).
    a = sel["cell_mm"] if "final" in f else 10.0
    blocks = [("interior", 20 - a, 20 + a)]
    if "test_article" in f:
        blocks.append(("corner incl. skin junction", 0.0, 8.0))
    for label, lo, hi in blocks:
        t = mesh_wall_thickness(m, lo, hi)
        check(np.percentile(t, 1) >= MIN_WALL,
              f"{f} [{label}]: wall thickness on mesh p1 {np.percentile(t, 1):.3f}  min {t.min():.3f}  "
              f"median {np.median(t):.3f} mm (n={len(t):,})")
    if "core" in f:  # informational: knife-edge tips where walls meet the bare side faces
        t = mesh_wall_thickness(m, 0.0, 8.0)
        print(f"  INFO {f} [corner, bare side faces]: min {t.min():.3f}  p1 {np.percentile(t, 1):.3f} mm "
              f"(thin tips at cut faces; print the test article)")

print("\nRESULT:", "ALL CHECKS PASSED" if not fails else f"{len(fails)} FAILURE(S)")
sys.exit(1 if fails else 0)
