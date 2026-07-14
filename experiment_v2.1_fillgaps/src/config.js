// config.js — global configuration for the experiment
// All tunable parameters and preregistered constants live here.
//
// *** FILL-GAPS VARIANT ***
// This is a copy of experiment_v2.1/src/config.js for a small top-up study
// that only recruits the 6 preregistered slots the main 60-slot study is
// still missing (assignment_id 11, 18, 24, 33, 47, 52 — see
// stimuli/assignments.js in this folder for details). The ONLY substantive
// differences from the main config are:
//   - experiment_version has a "-fillgaps" suffix so exported rows are
//     trivially distinguishable from the main study's export.
//   - n_assignments_cycle is 6, matching this folder's filtered
//     stimuli/assignments.js (main study uses 60).
// Everything else (task parameters, attention check, session structure) is
// unchanged so the two studies stay methodologically identical.

var CONFIG = {
  // ---- Versioning ----
  experiment_version: '0.1.0-dev-fillgaps',
  jspsych_version: '8.2.1',  // pin the exact patch version used in the preregistered build
  build_date_iso: '2026-04-23',

  // ---- CDN URLs for jsPsych 8.x plugins (loaded from index.html) ----
  // Kept here for documentation; actual <script> tags are in index.html or
  // injected by the Cognition platform.

  // ---- Task parameters ----
  story_reading: {
    min_reading_time_ms: 60000,   // 60s floor; continue button disabled until reached
    show_timer_to_participant: false, // do not display reading clock to ppts
  },
  comprehension: {
    response_options: ['Yes', 'No', 'Unsure'],
    response_time_flag_ms: 1500,       // flag (not exclude) responses faster than this
    response_time_slow_flag_ms: 30000, // flag (not exclude) responses slower than this
    randomize_item_order: true,
  },
  ordering: {
    // Preregistered fixed scrambled starting order.
    // Satisfies: derangement; tau=14/28 to canonical E1..E8; tau=14/28 to C-B-A-D;
    // no block adjacencies; no ascending canonical run of length >=3.
    scrambled_start_order: ['E2', 'E4', 'E5', 'E8', 'E6', 'E7', 'E3', 'E1'],
    confidence_scale_min: 1,
    confidence_scale_max: 7,
    confidence_scale_min_label: 'Not at all confident',
    confidence_scale_max_label: 'Completely confident',
  },
  pair_scaling: {
    n_pairs_per_story: 56,        // 8×8 directed, excluding diagonal
    scale_min: 0,
    scale_max: 6,
    randomize_pair_order: true,
    randomize_ab_assignment: true,
  },
  counterfactual: {
    scale_labels: [
      'Much less likely',
      'Slightly less likely',
      'No change',
      'Slightly more likely',
      'Much more likely',
    ],
  },

  // ---- Counterbalancing ----
  n_stories_per_participant: 4,
  n_conditions: 3,
  conditions: ['linear', 'nonlinear', 'atemporal'],
  n_assignments_cycle: 6,  // FILL-GAPS VARIANT: matches the 6-row filtered stimuli/assignments.js
  // Participant pool (six of the eight source domains). The remaining two
  // (`care_home_incident` and `family_conflict`) stay in the source stimulus
  // files for the computational pipeline but are filtered out of the human
  // timeline by virtue of not appearing in any assignment row.
  participant_pool_domains: [
    'hospital_incident',
    'community_fair',
    'restaurant_fire',
    'school_trip',
    'power_cut',
    'missed_flight',
  ],
  computational_only_domains: [
    'care_home_incident',
    'family_conflict',
  ],

  // ---- Logging ----
  // 'detail' = trial-summary + nested event trace (recommended, supports raw-behavior auditing)
  // 'summary' = trial-summary only (smaller files, analysis-ready)
  logging_level: 'detail',

  // ---- Prolific integration ----
  prolific: {
    // TODO before deployment: point this at whichever Prolific study you use
    // to recruit for this fill-gaps task (a brand-new study, or a new
    // "completion path" on the existing one — your choice). Left identical
    // to the main study's codes as a starting point; Cognition/Prolific
    // will reject a completion code that doesn't match what's configured on
    // the Prolific study side, so update this if you set up a new study.
    completion_url: 'https://app.prolific.com/submissions/complete?cc=C1LQCAE4',
    // Screen-out completion URL for participants who decline consent. Set this
    // to a Prolific "screen out" completion code so non-consenting participants
    // are returned to Prolific without counting against paid submission slots
    // (Prolific → Completion paths → add a screen-out path). If left null, the
    // consent-refusal screen simply asks the participant to close the browser.
    screen_out_url: 'https://app.prolific.com/submissions/complete?cc=C11W5NB1',
    // If true, redirect automatically after the debrief screen.
    // If false, display the completion URL for the participant to click.
    auto_redirect: true,
    // Delay (ms) before redirect — buffer for data upload to Cognition.
    redirect_buffer_ms: 2000,
  },

  // ---- Session-start attention check ----
  attention_check: {
    enabled: true,
    prompt: 'It is important that you read instructions carefully. To confirm that you are paying attention, please select "Orange" below, regardless of your actual colour preference.',
    options: ['Red', 'Blue', 'Green', 'Yellow', 'Orange', 'Purple'],
    correct_option: 'Orange',
    // If false, failing the check just flags the data; the session continues.
    reject_on_fail: false,
  },

  // ---- Session structure ----
  session: {
    show_progress_indicator: true,    // "Story N of 4" between stories
    inter_story_break: 'optional',    // 'optional' | 'mandatory_30s' | 'none'
    min_screen_width_px: 900,         // desktop-only; blocks narrow viewports
    min_screen_height_px: 600,
  },

  // ---- Debug ----
  debug: {
    enabled: false,               // set true during local dev
    skip_consent: false,
    skip_demographics: false,
    force_condition: null,        // 'linear' | 'nonlinear' | 'atemporal' | null
    force_assignment_id: null,    // 0..5 (LOCAL array index into this file's 6-row table) | null
  },
};
