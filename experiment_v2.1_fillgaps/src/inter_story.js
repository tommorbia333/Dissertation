// inter_story.js — between-story break screens with progress indicator.
//
// Per CONFIG.session.inter_story_break:
//   'optional'     → "Story N of 4. Take a break if you like, then Continue."
//   'mandatory_30s' → Continue button disabled for 30s
//   'none'         → no screen inserted
//
// Always shows a progress indicator: "Story N of 4".

var InterStoryScreen = (function () {

  function buildTrial(storyPosition, totalStories) {
    var mode = CONFIG.session.inter_story_break || 'optional';
    if (mode === 'none') return null;

    var mandatoryWaitMs = (mode === 'mandatory_30s') ? 30000 : 0;
    var t0 = null;

    return {
      type: jsPsychHtmlButtonResponse,
      stimulus: [
        '<div class="inter-story">',
        '<div class="progress-indicator">Story ' + storyPosition + ' of ' + totalStories + '</div>',
        '<h2>Short break</h2>',
        (storyPosition === 1)
          ? '<p>You are about to read the first story. When you are ready, click <em>Continue</em>.</p>'
          : '<p>Take a short break if you like. When you are ready for the next story, click <em>Continue</em>.</p>',
        (mandatoryWaitMs > 0)
          ? '<p id="wait-msg" class="debug-note"><small>The Continue button will become available in a moment.</small></p>'
          : '',
        '</div>',
      ].join(''),
      choices: ['Continue'],
      button_html: function (choice) {
        var disabled = (mandatoryWaitMs > 0) ? ' disabled="disabled"' : '';
        return '<button id="inter-continue" class="jspsych-btn"' + disabled + '>' + choice + '</button>';
      },
      data: {
        task: 'inter_story_break',
        story_position: storyPosition,
        total_stories: totalStories,
      },
      on_load: function () {
        t0 = performance.now();
        if (mandatoryWaitMs > 0) {
          setTimeout(function () {
            var btn = document.getElementById('inter-continue');
            if (btn) btn.removeAttribute('disabled');
            var msg = document.getElementById('wait-msg');
            if (msg) msg.style.display = 'none';
          }, mandatoryWaitMs);
        }
      },
      on_finish: function (data) {
        data.break_duration_ms = Math.round(performance.now() - t0);
      },
    };
  }

  return { buildTrial: buildTrial };
})();
