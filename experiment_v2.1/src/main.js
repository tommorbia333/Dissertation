// main.js — timeline entry point.
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

  // Participant index (0..59) drives BOTH story assignment and condition, so a
  // single balanced index guarantees the full preregistered design.
  // Resolution priority:
  //   1. Explicit ?pIndex=N in the URL — manual control / piloting.
  //   2. Cognition's server-side balancer. Configure the task with 60
  //      "inter experiment conditions"; the platform injects a global
  //      CONDITION kept at equal N across participants. CONDITION % 60 yields
  //      a balanced 0..59 index whether the platform numbers its conditions
  //      0..59 or 1..60 (both are a bijection onto 0..59).
  //   3. Off-platform fallback (local testing / non-Cognition hosting):
  //      hash of the participant ID. Approximate balance only.
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

  var condition = Condition.assignCondition(pIndex);
  var assignment = Selection.assignStories(pIndex);
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
