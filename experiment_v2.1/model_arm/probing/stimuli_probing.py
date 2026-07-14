"""
Shared inputs for the probing arm: stimulus parsing, temporal ground truth,
author causal graph, and the pair helpers every probe uses.

This is the single, deduplicated home for logic that the original Colab notebook
repeated in every cell. Nothing here loads a model or touches torch, so it is
cheap to import from analysis code and tests.

Input files (all already in the repo, resolved relative to this file):
    ../../stimuli/narrative_stimuli.txt   parsed into domains x conditions x events
    ../../stimuli/temporal_structure.txt  before/after/concurrent ground truth
    ../../author_intended_graphs.json     author causal graph (RDM target)
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONDITIONS: tuple[str, ...] = ("linear", "nonlinear", "atemporal")
CLASSES: tuple[str, ...] = ("before", "after", "concurrent")
N_EVENTS = 8

# Topology labels per domain key, used to annotate per-story plots.
TOPOLOGY: dict[str, str] = {
    "hospital_incident": "convergent",
    "care_home_incident": "convergent*",
    "community_fair": "three-thread",
    "restaurant_fire": "long chain",
    "school_trip": "fan-out",
    "family_conflict": "chain+feedback",
    "power_cut": "chain+distal",
    "missed_flight": "hourglass",
}

# ---------------------------------------------------------------------------
# Default paths (relative to the repo layout)
# ---------------------------------------------------------------------------

_PKG_DIR = Path(__file__).resolve().parent          # .../model_arm/probing
_EXPERIMENT_DIR = _PKG_DIR.parent.parent            # .../experiment_v2.1

DEFAULT_STIMULI_PATH = _EXPERIMENT_DIR / "stimuli" / "narrative_stimuli.txt"
DEFAULT_TEMPORAL_PATH = _EXPERIMENT_DIR / "stimuli" / "temporal_structure.txt"
DEFAULT_GRAPH_PATH = _EXPERIMENT_DIR / "author_intended_graphs.json"


def normalize_key(name: str) -> str:
    """Domain display name ('Hospital Incident') -> graph key ('hospital_incident')."""
    return name.strip().lower().replace(" ", "_")


# ---------------------------------------------------------------------------
# Stimulus parsing
# ---------------------------------------------------------------------------

_H1 = re.compile(r"^#\s+(.+?)\s*$")                              # domain headers
_VERSION = re.compile(r"^##\s+(Linear|Nonlinear|Atemporal)\s+Version", re.I)
_EVENT = re.compile(r"^\*\*E(\d+)\.\*\*\s*(.+?)\s*$")            # **E1.** text
_NON_DOMAIN_H1 = {"contents", "design overview"}


def parse_stimuli(path: str | Path = DEFAULT_STIMULI_PATH) -> dict:
    """Return {domain: {condition: [(position, text), ...] in presentation order}}.

    Event labels (the '**E1.**' markers) are stripped from the text so the model
    never sees the chronological index written on the page.
    """
    data: dict = {}
    domain = None
    condition = None
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        with open(path, encoding="latin-1") as f:
            lines = f.readlines()

    for raw in lines:
        line = raw.rstrip("\n")

        h1 = _H1.match(line)
        if h1:
            title = h1.group(1).strip()
            domain = None if title.lower() in _NON_DOMAIN_H1 else title
            if domain is not None:
                data.setdefault(domain, {})
            condition = None
            continue

        ver = _VERSION.match(line)
        if ver and domain is not None:
            condition = ver.group(1).lower()
            data[domain][condition] = []
            continue

        ev = _EVENT.match(line)
        if ev and domain is not None and condition is not None:
            data[domain][condition].append((int(ev.group(1)), ev.group(2).strip()))

    return data


def validate(data: dict) -> None:
    """Cheap sanity checks so a silent parse error cannot poison everything.

    Unlike the original notebook this does not hard-require exactly 8 domains,
    so story subsets are allowed; it still enforces 3 conditions x 8 events per
    domain that is present.
    """
    assert data, "no domains parsed"
    for domain, conds in data.items():
        assert set(conds) == set(CONDITIONS), f"{domain}: conditions {set(conds)}"
        for cond, events in conds.items():
            positions = [p for p, _ in events]
            assert len(events) == N_EVENTS, f"{domain}/{cond}: {len(events)} events"
            assert set(positions) == set(range(1, N_EVENTS + 1)), \
                f"{domain}/{cond}: {positions}"
    print(f"validation passed: {len(data)} domains x 3 conditions x {N_EVENTS} events")


def select_domains(data: dict, story_ids: list[str] | None) -> dict:
    """Filter parsed data to the requested story keys (normalized names).

    ``story_ids`` may be graph keys ('hospital_incident') or display names
    ('Hospital Incident'); None keeps everything. Raises if a request is unknown.
    """
    if story_ids is None:
        return data
    wanted = {normalize_key(s) for s in story_ids}
    by_key = {normalize_key(name): name for name in data}
    unknown = wanted - set(by_key)
    if unknown:
        raise KeyError(
            f"unknown story_ids {sorted(unknown)}; available: {sorted(by_key)}"
        )
    return {by_key[k]: data[by_key[k]] for k in sorted(wanted)}


def story_keys_sorted(data: dict) -> list[str]:
    """Deterministic story-id ordering: sorted normalized domain keys.

    The integer story id used throughout the arrays is the index into this list.
    Storing it alongside the vectors removes any dependence on parse order and
    makes arbitrary story subsets safe.
    """
    return sorted(normalize_key(name) for name in data)


def to_story_units(data: dict) -> list[dict]:
    """Flatten to a list of story units (domain x condition) for extraction."""
    units = []
    for domain in data:
        for cond in CONDITIONS:
            units.append({
                "domain": domain,
                "domain_key": normalize_key(domain),
                "condition": cond,
                "events": data[domain][cond],
            })
    return units


# ---------------------------------------------------------------------------
# Temporal ground truth (before / after / concurrent)
# ---------------------------------------------------------------------------

def build_temporal_labels(path: str | Path = DEFAULT_TEMPORAL_PATH) -> dict:
    """{domain_key: {(i, j): 'before'/'after'/'concurrent'}} over positions 1..8.

    Reads chronological time-steps from the temporal-structure file. Events in
    the same step are concurrent; an earlier step is before, a later step after.
    Event En maps to position n.
    """
    labels: dict = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, rhs = line.split(":", 1)
            stages = [chunk.split() for chunk in rhs.split("|")]
            rank = {}
            for r, group in enumerate(stages):
                for ev in group:
                    rank[int(ev.lstrip("Ee"))] = r
            n = len(rank)
            pair = {}
            for i in range(1, n + 1):
                for j in range(1, n + 1):
                    if i == j:
                        continue
                    if rank[i] < rank[j]:
                        pair[(i, j)] = "before"
                    elif rank[i] > rank[j]:
                        pair[(i, j)] = "after"
                    else:
                        pair[(i, j)] = "concurrent"
            labels[key.strip()] = pair
    return labels


# ---------------------------------------------------------------------------
# Author causal graph -> directed RDM
# ---------------------------------------------------------------------------

def rating_map(scale_max: int = 6) -> dict[str, int]:
    """Edge-type -> strength. 6-point uses {causes:6, enables:3}; 3-level uses {2,1}."""
    return {"causes": 6, "enables": 3} if scale_max == 6 else {"causes": 2, "enables": 1}


def build_causal_rdm(path: str | Path = DEFAULT_GRAPH_PATH,
                     scale_max: int = 6) -> dict:
    """{domain_key: 8x8 directed causal-strength matrix} from the author graph."""
    import json
    rating = rating_map(scale_max)
    g = json.load(open(path))
    rdm: dict = {}
    for key, dom in g["domains"].items():
        id2pos = {e["id"]: e["canonical_position"] for e in dom["events"]}
        M = np.zeros((N_EVENTS, N_EVENTS))
        for edge in dom["causal_edges"]:
            i, j = id2pos[edge["source"]], id2pos[edge["target"]]
            M[i - 1, j - 1] = rating.get(edge["type"], 0)
        rdm[key] = M
    return rdm


# ---------------------------------------------------------------------------
# RDM / pair helpers
# ---------------------------------------------------------------------------

def offdiag(M: np.ndarray) -> np.ndarray:
    n = M.shape[0]
    return np.array([M[i, j] for i in range(n) for j in range(n) if i != j])


def pair_index(y_cond: np.ndarray, g_cond: np.ndarray) -> list[tuple]:
    """All ordered within-story pairs as (story_id, row_a, row_b, pos_i, pos_j).

    Positions within a story are unique (1..8), so every ordered a!=b pair is a
    distinct (i, j); the pos_i != pos_j guard is a harmless safety net.
    """
    pairs = []
    for d in np.unique(g_cond):
        rows = np.where(g_cond == d)[0]
        for a in rows:
            for b in rows:
                if a == b:
                    continue
                pos_a, pos_b = int(y_cond[a]), int(y_cond[b])
                if pos_a != pos_b:
                    pairs.append((int(d), int(a), int(b), pos_a, pos_b))
    return pairs


def pair_labels(pairs, labels, g_to_key) -> np.ndarray:
    return np.array([labels[g_to_key[d]][(i, j)] for (d, a, b, i, j) in pairs])


def pair_groups(pairs) -> np.ndarray:
    return np.array([d for (d, a, b, i, j) in pairs])


def pair_features_at_layer(pairs, X_cond, layer) -> np.ndarray:
    """Concatenate the two event vectors: [h_A ; h_B]."""
    return np.stack([np.concatenate([X_cond[a, layer], X_cond[b, layer]])
                     for (d, a, b, i, j) in pairs])


def causal_targets(pairs, author, g_to_key) -> np.ndarray:
    return np.array([author[g_to_key[d]][i - 1, j - 1] for (d, a, b, i, j) in pairs])
