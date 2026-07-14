#!/usr/bin/env python3
"""build_master_outputs.py — assemble experiment_v2.1/master_outputs/.

Creates an organised writeup hub with:

- Newly generated human RDM / RSA / cross-arm / ordering / author-alignment figures
- Labelled copies of key model behavioural-sweep and probing figures
- ``inventory.json`` (done vs missing)
- Auto-generated ``README.md`` with results values and canonical path links

Usage (from experiment_v2.1/):
    python3 analysis/build_master_outputs.py
    python3 analysis/build_master_outputs.py --skip-rerun   # only rebuild hub
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import yaml

ANALYSIS_DIR = Path(__file__).resolve().parent
EXPERIMENT_ROOT = ANALYSIS_DIR.parent
MASTER = EXPERIMENT_ROOT / "master_outputs"

if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from shared.rdm_utils import mantel_r, spearman_distance_rdm  # noqa: E402
from shared.story_sets import CONDITIONS, HUMAN_POOL_6, TOPOLOGY_LABELS  # noqa: E402

try:
    from model_arm.probing import stimuli_probing as S
except ImportError:
    sys.path.insert(0, str(EXPERIMENT_ROOT))
    from model_arm.probing import stimuli_probing as S  # type: ignore


SECTIONS = [
    "01_human_rdms",
    "02_second_order_rsa",
    "03_human_vs_author",
    "04_cross_arm_probing",
    "05_temporal_ordering",
    "06_model_behavioural_sweep",
    "07_model_probing",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--skip-rerun",
        action="store_true",
        help="Do not re-run upstream analysis scripts; only rebuild figures/README",
    )
    return p.parse_args()


def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=EXPERIMENT_ROOT, check=True)


def ensure_upstream(skip: bool) -> None:
    if skip:
        return
    py = sys.executable  # reuse whatever interpreter is running this script
    scripts = [
        [py, "analysis/track_01_human_collection/01_comprehension_accuracy.py"],
        [py, "analysis/track_02_human_rdm/01_extract_matrices.py"],
        [py, "analysis/track_02_human_rdm/02_aggregate_rdms.py"],
        [py, "analysis/track_02_human_rdm/03_second_order_rsa.py"],
        [py, "analysis/track_02_human_rdm/04_by_topology.py"],
        [py, "analysis/track_03_model_behavioural/01_summarize_sweep.py"],
        [py, "analysis/track_05_cross_arm/compare_pair_scaling_to_human.py"],
        [py, "analysis/track_05_cross_arm/compare_probing_to_human.py", "--probing-run", "full_1_5b"],
        [py, "analysis/track_ordering/01_analyze_ordering.py"],
    ]
    # Also compare 7B if artefacts exist
    cfg = yaml.safe_load((ANALYSIS_DIR / "configs" / "canonical_runs.yaml").read_text())
    run7 = EXPERIMENT_ROOT / cfg["probing"]["runs"]["full_7b"]["run_dir"]
    model7 = cfg["probing"]["runs"]["full_7b"]["model_key"]
    if (run7 / model7 / "behavioural" / "rdms" / "model_rdms_for_human.npz").exists():
        scripts.append(
            [py, "analysis/track_05_cross_arm/compare_probing_to_human.py", "--probing-run", "full_7b"]
        )
    # three_way_summary reads the outputs of the scripts above, so it must run last.
    scripts.append([py, "analysis/track_05_cross_arm/three_way_summary.py"])
    for cmd in scripts:
        _run(cmd)


def _savefig(path: Path, fig=None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    (fig or plt).savefig(path, dpi=150, bbox_inches="tight")
    plt.close("all")


def _heatmap(ax, M, title: str, vmin=None, vmax=None):
    im = ax.imshow(M, cmap="viridis", vmin=vmin, vmax=vmax, aspect="equal")
    ax.set_xticks(range(8))
    ax.set_yticks(range(8))
    ax.set_xticklabels([f"E{i}" for i in range(1, 9)], fontsize=7)
    ax.set_yticklabels([f"E{i}" for i in range(1, 9)], fontsize=7)
    ax.set_title(title, fontsize=9)
    return im


def plot_human_rdms(out_dir: Path) -> list[str]:
    npz = ANALYSIS_DIR / "track_02_human_rdm" / "outputs" / "aggregated" / "human_rdms.npz"
    with np.load(npz, allow_pickle=True) as z:
        stories = [str(s) for s in z["story_keys"]]
        stacks = {c: z[f"human_{c}"].astype(float) for c in CONDITIONS}

    written = []
    # Story-averaged by condition
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    for ax, cond in zip(axes, CONDITIONS):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            M = np.nanmean(stacks[cond], axis=0)
        _heatmap(ax, M, f"Human · pair-scaling · {cond}\n(story-averaged)")
    fig.suptitle("Human behavioural RDMs (pair-scaling ratings 0–6)", fontsize=11)
    fig.tight_layout()
    p = out_dir / "human__behavioural_pair_scaling__story_averaged_by_condition.png"
    _savefig(p, fig)
    written.append(p.name)

    # Per story × condition grid
    fig, axes = plt.subplots(len(stories), 3, figsize=(10, 2.2 * len(stories)), squeeze=False)
    for si, sid in enumerate(stories):
        for ci, cond in enumerate(CONDITIONS):
            _heatmap(axes[si][ci], stacks[cond][si], f"{sid}\n{cond}" if si == 0 else cond)
            if ci == 0:
                axes[si][ci].set_ylabel(sid.replace("_", "\n"), fontsize=7)
    fig.suptitle("Human behavioural RDMs by story × condition", fontsize=11)
    fig.tight_layout()
    p = out_dir / "human__behavioural_pair_scaling__per_story_condition.png"
    _savefig(p, fig)
    written.append(p.name)
    return written


def plot_second_order(out_dir: Path) -> list[str]:
    path = ANALYSIS_DIR / "track_02_human_rdm" / "outputs" / "second_order" / "second_order_rsa.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    written = []

    # Inter-story panels
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    for ax, cond in zip(axes, CONDITIONS):
        block = report["inter_story"][cond]
        M = np.array(block["rdm"], dtype=float)
        labels = block["labels"]
        im = ax.imshow(M, cmap="magma", vmin=0, vmax=1, aspect="equal")
        ax.set_xticks(range(len(labels)))
        ax.set_yticks(range(len(labels)))
        ax.set_xticklabels([s.replace("_", "\n") for s in labels], fontsize=6, rotation=45, ha="right")
        ax.set_yticklabels([s.replace("_", "\n") for s in labels], fontsize=6)
        ax.set_title(f"Inter-story · {cond}\nmean d={block['mean_offdiag_distance']:.3f}", fontsize=9)
        fig.colorbar(im, ax=ax, fraction=0.046)
    fig.suptitle("Human second-order RSA (1 − Spearman ρ on 56 off-diag cells)", fontsize=11)
    fig.tight_layout()
    p = out_dir / "human__second_order_rsa__inter_story_by_condition.png"
    _savefig(p, fig)
    written.append(p.name)

    # Inter-condition for each story
    stories = list(report["inter_condition"].keys())
    fig, axes = plt.subplots(2, 3, figsize=(10, 6.5))
    for ax, sid in zip(axes.ravel(), stories):
        block = report["inter_condition"][sid]
        M = np.array(block["rdm"], dtype=float)
        labels = block["labels"]
        im = ax.imshow(M, cmap="magma", vmin=0, vmax=1, aspect="equal")
        ax.set_xticks(range(len(labels)))
        ax.set_yticks(range(len(labels)))
        ax.set_xticklabels(labels, fontsize=7, rotation=30, ha="right")
        ax.set_yticklabels(labels, fontsize=7)
        ax.set_title(f"{sid}\nmean d={block['mean_offdiag_distance']:.3f}", fontsize=8)
    for ax in axes.ravel()[len(stories) :]:
        ax.axis("off")
    fig.suptitle("Human inter-condition second-order RSA", fontsize=11)
    fig.tight_layout()
    p = out_dir / "human__second_order_rsa__inter_condition_by_story.png"
    _savefig(p, fig)
    written.append(p.name)
    return written


def plot_human_vs_author(out_dir: Path) -> list[str]:
    npz = ANALYSIS_DIR / "track_02_human_rdm" / "outputs" / "aggregated" / "human_rdms.npz"
    author = S.build_causal_rdm(EXPERIMENT_ROOT / "author_intended_graphs.json", scale_max=6)
    with np.load(npz, allow_pickle=True) as z:
        stories = [str(s) for s in z["story_keys"]]
        stacks = {c: z[f"human_{c}"].astype(float) for c in CONDITIONS}

    rows = []
    for cond in CONDITIONS:
        for si, sid in enumerate(stories):
            h = stacks[cond][si]
            a = author[sid]
            rows.append(
                {
                    "story_id": sid,
                    "condition": cond,
                    "mantel_r": mantel_r(h, a),
                    "spearman_distance": spearman_distance_rdm(h, a),
                }
            )

    # Bar chart: mean Mantel by condition + per-story bars for linear as example grid
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), sharey=True)
    for ax, cond in zip(axes, CONDITIONS):
        sub = [r for r in rows if r["condition"] == cond]
        xs = np.arange(len(sub))
        ax.bar(xs, [r["mantel_r"] for r in sub], color="#4C72B0")
        ax.axhline(0, color="grey", lw=0.8)
        ax.set_xticks(xs)
        ax.set_xticklabels([r["story_id"].replace("_", "\n") for r in sub], fontsize=6)
        ax.set_title(f"{cond}\nmean r={np.nanmean([r['mantel_r'] for r in sub]):.3f}")
        ax.set_ylabel("Mantel r (human vs author)")
    fig.suptitle("Human pair-scaling vs author causal graph", fontsize=11)
    fig.tight_layout()
    p = out_dir / "human__behavioural_pair_scaling__vs_author_mantel_by_story.png"
    _savefig(p, fig)

    summary = {
        "metric": "Pearson Mantel r / 1-Spearman distance on 56 off-diag cells",
        "by_condition": {
            c: {
                "mean_mantel_r": float(np.nanmean([r["mantel_r"] for r in rows if r["condition"] == c])),
                "mean_spearman_distance": float(
                    np.nanmean([r["spearman_distance"] for r in rows if r["condition"] == c])
                ),
            }
            for c in CONDITIONS
        },
        "per_story": rows,
    }
    (out_dir / "human_vs_author_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return [p.name, "human_vs_author_summary.json"]


def plot_cross_arm(out_dir: Path) -> list[str]:
    written = []
    for key in ("full_1_5b", "full_7b"):
        src = ANALYSIS_DIR / "track_05_cross_arm" / "outputs" / f"probing_vs_human_{key}.json"
        if not src.exists():
            continue
        report = json.loads(src.read_text(encoding="utf-8"))
        means = report["mean_by_condition_arm"]
        arms = ["author", "behavioural", "prompted", "reading"]
        fig, axes = plt.subplots(1, 3, figsize=(12, 4), sharey=True)
        x = np.arange(len(arms))
        for ax, cond in zip(axes, CONDITIONS):
            rs = [means.get(cond, {}).get(a, {}).get("mean_mantel_r", np.nan) for a in arms]
            ax.bar(x, rs, color=["#55A868", "#4C72B0", "#C44E52", "#8172B2"])
            ax.set_xticks(x)
            ax.set_xticklabels(arms, rotation=30, ha="right", fontsize=8)
            ax.axhline(0, color="grey", lw=0.8)
            ax.set_title(cond)
            ax.set_ylabel("Mean Mantel r vs human")
        model = "qwen1.5b" if "1_5b" in key else "qwen7b"
        fig.suptitle(
            f"Cross-arm: probing ({model}) vs human RDMs\n"
            f"method = probing behavioural/prompted/reading + author graph",
            fontsize=11,
        )
        fig.tight_layout()
        p = out_dir / f"cross_arm__{model}__probing_vs_human__mean_mantel_by_arm.png"
        _savefig(p, fig)
        written.append(p.name)
        shutil.copy2(src, out_dir / src.name)
        written.append(src.name)
    return written


def plot_ordering(out_dir: Path) -> list[str]:
    src = ANALYSIS_DIR / "track_ordering" / "outputs" / "ordering_summary.json"
    report = json.loads(src.read_text(encoding="utf-8"))
    written = []
    shutil.copy2(src, out_dir / "ordering_summary.json")
    written.append("ordering_summary.json")

    human = report["human"]
    # Human by condition
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    conds = list(human["by_condition"].keys())
    # Panel 1: Kendall
    axes[0].bar(conds, [human["by_condition"][c]["mean_kendall_tau_distance"] for c in conds], color="#4C72B0")
    axes[0].set_title("Human Kendall τ distance\n(lower = better; max 28)")
    axes[0].set_ylabel("Mean Kτ distance")
    # Panel 2: exact match
    axes[1].bar(conds, [human["by_condition"][c]["exact_match_rate"] for c in conds], color="#55A868")
    axes[1].set_title("Human exact-match rate")
    axes[1].set_ylim(0, 1)
    # Panel 3: pairwise
    axes[2].bar(conds, [human["by_condition"][c]["mean_pairwise_accuracy"] for c in conds], color="#C44E52")
    axes[2].set_title("Human pairwise order accuracy")
    axes[2].set_ylim(0, 1)
    fig.suptitle("Human chronological ordering (behavioural drag task)", fontsize=11)
    fig.tight_layout()
    p = out_dir / "ordering__human__behavioural_drag__by_condition.png"
    _savefig(p, fig)
    written.append(p.name)

    # Human by story (pairwise accuracy)
    stories = list(human["by_story"].keys())
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(
        range(len(stories)),
        [human["by_story"][s]["mean_pairwise_accuracy"] for s in stories],
        color="#4C72B0",
    )
    ax.set_xticks(range(len(stories)))
    ax.set_xticklabels([s.replace("_", "\n") for s in stories], fontsize=8)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Pairwise order accuracy")
    ax.set_title("Human ordering pairwise accuracy by story")
    fig.tight_layout()
    p = out_dir / "ordering__human__behavioural_drag__pairwise_by_story.png"
    _savefig(p, fig)
    written.append(p.name)

    # Human vs model behavioural comparison
    models = report.get("model_behavioural", [])
    if models:
        labels = ["human"] + [m["model"] for m in models]
        kts = [human["overall"]["mean_kendall_tau_distance"]] + [
            m["overall"]["mean_kendall_tau_distance"] for m in models
        ]
        exacts = [human["overall"]["exact_match_rate"]] + [
            m["overall"]["exact_match_rate"] for m in models
        ]
        pairs = [human["overall"]["mean_pairwise_accuracy"]] + [
            m["overall"]["mean_pairwise_accuracy"] for m in models
        ]
        x = np.arange(len(labels))
        fig, axes = plt.subplots(1, 3, figsize=(13, 4))
        axes[0].bar(x, kts, color="#4C72B0")
        axes[0].set_title("Kendall τ distance (↓ better)")
        axes[1].bar(x, exacts, color="#55A868")
        axes[1].set_title("Exact-match rate")
        axes[1].set_ylim(0, 1)
        axes[2].bar(x, pairs, color="#C44E52")
        axes[2].set_title("Pairwise accuracy")
        axes[2].set_ylim(0, 1)
        for ax in axes:
            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=7)
        fig.suptitle(
            "Ordering: human drag task vs model behavioural prompt ordering\n"
            "(models = instruct, v5_human_like)",
            fontsize=11,
        )
        fig.tight_layout()
        p = out_dir / "ordering__human_vs_models__behavioural__overall_metrics.png"
        _savefig(p, fig)
        written.append(p.name)

    return written


def collect_model_behavioural(out_dir: Path, cfg: dict) -> list[dict]:
    """Copy key sweep figures with explicit model+method labels."""
    sweep = EXPERIMENT_ROOT / cfg["model_behavioural"]["sweep_dir"]
    collected = []
    key_rel = [
        ("figures/headline.png", "headline_summary"),
        ("figures/diagnostics/orderings.png", "ordering_kendall_heatmap"),
        ("figures/diagnostics/meta_rdm.png", "meta_rdm"),
        ("figures/diagnostics/inter_story_rdms.png", "inter_story_rdms"),
        ("figures/diagnostics/inter_condition_rdms.png", "inter_condition_rdms"),
        ("figures/diagnostics/pair_scaling_vs_gold_metrics.png", "pair_scaling_vs_author"),
        ("figures/diagnostics/cross_task_summary.png", "cross_task_summary"),
        ("figures/diagnostics/condition_contrasts.png", "condition_contrasts"),
        ("figures/diagnostics/comprehension_accuracy.png", "comprehension_accuracy"),
    ]
    for trial_dir in sorted(sweep.glob("trial_*")):
        if not (trial_dir / "manifest.json").exists():
            continue
        # Parse model name
        body = trial_dir.name.split("trial_", 1)[-1]
        parts = body.split("__", 1)
        stamp_model = parts[0]
        prompt = parts[1] if len(parts) > 1 else "prompt"
        bits = stamp_model.split("_", 2)
        model = bits[2] if len(bits) >= 3 else stamp_model
        safe_model = model.replace("/", "-")
        for rel, tag in key_rel:
            src = trial_dir / rel
            if not src.exists():
                continue
            dest_name = f"model_behavioural__{safe_model}__behavioural_prompt__{tag}.png"
            dest = out_dir / dest_name
            shutil.copy2(src, dest)
            collected.append(
                {
                    "file": dest_name,
                    "model": model,
                    "method": "behavioural_prompt (v5_human_like)",
                    "source": str(src.relative_to(EXPERIMENT_ROOT)),
                    "tag": tag,
                }
            )
    return collected


def collect_probing(out_dir: Path, cfg: dict) -> list[dict]:
    collected = []
    picks = [
        ("position_probe/position_accuracy_by_layer.png", "position_probe", "position_accuracy_by_layer"),
        ("pairwise_probe/pairwise_accuracy_by_layer.png", "pairwise_probe", "pairwise_accuracy_by_layer"),
        ("causal_rdm/causal_mantel_by_layer.png", "causal_rdm", "mantel_vs_author_by_layer"),
        ("geometry/cyclicity_by_layer.png", "geometry", "cyclicity_by_layer"),
        ("geometry/event_planes_cosine.png", "geometry", "event_planes_cosine"),
        ("behavioural/analysis_summary_rdms.png", "probing_behavioural", "story_averaged_rdms"),
        ("behavioural/analysis_perstory_linear.png", "probing_behavioural", "perstory_linear"),
        ("behavioural/analysis_perstory_nonlinear.png", "probing_behavioural", "perstory_nonlinear"),
        ("behavioural/analysis_perstory_atemporal.png", "probing_behavioural", "perstory_atemporal"),
        ("behavioural/per_story_three_arms_linear.png", "probing_behavioural", "three_arms_linear"),
        ("behavioural/per_story_three_arms_nonlinear.png", "probing_behavioural", "three_arms_nonlinear"),
        ("behavioural/per_story_three_arms_atemporal.png", "probing_behavioural", "three_arms_atemporal"),
    ]
    for key, entry in cfg.get("probing", {}).get("runs", {}).items():
        run_dir = EXPERIMENT_ROOT / entry["run_dir"]
        model_key = entry["model_key"]
        base = run_dir / model_key
        for rel, method, tag in picks:
            src = base / rel
            if not src.exists():
                continue
            dest_name = f"probing__{model_key}__{method}__{tag}.png"
            shutil.copy2(src, out_dir / dest_name)
            collected.append(
                {
                    "file": dest_name,
                    "model": model_key,
                    "method": method,
                    "probing_run": key,
                    "source": str(src.relative_to(EXPERIMENT_ROOT)),
                    "tag": tag,
                    "status": entry.get("status"),
                }
            )
    return collected


def build_inventory(cfg: dict, collected: dict) -> dict:
    """Catalogue what exists vs what is still missing for the writeup."""
    done = []
    missing = []

    def mark(name: str, ok: bool, detail: str = "") -> None:
        (done if ok else missing).append({"item": name, "detail": detail})

    mark(
        "Human fill-gaps merge (all67)",
        (EXPERIMENT_ROOT / cfg["human"]["combined_csv"]).exists(),
        cfg["human"]["combined_csv"],
    )
    mark(
        "Assignment slot 11 filled",
        False,
        "Still missing from design (59/60 slots have a complete run)",
    )
    mark(
        "Human RDM extraction + aggregation",
        (ANALYSIS_DIR / "track_02_human_rdm/outputs/aggregated/human_rdms.npz").exists(),
    )
    mark(
        "Human second-order RSA",
        (ANALYSIS_DIR / "track_02_human_rdm/outputs/second_order/second_order_rsa.json").exists(),
    )
    mark(
        "Cross-arm probing vs human (1.5B)",
        (ANALYSIS_DIR / "track_05_cross_arm/outputs/probing_vs_human_full_1_5b.json").exists(),
    )
    mark(
        "Cross-arm probing vs human (7B)",
        (ANALYSIS_DIR / "track_05_cross_arm/outputs/probing_vs_human_full_7b.json").exists(),
    )
    mark(
        "Human comprehension accuracy summary",
        (ANALYSIS_DIR / "track_01_human_collection/outputs/comprehension_accuracy.json").exists(),
    )
    mark(
        "Human ↔ model behavioural pair-scaling comparison script",
        (ANALYSIS_DIR / "track_05_cross_arm/outputs/pair_scaling_vs_human.json").exists(),
    )
    mark(
        "Track 03 model behavioural summaries",
        (ANALYSIS_DIR / "track_03_model_behavioural/outputs/model_behavioural_summary.json").exists(),
    )
    mark(
        "Track 02 topology stratification (04_by_topology.py)",
        (ANALYSIS_DIR / "track_02_human_rdm/outputs/by_topology/by_topology.json").exists(),
    )
    mark(
        "Three-way cross-arm summary (human + model behavioural + probing)",
        (ANALYSIS_DIR / "track_05_cross_arm/outputs/three_way_summary.json").exists(),
    )
    ord_summary = ANALYSIS_DIR / "track_ordering/outputs/ordering_summary.json"
    mark(
        "Temporal ordering analysis (human + model behavioural + probing probes)",
        ord_summary.exists(),
    )
    if ord_summary.exists():
        od = json.loads(ord_summary.read_text(encoding="utf-8"))
        rec = od.get("human", {}).get("order_recovery", {})
        mark(
            "Human final_order field populated in CSV export",
            rec.get("from_final_order_field", 0) > 0,
            (
                f"Recovered {rec.get('from_events_replay', 0)} orders via drag-event "
                f"replay; {rec.get('failed', 0)} failed"
            ),
        )

    sweep = EXPERIMENT_ROOT / cfg["model_behavioural"]["sweep_dir"]
    for trial in sorted(sweep.glob("trial_*")):
        ok = (trial / "manifest.json").exists()
        mark(f"Model behavioural trial {trial.name}", ok, "failed/empty" if not ok else "complete")

    for key, entry in cfg.get("probing", {}).get("runs", {}).items():
        rdm = (
            EXPERIMENT_ROOT
            / entry["run_dir"]
            / entry["model_key"]
            / "behavioural/rdms/model_rdms_for_human.npz"
        )
        mark(f"Probing run {key} ({entry['model_key']})", rdm.exists(), entry.get("status", ""))

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "done": done,
        "missing": missing,
        "collected_figures": collected,
        "canonical_paths": {
            "human_csv": cfg["human"]["combined_csv"],
            "human_audit": cfg["human"]["audit_json"],
            "author_graphs": cfg["author_graphs"],
            "model_behavioural_sweep": cfg["model_behavioural"]["sweep_dir"],
            "probing_runs": {
                k: v["run_dir"] for k, v in cfg.get("probing", {}).get("runs", {}).items()
            },
            "analysis_hub": "analysis/",
        },
    }


def _fmt(x, digits=3):
    if x is None:
        return "n/a"
    try:
        if isinstance(x, float) and np.isnan(x):
            return "n/a"
        return f"{float(x):.{digits}f}"
    except (TypeError, ValueError):
        return str(x)


def write_readme(inventory: dict, cfg: dict) -> None:
    # Load key result JSONs
    human_vs_author = {}
    hva = MASTER / "03_human_vs_author" / "human_vs_author_summary.json"
    if hva.exists():
        human_vs_author = json.loads(hva.read_text(encoding="utf-8"))

    cross_reports = {}
    for key in ("full_1_5b", "full_7b"):
        cx = MASTER / "04_cross_arm_probing" / f"probing_vs_human_{key}.json"
        if cx.exists():
            cross_reports[key] = json.loads(cx.read_text(encoding="utf-8"))

    ordering = {}
    ordp = MASTER / "05_temporal_ordering" / "ordering_summary.json"
    if ordp.exists():
        ordering = json.loads(ordp.read_text(encoding="utf-8"))

    so = {}
    sop = ANALYSIS_DIR / "track_02_human_rdm/outputs/second_order/second_order_rsa.json"
    if sop.exists():
        so = json.loads(sop.read_text(encoding="utf-8"))

    comp = {}
    compp = ANALYSIS_DIR / "track_01_human_collection/outputs/comprehension_accuracy.json"
    if compp.exists():
        comp = json.loads(compp.read_text(encoding="utf-8"))

    topo = {}
    topop = ANALYSIS_DIR / "track_02_human_rdm/outputs/by_topology/by_topology.json"
    if topop.exists():
        topo = json.loads(topop.read_text(encoding="utf-8"))

    model_behav = {}
    mbp = ANALYSIS_DIR / "track_03_model_behavioural/outputs/model_behavioural_summary.json"
    if mbp.exists():
        model_behav = json.loads(mbp.read_text(encoding="utf-8"))

    ps_vs_human = {}
    pshp = ANALYSIS_DIR / "track_05_cross_arm/outputs/pair_scaling_vs_human.json"
    if pshp.exists():
        ps_vs_human = json.loads(pshp.read_text(encoding="utf-8"))

    three_way = {}
    twp = ANALYSIS_DIR / "track_05_cross_arm/outputs/three_way_summary.json"
    if twp.exists():
        three_way = json.loads(twp.read_text(encoding="utf-8"))

    lines: list[str] = []
    lines.append("# Master outputs — dissertation results hub")
    lines.append("")
    lines.append(
        f"_Auto-generated by `analysis/build_master_outputs.py` at "
        f"{inventory['generated_at_utc']}. Re-run that script to refresh figures and this README._"
    )
    lines.append("")
    lines.append("## How to regenerate")
    lines.append("")
    lines.append("```bash")
    lines.append("cd experiment_v2.1")
    lines.append("python3 analysis/build_master_outputs.py")
    lines.append("```")
    lines.append("")
    lines.append("## Folder map")
    lines.append("")
    lines.append("| Folder | Contents |")
    lines.append("|--------|----------|")
    lines.append("| `01_human_rdms/` | Human pair-scaling RDM heatmaps |")
    lines.append("| `02_second_order_rsa/` | Inter-story / inter-condition second-order RSA |")
    lines.append("| `03_human_vs_author/` | Human RDMs vs author causal graph |")
    lines.append("| `04_cross_arm_probing/` | Probing arms vs human RDMs |")
    lines.append("| `05_temporal_ordering/` | Human + model ordering metrics & figures |")
    lines.append("| `06_model_behavioural_sweep/` | Key instruct-model behavioural-sweep figures |")
    lines.append("| `07_model_probing/` | Key base-model probing figures |")
    lines.append("| `inventory.json` | Done vs missing checklist |")
    lines.append("")
    lines.append("Figure filenames encode **who / method / what**:")
    lines.append("`{section}__{model_or_human}__{method}__{description}.png`")
    lines.append("")

    lines.append("## Canonical data paths (not copied here)")
    lines.append("")
    for k, v in inventory["canonical_paths"].items():
        if isinstance(v, dict):
            lines.append(f"- **{k}:**")
            for kk, vv in v.items():
                lines.append(f"  - `{kk}`: `{vv}`")
        else:
            lines.append(f"- **{k}:** `{v}`")
    lines.append("")

    lines.append("## Inventory — done vs missing")
    lines.append("")
    lines.append("### Done")
    for item in inventory["done"]:
        detail = f" — {item['detail']}" if item.get("detail") else ""
        lines.append(f"- [x] {item['item']}{detail}")
    lines.append("")
    lines.append("### Missing / still to conduct")
    for item in inventory["missing"]:
        detail = f" — {item['detail']}" if item.get("detail") else ""
        lines.append(f"- [ ] {item['item']}{detail}")
    lines.append("")

    # ---- Results sections ----
    lines.append("## Results")
    lines.append("")

    lines.append("### 1. Human pair-scaling RDMs")
    lines.append("")
    lines.append(
        "Humans produced directed 8×8 causal ratings (0–6) per story. "
        "Aggregates are means across canonical participants "
        "(one complete run per `assignment_id`; see "
        "`human results/_audits/canonical_runs_for_analysis.yaml`)."
    )
    lines.append("")
    lines.append("Figures: `01_human_rdms/`.")
    lines.append("")

    lines.append("### 2. Human second-order RSA")
    lines.append("")
    lines.append("Distance = **1 − Spearman ρ** on 56 off-diagonal cells.")
    lines.append("")
    if so:
        lines.append("| Condition | Mean inter-story distance |")
        lines.append("|-----------|---------------------------|")
        for cond in CONDITIONS:
            d = so.get("inter_story", {}).get(cond, {}).get("mean_offdiag_distance")
            lines.append(f"| {cond} | {_fmt(d)} |")
        meta_d = so.get("meta", {}).get("mean_offdiag_distance")
        lines.append("")
        lines.append(f"Meta RDM mean off-diagonal distance (all story×condition cells): **{_fmt(meta_d)}**.")
    lines.append("")
    lines.append("Figures: `02_second_order_rsa/`.")
    lines.append("")

    lines.append("### 3. Human vs author causal graph")
    lines.append("")
    if human_vs_author:
        lines.append("| Condition | Mean Mantel r | Mean 1−Spearman d |")
        lines.append("|-----------|---------------|-------------------|")
        for cond in CONDITIONS:
            cell = human_vs_author.get("by_condition", {}).get(cond, {})
            lines.append(
                f"| {cond} | {_fmt(cell.get('mean_mantel_r'))} | "
                f"{_fmt(cell.get('mean_spearman_distance'))} |"
            )
    lines.append("")
    lines.append("Figures: `03_human_vs_author/`.")
    lines.append("")

    lines.append("### 4. Cross-arm: probing vs human")
    lines.append("")
    lines.append(
        "Compares probing `model_rdms_for_human.npz` arms "
        "(author / behavioural / prompted / reading) against human aggregates "
        "on HUMAN_POOL_6."
    )
    lines.append("")
    for run_key, cross in cross_reports.items():
        lines.append(
            f"**`{run_key}`** · probing run `{cross.get('probing_run')}`"
        )
        lines.append("")
        lines.append("| Condition | Arm | Mean Mantel r | Mean 1−Spearman d | n stories |")
        lines.append("|-----------|-----|---------------|-------------------|-----------|")
        for cond in CONDITIONS:
            for arm, cell in cross.get("mean_by_condition_arm", {}).get(cond, {}).items():
                lines.append(
                    f"| {cond} | {arm} | {_fmt(cell.get('mean_mantel_r'))} | "
                    f"{_fmt(cell.get('mean_spearman_distance'))} | {cell.get('n_stories')} |"
                )
        lines.append("")
    lines.append("Figures: `04_cross_arm_probing/`.")
    lines.append("")

    lines.append("### 5. Temporal ordering")
    lines.append("")
    lines.append(
        "Primary behavioural metrics (human drag task + model prompt ordering): "
        "Kendall τ distance (0–28, lower better), exact-match rate, pairwise order accuracy."
    )
    lines.append("")
    if ordering:
        h = ordering.get("human", {}).get("overall", {})
        lines.append("**Human (canonical selection)**")
        lines.append("")
        lines.append(f"- n story-trials: **{h.get('n')}**")
        lines.append(f"- Mean Kendall τ distance: **{_fmt(h.get('mean_kendall_tau_distance'), 2)}**")
        lines.append(f"- Exact-match rate: **{_fmt(h.get('exact_match_rate'))}**")
        lines.append(f"- Mean pairwise accuracy: **{_fmt(h.get('mean_pairwise_accuracy'))}**")
        lines.append("")
        lines.append("| Condition | Kτ | Exact | Pairwise | n |")
        lines.append("|-----------|----|-------|----------|---|")
        for cond, cell in ordering.get("human", {}).get("by_condition", {}).items():
            lines.append(
                f"| {cond} | {_fmt(cell.get('mean_kendall_tau_distance'), 2)} | "
                f"{_fmt(cell.get('exact_match_rate'))} | "
                f"{_fmt(cell.get('mean_pairwise_accuracy'))} | {cell.get('n')} |"
            )
        lines.append("")
        lines.append("**Model behavioural ordering (instruct, prompted)**")
        lines.append("")
        lines.append("| Model | Kτ | Exact | Pairwise | n |")
        lines.append("|-------|----|-------|----------|---|")
        for m in ordering.get("model_behavioural", []):
            o = m["overall"]
            lines.append(
                f"| {m['model']} | {_fmt(o.get('mean_kendall_tau_distance'), 2)} | "
                f"{_fmt(o.get('exact_match_rate'))} | "
                f"{_fmt(o.get('mean_pairwise_accuracy'))} | {o.get('n')} |"
            )
        lines.append("")
        lines.append("**Probing temporal probes (representation; not behavioural ordering)**")
        lines.append("")
        for p in ordering.get("probing_temporal", []):
            pos = p.get("position_probe") or {}
            pw = p.get("pairwise_probe") or {}
            lines.append(
                f"- `{p['model_key']}` (`{p['probing_run_key']}`): "
                f"position_probe mean acc={_fmt(pos.get('mean_accuracy'))}; "
                f"pairwise_probe mean acc={_fmt(pw.get('mean_accuracy'))} "
                f"(baseline={_fmt(pw.get('baseline_accuracy'))})"
            )
            if pos.get("mean_accuracy_by_condition"):
                parts = ", ".join(
                    f"{c}={_fmt(v)}" for c, v in pos["mean_accuracy_by_condition"].items()
                )
                lines.append(f"  - position by condition: {parts}")
            if pw.get("mean_accuracy_by_condition"):
                parts = ", ".join(
                    f"{c}={_fmt(v)}" for c, v in pw["mean_accuracy_by_condition"].items()
                )
                lines.append(f"  - pairwise by condition: {parts}")
        lines.append("")
        for c in ordering.get("caveats", []):
            lines.append(f"> {c}")
    lines.append("")
    lines.append("Figures: `05_temporal_ordering/` (+ copied model ordering heatmaps in `06_`).")
    lines.append("")

    lines.append("### 6. Model behavioural sweep (key figures)")
    lines.append("")
    lines.append(
        "Instruct models answering human-like prompts "
        f"(`{cfg['model_behavioural']['sweep_id']}`, prompt `{cfg['model_behavioural']['prompt_variant']}`). "
        "Figures are labelled with model id and method=`behavioural_prompt`."
    )
    lines.append("")
    lines.append("See `06_model_behavioural_sweep/`.")
    lines.append("")

    lines.append("### 7. Model probing (key figures)")
    lines.append("")
    lines.append(
        "Base (non-instruct) models; hidden-state probes + probing behavioural sub-arm. "
        "Filenames encode `probing__{model}__{method}__{tag}.png`."
    )
    lines.append("")
    lines.append("See `07_model_probing/`.")
    lines.append("")

    lines.append("### 8. Human comprehension accuracy")
    lines.append("")
    if comp:
        o = comp["overall"]
        lines.append(
            f"Per-story-trial fraction correct on the 6-item comprehension battery "
            f"(canonical selection, n={o['n']}): **{_fmt(o['mean_accuracy'])}**."
        )
        lines.append("")
        lines.append("| Condition | n | Mean accuracy |")
        lines.append("|-----------|---|----------------|")
        for cond in CONDITIONS:
            cell = comp["by_condition"].get(cond, {})
            lines.append(f"| {cond} | {cell.get('n', 'n/a')} | {_fmt(cell.get('mean_accuracy'))} |")
        lines.append("")
        hardest = ", ".join(f"{it['item']} ({_fmt(it['accuracy'])})" for it in comp.get("hardest_items", [])[:5])
        lines.append(f"Hardest items: {hardest}.")
    lines.append("")
    lines.append("Data: `analysis/track_01_human_collection/outputs/comprehension_accuracy.json`.")
    lines.append("")

    lines.append("### 9. Human RDMs stratified by author topology")
    lines.append("")
    if topo:
        lines.append("Human-vs-author alignment grouped by causal-graph shape (`shared/story_sets.TOPOLOGY_FAMILY`):")
        lines.append("")
        lines.append("| Topology family | n | Mean Mantel r | Mean 1−Spearman d |")
        lines.append("|------------------|---|---------------|--------------------|")
        for fam, cell in topo.get("human_vs_author_by_topology", {}).get("by_family", {}).items():
            lines.append(
                f"| {fam} | {cell['n']} | {_fmt(cell['mean_mantel_r'])} | {_fmt(cell['mean_spearman_distance'])} |"
            )
        lines.append("")
        lines.append(
            "> Only 6 stories are in the human pool, so most topology families have "
            "just 1-2 members here — treat as descriptive, not a powered contrast."
        )
    lines.append("")
    lines.append("Data: `analysis/track_02_human_rdm/outputs/by_topology/by_topology.json`.")
    lines.append("")

    lines.append("### 10. Model behavioural sweep — comprehension & pair-scaling vs gold")
    lines.append("")
    if model_behav:
        lines.append("| Model | Comprehension acc. | Pearson r vs gold | Directional acc. | Edge F1 |")
        lines.append("|-------|--------------------|-------------------|-------------------|---------|")
        for m in model_behav.get("per_model", []):
            c = m["comprehension"]["overall_accuracy"]
            p = m["pair_scaling_vs_gold"]["overall"]
            lines.append(
                f"| {m['model']} | {_fmt(c)} | {_fmt(p['mean_pearson_r_vs_gold'])} | "
                f"{_fmt(p['mean_directional_accuracy'])} | {_fmt(p['mean_edge_f1'])} |"
            )
    lines.append("")
    lines.append("Data: `analysis/track_03_model_behavioural/outputs/model_behavioural_summary.json`.")
    lines.append("")

    lines.append("### 11. Three-way summary: human-vs-author ceiling vs model behavioural vs probing")
    lines.append("")
    lines.append(
        "Every arm's pair-scaling RDM compared against the **human aggregated RDM** "
        "on HUMAN_POOL_6 (mean Mantel r; higher = closer to human). "
        "`human_vs_author` is the ceiling reference (how well humans track the gold "
        "graph), not itself a model."
    )
    lines.append("")
    if three_way:
        lines.append("| Condition | Arm | Mean Mantel r | Mean 1−Spearman d |")
        lines.append("|-----------|-----|---------------|--------------------|")
        for cond in CONDITIONS:
            for r in [r for r in three_way.get("rows", []) if r["condition"] == cond]:
                lines.append(
                    f"| {cond} | {r['arm']} | {_fmt(r['mean_mantel_r'])} | {_fmt(r['mean_spearman_distance'])} |"
                )
    lines.append("")
    lines.append(
        "Data: `analysis/track_05_cross_arm/outputs/three_way_summary.{json,csv}` "
        "(also: `pair_scaling_vs_human.json` for the model-behavioural arm alone)."
    )
    lines.append("")

    lines.append("## Story topologies (reference)")
    lines.append("")
    for sid in HUMAN_POOL_6:
        lines.append(f"- `{sid}`: {TOPOLOGY_LABELS.get(sid, '')}")
    lines.append("")

    (MASTER / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    cfg = yaml.safe_load((ANALYSIS_DIR / "configs" / "canonical_runs.yaml").read_text())

    print("== Building master_outputs ==")
    ensure_upstream(args.skip_rerun)

    if MASTER.exists():
        # Keep folder but clear section dirs for a clean rebuild of generated content
        for sec in SECTIONS:
            d = MASTER / sec
            if d.exists():
                shutil.rmtree(d)
    MASTER.mkdir(parents=True, exist_ok=True)
    for sec in SECTIONS:
        (MASTER / sec).mkdir(parents=True, exist_ok=True)

    print("Plotting human / RSA / cross-arm / ordering figures ...")
    collected = {
        "01_human_rdms": plot_human_rdms(MASTER / "01_human_rdms"),
        "02_second_order_rsa": plot_second_order(MASTER / "02_second_order_rsa"),
        "03_human_vs_author": plot_human_vs_author(MASTER / "03_human_vs_author"),
        "04_cross_arm_probing": plot_cross_arm(MASTER / "04_cross_arm_probing"),
        "05_temporal_ordering": plot_ordering(MASTER / "05_temporal_ordering"),
        "06_model_behavioural_sweep": collect_model_behavioural(MASTER / "06_model_behavioural_sweep", cfg),
        "07_model_probing": collect_probing(MASTER / "07_model_probing", cfg),
    }

    inventory = build_inventory(cfg, collected)
    (MASTER / "inventory.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    write_readme(inventory, cfg)

    n_figs = sum(
        len(v) if isinstance(v, list) and (not v or isinstance(v[0], str)) else len(v)
        for v in collected.values()
    )
    print(f"Wrote hub → {MASTER}")
    print(f"  sections={len(SECTIONS)}  collected_entries≈{n_figs}")
    print(f"  README.md + inventory.json updated")
    print(f"  missing items: {len(inventory['missing'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
