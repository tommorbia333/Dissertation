// selection.js — story selection from the 32-row preregistered assignment table.
//
// assignStories(participantIndex) returns the ordered list of 4 story IDs
// for that participant. Selection is deterministic — participant N always
// receives assignment (N mod 32). This is the counterbalancing guarantee.

var Selection = (function () {
  function assignStories(participantIndex) {
    // Debug override.
    if (CONFIG.debug && CONFIG.debug.force_assignment_id !== null &&
        CONFIG.debug.force_assignment_id !== undefined) {
      return ASSIGNMENTS.assignments[CONFIG.debug.force_assignment_id];
    }
    var idx = ((participantIndex % ASSIGNMENTS.cycle_length) + ASSIGNMENTS.cycle_length) % ASSIGNMENTS.cycle_length;
    return ASSIGNMENTS.assignments[idx];
  }

  return {
    assignStories: assignStories,
  };
})();
