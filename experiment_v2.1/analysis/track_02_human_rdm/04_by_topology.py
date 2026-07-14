#!/usr/bin/env python3
"""04_by_topology.py — stratify human RDM summaries by author topology.

Two views of the same 6-story overlap, grouped by ``TOPOLOGY_FAMILY``
(convergent / chain / fan_out / hourglass — see ``shared/story_sets.py``):

1. Human-vs-author alignment (Mantel r, 1 − Spearman distance) per story,
   grouped by topology family and condition — does the human world-model
   track the author graph equally well regardless of causal shape?
2. Inter-story second-order distances (from ``03_second_order_rsa``),
   split into within-family vs across-family pairs — are stories with the
   same topology more similar to each other than stories with different
   topologies?
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

from shared.rdm_utils import mantel_r, spearman_distance_rdm  # noqa: E402
from shared.story_sets import CONDITIONS, TOPOLOGY_FAMILY  # noqa: E402

try:
    from model_arm.probing import stimuli_probing as S
except ImportError:
    sys.path.insert(0, str(EXPERIMENT_ROOT))
    from model_arm.probing import stimuli_probing as S  # type: ignore


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--aggregated-dir",
        type=Path,
        default=TRACK_DIR / "outputs" / "aggregated",
        help="Input from 02_aggregate_rdms",
    )
    p.add_argument(
        "--second-order-dir",
        type=Path,
        default=TRACK_DIR / "outputs" / "second_order",
        help="Input from 03_second_order_rsa",
    )
    p.add_argument(
        "--graph-path",
        type=Path,
        default=EXPERIMENT_ROOT / "author_intended_graphs.json",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=TRACK_DIR / "outputs" / "by_topology",
    )
    return p.parse_args()


def _load_aggregated(path: Path) -> tuple[list[str], dict[str, np.ndarray]]:
    npz = path / "human_rdms.npz"
    if not npz.exists():
        raise FileNotFoundError(f"Missing aggregated artefact: {npz}")
    with np.load(npz, allow_pickle=True) as z:
        story_keys = [str(s) for s in z["story_keys"]]
        by_cond = {c: z[f"human_{c}"].astype(float) for c in CONDITIONS if f"human_{c}" in z.files}
    return story_keys, by_cond


def _mean(vals: list[float]) -> float:
    arr = [v for v in vals if v is not None and not (isinstance(v, float) and np.isnan(v))]
    return float(np.mean(arr)) if arr else float("nan")


def by_topology_vs_author(story_keys: list[str], by_cond: dict[str, np.ndarray], graph_path: Path) -> dict:
    author = S.build_causal_rdm(graph_path, scale_max=6)
    rows = []
    for cond, stack in by_cond.items():
        for si, sid in enumerate(story_keys):
            h = stack[si]
            if np.all(np.isnan(h)) or sid not in author:
                continue
            a = author[sid]
            rows.append(
                {
                    "story_id": sid,
                    "condition": cond,
                    "topology_family": TOPOLOGY_FAMILY.get(sid, "unknown"),
                    "mantel_r": mantel_r(h, a),
                    "spearman_distance": spearman_distance_rdm(h, a),
                }
            )

    by_family: dict[str, list] = defaultdict(list)
    by_family_cond: dict[tuple[str, str], list] = defaultdict(list)
    for r in rows:
        by_family[r["topology_family"]].append(r)
        by_family_cond[(r["topology_family"], r["condition"])].append(r)

    def pack(recs: list[dict]) -> dict:
        return {
            "n": len(recs),
            "mean_mantel_r": _mean([r["mantel_r"] for r in recs]),
            "mean_spearman_distance": _mean([r["spearman_distance"] for r in recs]),
        }

    families = sorted(by_family.keys())
    return {
        "per_story_condition": rows,
        "by_family": {fam: pack(v) for fam, v in by_family.items()},
        "by_family_condition": {
            f"{fam}__{cond}": pack(by_family_cond[(fam, cond)])
            for fam in families
            for cond in CONDITIONS
            if (fam, cond) in by_family_cond
        },
    }


def within_vs_across_family(second_order_dir: Path) -> dict:
    path = second_order_dir / "second_order_rsa.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing second-order artefact: {path}\nRun 03_second_order_rsa.py first."
        )
    report = json.loads(path.read_text(encoding="utf-8"))

    out = {}
    for cond, block in report.get("inter_story", {}).items():
        labels = block["labels"]
        rdm = np.array(block["rdm"], dtype=float)
        within, across = [], []
        for i in range(len(labels)):
            for j in range(i + 1, len(labels)):
                d = rdm[i, j]
                if np.isnan(d):
                    continue
                fam_i = TOPOLOGY_FAMILY.get(labels[i], "unknown")
                fam_j = TOPOLOGY_FAMILY.get(labels[j], "unknown")
                (within if fam_i == fam_j else across).append(float(d))
        out[cond] = {
            "within_family_mean_distance": _mean(within),
            "within_family_n_pairs": len(within),
            "across_family_mean_distance": _mean(across),
            "across_family_n_pairs": len(across),
        }
    return out


def main() -> int:
    args = parse_args()
    try:
        story_keys, by_cond = _load_aggregated(args.aggregated_dir)
        vs_author = by_topology_vs_author(story_keys, by_cond, args.graph_path)
        within_across = within_vs_across_family(args.second_order_dir)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    report = {
        "topology_family": TOPOLOGY_FAMILY,
        "human_vs_author_by_topology": vs_author,
        "inter_story_within_vs_across_family": within_across,
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / "by_topology.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Wrote {out_path}")
    print("\nHuman vs author, by topology family:")
    for fam, cell in vs_author["by_family"].items():
        print(f"  {fam:<12} n={cell['n']:>3}  mean_r={cell['mean_mantel_r']:.3f}  mean_d={cell['mean_spearman_distance']:.3f}")
    print("\nInter-story distance, within- vs across-family:")
    for cond, cell in within_across.items():
        print(
            f"  {cond:<12} within={cell['within_family_mean_distance']:.3f} (n={cell['within_family_n_pairs']})  "
            f"across={cell['across_family_mean_distance']:.3f} (n={cell['across_family_n_pairs']})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
