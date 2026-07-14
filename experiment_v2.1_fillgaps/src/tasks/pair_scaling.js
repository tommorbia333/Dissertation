// tasks/pair_scaling.js — directed pair scaling task (primary RSA data).
//
// Per task design §6:
//   - All 56 ordered pairs (8 × 7, diagonal excluded), one per screen.
//   - Prompt: "How much did [A] cause or contribute to [B]?"
//   - Scale 0–6 with anchors: 0 = no causal link, 3 = enables/contributes,
//     6 = direct cause.
//   - Pair order randomised per participant; A/B direction randomised via
//     shuffling the 56 directed pairs (not 28 unordered).
//   - Back button on pairs 2..56 (not on pair 1, never crosses task boundary).
//   - "Pair N of 56" indicator + "Story X of Y · Causal pairs" badge.
//
// Output (driven by the LATEST visit per pair):
//   - One data row per visit (action: 'answer' or 'back').
//   - One summary row per story (task: 'pair_scaling_summary') containing the
//     full 8×8 directed causal matrix as a nested array, RSA-ready.

var PairScalingTask = (function () {

  var EVENT_IDS = ['E1','E2','E3','E4','E5','E6','E7','E8'];

  function escapeHtml(s) { return Utils.escapeHtml(s); }

  function buildAllOrderedPairs() {
    var pairs = [];
    for (var i = 0; i < 8; i++) {
      for (var j = 0; j < 8; j++) {
        if (i !== j) {
          pairs.push({ source: EVENT_IDS[i], target: EVENT_IDS[j] });
        }
      }
    }
    return pairs;
  }

  function renderStimulusHTML(cards, source, target) {
    return [
      '<div class="pair-scaling-container">',
      '  <div class="pair-card pair-card-source">',
      '    <div class="pair-card-label">' + escapeHtml(cards[source]) + '</div>',
      '  </div>',
      '  <div class="pair-arrow" aria-hidden="true">↓</div>',
      '  <div class="pair-card pair-card-target">',
      '    <div class="pair-card-label">' + escapeHtml(cards[target]) + '</div>',
      '  </div>',
      '  <p class="pair-prompt">',
      '    How much did the first event cause or contribute to the second?',
      '  </p>',
      '</div>',
    ].join('\n');
  }

  function renderAnchorPromptHTML() {
    // One column per scale point (0–6); text labels sit under 0, 3, and 6.
    // CSS .pair-scale-anchors uses a 7-column grid so this lines up with the
    // horizontal row of seven number buttons.
    return [
      '<div class="pair-scale-legend" aria-hidden="true">',
      '  <div class="pair-scale-anchors">',
      '    <span class="pair-anchor" style="grid-column: 1 / 2">no causal link</span>',
      '    <span class="pair-anchor" style="grid-column: 4 / 5">enables / contributes</span>',
      '    <span class="pair-anchor" style="grid-column: 7 / 8">direct cause</span>',
      '  </div>',
      '</div>',
    ].join('\n');
  }

  /**
   * Build a full pair-scaling block for one story: a single dynamic loop trial
   * iterating through 56 pairs (with Back navigation), followed by a summary
   * trial that emits the 8×8 directed causal matrix.
   *
   * @param {string} storyId
   * @param {Object} [opts]
   * @param {number} [opts.storyPosition]
   * @param {number} [opts.totalStories]
   */
  function buildBlock(storyId, opts) {
    opts = opts || {};
    var cards = EVENT_CARDS[storyId];
    if (!cards) throw new Error('No event cards for story_id=' + storyId);

    var pairs = buildAllOrderedPairs();
    if (CONFIG.pair_scaling.randomize_pair_order) {
      pairs = Utils.shuffle(pairs);
    }

    var rushedMs = 500;

    // Final ratings per pair — index aligns with `pairs` ordering.
    var finalRatings = new Array(pairs.length).fill(null);
    var firstItemTime = null;
    var lastItemTime  = null;

    // 8×8 matrix: rebuilt at summary time from finalRatings (avoids stale
    // values when a participant goes back and changes a rating).
    function buildMatrixFromFinals() {
      var m = [];
      for (var i = 0; i < 8; i++) m.push(new Array(8).fill(null));
      for (var k = 0; k < pairs.length; k++) {
        var r = finalRatings[k];
        if (r == null) continue;
        var i0 = EVENT_IDS.indexOf(pairs[k].source);
        var j0 = EVENT_IDS.indexOf(pairs[k].target);
        if (i0 >= 0 && j0 >= 0) m[i0][j0] = r;
      }
      return m;
    }

    var loopTrial = Utils.buildLoopWithBack({
      items: pairs,
      // Flex (default): one full-width Back row, then 0–6 in a single row; see
      // .pair-scaling-btngroup in style.css. Grid 2×4 put Back in the first cell
      // and misaligned the verbal anchors with the scale.
      button_layout: 'flex',
      header: {
        storyPosition: opts.storyPosition,
        totalStories:  opts.totalStories,
        taskLabel:     'Causal pairs',
        stepNoun:      'Pair',
      },
      render: function (pair /*, idx, total */) {
        return renderStimulusHTML(cards, pair.source, pair.target);
      },
      choices: ['0', '1', '2', '3', '4', '5', '6'],
      buttonClass: 'pair-btn',
      prompt: renderAnchorPromptHTML(),
      data: function (pair, idx) {
        return {
          task:            'pair_scaling_item',
          story_id:        storyId,
          source_event_id: pair.source,
          target_event_id: pair.target,
          pair_index:      idx,
          n_pairs_total:   pairs.length,
        };
      },
      onAnswer: function (data, pair, idx, choiceIdx) {
        var rating = choiceIdx;            // 0..6 maps directly
        var rushed = data.rt != null && data.rt < rushedMs;

        var events = [
          { t: 0,       type: 'item_shown', source: pair.source, target: pair.target },
          { t: data.rt, type: 'response_clicked', rating: rating },
        ];

        var row = DataHelpers.composeTrialRow({
          trial_type:      'pair_scaling_item',
          task:            'pair_scaling_item',
          story_id:        storyId,
          source_event_id: pair.source,
          target_event_id: pair.target,
          pair_index:      idx,
          rating:          rating,
          rt_ms:           data.rt,
          rushed_flag:     rushed,
          events:          events,
        });
        Object.keys(row).forEach(function (k) { data[k] = row[k]; });

        finalRatings[idx] = rating;
        if (firstItemTime === null) {
          firstItemTime = data.time_elapsed - (data.rt || 0);
        }
        lastItemTime = data.time_elapsed;
      },
      onBack: function (data, pair, idx) {
        data.trial_type      = 'pair_scaling_back';
        data.task            = 'pair_scaling_item';
        data.story_id        = storyId;
        data.source_event_id = pair.source;
        data.target_event_id = pair.target;
        data.pair_index      = idx;
      },
    });

    var summaryTrial = {
      type: jsPsychCallFunction,
      func: function () { return null; },
      on_finish: function (data) {
        var nDone = finalRatings.filter(function (r) { return r != null; }).length;
        data.trial_type        = 'pair_scaling_summary';
        data.task              = 'pair_scaling_summary';
        data.story_id          = storyId;
        data.n_pairs           = nDone;
        data.n_pairs_expected  = pairs.length;
        data.block_rt_ms       = (lastItemTime != null && firstItemTime != null)
          ? Math.round(lastItemTime - firstItemTime)
          : null;
        data.directed_matrix   = buildMatrixFromFinals();
        data.matrix_event_ids  = EVENT_IDS.slice();
        data.presentation_order = pairs.map(function (p) { return [p.source, p.target]; });
      },
    };

    return [loopTrial, summaryTrial];
  }

  return {
    buildBlock: buildBlock,
    _buildAllOrderedPairs: buildAllOrderedPairs,
  };
})();
