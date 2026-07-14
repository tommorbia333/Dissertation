# Track — Temporal ordering

Summarises chronological ordering for humans and models.

## Metrics

| Metric | Range | Direction |
|--------|-------|-----------|
| Kendall τ distance | 0–28 | lower better |
| Exact match | 0–1 | higher better |
| Pairwise order accuracy | 0–1 | higher better |

## Sources

- **Human** — drag-and-drop `ordering` rows (`final_order`, `kendall_tau_to_canonical`)
- **Model behavioural** — instruct sweep `parsed/ordering.json`
- **Probing** — `position_probe` + `pairwise_probe` (representation probes; not the same task)

## Run

```bash
cd experiment_v2.1
python3 analysis/track_ordering/01_analyze_ordering.py
```

Or regenerate the full writeup hub (includes this track):

```bash
python3 analysis/build_master_outputs.py
```
