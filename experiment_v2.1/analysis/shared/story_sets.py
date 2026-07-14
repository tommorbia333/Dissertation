"""Story subsets and topology labels for cross-arm alignment.

Constants mirror ``scripts/build_assignments.py`` (participant pool) and
``author_intended_graphs.json`` (topology metadata).
"""

from __future__ import annotations

# Six domains in the human participant pool (4-of-6 BIBD).
HUMAN_POOL_6: tuple[str, ...] = (
    "hospital_incident",
    "community_fair",
    "restaurant_fire",
    "school_trip",
    "power_cut",
    "missed_flight",
)

# All eight source domains (human pool + model-only replicates).
ALL_8: tuple[str, ...] = HUMAN_POOL_6 + (
    "care_home_incident",
    "family_conflict",
)

# Domains excluded from the participant pool but present in model/probing runs.
MODEL_ONLY: tuple[str, ...] = (
    "care_home_incident",
    "family_conflict",
)

# Author-intended topology strings from author_intended_graphs.json (schema v0.4.0).
TOPOLOGY_LABELS: dict[str, str] = {
    "hospital_incident": "convergent — two enabling threads merge at crisis",
    "care_home_incident": "convergent — structural replicate of hospital_incident",
    "community_fair": "three-thread convergence",
    "restaurant_fire": "long chain — minimal branching, sequential causation",
    "school_trip": "fan-out — early decision diverges into multiple consequences",
    "family_conflict": "chain with feedback — early enabling conditions gain causal weight retroactively",
    "power_cut": "chain with critical distal enabler",
    "missed_flight": "hourglass — independent causes converge, then consequences diverge",
}

CONDITIONS: tuple[str, ...] = ("linear", "nonlinear", "atemporal")

# Coarse topology family for each story, derived from TOPOLOGY_LABELS above.
# Used to stratify RSA/Mantel results by causal-graph shape rather than by
# individual story identity (see track_02_human_rdm/04_by_topology.py).
TOPOLOGY_FAMILY: dict[str, str] = {
    "hospital_incident": "convergent",
    "care_home_incident": "convergent",
    "community_fair": "convergent",
    "restaurant_fire": "chain",
    "power_cut": "chain",
    "family_conflict": "chain",
    "school_trip": "fan_out",
    "missed_flight": "hourglass",
}
