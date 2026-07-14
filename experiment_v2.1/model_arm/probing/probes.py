"""
Linear-probe studies over the reading-pass vectors.

Three studies, each leave-one-story-out (LOSO) so accuracy reflects
generalisation to an unseen story, not memorisation:

  position_probe : decode chronological position 1..8 per layer (multiclass).
  pairwise_probe : decode before/after/concurrent per event pair, with a
                   label-scramble control, a class-balanced variant, and
                   confusion matrices.
  causal_rdm     : regress author causal strength per pair, rebuild a model RDM,
                   and Mantel-correlate it with the author graph per layer.
                   ``causal_rdm_extra`` adds the diagnostic metric panel.

Every function writes its figures/arrays into a given output directory and
returns the numeric results for programmatic use.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.metrics import confusion_matrix, roc_auc_score

from . import stimuli_probing as S

CONDITIONS = S.CONDITIONS
CLASSES = S.CLASSES
POSITION_CHANCE = 1.0 / S.N_EVENTS

_LABELS = {"linear": "A  linear", "nonlinear": "B  nonlinear", "atemporal": "C  atemporal"}
_COLOURS = {"linear": "C0", "nonlinear": "C1", "atemporal": "C2"}


def _mpl():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


# ===========================================================================
# Study 1: chronological position probe
# ===========================================================================

def _probe_position_condition(X_c, y_c, g_c) -> np.ndarray:
    n, n_layers, _ = X_c.shape
    logo = LeaveOneGroupOut()
    acc = np.zeros(n_layers)
    for layer in range(n_layers):
        Xl = X_c[:, layer, :]
        preds = np.empty(n, dtype=int)
        for tr, te in logo.split(Xl, y_c, g_c):
            clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000))
            clf.fit(Xl[tr], y_c[tr])
            preds[te] = clf.predict(Xl[te])
        acc[layer] = (preds == y_c).mean()
    return acc


def position_probe(X, y, g, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    acc = {c: _probe_position_condition(X[c], y[c], g[c]) for c in CONDITIONS}

    plt = _mpl()
    layers = np.arange(len(acc["linear"]))
    plt.figure(figsize=(8, 5))
    for c in CONDITIONS:
        plt.plot(layers, acc[c], marker="o", markersize=3, label=_LABELS[c], color=_COLOURS[c])
    plt.axhline(POSITION_CHANCE, ls="--", color="grey", label=f"chance ({POSITION_CHANCE:.3f})")
    plt.xlabel("layer (0 = embedding output)")
    plt.ylabel("leave-one-story-out accuracy")
    plt.title("Decoding chronological position from hidden states")
    plt.ylim(0, 1)
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(out_dir / "position_accuracy_by_layer.png", dpi=150)
    plt.close()

    np.savez(out_dir / "position_accuracy.npz", **{c: acc[c] for c in CONDITIONS})

    print(f"\n{'condition':<12}{'peak layer':>12}{'peak acc':>11}")
    for c in CONDITIONS:
        L = int(np.argmax(acc[c]))
        print(f"{c:<12}{L:>12}{acc[c][L]:>11.3f}")
    return acc


# ===========================================================================
# Study 2: pairwise before / after / concurrent probe
# ===========================================================================

def _new_probe():
    return make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))


def _balanced_probe():
    return make_pipeline(StandardScaler(),
                         LogisticRegression(max_iter=2000, class_weight="balanced"))


def _pairwise_curve(X_c, y_c, g_c, labels, g_to_key, probe_factory):
    pairs = S.pair_index(y_c, g_c)
    yp = S.pair_labels(pairs, labels, g_to_key)
    gp = S.pair_groups(pairs)
    n_layers = X_c.shape[1]
    logo = LeaveOneGroupOut()
    acc, conf = np.zeros(n_layers), np.zeros(n_layers)
    for layer in range(n_layers):
        Xp = S.pair_features_at_layer(pairs, X_c, layer)
        preds = np.empty(len(yp), dtype=object)
        pmax = np.zeros(len(yp))
        for tr, te in logo.split(Xp, yp, gp):
            clf = probe_factory()
            clf.fit(Xp[tr], yp[tr])
            preds[te] = clf.predict(Xp[te])
            pmax[te] = clf.predict_proba(Xp[te]).max(axis=1)
        acc[layer] = (preds == yp).mean()
        conf[layer] = pmax.mean()
    return acc, conf, yp


def _scramble(y_c, seed=42):
    rng = np.random.default_rng(seed)
    y2 = y_c.copy()
    rng.shuffle(y2)
    return y2


def _confusion_at_layer(X_c, y_c, g_c, labels, g_to_key, layer):
    pairs = S.pair_index(y_c, g_c)
    yp = S.pair_labels(pairs, labels, g_to_key)
    gp = S.pair_groups(pairs)
    Xp = S.pair_features_at_layer(pairs, X_c, layer)
    preds = np.empty(len(yp), dtype=object)
    for tr, te in LeaveOneGroupOut().split(Xp, yp, gp):
        clf = _new_probe()
        clf.fit(Xp[tr], yp[tr])
        preds[te] = clf.predict(Xp[te])
    return confusion_matrix(yp, preds, labels=list(CLASSES))


def pairwise_probe(X, y, g, labels, g_to_key, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)

    acc, conf, yp_ref = {}, {}, None
    for c in CONDITIONS:
        acc[c], conf[c], yp_ref = _pairwise_curve(X[c], y[c], g[c], labels, g_to_key, _new_probe)

    counts = {k: int((yp_ref == k).sum()) for k in CLASSES}
    baseline = max(counts.values()) / len(yp_ref)
    print("class counts:", counts)
    print(f"majority baseline: {baseline:.3f}")

    # scramble control
    acc_scramble = {}
    for c in CONDITIONS:
        acc_scramble[c], _, _ = _pairwise_curve(X[c], _scramble(y[c]), g[c],
                                                labels, g_to_key, _new_probe)

    # balanced probe (nonlinear only, concurrent upweighted)
    acc_balanced = {}
    acc_balanced["nonlinear"], _, _ = _pairwise_curve(
        X["nonlinear"], y["nonlinear"], g["nonlinear"], labels, g_to_key, _balanced_probe)

    print(f"\n{'condition':<12}{'peak layer':>12}{'peak acc':>11}{'conf@peak':>12}")
    for c in CONDITIONS:
        L = int(np.argmax(acc[c]))
        print(f"{c:<12}{L:>12}{acc[c][L]:>11.3f}{conf[c][L]:>12.3f}")

    # confusion matrices at each condition's peak layer
    for c in CONDITIONS:
        L = int(np.argmax(acc[c]))
        cm = _confusion_at_layer(X[c], y[c], g[c], labels, g_to_key, L)
        print(f"\nconfusion at layer {L} (rows=true, cols=pred), {c}:")
        print("           " + "".join(f"{cl:>12}" for cl in CLASSES))
        for name, row in zip(CLASSES, cm):
            print(f"{name:>11}" + "".join(f"{v:>12}" for v in row))

    _plot_pairwise(acc, baseline, out_dir / "pairwise_accuracy_by_layer.png",
                   acc_balanced=acc_balanced, acc_scramble=acc_scramble)

    np.savez(out_dir / "pairwise_accuracy.npz", baseline=baseline,
             **{f"acc_{c}": acc[c] for c in CONDITIONS},
             acc_balanced_nonlinear=acc_balanced["nonlinear"],
             **{f"acc_scramble_{c}": acc_scramble[c] for c in CONDITIONS})
    return {"acc": acc, "baseline": baseline,
            "acc_scramble": acc_scramble, "acc_balanced": acc_balanced}


def _plot_pairwise(acc, baseline, out, acc_balanced=None, acc_scramble=None):
    plt = _mpl()
    layers = np.arange(len(acc["linear"]))
    plt.figure(figsize=(8, 5))
    for c in CONDITIONS:
        plt.plot(layers, acc[c], marker="o", markersize=3, label=_LABELS[c], color=_COLOURS[c])
    if acc_balanced is not None:
        plt.plot(layers, acc_balanced["nonlinear"], ls="--", marker="s", markersize=3,
                 color="purple", label="B balanced (concurrent upweighted)")
    if acc_scramble is not None:
        for c in CONDITIONS:
            plt.plot(layers, acc_scramble[c], ls=":", marker="x", markersize=3,
                     color=_COLOURS[c], label=f"{_LABELS[c]} scrambled (control)")
    plt.axhline(baseline, ls="--", color="grey", label=f"majority baseline ({baseline:.3f})")
    plt.xlabel("layer (0 = embedding output)")
    plt.ylabel("leave-one-story-out accuracy")
    plt.title("Decoding pairwise temporal relation (before / after / concurrent)")
    plt.ylim(0, 1)
    plt.legend(fontsize=7)
    plt.tight_layout()
    plt.savefig(out, dpi=150)
    plt.close()


# ===========================================================================
# Study 3: causal RDM crystallisation (Mantel by layer)
# ===========================================================================

def _mantel_r(A, B):
    return np.corrcoef(S.offdiag(A), S.offdiag(B))[0, 1]


def _causal_condition(X_c, y_c, g_c, author, g_to_key):
    pairs = S.pair_index(y_c, g_c)
    t = S.causal_targets(pairs, author, g_to_key)
    gp = S.pair_groups(pairs)
    n_layers = X_c.shape[1]
    mant = np.zeros(n_layers)
    peak_rdms: dict = {}
    for L in range(n_layers):
        Xp = S.pair_features_at_layer(pairs, X_c, L)
        pred = np.zeros(len(t))
        for tr, te in LeaveOneGroupOut().split(Xp, t, gp):
            clf = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
            clf.fit(Xp[tr], t[tr])
            pred[te] = clf.predict(Xp[te])
        # BLAS on this design (few underlying vectors -> rank-deficient pair
        # matrix) can print spurious "encountered in matmul" RuntimeWarnings
        # (Apple Accelerate quirk); guard against a *real* numerical blow-up.
        assert np.isfinite(pred).all(), f"non-finite Ridge predictions at layer {L}"
        rs, layer_rdms = [], {}
        for s in np.unique(gp):
            M = np.zeros((S.N_EVENTS, S.N_EVENTS))
            for k in np.where(gp == s)[0]:
                _, a, b, i, j = pairs[k]
                M[i - 1, j - 1] = pred[k]
            layer_rdms[int(s)] = M
            rs.append(_mantel_r(M, author[g_to_key[int(s)]]))
        mant[L] = np.nanmean(rs)
        peak_rdms[L] = layer_rdms
    return mant, peak_rdms


def causal_rdm(X, y, g, author, g_to_key, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    mantel, rdms = {}, {}
    for c in CONDITIONS:
        mantel[c], rdms[c] = _causal_condition(X[c], y[c], g[c], author, g_to_key)

    print(f"\n{'condition':<12}{'peak layer':>12}{'peak Mantel r':>16}")
    for c in CONDITIONS:
        L = int(np.argmax(mantel[c]))
        print(f"{c:<12}{L:>12}{mantel[c][L]:>16.3f}")

    plt = _mpl()
    plt.figure(figsize=(8, 5))
    for c in CONDITIONS:
        plt.plot(range(len(mantel[c])), mantel[c], marker="o", markersize=3,
                 label=c, color=_COLOURS[c])
    plt.xlabel("layer (0 = embedding output)")
    plt.ylabel("Mantel r (model RDM vs author causal RDM)")
    plt.title("Causal RDM crystallisation by layer")
    plt.ylim(-0.1, 1)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_dir / "causal_mantel_by_layer.png", dpi=150)
    plt.close()

    story_ids = sorted(g_to_key)
    peak = {c: int(np.argmax(mantel[c])) for c in CONDITIONS}
    np.savez(out_dir / "causal_model_rdms.npz",
             author=np.stack([author[g_to_key[s]] for s in story_ids]),
             story_keys=np.array([g_to_key[s] for s in story_ids]),
             peak_layers=np.array([peak[c] for c in CONDITIONS]),
             **{f"model_{c}": np.stack([rdms[c][peak[c]][s] for s in story_ids])
                for c in CONDITIONS})
    return {"mantel": mantel, "peak_layers": peak}


# ===========================================================================
# Study 3b: diagnostic causal metrics (Spearman Mantel, edge AUC, geometric RDMs)
# ===========================================================================

def causal_rdm_extra(X, y, g, author, g_to_key, out_dir: Path) -> dict:
    """The 'is it the probe's fault?' diagnostic panel: Spearman Mantel, binary
    edge-detection AUC, and label-free symmetric/directed geometric RDMs."""
    from scipy.stats import spearmanr
    out_dir.mkdir(parents=True, exist_ok=True)
    plt = _mpl()

    nL = X["linear"].shape[1]
    story_ids = sorted(g_to_key)
    pairs = {c: S.pair_index(y[c], g[c]) for c in CONDITIONS}
    gp = {c: S.pair_groups(pairs[c]) for c in CONDITIONS}
    targ = {c: S.causal_targets(pairs[c], author, g_to_key) for c in CONDITIONS}

    def to_rdms(pc, pred):
        out = {}
        for s in np.unique([d for (d, a, b, i, j) in pc]):
            M = np.zeros((S.N_EVENTS, S.N_EVENTS))
            for k, (d, a, b, i, j) in enumerate(pc):
                if d == s:
                    M[i - 1, j - 1] = pred[k]
            out[int(s)] = M
        return out

    def loso_reg(Xc, pc, t, gpc, layer):
        Xp = S.pair_features_at_layer(pc, Xc, layer)
        pred = np.zeros(len(t))
        for tr, te in LeaveOneGroupOut().split(Xp, t, gpc):
            clf = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
            clf.fit(Xp[tr], t[tr])
            pred[te] = clf.predict(Xp[te])
        return pred

    # --- Spearman Mantel ---
    sp = {}
    for c in CONDITIONS:
        sp[c] = np.zeros(nL)
        for L in range(nL):
            r = to_rdms(pairs[c], loso_reg(X[c], pairs[c], targ[c], gp[c], L))
            sp[c][L] = np.nanmean([spearmanr(S.offdiag(r[s]), S.offdiag(author[g_to_key[s]])).correlation
                                   for s in story_ids])
    _line_plot(plt, sp, "Spearman Mantel r", "Causal RDM crystallisation (Spearman)",
               out_dir / "causal_mantel_spearman.png", ylim=(-0.1, 1))

    # --- Binary edge / no-edge, scored by AUC ---
    auc = {}
    for c in CONDITIONS:
        tb = (targ[c] > 0).astype(int)
        auc[c] = np.zeros(nL)
        for L in range(nL):
            Xp = S.pair_features_at_layer(pairs[c], X[c], L)
            prob = np.zeros(len(tb))
            for tr, te in LeaveOneGroupOut().split(Xp, tb, gp[c]):
                clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
                clf.fit(Xp[tr], tb[tr])
                prob[te] = clf.predict_proba(Xp[te])[:, 1]
            auc[c][L] = roc_auc_score(tb, prob)
    _line_plot(plt, auc, "edge-detection ROC-AUC", "Causal edge detection (binary, AUC)",
               out_dir / "causal_edge_auc.png", ylim=(0.4, 1), chance=0.5)

    # --- label-free geometric RDMs (symmetric 5a, directed 5b) ---
    tril = np.tril_indices(S.N_EVENTS, -1)
    offmask = ~np.eye(S.N_EVENTS, dtype=bool)

    def story_vectors(c, s, L):
        idx = np.where(g[c] == s)[0]
        idx = idx[np.argsort(y[c][idx])]
        return X[c][idx, L, :]

    def centered(H):
        return H - H.mean(0, keepdims=True)

    def sym_rdm(Hc):
        n = Hc / (np.linalg.norm(Hc, axis=1, keepdims=True) + 1e-8)
        return n @ n.T

    def dir_rdm(Hc):
        G = Hc @ Hc.T
        nrm2 = (Hc ** 2).sum(1)
        return G / (nrm2[:, None] + 1e-8)

    sym, dirc = {}, {}
    for c in CONDITIONS:
        sym[c], dirc[c] = np.zeros(nL), np.zeros(nL)
        for L in range(nL):
            rs_s, rs_d = [], []
            for s in story_ids:
                Hs = centered(story_vectors(c, s, L))
                Su = sym_rdm(Hs)
                Au = author[g_to_key[s]] + author[g_to_key[s]].T
                rs_s.append(spearmanr(Su[tril], Au[tril]).correlation)
                Ad = dir_rdm(Hs)
                rs_d.append(spearmanr(Ad[offmask], author[g_to_key[s]][offmask]).correlation)
            sym[c][L] = np.nanmean(rs_s)
            dirc[c][L] = np.nanmean(rs_d)
    _line_plot(plt, sym, "Spearman r (cosine RDM vs undirected graph)",
               "Option 5a: symmetric geometric RDM (label-free)",
               out_dir / "opt5a_symmetric.png", ylim=(-0.3, 1))
    _line_plot(plt, dirc, "Spearman r (directed RDM vs directed graph)",
               "Option 5b: directed projection RDM (label-free)",
               out_dir / "opt5b_directed.png", ylim=(-0.3, 1))

    np.savez(out_dir / "causal_extra_metrics.npz",
             **{f"spearman_{c}": sp[c] for c in CONDITIONS},
             **{f"auc_{c}": auc[c] for c in CONDITIONS},
             **{f"sym_{c}": sym[c] for c in CONDITIONS},
             **{f"dir_{c}": dirc[c] for c in CONDITIONS})
    return {"spearman": sp, "auc": auc, "sym": sym, "dir": dirc}


def _line_plot(plt, curves, ylabel, title, out, ylim, chance=None):
    plt.figure(figsize=(8, 5))
    for c in CONDITIONS:
        plt.plot(range(len(curves[c])), curves[c], marker="o", markersize=3,
                 label=c, color=_COLOURS[c])
    if chance is not None:
        plt.axhline(chance, ls="--", color="grey", label=f"chance ({chance})")
    else:
        plt.axhline(0, color="grey", lw=0.8)
    plt.xlabel("layer")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.ylim(*ylim)
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(out, dpi=150)
    plt.close()
