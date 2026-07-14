#!/usr/bin/env python3
"""compare_probing_to_human.py — probing behavioural RDMs vs human RDMs.

Loads ``behavioural/rdms/model_rdms_for_human.npz`` from a probing run and
compares against human aggregated RDMs from track 02 on the HUMAN_POOL_6
overlap.

For each condition and each probing arm (author / behavioural / prompted /
reading), reports per-story Pearson Mantel r and second-order distance
(1 − Spearman ρ) against the human mean matrix.
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

from shared.loaders import model_probing as probing_loader  # noqa: E402
from shared.rdm_utils import mantel_r, spearman_distance_rdm  # noqa: E402
from shared.story_sets import CONDITIONS, HUMAN_POOL_6  # noqa: E402

ARMS = ("author", "behavioural", "prompted", "reading")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--config",
        type=Path,
        default=ANALYSIS_DIR / "configs" / "canonical_runs.yaml",
    )
    p.add_argument(
        "--probing-run",
        default="full_1_5b",
        help="Key under probing.runs in canonical_runs.yaml",
    )
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
            "Run analysis/track_02_human_rdm/02_aggregate_rdms.py first."
        )
    with np.load(path, allow_pickle=True) as z:
        story_keys = [str(s) for s in z["story_keys"]]
        by_cond = {
            c: z[f"human_{c}"].astype(float)
            for c in CONDITIONS
            if f"human_{c}" in z.files
        }
    return story_keys, by_cond


def main() -> int:
    args = parse_args()
    _ = args.config  # loader uses DEFAULT_CONFIG; flag kept for CLI parity

    try:
        human_keys, human_by_cond = _load_human(args.human_rdms)
        probing = probing_loader.load_behavioural_rdms_by_key(
            args.probing_run, root=EXPERIMENT_ROOT
        )
    except (FileNotFoundError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    model_keys = probing["story_keys"]
    human_ix = _index_map(human_keys)
    model_ix = _index_map(model_keys)
    overlap = [s for s in HUMAN_POOL_6 if s in human_ix and s in model_ix]
    if not overlap:
        print("No overlapping stories between human and probing RDMs.", file=sys.stderr)
        return 1

    per_story: list[dict] = []
    summary_means: dict[str, dict[str, dict[str, float]]] = {}

    for cond in CONDITIONS:
        if cond not in human_by_cond:
            continue
        summary_means[cond] = {}
        for arm in ARMS:
            key = f"{arm}_{cond}"
            if key not in probing:
                continue
            mantel_vals: list[float] = []
            dist_vals: list[float] = []
            for sid in overlap:
                h = human_by_cond[cond][human_ix[sid]]
                m = probing[key][model_ix[sid]]
                if np.all(np.isnan(h)) or np.all(np.isnan(m)):
                    mr = float("nan")
                    sd = float("nan")
                else:
                    mr = mantel_r(h, m)
                    sd = spearman_distance_rdm(h, m)
                mantel_vals.append(mr)
                dist_vals.append(sd)
                per_story.append(
                    {
                        "story_id": sid,
                        "condition": cond,
                        "arm": arm,
                        "mantel_r": mr,
                        "spearman_distance": sd,
                    }
                )
            summary_means[cond][arm] = {
                "mean_mantel_r": float(np.nanmean(mantel_vals)),
                "mean_spearman_distance": float(np.nanmean(dist_vals)),
                "n_stories": int(np.sum(~np.isnan(mantel_vals))),
            }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / f"probing_vs_human_{args.probing_run}.json"
    report = {
        "probing_run": args.probing_run,
        "probing_artefact": probing.get("path"),
        "human_artefact": str(args.human_rdms),
        "story_subset": "human_pool_6",
        "overlap_stories": overlap,
        "metrics": {
            "mantel_r": "Pearson r on 56 off-diagonal cells",
            "spearman_distance": "1 - Spearman rho on 56 off-diagonal cells",
        },
        "mean_by_condition_arm": summary_means,
        "per_story": per_story,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Wrote {out_path}")
    print(f"Overlap stories ({len(overlap)}): {', '.join(overlap)}")
    print(f"{'condition':<12}{'arm':<14}{'mean_r':>10}{'mean_d':>10}{'n':>6}")
    for cond in CONDITIONS:
        for arm in ARMS:
            cell = summary_means.get(cond, {}).get(arm)
            if not cell:
                continue
            print(
                f"{cond:<12}{arm:<14}"
                f"{cell['mean_mantel_r']:>10.3f}"
                f"{cell['mean_spearman_distance']:>10.3f}"
                f"{cell['n_stories']:>6}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
