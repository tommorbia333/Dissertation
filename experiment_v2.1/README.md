# `experiment_v2.1` — implementation root

Canonical implementation of the dissertation experiment: the **human (jsPsych) arm** at the top of this folder, the **model (Python) arm** under `model_arm/`. Hidden-state probing work (Stage 3) will land under `model_arm/probing/`; see the top-level [`../README.md`](../README.md) for the cross-arm overview.

For full design rationale and deployment notes, see **`implementation_documentation.docx`** (or its `.pdf` render). For the data schema produced by the human arm, see **`DATA_SCHEMA.md`**.

## Folder layout

```
experiment_v2.1/
├── src/                              # JavaScript modules (the human-arm logic)
│   ├── config.js                     # versions, task params, participant pool, feature flags
│   ├── main.js                       # timeline entry point — intro + per-story blocks + outro
│   ├── condition.js                  # between-subjects condition assignment (deterministic pIndex % 3)
│   ├── selection.js                  # story selection from the 60-row preregistered table
│   ├── data.js                       # participant metadata + Prolific redirect helpers
│   ├── utils.js                      # URL params, timestamps, scroll/focus tracker, shuffle
│   ├── intro.js                      # browser check, welcome, consent, demographics, IMC, instructions
│   ├── inter_story.js                # between-story break + progress indicator
│   ├── outro.js                      # final comments, debrief, Prolific redirect
│   └── tasks/
│       ├── story_reading.js          # min-time threshold, activity tracking
│       ├── comprehension.js          # 6 items + summary row per story
│       ├── ordering.js               # SortableJS drag + confidence slider
│       ├── pair_scaling.js           # 56 directed pairs + 8×8 matrix summary row per story
│       └── counterfactual.js         # CF probes — NOT in the human timeline; kept for the model arm
│
├── stimuli/                          # Content (loaded as JS files setting globals — required by Cognition)
│   ├── stories.js                    # 8 stories × 3 versions (linear / nonlinear / atemporal)
│   ├── comprehension.js              # 48 comprehension items (6 per story × 8 stories)
│   ├── event_cards.js                # 64 short event labels (8 per story × 8 stories)
│   ├── cf_probes.js                  # 64 counterfactual probes (8 per story × 8 stories; model-arm-only)
│   └── assignments.js                # 60-row preregistered counterbalancing table (auto-generated)
│
├── scripts/
│   ├── build_assignments.py          # regenerate assignments.js + balance verification
│   ├── balance_check_export.py       # verify condition/story/slot balance in a Cognition export
│   └── deploy_to_cognition.py        # helper for pushing to Cognition.run
│
├── assets/
│   └── style.css                     # presentation styles for all tasks
│
├── index.html                        # local browser test harness — NOT used on Cognition
├── smoke_test.js                     # Node sandbox verification of all globals and builders
├── synthetic_run.js                  # end-to-end simulated participant runner
├── DATA_SCHEMA.md                    # operational reference for analysis code
├── author_intended_graphs.json       # design-blueprint causal graphs (8 stories, schema 0.4.0)
├── implementation_documentation.docx # full design + audit + deployment doc
├── implementation_documentation.pdf  # PDF render of the same
└── model_arm/                        # Python module — see model_arm/README.md
```

## Human arm — per-story battery

For each of the four stories assigned to a participant:

1. **Story reading** — minimum dwell time, scroll-depth and focus tracking.
2. **Comprehension** — 6 yes/no/unsure items (3 compound, 2 single, 1 distractor). Gates re-entry to the comprehension block before ordering if accuracy is below threshold.
3. **Ordering** — drag the 8 event cards into chronological order, then rate confidence (1–7).
4. **Pair scaling** — 56 directed pair ratings (0–6) per story; the resulting 8×8 directed matrix is the primary RSA input.

The counterfactual probe task has been removed from the participant timeline to keep sessions under 60 minutes; it remains available to the model arm and any future re-instatement.

## Counterbalancing — 4-of-6 BIBD × Williams (60-row cycle)

Six of the eight source domains form the **participant pool**: `hospital_incident`, `community_fair`, `restaurant_fire`, `school_trip`, `power_cut`, `missed_flight`. The other two (`care_home_incident`, `family_conflict`) remain in every source stimulus file but are filtered out at the allocation level — no assignment row references them.

The allocator (`scripts/build_assignments.py`) crosses every C(6,4) = 15 four-subset of the pool with a Williams' 4-square (each ordering visits each position once across the four rows), giving a 60-row balancing cycle. `pIndex` (0..59) selects the assignment row *and* the condition (`pIndex % 3`), so a balanced index yields the whole design. Verified properties per 60-participant cycle:

| Property                                       | Per cycle               | Status |
|------------------------------------------------|-------------------------|--------|
| Each story is read                             | 40 / 60                 | exact  |
| Each unordered story-pair co-occurs            | 24 / 60                 | exact  |
| Each story × position                          | 10 / 60                 | exact (Williams) |
| Each condition (linear/nonlinear/atemporal)    | 20 / 60                 | exact  |
| Each story × condition                         | 13 or 14 reads          | tightest possible (40 / 3 not integer) |

Balance holds exactly as long as the 60 indices are each used once, which Cognition's server-side 60-way auto-balancer guarantees in production (see *Before deployment*). `src/condition.js` maps `pIndex → condition` deterministically as `CONDITIONS[pIndex % 3]` (the design's stratified cycle) — no per-participant hashing, which would otherwise re-randomise the mapping and break exact balance. Run `python3 scripts/build_assignments.py --check-only` to print the verification at 60 / 180 / 300 participants.

