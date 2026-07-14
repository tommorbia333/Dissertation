# Track 01 — Human collection & audit

This track covers **data collection QA only** — no RDM extraction.

## Entry point

Use the existing audit script (do not duplicate logic here):

```bash
cd experiment_v2.1
python3 scripts/analyze_human_results.py
python3 scripts/analyze_human_results.py --json-out "human results/_audits/audit_latest.json"
python3 scripts/analyze_human_results.py --prolific-csv "human results/prolific_demographic_export_*.csv"
```

## What it reports

- Complete vs incomplete runs (4 stories × all gate tasks + debrief)
- Assignment slot coverage (0–59) and missing slots for fill-gaps
- Condition balance among complete runs
- Cross-export consistency (combined vs per-run CSV/JSON)

## Outputs

Audit JSON is written to `human results/_audits/` (canonical path in
`analysis/configs/canonical_runs.yaml`). Track 02 loaders consume this audit
to filter participants.
