# Dissertation analysis hub

Central comparison workflow for the human behavioural arm, model behavioural arm,
model probing arm, and cross-arm synthesis. This folder holds **orchestration stubs
and shared utilities only** — raw data stay in their canonical locations (see
`configs/canonical_runs.yaml`).

## Track overview

| Track | Folder | Role |
|-------|--------|------|
| **01 — Human collection** | `track_01_human_collection/` | Audit exports, completion counts, Prolific cross-check |
| **02 — Human RDM** | `track_02_human_rdm/` | Build participant-level 8×8 pair-scaling matrices → aggregate RDMs → second-order RSA |
| **03 — Model behavioural** | `track_03_model_behavioural/` | Summarise the main model sweep (pair-scaling, meta-RDMs) |
| **04 — Model probing** | `track_04_model_probing/` | Summarise hidden-state probes + probing behavioural RDMs |
| **05 — Cross-arm** | `track_05_cross_arm/` | Human ↔ model behavioural ↔ probing comparisons |

Track 01 is collection/QA only; tracks 02–05 are the analysis pipeline.

## What each track does

### Track 01 — Human collection

Wraps the existing audit script. Does **not** extract RDMs.

- Entry point: [`../scripts/analyze_human_results.py`](../scripts/analyze_human_results.py)
- See [`track_01_human_collection/README.md`](track_01_human_collection/README.md)

### Track 02 — Human RDM

Turns cleaned human pair-scaling trials into per-participant 8×8 directed matrices,
aggregates to condition- and story-level RDMs, runs second-order RSA (inter-story,
inter-condition), and slices by topology.

- Pipeline: `01_extract_matrices.py` → `02_aggregate_rdms.py` → `03_second_order_rsa.py` → `04_by_topology.py`
- Outputs land in `track_02_human_rdm/outputs/` (derived artefacts only)

### Track 03 — Model behavioural

Reads the canonical model sweep (`sweep_20260524_120056_main_run_v5_prompt_2`) and
produces dissertation-ready summaries of pair-scaling geometry, meta-RDMs, and
condition contrasts. Reuses logic from `model_arm/src/meta_rsa.py`.

### Track 04 — Model probing

Reads probing run folders (`outputs_probing/run_*`) — position/pairwise probes,
causal Mantel curves, geometry, and the behavioural sub-arm RDMs saved for human
comparison (`behavioural/rdms/model_rdms_for_human.npz`).

### Track 05 — Cross-arm

Three-way synthesis:

- `compare_pair_scaling_to_human.py` — model behavioural pair-scaling vs human RDMs
- `compare_probing_to_human.py` — probing behavioural RDMs vs human RDMs
- `three_way_summary.py` — human + model behavioural + probing on aligned story subsets

## Canonical data paths

All paths are relative to `experiment_v2.1/` unless noted. **Do not copy these
files into `analysis/`** — loaders resolve them via `configs/canonical_runs.yaml`.

| Source | Path |
|--------|------|
| Human combined CSV | `human results/experiment-v21_all67.csv` |
| Human audit JSON | `human results/_audits/audit_all67.json` |
| Fill-gaps merge manifest | `human results/_audits/fill_gaps_merge.json` |
| Canonical runs for analysis | `human results/_audits/canonical_runs_for_analysis.yaml` |
| Author causal graphs | `author_intended_graphs.json` |
| Model behavioural sweep | `model_arm/outputs/sweep_20260524_120056_main_run_v5_prompt_2/` |
| Probing 1.5B run | `model_arm/outputs_probing/run_20260709_131857_full_1_5b/` |
| Probing 7B run | `model_arm/outputs_probing/run_20260709_134350_full_7b/` *(in progress)* |

Story-set constants live in `shared/story_sets.py`. RDM metric conventions live
in `shared/rdm_utils.py`.

## Exclusion policy

Applied consistently across tracks (implemented in loaders / track 02 step 01):

1. **Incomplete runs** — exclude any run that fails the completion gate in
   `analyze_human_results.py` (4 stories with all gate tasks + debrief). The audit
   JSON lists `n_incomplete_runs` and per-run progress.
