#!/usr/bin/env python3
"""01_comprehension_accuracy.py — human comprehension accuracy summary.

Reads ``comprehension_summary`` rows (one per story-trial, fields
``n_correct`` / ``accuracy`` over the 6 yes/no/unsure items) from the
canonical human selection (one complete run per assignment slot; see
``shared/loaders/human.py``) and reports:

- overall accuracy
- accuracy by condition (linear / nonlinear / atemporal)
- accuracy by story
- accuracy by story x condition
- item-level accuracy (which of the 48 comprehension items are hardest),
  from ``comprehension_item`` rows
- a sensitivity split by the attention-check flag (``attn_correct``)

Comprehension accuracy gates re-entry to the block in the human arm, so this
also functions as a data-quality check: very low accuracy in a cell would
flag a stimulus or item problem.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

TRACK_DIR = Path(__file__).resolve().parent
ANALYSIS_DIR = TRACK_DIR.parent
EXPERIMENT_ROOT = ANALYSIS_DIR.parent

if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from shared.loaders import human as human_loader  # noqa: E402
from shared.story_sets import CONDITIONS, HUMAN_POOL_6  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--out-dir",
        type=Path,
        default=TRACK_DIR / "outputs",
    )
    p.add_argument(
        "--selection",
        choices=("canonical", "all_complete"),
        default="canonical",
    )
    return p.parse_args()


def _mean(vals: list[float]) -> float:
    arr = [float(v) for v in vals if v not in (None, "")]
    return float(np.mean(arr)) if arr else float("nan")


def _parse_bool(raw) -> bool | None:
    if raw is None or raw == "":
        return None
    s = str(raw).strip().lower()
    if s in ("true", "1", "yes"):
        return True
    if s in ("false", "0", "no"):
        return False
    return None


def main() -> int:
    args = parse_args()
    rows = human_loader.load_canonical_csv(
        root=EXPERIMENT_ROOT, selection=args.selection, write_canonical_yaml=False
    )

    summary_rows = [
        r for r in rows
        if r.get("task") == "comprehension_summary" and r.get("story_id") in HUMAN_POOL_6
    ]
    item_rows = [
        r for r in rows
        if r.get("task") == "comprehension_item" and r.get("story_id") in HUMAN_POOL_6
    ]

    for r in summary_rows:
        r["_accuracy"] = float(r["accuracy"]) if r.get("accuracy") not in (None, "") else float("nan")
        r["_attn"] = _parse_bool(r.get("attn_correct"))

    by_cond: dict[str, list] = defaultdict(list)
    by_story: dict[str, list] = defaultdict(list)
    by_cell: dict[tuple[str, str], list] = defaultdict(list)
    for r in summary_rows:
        by_cond[r["condition"]].append(r)
        by_story[r["story_id"]].append(r)
        by_cell[(r["story_id"], r["condition"])].append(r)

    def pack(recs: list[dict]) -> dict:
        return {
            "n": len(recs),
            "mean_accuracy": _mean([r["_accuracy"] for r in recs]),
        }

    flagged = [r for r in summary_rows if r["_attn"] is False]
    clean = [r for r in summary_rows if r["_attn"] is not False]

    # Item-level: which of the 48 items are hardest.
    item_stats: dict[str, list] = defaultdict(list)
    for r in item_rows:
        key = f"{r.get('story_id')}::{r.get('item_id')}"
        item_stats[key].append(1.0 if _parse_bool(r.get("is_correct")) else 0.0)
    item_accuracy = sorted(
        (
            {"item": k, "n": len(v), "accuracy": float(np.mean(v))}
            for k, v in item_stats.items()
        ),
        key=lambda d: d["accuracy"],
    )

    report = {
        "selection": args.selection,
        "n_story_trials": len(summary_rows),
        "n_items": len(item_rows),
        "overall": pack(summary_rows),
        "overall_excluding_attn_flagged": pack(clean),
        "n_attn_flagged_story_trials": len(flagged),
        "by_condition": {c: pack(by_cond[c]) for c in CONDITIONS if c in by_cond},
        "by_story": {s: pack(by_story[s]) for s in HUMAN_POOL_6 if s in by_story},
        "by_story_condition": {
            f"{sid}__{cond}": pack(by_cell[(sid, cond)])
            for sid in HUMAN_POOL_6
            for cond in CONDITIONS
            if (sid, cond) in by_cell
        },
        "hardest_items": item_accuracy[:10],
        "easiest_items": item_accuracy[-10:][::-1],
        "notes": [
            "accuracy is the per-story-trial fraction correct on the 6-item "
            "comprehension battery (3 compound, 2 single, 1 distractor).",
            "Comprehension gates re-entry to the block before ordering if "
            "accuracy is below threshold, so summary-row accuracy already "
            "reflects the participant's best completed attempt.",
        ],
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / "comprehension_accuracy.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Wrote {out_path}")
    o = report["overall"]
    print(f"  Overall (n={o['n']}): mean accuracy = {o['mean_accuracy']:.3f}")
    for c in CONDITIONS:
        cell = report["by_condition"].get(c)
        if cell:
            print(f"  {c:<10} (n={cell['n']:>3}): {cell['mean_accuracy']:.3f}")
    print(f"  attn-flagged story-trials excluded in sensitivity check: {len(flagged)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
