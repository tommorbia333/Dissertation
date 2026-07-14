#!/usr/bin/env python3
"""01_extract_matrices.py — extract per-participant 8×8 pair-scaling matrices.

Reads the canonical human CSV via ``shared/loaders/human``, filters to the
selected run set (default: one canonical run per assignment_id), parses
``pair_scaling_summary.directed_matrix``, and writes one ``.npz`` per
(run_id, story_id, condition) under ``outputs/matrices/``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

TRACK_DIR = Path(__file__).resolve().parent
ANALYSIS_DIR = TRACK_DIR.parent
EXPERIMENT_ROOT = ANALYSIS_DIR.parent

if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from shared.loaders import human as human_loader  # noqa: E402
from shared.story_sets import ALL_8, HUMAN_POOL_6  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--config",
        type=Path,
        default=ANALYSIS_DIR / "configs" / "canonical_runs.yaml",
        help="Canonical paths config (used by the human loader)",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=TRACK_DIR / "outputs" / "matrices",
        help="Directory for extracted matrix artefacts",
    )
    p.add_argument(
        "--story-subset",
        choices=("human_pool_6", "all_8"),
        default="human_pool_6",
        help="Story filter (all_8 includes model-only domains if present in CSV)",
    )
    p.add_argument(
        "--selection",
        choices=("canonical", "all_complete"),
        default="canonical",
        help="Run selection: one per assignment_id (canonical) or all completes",
    )
    return p.parse_args()


def _parse_directed_matrix(raw: str | list | None) -> np.ndarray:
    if raw is None or raw == "":
        raise ValueError("empty directed_matrix")
    if isinstance(raw, str):
        data = json.loads(raw)
    else:
        data = raw
    arr = np.array(data, dtype=object)
    arr = np.where(arr == None, np.nan, arr).astype(float)  # noqa: E711
    if arr.shape != (8, 8):
        raise ValueError(f"expected 8×8 matrix, got {arr.shape}")
    return arr


def _safe_name(value: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in value)


def main() -> int:
    args = parse_args()
    _ = args.config  # loader resolves DEFAULT_CONFIG; flag kept for CLI parity

    story_set = HUMAN_POOL_6 if args.story_subset == "human_pool_6" else ALL_8
    story_allow = set(story_set)

    rows = human_loader.load_canonical_csv(
        root=EXPERIMENT_ROOT,
        selection=args.selection,  # type: ignore[arg-type]
        write_canonical_yaml=True,
    )

    summaries = [
        r for r in rows
        if r.get("task") == "pair_scaling_summary"
        and r.get("story_id") in story_allow
    ]

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # Clear previous extracts so re-runs do not leave stale selection artefacts.
    for old in out_dir.glob("*.npz"):
        old.unlink()

    written: list[dict] = []
    errors: list[str] = []
    for row in summaries:
        rid = str(row.get("run_id", ""))
        story_id = str(row.get("story_id", ""))
        condition = str(row.get("condition", ""))
        try:
            matrix = _parse_directed_matrix(row.get("directed_matrix"))
        except (ValueError, json.JSONDecodeError, TypeError) as exc:
            errors.append(f"run={rid} story={story_id}: {exc}")
            continue

        event_ids_raw = row.get("matrix_event_ids") or ""
        try:
            event_ids = json.loads(event_ids_raw) if isinstance(event_ids_raw, str) and event_ids_raw else event_ids_raw
        except json.JSONDecodeError:
            event_ids = None

        fname = (
            f"run{_safe_name(rid)}__{_safe_name(story_id)}__{_safe_name(condition)}.npz"
        )
        path = out_dir / fname
        np.savez_compressed(
            path,
            matrix=matrix,
            run_id=rid,
            story_id=story_id,
            condition=condition,
            assignment_id=str(row.get("assignment_id", "")),
            attn_correct=np.array(row.get("attn_correct"), dtype=object),
            matrix_event_ids=np.array(event_ids if event_ids is not None else [], dtype=object),
            selection=args.selection,
        )
        written.append(
            {
                "file": fname,
                "run_id": rid,
                "story_id": story_id,
                "condition": condition,
                "assignment_id": str(row.get("assignment_id", "")),
                "attn_correct": row.get("attn_correct"),
            }
        )

    manifest = {
        "selection": args.selection,
        "story_subset": args.story_subset,
        "n_matrices": len(written),
        "n_errors": len(errors),
        "errors": errors,
        "matrices": written,
    }
    with open(out_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(
        f"Wrote {len(written)} matrices to {out_dir} "
        f"(selection={args.selection}, stories={args.story_subset})"
    )
    if errors:
        print(f"  {len(errors)} parse errors:", file=sys.stderr)
        for msg in errors[:10]:
            print(f"    {msg}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
