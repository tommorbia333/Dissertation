"""Load probing run outputs (vectors, probes, behavioural RDMs).

Resolves run folders via ``analysis/configs/canonical_runs.yaml``.
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


def _load_paths_config(root: Path | None = None) -> dict[str, Any]:
    with open(DEFAULT_CONFIG, encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_probing_run(
    probing_run_key: str = "full_1_5b",
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    """Return the ``probing.runs[<key>]`` entry with absolute ``run_dir``."""
    root = _experiment_root(root)
    cfg = _load_paths_config(root)
    runs = cfg.get("probing", {}).get("runs", {})
    if probing_run_key not in runs:
        raise KeyError(
            f"Unknown probing run key {probing_run_key!r}; "
            f"available: {sorted(runs)}"
        )
    entry = dict(runs[probing_run_key])
    run_dir = Path(entry["run_dir"])
    if not run_dir.is_absolute():
        run_dir = root / run_dir
    entry["run_dir"] = run_dir
    return entry


def load_run_manifest(run_dir: Path) -> dict:
    """Load ``manifest.json`` from an outputs_probing run folder."""
    path = Path(run_dir) / "manifest.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _rdm_npz_path(run_dir: Path, model_key: str) -> Path:
    return Path(run_dir) / model_key / "behavioural" / "rdms" / "model_rdms_for_human.npz"


def load_behavioural_rdms(run_dir: Path, model_key: str) -> dict:
    """Load ``behavioural/rdms/model_rdms_for_human.npz`` for a model.

    Returns a dict with:
      - ``story_keys``: list[str]
      - ``rep_layer``: int | None
      - per-arm stacks under ``{arm}_{condition}`` as float arrays (n_stories, 8, 8)
    """
    path = _rdm_npz_path(run_dir, model_key)
    if not path.exists():
        raise FileNotFoundError(f"Missing probing RDM artefact: {path}")
    with np.load(path, allow_pickle=True) as z:
        out: dict[str, Any] = {
            "path": str(path),
            "story_keys": [str(s) for s in z["story_keys"]],
            "rep_layer": int(z["rep_layer"]) if "rep_layer" in z.files else None,
        }
        for key in z.files:
            if key in ("story_keys", "rep_layer"):
                continue
            out[key] = z[key].astype(float)
    return out


def load_mantel_summary(run_dir: Path, model_key: str) -> dict:
    """Load ``behavioural/rdms/mantel_summary.json``."""
    path = Path(run_dir) / model_key / "behavioural" / "rdms" / "mantel_summary.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_behavioural_rdms_by_key(
    probing_run_key: str = "full_1_5b",
    *,
    root: Path | None = None,
) -> dict:
    """Convenience: resolve canonical run key → behavioural RDM payload."""
    entry = resolve_probing_run(probing_run_key, root=root)
    return load_behavioural_rdms(entry["run_dir"], entry["model_key"])
