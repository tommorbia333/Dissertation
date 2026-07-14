"""
Representational / probing arm.

A hidden-state (interpretability) counterpart to the behavioural ``model_arm``.
Where the behavioural arm generates text answers and parses them, this arm pulls
per-event hidden-state vectors out of a base LM and asks what temporal / causal
structure is linearly decodable from them, and how the geometry is organised.

Pipeline (see ``run_probing.py``):
    extract  -> event_vectors.npz          (one reading forward pass per story)
    position_probe / pairwise_probe / causal_rdm / geometry   (consume vectors)
    behavioural                            (prompted rating + prompted state,
                                            three-arm comparison to the author graph)

Everything is config-driven so models, model sizes, story subsets, conditions,
and analysis selection are one-line changes. Outputs are namespaced per model
under a timestamped run directory so results are directly comparable and easy
to line up against the human data later.
"""
