# Track 05 — Cross-arm comparison

Human ↔ model behavioural ↔ probing synthesis on aligned story subsets.

## Scripts

| Script | Comparison |
|--------|--------------|
| `compare_pair_scaling_to_human.py` | Model behavioural sweep vs human RDMs (6-story overlap) |
| `compare_probing_to_human.py` | Probing behavioural RDMs vs human RDMs |
| `three_way_summary.py` | Combined human + model behavioural + probing table |

## Metrics

- Second-order distance: **1 − Spearman ρ** on 56 off-diagonal cells (`shared/rdm_utils.py`)
- First-order Mantel (probing hidden states): Pearson r on off-diagonal vectors

## Story alignment

Default cross-arm subset: **HUMAN_POOL_6**. Model-only stories (care_home,
family_conflict) reported in a separate block.

## Outputs

Derived comparisons → `outputs/`.

```bash
cd experiment_v2.1
# Requires track_02 aggregated human_rdms.npz
python3 analysis/track_05_cross_arm/compare_probing_to_human.py --probing-run full_1_5b
```

Writes `outputs/probing_vs_human_full_1_5b.json` with per-story Mantel r and
1 − Spearman ρ distances for author / behavioural / prompted / reading arms.
