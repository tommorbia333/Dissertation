// intro.js — session opening.
//
// Order:
//   1. Browser / viewport check (fail-out on mobile and small screens)
//   2. Welcome
//   3. Informed consent (refusal ends session cleanly)
//   4. Demographics (age, native language, optional education)
//   5. Session-start attention check / IMC (flag-don't-eject by default)
//   6. General task instructions (2-page walkthrough)

var IntroSequence = (function () {

  function escapeHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function isTooSmall() {
    var w = window.innerWidth || document.documentElement.clientWidth;
    var h = window.innerHeight || document.documentElement.clientHeight;
    return w < CONFIG.session.min_screen_width_px || h < CONFIG.session.min_screen_height_px;
  }
  function isMobile() {
    return /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent);
  }

  function browserCheckTrial() {
    return {
      type: jsPsychHtmlButtonResponse,
      stimulus: function () {
        var w = window.innerWidth || 0, h = window.innerHeight || 0;
        if (isMobile() || isTooSmall()) {
          return [
            '<h2>Device not supported</h2>',
            '<p>This study requires a desktop or laptop computer with a browser window of at least ',
            CONFIG.session.min_screen_width_px, '×', CONFIG.session.min_screen_height_px, ' pixels.</p>',
            '<p>Your window is currently <strong>', w, '×', h, '</strong> pixels',
            isMobile() ? ' (mobile device detected)' : '', '.</p>',
            '<p>Please return this study on Prolific so you are not charged.</p>',
          ].join('');
        }
        return [
          '<h2>Browser check passed</h2>',
          '<p>Your browser and screen size are suitable for this study.</p>',
        ].join('');
      },
      choices: function () {
        return (isMobile() || isTooSmall()) ? [] : ['Continue'];
      },
      data: { task: 'browser_check' },
      on_finish: function (data) {
        data.viewport_width = window.innerWidth || null;
        data.viewport_height = window.innerHeight || null;
        data.is_mobile = isMobile();
        data.user_agent = navigator.userAgent;
      },
    };
  }

  function welcomeTrial() {
    return {
      type: jsPsychHtmlButtonResponse,
      stimulus: function () {
        var meta = DataHelpers.getParticipantMeta();
        return [
          '<h2>Welcome</h2>',
          '<p>Thank you for agreeing to take part in this study.</p>',
          '<p>In this session you will read four short stories and answer a series of questions about each one. ',
          'The session takes between 45-60 minutes to complete.</p>',
          '<p>Please find a quiet place where you will not be interrupted, and work through the tasks at your own pace.</p>',
          (CONFIG.debug && CONFIG.debug.enabled && meta)
            ? '<p class="debug-note"><small>Participant: ' + escapeHtml(meta.participant_id)
                + ' · Condition: ' + escapeHtml(meta.condition)
                + ' · Assignment: #' + meta.assignment_id + '</small></p>'
            : '',
        ].join('');
      },
      choices: ['Continue'],
      data: { task: 'welcome' },
    };
  }

  function consentTrial() {
    // Placeholders: [INSTITUTION], [ETHICS_REF], [RESEARCHER], [EMAIL],
    // [SUPERVISOR], [SUPERVISOR_EMAIL] — replace before deployment.
    return {
      type: jsPsychHtmlButtonResponse,
      stimulus: [
        '<div class="consent-box">',
        '<h2>Informed consent</h2>',
        '<p><strong>Purpose.</strong> This research is about how people understand and interpret short written stories. It is part of a masters dissertation.</p>',
        '<p><strong>What you will do.</strong> You will read four short stories and answer questions about each one. The whole session takes approximately 45-60 minutes.</p>',
        '<p><strong>Payment.</strong> You will receive the amount shown on Prolific upon successful completion.</p>',
        '<p><strong>Risks and benefits.</strong> There are no anticipated risks beyond those of ordinary online reading. Your participation helps us understand how people construct meaning from narrative.</p>',
        '<p><strong>Data use.</strong> Your responses will be anonymised and stored securely. Only aggregated results will appear in publications. Your Prolific ID links your submission to payment and will be removed from the research dataset before analysis.</p>',
        '<p><strong>Right to withdraw.</strong> You may withdraw at any time by closing this window, without giving a reason. Data already submitted may still be used in aggregate unless you contact the researcher.</p>',
        '<p><strong>Ethics.</strong> This study has been approved by University College London Research Ethics Committee.</p>',
        '<p><strong>Contact.</strong> For questions, contact Tommaso Morini Bianzino at tommaso.bianzino.25@ucl.ac.uk or the supervisor Mario Giulianelli at m.giulianelli@ucl.ac.uk.</p>',
        '<p style="margin-top: 1.8em;"><strong>Do you consent to participate in this study?</strong></p>',
        '</div>',
      ].join(''),
      choices: ['Yes, I consent', 'No, I do not consent'],
      data: { task: 'consent' },
      on_finish: function (data) {
        data.consent_given = (data.response === 0);
        if (!data.consent_given) {
          var screenOutURL = CONFIG.prolific && CONFIG.prolific.screen_out_url;
          if (screenOutURL) {
            jsPsych.abortExperiment(
              '<h2>Thank you</h2>' +
              '<p>You have chosen not to take part. You will be returned to Prolific in a moment.</p>' +
              '<p class="debug-note"><small>If nothing happens, <a href="' + escapeHtml(screenOutURL) + '">click here</a>.</small></p>'
            );
            setTimeout(function () { window.location.href = screenOutURL; },
              (CONFIG.prolific && CONFIG.prolific.redirect_buffer_ms) || 2000);
          } else {
            jsPsych.abortExperiment(
              '<h2>Thank you</h2>' +
              '<p>You may now close this browser.</p>'
            );
          }
        }
      },
    };
  }

  function demographicsTrial() {
    return {
      type: jsPsychSurveyHtmlForm,
      preamble: [
        '<h2>About you</h2>',
        '<p>A few brief questions before we begin.</p>',
      ].join(''),
      html: [
        '<div class="demog-form">',
        '<p><label>Your age in years:<br>',
        '  <input type="number" name="age" min="18" max="120" required style="width:120px"/></label></p>',
        '<p><label>Is English your first language?<br>',
        '  <select name="english_l1" required style="width:220px">',
        '    <option value="">-- please select --</option>',
        '    <option value="yes">Yes</option>',
        '    <option value="no_fluent">No, but I am fluent</option>',
        '  </select></label></p>',
        '<p><label>Highest completed level of education (optional):<br>',
        '  <select name="education" style="width:300px">',
        '    <option value="prefer_not_say">Prefer not to say</option>',
        '    <option value="secondary">Secondary school</option>',
        '    <option value="some_higher">Some further/higher education</option>',
        '    <option value="bachelor">Bachelor\'s degree</option>',
        '    <option value="masters">Master\'s degree</option>',
        '    <option value="doctorate">Doctoral degree</option>',
        '  </select></label></p>',
        '</div>',
      ].join(''),
      button_label: 'Continue',
      data: { task: 'demographics' },
      on_finish: function (data) {
        if (data.response) {
          data.age = data.response.age ? parseInt(data.response.age, 10) : null;
          data.english_l1 = data.response.english_l1 || null;
          data.education = data.response.education || null;
        }
      },
    };
  }

  function attentionCheckTrial() {
    if (!CONFIG.attention_check.enabled) return null;
    var ac = CONFIG.attention_check;
    return {
      type: jsPsychHtmlButtonResponse,
      stimulus: [
        '<div class="attn-check">',
        '<h2>Brief check</h2>',
        '<p>' + escapeHtml(ac.prompt) + '</p>',
        '</div>',
      ].join(''),
      choices: ac.options,
      data: { task: 'attention_check' },
      on_finish: function (data) {
        var chosen = ac.options[data.response];
        data.attn_chosen = chosen;
        data.attn_correct = (chosen === ac.correct_option);
        if (!data.attn_correct && ac.reject_on_fail) {
          jsPsych.abortExperiment(
            '<h2>Study ended</h2>' +
            '<p>Thank you for your time. Please return this study on Prolific.</p>'
          );
        }
      },
    };
  }

  function instructionsTrial() {
    return {
      type: jsPsychInstructions,
      pages: [
        [
          '<h2>What happens in this session</h2>',
          '<p>For each of four stories you will go through this sequence:</p>',
          '<ol style="text-align:left; max-width:540px; margin:1em auto; line-height:1.7;">',
          '  <li><strong>Read the story</strong> at your own pace.</li>',
          '  <li><strong>Answer six brief questions</strong> about what happened.</li>',
          '  <li><strong>Arrange the events</strong> in the order they occurred.</li>',
          '  <li><strong>Rate pairs of events</strong> for how much one caused the other.</li>',
          '</ol>',
          '<p>Nothing is timed. Please take the time you need to answer thoughtfully.</p>',
        ].join(''),
        [
          '<h2>Practical notes</h2>',
          '<ul style="text-align:left; max-width:540px; margin:1em auto; line-height:1.7;">',
          '  <li>Please <strong>do not switch tabs</strong> or leave this window during a task.</li>',
          '  <li>If you need a short break between stories, there will be a pause screen where you can rest.</li>',
          '  <li>There are no trick questions. Answer based on what the stories tell you.</li>',
          '  <li>If something goes wrong, contact the researcher via Prolific.</li>',
          '</ul>',
          '<p>Click <em>Next</em> when you are ready to begin.</p>',
        ].join(''),
      ],
      show_clickable_nav: true,
      button_label_previous: 'Back',
      button_label_next: 'Next',
      data: { task: 'instructions' },
    };
  }

  function buildAll() {
    var trials = [browserCheckTrial(), welcomeTrial(), consentTrial()];
    if (!(CONFIG.debug && CONFIG.debug.skip_demographics)) {
      trials.push(demographicsTrial());
    }
    var ac = attentionCheckTrial();
    if (ac) trials.push(ac);
    trials.push(instructionsTrial());
    return trials;
  }

  return { buildAll: buildAll };
})();
