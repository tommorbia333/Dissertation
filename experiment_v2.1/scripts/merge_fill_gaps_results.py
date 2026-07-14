#!/usr/bin/env python3
"""merge_fill_gaps_results.py — merge fill-gaps Cognition exports into the master dataset.

Fill-gaps Cognition run_ids (1, 2, 4, 5, 6, 8) collide with unrelated main-study
participants. This script renumbers them to 97–102, copies the 61 existing master
per-run files into a new all67 individual folder (without modifying the originals),
writes the six renumbered fill-gaps files, rebuilds the combined CSV from every
individual file (avoids trailing-newline append corruption), and writes a merge
manifest JSON.

Usage (from experiment_v2.1/):
    python3 scripts/merge_fill_gaps_results.py
    python3 scripts/merge_fill_gaps_results.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
from datetime import datetime, timezone

RENUMBER_MAP = {
    "1": "97",
    "2": "98",
    "4": "99",
    "5": "100",
    "6": "101",
    "8": "102",
}

FILL_GAPS_ASSIGNMENTS = {
    "1": "24",
    "2": "18",
    "4": "47",
    "5": "52",
    "6": "33",
    "8": "24",
}

DEFAULTS = {
    "master_individual_dir": "human results/experiment-v21_all60_individual",
    "master_combined_csv": "human results/experiment-v21_all60.csv",
    "fill_gaps_individual_dir": "human results/experiment-v21-fill-gaps_final6",
    "fill_gaps_combined_csv": "human results/experiment-v21-fill-gaps.csv",
    "out_individual_dir": "human results/experiment-v21_all67_individual",
    "out_combined_csv": "human results/experiment-v21_all67.csv",
    "manifest_json": "human results/_audits/fill_gaps_merge.json",
}


def _experiment_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _resolve(path: str, root: str) -> str:
    return path if os.path.isabs(path) else os.path.join(root, path)


def load_csv_rows(path: str) -> tuple[list[str], list[dict[str, str]]]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    return fieldnames, rows


def write_per_run_csv(path: str, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in fieldnames})


def renumber_rows(rows: list[dict[str, str]], new_run_id: str) -> list[dict[str, str]]:
    out = []
    for row in rows:
        updated = dict(row)
        updated["run_id"] = new_run_id
        out.append(updated)
    return out


def collect_union_fieldnames(
    canonical_fieldnames: list[str],
    per_run_fieldnames: list[list[str]],
) -> list[str]:
    union = list(canonical_fieldnames)
    seen = set(union)
    for fields in per_run_fieldnames:
        for col in fields:
            if col not in seen:
                union.append(col)
                seen.add(col)
    return union


def rebuild_combined_csv(
    individual_dir: str,
    out_path: str,
    canonical_fieldnames: list[str],
) -> dict[str, int]:
    """Concatenate all per-run CSVs into one combined export; return row counts per run_id."""
    files = sorted(
        (f for f in os.listdir(individual_dir) if f.endswith(".csv")),
        key=lambda name: int(os.path.splitext(name)[0]),
    )
    per_run_fieldnames: list[list[str]] = []
    all_rows: list[dict[str, str]] = []
    row_counts: dict[str, int] = {}

    for fname in files:
        run_id = os.path.splitext(fname)[0]
        fieldnames, rows = load_csv_rows(os.path.join(individual_dir, fname))
        per_run_fieldnames.append(fieldnames)
        row_counts[run_id] = len(rows)
        all_rows.extend(rows)

    union_fieldnames = collect_union_fieldnames(canonical_fieldnames, per_run_fieldnames)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=union_fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in all_rows:
            writer.writerow({col: row.get(col, "") for col in union_fieldnames})
    return row_counts


def validate_fill_gaps_sources(fill_dir: str) -> None:
    expected_old_ids = set(RENUMBER_MAP)
    found = {
        os.path.splitext(f)[0]
        for f in os.listdir(fill_dir)
        if f.endswith(".csv")
    }
    missing = sorted(expected_old_ids - found, key=int)
    extra = sorted(found - expected_old_ids, key=int)
    if missing:
        raise FileNotFoundError(f"Missing fill-gaps per-run files in {fill_dir}: {missing}")
    if extra:
        raise ValueError(f"Unexpected fill-gaps per-run files in {fill_dir}: {extra}")


def validate_master_individual(master_dir: str) -> list[str]:
    master_ids = sorted(
        int(os.path.splitext(f)[0])
        for f in os.listdir(master_dir)
        if f.endswith(".csv")
    )
    if not master_ids:
        raise FileNotFoundError(f"No per-run CSV files found in {master_dir}")
    new_ids = {int(v) for v in RENUMBER_MAP.values()}
    overlap = new_ids & set(master_ids)
    if overlap:
        raise ValueError(f"Renumbered fill-gaps IDs already exist in master: {sorted(overlap)}")
    return [str(i) for i in master_ids]


def build_manifest(
    *,
    renumbered_runs: list[dict],
    master_run_ids: list[str],
    row_counts: dict[str, int],
    out_paths: dict[str, str],
) -> dict:
    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "renumber_map": RENUMBER_MAP,
        "source": {
            "master_individual_dir": DEFAULTS["master_individual_dir"],
            "fill_gaps_individual_dir": DEFAULTS["fill_gaps_individual_dir"],
            "fill_gaps_combined_csv": DEFAULTS["fill_gaps_combined_csv"],
        },
        "outputs": out_paths,
        "master_run_ids_preserved": master_run_ids,
        "fill_gaps_runs_added": renumbered_runs,
        "row_counts_by_run_id": {k: row_counts[k] for k in sorted(row_counts, key=int)},
        "n_total_runs": len(row_counts),
        "notes": {
            "assignment_24_duplicate": (
                "Two separate fill-gaps participants (runs 97 and 102); both kept."
            ),
            "assignment_11_still_missing": True,
            "assignment_47_multiple_complete": (
                "Main-study run 90 and fill-gaps run 99 are both complete; "
                "incomplete run 73 also present."
            ),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="Validate and print actions without writing files")
    ap.add_argument("--master-individual-dir", default=DEFAULTS["master_individual_dir"])
    ap.add_argument("--master-combined-csv", default=DEFAULTS["master_combined_csv"])
    ap.add_argument("--fill-gaps-individual-dir", default=DEFAULTS["fill_gaps_individual_dir"])
    ap.add_argument("--out-individual-dir", default=DEFAULTS["out_individual_dir"])
    ap.add_argument("--out-combined-csv", default=DEFAULTS["out_combined_csv"])
    ap.add_argument("--manifest-json", default=DEFAULTS["manifest_json"])
    args = ap.parse_args()

    root = _experiment_root()
    master_individual_dir = _resolve(args.master_individual_dir, root)
    master_combined_csv = _resolve(args.master_combined_csv, root)
    fill_gaps_individual_dir = _resolve(args.fill_gaps_individual_dir, root)
    out_individual_dir = _resolve(args.out_individual_dir, root)
    out_combined_csv = _resolve(args.out_combined_csv, root)
    manifest_json = _resolve(args.manifest_json, root)

    for path, label in [
        (master_individual_dir, "master individual dir"),
        (master_combined_csv, "master combined CSV"),
        (fill_gaps_individual_dir, "fill-gaps individual dir"),
    ]:
        if not os.path.exists(path):
            sys.exit(f"Missing {label}: {path}")

    validate_fill_gaps_sources(fill_gaps_individual_dir)
    master_run_ids = validate_master_individual(master_individual_dir)
    canonical_fieldnames, _ = load_csv_rows(master_combined_csv)

    renumbered_runs = []
    for old_id, new_id in sorted(RENUMBER_MAP.items(), key=lambda item: int(item[0])):
        src = os.path.join(fill_gaps_individual_dir, f"{old_id}.csv")
        fieldnames, rows = load_csv_rows(src)
        observed_run_ids = {row.get("run_id", "") for row in rows}
        if observed_run_ids != {old_id}:
            sys.exit(
                f"Fill-gaps file {src} has unexpected run_id values {observed_run_ids}; "
                f"expected only {old_id!r}."
            )
        assignment_ids = {row.get("assignment_id", "") for row in rows if row.get("assignment_id", "")}
        expected_assignment = FILL_GAPS_ASSIGNMENTS[old_id]
        if assignment_ids != {expected_assignment}:
            sys.exit(
                f"Fill-gaps file {src} has assignment_id values {assignment_ids}; "
                f"expected only {expected_assignment!r}."
            )
        renumbered_runs.append(
            {
                "old_run_id": old_id,
                "new_run_id": new_id,
                "assignment_id": expected_assignment,
                "source_file": os.path.relpath(src, root),
                "n_rows": len(rows),
            }
        )

    n_master = len(master_run_ids)
    n_fill = len(RENUMBER_MAP)
    n_total = n_master + n_fill

    print("=" * 78)
    print("MERGE FILL-GAPS INTO MASTER HUMAN RESULTS")
    print("=" * 78)
    print(f"Master individual files : {n_master} (unchanged source: {master_individual_dir})")
    print(f"Fill-gaps files to add  : {n_fill} (renumbered {sorted(RENUMBER_MAP)} -> {sorted(RENUMBER_MAP.values(), key=int)})")
    print(f"Output individual dir   : {out_individual_dir}")
    print(f"Output combined CSV     : {out_combined_csv}")
    print(f"Manifest JSON           : {manifest_json}")
    print(f"Expected total runs     : {n_total}")

    if args.dry_run:
        print("\nDry run only — no files written.")
        return 0

    if os.path.exists(out_individual_dir):
        shutil.rmtree(out_individual_dir)
    os.makedirs(out_individual_dir, exist_ok=True)

    for run_id in master_run_ids:
        shutil.copy2(
            os.path.join(master_individual_dir, f"{run_id}.csv"),
            os.path.join(out_individual_dir, f"{run_id}.csv"),
        )

    for old_id, new_id in RENUMBER_MAP.items():
        src = os.path.join(fill_gaps_individual_dir, f"{old_id}.csv")
        fieldnames, rows = load_csv_rows(src)
        renumbered = renumber_rows(rows, new_id)
        write_per_run_csv(
            os.path.join(out_individual_dir, f"{new_id}.csv"),
            fieldnames,
            renumbered,
        )

    os.makedirs(os.path.dirname(manifest_json), exist_ok=True)
    row_counts = rebuild_combined_csv(out_individual_dir, out_combined_csv, canonical_fieldnames)

    manifest = build_manifest(
        renumbered_runs=renumbered_runs,
        master_run_ids=master_run_ids,
        row_counts=row_counts,
        out_paths={
            "individual_dir": os.path.relpath(out_individual_dir, root),
            "combined_csv": os.path.relpath(out_combined_csv, root),
            "manifest_json": os.path.relpath(manifest_json, root),
        },
    )
    with open(manifest_json, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    out_files = sorted(f for f in os.listdir(out_individual_dir) if f.endswith(".csv"))
    if len(out_files) != n_total:
        sys.exit(
            f"Post-merge check failed: expected {n_total} individual files, got {len(out_files)}."
        )
    if len(row_counts) != n_total:
        sys.exit(
            f"Post-merge check failed: expected {n_total} run_ids in combined CSV, got {len(row_counts)}."
        )

    print("\nMerge complete.")
    print(f"  Individual files written : {len(out_files)}")
    print(f"  Combined CSV rows        : {sum(row_counts.values())}")
    print(f"  Unique run_ids           : {len(row_counts)}")
    print(f"  Manifest                 : {manifest_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
