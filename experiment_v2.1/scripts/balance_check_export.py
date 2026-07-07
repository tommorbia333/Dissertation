#!/usr/bin/env python3
"""balance_check_export.py — verify condition / story balance in a Cognition export.

Reads a Cognition data export (CSV — one row per trial — or JSON) for the
participant-facing study and reports, per *participant* (not per trial):

  1. Condition counts (target: 20 / 20 / 20 at n = 60).
  2. Assignment-slot (assignment_id, 0..59) usage: which of the 60 slots are
     filled, which are MISSING, and which are DUPLICATED. This is the
     operational view for the run-cleanup workflow described in the README:
     a slot with a non-completing run (no-consent / dropout) shows up as
     "claimed but not completed", and you delete that run in Cognition so the
     slot reopens.
  3. Story read counts (target: 40 each) and the story x condition crosstab
     (target: 13/14 per cell), derived from stimuli/assignments.js.
  4. Consistency + data-quality flags (condition vs assignment_id % 3,
     consent, completion).

By default every participant that appears in the export is counted. Use
--completed-only to restrict to participants who reached the end of the
session (the set you actually keep) — this is the number that should be
exactly 20/20/20.

Usage:
    python3 scripts/balance_check_export.py EXPORT.json
    python3 scripts/balance_check_export.py EXPORT.csv --completed-only
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict

CONDITIONS = ["linear", "nonlinear", "atemporal"]
CYCLE_LENGTH = 60
PARTICIPANT_DOMAINS = [
    "hospital_incident",
    "community_fair",
    "restaurant_fire",
    "school_trip",
    "power_cut",
    "missed_flight",
]
EXCLUDED_DOMAINS = ["care_home_incident", "family_conflict"]

# A participant is treated as "completed" if the export contains any of these
# end-of-session task rows for them.
COMPLETION_TASKS = {"redirect", "debrief"}


# -----------------------------------------------------------------------------
# Loading
# -----------------------------------------------------------------------------

def _load_rows(path):
    """Return a flat list of trial-row dicts from a CSV or JSON export."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        with open(path, newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    if ext == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        # Accept: a flat list of rows, or common nested shapes.
        if isinstance(data, list):
            # list of rows, or list of per-participant {data: [...]} objects
            if data and isinstance(data[0], dict) and "data" in data[0] and isinstance(data[0]["data"], list):
                rows = []
                for rec in data:
                    rows.extend(rec.get("data", []))
                return rows
            return data
        if isinstance(data, dict):
            for key in ("data", "trials", "rows", "results"):
                if isinstance(data.get(key), list):
                    return data[key]
        raise ValueError("Unrecognised JSON structure; expected a list of trial rows.")
    raise ValueError(f"Unsupported file type: {ext!r} (use .csv or .json)")


def _load_assignment_table():
    """Parse ../stimuli/assignments.js into {assignment_id: [stories]}."""
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "stimuli", "assignments.js")
    text = open(path, encoding="utf-8").read()
    payload = json.loads(text.split("var ASSIGNMENTS = ", 1)[1].rstrip(";\n \t\r"))
    table = {}
    for row in payload["assignments"]:
        table[int(row["assignment_id"])] = row["stories"]
    return table


# -----------------------------------------------------------------------------
# Per-participant assembly
# -----------------------------------------------------------------------------

def _coerce_int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _truthy(v):
    if isinstance(v, bool):
        return v
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ("true", "1", "yes"):
        return True
    if s in ("false", "0", "no"):
        return False
    return None


def _mode_nonempty(values):
    """Most common non-empty value, or None."""
    c = Counter(v for v in values if v not in (None, "", "null"))
    return c.most_common(1)[0][0] if c else None


def assemble_participants(rows):
    """Collapse trial rows into one record per participant_id."""
    by_pid = defaultdict(list)
    for r in rows:
        pid = r.get("participant_id")
        if pid in (None, "", "null"):
            continue
        by_pid[pid].append(r)

    participants = {}
    for pid, prows in by_pid.items():
        tasks = {r.get("task") for r in prows}
        # consent_given lives on the consent row.
        consent_vals = [_truthy(r.get("consent_given")) for r in prows]
        consent_vals = [c for c in consent_vals if c is not None]
        consent = consent_vals[0] if consent_vals else None

        assignment_id = _coerce_int(_mode_nonempty([r.get("assignment_id") for r in prows]))
        condition = _mode_nonempty([r.get("condition") for r in prows])

        n_pair_summaries = sum(1 for r in prows if r.get("task") == "pair_scaling_summary")

        participants[pid] = {
            "participant_id": pid,
            "condition": condition,
            "assignment_id": assignment_id,
            "consent": consent,
            "completed": bool(tasks & COMPLETION_TASKS),
            "n_pair_scaling_summaries": n_pair_summaries,
            "n_rows": len(prows),
        }
    return participants


# -----------------------------------------------------------------------------
# Reporting
# -----------------------------------------------------------------------------

def _hdr(title):
    print("\n" + title)
    print("-" * len(title))


