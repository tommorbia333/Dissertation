"""
Full probing run for 14B+ models, meant to run on a rented CUDA GPU, not the
local 24GB Apple Silicon box.

qwen14b-base needs ~28GB (fits a 40GB+ GPU); qwen32b-base needs ~64GB (needs
an 80GB GPU with headroom). No code changes are required to run this on CUDA:
``models_probing.pick_device`` / ``pick_dtype`` already auto-detect CUDA and
pick fp16. Just launch on a box with enough VRAM and run:

    cd experiment_v2.1/model_arm/probing
    python run_probing.py cloud_large_models

For 70B-class models (qwen72b-base / llama70b-base) prefer a separate run with
either two 80GB GPUs (``device_map="auto"`` -- would need a small change to
``models_probing.load_model`` to pass ``device_map`` instead of ``.to(dev)``)
or 8-bit quantisation on one 80GB GPU. Not included here by default since it
needs that extra plumbing decision; ask before running 70B+.
"""

DESCRIPTION = "Qwen2.5-14B/32B base, all 8 stories, full battery -- CUDA only"

CONFIG = {
    "run_id":       "cloud_large_models",
    "models":       ["qwen14b-base", "qwen32b-base"],
    "story_ids":    None,
    "conditions":   ["linear", "nonlinear", "atemporal"],
    "analyses":     ["position_probe", "pairwise_probe", "causal_rdm",
                     "causal_rdm_extra", "geometry", "behavioural"],
    "scale_max":    6,
    "rep_layer":    20,
    "n_perm":       1000,
    "device":       "cuda",
    "skip_existing": True,
}
