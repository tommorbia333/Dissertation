"""
Representation-geometry / cyclicity analysis.

A parameter-free geometric readout of the same reading-pass vectors, per
(condition, layer), asking two questions about the 8-event cloud per story:

  Meaning 2 (axis test): is the dominant organising axis temporal? Measured as
            |Spearman| between each event's PC1 projection and its chronological
            position.
  Meaning 3 (arc-vs-ring test): does the geometry trace an OPEN arc (sequential)
            or a CLOSED ring (timeline wrapping)? Measured as how much better a
            chronological ring fits the top-2 PC layout than a straight line.

Both are computed under cosine and euclidean geometries, with a label-permutation
null (the geometry is held fixed; only the position labels are shuffled), matching
the Mantel logic used elsewhere.

Produces cyclicity_by_layer.png, cyclicity.npz and event_planes_{euclidean,cosine}.png.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from . import stimuli_probing as S

CONDITIONS = list(S.CONDITIONS)
N_EVENTS = S.N_EVENTS
N_PERM = 1000
RNG = np.random.default_rng(0)


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _prep(points, metric):
    P = np.asarray(points, dtype=np.float64)
    if metric == "cosine":
        norms = np.linalg.norm(P, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        P = P / norms
    return P


def _pca_scores(P, n_components=2):
    Pc = P - P.mean(axis=0, keepdims=True)
    _, _, Vt = np.linalg.svd(Pc, full_matrices=False)
    k = min(n_components, Vt.shape[0])
    return Pc @ Vt[:k].T


def _best_line_residual(xy):
    proj = _pca_scores(xy, n_components=1)
    recon = proj @ np.linalg.svd(xy - xy.mean(0), full_matrices=False)[2][:1]
    recon = recon + xy.mean(0)
    resid = xy - recon
    total = ((xy - xy.mean(0)) ** 2).sum()
    return (resid ** 2).sum() / total if total > 0 else 0.0


def _best_circle_residual(xy, positions):
    x, y = xy[:, 0], xy[:, 1]
    A = np.column_stack([2 * x, 2 * y, np.ones_like(x)])
    bvec = x ** 2 + y ** 2
    sol, *_ = np.linalg.lstsq(A, bvec, rcond=None)
    a, b, c = sol
    cx, cy = a, b
    r = np.sqrt(max(c + a ** 2 + b ** 2, 1e-12))
    ang = np.arctan2(y - cy, x - cx)
    order = np.argsort(positions)
    ideal = np.zeros(N_EVENTS)
    ideal[order] = np.linspace(0, 2 * np.pi, N_EVENTS, endpoint=False)
    offset = np.angle(np.exp(1j * (ang - ideal)).mean())
    ideal_aligned = ideal + offset
    ex = cx + r * np.cos(ideal_aligned)
    ey = cy + r * np.sin(ideal_aligned)
    resid = (x - ex) ** 2 + (y - ey) ** 2
    total = ((xy - xy.mean(0)) ** 2).sum()
    return resid.sum() / total if total > 0 else 0.0


def ring_advantage(points, positions, metric):
    xy = _pca_scores(_prep(points, metric), n_components=2)
    return _best_line_residual(xy) - _best_circle_residual(xy, positions)


# ---------------------------------------------------------------------------
# Observed value + permutation null (geometry computed once per story)
# ---------------------------------------------------------------------------

def _perm_positions(pos, n_perm):
    idx = np.argsort(RNG.random((n_perm, pos.shape[0])), axis=1)
    return pos[idx]


def _corr_rows(a_centered, B):
    B = np.atleast_2d(B).astype(np.float64)
    Bc = B - B.mean(axis=1, keepdims=True)
    num = Bc @ a_centered
    den = np.sqrt((Bc ** 2).sum(axis=1) * (a_centered ** 2).sum())
    den[den == 0] = 1.0
    return num / den


def _pc1_obs_null(X_layer, y, g, metric, n_perm):
    from scipy.stats import rankdata
    sids = np.unique(g)
    null_acc = np.zeros(n_perm)
    obs_vals = []
    for sid in sids:
        rows = np.where(g == sid)[0]
        pts = X_layer[rows]
        pos = y[rows].astype(np.float64)
        scores = _pca_scores(_prep(pts, metric), n_components=1)[:, 0]
        rs = rankdata(scores)
        rs_c = rs - rs.mean()
        obs_vals.append(abs(_corr_rows(rs_c, pos[None, :])[0]))
        P = _perm_positions(pos, n_perm)
        null_acc += np.abs(_corr_rows(rs_c, P))
    return float(np.mean(obs_vals)), null_acc / len(sids)


def _ring_resids(Pmat, base, ang, cx, cy, r, x, yc, total):
    Pmat = np.atleast_2d(Pmat).astype(int)
    ideal = base[Pmat - 1]
    diff = ang[None, :] - ideal
    offset = np.angle(np.exp(1j * diff).mean(axis=1))
    ideal_al = ideal + offset[:, None]
    ex = cx + r * np.cos(ideal_al)
    ey = cy + r * np.sin(ideal_al)
    resid = ((x[None, :] - ex) ** 2 + (yc[None, :] - ey) ** 2).sum(axis=1)
    return resid / total if total > 0 else np.zeros(Pmat.shape[0])


def _ring_obs_null(X_layer, y, g, metric, n_perm):
    sids = np.unique(g)
    null_acc = np.zeros(n_perm)
    obs_vals = []
    base = np.linspace(0, 2 * np.pi, N_EVENTS, endpoint=False)
    for sid in sids:
        rows = np.where(g == sid)[0]
        pts = X_layer[rows]
        pos = y[rows].astype(np.float64)
        xy = _pca_scores(_prep(pts, metric), n_components=2)
        line_r = _best_line_residual(xy)
        x, yc = xy[:, 0], xy[:, 1]
        A = np.column_stack([2 * x, 2 * yc, np.ones_like(x)])
        sol, *_ = np.linalg.lstsq(A, x ** 2 + yc ** 2, rcond=None)
        a, b, c = sol
        cx, cy = a, b
        r = np.sqrt(max(c + a ** 2 + b ** 2, 1e-12))
        ang = np.arctan2(yc - cy, x - cx)
        total = ((xy - xy.mean(0)) ** 2).sum()
        ring_obs = _ring_resids(pos[None, :], base, ang, cx, cy, r, x, yc, total)[0]
        obs_vals.append(line_r - ring_obs)
        P = _perm_positions(pos, n_perm)
        ring_null = _ring_resids(P, base, ang, cx, cy, r, x, yc, total)
        null_acc += (line_r - ring_null)
    return float(np.mean(obs_vals)), null_acc / len(sids)


def analyse(X, y, g, n_perm=N_PERM):
    metrics = ["cosine", "euclidean"]
    obs_null = {"pc1_axis": _pc1_obs_null, "ring_adv": _ring_obs_null}
    n_layers = next(iter(X.values())).shape[1]
    out: dict = {}
    for metric in metrics:
        out[metric] = {}
        for sname, fn in obs_null.items():
            out[metric][sname] = {}
            for c in CONDITIONS:
                obs = np.empty(n_layers)
                pval = np.empty(n_layers)
                nullm = np.empty(n_layers)
                for L in range(n_layers):
                    o, null = fn(X[c][:, L, :], y[c], g[c], metric, n_perm)
                    obs[L] = o
                    pval[L] = (1 + np.sum(null >= o)) / (1 + n_perm)
                    nullm[L] = null.mean()
                out[metric][sname][c] = {"value": obs, "p": pval, "null_mean": nullm}
    return out


# ---------------------------------------------------------------------------
# Reporting / plots
# ---------------------------------------------------------------------------

def summary(results):
    for metric in results:
        print(f"\n================  geometry: {metric}  ================")
        for sname, label in [("pc1_axis", "PC1 is temporal (Meaning 2)"),
                             ("ring_adv", "ring beats line (Meaning 3)")]:
            print(f"\n  {label}")
            for c in CONDITIONS:
                d = results[metric][sname][c]
                peak = int(np.argmax(d["value"]))
                print(f"    {c:10s} peak layer {peak:2d}  value {d['value'][peak]:+.3f}  "
                      f"(null {d['null_mean'][peak]:+.3f}, p {d['p'][peak]:.3f})")


def plot_results(results, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    metrics = list(results.keys())
    fig, axes = plt.subplots(2, len(metrics), figsize=(6 * len(metrics), 9), squeeze=False)
    rows = [("pc1_axis", "PC1-position |Spearman|  (Meaning 2)"),
            ("ring_adv", "ring advantage  (Meaning 3)")]
    colours = {"linear": "C0", "nonlinear": "C1", "atemporal": "C2"}
    for j, metric in enumerate(metrics):
        for i, (sname, title) in enumerate(rows):
            ax = axes[i][j]
            for c in CONDITIONS:
                d = results[metric][sname][c]
                ax.plot(d["value"], label=c, color=colours[c])
                ax.plot(d["null_mean"], color=colours[c], ls=":", alpha=0.5)
            ax.set_title(f"{metric}\n{title}", fontsize=9)
            ax.set_xlabel("layer")
            ax.set_ylabel(sname)
            if i == 0 and j == 0:
                ax.legend(fontsize=8)
            ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def plot_event_planes(X, y, g, g_to_key, layer=None, metric="euclidean", out=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import cm

    n_layers = next(iter(X.values())).shape[1]
    L = (n_layers - 1) if layer is None else layer
    story_ids = np.unique(next(iter(g.values())))
    n_stories = len(story_ids)
    story_names = [g_to_key.get(int(s), f"story {int(s)}") for s in story_ids]

    ink = "#2b2b2b"
    path_grey = "#b8b8b8"
    cmap = cm.get_cmap("viridis")
    fig, axes = plt.subplots(len(CONDITIONS), n_stories,
                             figsize=(2.05 * n_stories, 2.25 * len(CONDITIONS)),
                             squeeze=False)
    for ri, cond in enumerate(CONDITIONS):
        for ci, sid in enumerate(story_ids):
            ax = axes[ri][ci]
            rows = np.where(g[cond] == sid)[0]
            pts = X[cond][rows][:, L, :]
            pos = y[cond][rows]
            xy = _pca_scores(_prep(pts, metric), n_components=2)
            order = np.argsort(pos)
            path = xy[order]
            ax.plot(path[:, 0], path[:, 1], "-", color=path_grey, lw=1.2, zorder=1)
            ax.plot([path[-1, 0], path[0, 0]], [path[-1, 1], path[0, 1]],
                    "--", color=path_grey, lw=1.0, alpha=0.7, zorder=1)
            for k, idx in enumerate(order):
                frac = k / (len(order) - 1)
                ax.scatter(xy[idx, 0], xy[idx, 1], s=150, color=cmap(frac),
                           edgecolor=ink, linewidth=0.6, zorder=3)
                ax.text(xy[idx, 0], xy[idx, 1], str(int(pos[idx])),
                        ha="center", va="center", fontsize=7, color="white",
                        zorder=4, fontweight="bold")
            adv = ring_advantage(pts, pos, metric)
            ax.text(0.04, 0.95, f"ring adv {adv:+.2f}", transform=ax.transAxes,
                    fontsize=7, va="top", ha="left", color=ink, alpha=0.8)
            ax.set_aspect("equal", adjustable="datalim")
            ax.set_xticks([]); ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_edgecolor("#dddddd")
            if ri == 0:
                ax.set_title(story_names[ci], fontsize=8, color=ink, pad=6)
            if ci == 0:
                ax.set_ylabel(cond, fontsize=10, color=ink, labelpad=8)
    fig.suptitle(f"Per-story event geometry (PC1-PC2, {metric}, layer {L})",
                 fontsize=10, color=ink, y=1.0)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)


def run_geometry(X, y, g, g_to_key, out_dir: Path, n_perm=N_PERM) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    results = analyse(X, y, g, n_perm=n_perm)
    summary(results)
    plot_results(results, out_dir / "cyclicity_by_layer.png")

    flat = {}
    for metric in results:
        for sname in results[metric]:
            for c in CONDITIONS:
                for field, arr in results[metric][sname][c].items():
                    flat[f"{metric}__{sname}__{c}__{field}"] = arr
    np.savez(out_dir / "cyclicity.npz", **flat)

    plot_event_planes(X, y, g, g_to_key, metric="euclidean",
                      out=out_dir / "event_planes_euclidean.png")
    plot_event_planes(X, y, g, g_to_key, metric="cosine",
                      out=out_dir / "event_planes_cosine.png")
    return results
