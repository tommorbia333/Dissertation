#!/usr/bin/env python3
"""03_second_order_rsa.py — inter-story and inter-condition second-order RSA.

Computes meta-RDMs from aggregated human pair-scaling matrices using
1 − Spearman ρ on 56 off-diagonal cells (``shared/rdm_utils.py``), mirroring
the views in ``model_arm/src/meta_rsa.py``:

- inter_story: story × story RDM within each condition
- inter_condition: condition × condition RDM within each story
- meta: all filled (story, condition) cells vs each other
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

TRACK_DIR = Path(__file__).resolve().parent
ANALYSIS_DIR = TRACK_DIR.parent

if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from shared.rdm_utils import matrix_to_offdiag_vec, spearman_distance_rdm  # noqa: E402
from shared.story_sets import CONDITIONS  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--in-dir",
        type=Path,
        default=TRACK_DIR / "outputs" / "aggregated",
        help="Input from 02_aggregate_rdms",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=TRACK_DIR / "outputs" / "second_order",
        help="Second-order RSA output directory",
    )
    return p.parse_args()


def _pairwise_distance_rdm(vecs: list[np.ndarray]) -> np.ndarray:
    n = len(vecs)
    rdm = np.full((n, n), np.nan)
    for i in range(n):
        rdm[i, i] = 0.0
        for j in range(i + 1, n):
            d = spearman_distance_rdm(vecs[i], vecs[j])
            rdm[i, j] = d
            rdm[j, i] = d
    return rdm


def _load_aggregated(in_dir: Path) -> tuple[list[str], dict[str, np.ndarray]]:
    path = in_dir / "human_rdms.npz"
    if not path.exists():
        raise FileNotFoundError(f"Missing aggregated artefact: {path}")
    with np.load(path, allow_pickle=True) as z:
        story_keys = [str(s) for s in z["story_keys"]]
        by_cond = {c: z[f"human_{c}"].astype(float) for c in CONDITIONS if f"human_{c}" in z.files}
    return story_keys, by_cond


def main() -> int:
    args = parse_args()
    try:
        story_keys, by_cond = _load_aggregated(args.in_dir)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    # --- inter-story (per condition) -----------------------------------------
    inter_story: dict[str, dict] = {}
    inter_story_arrays: dict[str, np.ndarray] = {}
    for cond, stack in by_cond.items():
        keep_idx = [i for i, sid in enumerate(story_keys) if not np.all(np.isnan(stack[i]))]
        keep = [story_keys[i] for i in keep_idx]
        vecs = [matrix_to_offdiag_vec(stack[i]) for i in keep_idx]
        rdm = _pairwise_distance_rdm(vecs) if vecs else np.zeros((0, 0))
        inter_story[cond] = {
            "labels": keep,
            "rdm": rdm.tolist(),
            "mean_offdiag_distance": float(np.nanmean(rdm[np.triu_indices(len(keep), k=1)]))
            if len(keep) > 1
            else float("nan"),
        }
        inter_story_arrays[cond] = rdm

    # --- inter-condition (per story) -----------------------------------------
    inter_condition: dict[str, dict] = {}
    inter_condition_arrays: dict[str, np.ndarray] = {}
    for si, sid in enumerate(story_keys):
        keep = []
        vecs = []
        for cond in CONDITIONS:
            if cond not in by_cond:
                continue
            mat = by_cond[cond][si]
            if np.all(np.isnan(mat)):
                continue
            keep.append(cond)
            vecs.append(matrix_to_offdiag_vec(mat))
        rdm = _pairwise_distance_rdm(vecs) if vecs else np.zeros((0, 0))
        inter_condition[sid] = {
            "labels": keep,
            "rdm": rdm.tolist(),
            "mean_offdiag_distance": float(np.nanmean(rdm[np.triu_indices(len(keep), k=1)]))
            if len(keep) > 1
            else float("nan"),
        }
        inter_condition_arrays[sid] = rdm

    # --- meta: all filled (story, condition) cells ---------------------------
    meta_labels: list[list[str]] = []
    meta_vecs: list[np.ndarray] = []
    for cond in CONDITIONS:
        if cond not in by_cond:
            continue
        for si, sid in enumerate(story_keys):
            mat = by_cond[cond][si]
            if np.all(np.isnan(mat)):
                continue
            meta_labels.append([sid, cond])
            meta_vecs.append(matrix_to_offdiag_vec(mat))
    meta_rdm = _pairwise_distance_rdm(meta_vecs) if meta_vecs else np.zeros((0, 0))

    args.out_dir.mkdir(parents=True, exist_ok=True)

    npz_payload: dict = {
        "meta_rdm": meta_rdm,
        "meta_labels": np.array(meta_labels, dtype=object),
    }
    for cond, rdm in inter_story_arrays.items():
        npz_payload[f"inter_story_{cond}"] = rdm
        npz_payload[f"inter_story_{cond}_labels"] = np.array(
            inter_story[cond]["labels"], dtype=object
        )
    for sid, rdm in inter_condition_arrays.items():
        safe = sid.replace("/", "_")
        npz_payload[f"inter_condition_{safe}"] = rdm
        npz_payload[f"inter_condition_{safe}_labels"] = np.array(
            inter_condition[sid]["labels"], dtype=object
        )
    np.savez_compressed(args.out_dir / "second_order_rdms.npz", **npz_payload)

    report = {
        "metric": "1 - Spearman rho on 56 off-diagonal cells",
        "n_meta_cells": len(meta_labels),
        "inter_story": {
            cond: {
                "labels": v["labels"],
                "mean_offdiag_distance": v["mean_offdiag_distance"],
                "rdm": v["rdm"],
            }
            for cond, v in inter_story.items()
        },
        "inter_condition": {
            sid: {
                "labels": v["labels"],
                "mean_offdiag_distance": v["mean_offdiag_distance"],
                "rdm": v["rdm"],
            }
            for sid, v in inter_condition.items()
        },
        "meta": {
            "labels": meta_labels,
            "mean_offdiag_distance": float(
                np.nanmean(meta_rdm[np.triu_indices(len(meta_labels), k=1)])
            )
            if len(meta_labels) > 1
            else float("nan"),
            "rdm": meta_rdm.tolist(),
        },
    }
    with open(args.out_dir / "second_order_rsa.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Wrote second-order RSA artefacts to {args.out_dir}")
    for cond, v in inter_story.items():
        print(
            f"  inter_story[{cond}]: n={len(v['labels'])} "
            f"mean_d={v['mean_offdiag_distance']:.3f}"
        )
    print(f"  meta cells: {len(meta_labels)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
