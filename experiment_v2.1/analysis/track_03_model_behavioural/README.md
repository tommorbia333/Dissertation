# Track 03 — Model behavioural summaries

Summarise the canonical model behavioural sweep for dissertation figures and
tables. Reads existing trial outputs — no model re-runs.

## Canonical run

`sweep_20260524_120056_main_run_v5_prompt_2` under
`model_arm/outputs/` (see `configs/canonical_runs.yaml`).

Each trial folder contains:

- `parsed/pair_scaling_matrices.json` — 8×8 directed matrices per (story, condition, seed)
- `parsed/meta_rdms.json` — precomputed second-order RSA (1 − Spearman ρ)

## Planned scripts

Scripts will live here as needed; core RSA logic remains in
`model_arm/src/meta_rsa.py`. This track aggregates across trials/models and
aligns story subsets (ALL_8) with human comparisons.

## Outputs

Derived summaries only → `outputs/`.
