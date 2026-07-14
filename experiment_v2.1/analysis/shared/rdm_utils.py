"""Unified RDM helpers for human, model behavioural, and probing tracks.

Metric conventions
------------------
Second-order RSA distance (``model_arm/src/meta_rsa.py``, dissertation default):

    distance = 1 − Spearman ρ

computed on the **56 off-diagonal cells** of two 8×8 directed pair-scaling /
similarity matrices (diagonal excluded; upper and lower triangles both used).

This is scale-invariant and matches the JSON export in ``meta_rdms.json``.

First-order Mantel test (``model_arm/probing/probes.py``):

    r = Pearson ρ between off-diagonal vectors

used for hidden-state RDM vs author-graph alignment by layer. Probing extras
also report Spearman Mantel variants; see ``causal_rdm_extra``.

Both tracks flatten matrices via the same off-diagonal indexing order (row-major,
``i != j``).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy.stats import spearmanr


def matrix_to_offdiag_vec(matrix: NDArray | list | np.ndarray) -> NDArray:
    """Flatten an n×n matrix to its off-diagonal cells (n*(n−1) values).

    None / NaN cells are preserved as NaN. Index order: row-major with
    ``i != j`` (matches ``model_arm/probing/stimuli_probing.offdiag`` and
    ``model_arm/src/meta_rsa._matrix_to_vec``).
    """
    arr = np.array(matrix, dtype=object)
    arr = np.where(arr == None, np.nan, arr).astype(float)  # noqa: E711
    n = arr.shape[0]
    # Row-major i!=j — equivalent to ~eye boolean indexing on C-order arrays.
    return np.array([arr[i, j] for i in range(n) for j in range(n) if i != j], dtype=float)


def _as_offdiag_vec(x: NDArray) -> NDArray:
    x = np.asarray(x, dtype=float)
    if x.ndim == 2 and x.shape[0] == x.shape[1]:
        return matrix_to_offdiag_vec(x)
    if x.ndim == 1:
        return x
    raise ValueError(f"Expected square matrix or 1-d vector, got shape {x.shape}")


def mantel_r(a: NDArray, b: NDArray) -> float:
    """Pearson correlation between two off-diagonal vectors (probing Mantel).

    Expects ``a`` and ``b`` to already be off-diagonal vectors of equal length,
    or square matrices (will be flattened via ``matrix_to_offdiag_vec``).
    Returns NaN if fewer than two valid pairs.
    """
    va = _as_offdiag_vec(a)
    vb = _as_offdiag_vec(b)
    if va.shape != vb.shape:
        raise ValueError(f"Vector length mismatch: {va.shape} vs {vb.shape}")
    valid = ~(np.isnan(va) | np.isnan(vb))
    if valid.sum() < 2:
        return float("nan")
    r = np.corrcoef(va[valid], vb[valid])[0, 1]
    return float(r) if not np.isnan(r) else float("nan")


def spearman_distance_rdm(
    a: NDArray,
    b: NDArray,
    *,
    min_valid: int = 5,
) -> float:
    """Second-order RSA distance: 1 − Spearman ρ on off-diagonal cells.

    If ``a`` and ``b`` are square matrices they are flattened first. NaN-safe;
    returns NaN when fewer than ``min_valid`` overlapping non-NaN pairs remain.
    """
    va = _as_offdiag_vec(a)
    vb = _as_offdiag_vec(b)
    if va.shape != vb.shape:
        raise ValueError(f"Vector length mismatch: {va.shape} vs {vb.shape}")
    valid = ~(np.isnan(va) | np.isnan(vb))
    if int(valid.sum()) < min_valid:
        return float("nan")
    rho, _ = spearmanr(va[valid], vb[valid])
    if np.isnan(rho):
        return float("nan")
    return 1.0 - float(rho)
