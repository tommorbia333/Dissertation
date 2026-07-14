"""
Model-size sweep: same stimuli and analyses across 0.5B -> 7B.

Loads each model in turn (evicting the previous one), so peak memory is just the
largest single model. Use this for the "does temporal/causal structure sharpen
with scale?" comparison. Representation-only by default (no behavioural) to keep
it tractable; add "behavioural" to ``analyses`` if you want the prompted arm too.

Run: python run_probing.py size_sweep
"""

DESCRIPTION = "Qwen2.5 0.5B/1.5B/3B/7B base, all stories, representation analyses"

CONFIG = {
    "run_id":       "size_sweep",
    "models":       ["qwen0.5b", "qwen1.5b", "qwen3b", "qwen7b"],
    "story_ids":    None,
    "conditions":   ["linear", "nonlinear", "atemporal"],
    "analyses":     ["position_probe", "pairwise_probe", "causal_rdm", "geometry"],
    "scale_max":    6,
    "n_perm":       1000,
    "skip_existing": True,
}
