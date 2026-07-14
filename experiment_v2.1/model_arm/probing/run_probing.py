"""
Config-driven launcher for the probing arm.

Usage:
    python -m model_arm.probing.run_probing <config_name>
    # or, from inside model_arm/probing/:
    python run_probing.py <config_name>

A config is a Python module under ``probing/configs/`` exposing a ``CONFIG`` dict.
Switching model, size, story subset, conditions, or which analyses run is a
one-line edit there. See ``configs/smoke.py`` for the annotated schema.

Output layout (one timestamped run, models namespaced within it):
    outputs_probing/run_<stamp>_<run_id>/
        manifest.json
        <model_key>/
            event_vectors.npz
            position_probe/  pairwise_probe/  causal_rdm/  geometry/
            behavioural/            (+ behavioural/rdms/ for human comparison)

Every model reuses the same stimuli, temporal ground truth and author graph,
so results across models/sizes are directly comparable, and the behavioural arm
mirrors the human directed pair-rating task for later human-vs-model contrasts.
"""

from __future__ import annotations

import importlib
import json
import sys
import warnings
from datetime import datetime
from pathlib import Path

# macOS numpy (Apple Accelerate BLAS) raises spurious "divide by zero" /
# "overflow" / "invalid value ... in matmul" RuntimeWarnings on the
# heavily rank-deficient design matrices the causal-RDM Ridge fits use
# (few underlying event vectors, many linearly dependent pair rows). The
# warnings are cosmetic: results are verified NaN/Inf-free regardless.
# See https://github.com/numpy/numpy/issues/21150.
warnings.filterwarnings("ignore", message=r".*encountered in matmul",
                        category=RuntimeWarning)

# Allow both `python -m model_arm.probing.run_probing` and direct execution.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from model_arm.probing import stimuli_probing as S
    from model_arm.probing import models_probing as M
    from model_arm.probing import extract as E
    from model_arm.probing import probes as P
    from model_arm.probing import geometry as G
    from model_arm.probing import behavioural as B
else:
    from . import stimuli_probing as S
    from . import models_probing as M
    from . import extract as E
    from . import probes as P
    from . import geometry as G
    from . import behavioural as B


ALL_ANALYSES = ("position_probe", "pairwise_probe", "causal_rdm",
                "causal_rdm_extra", "geometry", "behavioural")


def _resolve_analyses(config: dict) -> list[str]:
    raw = config.get("analyses")
    if raw is None:
        return ["position_probe", "pairwise_probe", "causal_rdm", "geometry"]
    unknown = set(raw) - set(ALL_ANALYSES)
    if unknown:
        raise ValueError(f"unknown analyses {sorted(unknown)}; valid: {list(ALL_ANALYSES)}")
    return list(raw)


