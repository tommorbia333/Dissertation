// condition.js — between-subjects condition assignment.
//
// Condition is a pure deterministic function of the participant index:
//   condition = CONDITIONS[pIndex mod 3]
// i.e. linear, nonlinear, atemporal, linear, ... This is exactly the
// "stratified" pairing the assignment table in stimuli/assignments.js was
// built and balance-optimised against (see scripts/build_assignments.py):
//   - Over any contiguous set of 60 indices (0..59), each condition is used
//     exactly 20 times — perfect 20/20/20.
//   - The story × condition crosstab lands at the design optimum of 13/14
//     reads per cell.
//
// Balance therefore depends only on the *index* being balanced, which is
// guaranteed upstream by Cognition's server-side 60-way auto-balancer (or by
// passing sequential ?pIndex values). We intentionally do NOT perturb the
// mapping by a hash of the participant ID: doing so re-randomises the
// condition for each index and destroys the exact 20/20/20 guarantee (it
// lands on perfect balance only ~1.5% of the time).

var Condition = (function () {
  var CONDITIONS = CONFIG.conditions; // ['linear', 'nonlinear', 'atemporal']

  /**
   * Assign a condition from the participant's 0-based index.
   * The optional second argument (a seed) is accepted for backward
   * compatibility with existing callers but is deliberately ignored.
   */
  function assignCondition(pIndex) {
    // Debug override takes precedence.
    if (CONFIG.debug && CONFIG.debug.force_condition) {
      return CONFIG.debug.force_condition;
    }
    var n = CONDITIONS.length; // 3
    var idx = ((pIndex % n) + n) % n; // safe for any integer pIndex
    return CONDITIONS[idx];
  }

  return {
    assignCondition: assignCondition,
  };
})();
