# Track 04 — Model probing summaries

Summarise hidden-state probing runs for dissertation figures and tables.

## Canonical runs

| Run | Model | Status |
|-----|-------|--------|
| `run_20260709_131857_full_1_5b` | qwen1.5b (base) | complete |
| `run_20260709_134350_full_7b` | qwen7b (base) | in progress |

Paths under `model_arm/outputs_probing/` (see `configs/canonical_runs.yaml`).

## Key artefacts per run

- `position_probe/`, `pairwise_probe/` — LOSO decode curves by layer
- `causal_rdm/` — Mantel r vs author graph by layer
- `geometry/` — cyclicity, event-plane plots
- `behavioural/rdms/model_rdms_for_human.npz` — per-story RDMs for cross-arm comparison

See `model_arm/probing/README.md` for the full output schema.

## Outputs

Derived summaries only → `outputs/`.
