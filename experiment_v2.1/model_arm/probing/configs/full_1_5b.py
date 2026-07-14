"""
Full probing run on the 1.5B base model (the Colab default), all 8 stories.

Runs every reading-pass analysis. Behavioural is included but is the slow part
(prompts all 448 pairs per condition); drop it from ``analyses`` if you only
want the representational studies.

Run: python run_probing.py full_1_5b
"""

DESCRIPTION = "Qwen2.5-1.5B base, all 8 stories, full analysis battery"

CONFIG = {
    "run_id":       "full_1_5b",
    "models":       ["qwen1.5b"],
    "story_ids":    None,                 # all 8 domains
    "conditions":   ["linear", "nonlinear", "atemporal"],
    "analyses":     ["position_probe", "pairwise_probe", "causal_rdm",
                     "causal_rdm_extra", "geometry", "behavioural"],
    "scale_max":    6,
    "rep_layer":    20,                    # clamped to n_layers-1 automatically
    "n_perm":       1000,
    "skip_existing": True,
}
