"""
Render orthographic views of the STL files (front, side, top, isometric) with a simple
z-buffer rasteriser over the real mesh triangles, so see-through openings show the white
background exactly where a line of sight passes through the part. Also writes annotated
opening maps, mid-plane sections and slicer layer previews.

Outputs: results/3x3/views/*.png
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).parent))
from openings import voxelize_field  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results" / "3x3"
VIEWS = RES / "views"
VIEWS.mkdir(parents=True, exist_ok=True)
L = 40.0

CAMERAS = {  # name: (viewing direction into the scene, up vector, label)
    "front": ((0, 1, 0), (0, 0, 1), "Front (looking along +Y)"),
    "side": ((-1, 0, 0), (0, 0, 1), "Side (looking along -X)"),
    "top": ((0, 0, -1), (0, 1, 0), "Top (looking along -Z)"),
    "iso": ((-1, 1, -0.8), (0, 0, 1), "Isometric"),
}


def render(mesh, direction, up, res=900, span=46.0):
    f = np.asarray(direction, float); f /= np.linalg.norm(f)
    r = np.cross(f, up); r /= np.linalg.norm(r)
    u = np.cross(r, f)
    c = mesh.bounds.mean(0)
    V = mesh.vertices - c
    P = np.c_[V @ r, V @ u]                 # image plane (mm)
    D = V @ f                               # depth (larger = farther)
    F = mesh.faces
    n = mesh.face_normals
    vis = n @ f < 0                         # back-face culling (closed mesh)
    F, n = F[vis], n[vis]
    light = -f + 0.6 * u + 0.4 * r; light /= np.linalg.norm(light)
    shade = 0.28 + 0.72 * np.clip(n @ light, 0, 1)

    s = res / span
    pix = (P + span / 2) * s                # pixel coords, x right, y up
    zbuf = np.full(res * res, np.inf)
    ibuf = np.full(res * res, -1)
    tri = pix[F]; dep = D[F]
    lo = np.floor(tri.min(1)).astype(int); hi = np.ceil(tri.max(1)).astype(int)
    lo = np.clip(lo, 0, res - 1); hi = np.clip(hi, 0, res - 1)
    wh = (hi - lo + 1)
    cnt = wh[:, 0] * wh[:, 1]
    order = np.arange(len(F))
    for chunk in np.array_split(order, max(1, int(cnt.sum() // 8_000_000) + 1)):
        cc = cnt[chunk]
        t = np.repeat(chunk, cc)
        k = np.arange(cc.sum()) - np.repeat(np.cumsum(cc) - cc, cc)
        px_ = lo[t, 0] + k % wh[t, 0]
        py_ = lo[t, 1] + k // wh[t, 0]
        qx, qy = px_ + 0.5, py_ + 0.5
        a, b, cpt = tri[t, 0], tri[t, 1], tri[t, 2]
        det = (b[:, 0] - a[:, 0]) * (cpt[:, 1] - a[:, 1]) - (cpt[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1])
        ok = np.abs(det) > 1e-12
        det = np.where(ok, det, 1)
        w1 = ((qx - a[:, 0]) * (cpt[:, 1] - a[:, 1]) - (cpt[:, 0] - a[:, 0]) * (qy - a[:, 1])) / det
        w2 = ((b[:, 0] - a[:, 0]) * (qy - a[:, 1]) - (qx - a[:, 0]) * (b[:, 1] - a[:, 1])) / det
        w0 = 1 - w1 - w2
        inside = ok & (w0 >= -1e-9) & (w1 >= -1e-9) & (w2 >= -1e-9)
        t, px_, py_ = t[inside], px_[inside], py_[inside]
        z = (w0[inside] * dep[t, 0] + w1[inside] * dep[t, 1] + w2[inside] * dep[t, 2])
        idx = py_ * res + px_
        np.minimum.at(zbuf, idx, z)
        win = z <= zbuf[idx] + 1e-9
        ibuf[idx[win]] = t[win]
    img = np.ones((res * res, 3))
    hit = ibuf >= 0
    base = np.array([0.62, 0.70, 0.80])
    img[hit] = shade[ibuf[hit], None] * base
    return img.reshape(res, res, 3)[::-1], span  # flip so +up is up


def axis_view_extent(span):
    return [-span / 2 + L / 2, span / 2 + L / 2, -span / 2 + L / 2, span / 2 + L / 2]


def main():
    val = json.loads((RES / "validation.json").read_text())
    new = trimesh.load(ROOT / "stl" / "gyroid_3x3_40mm.stl", force="mesh")
    new_r = new.simplify_quadric_decimation(face_count=250_000)
    imgs = {}
    for name, (d, up, label) in CAMERAS.items():
        img, span = render(new_r, d, up, span=74.0 if name == "iso" else 46.0)
        imgs[name] = (img, span, label)
        plt.imsave(VIEWS / f"view_{name}.png", img)

    # 2 x 2 composite
    fig, axs = plt.subplots(2, 2, figsize=(10, 10))
    for ax, name in zip(axs.flat, CAMERAS):
        img, span, label = imgs[name]
        ext = axis_view_extent(span) if name != "iso" else None
        ax.imshow(img, extent=ext)
        ax.set_title(label, fontsize=11)
        if name == "iso":
            ax.axis("off")
        else:
            ax.set_xlabel({"front": "x [mm]", "side": "y [mm]", "top": "x [mm]"}[name])
            ax.set_ylabel({"front": "z [mm]", "side": "z [mm]", "top": "y [mm]"}[name])
    fig.suptitle("Gyroid 3x3 openings, 40 x 40 x 40 mm, a = 26.67 mm, wall 1.6 mm (rendered from the STL)")
    fig.tight_layout()
    fig.savefig(VIEWS / "views_composite.png", dpi=130)
    plt.close(fig)

    # annotated axis views: number every see-through opening using the measured centres
    fig, axs = plt.subplots(1, 3, figsize=(15, 5.4))
    for ax, (name, axis) in zip(axs, [("front", "y"), ("side", "x"), ("top", "z")]):
        img, span, label = imgs[name]
        ax.imshow(img, extent=axis_view_extent(span))
        st = val["see_through"][axis]
        full = [h for h in val["see_through_detail"][axis] if not h["edge_cut"]]
        for i, h in enumerate(sorted(full, key=lambda h: (-round(h["centre_mm"][1]), h["centre_mm"][0])), 1):
            u, v = h["centre_mm"]
            ax.add_patch(plt.Circle((u, v), h["clear_diameter_mm"] / 2, fill=False, ec="crimson", lw=1.4))
            ax.text(u, v, str(i), color="crimson", ha="center", va="center", fontsize=9, weight="bold")
        ax.set_title(f"{label}\n{st['full']} see-through openings ({st['grid_cols_rows'][0]} x {st['grid_cols_rows'][1]}), "
                     f"{st['edge_cut']} edge-cut, min clear Ø {st['min_clear_diameter_mm']:.2f} mm", fontsize=9.5)
        ax.set_xlim(-2, 42); ax.set_ylim(-2, 42)
    fig.tight_layout()
    fig.savefig(VIEWS / "openings_annotated.png", dpi=130)
    plt.close(fig)

    # before / after (same renderer, same scale)
    fig, axs = plt.subplots(1, 3, figsize=(15, 5.4))
    for ax, (f, title) in zip(axs, [("gyroid_final_test_article", "Original print file (test article)\na = 8 mm, w = 0.9 mm, 1.25 mm side walls"),
                                    ("gyroid_final_core", "Original lattice without side walls\na = 8 mm, w = 0.9 mm"),
                                    ("gyroid_3x3_40mm", "Revised: a = 26.67 mm, w = 1.6 mm, shift a/8\n3 openings per axis")]):
        mo = trimesh.load(ROOT / "stl" / f"{f}.stl", force="mesh").simplify_quadric_decimation(face_count=250_000)
        img, span = render(mo, CAMERAS["front"][0], CAMERAS["front"][1])
        ax.imshow(img, extent=axis_view_extent(span)); ax.set_title(title, fontsize=10)
        ax.set_xlabel("x [mm]"); ax.set_ylabel("z [mm]")
    fig.suptitle("Front views (looking along +Y): white = line of sight through the part")
    fig.tight_layout()
    fig.savefig(VIEWS / "before_after_front.png", dpi=130)
    plt.close(fig)

    # mid-plane sections of the design field
    p = val["parameters"]
    vol = voxelize_field(L, p["period_mm"], p["wall_nominal_mm"], p["shift_mm"], px=0.1)
    fig, axs = plt.subplots(1, 3, figsize=(15, 5))
    mid = vol.shape[0] // 2
    for ax, (sl, title, xl, yl) in zip(axs, [(vol[mid], "z = 20 mm section", "x", "y"),
                                             (vol[:, mid, :], "y = 20 mm section", "x", "z"),
                                             (vol[:, :, mid], "x = 20 mm section", "y", "z")]):
        ax.imshow(sl, origin="lower", cmap="Greys", extent=[0, L, 0, L])
        ax.set_title(title); ax.set_xlabel(f"{xl} [mm]"); ax.set_ylabel(f"{yl} [mm]")
    fig.suptitle("Mid-plane sections (solid = dark): continuous sheet, two interlocked channel networks")
    fig.tight_layout()
    fig.savefig(VIEWS / "sections_mid.png", dpi=130)
    plt.close(fig)

    # slicer layer previews (from the G-code toolpaths), if the slicer check has been run
    sl_dir = RES / "slicer"
    cases = [("new_supports_off", "Revised\nsupports OFF"),
             ("new_supports_everywhere", "Revised\nsupports everywhere"),
             ("original_supports_everywhere", "Original\nsupports everywhere")]
    if all((sl_dir / f"{c}_layers.npz").exists() for c, _ in cases):
        zs = [0.2, 6.6, 13.4, 20.0, 26.6, 33.4]
        fig, axs = plt.subplots(len(cases), len(zs), figsize=(16, 8.4))
        for row, (c, title) in enumerate(cases):
            d = np.load(sl_dir / f"{c}_layers.npz")
            model, sup = d["model"], d["support"]
            for col, z in enumerate(zs):
                k = int(round(z / 0.2)) - 1
                rgb = np.ones(model.shape[1:] + (3,))
                rgb[model[k]] = [0.25, 0.35, 0.55]
                rgb[sup[k]] = [0.95, 0.45, 0.1]
                ax = axs[row, col]
                ax.imshow(rgb, origin="lower", extent=[-0.5, 40.5, -0.5, 40.5])
                ax.set_xticks([]); ax.set_yticks([])
                if row == 0:
                    ax.set_title(f"layer z = {z:.1f} mm", fontsize=9)
                if col == 0:
                    ax.set_ylabel(title, fontsize=8.5)
        fig.suptitle("PrusaSlicer 2.9.6 toolpaths rebuilt from G-code (blue = model, orange = support)")
        fig.tight_layout()
        fig.savefig(VIEWS / "slicer_layers.png", dpi=120)
        plt.close(fig)
    print("views written to", VIEWS)


if __name__ == "__main__":
    main()
