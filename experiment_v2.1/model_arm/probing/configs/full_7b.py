"""
Full probing run on the 7B base model, all 8 stories.

This is the run that would not fit on Colab. On a 24 GB M5 (MPS) the 7B loads at
fp16 (~14 GB) with headroom. The behavioural pass is the slow part (~448 pairs x
3 conditions of full forward passes with hidden states) — expect it to be the
dominant cost; run overnight or drop "behavioural" for a representation-only pass.

Run: python run_probing.py full_7b
"""

DESCRIPTION = "Qwen2.5-7B base, all 8 stories, full analysis battery (local, MPS)"

CONFIG = {
    "run_id":       "full_7b",
    "models":       ["qwen7b"],
    "story_ids":    None,
    "conditions":   ["linear", "nonlinear", "atemporal"],
    "analyses":     ["position_probe", "pairwise_probe", "causal_rdm",
                     "causal_rdm_extra", "geometry", "behavioural"],
    "scale_max":    6,
    "rep_layer":    20,
    "n_perm":       1000,
    "skip_existing": True,
}