2. **Attention check** — flag (do not auto-drop) runs where `attn_correct == false`
   on the comprehension attention item. Primary analyses use all complete runs;
   sensitivity analyses exclude flagged runs.
3. **Fill-gaps merge** — done via `scripts/merge_fill_gaps_results.py`. Fill-gaps
   Cognition `run_id`s were renumbered 97–102 to avoid collisions and appended
   into `experiment-v21_all67.csv` (67 runs). Both assignment-24 fill-gaps
   participants are kept in the stored dataset; primary analyses pick one
   canonical run per `assignment_id` (see
   `human results/_audits/canonical_runs_for_analysis.yaml`). Slot **11** is
   still missing.

## Story subset alignment (6 vs 8)

| Set | Stories | Used by |
|-----|---------|---------|
| **HUMAN_POOL_6** | hospital, community_fair, restaurant_fire, school_trip, power_cut, missed_flight | Human participants (4-of-6 BIBD) |
| **ALL_8** | HUMAN_POOL_6 + care_home_incident, family_conflict | Model behavioural sweep, probing |

Cross-arm comparisons must declare which subset they use:

- **6-story overlap** — fair human ↔ model comparisons (each human saw 4 of these 6)
- **8-story model-only** — care_home and family_conflict have no human data; report separately

Constants and topology labels: `shared/story_sets.py`.

## Model variant note (instruct vs base)

- **Model behavioural sweep** uses instruct/chat-tuned models with human-like prompts
  (`v5_human_like`). Paths under `model_arm/outputs/`.
- **Probing arm** uses **base** (non-instruct) Qwen weights because hidden states
  require `output_hidden_states` via Hugging Face transformers. Config keys:
  `qwen1.5b`, `qwen7b` (not `*-instruct`).
- When comparing arms, note the variant mismatch: behavioural outputs reflect
  instruction-following; probing outputs reflect base-model representations.
  The probing **behavioural sub-arm** partially bridges this (prompted pair-rating
  on the same base model).

## NOW vs LATER

### NOW (skeleton + first implementations)

- [x] Folder structure, shared stubs, canonical run config
- [x] Fill-gaps CSV merge + re-audit (`experiment-v21_all67.csv`, 67 runs; slot 11 still missing)
- [x] Track 01: audit on merged dataset (`human results/_audits/audit_all67.json`)
- [x] Track 01: comprehension accuracy summary (`01_comprehension_accuracy.py`)
- [x] Track 02: human RDM extraction → aggregate → second-order RSA → topology stratification
- [x] Track 03: model sweep summaries wired to shared `rdm_utils` (`01_summarize_sweep.py`)
- [x] Track 04/shared: load probing 1.5B + 7B behavioural RDMs (`shared/loaders/model_probing.py`)
- [x] Track 05: 6-story human ↔ probing behavioural comparison (1.5B + 7B)
- [x] Track 05: human ↔ model-behavioural pair-scaling comparison (`compare_pair_scaling_to_human.py`)
- [x] Track 05: three-way summary table (`three_way_summary.py`)

### LATER

- [ ] Recruit / merge assignment_id 11 if needed for full 60-slot coverage
- [x] Probing 7B run complete → canonical config flipped to `complete`
- [ ] Attention-check sensitivity tables (comprehension accuracy script has the hook; 0 flagged runs so far)
- [ ] Instruct-vs-base paired comparison (if instruct probing runs added)
- [ ] Retry the failed `Qwen3-8B` behavioural trial (died silently after trial 1/90, no exception logged)
- [ ] Dissertation figure export scripts for sections 8-11 (currently tables only, no new PNGs)

## Shared code

```
shared/
├── story_sets.py      # HUMAN_POOL_6, ALL_8, topology labels
├── rdm_utils.py       # off-diagonal vectors, Mantel r, 1−ρ distance
└── loaders/           # human, model_behavioural, model_probing stubs
```

Run track scripts from `experiment_v2.1/`:

```bash
python analysis/track_02_human_rdm/01_extract_matrices.py --help
```

## Master writeup hub

Organised figures + auto-updating results README live in
[`../master_outputs/`](../master_outputs/) (sibling of `analysis/`). Regenerate with:

```bash
python3 analysis/build_master_outputs.py
```
