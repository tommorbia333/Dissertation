"""
Full probing run on a handful of additional models, all 8 stories, full battery.

Extends the existing full_1_5b / full_7b runs with:
  - qwen0.5b        Qwen2.5-0.5B base  -- fills in the bottom of the size ladder
  - qwen3b          Qwen2.5-3B base    -- fills in the middle of the size ladder
  - qwen3-8b-base   Qwen3-8B-Base      -- next-gen Qwen architecture, ~7B scale
  - mistral7b       Mistral-7B-v0.3    -- cross-family comparison, ~7B scale
                                          (GATED on HF -- accept the licence at
                                          huggingface.co/mistralai/Mistral-7B-v0.3
                                          with the account behind your local HF
                                          token before running this)

Models are evicted one at a time so peak memory is just the largest single
model (~16 GB for qwen3-8b-base/mistral7b at fp16). Run overnight: the
behavioural sub-arm (448 pairs x 3 conditions x 4 models) is the slow part.

Run: python run_probing.py full_additional_models
"""

DESCRIPTION = "Qwen2.5-0.5B/3B, Qwen3-8B-Base, Mistral-7B-v0.3 -- all 8 stories, full battery"

CONFIG = {
    "run_id":       "full_additional_models",
    "models":       ["qwen0.5b", "qwen3b", "qwen3-8b-base", "mistral7b"],
    "story_ids":    None,                 # all 8 domains
    "conditions":   ["linear", "nonlinear", "atemporal"],
    "analyses":     ["position_probe", "pairwise_probe", "causal_rdm",
                     "causal_rdm_extra", "geometry", "behavioural"],
    "scale_max":    6,
    "rep_layer":    20,                    # clamped to n_layers-1 automatically per model
    "n_perm":       1000,
    "skip_existing": True,
}
