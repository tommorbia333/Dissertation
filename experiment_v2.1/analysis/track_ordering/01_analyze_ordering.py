#!/usr/bin/env python3
"""01_analyze_ordering.py — human + model chronological ordering summaries.

Reports Kendall τ distance, exact-match rate, and pairwise order accuracy for:

- Human participants (canonical selection from track-02 loader)
- Model behavioural sweep trials (parsed ordering.json)
- Probing representation probes (position_probe + pairwise_probe) as related
  temporal measures (not the same behavioural ordering task)

Outputs JSON under ``outputs/``; figures are produced by
``analysis/build_master_outputs.py``.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import yaml

TRACK_DIR = Path(__file__).resolve().parent
ANALYSIS_DIR = TRACK_DIR.parent
EXPERIMENT_ROOT = ANALYSIS_DIR.parent

if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from shared.loaders import human as human_loader  # noqa: E402
from shared.ordering_metrics import (  # noqa: E402
    MAX_KENDALL,
    reconstruct_order_from_events,
    score_order,
)
from shared.story_sets import CONDITIONS, HUMAN_POOL_6  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--config",
        type=Path,
        default=ANALYSIS_DIR / "configs" / "canonical_runs.yaml",
    )
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


def _mean(vals: list[float | int | None]) -> float:
    arr = [float(v) for v in vals if v is not None and not (isinstance(v, float) and np.isnan(v))]
    return float(np.mean(arr)) if arr else float("nan")


def _rate(bools: list[bool | None]) -> float:
    arr = [1.0 if b else 0.0 for b in bools if b is not None]
    return float(np.mean(arr)) if arr else float("nan")


def analyze_human(selection: str) -> dict:
    rows = human_loader.load_canonical_csv(
        root=EXPERIMENT_ROOT,
        selection=selection,  # type: ignore[arg-type]
        write_canonical_yaml=False,
    )
    ordering_rows = [
        r for r in rows
        if r.get("task") == "ordering" and r.get("story_id") in HUMAN_POOL_6
    ]
    records = []
    n_from_final = 0
    n_from_events = 0
    n_failed = 0
    for r in ordering_rows:
        order = None
        source = None
        raw = r.get("final_order") or ""
        try:
            parsed = json.loads(raw) if isinstance(raw, str) and raw.startswith("[") else None
            if parsed:
                order = parsed
                source = "final_order"
                n_from_final += 1
        except json.JSONDecodeError:
            parsed = None

        if order is None:
            try:
                initial = json.loads(r.get("initial_order") or "[]")
                events = json.loads(r.get("events") or "[]")
            except json.JSONDecodeError:
                initial, events = [], []
            order = reconstruct_order_from_events(initial, events)
            if order is not None:
                source = "events_replay"
                n_from_events += 1
            else:
                n_failed += 1

        scored = score_order(order)
        logged = r.get("kendall_tau_to_canonical")
        if logged not in (None, "", "null") and scored["valid"]:
            try:
                scored["kendall_tau_distance"] = int(float(logged))
            except (TypeError, ValueError):
                pass
        records.append(
            {
                "run_id": str(r.get("run_id", "")),
                "assignment_id": str(r.get("assignment_id", "")),
                "story_id": str(r.get("story_id", "")),
                "condition": str(r.get("condition", "")),
                "order_source": source,
                **scored,
            }
        )

    by_cond: dict[str, list] = defaultdict(list)
    by_story: dict[str, list] = defaultdict(list)
    by_cell: dict[tuple[str, str], list] = defaultdict(list)
    for rec in records:
        by_cond[rec["condition"]].append(rec)
        by_story[rec["story_id"]].append(rec)
        by_cell[(rec["story_id"], rec["condition"])].append(rec)

    def pack(recs: list[dict]) -> dict:
        return {
            "n": len(recs),
            "mean_kendall_tau_distance": _mean([r["kendall_tau_distance"] for r in recs]),
            "exact_match_rate": _rate([r["exact_match"] for r in recs]),
            "mean_pairwise_accuracy": _mean([r["pairwise_accuracy"] for r in recs]),
        }

    valid = [r for r in records if r.get("valid")]
    return {
        "source": "human_pair_scaling_arm",
        "method": "behavioural_drag_ordering",
        "selection": selection,
        "n_trials": len(records),
        "n_valid": len(valid),
        "order_recovery": {
            "from_final_order_field": n_from_final,
            "from_events_replay": n_from_events,
            "failed": n_failed,
            "note": (
                "Cognition CSV exports often leave final_order=[] / "
                "kendall_tau_to_canonical=null; orders are reconstructed by "
                "replaying drag_end_moved events onto initial_order."
            ),
        },
        "max_kendall": MAX_KENDALL,
        "overall": pack(valid),
        "by_condition": {c: pack([r for r in by_cond[c] if r.get("valid")]) for c in CONDITIONS if c in by_cond},
        "by_story": {s: pack([r for r in by_story[s] if r.get("valid")]) for s in HUMAN_POOL_6 if s in by_story},
        "by_story_condition": {
            f"{sid}__{cond}": pack([r for r in by_cell[(sid, cond)] if r.get("valid")])
            for sid in HUMAN_POOL_6
            for cond in CONDITIONS
            if (sid, cond) in by_cell
        },
        "records": records,
    }


def _trial_label(trial_dir: Path) -> dict:
    """Extract a readable model label from a behavioural sweep trial folder name."""
    name = trial_dir.name
    # trial_<stamp>_<model>__<prompt>
    body = name.split("trial_", 1)[-1]
    parts = body.split("__", 1)
    stamp_model = parts[0]
    prompt = parts[1] if len(parts) > 1 else ""
    # drop leading timestamp YYYYMMDD_HHMMSS_
    bits = stamp_model.split("_", 2)
    model = bits[2] if len(bits) >= 3 else stamp_model
    return {
        "trial_dir": str(trial_dir.relative_to(EXPERIMENT_ROOT)),
        "model": model,
        "prompt_variant": prompt,
        "method": "behavioural_prompt_ordering",
        "label": f"{model} / behavioural ordering ({prompt or 'prompt'})",
    }


def analyze_model_behavioural(sweep_dir: Path) -> list[dict]:
    out = []
    if not sweep_dir.is_dir():
        return out
    for trial_dir in sorted(sweep_dir.glob("trial_*")):
        oj = trial_dir / "parsed" / "ordering.json"
        if not oj.exists():
            continue
        meta = _trial_label(trial_dir)
        data = json.loads(oj.read_text(encoding="utf-8"))
        records = []
        for entry in data:
            scored = score_order(entry.get("parsed"))
            records.append(
                {
                    "story_id": entry.get("story_id"),
                    "condition": entry.get("condition"),
                    "seed": entry.get("seed"),
                    **scored,
                }
            )

        by_cond: dict[str, list] = defaultdict(list)
        by_story: dict[str, list] = defaultdict(list)
        for rec in records:
            by_cond[str(rec["condition"])].append(rec)
            by_story[str(rec["story_id"])].append(rec)

        def pack(recs: list[dict]) -> dict:
            return {
                "n": len(recs),
                "mean_kendall_tau_distance": _mean([r["kendall_tau_distance"] for r in recs]),
                "exact_match_rate": _rate([r["exact_match"] for r in recs]),
                "mean_pairwise_accuracy": _mean([r["pairwise_accuracy"] for r in recs]),
            }

        out.append(
            {
                **meta,
                "n_trials": len(records),
                "overall": pack(records),
                "by_condition": {c: pack(v) for c, v in sorted(by_cond.items())},
                "by_story": {s: pack(v) for s, v in sorted(by_story.items())},
            }
        )
    return out


def analyze_probing_temporal(cfg: dict) -> list[dict]:
    """Summarise position_probe + pairwise_probe (representation, not behavioural)."""
    results = []
    runs = cfg.get("probing", {}).get("runs", {})
    for key, entry in runs.items():
        run_dir = EXPERIMENT_ROOT / entry["run_dir"]
        model_key = entry["model_key"]
        base = run_dir / model_key
        item = {
            "probing_run_key": key,
            "model_key": model_key,
            "run_dir": str(run_dir.relative_to(EXPERIMENT_ROOT)),
            "status": entry.get("status", "unknown"),
            "position_probe": None,
            "pairwise_probe": None,
            "note": (
                "These are hidden-state decode probes, NOT the behavioural "
                "drag/prompt ordering task. Included as related temporal measures."
            ),
        }
        pos = base / "position_probe" / "position_accuracy.npz"
        if pos.exists():
            with np.load(pos, allow_pickle=True) as z:
                keys = list(z.files)
                by_cond = {
                    k: float(np.nanmean(np.asarray(z[k], dtype=float)))
                    for k in keys
                }
            item["position_probe"] = {
                "method": "position_probe_LOSO",
                "artefact": str(pos.relative_to(EXPERIMENT_ROOT)),
                "npz_keys": keys,
                "mean_accuracy_by_condition": by_cond,
                "mean_accuracy": float(np.nanmean(list(by_cond.values()))) if by_cond else None,
                "figure": str((base / "position_probe" / "position_accuracy_by_layer.png").relative_to(EXPERIMENT_ROOT))
                if (base / "position_probe" / "position_accuracy_by_layer.png").exists()
                else None,
            }
        pair = base / "pairwise_probe" / "pairwise_accuracy.npz"
        if pair.exists():
            with np.load(pair, allow_pickle=True) as z:
                keys = list(z.files)
                by_cond = {}
                for cond in CONDITIONS:
                    key = f"acc_{cond}"
                    if key in z.files:
                        by_cond[cond] = float(np.nanmean(np.asarray(z[key], dtype=float)))
                baseline = float(z["baseline"]) if "baseline" in z.files else None
            item["pairwise_probe"] = {
                "method": "pairwise_probe_before_after_concurrent",
                "artefact": str(pair.relative_to(EXPERIMENT_ROOT)),
                "npz_keys": keys,
                "baseline_accuracy": baseline,
                "mean_accuracy_by_condition": by_cond,
                "mean_accuracy": float(np.nanmean(list(by_cond.values()))) if by_cond else baseline,
                "figure": str((base / "pairwise_probe" / "pairwise_accuracy_by_layer.png").relative_to(EXPERIMENT_ROOT))
                if (base / "pairwise_probe" / "pairwise_accuracy_by_layer.png").exists()
                else None,
            }
        results.append(item)
    return results


def main() -> int:
    args = parse_args()
    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    human = analyze_human(args.selection)
    sweep_rel = cfg["model_behavioural"]["sweep_dir"]
    sweep_dir = EXPERIMENT_ROOT / sweep_rel
    models = analyze_model_behavioural(sweep_dir)
    probing = analyze_probing_temporal(cfg)

    report = {
        "human": human,
        "model_behavioural": models,
        "probing_temporal": probing,
        "caveats": [
            "Human ordering uses a fixed preregistered scramble; model behavioural ordering uses a seed-dependent shuffle.",
            "Probing position/pairwise probes decode temporal structure from hidden states — not the same as producing an ordered sequence.",
            human.get("order_recovery", {}).get("note", ""),
        ],
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / "ordering_summary.json"
    # Drop per-record dump from human for the compact summary; keep full separately
    compact = dict(report)
    compact["human"] = {k: v for k, v in human.items() if k != "records"}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(compact, f, indent=2)
    with open(args.out_dir / "ordering_human_records.json", "w", encoding="utf-8") as f:
        json.dump(human["records"], f, indent=2)

    print(f"Wrote {out_path}")
    o = human["overall"]
    print(
        f"  Human (n={o['n']}): Kτ={o['mean_kendall_tau_distance']:.2f}  "
        f"exact={o['exact_match_rate']:.3f}  pairwise={o['mean_pairwise_accuracy']:.3f}"
    )
    for m in models:
        o = m["overall"]
        print(
            f"  {m['model']}: Kτ={o['mean_kendall_tau_distance']:.2f}  "
            f"exact={o['exact_match_rate']:.3f}  pairwise={o['mean_pairwise_accuracy']:.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
