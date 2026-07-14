// tasks/counterfactual.js — counterfactual probes task.
//
// Per task design §7:
//   - 8 probes per story: 6 anchor (E1..E6 → E7) + 1 sibling null + 1 reverse null (E8 → E7).
//   - One probe per screen.
//   - Randomised probe order per participant.
//   - 5-point signed scale: 1 = Much less likely, 3 = No change, 5 = Much more likely.
//   - Probe prompt: "If [antecedent], would [consequent] still have occurred?"
//   - Back button on probes 2..8 (not on probe 1, never crosses task boundary).
//   - "Probe N of 8" indicator + "Story X of Y · Counterfactual" badge.
//   - UI matches pair scaling: Back on its own row, five options in one band,
//     1–5 code row in the legend below the buttons (see renderResponseLegendHTML).
//
// Output (driven by the LATEST visit per probe):
//   - One data row per visit (action: 'answer' or 'back').
//   - One summary row (task: 'counterfactual_summary') with the length-6 anchor
//     vector + 2 null-control ratings + discrimination index (per §7.5).

var CounterfactualTask = (function () {

  var SCALE_LABELS = CONFIG.counterfactual.scale_labels; // length-5 array

  function escapeHtml(s) { return Utils.escapeHtml(s); }

  function renderStimulusHTML(probe) {
    return [
      '<div class="cf-container">',
      '  <p class="cf-prompt">' + escapeHtml(probe.prompt) + '</p>',
      '</div>',
    ].join('\n');
  }

  /** Small 1–5 row under the five response buttons (same column alignment as the pair task legend). */
  function renderResponseLegendHTML() {
    return [
      '<div class="cf-scale-legend" aria-hidden="true">',
      '  <div class="cf-scale-nums" title="1 = most negative, 3 = no change, 5 = most positive">',
      '    <span>1</span><span>2</span><span>3</span><span>4</span><span>5</span>',
      '  </div>',
      '</div>',
    ].join('\n');
  }

  /**
   * Build a full CF block for one story: a single dynamic loop trial covering
   * all 8 probes (with Back navigation), followed by a summary trial.
   *
   * @param {string} storyId
   * @param {Object} [opts]
   * @param {number} [opts.storyPosition]
   * @param {number} [opts.totalStories]
   */
  function buildBlock(storyId, opts) {
    opts = opts || {};
    var storyData = CF_PROBES.stories[storyId];
    if (!storyData) throw new Error('No CF probes for story_id=' + storyId);
    var probes = Utils.shuffle(storyData.probes.slice());

    // Final ratings per probe (latest visit wins). Indexed alongside `probes`.
    var finalByProbeId = {};
    var firstItemTime = null;
    var lastItemTime  = null;

    var loopTrial = Utils.buildLoopWithBack({
      items: probes,
      // Back on its own row, five scale buttons on the next; legend under (see style.css).
      button_layout: 'flex',
      prompt: renderResponseLegendHTML(),
      header: {
        storyPosition: opts.storyPosition,
        totalStories:  opts.totalStories,
        taskLabel:     'Counterfactual',
        stepNoun:      'Probe',
      },
      render: function (probe /*, idx, total */) {
        return renderStimulusHTML(probe);
      },
      choices: SCALE_LABELS,
      buttonClass: 'cf-btn',
      data: function (probe, idx) {
        return {
          task:                  'counterfactual_item',
          story_id:              storyId,
          probe_id:              probe.probe_id,
          probe_role:            probe.role,
          antecedent_event_id:   probe.antecedent_event_id,
          consequent_event_id:   probe.consequent_event_id,
          probe_index:           idx,
          n_probes_total:        probes.length,
        };
      },
      onAnswer: function (data, probe, idx, choiceIdx) {
        var rating = choiceIdx + 1;        // 1..5 on the signed scale
        var label  = SCALE_LABELS[choiceIdx];
        var events = [
          { t: 0,       type: 'probe_shown',     probe_id: probe.probe_id },
          { t: data.rt, type: 'response_clicked', rating: rating, label: label },
        ];

        var row = DataHelpers.composeTrialRow({
          trial_type:           'counterfactual_item',
          task:                 'counterfactual_item',
          story_id:             storyId,
          probe_id:             probe.probe_id,
          probe_role:           probe.role,
          antecedent_event_id:  probe.antecedent_event_id,
          consequent_event_id:  probe.consequent_event_id,
          probe_index:          idx,
          prompt_text:          probe.prompt,
          rating:               rating,
          rating_label:         label,
          rt_ms:                data.rt,
          events:               events,
        });
        Object.keys(row).forEach(function (k) { data[k] = row[k]; });

        finalByProbeId[probe.probe_id] = {
          probe_id:            probe.probe_id,
          role:                probe.role,
          antecedent_event_id: probe.antecedent_event_id,
          consequent_event_id: probe.consequent_event_id,
          rating:              rating,
        };
        if (firstItemTime === null) {
          firstItemTime = data.time_elapsed - (data.rt || 0);
        }
        lastItemTime = data.time_elapsed;
      },
      onBack: function (data, probe, idx) {
        data.trial_type    = 'counterfactual_back';
        data.task          = 'counterfactual_item';
        data.story_id      = storyId;
        data.probe_id      = probe.probe_id;
        data.probe_index   = idx;
      },
    });

    var summaryTrial = {
      type: jsPsychCallFunction,
      func: function () { return null; },
      on_finish: function (data) {
        // Build length-6 anchor vector in canonical E1..E6 order.
        var anchor = ['E1','E2','E3','E4','E5','E6'].map(function (eid) {
          // Anchor probes have antecedent_event_id = eid and role 'anchor'.
          var hit = null;
          Object.keys(finalByProbeId).forEach(function (k) {
            var f = finalByProbeId[k];
            if (f.role === 'anchor' && f.antecedent_event_id === eid) hit = f;
          });
          return hit ? hit.rating : null;
        });
        var sibling = null, reverse = null;
        Object.keys(finalByProbeId).forEach(function (k) {
          var f = finalByProbeId[k];
          if (f.role === 'sibling_null') sibling = f.rating;
          else if (f.role === 'reverse_null') reverse = f.rating;
        });

        // Discrimination index (§7.5): mean anchor magnitude vs mean null magnitude.
        // Magnitude is |rating - 3| (distance from "no change" baseline).
        var anchorMags = anchor.filter(function (v) { return v != null; })
          .map(function (v) { return Math.abs(v - 3); });
        var nullMags = [sibling, reverse].filter(function (v) { return v != null; })
          .map(function (v) { return Math.abs(v - 3); });
        var meanAnchor = anchorMags.length
          ? anchorMags.reduce(function (a, b) { return a + b; }, 0) / anchorMags.length
          : null;
        var meanNull = nullMags.length
          ? nullMags.reduce(function (a, b) { return a + b; }, 0) / nullMags.length
          : null;
        var discrimination = (meanAnchor != null && meanNull != null)
          ? meanAnchor - meanNull
          : null;

        data.trial_type            = 'counterfactual_summary';
        data.task                  = 'counterfactual_summary';
        data.story_id              = storyId;
        data.anchor_vector         = anchor;
        data.sibling_null_rating   = sibling;
        data.reverse_null_rating   = reverse;
        data.discrimination_index  = discrimination;
        data.block_rt_ms           = (lastItemTime != null && firstItemTime != null)
          ? Math.round(lastItemTime - firstItemTime)
          : null;
        data.presentation_order    = probes.map(function (p) { return p.probe_id; });
      },
    };

    return [loopTrial, summaryTrial];
  }

  return {
    buildBlock: buildBlock,
  };
})();
