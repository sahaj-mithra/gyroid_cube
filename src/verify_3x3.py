"""Check every revision-3 deliverable from disk. Exit code 1 on any failure."""
import json
import sys
import warnings
from pathlib import Path

import trimesh
from PIL import Image
from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).parent))
from mesh_checks import defect_free, defects  # noqa: E402
from openings import grid_arrangement, see_through, voxelize_mesh  # noqa: E402

warnings.filterwarnings("ignore", category=RuntimeWarning, module="trimesh")
ROOT = Path(__file__).resolve().parent.parent
fails = []


def check(cond, msg):
    print(("  OK   " if cond else "  FAIL ") + msg)
    if not cond:
        fails.append(msg)


files = ["stl/gyroid_3x3_40mm.stl", "src/build_3x3.py", "src/gyroid.py", "src/mesh_checks.py", "src/openings.py",
         "src/printability.py", "src/slice_check.py", "src/render_views.py", "src/make_report.py",
         "print/prusaslicer_PLA_0.4mm_gyroid_3x3.ini", "results/3x3/validation.json",
         "results/3x3/design_study.json", "results/3x3/original_comparison.json",
         "results/3x3/slicer/slicer_report.json", "Gyroid_Design_and_3D_Printing_Report.pdf",
         "Gyroid_3D_Printing_Settings.txt"]
views = ["view_front", "view_side", "view_top", "view_iso", "views_composite", "openings_annotated",
         "before_after_front", "sections_mid", "slicer_layers"]
print("Files:")
for f in files + [f"results/3x3/views/{v}.png" for v in views]:
    p = ROOT / f
    check(p.is_file() and p.stat().st_size > 0, f"{p} ({p.stat().st_size if p.exists() else 0:,} bytes)")
for v in views:
    with Image.open(ROOT / "results/3x3/views" / f"{v}.png") as im:
        im.verify()

print("STL (reloaded from disk):")
m = trimesh.load(ROOT / "stl/gyroid_3x3_40mm.stl", force="mesh")
size = m.bounds[1] - m.bounds[0]
check(all(abs(s - 40.0) < 0.05 for s in size), f"size {size.round(3).tolist()} mm (40 +- 0.05)")
check(m.is_watertight and m.is_winding_consistent and m.is_volume, "watertight, consistent winding, valid volume")
check(len(m.split(only_watertight=False)) == 1, "single connected body")
d = defects(m)
check(defect_free(d), f"defects {d}")
st = see_through(voxelize_mesh(m, 40.0, 0.1), 0.1)
for ax in "xyz":
    full = [h for h in st[ax]["openings"] if not h["edge_cut"]]
    grid = grid_arrangement([h["centre_mm"] for h in full])
    check(len(full) == 9 and grid == (3, 3) and st[ax]["min_clear_diameter_mm"] >= 4.5,
          f"{ax}: {len(full)} whole openings, grid {grid}, min clear {st[ax]['min_clear_diameter_mm']:.2f} mm")

print("Validation / slicer data:")
v = json.loads((ROOT / "results/3x3/validation.json").read_text())
check(v["wall_thickness_on_mesh"]["p1"] >= 1.2, f"3D wall p1 {v['wall_thickness_on_mesh']['p1']:.2f} mm >= 1.2")
sl = json.loads((ROOT / "results/3x3/slicer/slicer_report.json").read_text())
off = sl["cases"]["new_supports_off"]
check(off["support_extrusion_mm"] == 0, f"supports OFF: {off['support_extrusion_mm']} mm support")
check(all(off["openings_after_slicing"][ax]["full"] == 9 for ax in "xyz"),
      f"openings after slicing {[off['openings_after_slicing'][ax]['full'] for ax in 'xyz']}")
check(off["brim_inside_footprint_mm2"] == 0, f"no brim inside the footprint ({off['brim_inside_footprint_mm2']} mm2)")
check("brim_type = no_brim" in (ROOT / "print/prusaslicer_PLA_0.4mm_gyroid_3x3.ini").read_text(),
      "PrusaSlicer profile has no brim")

print("PDF:")
r = PdfReader(ROOT / "Gyroid_Design_and_3D_Printing_Report.pdf")
text = "".join(pg.extract_text() for pg in r.pages)
check(len(r.pages) >= 8, f"{len(r.pages)} pages")
for s in ["Original design assessment", "Updated geometry", "Design changes", "3D-printability assessment",
          "Material selection", "Final slicer configuration", "Support-removal strategy", "Validation results",
          "Final deliverables", "Final recommendations", "Pre-print checklist", "Not performed",
          "Why no brim", "Gyroid_3D_Printing_Settings.txt"]:
    check(s in text, f"PDF contains '{s}'")

print("\nRESULT:", "ALL CHECKS PASSED" if not fails else f"{len(fails)} FAILURE(S)")
sys.exit(1 if fails else 0)
