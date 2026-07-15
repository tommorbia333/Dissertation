"""
Prompted behavioural + hidden-state run (the three-arm study).

For every ordered event pair the model is asked, in-context, to rate on a 0..N
scale how much the first event caused/contributed to the second. Two things are
recorded from the same forward pass:

  behavioural : the answer, as an expectation over the digit-token probabilities
                at the final position (a soft, calibrated read of the rating).
  prompted    : the hidden state at the final token, at every layer.

These are then compared, per story, against the author causal graph alongside
the reading-pass hidden state (arm 3), giving three "arms":

    behavioural (answers)  |  prompted state  |  reading state

This module is the bridge to the human data: humans do the same directed pair-
rating task, so the model's behavioural RDM and the human RDM are directly
Mantel-comparable. Per-story RDMs for all arms are saved to ``rdms/`` in a
canonical layout so a later human-vs-model comparison is a straight load-and-correlate.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.stats import spearmanr
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import LeaveOneGroupOut

from . import stimuli_probing as S
from . import extract as E

CONDITIONS = S.CONDITIONS
N = S.N_EVENTS


# ---------------------------------------------------------------------------
# Prompting
# ---------------------------------------------------------------------------

def digit_ids(tok, kmax: int) -> dict[int, list[int]]:
    ids = {}
    for k in range(kmax + 1):
        cand = set()
        for form in (str(k), " " + str(k)):
            t = tok.encode(form, add_special_tokens=False)
            if t:
                cand.add(t[-1])
        ids[k] = list(cand)
    return ids


def make_prompt(events, i, j, scale_max: int) -> str:
    story = "\n\n".join(t for _, t in events)
    ti = next(t for p, t in events if p == i)
    tj = next(t for p, t in events if p == j)
    return (f"{story}\n\nOn a scale of 0 to {scale_max}, how much did the first event "
            f"cause or contribute to the second event?\nFirst event: {ti}\n"
            f"Second event: {tj}\nAnswer with a single number from 0 to {scale_max}: ")


def answer_and_state(model, tok, device, prompt, dids, scale_max):
    import torch
    with torch.no_grad():
        enc = tok(prompt, return_tensors="pt").to(device)
        out = model(**enc, output_hidden_states=True)
    probs = torch.softmax(out.logits[0, -1].float(), dim=-1)
    ks = np.array(list(dids.keys()))
    ps = np.array([probs[dids[k]].sum().item() for k in ks])
    ps = ps / ps.sum() if ps.sum() > 0 else np.ones_like(ps) / len(ps)
    ans = float((ks * ps).sum())
    state = np.stack([hs[0, -1].float().cpu().numpy() for hs in out.hidden_states])
    # Compute is bf16 (fp32-range) but pstate is stored fp16 to keep the
    # per-layer, per-pair archive small. A genuine massive activation can exceed
    # the fp16 ceiling (65504) and would become +/-inf on downcast, re-poisoning
    # the very probes this whole change fixes; clamp to the fp16 finite range
    # first. These dims are near-constant across pairs and get standardised out
    # by the probe ridge, so clamping is benign.
    finfo = np.finfo(np.float16)
    state = np.clip(state, finfo.min, finfo.max)
    return ans, state.astype(np.float16)


def run_behavioural(tok, model, device, data: dict, g_to_key: dict,
                    out_path: Path, scale_max: int = 6):
    """Prompt every ordered pair; save answers + prompted states to out_path."""
    key_to_id = {k: i for i, k in g_to_key.items()}
    dids = digit_ids(tok, scale_max)

    beh = {}
    for c in CONDITIONS:
        story_ids, ii, jj, ans_list, states = [], [], [], [], []
        for domain, conds in data.items():
            key = S.normalize_key(domain)
            if key not in key_to_id:
                continue
            events = conds[c]
            s = key_to_id[key]
            for i in range(1, N + 1):
                for j in range(1, N + 1):
                    if i == j:
                        continue
                    a, st = answer_and_state(model, tok, device,
                                             make_prompt(events, i, j, scale_max),
                                             dids, scale_max)
                    story_ids.append(s); ii.append(i); jj.append(j)
                    ans_list.append(a); states.append(st)
            print(f"  prompted {domain:<22} {c}")
        beh[c] = dict(story=np.array(story_ids), i=np.array(ii), j=np.array(jj),
                      ans=np.array(ans_list), pstate=np.stack(states).astype(np.float16))

    np.savez_compressed(
        out_path,
        story_keys=np.array([g_to_key[i] for i in sorted(g_to_key)]),
        scale_max=scale_max,
        **{f"story_{c}": beh[c]["story"] for c in CONDITIONS},
        **{f"i_{c}": beh[c]["i"] for c in CONDITIONS},
        **{f"j_{c}": beh[c]["j"] for c in CONDITIONS},
        **{f"ans_{c}": beh[c]["ans"] for c in CONDITIONS},
        **{f"pstate_{c}": beh[c]["pstate"] for c in CONDITIONS})
    print(f"saved {out_path}")
    return beh


# ---------------------------------------------------------------------------
# Three-arm analysis
# ---------------------------------------------------------------------------

def analyse_three_arms(behav_path: Path, vectors_path: Path, author, g_to_key,
                       out_dir: Path, rep_layer: int = 20):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    rdm_dir = out_dir / "rdms"
    rdm_dir.mkdir(exist_ok=True)

    off = ~np.eye(N, dtype=bool)
    tril = np.tril_indices(N, -1)

    b = np.load(behav_path, allow_pickle=True)
    Xc, yc, gc, _, _ = E.load_vectors(vectors_path)
    REP = min(rep_layer, Xc["linear"].shape[1] - 1)
    story_ids = sorted(g_to_key)

    def beh_rdm(c, s):
        m = b[f"story_{c}"] == s
        M = np.zeros((N, N))
        for i, j, v in zip(b[f"i_{c}"][m], b[f"j_{c}"][m], b[f"ans_{c}"][m]):
            M[i - 1, j - 1] = v
        return M

    def prompted_pred(c):
        X = b[f"pstate_{c}"][:, REP, :].astype(np.float32)
        story = b[f"story_{c}"]
        t = np.array([author[g_to_key[d]][i - 1, j - 1]
                      for d, i, j in zip(story, b[f"i_{c}"], b[f"j_{c}"])])
        pred = np.zeros(len(t))
        for tr, te in LeaveOneGroupOut().split(X, t, story):
            clf = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
            clf.fit(X[tr], t[tr])
            pred[te] = clf.predict(X[te])
        out = {}
        for s in story_ids:
            m = story == s
            M = np.zeros((N, N))
            for i, j, v in zip(b[f"i_{c}"][m], b[f"j_{c}"][m], pred[m]):
                M[i - 1, j - 1] = v
            out[s] = M
        return out

    def reading_rdm(c, s):
        idx = np.where(gc[c] == s)[0]
        idx = idx[np.argsort(yc[c][idx])]
        H = Xc[c][idx, REP, :]
        H = H - H.mean(0)
        n = H / (np.linalg.norm(H, axis=1, keepdims=True) + 1e-8)
        return n @ n.T

    prom = {c: prompted_pred(c) for c in CONDITIONS}

    def rdm(arm, c, s):
        return {"author": author[g_to_key[s]], "behavioural": beh_rdm(c, s),
                "prompted": prom[c][s], "reading": reading_rdm(c, s)}[arm]

    def mant(arm, c, s):
        A = author[g_to_key[s]]
        M = rdm(arm, c, s)
        if arm == "author":
            return 1.0
        if arm == "reading":
            return spearmanr(M[tril], (A + A.T)[tril]).correlation
        return spearmanr(M[off], A[off]).correlation

    ARMS = ["author", "behavioural", "prompted", "reading"]
    mtab = {arm: {c: np.nanmean([mant(arm, c, s) for s in story_ids]) for c in CONDITIONS}
            for arm in ARMS}

    # Figure 1: story-averaged RDMs (rows = arm, cols = condition)
    fig, ax = plt.subplots(len(ARMS), len(CONDITIONS), figsize=(11, 13), squeeze=False)
    for r, arm in enumerate(ARMS):
        for cc, c in enumerate(CONDITIONS):
            M = np.mean([rdm(arm, c, s) for s in story_ids], axis=0)
            ax[r][cc].imshow(M, cmap="viridis")
            ax[r][cc].set_xticks([]); ax[r][cc].set_yticks([])
            ttl = "author" if arm == "author" else f"{arm} / {c}"
            ax[r][cc].set_title(f"{ttl}\nr\u0304={mtab[arm][c]:.2f}", fontsize=8)
    fig.suptitle("Story-averaged RDMs (rows = arm, cols = condition)")
    fig.tight_layout()
    fig.savefig(out_dir / "analysis_summary_rdms.png", dpi=130)
    plt.close(fig)

    # Figures 2..: per-story RDMs, one per condition
    for c in CONDITIONS:
        fig, ax = plt.subplots(len(story_ids), len(ARMS),
                               figsize=(9, 2.1 * len(story_ids)), squeeze=False)
        for si, s in enumerate(story_ids):
            for k, arm in enumerate(ARMS):
                ax[si][k].imshow(rdm(arm, c, s), cmap="viridis")
                ax[si][k].set_xticks([]); ax[si][k].set_yticks([])
                lab = "author" if arm == "author" else f"{arm} r={mant(arm, c, s):.2f}"
                ax[si][k].set_title(lab, fontsize=7)
            ax[si][0].set_ylabel(S.TOPOLOGY.get(g_to_key[s], g_to_key[s]), fontsize=7)
        fig.suptitle(f"Per-story RDMs \u2014 {c}")
        fig.tight_layout()
        fig.savefig(out_dir / f"analysis_perstory_{c}.png", dpi=110)
        plt.close(fig)

    # Figure: three-arm per-story bars (per condition)
    for c in CONDITIONS:
        order = sorted(story_ids, key=lambda s: S.TOPOLOGY.get(g_to_key[s], g_to_key[s]))
        labels = [S.TOPOLOGY.get(g_to_key[s], g_to_key[s]) for s in order]
        x = np.arange(len(order))
        plt.figure(figsize=(11, 5))
        plt.bar(x - 0.25, [mant("behavioural", c, s) for s in order], 0.25, label="behavioural")
        plt.bar(x + 0.00, [mant("prompted", c, s) for s in order], 0.25, label="prompted state")
        plt.bar(x + 0.25, [mant("reading", c, s) for s in order], 0.25, label="reading state")
        plt.axhline(0, color="grey", lw=0.8)
        plt.xticks(x, labels, rotation=30, ha="right")
        plt.ylabel("per-story Mantel r vs author")
        plt.title(f"Per-story causal alignment by arm ({c})")
        plt.legend(); plt.tight_layout()
        plt.savefig(out_dir / f"per_story_three_arms_{c}.png", dpi=150)
        plt.close()

    # Canonical per-story RDMs for later human comparison + a mantel summary.
    payload = {"story_keys": np.array([g_to_key[s] for s in story_ids]),
               "rep_layer": REP}
    for c in CONDITIONS:
        payload[f"author_{c}"] = np.stack([author[g_to_key[s]] for s in story_ids])
        payload[f"behavioural_{c}"] = np.stack([beh_rdm(c, s) for s in story_ids])
        payload[f"prompted_{c}"] = np.stack([prom[c][s] for s in story_ids])
        payload[f"reading_{c}"] = np.stack([reading_rdm(c, s) for s in story_ids])
    np.savez_compressed(rdm_dir / "model_rdms_for_human.npz", **payload)

    import json
    (rdm_dir / "mantel_summary.json").write_text(json.dumps(
        {arm: {c: float(mtab[arm][c]) for c in CONDITIONS} for arm in ARMS}, indent=2))

    print("\nmean per-story Mantel r (rows=arm, cols=condition):")
    print(f"{'arm':<12}" + "".join(f"{c:>12}" for c in CONDITIONS))
    for arm in ARMS[1:]:
        print(f"{arm:<12}" + "".join(f"{mtab[arm][c]:>12.3f}" for c in CONDITIONS))
    return mtab


# ---------------------------------------------------------------------------
# Prompted-state causal RDM crystallisation (layer sweep)
# ---------------------------------------------------------------------------
#
# ``analyse_three_arms`` above evaluates the prompted arm at a single,
# hard-coded ``rep_layer`` (default 20 for every model regardless of depth) so
# it can be plotted next to reading/behavioural in one apples-to-apples figure.
# That leaves a real gap: unlike the reading arm (which gets a full per-layer
# "crystallisation" sweep via ``probes.causal_rdm``/``causal_rdm_extra``), the
# prompted arm's causal decodability across depth was never characterised —
# even though ``pstate_{c}`` already stores the hidden state at *every* layer.
# This fills that gap using data already saved in ``behavioural.npz`` (no
# model reload / re-generation required).

def _ridge_loso_predict(X: np.ndarray, y: np.ndarray, groups: np.ndarray,
                        alpha: float = 1.0) -> np.ndarray:
    """Leave-one-group-out ridge regression via the closed-form dual solve.

    Mathematically identical to ``LeaveOneGroupOut`` + ``StandardScaler`` +
    ``sklearn.linear_model.Ridge`` (same standardisation, same intercept
    handling, same alpha) -- verified to match to ~1e-16. sklearn's default
    solver selection hit a severe (minutes-per-fit, not seconds) performance
    pathology on this hidden-size scale (n ~= 390 rows, p up to ~4000
    features) under this machine's Accelerate BLAS backend; solving the n x n
    Gram system directly with ``numpy.linalg.solve`` avoids whatever slow
    path that triggers and is ~1000x faster here.
    """
    pred = np.zeros(len(y), dtype=np.float64)
    for grp in np.unique(groups):
        te = groups == grp
        tr = ~te
        mu, sd = X[tr].mean(0), X[tr].std(0)
        sd = np.where(sd < 1e-8, 1e-8, sd)
        Xtr, Xte = (X[tr] - mu) / sd, (X[te] - mu) / sd
        y_mean = y[tr].mean()
        n = Xtr.shape[0]
        K = Xtr @ Xtr.T
        sol = np.linalg.solve(K + alpha * np.eye(n), y[tr] - y_mean)
        w = Xtr.T @ sol
        pred[te] = Xte @ w + y_mean
    return pred


def prompted_causal_mantel_by_layer(behav_path: Path, author, g_to_key,
                                    out_dir: Path,
                                    reading_spearman: dict | None = None) -> dict:
    """LOSO-Ridge decode causal strength from the prompted hidden state at
    every layer, Mantel-correlate the resulting model RDM against the author
    graph, and plot the crystallisation curve — the prompted-arm counterpart
    to ``probes.causal_rdm``'s reading-arm curve.

    Metric matches the *Spearman* Mantel used for ``prompted`` elsewhere
    (``analyse_three_arms.mant`` and ``probes.causal_rdm_extra``'s
    ``spearman`` panel): off-diagonal, directed, no symmetrisation.

    ``reading_spearman``, if given, is the ``{condition: array}`` curve from
    ``probes.causal_rdm_extra`` (same metric, reading features) — overlaid on
    the same axes so the two extraction methods are directly comparable
    layer-by-layer, not just at one fixed layer.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    b = np.load(behav_path, allow_pickle=True)
    story_ids = sorted(g_to_key)
    off = ~np.eye(N, dtype=bool)

    mant, peak_rdms = {}, {}
    for c in CONDITIONS:
        story = b[f"story_{c}"]
        ii, jj = b[f"i_{c}"], b[f"j_{c}"]
        pstate = b[f"pstate_{c}"].astype(np.float32)
        t = np.array([author[g_to_key[d]][i - 1, j - 1] for d, i, j in zip(story, ii, jj)])
        n_layers = pstate.shape[1]
        m = np.zeros(n_layers)
        layer_rdms: dict = {}
        for L in range(n_layers):
            X = pstate[:, L, :]
            pred = _ridge_loso_predict(X, t, story, alpha=1.0)
            rs, rdms_L = [], {}
            for s in story_ids:
                sel = story == s
                M = np.zeros((N, N))
                for i, j, v in zip(ii[sel], jj[sel], pred[sel]):
                    M[i - 1, j - 1] = v
                rdms_L[s] = M
                rs.append(spearmanr(M[off], author[g_to_key[s]][off]).correlation)
            m[L] = np.nanmean(rs)
            layer_rdms[L] = rdms_L
        mant[c] = m
        peak_rdms[c] = layer_rdms

    # Layer 0 (raw token embedding) is degenerate here: the prompt's final
    # token is identical across every pair, so the "hidden state" carries no
    # pair-specific information and the resulting RDM has zero variance ->
    # undefined (NaN) Spearman correlation. Use nan-aware peak detection so
    # that one structurally-NaN layer doesn't poison argmax (which otherwise
    # treats NaN as the max) for every downstream layer that has real signal.
    def _nanargmax(arr):
        return int(np.nanargmax(arr)) if np.isfinite(arr).any() else 0

    print(f"\n{'condition':<12}{'peak layer':>12}{'peak Mantel r':>16}")
    for c in CONDITIONS:
        L = _nanargmax(mant[c])
        print(f"{c:<12}{L:>12}{mant[c][L]:>16.3f}")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colours = {"linear": "C0", "nonlinear": "C1", "atemporal": "C2"}

    plt.figure(figsize=(8, 5))
    for c in CONDITIONS:
        plt.plot(range(len(mant[c])), mant[c], marker="o", markersize=3,
                 label=f"{c} (prompted)", color=colours[c])
        if reading_spearman is not None and c in reading_spearman:
            plt.plot(range(len(reading_spearman[c])), reading_spearman[c], ls="--",
                     marker="x", markersize=3, color=colours[c], label=f"{c} (reading)")
    plt.axhline(0, color="grey", lw=0.8)
    plt.xlabel("layer (0 = embedding output)")
    plt.ylabel("Spearman Mantel r (model RDM vs author causal RDM)")
    title = "Prompted-state causal RDM crystallisation by layer"
    if reading_spearman is not None:
        title += "\n(dashed = reading arm, same metric)"
    plt.title(title)
    plt.ylim(-0.3, 1)
    plt.legend(fontsize=7)
    plt.tight_layout()
    plt.savefig(out_dir / "prompted_causal_mantel_by_layer.png", dpi=150)
    plt.close()

    peak = {c: _nanargmax(mant[c]) for c in CONDITIONS}
    np.savez(out_dir / "prompted_causal_by_layer.npz",
             story_keys=np.array([g_to_key[s] for s in story_ids]),
             peak_layers=np.array([peak[c] for c in CONDITIONS]),
             **{f"mantel_{c}": mant[c] for c in CONDITIONS},
             **{f"model_{c}": np.stack([peak_rdms[c][peak[c]][s] for s in story_ids])
                for c in CONDITIONS})
    return {"mantel": mant, "peak_layers": peak}
