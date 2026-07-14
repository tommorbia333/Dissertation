#!/usr/bin/env python3
"""02_aggregate_rdms.py — aggregate participant matrices to group-level RDMs.

Loads per-participant ``.npz`` matrices from ``01_extract_matrices``, averages
across participants within each (story_id, condition) cell, and writes a
stacked ``human_rdms.npz`` (plus a JSON summary) for downstream RSA / cross-arm
comparison.
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np

TRACK_DIR = Path(__file__).resolve().parent
ANALYSIS_DIR = TRACK_DIR.parent

if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from shared.story_sets import CONDITIONS, HUMAN_POOL_6  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--in-dir",
        type=Path,
        default=TRACK_DIR / "outputs" / "matrices",
        help="Input from 01_extract_matrices",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=TRACK_DIR / "outputs" / "aggregated",
        help="Aggregated RDM output directory",
    )
    p.add_argument(
        "--reducer",
        choices=("mean", "median"),
        default="mean",
        help="How to aggregate participant matrices within a cell",
    )
    return p.parse_args()


def _load_participant_matrices(in_dir: Path) -> list[dict]:
    entries: list[dict] = []
    for path in sorted(in_dir.glob("run*.npz")):
        with np.load(path, allow_pickle=True) as z:
            entries.append(
                {
                    "path": path.name,
                    "matrix": z["matrix"].astype(float),
                    "run_id": str(z["run_id"]),
                    "story_id": str(z["story_id"]),
                    "condition": str(z["condition"]),
                    "assignment_id": str(z["assignment_id"]) if "assignment_id" in z.files else "",
                }
            )
    return entries


def main() -> int:
    args = parse_args()
    if not args.in_dir.is_dir():
        print(f"Input directory not found: {args.in_dir}", file=sys.stderr)
        return 1

    entries = _load_participant_matrices(args.in_dir)
    if not entries:
        print(f"No participant matrices found in {args.in_dir}", file=sys.stderr)
        return 1

    by_cell: dict[tuple[str, str], list[np.ndarray]] = defaultdict(list)
    run_ids_by_cell: dict[tuple[str, str], list[str]] = defaultdict(list)
    for e in entries:
        key = (e["story_id"], e["condition"])
        by_cell[key].append(e["matrix"])
        run_ids_by_cell[key].append(e["run_id"])

    story_ids = [s for s in HUMAN_POOL_6 if any(s == sid for sid, _ in by_cell)]
    # Keep any unexpected stories after the pool order (should be empty for human data).
    extras = sorted({sid for sid, _ in by_cell if sid not in story_ids})
    story_ids = list(story_ids) + extras

    reducer = np.nanmean if args.reducer == "mean" else np.nanmedian
    payload: dict = {
        "story_keys": np.array(story_ids, dtype=object),
        "conditions": np.array(list(CONDITIONS), dtype=object),
        "reducer": args.reducer,
        "n_participant_matrices": len(entries),
    }
    cell_summary: list[dict] = []

    for cond in CONDITIONS:
        stacked = []
        counts = []
        for sid in story_ids:
            mats = by_cell.get((sid, cond), [])
            if mats:
                # Diagonal cells are NaN by design → nanmean emits "Mean of empty slice".
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", category=RuntimeWarning)
                    agg = reducer(np.stack(mats, axis=0), axis=0)
                stacked.append(agg)
                counts.append(len(mats))
                cell_summary.append(
                    {
                        "story_id": sid,
                        "condition": cond,
                        "n_participants": len(mats),
                        "run_ids": sorted(run_ids_by_cell[(sid, cond)], key=lambda x: int(x) if x.isdigit() else x),
                    }
                )
            else:
                stacked.append(np.full((8, 8), np.nan))
                counts.append(0)
        payload[f"human_{cond}"] = np.stack(stacked, axis=0)
        payload[f"n_participants_{cond}"] = np.array(counts, dtype=int)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    npz_path = args.out_dir / "human_rdms.npz"
    np.savez_compressed(npz_path, **payload)

    summary = {
        "reducer": args.reducer,
        "n_participant_matrices": len(entries),
        "n_story_keys": len(story_ids),
        "story_keys": story_ids,
        "conditions": list(CONDITIONS),
        "cells": cell_summary,
        "artefact": str(npz_path.relative_to(TRACK_DIR) if npz_path.is_relative_to(TRACK_DIR) else npz_path),
    }
    with open(args.out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    n_filled = sum(1 for c in cell_summary if c["n_participants"] > 0)
    print(
        f"Aggregated {len(entries)} matrices → {n_filled} filled "
        f"(story × condition) cells in {npz_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
