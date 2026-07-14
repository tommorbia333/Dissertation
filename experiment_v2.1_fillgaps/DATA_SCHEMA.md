# Data Export Schema

**Experiment:** Temporal Scaffolding and Causal World-Models in Narrative Comprehension
**Version:** 0.1.0-dev
**Platform:** jsPsych 8.x hosted on Cognition.run, recruitment via Prolific

This document specifies the structure of the data exported by the experiment and is intended as operational reference material for analysis scripts.

**Domain pool (human side).** The participant-facing study draws from
six domains: `hospital_incident`, `community_fair`, `restaurant_fire`,
`school_trip`, `power_cut`, `missed_flight`. Each participant reads four.
The two remaining source domains (`care_home_incident`,
`family_conflict`) are kept in the source stimulus files for the
computational pipeline but never appear in human data.

---

## 1. Export format

Cognition exports participant data as CSV (one row per trial) and JSON (structured). The JSON export is preferred for analysis because it preserves the nested `events` arrays and any array-valued fields (e.g., `directed_matrix`, `events`).

Each row carries all jsPsych-standard fields (`trial_index`, `trial_type`, `time_elapsed`, `rt`, `response`, etc.) plus the study-specific fields documented below.

## 2. Universal fields (on every row)

Added via `jsPsych.data.addProperties` in `src/main.js`:

| Field | Type | Description |
|---|---|---|
| `participant_id` | string | Prolific PID or fallback `anon_xxx` |
| `condition` | `'linear' \| 'nonlinear' \| 'atemporal'` | Between-subjects assignment |
| `assignment_id` | integer 0–59 | Index into the 60-row preregistered 4-of-6 BIBD × Williams allocator table |
| `experiment_version` | string | `CONFIG.experiment_version` |

Trial rows also carry (from jsPsych core):

| Field | Type | Description |
|---|---|---|
| `trial_index` | integer | Position in the timeline |
| `trial_type` | string | jsPsych plugin name |
| `time_elapsed` | ms | Time since experiment start |
| `rt` | ms | Response time on the trial |

## 3. Task-specific rows

Each custom row is identified by its `task` field.

### 3.1 Intro / session-management rows

| `task` | Fields of interest |
|---|---|
| `browser_check` | `viewport_width`, `viewport_height`, `is_mobile`, `user_agent` |
| `welcome` | — |
| `consent` | `consent_given` (bool) |
| `demographics` | `age` (int), `english_l1` (`'yes' \| 'no_fluent'`), `education` (categorical) |
| `attention_check` | `attn_chosen` (string), `attn_correct` (bool) |
| `instructions` | — |
| `inter_story_break` | `story_position`, `total_stories`, `break_duration_ms` |
| `final_comments` | `final_comments` (free-text string) |
| `debrief` | — |
| `redirect` | — |

### 3.2 Story reading (`task: 'story_reading'`)

One row per story.

| Field | Type | Description |
|---|---|---|
| `story_id` | string | e.g., `hospital_incident` |
| `condition` | categorical | Redundant with universal field but kept for convenience |
| `story_position` | 1–4 | Position in participant's sequence |
| `topology` | string | Story topology (e.g., `convergent`) |
| `reading_time_ms` | ms | Total time from story display to Continue click |
| `min_threshold_met` | bool | Whether `reading_time_ms ≥ CONFIG.story_reading.min_reading_time_ms` |
| `continue_enabled_at_ms` | ms | When the Continue button became available |
| `continue_clicked_at_ms` | ms | When the participant clicked Continue |
| `scroll_depth_max` | 0–1 | Maximum scroll depth reached |
| `focus_loss_count` | int | Number of tab/window focus losses |
| `focus_loss_total_ms` | ms | Total time with window unfocused |
| `events` (detail only) | array | `[{t, type, depth?}, ...]` with events: `story_shown`, `scroll`, `focus_loss`, `focus_return`, `min_time_reached`, `continue_clicked` |

### 3.3 Comprehension — items (`task: 'comprehension_item'`)

Six rows per story, one per item.

| Field | Type | Description |
|---|---|---|
| `story_id` | string | — |
| `item_id` | string | e.g., `hosp_3` |
| `item_text` | string | Verbatim item prompt |
| `item_role` | `'compound' \| 'single' \| 'negative_recall' \| 'distractor'` | Item role (see §3.2 of final doc) |
| `item_events` | array of strings | Event IDs the item covers (may be empty for distractors) |
| `response` | `'Yes' \| 'No' \| 'Unsure'` | Participant's answer |
| `response_index` | 0–2 | Numeric index into the options array |
| `correct_response` | `'Yes' \| 'No'` | The correct answer |
| `is_correct` | bool | Score |
| `rt_ms` | ms | Response time |
| `rushed_flag` | bool | `rt_ms < 1500` |
| `slow_flag` | bool | `rt_ms > 30000` |
| `events` (detail) | array | `item_shown`, `response_clicked` |

### 3.4 Comprehension — summary (`task: 'comprehension_summary'`)

One row per story, emitted after all 6 items.

| Field | Type | Description |
|---|---|---|
| `story_id` | string | — |
| `n_items` | 6 | — |
| `n_correct` | 0–6 | — |
| `n_rushed` | int | Count of items with `rushed_flag = true` |
| `n_slow` | int | Count of items with `slow_flag = true` |
| `accuracy` | 0.0–1.0 | `n_correct / n_items` |
| `block_rt_ms` | ms | Time from first to last item response |
| `presentation_order` | array | Order in which items were shown (randomised) |

