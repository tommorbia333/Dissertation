// tasks/comprehension.js — comprehension check component.
//
// Per task design §5.2:
//   - 6 yes/no/unsure items per story
//   - Randomised item order
//   - Logged per-item response times
//
// Implementation choices:
//   - One item per screen (clean per-item RT).
//   - Fixed answer order: [Yes, No, Unsure] left-to-right.
//   - Back button is offered on items 2..N (NOT on item 1, and never crosses
//     the task boundary into the story-reading screen — the story is read once).
//   - "Question N of 6" indicator + "Story X of Y · Comprehension" badge.
//   - A pre-ordering gate (buildBlockWithPreOrderingGate) lets participants
//     return to the comprehension block before ordering; the story is not shown
//     again. State resets on repeat (see Utils.buildLoopWithBack._resetIteration).
//   - Emits one data row per visit (forward + back), plus a summary row whose
//     stats are computed from the LATEST response per item.
//   - Rushed (< 1.5 s) and Slow (> 30 s) responses are FLAGGED, not excluded.

var ComprehensionTask = (function () {

  function escapeHtml(s) { return Utils.escapeHtml(s); }

  /**
   * Build the full comprehension block for one story: a single dynamic loop
   * trial covering the 6 items, followed by a summary trial.
   *
   * @param {string} storyId
   * @param {Object} [opts]
   * @param {number} [opts.storyPosition]  Index 1..N for the story header badge.
   * @param {number} [opts.totalStories]
   */
  function buildBlock(storyId, opts) {
    opts = opts || {};
    var storyItems = COMPREHENSION_ITEMS.stories[storyId];
    if (!storyItems) {
      throw new Error('No comprehension items found for story_id=' + storyId);
    }
    var items = storyItems.items.slice();
    if (CONFIG.comprehension.randomize_item_order) {
      items = Utils.shuffle(items);
    }

    var options  = CONFIG.comprehension.response_options;        // ['Yes','No','Unsure']
    var rushedMs = CONFIG.comprehension.response_time_flag_ms;
    var slowMs   = CONFIG.comprehension.response_time_slow_flag_ms;

    // Final-response store keyed by item index in the (possibly shuffled) list.
    var finalResponses = new Array(items.length).fill(null);
    var firstItemTime  = null;
    var lastItemTime   = null;

    var loopTrial = Utils.buildLoopWithBack({
      items: items,
      header: {
        storyPosition: opts.storyPosition,
        totalStories:  opts.totalStories,
        taskLabel:     'Comprehension',
        stepNoun:      'Question',
      },
      onLoopStart: function () {
        for (var r = 0; r < finalResponses.length; r++) finalResponses[r] = null;
        firstItemTime = null;
        lastItemTime = null;
      },
      render: function (item /*, idx, total */) {
        return [
          '<div class="comp-container">',
          '  <p class="comp-prompt">' + escapeHtml(item.text) + '</p>',
          '</div>',
        ].join('\n');
      },
      choices: options,
      buttonClass: 'comp-btn',
      data: function (item, idx) {
        return {
          task:           'comprehension_item',
          story_id:       storyId,
          item_id:        item.id,
          item_role:      item.role,
          item_events:    item.events,
          item_text:      item.text,
          correct_response: item.correct,
          item_index:     idx,
          n_items_total:  items.length,
        };
      },
      onAnswer: function (data, item, idx, choiceIdx) {
        var chosen    = options[choiceIdx];
        var isCorrect = (chosen === item.correct);
        var rushed    = data.rt != null && data.rt < rushedMs;
        var slow      = data.rt != null && data.rt > slowMs;

        var events = [
          { t: 0,        type: 'item_shown' },
          { t: data.rt,  type: 'response_clicked', choice: chosen },
        ];

        var row = DataHelpers.composeTrialRow({
          trial_type:       'comprehension_item',
          task:             'comprehension_item',
          story_id:         storyId,
          item_id:          item.id,
          item_text:        item.text,
          item_role:        item.role,
          item_events:      item.events,
          response:         chosen,
          response_index:   choiceIdx,
          correct_response: item.correct,
          is_correct:       isCorrect,
          rt_ms:            data.rt,
          rushed_flag:      rushed,
          slow_flag:        slow,
          events:           events,
        });
        Object.keys(row).forEach(function (k) { data[k] = row[k]; });

        // Latest visit's response wins for the summary.
        finalResponses[idx] = {
          item_id:    item.id,
          item_role:  item.role,
          item_text:  item.text,
          correct:    item.correct,
          chosen:     chosen,
          is_correct: isCorrect,
          rushed:     rushed,
          slow:       slow,
          rt:         data.rt,
        };
        if (firstItemTime === null) {
          firstItemTime = data.time_elapsed - (data.rt || 0);
        }
        lastItemTime = data.time_elapsed;
      },
      onBack: function (data, item, idx) {
        data.trial_type = 'comprehension_back';
        data.task       = 'comprehension_item';
        data.story_id   = storyId;
        data.item_id    = item.id;
        data.item_index = idx;
      },
    });

    var summaryTrial = {
      type: jsPsychCallFunction,
      func: function () { return null; },
      on_finish: function (data) {
        var responded = finalResponses.filter(function (r) { return r != null; });
        var nTotal    = responded.length;
        var nCorrect  = responded.filter(function (r) { return r.is_correct; }).length;
        var nRushed   = responded.filter(function (r) { return r.rushed; }).length;
        var nSlow     = responded.filter(function (r) { return r.slow; }).length;

        data.trial_type    = 'comprehension_summary';
        data.task          = 'comprehension_summary';
        data.story_id      = storyId;
        data.n_items       = nTotal;
        data.n_correct     = nCorrect;
        data.n_rushed      = nRushed;
        data.n_slow        = nSlow;
        data.accuracy      = nTotal > 0 ? (nCorrect / nTotal) : null;
        data.block_rt_ms   = (lastItemTime != null && firstItemTime != null)
          ? Math.round(lastItemTime - firstItemTime)
          : null;
        data.presentation_order = items.map(function (it) { return it.id; });
        data.final_responses = finalResponses.map(function (r, i) {
          return r ? {
            item_id:    r.item_id,
            item_role:  r.item_role,
            chosen:     r.chosen,
            is_correct: r.is_correct,
          } : { item_id: items[i].id, chosen: null, is_correct: null };
        });
      },
    };

    return [loopTrial, summaryTrial];
  }

  /**
   * Comprehension + summary, then a gate: participants may return to the
   * comprehension block (the story is not re-shown). The outer node repeats
   * while "Back" is selected on the gate. Uses loop._resetIteration to reset
   * state when a repeat runs (see Utils.buildLoopWithBack).
   */
  function buildBlockWithPreOrderingGate(storyId, opts) {
    var block = buildBlock(storyId, opts);
    var loop = block[0];
    var summary = block[1];

    var gate = {
      type: jsPsychHtmlButtonResponse,
      stimulus: [
        '<div class="comp-ordering-gate">',
        '<h3>Ready for the next task?</h3>',
        '<p>Next you will <strong>arrange the events in chronological order</strong> (drag and drop). ',
        'If you need to, you can <strong>go back to the comprehension questions</strong> to change an answer. ',
        'The <strong>story text will not be shown again</strong>.</p>',
        '</div>',
      ].join('\n'),
      choices: [
        'Back to the comprehension questions',
        'Continue to the ordering task',
      ],
      button_layout: 'flex',
      data: { task: 'comp_pre_ordering_gate' },
    };

    var compSection = {
      timeline: [loop, summary, gate],
      loop_function: function (data) {
        var d = Utils.lastDataFromSessionIter(data);
        if (d && d.task === 'comp_pre_ordering_gate' && d.response === 0) {
          if (loop && typeof loop._resetIteration === 'function') {
            loop._resetIteration();
          }
          return true; // re-run [comp, summary, gate] without re-showing the story
        }
        return false;
      },
    };

    return [compSection];
  }

  return {
    buildBlock: buildBlock,
    buildBlockWithPreOrderingGate: buildBlockWithPreOrderingGate,
  };
})();
