# Track 02 — Human RDM pipeline

Extract 8×8 directed pair-scaling matrices from human trials, aggregate to
RDMs, run second-order RSA, and slice by topology.

## Pipeline

| Step | Script | Output |
|------|--------|--------|
| 1 | `01_extract_matrices.py` | Per-participant matrices (complete / canonical runs) |
| 2 | `02_aggregate_rdms.py` | Condition / story aggregates → `outputs/aggregated/human_rdms.npz` |
| 3 | `03_second_order_rsa.py` | Inter-story, inter-condition, meta RDMs |
| 4 | `04_by_topology.py` | Topology-stratified summaries *(stub)* |

```bash
cd experiment_v2.1
python3 analysis/track_02_human_rdm/01_extract_matrices.py
python3 analysis/track_02_human_rdm/02_aggregate_rdms.py
python3 analysis/track_02_human_rdm/03_second_order_rsa.py
```

Derived artefacts go to `outputs/`. Source CSV stays in `human results/`.

## Metrics

Uses `shared/rdm_utils.spearman_distance_rdm` — **1 − Spearman ρ** on 56
off-diagonal cells (same convention as `model_arm/src/meta_rsa.py`).

## Story subset

Default: **HUMAN_POOL_6** (`shared/story_sets.py`). Each participant contributes
4 of 6 stories; aggregation respects assignment_id from the BIBD design.
