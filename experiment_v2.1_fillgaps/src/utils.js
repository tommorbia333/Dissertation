// utils.js — small shared helpers. No jsPsych dependencies.

var Utils = (function () {
  /** Parse query-string parameters from the current URL. */
  function getURLParams() {
    var params = {};
    var search = (typeof window !== 'undefined' && window.location && window.location.search) || '';
    var query = search.replace(/^\?/, '');
    if (!query) return params;
    query.split('&').forEach(function (kv) {
      var parts = kv.split('=');
      var k = decodeURIComponent(parts[0] || '');
      var v = decodeURIComponent(parts[1] || '');
      if (k) params[k] = v;
    });
    return params;
  }

  /** ISO timestamp with millisecond precision. */
  function nowISO() {
    return new Date().toISOString();
  }

  /** Generate a short random participant identifier (fallback if no Prolific ID). */
  function fallbackParticipantId() {
    var s = '';
    var chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
    for (var i = 0; i < 8; i++) s += chars[Math.floor(Math.random() * chars.length)];
    return 'anon_' + s;
  }

  /** Shuffle an array in place (Fisher-Yates) and return it. */
  function shuffle(arr) {
    var a = arr.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = a[i]; a[i] = a[j]; a[j] = tmp;
    }
    return a;
  }

  /**
   * Attach activity listeners to a DOM element that reports focus/blur,
   * scroll depth, and arbitrary typed events to a provided event log array.
   *
   * Returns a detach() function to remove listeners.
   */
  function attachActivityTracker(rootElement, eventLog, t0) {
    var maxScrollDepth = 0;
    var focusLossCount = 0;
    var focusLossTotalMs = 0;
    var lastBlurAt = null;

    function relTime() { return performance.now() - t0; }

    function onScroll() {
      var el = rootElement || window.document.scrollingElement || document.documentElement;
      var height = el.scrollHeight - el.clientHeight;
      var depth = height > 0 ? Math.min(1, (el.scrollTop || window.scrollY) / height) : 1;
      if (depth > maxScrollDepth) {
        maxScrollDepth = depth;
        eventLog.push({ t: Math.round(relTime()), type: 'scroll', depth: +depth.toFixed(3) });
      }
    }

    function onBlur() {
      lastBlurAt = relTime();
      focusLossCount += 1;
      eventLog.push({ t: Math.round(lastBlurAt), type: 'focus_loss' });
    }

    function onFocus() {
      if (lastBlurAt !== null) {
        var delta = relTime() - lastBlurAt;
        focusLossTotalMs += delta;
        eventLog.push({ t: Math.round(relTime()), type: 'focus_return', away_ms: Math.round(delta) });
        lastBlurAt = null;
      }
    }

    window.addEventListener('scroll', onScroll, { passive: true });
    if (rootElement) rootElement.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('blur', onBlur);
    window.addEventListener('focus', onFocus);

    function detach() {
      window.removeEventListener('scroll', onScroll);
      if (rootElement) rootElement.removeEventListener('scroll', onScroll);
      window.removeEventListener('blur', onBlur);
      window.removeEventListener('focus', onFocus);
      // Finalise any open blur interval.
      if (lastBlurAt !== null) {
        focusLossTotalMs += relTime() - lastBlurAt;
        lastBlurAt = null;
      }
      return {
        scroll_depth_max: +maxScrollDepth.toFixed(3),
        focus_loss_count: focusLossCount,
        focus_loss_total_ms: Math.round(focusLossTotalMs),
      };
    }
    return detach;
  }

  /**
   * HTML-escape a string for safe insertion into an HTML attribute or text node.
   */
  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  /**
   * Render the small "Story X of Y — TaskName" + "Step N of M" header that goes
   * at the top of every per-story task screen.
   *
   *   storyHeaderHTML({
   *     storyPosition: 2,
   *     totalStories: 4,
   *     taskLabel: 'Comprehension',
   *     stepIndex: 0,         // 0-based current item
   *     stepTotal: 6,
   *     stepNoun: 'Question', // singular noun for the per-task progress
   *   })
   *
   * Either part can be omitted (pass null for storyPosition or stepTotal).
   */
  /**
   * @param {object} data - Last trial, DataCollection, or { values() } from loop_function
   * @returns {object|null} Most recent trial's data
   */
  function lastDataFromSessionIter(data) {
    if (data == null) return null;
    if (data.task) return data;
    if (typeof data.values === 'function') {
      var a = data.values();
      if (a && a.length) return a[a.length - 1];
    }
    if (typeof data.get === 'function') {
      var g = data.get();
      if (g && g.length) return g[g.length - 1];
    }
    return null;
  }

  function storyHeaderHTML(opts) {
    var lines = [];
    if (opts && opts.storyPosition != null && opts.totalStories != null && opts.taskLabel) {
      lines.push(
        '<div class="story-position-badge">Story ' +
        escapeHtml(opts.storyPosition) + ' of ' + escapeHtml(opts.totalStories) +
        ' &middot; ' + escapeHtml(opts.taskLabel) +
        '</div>'
      );
    }
    if (opts && opts.stepTotal != null) {
      var noun = opts.stepNoun || 'Item';
      var n = (opts.stepIndex != null) ? (opts.stepIndex + 1) : 1;
      lines.push(
        '<div class="task-progress">' +
        escapeHtml(noun) + ' ' + n + ' of ' + escapeHtml(opts.stepTotal) +
        '</div>'
      );
    }
    if (lines.length === 0) return '';
    return '<div class="task-progress-row">' + lines.join('') + '</div>';
  }

  /**
   * Build a single jsPsych "loop" trial that iterates through `items`, optionally
   * showing a Back button on every screen except the first. The Back button lets
   * participants return to the immediately preceding item WITHIN the current
   * task (it cannot cross task boundaries because it only navigates this loop).
   *
   * The latest visit's response wins for downstream summaries; earlier visits
   * still appear as data rows but carry `superseded_by_revisit: true`.
   *
   * Spec:
   *   items:         Array of items to iterate (length defines `total`).
   *   render:        function(item, idx, total) -> stimulus HTML (NO buttons).
   *   choices:       Array of answer-button labels (Back is added automatically).
   *   buttonClass:   CSS class added to each ANSWER button (e.g. 'comp-btn').
   *   prompt:        Optional HTML rendered beneath buttons (jsPsych `prompt`).
   *   data:          function(item, idx) -> object of static data fields.
   *   onAnswer:      function(data, item, idx, choiceIdx) — mutate `data` to
   *                    record this trial's response. choiceIdx is 0-based on
   *                    spec.choices (i.e. the Back button is already stripped).
   *   onBack:        function(data, item, idx) — optional, called when Back clicked.
   *   header:        Optional object passed to storyHeaderHTML at each iteration.
   *                    `stepIndex` and `stepTotal` are filled in automatically;
   *                    pass storyPosition / totalStories / taskLabel / stepNoun.
   *
   * Returns: a jsPsych timeline node (a loop containing one dynamic trial).
   *
   * NOTE: this returns a SINGLE `loop` node that produces ONE jsPsych data row
   * per visit. The number of rows is therefore equal to the number of clicks
   * (forward + back). Use the caller-side `responses` accumulator (mutated in
   * onAnswer) for the canonical "final answers" — that is what summary trials
   * should consume.
   */
  function buildLoopWithBack(spec) {
    var items = spec.items;
    var total = items.length;
    var idx = 0;
    var direction = 'forward';

    function progressHTML() {
      var hdrOpts = Object.assign({}, spec.header || {}, {
        stepIndex: idx,
        stepTotal: total,
      });
      return storyHeaderHTML(hdrOpts);
    }

    function fullStimulus() {
      return progressHTML() + spec.render(items[idx], idx, total);
    }

    function currentChoices() {
      var c = spec.choices.slice();
      if (idx > 0) c.unshift('Back');
      return c;
    }

    var trial = {
      type: jsPsychHtmlButtonResponse,
      button_layout: spec.button_layout != null ? spec.button_layout : 'flex',
      stimulus: function () { return fullStimulus(); },
      choices: function () { return currentChoices(); },
      button_html: function (choice, choice_index) {
        var hasBack = idx > 0;
        var isBack = hasBack && choice_index === 0;
        if (isBack) {
          return '<button type="button" class="jspsych-btn back-btn">' +
                 escapeHtml(choice) + '</button>';
        }
        var cls = spec.buttonClass ? (' ' + spec.buttonClass) : '';
        return '<button type="button" class="jspsych-btn' + cls + '">' +
               escapeHtml(choice) + '</button>';
      },
      prompt: spec.prompt || null,
      data: function () {
        var d = (spec.data && typeof spec.data === 'function')
          ? spec.data(items[idx], idx)
          : Object.assign({}, spec.data || {});
        return d;
      },
      on_finish: function (data) {
        var hasBack = idx > 0;
        var clickedBack = hasBack && data.response === 0;
        var actualChoiceIdx = hasBack ? data.response - 1 : data.response;

        data.item_index = idx;
        data.visit_index = data.visit_index || 1;

        if (clickedBack) {
          data.action = 'back';
          if (spec.onBack) spec.onBack(data, items[idx], idx);
          direction = 'back';
        } else {
          data.action = 'answer';
          data.response_index = actualChoiceIdx;
          direction = 'forward';
          if (spec.onAnswer) {
            spec.onAnswer(data, items[idx], idx, actualChoiceIdx);
          }
        }
      },
    };

    if (spec.grid_rows != null) trial.grid_rows = spec.grid_rows;
    if (spec.grid_columns != null) trial.grid_columns = spec.grid_columns;

    var loop = {
      timeline: [trial],
      loop_function: function () {
        if (direction === 'back') {
          idx = Math.max(0, idx - 1);
        } else {
          idx += 1;
        }
        return idx < total;
      },
    };

    loop._resetIteration = function () {
      idx = 0;
      direction = 'forward';
      if (spec.onLoopStart) spec.onLoopStart();
    };

    return loop;
  }

  return {
    getURLParams: getURLParams,
    nowISO: nowISO,
    fallbackParticipantId: fallbackParticipantId,
    shuffle: shuffle,
    attachActivityTracker: attachActivityTracker,
    escapeHtml: escapeHtml,
    storyHeaderHTML: storyHeaderHTML,
    lastDataFromSessionIter: lastDataFromSessionIter,
    buildLoopWithBack: buildLoopWithBack,
  };
})();
