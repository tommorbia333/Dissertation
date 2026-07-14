// data.js — data schema helpers, participant metadata, and save/redirect.
//
// Design principles:
//   - Every trial's data row carries enough metadata to be analysed in
//     isolation (no reliance on trial ordering within the export).
//   - Event-detail logging is controlled by CONFIG.logging_level.
//   - Prolific redirect happens only after data save completes — mitigates
//     the documented Cognition+Prolific race where participants get redirected
//     before the data upload finishes.

var DataHelpers = (function () {
  var _participantMeta = null;

  /** Initialise participant metadata once at the start of the session. */
  function initParticipant(prolificParams, pIndex, condition, assignment) {
    _participantMeta = {
      participant_id: prolificParams.PROLIFIC_PID || Utils.fallbackParticipantId(),
      prolific_study_id: prolificParams.STUDY_ID || null,
      prolific_session_id: prolificParams.SESSION_ID || null,
      participant_index: pIndex,
      condition: condition,
      assignment_id: assignment.assignment_id,
      split: assignment.split,
      order_idx: assignment.order_idx,
      stories_assigned: assignment.stories,
      experiment_version: CONFIG.experiment_version,
      build_date_iso: CONFIG.build_date_iso,
      session_start_iso: Utils.nowISO(),
      user_agent: navigator.userAgent,
    };
    return _participantMeta;
  }

  function getParticipantMeta() { return _participantMeta; }

  /**
   * Compose a trial-summary data row from a task module's payload.
   * The `payload` should be an object containing trial-level fields.
   * If logging_level is 'detail', any `events` array in the payload is kept;
   * otherwise it is stripped.
   */
  function composeTrialRow(payload) {
    var row = Object.assign({
      participant_id: _participantMeta ? _participantMeta.participant_id : null,
      condition: _participantMeta ? _participantMeta.condition : null,
      assignment_id: _participantMeta ? _participantMeta.assignment_id : null,
      timestamp_iso: Utils.nowISO(),
    }, payload);
    if (CONFIG.logging_level !== 'detail' && row.events) {
      delete row.events;
    }
    return row;
  }

  /**
   * End-of-experiment: ensure any server sync is complete before redirecting.
   * This relies on jsPsych's data being serialised to Cognition's backend.
   * We give a small buffer (2s) and then redirect to Prolific.
   */
  function finishAndRedirect(prolificCompletionURL) {
    // jsPsych 8 saves to Cognition automatically at end of experiment.
    // A buffered final screen lets the upload complete before redirect.
    if (prolificCompletionURL) {
      setTimeout(function () { window.location.href = prolificCompletionURL; }, 2000);
    }
  }

  return {
    initParticipant: initParticipant,
    getParticipantMeta: getParticipantMeta,
    composeTrialRow: composeTrialRow,
    finishAndRedirect: finishAndRedirect,
  };
})();
