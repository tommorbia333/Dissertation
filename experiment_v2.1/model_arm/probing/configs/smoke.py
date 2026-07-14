"""
Smoke test: smallest model, 2 stories, fast analyses only.

Purpose: verify the whole probing pipeline runs end-to-end on this machine
(model load on MPS, extraction, probes, plots, output layout) before committing
to a full run. Skips the expensive behavioural prompting pass and geometry
permutation null.

Run: python run_probing.py smoke      (from model_arm/probing/)
"""

DESCRIPTION = "End-to-end plumbing check: qwen0.5b, 2 stories, position+causal probes"

# --- The knobs you will actually change between runs -------------------------
# models      : registry keys (see models_probing.PROBING_MODELS) or raw HF ids.
# story_ids   : None = all 8 domains; or a subset (keys or display names).
# conditions  : any subset of ("linear", "nonlinear", "atemporal").
# analyses    : any subset of ("position_probe", "pairwise_probe", "causal_rdm",
#               "causal_rdm_extra", "geometry", "behavioural").
CONFIG = {
    "run_id":       "smoke",
    "models":       ["qwen0.5b"],
    "story_ids":    ["hospital_incident", "missed_flight"],
    "conditions":   ["linear", "nonlinear", "atemporal"],
    "analyses":     ["position_probe", "causal_rdm"],
    "scale_max":    6,
    "skip_existing": True,
}
