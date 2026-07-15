"""
Post-hoc runner for ``behavioural.prompted_causal_mantel_by_layer``.

Backfills the prompted-state layer-sweep plot/npz for probing runs that
completed *before* that analysis existed. Reads only cached ``.npz`` outputs
already on disk (``event_vectors.npz`` for ``g_to_key``, ``behavioural.npz``
for the prompted hidden states, ``causal_rdm/causal_extra_metrics.npz`` for
the reading-arm overlay) — no model reload, no re-generation.

Usage:
    python rerun_prompted_by_layer.py <model_dir> [<model_dir> ...]

where each <model_dir> is e.g.
    outputs_probing/run_20260709_131857_full_1_5b/qwen1.5b
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from model_arm.probing import stimuli_probing as S
    from model_arm.probing import extract as E
    from model_arm.probing import behavioural as B
else:
    from . import stimuli_probing as S
    from . import extract as E
    from . import behavioural as B

import numpy as np


def rerun_one(model_dir: Path, scale_max: int = 6) -> None:
    behav_path = model_dir / "behavioural" / "behavioural.npz"
    vectors_path = model_dir / "event_vectors.npz"
    if not behav_path.exists():
        print(f"SKIP {model_dir.name}: no behavioural.npz (arm never completed)")
        return
    if not vectors_path.exists():
        print(f"SKIP {model_dir.name}: no event_vectors.npz (need it for g_to_key)")
        return

    _, _, _, _, g_to_key = E.load_vectors(vectors_path)
    author = S.build_causal_rdm(S.DEFAULT_GRAPH_PATH, scale_max)

    extra_path = model_dir / "causal_rdm" / "causal_extra_metrics.npz"
    reading_spearman = None
    if extra_path.exists():
        extra = np.load(extra_path)
        reading_spearman = {c: extra[f"spearman_{c}"] for c in S.CONDITIONS
                            if f"spearman_{c}" in extra}
    else:
        print(f"  (no causal_extra_metrics.npz for {model_dir.name} -> plotting prompted alone)")

    print(f"\n{'=' * 70}\n{model_dir.name}\n{'=' * 70}")
    bdir = model_dir / "behavioural"
    B.prompted_causal_mantel_by_layer(behav_path, author, g_to_key, bdir, reading_spearman)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python rerun_prompted_by_layer.py <model_dir> [<model_dir> ...]")
        return 1
    for arg in sys.argv[1:]:
        rerun_one(Path(arg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
