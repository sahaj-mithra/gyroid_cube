"""
Layer-by-layer printability analysis of a mesh (own scanline slicer, not a real slicer).

Per 0.2 mm layer (printed bottom-up along +z):
- in-plane wall width along the wall centreline (2 x distance transform on the skeleton),
- islands (separate printed regions) and islands with nothing underneath (floating starts),
- overhang reach: how far each new layer extends beyond the layer below. FDM prints
  reliably up to ~half a line width per layer at 0.2 mm (45 deg); larger reach means steep
  overhang, and a region printed far from any support is effectively a bridge/cantilever.

Calibration (audit): a 0.8 mm plate reads 0.791 mm, a 1.2 mm plate 1.202 mm at px = 0.025.
"""
import numpy as np
import trimesh
from scipy import ndimage as ndi
from skimage.morphology import skeletonize

from mesh_checks import _fill, _slice


def layer_analysis(m: trimesh.Trimesh, L=40.0, layer=0.2, px=0.025, edge_band=0.6):
    O = -0.2
    N = int(np.ceil((L + 0.4) / px))
    c = O + (np.arange(N) + 0.5) * px
    X, Y = np.meshgrid(c, c)
    dbox = np.minimum(np.minimum(X, L - X), np.minimum(Y, L - Y))
    T = m.triangles
    zs = (np.arange(int(round(L / layer))) + 0.5) * layer

    W_int, W_edge, islands, area = [], [], [], []
    floating = []
    reach_max, steep_area, unsup_regions = [], [], []
    prev, first = None, None
    for i, z in enumerate(zs):
        img = _fill(*_slice(T, z), O, N, px)
        dt = ndi.distance_transform_edt(np.pad(img, 1))[1:-1, 1:-1] * px
        sk = skeletonize(img)
        w = 2 * dt[sk]
        near = dbox[sk] <= edge_band
        W_int.append(w[~near])
        W_edge.append(w[near])
        lab, n = ndi.label(img, np.ones((3, 3)))
        islands.append(n)
        area.append(img.sum() * px * px)
        if i == 0:
            first = {"islands": int(n), "area_mm2": float(img.sum() * px * px),
                     "island_areas_mm2": sorted((ndi.sum(img, lab, range(1, n + 1)) * px * px).tolist())}
        else:
            ov = np.asarray(ndi.maximum(prev, lab, range(1, n + 1)), bool)
            new = np.nonzero(~ov)[0]
            if len(new):
                floating.append({"z": round(float(z), 2), "count": int(len(new)),
                                 "max_area_mm2": float((ndi.sum(img, lab, new + 1) * px * px).max())})
            reach = ndi.distance_transform_edt(~prev) * px  # distance to the layer below
            r = np.where(img, reach, 0)
            reach_max.append(float(r.max()))
            steep = r > 0.4  # more than ~one line width beyond the layer below
            steep_area.append(float(steep.sum() * px * px))
            if steep.any():
                sl, sn = ndi.label(steep, np.ones((3, 3)))
                sizes = ndi.sum(steep, sl, range(1, sn + 1)) * px * px
                j = int(np.argmax(sizes))
                unsup_regions.append({"z": round(float(z), 2), "largest_area_mm2": float(sizes[j]),
                                      "max_reach_mm": float(r[sl == j + 1].max())})
        prev = img

    Wi, We = np.concatenate(W_int), np.concatenate(W_edge)
    pct = lambda v, q: float(np.percentile(v, q)) if len(v) else float("nan")
    worst = sorted(unsup_regions, key=lambda d: -d["max_reach_mm"])[:5]
    return {
        "layers": len(zs), "layer_mm": layer, "pixel_mm": px,
        "layer_area_mm2": [float(min(area)), float(max(area))],
        "wall_width_interior_mm": {"p1": pct(Wi, 1), "p5": pct(Wi, 5), "median": pct(Wi, 50), "p95": pct(Wi, 95)},
        "wall_width_interior_share_below": {str(t): float((Wi < t).mean()) for t in (0.4, 0.8, 1.2, 1.6)},
        "wall_width_near_faces_share_below": {str(t): float((We < t).mean()) for t in (0.4, 0.6, 0.8)},
        "islands_per_layer": {"median": int(np.median(islands)), "max": int(max(islands))},
        "first_layer": first,
        "floating_islands": {"total": int(sum(f["count"] for f in floating)), "events": floating[:20]},
        "overhang": {
            "max_reach_per_layer_mm": float(max(reach_max)),
            "layers_with_reach_gt_0.4mm": int(sum(r > 0.4 for r in reach_max)),
            "steep_area_total_mm2": float(sum(steep_area)),
            "steep_area_max_per_layer_mm2": float(max(steep_area)),
            "worst_regions": worst,
        },
    }
