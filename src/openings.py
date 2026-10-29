"""
Opening analysis on a voxelised solid (from the exported mesh or from the design field).

Definitions (all in mm):
- see-through opening: a connected region of the face, viewed along one axis, where a
  straight line of sight passes through the whole 40 mm cube without touching solid.
  This is what "an opening you can see through" means physically. Openings touching the
  face border are reported separately as edge-cut.
- clear diameter: diameter of the largest circle inscribed in a see-through opening
  (the largest rod that can be pushed straight through it).
- face mouth: a connected void region on a face plane (what you see on the surface,
  including channel mouths that are not straight see-through).
- bottleneck: largest sphere diameter that can travel from one face to the opposite
  face through the void (channels may be curved).
"""
import numpy as np
import trimesh
from scipy import ndimage as ndi

from mesh_checks import _fill, _slice


def voxelize_mesh(m: trimesh.Trimesh, L=40.0, px=0.1) -> np.ndarray:
    """Solid occupancy of the cube [0, L]^3, indexed [z, y, x], voxel centres at (i+0.5)*px."""
    n = int(round(L / px))
    # _fill works on a grid starting at origin O with N cells; use O = 0 so cells match.
    vol = np.zeros((n, n, n), bool)
    T = m.triangles
    for k in range(n):
        z = (k + 0.5) * px
        p, q = _slice(T, z)
        if len(p):
            vol[k] = _fill(p, q, 0.0, n, px)
    return vol


def voxelize_field(L, a, w, shift, px=0.1) -> np.ndarray:
    """Solid occupancy from the design field (sheet |g/|grad g|| <= w/2), indexed [z, y, x]."""
    n = int(round(L / px))
    x = ((np.arange(n) + 0.5) * px + shift).astype(np.float32)
    k = np.float32(2 * np.pi / a)
    Z, Y, X = (k * x)[:, None, None], (k * x)[None, :, None], (k * x)[None, None, :]
    sX, cX, sY, cY, sZ, cZ = np.sin(X), np.cos(X), np.sin(Y), np.cos(Y), np.sin(Z), np.cos(Z)
    g = sX * cY + sY * cZ + sZ * cX
    grad = k * np.sqrt((cX * cY - sZ * sX) ** 2 + (cY * cZ - sX * sY) ** 2 + (cZ * cX - sY * sZ) ** 2)
    return np.abs(g) / np.maximum(grad, np.float32(1e-3 * k)) <= w / 2


AXES = {"x": 2, "y": 1, "z": 0}  # array axis for each viewing direction ([z, y, x] indexing)


def see_through(vol: np.ndarray, px: float) -> dict:
    """See-through openings for viewing along x, y and z."""
    out = {}
    for name, ax in AXES.items():
        open_map = ~vol.any(axis=ax)  # 2D map of the face, True = line of sight is clear
        lab, n = ndi.label(open_map)
        border = set(np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]])) - {0}
        dt = ndi.distance_transform_edt(open_map) * px
        holes = []
        for i in range(1, n + 1):
            r, c = np.nonzero(lab == i)
            holes.append({
                "edge_cut": i in border,
                "clear_diameter_mm": float(2 * dt[r, c].max()),
                "area_mm2": float(len(r) * px * px),
                # centre in face coordinates (u, v) = (column, row) of the 2D map
                "centre_mm": [float((c.mean() + 0.5) * px), float((r.mean() + 0.5) * px)],
            })
        full = [h for h in holes if not h["edge_cut"]]
        out[name] = {
            "full_openings": len(full),
            "edge_cut_openings": len(holes) - len(full),
            "min_clear_diameter_mm": min((h["clear_diameter_mm"] for h in full), default=0.0),
            "max_clear_diameter_mm": max((h["clear_diameter_mm"] for h in full), default=0.0),
            "open_area_fraction": float(open_map.mean()),
            "openings": holes,
            "map": open_map,
        }
    return out


def grid_arrangement(centres, tol=1.0):
    """Number of distinct rows and columns among opening centres (clustered within tol mm)."""
    def clusters(v):
        v = np.sort(np.asarray(v))
        return int(1 + (np.diff(v) > tol).sum()) if len(v) else 0
    c = np.asarray(centres)
    return clusters(c[:, 0]), clusters(c[:, 1])


def face_mouths(vol: np.ndarray, px: float) -> dict:
    """Void regions on each of the six face planes (outermost voxel layer)."""
    faces = {"x0": vol[:, :, 0], "x1": vol[:, :, -1], "y0": vol[:, 0, :], "y1": vol[:, -1, :],
             "z0": vol[0], "z1": vol[-1]}
    out = {}
    for name, solid in faces.items():
        void = ~solid
        lab, n = ndi.label(void)
        sizes = ndi.sum(void, lab, range(1, n + 1)) * px * px
        dt = ndi.distance_transform_edt(void) * px
        insc = ndi.maximum(dt, lab, range(1, n + 1)) * 2 if n else []
        out[name] = {"void_regions": int(n), "open_fraction": float(void.mean()),
                     "largest_inscribed_diameter_mm": float(np.max(insc)) if n else 0.0,
                     "solid_fraction_on_face": float(solid.mean()),
                     "solid_islands_on_face": int(ndi.label(solid, np.ones((3, 3)))[1]),
                     "region_areas_mm2": sorted([float(s) for s in sizes], reverse=True)[:12]}
    return out


def bottleneck(vol: np.ndarray, px: float) -> dict:
    """Largest sphere that passes face-to-face along each axis (binary search on percolation)."""
    dv = 2 * ndi.distance_transform_edt(~vol) * px
    out = {}
    for name, ax in AXES.items():
        lo, hi = 0.0, float(dv.max())
        while hi - lo > 0.05:
            D = (lo + hi) / 2
            lab, _ = ndi.label(dv >= D)
            a = set(np.unique(np.take(lab, 0, axis=ax))) - {0}
            b = set(np.unique(np.take(lab, -1, axis=ax))) - {0}
            lo, hi = (D, hi) if a & b else (lo, D)
        out[name] = round(lo, 2)
    return out
