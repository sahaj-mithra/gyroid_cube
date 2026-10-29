"""
Sheet-gyroid geometry generation and geometric measurement.

Geometry
--------
Gyroid level-set:  g(x,y,z) = sin X cos Y + sin Y cos Z + sin Z cos X,  X = 2*pi*x/a
The *sheet* gyroid is the set of points within w/2 of the surface g = 0. We use the
first-order signed-distance approximation  d ~ g / |grad g|  so the parameter w is a
NOMINAL wall thickness in mm. The approximation makes the as-built wall ~5 % thinner
(audit: w = 0.8 -> median 0.76 mm), so the true local thickness is measured with
lattice_stats() and the printability constraints use that, not w.

The lattice is intersected with the bounding box via min(f, box_sdf), which puts the
cut faces exactly on the box planes and closes the mesh (watertight by construction).

Units: mm throughout unless stated.
"""
from __future__ import annotations

import numpy as np
import trimesh
from skimage.measure import marching_cubes


def _axis(L: float, h: float) -> np.ndarray:
    """Grid coordinates covering [0, L] with two padding nodes on each side."""
    n = int(round(L / h))
    return (np.arange(-2, n + 3, dtype=np.float32)) * np.float32(L / n)


def solid_field(L: float, a: float, w: float, h: float, skin: float = 0.0, shift: float = 0.0):
    """Return (field, spacing, origin). field > 0 inside solid.

    shift (mm) translates the lattice by the same amount along x, y and z relative to
    the cube, i.e. it chooses where the cube faces cut the gyroid (phase). It does not
    change the geometry of the lattice itself.
    """
    x = _axis(L, h)
    k = np.float32(2 * np.pi / a)
    xs = x + np.float32(shift)
    X = (k * xs)[:, None, None]
    Y = (k * xs)[None, :, None]
    Z = (k * xs)[None, None, :]
    sX, cX, sY, cY, sZ, cZ = np.sin(X), np.cos(X), np.sin(Y), np.cos(Y), np.sin(Z), np.cos(Z)

    g = sX * cY + sY * cZ + sZ * cX
    gx = cX * cY - sZ * sX
    gy = cY * cZ - sX * sY
    gz = cZ * cX - sY * sZ
    grad = k * np.sqrt(gx * gx + gy * gy + gz * gz)
    del gx, gy, gz
    # |grad g| only vanishes at critical points far from the surface; the floor
    # just avoids division by zero there (those points are deep in the voids).
    f = np.float32(w / 2) - np.abs(g) / np.maximum(grad, np.float32(1e-3 * k))
    del g, grad

    xi = x[:, None, None]
    yi = x[None, :, None]
    zi = x[None, None, :]
    if skin > 0:
        # Solid side walls on the four x/y faces; flow direction is z (open ends).
        d_side = np.minimum(np.minimum(xi, L - xi), np.minimum(yi, L - yi))
        f = np.maximum(f, np.float32(skin) - d_side)
    box = np.minimum(
        np.minimum(np.minimum(xi, L - xi), np.minimum(yi, L - yi)),
        np.minimum(zi, L - zi),
    )
    f = np.minimum(f, box).astype(np.float32)
    # Grid nodes lying exactly on the iso-level (box planes, skin = k*h) make marching
    # cubes emit degenerate triangles. The shift must be large enough to survive float32
    # STL export (1e-5 was not: audit found 8,140 zero-area faces), so use 1e-3 * h.
    eps = np.float32(1e-3 * h)
    f[np.abs(f) < eps] = -eps
    spacing = float(x[1] - x[0])
    return f, spacing, float(x[0])


def build_mesh(L, a, w, h, skin=0.0, keep_largest=True, shift=0.0):
    f, sp, origin = solid_field(L, a, w, h, skin, shift)
    verts, faces, _, _ = marching_cubes(f, level=0.0, spacing=(sp, sp, sp))
    del f
    verts += origin
    # skimage returns faces wound with normals toward increasing field (into the
    # solid); flip so normals point outward.
    mesh = trimesh.Trimesh(vertices=verts, faces=faces[:, ::-1], process=True)
    info = {"bodies_raw": None, "removed_fragment_volume_mm3": 0.0}
    if keep_largest:
        parts = mesh.split(only_watertight=False)
        info["bodies_raw"] = len(parts)
        if len(parts) > 1:
            vols = np.array([abs(p.volume) for p in parts])
            info["removed_fragment_volume_mm3"] = float(vols.sum() - vols.max())
            mesh = parts[int(vols.argmax())]
    if mesh.volume < 0:
        mesh.invert()
    return mesh, info


