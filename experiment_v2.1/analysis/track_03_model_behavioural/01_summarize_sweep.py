#!/usr/bin/env python3
"""01_summarize_sweep.py — dissertation-ready summary of the model behavioural sweep.

Reads every completed trial in the canonical sweep
(``sweep_20260524_120056_main_run_v5_prompt_2``) and reports, per model:

- comprehension accuracy (overall / by condition / by story)
- pair-scaling quality vs the author gold graph (Pearson r, directional
  accuracy, edge F1), overall and by condition
- second-order geometry (inter-story / inter-condition mean distances),
  taken from the precomputed ``parsed/meta_rdms.json``

Ordering metrics are already covered by ``analysis/track_ordering/``; this
track focuses on comprehension + pair-scaling geometry, which is what
``compare_pair_scaling_to_human.py`` (track 05) and ``three_way_summary.py``
consume.
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

from shared.loaders import model_behavioural as mb  # noqa: E402
from shared.story_sets import CONDITIONS  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out-dir", type=Path, default=TRACK_DIR / "outputs")
    return p.parse_args()


def _mean(vals: list[float]) -> float:
    arr = [float(v) for v in vals if v is not None and not (isinstance(v, float) and np.isnan(v))]
    return float(np.mean(arr)) if arr else float("nan")


def _rate(vals: list[bool]) -> float:
    arr = [1.0 if v else 0.0 for v in vals if v is not None]
    return float(np.mean(arr)) if arr else float("nan")


def summarize_comprehension(trial_dir: Path) -> dict:
    rows = mb.load_comprehension(trial_dir)
    by_cond: dict[str, list] = defaultdict(list)
    by_story: dict[str, list] = defaultdict(list)
    for r in rows:
        by_cond[r["condition"]].append(r["correct"])
        by_story[r["story_id"]].append(r["correct"])
    return {
        "n_items": len(rows),
        "overall_accuracy": _rate([r["correct"] for r in rows]),
        "by_condition": {c: _rate(v) for c, v in sorted(by_cond.items())},
        "by_story": {s: _rate(v) for s, v in sorted(by_story.items())},
    }


def summarize_pair_scaling(trial_dir: Path) -> dict:
    records = mb.load_sweep_matrices(trial_dir)
    by_cond: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_cond[r["condition"]].append(r)

    def pack(recs: list[dict]) -> dict:
        return {
            "n": len(recs),
            "mean_pearson_r_vs_gold": _mean([r.get("pearson_r_vs_gold") for r in recs]),
            "mean_directional_accuracy": _mean([r.get("directional_accuracy") for r in recs]),
            "mean_edge_f1": _mean([r.get("edge_f1") for r in recs]),
            "mean_n_parse_failures": _mean([r.get("n_parse_failures") for r in recs]),
        }

    return {
        "n_cells": len(records),
        "overall": pack(records),
        "by_condition": {c: pack(v) for c, v in sorted(by_cond.items())},
    }


def summarize_geometry(trial_dir: Path) -> dict:
    meta = mb.load_meta_rdms(trial_dir)

    def _block_summary(block: dict, label_key: str) -> dict:
        labels = block[label_key]
        mat = np.array(block["matrix"], dtype=float)
        mean_d = (
            float(np.nanmean(mat[np.triu_indices(len(labels), k=1)]))
            if len(labels) > 1
            else float("nan")
        )
        return {label_key: labels, "mean_offdiag_distance": mean_d}

    inter_story = {
        cond: _block_summary(block, "story_ids")
        for cond, block in meta.get("inter_story_rdms", {}).items()
    }
    inter_condition = {
        story: _block_summary(block, "conditions" if "conditions" in block else "story_ids")
        for story, block in meta.get("inter_condition_rdms", {}).items()
    }
    n_meta = len(meta.get("meta_rdm", {}).get("labels", []))
    meta_mat = np.array(meta.get("meta_rdm", {}).get("matrix", []), dtype=float)
    meta_mean = (
        float(np.nanmean(meta_mat[np.triu_indices(n_meta, k=1)])) if n_meta > 1 else float("nan")
    )
    return {
        "metric": meta.get("metric"),
        "inter_story": inter_story,
        "inter_condition": inter_condition,
        "meta_mean_offdiag_distance": meta_mean,
    }


def main() -> int:
    args = parse_args()
    trials = mb.list_trials(root=EXPERIMENT_ROOT)
    if not trials:
        print("No completed trials found in the canonical sweep.", file=sys.stderr)
        return 1

    per_model = []
    for trial_dir in trials:
        model = mb.trial_model_label(trial_dir)
        try:
            comp = summarize_comprehension(trial_dir)
            ps = summarize_pair_scaling(trial_dir)
            geo = summarize_geometry(trial_dir)
        except FileNotFoundError as exc:
            print(f"  skip {model}: {exc}", file=sys.stderr)
            continue
        per_model.append(
            {
                "model": model,
                "trial_dir": str(trial_dir.relative_to(EXPERIMENT_ROOT)),
                "comprehension": comp,
                "pair_scaling_vs_gold": ps,
                "geometry": geo,
            }
        )

    report = {
        "sweep_dir": str(mb.sweep_dir(EXPERIMENT_ROOT).relative_to(EXPERIMENT_ROOT)),
        "n_trials_summarized": len(per_model),
        "per_model": per_model,
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / "model_behavioural_summary.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Wrote {out_path}")
    for m in per_model:
        c = m["comprehension"]["overall_accuracy"]
        p = m["pair_scaling_vs_gold"]["overall"]
        print(
            f"  {m['model']}: comprehension={c:.3f}  "
            f"pair_scaling pearson_r_vs_gold={p['mean_pearson_r_vs_gold']:.3f}  "
            f"directional_acc={p['mean_directional_accuracy']:.3f}  "
            f"edge_f1={p['mean_edge_f1']:.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
