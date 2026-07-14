"""Load and filter human experiment exports.

Resolves paths via ``analysis/configs/canonical_runs.yaml``. Selection policy
for primary analyses (one run per ``assignment_id``):

1. Prefer complete fill-gaps runs (``experiment_version`` containing ``fillgaps``)
2. Else prefer complete main-study runs
3. Else near-complete (all 4 story gates done, missing debrief)
4. Ties broken by lower ``run_id``

Sensitivity mode keeps every complete run (including duplicate assignment slots).
Attention-check failures are flagged via ``attn_correct``, never auto-dropped.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Literal

import yaml

N_STORIES_PER_PARTICIPANT = 4
STORY_GATE_TASKS = ("comprehension_summary", "ordering", "pair_scaling_summary")
FILLGAPS_VERSION_TOKEN = "fillgaps"
SELECTION = Literal["canonical", "all_complete"]

ANALYSIS_DIR = Path(__file__).resolve().parents[2]
EXPERIMENT_ROOT = ANALYSIS_DIR.parent
DEFAULT_CONFIG = ANALYSIS_DIR / "configs" / "canonical_runs.yaml"
CANONICAL_YAML_REL = Path("human results/_audits/canonical_runs_for_analysis.yaml")


def _experiment_root(root: Path | None = None) -> Path:
    return Path(root) if root is not None else EXPERIMENT_ROOT


def _load_paths_config(root: Path | None = None) -> dict[str, Any]:
    root = _experiment_root(root)
    config_path = DEFAULT_CONFIG
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg


def _resolve_human_path(rel: str | Path, root: Path | None = None) -> Path:
    root = _experiment_root(root)
    p = Path(rel)
    return p if p.is_absolute() else root / p


def load_audit(root: Path | None = None) -> dict:
    """Load the audit JSON listed in ``canonical_runs.yaml`` (``audit_all67.json``)."""
    cfg = _load_paths_config(root)
    path = _resolve_human_path(cfg["human"]["audit_json"], root)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def complete_run_ids(audit: dict | None = None, root: Path | None = None) -> set[str]:
    """Return run_id strings for runs passing the completion gate."""
    if audit is None:
        audit = load_audit(root)
    return {str(s["run_id"]) for s in audit.get("runs", []) if s.get("is_complete")}


def _parse_bool(raw: Any) -> bool | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool):
        return raw
    s = str(raw).strip().lower()
    if s in ("true", "1", "yes"):
        return True
    if s in ("false", "0", "no"):
        return False
    return None


def _attn_correct_by_run(rows: list[dict]) -> dict[str, bool | None]:
    """Per-run attention-check flag from ``task == attention_check`` rows."""
    out: dict[str, bool | None] = {}
    for row in rows:
        if row.get("task") != "attention_check":
            continue
        rid = str(row.get("run_id", ""))
        if not rid:
            continue
        out[rid] = _parse_bool(row.get("attn_correct"))
    return out


def _version_by_run(rows: list[dict]) -> dict[str, str]:
    by_run: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        rid = str(row.get("run_id", ""))
        if not rid:
            continue
        ver = (row.get("experiment_version") or "").strip()
        if ver:
            by_run[rid].append(ver)
    out: dict[str, str] = {}
    for rid, vers in by_run.items():
        # Majority version for the run (fill-gaps vs main).
        out[rid] = max(set(vers), key=vers.count)
    return out


def _is_fillgaps_version(version: str) -> bool:
    return FILLGAPS_VERSION_TOKEN in (version or "").lower()


def _is_near_complete(summary: dict) -> bool:
    return (
        not summary.get("is_complete")
        and int(summary.get("n_stories_fully_done") or 0) == N_STORIES_PER_PARTICIPANT
    )


def _selection_rank(summary: dict, version: str) -> tuple[int, int]:
    """Higher rank preferred. Second key is -run_id so lower id wins ties."""
    rid = int(summary["run_id"])
    if summary.get("is_complete") and _is_fillgaps_version(version):
        tier = 3
    elif summary.get("is_complete"):
        tier = 2
    elif _is_near_complete(summary):
        tier = 1
    else:
        tier = 0
    return (tier, -rid)


def select_canonical_runs(
    audit: dict | None = None,
    *,
    rows: list[dict] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """Pick one run per assignment_id and return a serialisable selection record."""
    root = _experiment_root(root)
    if audit is None:
        audit = load_audit(root)
    if rows is None:
        cfg = _load_paths_config(root)
        csv_path = _resolve_human_path(cfg["human"]["combined_csv"], root)
        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

    versions = _version_by_run(rows)
    attn = _attn_correct_by_run(rows)

    by_assignment: dict[str, list[dict]] = defaultdict(list)
    for summary in audit.get("runs", []):
        aid = str(summary.get("assignment_id", "")).strip()
        if aid == "":
            continue
        by_assignment[aid].append(summary)

    canonical: dict[str, dict[str, Any]] = {}
    duplicates: dict[str, list[str]] = {}
    for aid, summaries in sorted(by_assignment.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else kv[0]):
        ranked = sorted(
            summaries,
            key=lambda s: _selection_rank(s, versions.get(str(s["run_id"]), "")),
            reverse=True,
        )
        best = ranked[0]
        best_rank = _selection_rank(best, versions.get(str(best["run_id"]), ""))
        if best_rank[0] == 0:
            continue  # no usable run for this slot

        complete_ids = [str(s["run_id"]) for s in summaries if s.get("is_complete")]
        if len(complete_ids) > 1:
            duplicates[aid] = complete_ids

        chosen_id = str(best["run_id"])
        reason = {
            3: "fillgaps_complete",
            2: "main_complete",
            1: "near_complete",
        }[best_rank[0]]
        canonical[aid] = {
            "run_id": chosen_id,
            "reason": reason,
            "is_complete": bool(best.get("is_complete")),
            "experiment_version": versions.get(chosen_id, ""),
            "attn_correct": attn.get(chosen_id),
            "condition": best.get("condition", ""),
            "alternatives": [
                str(s["run_id"]) for s in ranked[1:]
                if _selection_rank(s, versions.get(str(s["run_id"]), ""))[0] > 0
            ],
        }

    record = {
        "policy": {
            "priority": [
                "fillgaps_complete",
                "main_complete",
                "near_complete",
            ],
            "tie_break": "lowest_run_id",
            "notes": {
                "assignment_11_still_missing": "11" not in canonical,
                "assignment_24_duplicate": (
                    "Two separate fill-gaps completes (97, 102); "
                    "canonical keeps lowest run_id among fillgaps."
                ),
                "assignment_47_multiple_complete": (
                    "Main 90 and fill-gaps 99 both complete; canonical prefers fillgaps."
                ),
            },
        },
        "n_assignment_slots_selected": len(canonical),
        "canonical_by_assignment_id": canonical,
        "duplicate_complete_assignment_ids": duplicates,
        "canonical_run_ids": sorted(
            (v["run_id"] for v in canonical.values()),
            key=lambda x: int(x) if x.isdigit() else x,
        ),
    }
    return record


def write_canonical_runs_yaml(
    record: dict[str, Any] | None = None,
    *,
    root: Path | None = None,
    path: Path | None = None,
) -> Path:
    """Write ``human results/_audits/canonical_runs_for_analysis.yaml``."""
    root = _experiment_root(root)
    if record is None:
        record = select_canonical_runs(root=root)
    out = path if path is not None else root / CANONICAL_YAML_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        yaml.safe_dump(record, f, sort_keys=False, allow_unicode=True)
    return out


def load_canonical_csv(
    root: Path | None = None,
    *,
    selection: SELECTION = "canonical",
    write_canonical_yaml: bool = True,
) -> list[dict]:
    """Load the combined human CSV as row dicts.

    Applies the run selection filter and attaches ``attn_correct`` on every
    returned row. Does not copy source files.
    """
    root = _experiment_root(root)
    cfg = _load_paths_config(root)
    csv_path = _resolve_human_path(cfg["human"]["combined_csv"], root)
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    audit = load_audit(root)
    attn = _attn_correct_by_run(rows)

    if selection == "canonical":
        record = select_canonical_runs(audit, rows=rows, root=root)
        if write_canonical_yaml:
            write_canonical_runs_yaml(record, root=root)
        keep = set(record["canonical_run_ids"])
    elif selection == "all_complete":
        keep = complete_run_ids(audit)
    else:
        raise ValueError(f"Unknown selection={selection!r}")

    out: list[dict] = []
    for row in rows:
        rid = str(row.get("run_id", ""))
        if rid not in keep:
            continue
        enriched = dict(row)
        enriched["attn_correct"] = attn.get(rid)
        out.append(enriched)
    return out
