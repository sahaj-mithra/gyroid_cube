"""Mid-plane cross-sections of the final and reference designs (solid = dark)."""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parent))
from gyroid import solid_field  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
L, H, SKIN = 40.0, 0.1, 1.25
sel = json.loads((ROOT / "results" / "selection.json").read_text())["selected"]
a, w = sel["cell_mm"], sel["wall_mm"]
cases = [(f"Final: a = {a:.2f} mm, w = {w} mm (nominal)", a, w, 0.0),
         (f"Final test article (+{SKIN} mm side walls)", a, w, SKIN),
         ("Reference: a = 10 mm, w = 1.0 mm", 10.0, 1.0, 0.0)]
fig, axs = plt.subplots(1, 3, figsize=(13, 4.6))
for ax, (title, ca, cw, skin) in zip(axs, cases):
    f, sp, o = solid_field(L, ca, cw, H, skin)
    mid = f.shape[2] // 2
    ext = [o, o + sp * (f.shape[0] - 1)] * 2
    ax.imshow((f[:, :, mid] > 0).T, origin="lower", cmap="Greys", extent=ext)
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")
fig.suptitle("Cross-sections at z = 20 mm (flow direction z, out of page)")
fig.tight_layout()
fig.savefig(ROOT / "results" / "cross_sections.png", dpi=150)
print("wrote results/cross_sections.png")
