// tasks/story_reading.js — story reading component.
//
// Behaviour (per task design §4):
//   - Displays the story (linear/nonlinear/atemporal) as a single scrollable block.
//   - Continue button is disabled until min_reading_time_ms has elapsed.
//   - Reading time is logged (total, continue-enabled, continue-clicked).
//   - Activity tracking: scroll depth, focus loss count + total away time.
//   - No timer shown to the participant by default.
//
// Per CONFIG.logging_level:
//   'summary' → trial-summary row only.
//   'detail'  → trial-summary row + nested `events` array with per-event timestamps.

var StoryReadingTask = (function () {

  function renderStoryHTML(storyData) {
    // storyData is a version record: { events: [{id, text}, ...], ... }.
    // Event IDs are NOT shown to the participant — the text flows as prose.
    var paragraphs = storyData.events.map(function (e) {
      return '<p class="story-event">' + escapeHtml(e.text) + '</p>';
    }).join('\n');
    return [
      '<div class="story-container">',
      '  <div class="story-scroll" id="story-scroll">',
      paragraphs,
      '  </div>',
      '</div>',
    ].join('\n');
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  /**
   * Build a jsPsych trial for reading a single story.
   *
   * @param {Object} opts
   * @param {string} opts.storyId          - Story identifier (key in STORIES)
   * @param {string} opts.condition        - 'linear' | 'nonlinear' | 'atemporal'
   * @param {number} opts.storyPosition    - 1..N position in the participant's sequence
   */
  function buildTrial(opts) {
    var storyId = opts.storyId;
    var condition = opts.condition;
    var storyPosition = opts.storyPosition;
    var storyData = STORIES[storyId].versions[condition];
    var minTimeMs = CONFIG.story_reading.min_reading_time_ms;

    // Closure state, shared between on_load and on_finish.
    var t0 = null;
    var events = [];
    var minTimeReachedAt = null;
    var continueClickedAt = null;
    var detachTracker = null;

    var totalStories = (opts.totalStories != null)
      ? opts.totalStories
      : CONFIG.n_stories_per_participant;
    var headerHTML = Utils.storyHeaderHTML({
      storyPosition: storyPosition,
      totalStories:  totalStories,
      taskLabel:     'Reading',
      stepNoun:      'Page',
      stepIndex:     0,
      stepTotal:     1,
    });

    var stimulus = [
      headerHTML,
      renderStoryHTML(storyData),
      '<div class="reading-footer">',
      '  <p class="reading-instruction" id="reading-instruction">' +
        'Please read the story carefully. The Continue button will appear shortly.' +
      '  </p>',
      '</div>',
    ].join('\n');

    var trial = {
      type: jsPsychHtmlButtonResponse,
      stimulus: stimulus,
      choices: ['Continue'],
      button_html: function (choice) {
        // Inject id + initial disabled state; the timer flips disabled=false.
        return '<button class="jspsych-btn continue-btn" id="continue-btn" disabled="disabled">' +
               choice + '</button>';
      },
      data: {
        task: 'story_reading',
        story_id: storyId,
        condition: condition,
        story_position: storyPosition,
        topology: STORIES[storyId].topology,
      },
      on_load: function () {
        t0 = performance.now();
        events.push({ t: 0, type: 'story_shown' });

        var scrollRoot = document.getElementById('story-scroll');
        detachTracker = Utils.attachActivityTracker(scrollRoot, events, t0);

        // Enable the Continue button after the min-time threshold.
        setTimeout(function () {
          minTimeReachedAt = performance.now() - t0;
          events.push({ t: Math.round(minTimeReachedAt), type: 'min_time_reached' });
          var btn = document.getElementById('continue-btn');
          if (btn) btn.removeAttribute('disabled');
          var instr = document.getElementById('reading-instruction');
          if (instr) instr.textContent = 'You can now continue when you are ready.';
        }, minTimeMs);
      },
      on_finish: function (data) {
        continueClickedAt = performance.now() - t0;
        events.push({ t: Math.round(continueClickedAt), type: 'continue_clicked' });

        var activitySummary = detachTracker ? detachTracker() : {
          scroll_depth_max: null, focus_loss_count: null, focus_loss_total_ms: null,
        };

        // Compose the trial-summary row.
        var row = DataHelpers.composeTrialRow({
          trial_type: 'story_reading',
          task: 'story_reading',
          story_id: storyId,
          story_position: storyPosition,
          topology: STORIES[storyId].topology,
          reading_time_ms: Math.round(continueClickedAt),
          min_threshold_met: continueClickedAt >= minTimeMs,
          continue_enabled_at_ms: minTimeReachedAt !== null ? Math.round(minTimeReachedAt) : null,
          continue_clicked_at_ms: Math.round(continueClickedAt),
          scroll_depth_max: activitySummary.scroll_depth_max,
          focus_loss_count: activitySummary.focus_loss_count,
          focus_loss_total_ms: activitySummary.focus_loss_total_ms,
          events: events.slice(),  // detail log; stripped if logging_level='summary'
        });

        // Merge the row into jsPsych's data. jsPsych records `data` already;
        // we augment with our composed trial row for export parity.
        Object.keys(row).forEach(function (k) { data[k] = row[k]; });
      },
    };

    return trial;
  }

  return {
    buildTrial: buildTrial,
  };
})();
