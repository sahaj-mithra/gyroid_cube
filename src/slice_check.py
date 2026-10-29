"""
Real-slicer check with PrusaSlicer (CLI) and analysis of the generated G-code.

For each case the model is sliced, then the G-code is read back:
- print time and filament from PrusaSlicer's own estimates,
- extrusion length per feature type (perimeters, infill, bridges, support, ...),
- the printed volume is rebuilt from the toolpaths (each extrusion stamped with its real
  ;WIDTH and layer height) and checked for see-through openings along x, y and z, i.e.
  whether the openings survive slicing,
- support material, if any, is classified per connected region as "clear to bed"
  (straight vertical void down to the bed: pull-out) or "resting on model" (stands on the
  lattice's own surfaces inside the cube: likely trapped).

Usage: python src/slice_check.py <prusa-slicer-console.exe>
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).parent))
from openings import grid_arrangement  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "print" / "prusaslicer_PLA_0.4mm_gyroid_3x3.ini"
OUT = ROOT / "results" / "3x3" / "slicer"
OUT.mkdir(parents=True, exist_ok=True)
CENTER = (110.0, 110.0)
L, PX, LH = 40.0, 0.05, 0.2

CASES = {
    # name: (stl, extra CLI options)
    "new_supports_off": ("stl/gyroid_3x3_40mm.stl", []),
    "new_supports_buildplate_only": ("stl/gyroid_3x3_40mm.stl",
                                     ["--support-material", "--support-material-buildplate-only"]),
    "new_supports_everywhere": ("stl/gyroid_3x3_40mm.stl",
                                ["--support-material", "--no-support-material-buildplate-only"]),
    "original_supports_everywhere": ("stl/gyroid_final_test_article.stl",
                                     ["--support-material", "--no-support-material-buildplate-only"]),
}
# Alternative setups sliced for print time / filament only (layer height differs from LH,
# so the toolpath-raster checks above are not applied to them).
ESTIMATE_CASES = {
    "new_supports_off_nozzle0.6": ("stl/gyroid_3x3_40mm.stl",
                                   ["--nozzle-diameter", "0.6", "--layer-height", "0.3",
                                    "--first-layer-height", "0.3", "--extrusion-width", "0.65",
                                    "--perimeter-extrusion-width", "0.65",
                                    "--external-perimeter-extrusion-width", "0.65",
                                    "--first-layer-extrusion-width", "0.7", "--infill-extrusion-width", "0.65",
                                    "--solid-infill-extrusion-width", "0.65", "--top-infill-extrusion-width", "0.6",
                                    "--perimeters", "2", "--filament-max-volumetric-speed", "15"]),
}
MODEL_TYPES = {"Perimeter", "External perimeter", "Overhang perimeter", "Internal infill", "Solid infill",
               "Top solid infill", "Bridge infill", "Gap fill"}
SUPPORT_TYPES = {"Support material", "Support material interface"}


def slice_case(exe, name, stl, extra):
    gcode = OUT / f"{name}.gcode"
    cmd = [exe, "--load", str(CFG), "--center", f"{CENTER[0]},{CENTER[1]}", *extra,
           "--export-gcode", "--output", str(gcode), str(ROOT / stl)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if r.returncode != 0 or not gcode.exists():
        raise RuntimeError(f"{name}: slicer failed\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return gcode, r.stdout


def parse_gcode(path):
    """Return extrusion segments [(z, type, x0, y0, x1, y1, width)] and summary comments."""
    segs, summary = [], {}
    z = 0.0; typ = None; width = 0.45; x = y = None
    num = re.compile(r"([XYZEF])(-?\d*\.?\d+)")
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if line.startswith(";"):
                if line.startswith(";Z:"):
                    z = float(line[3:])
                elif line.startswith(";TYPE:"):
                    typ = line[6:].strip()
                elif line.startswith(";WIDTH:"):
                    width = float(line[7:])
                elif line.startswith("; ") and "=" in line:
                    k, v = line[2:].split("=", 1)
                    k = k.strip()
                    if k.startswith(("estimated printing time", "filament used", "total filament used",
                                     "total layers count")):
                        summary[k] = v.strip()
                continue
            if line.startswith(("G1 ", "G0 ")):
                p = dict(num.findall(line.split(";")[0]))
                nx = float(p["X"]) if "X" in p else x
                ny = float(p["Y"]) if "Y" in p else y
                if "E" in p and float(p["E"]) > 0 and x is not None and (nx != x or ny != y):
                    segs.append((z, typ, x, y, nx, ny, width))
                x, y = nx, ny
    return segs, summary


def rasterize(segs, types, x0, y0, n, nz):
    """Printed occupancy [layer, y, x] from extrusion segments of the given feature types."""
    vol = np.zeros((nz, n, n), bool)
    by_layer = {}
    for s in segs:
        if s[1] in types:
            k = int(round(s[0] / LH)) - 1
            if 0 <= k < nz:
                by_layer.setdefault(k, []).append(s)
    for k, ss in by_layer.items():
        a = np.array([s[2:] for s in ss])  # x0 y0 x1 y1 w
        for wb in np.unique(np.round(a[:, 4] / 0.05) * 0.05):
            sel = np.abs(np.round(a[:, 4] / 0.05) * 0.05 - wb) < 1e-6
            b = a[sel]
            ln = np.hypot(b[:, 2] - b[:, 0], b[:, 3] - b[:, 1])
            ns = np.maximum(2, np.ceil(ln / (PX / 2)).astype(int))
            idx = np.repeat(np.arange(len(b)), ns)
            t = (np.arange(ns.sum()) - np.repeat(np.cumsum(ns) - ns, ns)) / np.repeat(ns - 1, ns)
            px_ = b[idx, 0] + t * (b[idx, 2] - b[idx, 0])
            py_ = b[idx, 1] + t * (b[idx, 3] - b[idx, 1])
            ix = np.floor((px_ - x0) / PX).astype(int)
            iy = np.floor((py_ - y0) / PX).astype(int)
            ok = (ix >= 0) & (ix < n) & (iy >= 0) & (iy < n)
            line = np.zeros((n, n), bool)
            line[iy[ok], ix[ok]] = True
            vol[k] |= ndi.distance_transform_edt(~line) * PX <= wb / 2
    return vol


def see_through_counts(model):
    """Openings that pass through the printed model, per viewing axis (array order [z, y, x])."""
    out = {}
    for name, ax in {"x": 2, "y": 1, "z": 0}.items():
        m = ~model.any(axis=ax)
        row_mm = PX if ax == 0 else LH  # 2D map rows are y (z-view) or layers (x/y-view)
        lab, n = ndi.label(m)
        border = set(np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]])) - {0}
        full = [i for i in range(1, n + 1) if i not in border]
        dt = ndi.distance_transform_edt(m, sampling=(row_mm, PX))
        d, cents = [], []
        for i in full:
            r, c = np.nonzero(lab == i)
            d.append(2 * dt[r, c].max())
            cents.append([c.mean() * PX, r.mean() * row_mm])
        out[name] = {"full": len(full), "edge_cut": len(border),
                     "grid_cols_rows": grid_arrangement(cents, 1.0) if cents else (0, 0),
                     "min_clear_diameter_mm": round(float(min(d)), 2) if d else 0.0}
    return out


def support_access(model, support):
    """Classify connected support regions by how they can be removed.

    clear_to_bed: every support voxel has no printed model below it in its column, so the
      support stands on the bed in a straight vertical void and can be pulled out downwards.
    resting_on_model: the support stands on the model's own surfaces inside the lattice;
      it is enclosed by curved walls and is likely to be trapped or hard to remove.
    """
    lab, n = ndi.label(support, np.ones((3, 3, 3)))
    res = {"regions": int(n), "clear_to_bed_mm3": 0.0, "resting_on_model_mm3": 0.0,
           "resting_on_model_regions": 0}
    if n == 0:
        return res
    vox = PX * PX * LH
    model_below = np.cumsum(model, axis=0) > 0  # any model at or below this layer
    for i in range(1, n + 1):
        k, yy, xx = np.nonzero(lab == i)
        vol = len(k) * vox
        if model_below[k, yy, xx].mean() < 0.05:
            res["clear_to_bed_mm3"] += vol
        else:
            res["resting_on_model_mm3"] += vol
            res["resting_on_model_regions"] += 1
    res["clear_to_bed_mm3"] = round(res["clear_to_bed_mm3"], 1)
    res["resting_on_model_mm3"] = round(res["resting_on_model_mm3"], 1)
    return res


def estimates(exe, report):
    report.setdefault("estimate_cases", {})
    for name, (stl, extra) in ESTIMATE_CASES.items():
        gcode, _ = slice_case(exe, name, stl, extra)
        segs, summary = parse_gcode(gcode)
        lengths = {}
        for s in segs:
            lengths[s[1]] = lengths.get(s[1], 0.0) + float(np.hypot(s[4] - s[2], s[5] - s[3]))
        report["estimate_cases"][name] = {
            "stl": stl, "options": extra, "gcode": str(gcode.relative_to(ROOT)), "prusaslicer_summary": summary,
            "extrusion_length_mm_by_type": {k: round(v, 1) for k, v in sorted(lengths.items(), key=lambda t: -t[1])}}
        print(f"{name}: time {summary.get('estimated printing time (normal mode)')}, "
              f"filament {summary.get('filament used [g]')} g", flush=True)


def main(exe, estimates_only=False):
    path = OUT / "slicer_report.json"
    if estimates_only:  # add the estimate cases to an existing report
        report = json.loads(path.read_text())
        estimates(exe, report)
        path.write_text(json.dumps(report, indent=2))
        return
    report = {"slicer": None, "config": str(CFG.relative_to(ROOT)), "cases": {}}
    for name, (stl, extra) in CASES.items():
        gcode, stdout = slice_case(exe, name, stl, extra)
        segs, summary = parse_gcode(gcode)
        x0, y0 = CENTER[0] - L / 2 - 0.5, CENTER[1] - L / 2 - 0.5
        n, nz = int((L + 1.0) / PX), int(round(L / LH))
        model = rasterize(segs, MODEL_TYPES, x0, y0, n, nz)
        support = rasterize(segs, SUPPORT_TYPES, x0, y0, n, nz)
        lengths = {}
        for s in segs:
            lengths[s[1]] = lengths.get(s[1], 0.0) + float(np.hypot(s[4] - s[2], s[5] - s[3]))
        case = {"stl": stl, "options": extra, "gcode": str(gcode.relative_to(ROOT)),
                "prusaslicer_summary": summary,
                "extrusion_length_mm_by_type": {k: round(v, 1) for k, v in sorted(lengths.items(), key=lambda t: -t[1])},
                "support_extrusion_mm": round(sum(v for k, v in lengths.items() if k in SUPPORT_TYPES), 1),
                "support_access": support_access(model, support),
                "openings_after_slicing": see_through_counts(model)}
        report["cases"][name] = case
        np.savez_compressed(OUT / f"{name}_layers.npz", model=model, support=support)
        print(f"{name}: time {summary.get('estimated printing time (normal mode)')}, "
              f"filament {summary.get('filament used [g]')} g, support {case['support_extrusion_mm']} mm, "
              f"access {case['support_access']}, openings {case['openings_after_slicing']}", flush=True)
    estimates(exe, report)
    ver = subprocess.run([exe, "--help"], capture_output=True, text=True).stdout.splitlines()[0]
    report["slicer"] = ver
    path.write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main(sys.argv[1], estimates_only="--estimates-only" in sys.argv)