def report(participants, table, completed_only):
    pool = list(participants.values())
    total_seen = len(pool)
    if completed_only:
        pool = [p for p in pool if p["completed"]]

    n = len(pool)
    label = "completed" if completed_only else "all"
    print("=" * 60)
    print(f"Balance check — {n} participants counted ({label})")
    if not completed_only:
        n_completed = sum(1 for p in pool if p["completed"])
        print(f"  (of these, {n_completed} reached the end of the session)")
    print(f"  total participant_ids in export: {total_seen}")
    print("=" * 60)

    # --- 1. Condition balance ---
    _hdr("[1] Condition counts (target 20/20/20 at n=60)")
    cond_counts = Counter(p["condition"] for p in pool)
    for c in CONDITIONS:
        print(f"  {c:<12} {cond_counts.get(c, 0)}")
    other = {k: v for k, v in cond_counts.items() if k not in CONDITIONS}
    if other:
        print(f"  UNEXPECTED condition labels: {other}")
    known = [cond_counts.get(c, 0) for c in CONDITIONS]
    spread = (max(known) - min(known)) if known else 0
    print(f"  spread (max-min): {spread}  ->  {'BALANCED' if spread == 0 else 'not yet balanced'}")

    # --- 2. Assignment-slot usage ---
    _hdr("[2] Assignment slots (0..59): fill / missing / duplicate")
    slot_counts = Counter(
        p["assignment_id"] for p in pool if p["assignment_id"] is not None
    )
    missing = [s for s in range(CYCLE_LENGTH) if slot_counts.get(s, 0) == 0]
    duplicated = sorted(s for s, k in slot_counts.items() if k > 1)
    filled_once = sum(1 for s in range(CYCLE_LENGTH) if slot_counts.get(s, 0) == 1)
    print(f"  slots filled exactly once: {filled_once}/60")
    print(f"  slots MISSING ({len(missing)}): {missing if missing else 'none'}")
    if duplicated:
        print("  slots DUPLICATED:")
        for s in duplicated:
            print(f"    slot {s}: {slot_counts[s]} participants")
    else:
        print("  slots duplicated: none")
    bad_slot = _coerce_int  # noqa (kept for clarity)
    out_of_range = sorted(
        s for s in slot_counts if s is None or s < 0 or s >= CYCLE_LENGTH
    )
    if out_of_range:
        print(f"  WARNING out-of-range assignment_id values: {out_of_range}")

    # --- 3. Story reads + story x condition ---
    _hdr("[3] Story reads (target 40 each) and story x condition (target 13/14)")
    story_counts = Counter()
    cell_counts = Counter()
    unmapped = 0
    for p in pool:
        sid_list = table.get(p["assignment_id"])
        if sid_list is None:
            unmapped += 1
            continue
        for s in sid_list:
            story_counts[s] += 1
            if p["condition"] in CONDITIONS:
                cell_counts[(s, p["condition"])] += 1
    for d in PARTICIPANT_DOMAINS:
        print(f"  {d:<22} {story_counts.get(d, 0)}")
    excluded_present = [d for d in EXCLUDED_DOMAINS if story_counts.get(d, 0) > 0]
    if excluded_present:
        print(f"  WARNING excluded domains appear in data: {excluded_present}")
    if unmapped:
        print(f"  ({unmapped} participants had no/unknown assignment_id — not counted here)")
    if cell_counts:
        cell_vals = [
            cell_counts.get((d, c), 0) for d in PARTICIPANT_DOMAINS for c in CONDITIONS
        ]
        print(f"  story x condition cell range: [{min(cell_vals)}, {max(cell_vals)}]")

    # --- 4. Data-quality flags ---
    _hdr("[4] Consistency & data-quality flags")
    mismatches = []
    for p in pool:
        aid, cond = p["assignment_id"], p["condition"]
        if aid is None or cond not in CONDITIONS:
            continue
        expected = CONDITIONS[aid % 3]
        if cond != expected:
            mismatches.append((p["participant_id"], aid, cond, expected))
    if mismatches:
        print(f"  condition vs (assignment_id % 3) MISMATCHES: {len(mismatches)}")
        for pid, aid, got, exp in mismatches[:10]:
            print(f"    {pid}: slot {aid} -> got {got}, expected {exp}")
    else:
        print("  condition <-> assignment_id % 3: all consistent")

    no_consent = [p for p in participants.values() if p["consent"] is False]
    incomplete = [p for p in participants.values() if not p["completed"]]
    print(f"  participants who declined consent (consent_given=false): {len(no_consent)}")
    print(f"  participants who did NOT reach the end of session: {len(incomplete)}")
    if not completed_only and (no_consent or incomplete):
        print("  -> these claimed a Cognition slot; delete their runs in Cognition")
        print("     so the slot reopens (see README: 'Keeping the balance exact').")

    # --- Verdict ---
    _hdr("Verdict")
    ok = (
        completed_only
        and n == CYCLE_LENGTH
        and spread == 0
        and not missing
        and not duplicated
        and not mismatches
        and not excluded_present
    )
    if ok:
        print("  PERFECT: 60 completed, 20/20/20, all 60 slots filled once, consistent.")
    else:
        needs = []
        if n != CYCLE_LENGTH:
            needs.append(f"n={n} (want 60 completed)")
        if spread != 0:
            needs.append(f"condition spread={spread}")
        if missing:
            needs.append(f"{len(missing)} slot(s) still to fill")
        if duplicated:
            needs.append(f"{len(duplicated)} duplicated slot(s)")
        if mismatches:
            needs.append(f"{len(mismatches)} condition mismatch(es)")
        print("  NOT YET COMPLETE: " + "; ".join(needs) if needs else "  see flags above")
    print()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("export", help="Path to the Cognition export (.csv or .json).")
    ap.add_argument(
        "--completed-only",
        action="store_true",
        help="Count only participants who reached the end of the session "
        "(the set you keep; this is what should be exactly 20/20/20).",
    )
    args = ap.parse_args()

    rows = _load_rows(args.export)
    if not rows:
        print("No rows found in export.", file=sys.stderr)
        return 1
    table = _load_assignment_table()
    participants = assemble_participants(rows)
    if not participants:
        print("No participant_id values found in export.", file=sys.stderr)
        return 1
    report(participants, table, args.completed_only)
    return 0


if __name__ == "__main__":
    sys.exit(main())