This row is the **comprehension data-quality gate** per task design §4.

### 3.5 Ordering (`task: 'ordering'`)

One row per story.

| Field | Type | Description |
|---|---|---|
| `story_id` | string | — |
| `initial_order` | array | Always `['E2','E4','E5','E8','E6','E7','E3','E1']` (preregistered) |
| `final_order` | array | Participant's submitted ordering |
| `confidence_rating` | 1–7 | — |
| `total_time_ms` | ms | — |
| `n_drags_total` | int | Total drag operations (including null-drops) |
| `n_drags_moved` | int | Drag operations that actually moved a card |
| `kendall_tau_to_canonical` | 0–28 | Distance from `E1..E8` (lower = closer to chronology) |
| `events` (detail) | array | `ordering_shown`, `drag_start`, `drag_end_moved`, `drag_end_unchanged`, `confidence_first_touch`, `confidence_change`, `continue_clicked` |

### 3.6 Pair scaling — items (`task: 'pair_scaling_item'`)

56 rows per story.

| Field | Type | Description |
|---|---|---|
| `story_id` | string | — |
| `source_event_id` | `E1..E8` | Antecedent event (the "A") |
| `target_event_id` | `E1..E8` | Consequent event (the "B") |
| `pair_index` | 0–55 | Serial position within this story's pair-scaling block |
| `n_pairs_total` | 56 | — |
| `rating` | 0–6 | 0 = no causal link, 3 = enables/contributes, 6 = direct cause |
| `rt_ms` | ms | — |
| `rushed_flag` | bool | `rt_ms < 500` |
| `events` (detail) | array | `item_shown` (with source/target), `response_clicked` |

### 3.7 Pair scaling — summary (`task: 'pair_scaling_summary'`)

One row per story. **This is the primary RSA input.**

| Field | Type | Description |
|---|---|---|
| `story_id` | string | — |
| `n_pairs` | int | Items completed |
| `n_pairs_expected` | 56 | — |
| `n_rushed` | int | Count of items with `rushed_flag` |
| `block_rt_ms` | ms | Time from first to last item response |
| `directed_matrix` | 8×8 array | `matrix[i][j]` = rating of `EVENT_IDS[i] → EVENT_IDS[j]`, diagonal = `null` |
| `matrix_event_ids` | array | Row/column labels: `['E1','E2','E3','E4','E5','E6','E7','E8']` |
| `presentation_order` | array of `[source, target]` pairs | Full 56-pair sequence used |

### 3.8 Counterfactual probes (NOT EMITTED on the human side)

The counterfactual probe task is **not** part of the participant-facing
timeline as of `experiment_version` 0.1.0-dev (rev. 2026-05-21). The
task module (`src/tasks/counterfactual.js`) and its stimuli
(`stimuli/cf_probes.js`) are retained in the build for use by the
computational pipeline only; no `counterfactual_item` or
`counterfactual_summary` rows will appear in human data exports.

## 4. Participant-level record assembly

For analysis, the canonical per-participant × per-story record is built by:

1. Filter rows by `participant_id` and `story_id`
2. From each task, extract the **summary row** as the analysis-ready unit:
   - `comprehension_summary.accuracy` → quality gate
   - `ordering.final_order`, `ordering.kendall_tau_to_canonical` → temporal axis
   - `pair_scaling_summary.directed_matrix` → 8×8 RSA matrix

3. For item-level analyses (by-role comprehension breakdown, pair-level regressions, probe-level responses), keep the item rows too.

## 5. Detail-level events

When `CONFIG.logging_level === 'detail'` (default), each row carries a nested `events` array with timestamped activity within the trial. Detail events are:

- **Story reading:** `story_shown`, `scroll` (with `depth`), `focus_loss`, `focus_return` (with `away_ms`), `min_time_reached`, `continue_clicked`
- **Comprehension item:** `item_shown`, `response_clicked`
- **Ordering:** `ordering_shown`, `drag_start` / `drag_end_moved` / `drag_end_unchanged` (with `event_id`, `from`, `to`), `confidence_first_touch`, `confidence_change`, `continue_clicked`
- **Pair scaling item:** `item_shown` (with source/target), `response_clicked` (with rating)

These are optional for analysis but enable post-hoc data-quality audits (did participants attend throughout? do rushed responses cluster?).

## 6. Notes on preparation for analysis

- **Matrix reconstruction fallback:** if `directed_matrix` is somehow incomplete, it can be rebuilt from the 56 item rows by iterating `(source_event_id, target_event_id, rating)`.
- **Permutation vs position:** `ordering.final_order` is a permutation of event IDs *in placed order* (first element = what the participant thinks happened first). To get "what position did E1 end up at", invert the permutation.
- **Discrimination index interpretation:** positive values mean the participant distinguishes causal events from control events; near-zero suggests flat responding; negative is diagnostic of confusion or motivated over-rating.
- **Attention check failures are flagged, not excluded** (`attn_correct === false`). Decision on whether to exclude is part of the preregistered exclusion policy, not hard-coded into the data-collection pipeline.