def _distance_field_cell(a: float, px: float, pad: int):
    """Approximate signed distance g/|grad g| on one periodic cell, wrap-padded."""
    n = int(round(a / px))
    x = ((np.arange(n) + 0.5) * (a / n)).astype(np.float32)
    k = np.float32(2 * np.pi / a)
    X, Y, Z = (k * x)[:, None, None], (k * x)[None, :, None], (k * x)[None, None, :]
    sX, cX, sY, cY, sZ, cZ = np.sin(X), np.cos(X), np.sin(Y), np.cos(Y), np.sin(Z), np.cos(Z)
    g = sX * cY + sY * cZ + sZ * cX
    grad = k * np.sqrt((cX * cY - sZ * sX) ** 2 + (cY * cZ - sX * sY) ** 2 + (cZ * cX - sY * sZ) ** 2)
    d = g / np.maximum(grad, np.float32(1e-3 * k))
    return np.pad(d, pad, mode="wrap"), n, a / n


def lattice_stats(a: float, w: float):
    """As-built local wall thickness and channel bottleneck of the periodic lattice.

    Uses the same distance field the mesh is built from (mesh vertices match it to
    +-0.016 mm, see audit). Wall thickness = 2 x distance-to-surface at medial-axis
    voxels. Bottleneck = largest sphere diameter that can still pass through a channel
    network (binary search on percolation of {2*dist >= D}). The two channel networks of
    a g = 0 sheet gyroid are congruent, so one is evaluated.
    """
    from scipy import ndimage as ndi

    px = max(0.04, a / 200)
    pad = int(np.ceil(0.45 * 0.42 * a / px)) + 4  # > largest channel radius
    d, n, sp = _distance_field_cell(a, px, pad)
    core = (slice(pad, pad + n),) * 3

    solid = np.abs(d) <= w / 2
    dt = ndi.distance_transform_edt(solid) * sp
    med = solid & (dt >= ndi.maximum_filter(dt, size=3) - 1e-9)
    t = 2 * dt[core][med[core]]
    del dt, med, solid

    void = d > w / 2
    dv = 2 * ndi.distance_transform_edt(void) * sp
    del d, void
    lo, hi = 0.0, float(dv.max())
    while hi - lo > 0.01:
        D = (lo + hi) / 2
        lab, _ = ndi.label(dv >= D)
        through = (set(np.unique(lab[0])) & set(np.unique(lab[-1]))) - {0}
        lo, hi = (D, hi) if through else (lo, D)
    return {
        "wall_min_mm": float(t.min()),
        "wall_p1_mm": float(np.percentile(t, 1)),
        "wall_p5_mm": float(np.percentile(t, 5)),
        "wall_median_mm": float(np.median(t)),
        "wall_max_mm": float(t.max()),
        "bottleneck_mm": lo,
        "stats_voxel_mm": sp,
    }


def measure(mesh: trimesh.Trimesh, L: float, w_target: float, rho_pla=1.24):
    """Geometric measurements taken directly from the mesh."""
    tol = 1e-3 * L
    tri = mesh.triangles  # (n,3,3)
    on_face = np.zeros(len(tri), dtype=bool)
    for ax in range(3):
        c = tri[:, :, ax]
        on_face |= np.all(np.abs(c) < tol, axis=1) | np.all(np.abs(c - L) < tol, axis=1)
    areas = mesh.area_faces
    A_total = float(areas.sum())
    A_wet = float(areas[~on_face].sum())  # internal fluid-contact surface (both networks)
    V_box = L ** 3
    V_s = float(mesh.volume)
    phi = V_s / V_box
    eps = 1 - phi
    Dh = 4 * (eps * V_box) / A_wet  # hydraulic diameter, mm

    # Overhang check (FDM, build direction +z): down-facing internal surface steeper
    # than 45 deg from vertical, excluding the bed contact face.
    nz = mesh.face_normals[:, 2]
    zmin = tri[:, :, 2].min(axis=1)
    not_bed = ~(np.all(np.abs(tri[:, :, 2]) < tol, axis=1))
    down45 = (nz < -np.cos(np.radians(45))) & not_bed
    down70 = (nz < -np.cos(np.radians(20))) & not_bed  # near-horizontal ceilings
    bed_area = float(areas[np.all(np.abs(tri[:, :, 2]) < tol, axis=1)].sum())

    return {
        "solid_volume_mm3": V_s,
        "box_volume_mm3": V_box,
        "solid_fraction": phi,
        "porosity": eps,
        "surface_area_total_mm2": A_total,
        "wetted_area_mm2": A_wet,
        "wall_area_one_side_mm2": A_wet / 2,
        "specific_surface_m2_per_m3": A_wet / V_box * 1e3,
        "hydraulic_diameter_mm": Dh,
        "mean_wall_thickness_mm": V_s / (A_wet / 2),
        "wall_thickness_target_mm": w_target,
        "pla_mass_g": V_s / 1000 * rho_pla,
        "overhang_gt45_area_frac": float(areas[down45].sum() / A_wet),
        "overhang_gt70_area_frac": float(areas[down70].sum() / A_wet),
        "bed_contact_area_mm2": bed_area,
        "triangles": int(len(mesh.faces)),
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "is_volume": bool(mesh.is_volume),
        "euler_number": int(mesh.euler_number),
    }
