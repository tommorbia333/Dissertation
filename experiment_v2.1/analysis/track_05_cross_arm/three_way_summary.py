#!/usr/bin/env python3
"""three_way_summary.py — human + model behavioural + probing overview table.

Aligns all three arms on HUMAN_POOL_6 (the model-only ``care_home_incident``/
``family_conflict`` stories are excluded here since there is no human data
to compare against). One row per (condition, arm); each row is a mean Mantel
r / mean 1-Spearman distance against the human aggregated RDM for that
condition.

Arms:
- ``human_vs_author``       — human pair-scaling vs the author causal graph
                               (the ceiling: how well humans track the gold
                               graph, not a model comparison)
- ``model_behavioural:<id>`` — instruct model prompted like a human
                               (track_05/compare_pair_scaling_to_human.py)
- ``probing:<run>:<arm>``    — base-model hidden-state probing run, arm in
                               {author, behavioural, prompted, reading}
                               (track_05/compare_probing_to_human.py)

Sources are read directly from their track output JSONs; run those scripts
first (or via ``analysis/build_master_outputs.py``, which orchestrates all of
them).
"""

from __future__ import annotations

import argparse
import csv
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

from shared.rdm_utils import mantel_r, spearman_distance_rdm  # noqa: E402
from shared.story_sets import CONDITIONS  # noqa: E402

try:
    from model_arm.probing import stimuli_probing as S
except ImportError:
    sys.path.insert(0, str(EXPERIMENT_ROOT))
    from model_arm.probing import stimuli_probing as S  # type: ignore


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--config",
        type=Path,
        default=ANALYSIS_DIR / "configs" / "canonical_runs.yaml",
    )
    p.add_argument("--out-dir", type=Path, default=TRACK_DIR / "outputs")
    return p.parse_args()


def _mean(vals: list[float]) -> float:
    arr = [v for v in vals if v is not None and not (isinstance(v, float) and np.isnan(v))]
    return float(np.mean(arr)) if arr else float("nan")


def human_vs_author_rows() -> list[dict]:
    if not TRACK02_AGG.exists():
        return []
    author = S.build_causal_rdm(EXPERIMENT_ROOT / "author_intended_graphs.json", scale_max=6)
    with np.load(TRACK02_AGG, allow_pickle=True) as z:
        story_keys = [str(s) for s in z["story_keys"]]
        by_cond = {c: z[f"human_{c}"].astype(float) for c in CONDITIONS if f"human_{c}" in z.files}

    rows = []
    for cond, stack in by_cond.items():
        mantel_vals, dist_vals = [], []
        for si, sid in enumerate(story_keys):
            h = stack[si]
            if np.all(np.isnan(h)) or sid not in author:
                continue
            a = author[sid]
            mantel_vals.append(mantel_r(h, a))
            dist_vals.append(spearman_distance_rdm(h, a))
        rows.append(
            {
                "condition": cond,
                "arm": "human_vs_author",
                "mean_mantel_r": _mean(mantel_vals),
                "mean_spearman_distance": _mean(dist_vals),
                "n_stories": len(mantel_vals),
            }
        )
    return rows


def model_behavioural_rows() -> list[dict]:
    path = TRACK_DIR / "outputs" / "pair_scaling_vs_human.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for model_report in data.get("models", []):
        model = model_report["model"]
        for cond, cell in model_report.get("mean_by_condition", {}).items():
            rows.append(
                {
                    "condition": cond,
                    "arm": f"model_behavioural:{model}",
                    "mean_mantel_r": cell["mean_mantel_r"],
                    "mean_spearman_distance": cell["mean_spearman_distance"],
                    "n_stories": cell["n_stories"],
                }
            )
    return rows


def probing_rows(cfg: dict) -> list[dict]:
    rows = []
    for run_key in cfg.get("probing", {}).get("runs", {}):
        path = TRACK_DIR / "outputs" / f"probing_vs_human_{run_key}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for cond, arms in data.get("mean_by_condition_arm", {}).items():
            for arm, cell in arms.items():
                rows.append(
                    {
                        "condition": cond,
                        "arm": f"probing:{run_key}:{arm}",
                        "mean_mantel_r": cell["mean_mantel_r"],
                        "mean_spearman_distance": cell["mean_spearman_distance"],
                        "n_stories": cell["n_stories"],
                    }
                )
    return rows


def main() -> int:
    args = parse_args()
    import yaml

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    rows = human_vs_author_rows() + model_behavioural_rows() + probing_rows(cfg)
    if not rows:
        print(
            "No inputs found. Run track_02 (01-03), "
            "track_05/compare_pair_scaling_to_human.py and "
            "track_05/compare_probing_to_human.py first.",
            file=sys.stderr,
        )
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_json = args.out_dir / "three_way_summary.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"story_subset": "human_pool_6", "rows": rows}, f, indent=2)

    out_csv = args.out_dir / "three_way_summary.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["condition", "arm", "mean_mantel_r", "mean_spearman_distance", "n_stories"]
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print(f"Wrote {out_json}")
    print(f"Wrote {out_csv}")
    print(f"\n{'condition':<12}{'arm':<40}{'mean_r':>10}{'mean_d':>10}{'n':>6}")
    for cond in CONDITIONS:
        for r in [r for r in rows if r["condition"] == cond]:
            print(
                f"{r['condition']:<12}{r['arm']:<40}"
                f"{r['mean_mantel_r']:>10.3f}{r['mean_spearman_distance']:>10.3f}{r['n_stories']:>6}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
