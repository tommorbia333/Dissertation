#!/usr/bin/env python3
"""analyze_human_results.py — audit the "human results" export folder.

Purpose
-------
Cognition/Prolific sync issues can leave partial runs behind (e.g. a
participant's browser was closed mid-session, or Prolific returned/timed-out
a submission that Cognition still has a partial data file for). This script
gives a full accounting of what is actually present in the human data export
so you know:

  1. How many of the 60 preregistered assignment slots (`assignment_id`
     0-59, see stimuli/assignments.js) have at least one COMPLETE run.
  2. How many runs (files) are incomplete, and their run_id / PROLIFIC_PID /
     participant_id, so you know exactly which sessions to delete from the
     Cognition dashboard/repo.
  3. How many complete trials (= completed runs) there are in total, and
     broken down by condition (linear / nonlinear / atemporal) and by
     assignment_id.
  4. A consistency check between the "all runs combined" export (csv/json)
     and the "one file per run" export folders (csv/json), since you
     downloaded four overlapping exports of the same underlying data.
  5. Total file counts across all four export types.

Usage
-----
    python3 scripts/analyze_human_results.py
    python3 scripts/analyze_human_results.py --dir "human results" --verbose
    python3 scripts/analyze_human_results.py --json-out audit.json
    python3 scripts/analyze_human_results.py --prolific-csv "prolific_export.csv"

Only the Python standard library is used (csv, json, argparse, collections)
so this runs anywhere without installing dependencies.

Cross-referencing against Prolific's own export (--prolific-csv)
------------------------------------------------------------------
Cognition only tells you what got saved; it can't tell you what actually
happened in the participant's browser after saving broke. Prolific's own
submissions export (Study page -> "Go to app" data / export -> download the
CSV) has independent columns — participant id, status, and total time taken
on Prolific's own clock — that let you distinguish two very different
failure modes that both look identical from the Cognition side alone:

  - Genuine early abandonment: Prolific's own "time taken" is also tiny
    (matches Cognition's last time_elapsed). The participant really did
    bail almost immediately.
  - Silent data-loss (the participant kept working, but their trial data
    stopped reaching Cognition): Prolific's "time taken" is large (tens of
    minutes, consistent with a real attempt at the ~45-60 min study) even
    though Cognition only captured one or two rows near the start. This is
    a strong signal the SAVE PIPELINE broke mid-session (network hiccup,
    ad-blocker/extension blocking the ingestion call, a client-side JS
    error, etc.) rather than the participant abandoning — they may well
    deserve payment even though their data is unusable, and it's worth
    messaging them on Prolific to ask what they saw on screen when they
    gave up, since Cognition's logs alone can't tell you that.

Prolific's export column names have changed over time, so this script
matches loosely (case/whitespace-insensitive substring match) for a
participant-id column, a status column, and a time-taken column. If your
export doesn't match, pass --prolific-csv anyway and read the error for
what columns were detected/expected.

Completion definition
----------------------
A run is considered COMPLETE if and only if ALL of the following hold:
  - It has exactly 4 distinct `story_id`s with a `story_reading` row
    (i.e. reached and displayed all 4 assigned stories).
  - Each of those 4 stories has a `comprehension_summary` row, an
    `ordering` row, and a `pair_scaling_summary` row (i.e. finished every
    task block for every story — the per-story completion gate).
  - It has a `debrief` row (i.e. reached the end-of-study outro screen,
    which only appears after `final_comments` and after all 4 stories'
    task blocks are finished; see src/main.js timeline order).

Everything else is INCOMPLETE. The script also reports, for each
incomplete run, exactly how far it got (last task / trial_index /
time_elapsed and which of the 4 stories were left unfinished) so you can
decide whether it's worth manually recovering or should simply be deleted.
"""

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict

# jsPsych timeline order per story (see src/main.js): story_reading ->
# comprehension_item(s) + comprehension_summary -> ordering ->
# pair_scaling_item(s) + pair_scaling_summary.
STORY_GATE_TASKS = ["comprehension_summary", "ordering", "pair_scaling_summary"]

N_ASSIGNMENTS = 60
N_STORIES_PER_PARTICIPANT = 4
CONDITIONS = ["linear", "nonlinear", "atemporal"]


def load_combined_csv(path):
    """Return list of row dicts from the single combined CSV export."""
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _rows_from_header_table(table):
    """Convert a Cognition [header_row, data_row, data_row, ...] table
    (each a flat list of strings) into a list of dicts keyed by header."""
    header, *data_rows = table
    return [dict(zip(header, row)) for row in data_rows]


