"""Load model behavioural sweep outputs (pair-scaling matrices, meta-RDMs).

Resolves the canonical sweep directory via ``configs/canonical_runs.yaml`` and
reads the per-trial ``parsed/*.json`` artefacts written by the model_arm
runner (one trial folder per model, already averaged over nothing — each
story/condition has one row per seed, so callers usually want the
seed-averaged matrix; see ``aggregate_matrices_by_story_condition``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import yaml

ANALYSIS_DIR = Path(__file__).resolve().parents[2]
EXPERIMENT_ROOT = ANALYSIS_DIR.parent
DEFAULT_CONFIG = ANALYSIS_DIR / "configs" / "canonical_runs.yaml"


def _experiment_root(root: Path | None = None) -> Path:
    return Path(root) if root is not None else EXPERIMENT_ROOT


def _load_cfg(root: Path | None = None) -> dict[str, Any]:
    with open(DEFAULT_CONFIG, encoding="utf-8") as f:
        return yaml.safe_load(f)


def sweep_dir(root: Path | None = None) -> Path:
    root = _experiment_root(root)
    cfg = _load_cfg(root)
    return root / cfg["model_behavioural"]["sweep_dir"]


def list_trials(root: Path | None = None) -> list[Path]:
    """Trial directories that completed (have a manifest.json)."""
    sd = sweep_dir(root)
    if not sd.is_dir():
        return []
    return sorted(t for t in sd.glob("trial_*") if (t / "manifest.json").exists())


def trial_model_label(trial_dir: Path) -> str:
    """Extract a readable model id from a trial folder name.

    Folder naming: ``trial_<YYYYMMDD>_<HHMMSS>_<model-with-dashes>__<prompt>``
    """
    body = trial_dir.name.split("trial_", 1)[-1]
    stamp_model = body.split("__", 1)[0]
    bits = stamp_model.split("_", 2)
    return bits[2] if len(bits) >= 3 else stamp_model


def load_sweep_matrices(trial_dir: Path) -> list[dict]:
    """Load parsed pair-scaling matrices from a sweep trial folder.

    Each dict has keys ``story_id``, ``condition``, ``seed``, ``matrix``
    (8x8, ``None`` on the diagonal) plus per-cell quality metrics
    (``pearson_r_vs_gold``, ``directional_accuracy``, ``edge_f1``, ...), as
    written to ``parsed/pair_scaling_matrices.json``.
    """
    path = trial_dir / "parsed" / "pair_scaling_matrices.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing parsed pair-scaling matrices: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_meta_rdms(trial_dir: Path) -> dict:
    """Load the precomputed meta-RDM JSON from ``parsed/meta_rdms.json``."""
    path = trial_dir / "parsed" / "meta_rdms.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing meta-RDMs: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_comprehension(trial_dir: Path) -> list[dict]:
    path = trial_dir / "parsed" / "comprehension.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing comprehension: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def aggregate_matrices_by_story_condition(
    records: list[dict],
) -> tuple[list[str], dict[str, np.ndarray]]:
    """Mean pair-scaling matrix per (story, condition), averaged over seeds.

    Returns ``(story_keys_sorted, {condition: stack})`` where ``stack`` has
    shape ``(n_stories, 8, 8)``, aligned to ``story_keys_sorted`` — the same
    layout as ``track_02_human_rdm``'s aggregated human RDMs, so the two are
    directly comparable story-by-story.
    """
    by_key: dict[tuple[str, str], list[np.ndarray]] = {}
    conditions: set[str] = set()
    stories: set[str] = set()
    for r in records:
        mat = np.array(r["matrix"], dtype=object)
        mat = np.where(mat == None, np.nan, mat).astype(float)  # noqa: E711
        key = (r["story_id"], r["condition"])
        by_key.setdefault(key, []).append(mat)
        conditions.add(r["condition"])
        stories.add(r["story_id"])

    story_keys = sorted(stories)
    out: dict[str, np.ndarray] = {}
    for cond in sorted(conditions):
        stack = np.full((len(story_keys), 8, 8), np.nan)
        for si, sid in enumerate(story_keys):
            mats = by_key.get((sid, cond))
            if mats:
                stack[si] = np.nanmean(np.stack(mats, axis=0), axis=0)
        out[cond] = stack
    return story_keys, out
