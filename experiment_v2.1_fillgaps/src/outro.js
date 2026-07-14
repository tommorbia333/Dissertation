// outro.js — session closing.
//
// Shows:
//   1. Post-task optional comments field
//   2. Debrief (brief and vague enough not to leak design to future participants)
//   3. Prolific redirect (buffered to allow data upload to complete)

var OutroSequence = (function () {

  function escapeHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function commentsTrial() {
    return {
      type: jsPsychSurveyHtmlForm,
      preamble: [
        '<h2>Before you finish</h2>',
        '<p>If you encountered any technical problems or have anything you would like to share about the session, please tell us here. This is optional.</p>',
      ].join(''),
      html: [
        '<div class="comments-form" style="max-width: 560px; margin: 0 auto;">',
        '  <textarea name="comments" rows="5" style="width:100%; font-family:inherit; font-size:15px; padding:0.5em;" placeholder="Any technical problems or comments (optional)..."></textarea>',
        '</div>',
      ].join(''),
      button_label: 'Finish',
      data: { task: 'final_comments' },
      on_finish: function (data) {
        data.final_comments = (data.response && data.response.comments) || '';
      },
    };
  }

  function debriefTrial() {
    // Kept deliberately vague: specific hypotheses and conditions aren't
    // mentioned because Prolific participants discuss studies. The real
    // debrief can be expanded with a link to the post-study information
    // sheet hosted elsewhere.
    return {
      type: jsPsychHtmlButtonResponse,
      stimulus: [
        '<div class="debrief-box">',
        '<h2>Thank you for taking part</h2>',
        '<p>This study is part of research into how people interpret and remember short narratives. Your responses will contribute to understanding how readers construct mental models of events and their relationships.</p>',
        '<p>If you would like to read a full summary of the research once it is complete, you may contact the researcher at the email on the consent page.</p>',
        '<p style="margin-top:1.5em;"><strong>Your data has been recorded.</strong> Click the button below to return to Prolific and register your completion.</p>',
        '</div>',
      ].join(''),
      choices: ['Return to Prolific'],
      data: { task: 'debrief' },
    };
  }

  /**
   * Final redirect trial. Waits CONFIG.prolific.redirect_buffer_ms for data
   * upload to complete, then either auto-redirects or displays the link.
   */
  function redirectTrial() {
    return {
      type: jsPsychHtmlKeyboardResponse,
      stimulus: function () {
        var url = CONFIG.prolific.completion_url;
        if (CONFIG.prolific.auto_redirect) {
          return [
            '<h2>Saving your responses...</h2>',
            '<p>Please wait. You will be redirected to Prolific in a moment.</p>',
            '<p class="debug-note"><small>If nothing happens after a few seconds, <a href="', escapeHtml(url), '">click here</a> to complete.</small></p>',
          ].join('');
        }
        return [
          '<h2>Session complete</h2>',
          '<p>Your responses have been saved.</p>',
          '<p><a href="', escapeHtml(url), '" class="prolific-link"><strong>Click here to return to Prolific and register your completion.</strong></a></p>',
        ].join('');
      },
      choices: 'NO_KEYS',
      trial_duration: function () {
        return CONFIG.prolific.auto_redirect ? CONFIG.prolific.redirect_buffer_ms : null;
      },
      data: { task: 'redirect' },
      on_finish: function () {
        if (CONFIG.prolific.auto_redirect) {
          window.location.href = CONFIG.prolific.completion_url;
        }
      },
    };
  }

  function buildAll() {
    return [commentsTrial(), debriefTrial(), redirectTrial()];
  }

  return { buildAll: buildAll };
})();
