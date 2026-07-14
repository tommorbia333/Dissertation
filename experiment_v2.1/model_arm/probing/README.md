# Probing arm (representational / hidden-state studies)

The interpretability counterpart to the behavioural `model_arm`. Where the
behavioural arm generates text answers and parses them, this arm pulls per-event
**hidden-state vectors** out of a base LM and asks what temporal / causal
structure is linearly decodable, and how the representation is geometrically
organised.

This is the local, git-tracked port of the Colab probing notebook, restructured so it runs on Apple Silicon (MPS) and so models, sizes, story subsets, conditions and analyses are one-line config changes.

## Studies

| analysis            | question                                                           | outputs |
|---------------------|--------------------------------------------------------------------|---------|
| `position_probe`    | Is chronological position 1..8 decodable per layer? (LOSO)         | `position_accuracy_by_layer.png`, `.npz` |
| `pairwise_probe`    | before / after / concurrent per pair, + scramble + balanced + confusion | `pairwise_accuracy_by_layer.png`, `.npz` |
| `causal_rdm`        | Does the model RDM match the author causal graph? (Mantel by layer) | `causal_mantel_by_layer.png`, `causal_model_rdms.npz` |
| `causal_rdm_extra`  | Diagnostics: Spearman Mantel, edge AUC, label-free geometric RDMs   | several `.png`, `.npz` |
| `geometry`          | Is the dominant axis temporal? Arc vs ring? (permutation null)      | `cyclicity_by_layer.png`, `event_planes_*.png`, `.npz` |
| `behavioural`       | Prompted pair-rating + prompted state, three-arm vs author graph    | `analysis_*.png`, `per_story_*`, `rdms/` |

## Running

```bash
cd experiment_v2.1/model_arm/probing
python run_probing.py smoke        # plumbing check: 0.5B, 2 stories
python run_probing.py full_1_5b    # 1.5B, all stories, full battery
python run_probing.py full_7b      # 7B, all stories (the Colab-crashing run)
python run_probing.py size_sweep   # 0.5B -> 7B, representation analyses
```

(Or `python -m model_arm.probing.run_probing <config>` from `experiment_v2.1/`.)

## Configs — what you change between runs

Configs live in `configs/` and expose a `CONFIG` dict. The knobs:

- `models` — registry keys (`qwen0.5b`, `qwen1.5b`, `qwen3b`, `qwen7b`, and
  `*-instruct` variants; see `models_probing.PROBING_MODELS`) **or** any raw
  Hugging Face id. A list runs several in turn, evicting each before the next so
  peak memory is just the largest model.
- `story_ids` — `None` for all 8 domains, or a subset (keys like
  `hospital_incident` or display names like `Hospital Incident`).
- `conditions` — any subset of `linear`, `nonlinear`, `atemporal`.
- `analyses` — any subset of the table above.
- `scale_max`, `rep_layer`, `n_perm`, `device`, `dtype`, `skip_existing`.

## Outputs

```
outputs_probing/run_<stamp>_<run_id>/
    manifest.json
    <model_key>/
        event_vectors.npz              # reading-pass vectors (shared by all probes)
        position_probe/  pairwise_probe/  causal_rdm/  geometry/
        behavioural/
            behavioural.npz            # answers + prompted states
            analysis_*.png  per_story_*.png
            rdms/
                model_rdms_for_human.npz   # per-story RDMs, all arms
                mantel_summary.json
```

## Comparing to the human data

The `behavioural` arm mirrors the human directed pair-rating task, so its
per-story 8×8 RDMs are directly Mantel-comparable to human RDMs. They are saved
in a canonical layout in `behavioural/rdms/model_rdms_for_human.npz`
(`author_<cond>`, `behavioural_<cond>`, `prompted_<cond>`, `reading_<cond>`,
each stacked over stories in `story_keys` order). A future
`compare_to_human.py` just loads this plus the human RDMs and correlates them —
no re-running the model required.

## Inputs (already in the repo)

- `../../stimuli/narrative_stimuli.txt` — stimulus text (parsed to domains × conditions × events)
- `../../stimuli/temporal_structure.txt` — before/after/concurrent ground truth
- `../../author_intended_graphs.json` — author causal graph (RDM target)

## Notes

- Probing needs `output_hidden_states`, so this arm is **transformers-only**
  (the MLX / API backends used by the behavioural arm cannot expose hidden
  states). On a 24 GB M5 the largest fp16 model that fits is 7B.
- Requires `scikit-learn` (added to `requirements.txt`).
