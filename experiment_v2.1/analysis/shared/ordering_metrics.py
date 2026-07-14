"""Shared metrics for chronological ordering (human + model behavioural).

Canonical order is always ``E1..E8``. Metrics:

- Kendall τ distance (0–28): number of pairwise inversions vs canonical
- Exact match: predicted order == canonical
- Pairwise accuracy: fraction of unordered pairs in the correct relative order
"""

from __future__ import annotations

from typing import Sequence

CANONICAL = ("E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8")
N_EVENTS = 8
MAX_KENDALL = N_EVENTS * (N_EVENTS - 1) // 2  # 28


def kendall_tau_distance(order: Sequence[str]) -> int:
    """Bubble-sort / inversion distance from canonical E1..E8."""
    pos = [int(str(e)[1:]) for e in order]
    d = 0
    for i in range(len(pos)):
        for j in range(i + 1, len(pos)):
            if pos[i] > pos[j]:
                d += 1
    return d


def exact_match(order: Sequence[str]) -> bool:
    return tuple(str(e) for e in order) == CANONICAL


def pairwise_accuracy(order: Sequence[str]) -> float:
    """Fraction of unordered pairs whose relative order matches canonical."""
    ids = [str(e) for e in order]
    if len(ids) != N_EVENTS or len(set(ids)) != N_EVENTS:
        return float("nan")
    rank = {e: i for i, e in enumerate(ids)}
    correct = 0
    total = 0
    for i in range(1, N_EVENTS + 1):
        for j in range(i + 1, N_EVENTS + 1):
            ei, ej = f"E{i}", f"E{j}"
            total += 1
            if rank[ei] < rank[ej]:
                correct += 1
    return correct / total if total else float("nan")


def reconstruct_order_from_events(
    initial_order: Sequence[str],
    events: Sequence[dict],
) -> list[str] | None:
    """Replay SortableJS ``drag_end_moved`` events onto ``initial_order``.

    Cognition's CSV export often leaves ``final_order`` empty even when the
    drag trace in ``events`` is complete. Replaying ``from``→``to`` moves
    recovers the submitted order.
    """
    if not initial_order:
        return None
    order = [str(e) for e in initial_order]
    for ev in events or []:
        if ev.get("type") != "drag_end_moved":
            continue
        try:
            frm = int(ev["from"])
            to = int(ev["to"])
        except (KeyError, TypeError, ValueError):
            return None
        if frm < 0 or frm >= len(order) or to < 0 or to > len(order):
            return None
        item = order.pop(frm)
        # Prefer event_id when present; fall back to the item at ``from``.
        eid = ev.get("event_id")
        if eid and item != eid:
            # Indices drifted — abort rather than guess.
            return None
        order.insert(to, item)
    return order


def score_order(order: Sequence[str] | None) -> dict:
    if not order:
        return {
            "kendall_tau_distance": None,
            "exact_match": None,
            "pairwise_accuracy": None,
            "valid": False,
        }
    try:
        order_l = [str(e) for e in order]
        return {
            "kendall_tau_distance": kendall_tau_distance(order_l),
            "exact_match": exact_match(order_l),
            "pairwise_accuracy": pairwise_accuracy(order_l),
            "valid": True,
        }
    except (ValueError, TypeError, KeyError, IndexError):
        return {
            "kendall_tau_distance": None,
            "exact_match": None,
            "pairwise_accuracy": None,
            "valid": False,
        }
