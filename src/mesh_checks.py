"""
Mesh-quality checks used as build acceptance criteria and in verify_outputs.py.

- defects():            zero-area faces, open/non-manifold edges, edge-triangle self-intersections
- mesh_wall_thickness(): local wall thickness measured on the MESH itself (scanline
                         voxelisation of horizontal slices + 3D distance transform)

The self-intersection test was validated in the audit on two overlapping boxes (hits found)
and a clean icosphere (none found).
"""
import numpy as np
import trimesh
from scipy import ndimage as ndi
from trimesh.grouping import group_rows

ZERO_AREA_MM2 = 1e-9


def self_intersections(m: trimesh.Trimesh, cell=0.5, eps=1e-7) -> int:
    """Count mesh edges that pierce the interior of a non-adjacent triangle."""
    V, F, E = m.vertices, m.faces, m.edges_unique

    def cells(lo, hi):
        a = np.floor(lo / cell).astype(np.int64)
        n = np.floor(hi / cell).astype(np.int64) - a + 1
        tot = n.prod(1)
        idx = np.repeat(np.arange(len(lo)), tot)
        off = np.arange(tot.sum()) - np.repeat(np.cumsum(tot) - tot, tot)
        nn = np.repeat(n, tot, axis=0)
        c = np.repeat(a, tot, axis=0) + np.stack(
            [off % nn[:, 0], (off // nn[:, 0]) % nn[:, 1], off // (nn[:, 0] * nn[:, 1])], 1)
        return (c[:, 0] + 1000) * 4_000_000 + (c[:, 1] + 1000) * 2000 + (c[:, 2] + 1000), idx

    T, S = V[F], V[E]
    kt, it = cells(T.min(1), T.max(1))
    ke, ie = cells(S.min(1), S.max(1))
    o = np.argsort(kt)
    kt, it = kt[o], it[o]
    uk, start, count = np.unique(kt, return_index=True, return_counts=True)
    pos = np.clip(np.searchsorted(uk, ke), 0, len(uk) - 1)
    hit = uk[pos] == ke
    ie, pos = ie[hit], pos[hit]
    cnt = count[pos]
    pe = np.repeat(ie, cnt)
    pt = it[np.repeat(start[pos], cnt) + np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt)]
    pairs = np.unique(pe.astype(np.int64) * 10_000_000 + pt)
    pe, pt = pairs // 10_000_000, pairs % 10_000_000
    fe = F[pt]
    share = (fe == E[pe, 0][:, None]).any(1) | (fe == E[pe, 1][:, None]).any(1)
    pe, pt = pe[~share], pt[~share]

    n_hits = 0
    for s in range(0, len(pe), 2_000_000):  # Moller-Trumbore, segment version
        a, b = pe[s:s + 2_000_000], pt[s:s + 2_000_000]
        O = V[E[a, 0]]
        D = V[E[a, 1]] - O
        v0 = V[F[b, 0]]
        e1, e2 = V[F[b, 1]] - v0, V[F[b, 2]] - v0
        P = np.cross(D, e2)
        det = (e1 * P).sum(1)
        ok = np.abs(det) > 1e-12
        inv = np.where(ok, 1 / np.where(ok, det, 1), 0)
        Tv = O - v0
        u = (Tv * P).sum(1) * inv
        Q = np.cross(Tv, e1)
        v = (D * Q).sum(1) * inv
        t = (e2 * Q).sum(1) * inv
        n_hits += int((ok & (u > eps) & (v > eps) & (u + v < 1 - eps) & (t > eps) & (t < 1 - eps)).sum())
    return n_hits


def defects(m: trimesh.Trimesh) -> dict:
    uses = np.array([len(g) for g in group_rows(m.edges_sorted, require_count=None)])
    return {
        "zero_area_faces": int((m.area_faces < ZERO_AREA_MM2).sum()),
        "open_edges": int((uses == 1).sum()),
        "non_manifold_edges": int((uses > 2).sum()),
        "self_intersections": self_intersections(m),
    }


def defect_free(d: dict) -> bool:
    return all(v == 0 for v in d.values())


# --- wall thickness measured on the mesh -------------------------------------------------

def _slice(T, z):
    zs = T[:, :, 2]
    t = T[(zs.min(1) < z) & (zs.max(1) > z)]
    s = t[:, :, 2] > z
    lone = np.where(s.sum(1) == 1, np.argmax(s, 1), np.argmax(~s, 1))
    r = np.arange(len(t))
    a, b, c = t[r, lone], t[r, (lone + 1) % 3], t[r, (lone + 2) % 3]
    p = a + (b - a) * ((z - a[:, 2]) / (b[:, 2] - a[:, 2]))[:, None]
    q = a + (c - a) * ((z - a[:, 2]) / (c[:, 2] - a[:, 2]))[:, None]
    return p[:, :2], q[:, :2]


def _fill(p, q, O, N, px):
    """Even-odd scanline fill of a closed slice outline onto an N x N pixel grid."""
    y1, y2, x1, x2 = p[:, 1], q[:, 1], p[:, 0], q[:, 0]
    jlo = np.ceil((np.minimum(y1, y2) - O) / px - 0.5).astype(int)
    cnt = np.ceil((np.maximum(y1, y2) - O) / px - 0.5).astype(int) - jlo
    k = cnt > 0
    y1, y2, x1, x2, jlo, cnt = y1[k], y2[k], x1[k], x2[k], jlo[k], cnt[k]
    r = np.repeat(np.arange(len(cnt)), cnt)
    j = jlo[r] + np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt)
    x = x1[r] + (O + (j + 0.5) * px - y1[r]) * (x2[r] - x1[r]) / (y2[r] - y1[r])
    o = np.lexsort((x, j))
    j, x = j[o], x[o]
    keep = (np.bincount(j, minlength=N)[j] % 2) == 0
    j, x = j[keep], x[keep]
    c0 = np.clip(np.ceil((x[0::2] - O) / px - 0.5).astype(int), 0, N)
    c1 = np.clip(np.ceil((x[1::2] - O) / px - 0.5).astype(int), 0, N)
    d = np.zeros((N, N + 1), np.int32)
    np.add.at(d, (j[0::2], c0), 1)
    np.add.at(d, (j[0::2], c1), -1)
    return np.cumsum(d, 1)[:, :N] > 0


def mesh_wall_thickness(m: trimesh.Trimesh, lo: float, hi: float, L=40.0, px=0.05) -> np.ndarray:
    """Local wall thickness (mm) at medial voxels inside the cube window [lo, hi]^3.
    Calibration in the audit: a tilted 0.8 mm plate reads 0.806 mm at px = 0.05."""
    O, N = -0.2, int(np.ceil((L + 0.4) / px))
    c = O + (np.arange(N) + 0.5) * px
    ix = np.nonzero((c >= lo - 1.0) & (c <= hi + 1.0))[0]  # 1 mm margin, cropped below
    T = m.triangles
    vol = np.zeros((len(ix),) * 3, bool)
    for k, z in enumerate(c[ix]):
        if 0 < z < L:
            vol[k] = _fill(*_slice(T, z), O, N, px)[np.ix_(ix, ix)]
    dt = ndi.distance_transform_edt(vol) * px
    med = vol & (dt >= ndi.maximum_filter(dt, size=3) - 1e-9)
    cc = c[ix]
    inside = (cc >= lo) & (cc <= hi)
    med &= inside[:, None, None] & inside[None, :, None] & inside[None, None, :]
    return 2 * dt[med]