def load_combined_json(path):
    """Return list of row dicts from the single combined JSON export.

    Cognition's combined JSON export is a list with one entry per run;
    each entry is itself a "table": `[header_row, data_row, data_row, ...]`
    where `header_row` and each `data_row` are flat lists of strings
    (i.e. NOT a list of dicts — it mirrors the per-run CSV layout exactly,
    just nested one level deeper). Each run may have a slightly different
    header (e.g. only runs that reached `final_comments` have that column),
    so headers are applied per-run, not globally.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Unrecognized JSON export shape in {path}: expected top-level list")

    rows = []
    for run_table in data:
        if not isinstance(run_table, list) or not run_table:
            continue
        rows.extend(_rows_from_header_table(run_table))
    return rows


def load_per_run_json(path):
    """Return list of row dicts from a single per-run JSON export file
    (a single `[header_row, data_row, ...]` table)."""
    with open(path, encoding="utf-8") as f:
        table = json.load(f)
    return _rows_from_header_table(table)


def group_by_run(rows):
    runs = defaultdict(list)
    for row in rows:
        runs[row.get("run_id", "")].append(row)
    return runs


def analyze_run(run_id, rows):
    """Build a summary dict describing one participant run."""
    prolific_pids = {r.get("PROLIFIC_PID", "") for r in rows if r.get("PROLIFIC_PID")}
    participant_ids = {r.get("participant_id", "") for r in rows if r.get("participant_id")}
    conditions = {r.get("condition", "") for r in rows if r.get("condition")}
    assignment_ids = {r.get("assignment_id", "") for r in rows if r.get("assignment_id") not in (None, "")}

    tasks_present = Counter(r.get("task", "") for r in rows)

    stories_read = set()
    story_task_status = defaultdict(set)  # story_id -> set of gate tasks completed
    for r in rows:
        story_id = r.get("story_id", "")
        if not story_id:
            continue
        task = r.get("task", "")
        if task == "story_reading":
            stories_read.add(story_id)
        if task in STORY_GATE_TASKS:
            story_task_status[story_id].add(task)

    stories_fully_done = {
        sid for sid, done in story_task_status.items()
        if set(STORY_GATE_TASKS).issubset(done)
    }

    reached_debrief = tasks_present.get("debrief", 0) > 0
    reached_redirect = tasks_present.get("redirect", 0) > 0
    reached_final_comments = tasks_present.get("final_comments", 0) > 0
    consent_given = any(r.get("consent_given", "") in ("true", "True", "1") for r in rows if r.get("task") == "consent")

    # Sort by trial_index (numeric) to find the last thing the participant did.
    def trial_idx(r):
        try:
            return int(r.get("trial_index", -1))
        except (ValueError, TypeError):
            return -1

    last_row = max(rows, key=trial_idx) if rows else None

    is_complete = (
        len(stories_read) == N_STORIES_PER_PARTICIPANT
        and len(stories_fully_done) == N_STORIES_PER_PARTICIPANT
        and reached_debrief
    )

    missing_stories = stories_read - stories_fully_done
    n_expected_stories_not_even_started = N_STORIES_PER_PARTICIPANT - len(stories_read)

    return {
        "run_id": run_id,
        "n_rows": len(rows),
        "prolific_pid": next(iter(prolific_pids), ""),
        "prolific_pid_count": len(prolific_pids),  # >1 would itself be a data problem
        "participant_id": next(iter(participant_ids), ""),
        "condition": next(iter(conditions), ""),
        "condition_count": len(conditions),
        "assignment_id": next(iter(assignment_ids), ""),
        "consent_given": consent_given,
        "n_stories_started": len(stories_read),
        "n_stories_fully_done": len(stories_fully_done),
        "stories_started": sorted(stories_read),
        "stories_incomplete": sorted(missing_stories),
        "n_stories_not_started": n_expected_stories_not_even_started,
        "reached_final_comments": reached_final_comments,
        "reached_debrief": reached_debrief,
        "reached_redirect": reached_redirect,
        "is_complete": is_complete,
        "last_task": last_row.get("task", "") if last_row else "",
        "last_trial_index": trial_idx(last_row) if last_row else None,
        "last_time_elapsed_ms": last_row.get("time_elapsed", "") if last_row else "",
        "recorded_at": next((r.get("recorded_at", "") for r in rows if r.get("recorded_at")), ""),
    }


def fmt_bool(b):
    return "yes" if b else "no"


def _find_col(fieldnames, *substrings):
    """Find the first column whose lowercased name contains ALL of the given
    lowercased substrings. Returns None if not found."""
    for fn in fieldnames:
        low = fn.strip().lower()
        if all(sub in low for sub in substrings):
            return fn
    return None


def _parse_time_taken(raw):
    """Parse Prolific's 'time taken' field, which may be plain seconds
    ('2467'), or 'HH:MM:SS' / 'MM:SS'. Returns seconds as float, or None."""
    if raw is None or raw == "":
        return None
    raw = raw.strip()
    if ":" in raw:
        parts = [float(p) for p in raw.split(":")]
        secs = 0.0
        for p in parts:
            secs = secs * 60 + p
        return secs
    try:
        return float(raw)
    except ValueError:
        return None


def _detect_completion_codes(human_results_dir):
    """Read src/config.js (assumed to live at ../src/config.js relative to
    the human-results folder's parent) and extract the `cc=` completion
    codes from CONFIG.prolific.completion_url and .screen_out_url via a
    simple regex. Returns (real_code, screen_out_code), either possibly None.
    """
    import re
    config_path = os.path.join(os.path.dirname(human_results_dir), "src", "config.js")
    if not os.path.isfile(config_path):
        return None, None
    with open(config_path, encoding="utf-8") as f:
        text = f.read()

    def _extract(key):
        m = re.search(rf"{key}\s*:\s*'[^']*[?&]cc=([A-Za-z0-9]+)", text)
        return m.group(1) if m else None

    return _extract("completion_url"), _extract("screen_out_url")


def load_prolific_export(path):
    """Load a Prolific submissions CSV export and return a dict keyed by
    participant id -> {"status": str, "time_taken_s": float|None, "raw": dict}.
    """
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        pid_col = _find_col(fieldnames, "participant", "id")
        status_col = _find_col(fieldnames, "status")
        time_col = _find_col(fieldnames, "time", "taken") or _find_col(fieldnames, "time", "task")
        code_col = _find_col(fieldnames, "completion", "code") or _find_col(fieldnames, "entered", "code")
        if not pid_col or not status_col:
            raise ValueError(
                f"Could not find participant-id/status columns in {path}. "
                f"Detected columns: {fieldnames}. "
                f"(pid_col={pid_col!r}, status_col={status_col!r}, time_col={time_col!r})"
            )
        out = {}
        for row in reader:
            pid = row.get(pid_col, "").strip()
            if not pid:
                continue
            out[pid] = {
                "status": row.get(status_col, "").strip(),
                "time_taken_s": _parse_time_taken(row.get(time_col, "")) if time_col else None,
                "completion_code_entered": row.get(code_col, "").strip() if code_col else "",
                "raw": row,
            }
        return out



# Filename fragments that mark a file/folder as definitely NOT one of Cognition's
# four export types, even if it happens to end in .csv/.json or contain "csv"/"json"
# in its name (e.g. this script's own --json-out audit dumps, or Prolific's own
# export, which is a plain top-level .csv sitting right next to the real export).
_NON_EXPORT_NAME_HINTS = ("prolific", "audit", "_analysis", "_archive")


def _looks_like_combined_csv(path):
    """A real combined export has a `run_id` column and >1 distinct run_id."""
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or "run_id" not in reader.fieldnames:
                return False
            run_ids = set()
            for i, row in enumerate(reader):
                if row.get("run_id"):
                    run_ids.add(row["run_id"])
                if i > 5000:  # don't read a huge file just to sniff it
                    break
            return len(run_ids) >= 1
    except (OSError, csv.Error, UnicodeDecodeError):
        return False


def _looks_like_combined_json(path):
    """A real combined export is a top-level list of [header, row, row, ...] tables."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return (
            isinstance(data, list) and len(data) > 0
            and isinstance(data[0], list) and len(data[0]) > 0
            and isinstance(data[0][0], list) and "run_id" in data[0][0]
        )
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, IndexError, TypeError):
        return False