def _make_run_dir(root: Path, run_id: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = root / f"run_{stamp}_{run_id}"
    run_dir.mkdir()
    return run_dir


def run_config(config: dict) -> Path:
    analyses = _resolve_analyses(config)
    story_ids = config.get("story_ids")           # None = all
    conditions = config.get("conditions", list(S.CONDITIONS))
    scale_max = config.get("scale_max", 6)
    rep_layer = config.get("rep_layer", 20)
    n_perm = config.get("n_perm", G.N_PERM)
    device = config.get("device")
    dtype = config.get("dtype")
    skip_existing = config.get("skip_existing", True)
    outputs_root = Path(config.get("outputs_root",
                                   Path(__file__).resolve().parent.parent / "outputs_probing"))

    # Shared inputs (loaded once; identical across models).
    data_all = S.parse_stimuli(config.get("stimuli_path", S.DEFAULT_STIMULI_PATH))
    data = S.select_domains(data_all, story_ids)
    S.validate(data)
    temporal_labels = S.build_temporal_labels(config.get("temporal_path", S.DEFAULT_TEMPORAL_PATH))
    author = S.build_causal_rdm(config.get("graph_path", S.DEFAULT_GRAPH_PATH), scale_max)

    run_dir = _make_run_dir(outputs_root, config["run_id"])
    print(f"\nrun dir: {run_dir}")
    print(f"analyses: {analyses}")
    print(f"stories:  {S.story_keys_sorted(data)}")
    print(f"conditions: {conditions}\n")

    manifest = {
        "run_id": config["run_id"],
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "models": config["models"],
        "analyses": analyses,
        "story_keys": S.story_keys_sorted(data),
        "conditions": conditions,
        "scale_max": scale_max,
        "rep_layer": rep_layer,
        "n_perm": n_perm,
    }

    per_model = []
    for spec in config["models"]:
        model_key, model_id = M.resolve_model(spec)
        mdir = run_dir / model_key
        mdir.mkdir(parents=True, exist_ok=True)
        print("=" * 70)
        print(f"MODEL {model_key}  ({model_id})")
        print("=" * 70)

        vectors_path = mdir / "event_vectors.npz"
        needs_vectors = any(a != "behavioural" for a in analyses) or "behavioural" in analyses
        need_model_load = ("behavioural" in analyses) or not (skip_existing and vectors_path.exists())

        tok = model = dev = None
        if need_model_load:
            tok, model, dev = M.load_model(model_id, device=device, dtype=dtype)
            print(f"loaded on {dev}")

        # Reading-pass vectors (every non-behavioural analysis consumes these).
        if needs_vectors:
            if skip_existing and vectors_path.exists():
                print(f"reusing {vectors_path}")
                X, y, g, story_keys, g_to_key = E.load_vectors(vectors_path)
            else:
                X, y, g, story_keys, g_to_key = E.run_extraction(tok, model, dev, data, vectors_path)
        else:
            X, y, g, story_keys, g_to_key = E.load_vectors(vectors_path)

        if "position_probe" in analyses:
            print("\n--- position probe ---")
            P.position_probe(X, y, g, mdir / "position_probe")
        if "pairwise_probe" in analyses:
            print("\n--- pairwise probe ---")
            P.pairwise_probe(X, y, g, temporal_labels, g_to_key, mdir / "pairwise_probe")
        if "causal_rdm" in analyses:
            print("\n--- causal RDM ---")
            P.causal_rdm(X, y, g, author, g_to_key, mdir / "causal_rdm")
        if "causal_rdm_extra" in analyses:
            print("\n--- causal RDM (diagnostic metrics) ---")
            P.causal_rdm_extra(X, y, g, author, g_to_key, mdir / "causal_rdm")
        if "geometry" in analyses:
            print("\n--- geometry / cyclicity ---")
            G.run_geometry(X, y, g, g_to_key, mdir / "geometry", n_perm=n_perm)
        if "behavioural" in analyses:
            print("\n--- behavioural + prompted state ---")
            bdir = mdir / "behavioural"
            bdir.mkdir(parents=True, exist_ok=True)
            behav_path = bdir / "behavioural.npz"
            if not (skip_existing and behav_path.exists()):
                B.run_behavioural(tok, model, dev, data, g_to_key, behav_path, scale_max)
            B.analyse_three_arms(behav_path, vectors_path, author, g_to_key, bdir, rep_layer)

        per_model.append({"model_key": model_key, "model_id": model_id, "dir": str(mdir)})

        # Free GPU/unified memory before the next model.
        if model is not None:
            _evict(model)

    manifest["per_model"] = per_model
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nDONE. run dir: {run_dir}")
    return run_dir


def _evict(model):
    import gc
    try:
        model.to("cpu")
    except Exception:
        pass
    del model
    gc.collect()
    try:
        import torch
        if hasattr(torch, "mps") and hasattr(torch.mps, "empty_cache"):
            torch.mps.empty_cache()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def _list_configs() -> list[str]:
    cfg_dir = Path(__file__).resolve().parent / "configs"
    return sorted(p.stem for p in cfg_dir.glob("*.py") if p.stem != "__init__")


def main():
    if len(sys.argv) != 2:
        print("Usage: python run_probing.py <config_name>\n\nAvailable configs:")
        for name in _list_configs():
            print(f"  {name}")
        sys.exit(1)

    config_name = sys.argv[1]
    mod_name = (f"model_arm.probing.configs.{config_name}"
                if __package__ in (None, "") else f".configs.{config_name}")
    try:
        if __package__ in (None, ""):
            config_module = importlib.import_module(mod_name)
        else:
            config_module = importlib.import_module(mod_name, package=__package__)
    except ImportError as e:
        print(f"ERROR: could not load config '{config_name}': {e}\n\nAvailable configs:")
        for name in _list_configs():
            print(f"  {name}")
        sys.exit(1)

    print(f"\nLoaded config: {config_name}")
    if hasattr(config_module, "DESCRIPTION"):
        print(f"Description:   {config_module.DESCRIPTION}")
    run_config(config_module.CONFIG)


if __name__ == "__main__":
    main()
