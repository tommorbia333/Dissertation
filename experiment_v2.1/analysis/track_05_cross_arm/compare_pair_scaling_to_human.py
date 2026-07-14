#!/usr/bin/env python3
"""compare_pair_scaling_to_human.py — model behavioural vs human pair-scaling RDMs.

Correlates each model behavioural sweep trial's seed-averaged pair-scaling
matrices with human aggregated RDMs (track 02) on the 6-story human/model
overlap (HUMAN_POOL_6 — the sweep already only covers these 6 domains).

For each trial and condition, reports per-story Pearson Mantel r and
second-order distance (1 − Spearman ρ) against the human mean matrix, mirroring
``compare_probing_to_human.py`` so the two are directly comparable.
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
TRACK02_AGG = ANALYSIS_DIR / "track_02_human_rdm" / "outputs" / "aggregated" / "human_rdms.npz"

if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from shared.loaders import model_behavioural as mb  # noqa: E402
from shared.rdm_utils import mantel_r, spearman_distance_rdm  # noqa: E402
from shared.story_sets import CONDITIONS, HUMAN_POOL_6  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--human-rdms",
        type=Path,
        default=TRACK02_AGG,
        help="Path to track_02 aggregated human_rdms.npz",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=TRACK_DIR / "outputs",
    )
    return p.parse_args()


def _index_map(keys: list[str]) -> dict[str, int]:
    return {k: i for i, k in enumerate(keys)}


def _load_human(path: Path) -> tuple[list[str], dict[str, np.ndarray]]:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing human aggregated RDMs: {path}\n"
            "Run analysis/track_02_human_rdm/01_extract_matrices.py, "
            "02_aggregate_rdms.py first."
        )
    with np.load(path, allow_pickle=True) as z:
        story_keys = [str(s) for s in z["story_keys"]]
        by_cond = {
            c: z[f"human_{c}"].astype(float) for c in CONDITIONS if f"human_{c}" in z.files
        }
    return story_keys, by_cond


def main() -> int:
    args = parse_args()

    try:
        human_keys, human_by_cond = _load_human(args.human_rdms)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    trials = mb.list_trials(root=EXPERIMENT_ROOT)
    if not trials:
        print("No completed model behavioural trials found.", file=sys.stderr)
        return 1

    human_ix = _index_map(human_keys)
    all_reports = []

    for trial_dir in trials:
        model = mb.trial_model_label(trial_dir)
        try:
            records = mb.load_sweep_matrices(trial_dir)
        except FileNotFoundError as exc:
            print(f"  skip {model}: {exc}", file=sys.stderr)
            continue
        model_keys, model_by_cond = mb.aggregate_matrices_by_story_condition(records)
        model_ix = _index_map(model_keys)
        overlap = [s for s in HUMAN_POOL_6 if s in human_ix and s in model_ix]
        if not overlap:
            continue

        per_story: list[dict] = []
        summary_means: dict[str, dict] = {}
        for cond in CONDITIONS:
            if cond not in human_by_cond or cond not in model_by_cond:
                continue
            mantel_vals, dist_vals = [], []
            for sid in overlap:
                h = human_by_cond[cond][human_ix[sid]]
                m = model_by_cond[cond][model_ix[sid]]
                if np.all(np.isnan(h)) or np.all(np.isnan(m)):
                    mr, sd = float("nan"), float("nan")
                else:
                    mr = mantel_r(h, m)
                    sd = spearman_distance_rdm(h, m)
                mantel_vals.append(mr)
                dist_vals.append(sd)
                per_story.append(
                    {"story_id": sid, "condition": cond, "mantel_r": mr, "spearman_distance": sd}
                )
            summary_means[cond] = {
                "mean_mantel_r": float(np.nanmean(mantel_vals)),
                "mean_spearman_distance": float(np.nanmean(dist_vals)),
                "n_stories": int(np.sum(~np.isnan(mantel_vals))),
            }

        report = {
            "model": model,
            "trial_dir": str(trial_dir.relative_to(EXPERIMENT_ROOT)),
            "arm": "behavioural_prompt (instruct model, v5_human_like)",
            "story_subset": "human_pool_6",
            "overlap_stories": overlap,
            "metrics": {
                "mantel_r": "Pearson r on 56 off-diagonal cells",
                "spearman_distance": "1 - Spearman rho on 56 off-diagonal cells",
            },
            "mean_by_condition": summary_means,
            "per_story": per_story,
        }
        all_reports.append(report)

    if not all_reports:
        print("No model/human overlap found.", file=sys.stderr)
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / "pair_scaling_vs_human.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"human_artefact": str(args.human_rdms), "models": all_reports}, f, indent=2)

    print(f"Wrote {out_path}")
    for report in all_reports:
        print(f"\n{report['model']}:")
        print(f"{'condition':<12}{'mean_r':>10}{'mean_d':>10}{'n':>6}")
        for cond in CONDITIONS:
            cell = report["mean_by_condition"].get(cond)
            if not cell:
                continue
            print(
                f"{cond:<12}{cell['mean_mantel_r']:>10.3f}"
                f"{cell['mean_spearman_distance']:>10.3f}{cell['n_stories']:>6}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