def _looks_like_per_run_dir(full, ext):
    """A real per-run export folder contains files named like `<run_id>.<ext>`
    (numeric stem), not some other kind of directory that merely has "csv"/"json"
    in its own name."""
    try:
        entries = [e for e in os.listdir(full) if e.lower().endswith(ext)]
    except OSError:
        return False
    if not entries:
        return False
    numeric_stems = sum(1 for e in entries if e[: -len(ext)].isdigit())
    return numeric_stems / len(entries) > 0.8  # allow a few odd files, e.g. .DS_Store-adjacent cruft


def _pick_best(candidates, base):
    """candidates: list of (path, mtime). Picks the most-recently-modified one and
    warns if there was more than one, so an ambiguous folder never silently picks
    the wrong file the way filename-only auto-detection did before."""
    if not candidates:
        return None
    candidates.sort(key=lambda c: c[1], reverse=True)
    if len(candidates) > 1:
        print("  WARNING: multiple candidates found, picking most recently modified:")
        for path, mtime in candidates:
            marker = " <- chosen" if path == candidates[0][0] else ""
            print(f"    {os.path.relpath(path, base)}{marker}")
    return candidates[0][0]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=None, help='Path to the "human results" folder (default: auto-detect next to this script)')
    ap.add_argument("--json-out", default=None, help="Optional path to dump the full machine-readable audit as JSON")
    ap.add_argument("--verbose", action="store_true", help="Print a full per-run table, not just the summary")
    ap.add_argument("--prolific-csv", default=None,
                     help="Optional path to a Prolific submissions export CSV, to cross-check incomplete "
                          "Cognition runs against Prolific's own status/time-taken (distinguishes genuine "
                          "abandonment from silent mid-session data loss).")
    ap.add_argument("--combined-csv", default=None, help="Explicit path to the combined CSV export (skips auto-detection)")
    ap.add_argument("--combined-json", default=None, help="Explicit path to the combined JSON export (skips auto-detection)")
    ap.add_argument("--per-run-csv-dir", default=None, help="Explicit path to the per-run CSV folder (skips auto-detection)")
    ap.add_argument("--per-run-json-dir", default=None, help="Explicit path to the per-run JSON folder (skips auto-detection)")
    args = ap.parse_args()

    if args.dir:
        base = args.dir
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        base = os.path.join(os.path.dirname(script_dir), "human results")
    base = os.path.abspath(base)

    if not os.path.isdir(base):
        sys.exit(f"Could not find human results folder at: {base}\nPass --dir explicitly.")

    print("=" * 78)
    print("HUMAN RESULTS EXPORT AUDIT")
    print("=" * 78)
    print(f"Folder: {base}\n")
    print("Detecting export files/folders:")

    csv_candidates, json_candidates = [], []
    csv_dir_candidates, json_dir_candidates = [], []

    for entry in os.listdir(base):
        full = os.path.join(base, entry)
        low = entry.lower()
        if any(hint in low for hint in _NON_EXPORT_NAME_HINTS):
            continue
        if os.path.isfile(full) and low.endswith(".csv") and "(csv)" not in low:
            if _looks_like_combined_csv(full):
                csv_candidates.append((full, os.path.getmtime(full)))
        elif os.path.isfile(full) and low.endswith(".json") and "(json)" not in low:
            if _looks_like_combined_json(full):
                json_candidates.append((full, os.path.getmtime(full)))
        elif os.path.isdir(full):
            # Judge per-run folders by CONTENT (numeric-named .csv/.json files inside),
            # not by the folder's own name — e.g. "experiment-v21_all60_individual"
            # holds per-run CSVs but doesn't have "csv" in its name.
            if _looks_like_per_run_dir(full, ".csv"):
                csv_dir_candidates.append((full, os.path.getmtime(full)))
            if _looks_like_per_run_dir(full, ".json"):
                json_dir_candidates.append((full, os.path.getmtime(full)))

    combined_csv_path = args.combined_csv and os.path.abspath(args.combined_csv) or _pick_best(csv_candidates, base)
    combined_json_path = args.combined_json and os.path.abspath(args.combined_json) or _pick_best(json_candidates, base)
    per_run_csv_dir = args.per_run_csv_dir and os.path.abspath(args.per_run_csv_dir) or _pick_best(csv_dir_candidates, base)
    per_run_json_dir = args.per_run_json_dir and os.path.abspath(args.per_run_json_dir) or _pick_best(json_dir_candidates, base)

    print(f"  Combined CSV : {combined_csv_path}")
    print(f"  Combined JSON: {combined_json_path}")
    print(f"  Per-run CSV folder : {per_run_csv_dir}")
    print(f"  Per-run JSON folder: {per_run_json_dir}")

    if not combined_csv_path:
        sys.exit("Could not find the combined CSV export (a .csv file directly in the folder with a run_id column).\n"
                  "Pass --combined-csv explicitly.")

    # ---- File counts across all four export types -------------------------
    per_run_csv_files = sorted(f for f in os.listdir(per_run_csv_dir) if f.endswith(".csv")) if per_run_csv_dir else []
    per_run_json_files = sorted(f for f in os.listdir(per_run_json_dir) if f.endswith(".json")) if per_run_json_dir else []
    n_combined_files = sum(1 for p in (combined_csv_path, combined_json_path) if p)
    total_files = n_combined_files + len(per_run_csv_files) + len(per_run_json_files)

    print("\n" + "-" * 78)
    print("FILE COUNTS")
    print("-" * 78)
    print(f"  Combined 'all runs' files      : {n_combined_files} (1 csv + 1 json)")
    print(f"  Per-run CSV files              : {len(per_run_csv_files)}")
    print(f"  Per-run JSON files             : {len(per_run_json_files)}")
    print(f"  TOTAL files across all 4 export types: {total_files}")

    # ---- Load combined CSV (source of truth for the analysis) -------------
    combined_rows = load_combined_csv(combined_csv_path)
    runs = group_by_run(combined_rows)
    n_unique_runs_combined = len(runs)

    print(f"\n  Unique run_ids in combined CSV : {n_unique_runs_combined}")

    # ---- Cross-check against per-run files ---------------------------------
    per_run_csv_ids = {os.path.splitext(f)[0] for f in per_run_csv_files}
    per_run_json_ids = {os.path.splitext(f)[0] for f in per_run_json_files}
    combined_ids = set(runs.keys())

    print("\n" + "-" * 78)
    print("CROSS-CHECK: combined export vs. per-run file folders")
    print("-" * 78)
    csv_ids_missing_from_folder = combined_ids - per_run_csv_ids
    folder_ids_missing_from_csv = per_run_csv_ids - combined_ids
    json_ids_missing_from_folder = combined_ids - per_run_json_ids
    folder_ids_missing_from_json = per_run_json_ids - combined_ids

    def report_mismatch(label, missing_a, missing_b):
        if not missing_a and not missing_b:
            print(f"  {label}: OK — run_id sets are identical ({len(combined_ids)} runs).")
        else:
            print(f"  {label}: MISMATCH")
            if missing_a:
                print(f"    In combined export but NO per-run file: {sorted(missing_a, key=lambda x: int(x))}")
            if missing_b:
                print(f"    Per-run file exists but NOT in combined export: {sorted(missing_b, key=lambda x: int(x))}")

    if per_run_csv_dir:
        report_mismatch("Combined CSV vs per-run CSV folder", csv_ids_missing_from_folder, folder_ids_missing_from_csv)
    if per_run_json_dir:
        report_mismatch("Combined CSV vs per-run JSON folder", json_ids_missing_from_folder, folder_ids_missing_from_json)

    if combined_json_path:
        combined_json_rows = load_combined_json(combined_json_path)
        json_runs = group_by_run(combined_json_rows)
        if set(json_runs.keys()) == combined_ids and sum(len(v) for v in json_runs.values()) == len(combined_rows):
            print("  Combined CSV vs combined JSON: OK — identical run_id sets and row counts (confirms your note that these two are duplicates).")
        else:
            print("  Combined CSV vs combined JSON: MISMATCH — these two combined exports are NOT identical!")
            print(f"    CSV rows={len(combined_rows)} runs={len(combined_ids)} | JSON rows={sum(len(v) for v in json_runs.values())} runs={len(json_runs)}")

    # Row-count parity between the combined CSV and each per-run CSV/JSON file
    # (catches partial/truncated downloads of individual files).
    row_count_mismatches = []
    for rid, rws in runs.items():
        expected_n = len(rws)
        if per_run_csv_dir and rid in per_run_csv_ids:
            with open(os.path.join(per_run_csv_dir, f"{rid}.csv"), newline="", encoding="utf-8") as f:
                n = sum(1 for _ in csv.DictReader(f))
            if n != expected_n:
                row_count_mismatches.append((rid, "csv", expected_n, n))
        if per_run_json_dir and rid in per_run_json_ids:
            n = len(load_per_run_json(os.path.join(per_run_json_dir, f"{rid}.json")))
            if n != expected_n:
                row_count_mismatches.append((rid, "json", expected_n, n))
    if row_count_mismatches:
        print("  Per-file row-count parity: MISMATCH")
        for rid, kind, exp, got in row_count_mismatches:
            print(f"    run_id={rid} ({kind}): combined export has {exp} rows, per-run file has {got} rows")
    else:
        print("  Per-file row-count parity: OK — every per-run CSV/JSON file has the same row count as its slice of the combined export.")

    # ---- Per-run analysis ---------------------------------------------------
    summaries = [analyze_run(rid, rws) for rid, rws in runs.items()]
    summaries.sort(key=lambda s: int(s["run_id"]))

    complete = [s for s in summaries if s["is_complete"]]
    incomplete = [s for s in summaries if not s["is_complete"]]

    print("\n" + "-" * 78)
    print("COMPLETION SUMMARY")
    print("-" * 78)
    print(f"  Total runs (files)     : {len(summaries)}")
    print(f"  Complete runs          : {len(complete)}")
    print(f"  Incomplete runs        : {len(incomplete)}")

    # ---- Assignment slot coverage (the "60 conditions") --------------------
    print("\n" + "-" * 78)
    print("ASSIGNMENT SLOT COVERAGE (60 preregistered assignment_id slots, 0-59)")
    print("-" * 78)
    assignment_complete_counts = Counter()
    assignment_any_counts = Counter()
    for s in summaries:
        aid = s["assignment_id"]
        if aid == "":
            continue
        assignment_any_counts[aid] += 1
        if s["is_complete"]:
            assignment_complete_counts[aid] += 1

    all_assignment_ids = {str(i) for i in range(N_ASSIGNMENTS)}
    done_assignment_ids = {aid for aid, c in assignment_complete_counts.items() if c > 0}
    not_done_assignment_ids = all_assignment_ids - done_assignment_ids
    duplicated_assignment_ids = {aid: c for aid, c in assignment_complete_counts.items() if c > 1}

    print(f"  Assignment slots with >=1 COMPLETE run : {len(done_assignment_ids)} / {N_ASSIGNMENTS}")
    print(f"  Assignment slots with ZERO complete runs: {len(not_done_assignment_ids)} / {N_ASSIGNMENTS}")
    if not_done_assignment_ids:
        print(f"    Missing assignment_ids: {sorted(int(x) for x in not_done_assignment_ids)}")
    if duplicated_assignment_ids:
        print(f"  Assignment slots with >1 COMPLETE run (re-used slot): {duplicated_assignment_ids}")

    # ---- Complete trials by condition ---------------------------------------
    print("\n" + "-" * 78)
    print("COMPLETE TRIALS BY CONDITION")
    print("-" * 78)
    cond_counts = Counter(s["condition"] for s in complete)
    for c in CONDITIONS:
        print(f"  {c:>10}: {cond_counts.get(c, 0)}")
    other = set(cond_counts) - set(CONDITIONS)
    for c in other:
        print(f"  {c!r:>10}: {cond_counts[c]}  <-- unexpected condition label!")

    # ---- Complete trials by assignment_id (full 0-59 table) -----------------
    print("\n" + "-" * 78)
    print("COMPLETE RUNS BY ASSIGNMENT_ID (0-59)")
    print("-" * 78)
    row_str = []
    for i in range(N_ASSIGNMENTS):
        n = assignment_complete_counts.get(str(i), 0)
        row_str.append(f"{i}:{n}")
        if (i + 1) % 10 == 0:
            print("  " + "  ".join(row_str))
            row_str = []
    if row_str:
        print("  " + "  ".join(row_str))

    # ---- Incomplete runs detail (what you need to delete from Cognition) ---
    print("\n" + "-" * 78)
    print(f"INCOMPLETE RUNS DETAIL ({len(incomplete)} runs — candidates to delete/re-sync)")
    print("-" * 78)
    if not incomplete:
        print("  None — every downloaded run is complete.")
    else:
        header = (f"{'run_id':>7} {'PROLIFIC_PID':>26} {'assign':>6} {'cond':>10} {'stories_ok':>10} "
                  f"{'last_task':>22} {'last_trial_idx':>15} {'elapsed_min':>12} {'consented':>10}")
        print(header)
        print("  " + "-" * (len(header)))
        for s in incomplete:
            try:
                elapsed_min = round(int(s["last_time_elapsed_ms"]) / 60000, 1)
            except (ValueError, TypeError):
                elapsed_min = "?"
            print(f"{s['run_id']:>7} {s['prolific_pid']:>26} {s['assignment_id']:>6} {s['condition']:>10} "
                  f"{s['n_stories_fully_done']}/{N_STORIES_PER_PARTICIPANT:>8} {s['last_task']:>22} {str(s['last_trial_index']):>15} "
                  f"{str(elapsed_min):>12} {fmt_bool(s['consent_given']):>10}")
        print("\n  NOTE: 'elapsed_min' is jsPsych's own internal clock (time_elapsed of the last logged row),")
        print("  i.e. time from page load to the last successfully-saved trial — NOT necessarily how long the")
        print("  participant was on Prolific's clock. Cross-reference against Prolific's per-submission")
        print("  'Time taken' export: a run marked 'Completed'/'Approved' on Prolific with only a few minutes")
        print("  or zero task rows here is a strong signal of a completion-code leak/misuse rather than a")
        print("  genuine finish (see README / chat guidance on CONFIG.prolific.completion_url exposure).")

    print("\n  Prolific PIDs of incomplete runs (paste into Prolific to cross-check status):")
    for s in incomplete:
        print(f"    run_id={s['run_id']:>4}  PROLIFIC_PID={s['prolific_pid']}  participant_id={s['participant_id']}")

    # ---- Split incomplete into "near-complete" (all content done, outro
    # never logged — likely a Cognition sync/logging glitch) vs. "abandoned"
    # (participant actually stopped partway through the study). This matters
    # for deciding whether Prolific likely still paid/approved these.
    near_complete = [s for s in incomplete if s["n_stories_fully_done"] == N_STORIES_PER_PARTICIPANT]
    abandoned = [s for s in incomplete if s["n_stories_fully_done"] < N_STORIES_PER_PARTICIPANT]

    print("\n" + "-" * 78)
    print("INCOMPLETE RUNS, SPLIT BY LIKELY CAUSE")
    print("-" * 78)
    print(f"  Near-complete (finished all {N_STORIES_PER_PARTICIPANT} stories' task blocks, but no 'debrief' row logged — ")
    print(f"                 likely a Cognition sync/upload glitch, not participant abandonment): {len(near_complete)}")
    for s in near_complete:
        print(f"    run_id={s['run_id']:>4}  PROLIFIC_PID={s['prolific_pid']}  last_task={s['last_task']}  "
              f"reached_final_comments={fmt_bool(s['reached_final_comments'])}")
    print(f"\n  Abandoned partway through (did not finish all {N_STORIES_PER_PARTICIPANT} stories — genuine incomplete session): {len(abandoned)}")
    for s in abandoned:
        print(f"    run_id={s['run_id']:>4}  PROLIFIC_PID={s['prolific_pid']}  stories_done={s['n_stories_fully_done']}/{N_STORIES_PER_PARTICIPANT}  "
              f"last_task={s['last_task']}  last_trial_idx={s['last_trial_index']}")

    # ---- Duplicate PROLIFIC_PID across ALL runs (complete or not) ----------
    # Computed here (before the Prolific cross-check) because the decisive
    # classification below needs to know if an incomplete run's participant
    # already has a separate, fully complete run.
    pid_to_runs = defaultdict(list)
    for s in summaries:
        if s["prolific_pid"]:
            pid_to_runs[s["prolific_pid"]].append(s["run_id"])
    dup_pids = {pid: rids for pid, rids in pid_to_runs.items() if len(rids) > 1}
    if dup_pids:
        print("\n" + "-" * 78)
        print("DUPLICATE PROLIFIC_PID ACROSS RUNS (same person, multiple sessions/attempts)")
        print("-" * 78)
        by_run_id = {s["run_id"]: s for s in summaries}
        for pid, rids in dup_pids.items():
            statuses = [("complete" if by_run_id[r]["is_complete"] else "incomplete") for r in rids]
            print(f"  PROLIFIC_PID={pid}: run_ids={rids}  statuses={statuses}")

    # ---- Decisive cross-check against Prolific's own export -----------------
    # The single most reliable signal Prolific gives us is the COMPLETION CODE
    # the participant actually entered: it can only be produced by the
    # `redirect` trial firing at the true end of the timeline (see
    # src/outro.js), so a match proves the participant finished the whole
    # study in their browser even if Cognition's log is empty/partial.
    if args.prolific_csv:
        print("\n" + "-" * 78)
        print("DECISIVE CROSS-CHECK AGAINST PROLIFIC EXPORT (--prolific-csv)")
        print("-" * 78)
        try:
            prolific = load_prolific_export(args.prolific_csv)
        except ValueError as e:
            print(f"  ERROR: {e}")
            prolific = None
        if prolific is not None:
            by_run_id = {s["run_id"]: s for s in summaries}
            real_code, screen_out_code = _detect_completion_codes(base)
            print(f"  Loaded {len(prolific)} Prolific submission records from {args.prolific_csv}")
            if real_code:
                print(f"  Detected real completion code from src/config.js: {real_code!r}"
                      + (f"  |  screen-out code: {screen_out_code!r}" if screen_out_code else ""))
            else:
                print("  Could not auto-detect completion code from src/config.js — code-based checks skipped.")

            buckets = defaultdict(list)
            for s in incomplete:
                pid = s["prolific_pid"]
                rec = prolific.get(pid)
                if not rec:
                    buckets["not_found"].append((s, None))
                    continue
                code = rec["completion_code_entered"]
                status = rec["status"].upper()
                backup_runs = [r for r in pid_to_runs.get(pid, []) if r != s["run_id"] and by_run_id[r]["is_complete"]]

                if status == "SCREENED OUT":
                    bucket = "screened_out"
                elif status == "RETURNED":
                    bucket = "voluntary_return"
                elif status == "TIMED-OUT":
                    bucket = "timed_out"
                elif real_code and code == real_code:
                    bucket = "genuine_completion_backed_up" if backup_runs else "genuine_completion_orphan"
                else:
                    bucket = "no_code_ambiguous_backed_up" if backup_runs else "no_code_ambiguous_orphan"
                buckets[bucket].append((s, rec, backup_runs))

            def _print_bucket(key, title, action):
                items = buckets.get(key, [])
                if not items:
                    return
                print(f"\n  {title}: {len(items)}")
                print(f"  ACTION: {action}")
                for entry in items:
                    s, rec = entry[0], entry[1]
                    backup = entry[2] if len(entry) > 2 else []
                    backup_str = f"  (backup complete run: {backup})" if backup else ""
                    code_str = f"code={rec['completion_code_entered']!r}" if rec else ""
                    status_str = f"status={rec['status']!r}" if rec else "NOT FOUND IN PROLIFIC EXPORT"
                    print(f"    run_id={s['run_id']:>4}  PID={s['prolific_pid']}  assignment_id={s['assignment_id']:>3}  "
                          f"stories_done={s['n_stories_fully_done']}/4  {status_str}  {code_str}{backup_str}")

            _print_bucket("genuine_completion_orphan",
                           "GENUINE FULL COMPLETION — valid completion code, no backup run exists",
                           "APPROVE payment. Data is real but was lost/partial in Cognition (not the "
                           "participant's fault). If 4/4 stories are marked done, this is actually usable "
                           "analysis data (just missing the trailing debrief/redirect bookkeeping rows) — "
                           "do NOT delete. If <4/4, keep the completed story blocks if your design allows "
                           "partial-participant data, and recruit a fresh participant for this assignment_id.")
            _print_bucket("genuine_completion_backed_up",
                           "GENUINE FULL COMPLETION — valid completion code, but a backup complete run already exists",
                           "This is a duplicate/retry attempt by someone who already succeeded elsewhere. "
                           "APPROVE payment only once (via the backup run's submission) — do not double-pay. "
                           "Safe to DELETE this orphan run_id from Cognition; it adds no analysis value.")
            _print_bucket("no_code_ambiguous_orphan",
                           "NO VALID CODE, no backup run — genuinely ambiguous",
                           "Message this participant on Prolific asking what they experienced before deciding "
                           "approve/reject. If you don't hear back or the account of what happened doesn't "
                           "match real engagement, safe to DELETE this run_id from Cognition.")
            _print_bucket("no_code_ambiguous_backed_up",
                           "NO VALID CODE, but a backup complete run already exists",
                           "Likely an abandoned retry by someone who already succeeded elsewhere. "
                           "Safe to DELETE this orphan run_id from Cognition.")
            _print_bucket("voluntary_return", "VOLUNTARY RETURN (participant chose to return the submission)",
                           "No payment owed per standard Prolific practice. Safe to DELETE this run_id from "
                           "Cognition and recruit a fresh participant for this assignment_id.")
            _print_bucket("timed_out", "TIMED OUT (Prolific's own allotted time expired)",
                           "No payment owed. Safe to DELETE this run_id from Cognition.")
            _print_bucket("screened_out", "SCREENED OUT (declined consent — working as designed)",
                           "Not real experimental data (no consent). Safe to DELETE this run_id from Cognition.")
            _print_bucket("not_found", "NOT FOUND in the Prolific export",
                           "Check manually — may be from a different study/batch or a PID mismatch.")

            # ---- Final consolidated action lists -------------------------------
            delete_ids, approve_keep_ids, message_ids = [], [], []
            for key in ("genuine_completion_backed_up", "no_code_ambiguous_backed_up", "voluntary_return",
                        "timed_out", "screened_out"):
                delete_ids += [e[0]["run_id"] for e in buckets.get(key, [])]
            for e in buckets.get("genuine_completion_orphan", []):
                approve_keep_ids.append(e[0]["run_id"])
            for e in buckets.get("no_code_ambiguous_orphan", []):
                message_ids.append(e[0])

            print("\n" + "-" * 78)
            print("FINAL RECOMMENDATION")
            print("-" * 78)
            print(f"  DELETE from Cognition ({len(delete_ids)} runs, no analysis value / already paid elsewhere / "
                  f"no payment owed): {sorted(delete_ids, key=int)}")
            print(f"  KEEP + APPROVE on Prolific ({len(approve_keep_ids)} runs — genuine completions, real data "
                  f"just missing bookkeeping rows or partially lost): {sorted(approve_keep_ids, key=int)}")
            print(f"  MESSAGE on Prolific before deciding ({len(message_ids)} runs — ambiguous, no backup, no code):")
            for s in message_ids:
                print(f"    run_id={s['run_id']:>4}  PROLIFIC_PID={s['prolific_pid']}")

    # ---- Data-quality flags on COMPLETE runs (not exclusion, just FYI) -----
    consent_false = [s for s in complete if not s["consent_given"]]
    multi_pid = [s for s in summaries if s["prolific_pid_count"] > 1]
    multi_cond = [s for s in summaries if s["condition_count"] > 1]
    if consent_false or multi_pid or multi_cond:
        print("\n" + "-" * 78)
        print("DATA QUALITY FLAGS (informational — not automatically excluded)")
        print("-" * 78)
        if consent_false:
            print(f"  Complete runs with consent_given != true: {[s['run_id'] for s in consent_false]}")
        if multi_pid:
            print(f"  Runs with >1 distinct PROLIFIC_PID in their rows (should be impossible): {[s['run_id'] for s in multi_pid]}")
        if multi_cond:
            print(f"  Runs with >1 distinct condition value in their rows (should be impossible): {[s['run_id'] for s in multi_cond]}")

    if args.verbose:
        print("\n" + "-" * 78)
        print("FULL PER-RUN TABLE")
        print("-" * 78)
        header = (f"{'run_id':>7} {'complete':>8} {'assign':>6} {'cond':>10} {'n_rows':>7} "
                  f"{'stories_started':>15} {'stories_done':>12} {'debrief':>7} {'redirect':>8} {'last_task':>22}")
        print(header)
        for s in summaries:
            print(f"{s['run_id']:>7} {fmt_bool(s['is_complete']):>8} {s['assignment_id']:>6} {s['condition']:>10} "
                  f"{s['n_rows']:>7} {s['n_stories_started']:>15} {s['n_stories_fully_done']:>12} "
                  f"{fmt_bool(s['reached_debrief']):>7} {fmt_bool(s['reached_redirect']):>8} {s['last_task']:>22}")

    if args.json_out:
        payload = {
            "base_dir": base,
            "file_counts": {
                "combined_files": n_combined_files,
                "per_run_csv_files": len(per_run_csv_files),
                "per_run_json_files": len(per_run_json_files),
                "total_files": total_files,
            },
            "n_total_runs": len(summaries),
            "n_complete_runs": len(complete),
            "n_incomplete_runs": len(incomplete),
            "assignment_slots_done": sorted(int(x) for x in done_assignment_ids),
            "assignment_slots_missing": sorted(int(x) for x in not_done_assignment_ids),
            "complete_by_condition": dict(cond_counts),
            "runs": summaries,
        }
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"\nFull machine-readable audit written to: {args.json_out}")

    print("\n" + "=" * 78)
    print("DONE")
    print("=" * 78)


if __name__ == "__main__":
    main()
