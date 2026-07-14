// main.js — timeline entry point.
//
// *** FILL-GAPS VARIANT ***
// Identical to experiment_v2.1/src/main.js except for ONE change, flagged
// below: condition is derived from the picked assignment's own
// `assignment_id` (11/18/24/33/47/52 — see stimuli/assignments.js in this
// folder) instead of from the raw local pIndex (0..5). In the main 60-slot
// study assignment_id === pIndex always, so this was a no-op there; here,
// where a small filtered subset of the original 60 rows is reindexed 0..5,
// using the raw pIndex would silently reassign the WRONG condition
// (linear/nonlinear/atemporal) to most of these story sets, since condition
// is defined as assignment_id mod 3, not array-position mod 3.
//
// Timeline (participant-facing study; see DATA_SCHEMA.md §3):
//   [Intro] browser check → welcome → consent → demographics → IMC → instructions
//   For each story i = 1..4 (drawn from a 6-domain participant pool):
//     Inter-story break screen (progress indicator)
//     Story reading
//     Comprehension (6 items + summary) + optional gate to re-enter comp before ordering
//     Ordering (8-card drag + confidence slider)
//     Pair scaling (56 pairs + 8x8 matrix summary)
//   [Outro] comments → debrief → Prolific redirect
//
// The counterfactual-probe task (`src/tasks/counterfactual.js`) and its
// stimuli (`stimuli/cf_probes.js`) are intentionally retained but not
// invoked here; they remain available to the computational pipeline.

var jsPsych;  // exposed as a global so sub-modules (intro, outro) can end early

(function () {
  jsPsych = initJsPsych({
    on_finish: function () {
      // Save handled by Cognition / hosting backend automatically.
      // For local testing, dump to the page so we can eyeball the data.
      if (CONFIG.debug && CONFIG.debug.enabled) {
        jsPsych.data.displayData('json');
      }
    },
  });

  // ---- Determine participant identity and assignment ----
  var urlParams = Utils.getURLParams();
  var participantIdStr = urlParams.PROLIFIC_PID || Utils.fallbackParticipantId();

  // Participant index (0..5 in this fill-gaps variant) drives which of the 6
  // filtered story sets a participant gets. Resolution priority:
  //   1. Explicit ?pIndex=N in the URL — manual control / piloting.
  //   2. Cognition's server-side balancer. Configure the task with 6
  //      "inter experiment conditions"; the platform injects a global
  //      CONDITION kept at equal N across participants. CONDITION % 60
  //      (kept wide on purpose — see note below) then gets reduced further
  //      to 0..5 by Selection.assignStories via ASSIGNMENTS.cycle_length.
  //   3. Off-platform fallback (local testing / non-Cognition hosting):
  //      hash of the participant ID. Approximate balance only.
  // NOTE: the outer `% 60` below is intentionally left as-is (not `% 6`):
  // for any CONDITION value Cognition actually sends (0..5 or 1..6 for a
  // 6-inter-experiment-condition task), `% 60` is a no-op (value unchanged),
  // and the real reduction to this file's 6-row cycle happens inside
  // Selection.assignStories (`% ASSIGNMENTS.cycle_length`). This keeps this
  // file identical in spirit to the main study's main.js.
  var pIndex;
  if (urlParams.pIndex !== undefined && urlParams.pIndex !== '') {
    pIndex = parseInt(urlParams.pIndex, 10);
  } else if (typeof CONDITION !== 'undefined' && CONDITION !== null && CONDITION !== '') {
    pIndex = ((parseInt(CONDITION, 10) % 60) + 60) % 60;
  } else {
    var h = 0;
    for (var i = 0; i < participantIdStr.length; i++) {
      h = ((h << 5) - h + participantIdStr.charCodeAt(i)) | 0;
    }
    pIndex = Math.abs(h);
  }

  // *** FILL-GAPS CHANGE (vs. main study's main.js) ***
  // Pick the assignment first, then derive condition from ITS OWN
  // assignment_id (not from pIndex), so each restored story set keeps the
  // exact condition it was preregistered with in the full 60-slot design.
  var assignment = Selection.assignStories(pIndex);
  var condition = Condition.assignCondition(assignment.assignment_id);
  var participantMeta = DataHelpers.initParticipant(urlParams, pIndex, condition, assignment);

  jsPsych.data.addProperties({
    participant_id: participantMeta.participant_id,
    condition: condition,
    assignment_id: assignment.assignment_id,
    experiment_version: CONFIG.experiment_version,
  });

  // ---- Build the timeline ----
  var timeline = [];

  IntroSequence.buildAll().forEach(function (t) { timeline.push(t); });

  var totalStories = assignment.stories.length;
  assignment.stories.forEach(function (storyId, idx) {
    var storyPosition = idx + 1;

    var breakTrial = InterStoryScreen.buildTrial(storyPosition, totalStories);
    if (breakTrial) timeline.push(breakTrial);

    timeline.push(StoryReadingTask.buildTrial({
      storyId: storyId,
      condition: condition,
      storyPosition: storyPosition,
      totalStories: totalStories,
    }));

    var taskOpts = { storyPosition: storyPosition, totalStories: totalStories };
    ComprehensionTask.buildBlockWithPreOrderingGate(storyId, taskOpts).forEach(function (t) {
      timeline.push(t);
    });
    timeline.push(OrderingTask.buildTrial({
      storyId: storyId,
      storyPosition: storyPosition,
      totalStories: totalStories,
    }));
    PairScalingTask.buildBlock(storyId, taskOpts).forEach(function (t) { timeline.push(t); });
  });

  OutroSequence.buildAll().forEach(function (t) { timeline.push(t); });

  jsPsych.run(timeline);
})();