Other randomisation (unchanged): between-subjects assignment to linear/nonlinear/atemporal in stratified blocks of 3; pair-presentation order and pair direction randomised per participant within each story; comprehension item order randomised per story; ordering trials start from the preregistered scrambled order `E2 E4 E5 E8 E6 E7 E3 E1`.

## Running the human arm locally

```bash
# from this folder, start any static HTTP server
python3 -m http.server 8000
# then open http://localhost:8000/index.html
```

The page renders the full participant timeline (intro → 4 × per-story battery → outro). For test runs, set `CONFIG.debug.enabled = true` in `src/config.js` (and use the `force_condition` / `force_assignment_id` overrides) to skip into a specific cell.

## Verification (no browser required)

Three checks confirm the build is well-formed without booting a browser:

```bash
node smoke_test.js                            # sandbox-loads every file; checks every global and builder
node synthetic_run.js                         # end-to-end simulated participant; writes synthetic_output.json
python3 scripts/build_assignments.py --check-only    # 4-of-6 counterbalancing verification
```

`smoke_test.js` also confirms that the two excluded domains (`care_home_incident`, `family_conflict`) are still loadable from every source stimulus file — i.e. that the computational pipeline isn't broken by the human-arm filter.

## Model arm

The Python module under `model_arm/` runs the same battery on language models (open-weights via Hugging Face transformers and MLX 4-bit, plus OpenAI and Anthropic APIs). It uses a *sweep* architecture: each (model × prompt-variant × story × condition × seed) cell is a self-contained trial folder, so individual cells can be re-run without touching the rest. See [`model_arm/README.md`](model_arm/README.md) for setup, configs, and the second-order RSA helpers used to compare 8×8 pair-scaling matrices across stories, conditions, and seeds.

The hidden-state probing work (Stage 3) will live in a sibling folder `model_arm/probing/` and reuse the same stimulus loader, sweep convention, and RDM/RSA machinery; see the top-level README for the plan.

## Before deployment

Checklist (full version in §3.3 of `implementation_documentation`):

1. Replace consent-text placeholders in `src/intro.js`: `[INSTITUTION]`, `[ETHICS_REF]`, `[RESEARCHER]`, `[EMAIL]`, `[SUPERVISOR]`, `[SUPERVISOR_EMAIL]`.
2. Set `CONFIG.prolific.completion_url` in `src/config.js` to the study-specific Prolific completion URL.
3. Confirm `CONFIG.debug.enabled = false` (it is, by default).
4. Deploy the flat file set to Cognition (`python3 scripts/deploy_to_cognition.py`, or upload `src/*.js` and `stimuli/*.js` in the order given in `index.html`).
5. In the Cognition task, set **Design → Configuration → Advanced → Inter experiment conditions = 60**. This is the number of *assignment slots*, not the 3 experimental conditions: Cognition keeps the 60 slots at equal N server-side and injects a global `CONDITION`, which `src/main.js` maps to `pIndex` (`CONDITION % 60`). Both the story set (`stimuli/assignments.js`) and the experimental condition (`pIndex % 3`, `src/condition.js`) are then derived from that one balanced index, giving exact 20/20/20 conditions and 40 reads per story at n = 60.
6. Configure Prolific to pass `PROLIFIC_PID`, `STUDY_ID`, `SESSION_ID` as URL parameters (the experiment reads these automatically). Do **not** append `?pIndex=` or `?condition=` to the Prolific link — that would pin every participant to one slot and defeat the balancer. `?pIndex=N` remains available for manual/local piloting only.
7. Recruit until you have exactly 60 *completed* runs per cycle (multiples of 60 for additional cycles). Balance does **not** self-heal automatically — see *Keeping the balance exact during collection* below.

## Keeping the balance exact during collection

Cognition assigns the balancing slot (`CONDITION`) at **page load — before the consent screen** — and its balancer counts **finished, unfinished, and declined** runs toward each slot's N. A participant who opens the task and then declines consent or drops out has therefore *claimed a slot* that will never produce a completed response. Left alone, that slot's condition (and its story set) ends up under-filled by one, and over-recruiting does **not** fix it: Cognition still treats the abandoned slot as filled and assigns the next participant elsewhere.

To preserve the exact 20/20/20 (and 40 reads/story) guarantee:

1. **Monitor as you go.** In Cognition, watch the per-slot run counts (and check `condition` / `assignment_id` in the export). You want each of the 60 slots to reach exactly one *completed* run.
2. **Delete non-completing runs.** When a participant declines consent, returns on Prolific, or times out, **delete their run in Cognition**. Cognition recalculates balance from stored runs, which reopens that slot so the next participant fills it. (Deleting the run is what frees the slot — recruiting more without deleting will not.)
3. **Let Prolific replace them.** Returned/timed-out submissions are automatically re-listed by Prolific, so you keep drawing participants until 60 slots are each completed once.
4. **Verify at the end.** Run `python3 scripts/balance_check_export.py EXPORT.json --completed-only` on the Cognition export. It reports condition counts (want 20/20/20), which of the 60 slots are filled / **missing** / **duplicated**, story reads, the story × condition crosstab, and consent/completion flags — so you can see at a glance which slots still need a completed run. Extras (from over-recruiting) are the only expected deviation; drop or account for them in analysis.

Genuine no-consent is rare on Prolific; mid-session dropout over the ~50-minute battery is the more common source of empty slots. Both are handled the same way (delete the run).
