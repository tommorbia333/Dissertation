// tasks/ordering.js — chronological ordering task.
//
// Per task design §5.3 (and Phase 1 Step 1 preregistered constants):
//   - 8 event cards, presented from the fixed scrambled starting order
//     [E2, E4, E5, E8, E6, E7, E3, E1]. This order is identical across all
//     participants, stories, and conditions.
//   - Drag-to-reorder via SortableJS; per-drag events logged (dual-level).
//   - Post-task confidence slider on the same page (1–7, unset initial state).
//   - Continue disabled until slider is touched.
//
// Emits ONE row per story:
//   task: 'ordering'
//   fields: initial_order, final_order, confidence_rating, total_time_ms,
//           n_drags, events[] (drag-level detail if logging_level='detail')

var OrderingTask = (function () {

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function renderStimulusHTML(storyId, cards, scrambledOrder, header) {
    var cardItems = scrambledOrder.map(function (eid) {
      var label = cards[eid];
      return (
        '<li class="order-card" data-event-id="' + eid + '">' +
          '<span class="order-card-grip" aria-hidden="true">⋮⋮</span>' +
          '<span class="order-card-label">' + escapeHtml(label) + '</span>' +
        '</li>'
      );
    }).join('\n');

    var sMin = CONFIG.ordering.confidence_scale_min;
    var sMax = CONFIG.ordering.confidence_scale_max;
    var sMinLabel = CONFIG.ordering.confidence_scale_min_label;
    var sMaxLabel = CONFIG.ordering.confidence_scale_max_label;

    return [
      Utils.storyHeaderHTML(header || {}),
      '<div class="ordering-container">',
      '  <h3 class="ordering-heading">Arrange the events in the order you think they happened.</h3>',
      '  <p class="ordering-instruction">Drag and drop the cards so that the earliest event is at the top and the latest at the bottom.</p>',
      '  <ol class="order-list" id="order-list">',
      cardItems,
      '  </ol>',
      '  <div class="confidence-container">',
      '    <p class="confidence-prompt">How confident are you in the order you have chosen?</p>',
      '    <div class="confidence-slider-row">',
      '      <span class="slider-end-label">' + escapeHtml(sMinLabel) + '</span>',
      '      <input type="range" id="confidence-slider" class="confidence-slider" ' +
                'min="' + sMin + '" max="' + sMax + '" step="1" value="' + Math.ceil((sMin + sMax) / 2) + '" ' +
                'aria-label="Confidence rating" />',
      '      <span class="slider-end-label">' + escapeHtml(sMaxLabel) + '</span>',
      '    </div>',
      '    <p class="slider-value-display">Your rating: <span id="confidence-value">—</span></p>',
      '  </div>',
      '</div>',
    ].join('\n');
  }

  function buildTrial(opts) {
    var storyId = opts.storyId;
    var cards = EVENT_CARDS[storyId];
    if (!cards) throw new Error('No event cards for story_id=' + storyId);
    var scrambledOrder = CONFIG.ordering.scrambled_start_order.slice();
    var header = {
      storyPosition: opts.storyPosition,
      totalStories:  opts.totalStories,
      taskLabel:     'Ordering',
      stepNoun:      'Part',
      stepIndex:     0,
      stepTotal:     1,
    };

    // Closure state
    var t0 = null;
    var eventsLog = [];
    var sliderTouched = false;
    var currentSliderValue = null;
    var sortableInstance = null;

    return {
      type: jsPsychHtmlButtonResponse,
      stimulus: renderStimulusHTML(storyId, cards, scrambledOrder, header),
      choices: ['Continue'],
      button_html: function (choice) {
        return '<button id="order-continue-btn" class="jspsych-btn continue-btn" disabled="disabled">' + choice + '</button>';
      },
      data: {
        task: 'ordering',
        story_id: storyId,
        initial_order: scrambledOrder.slice(),
      },
      on_load: function () {
        t0 = performance.now();
        eventsLog.push({ t: 0, type: 'ordering_shown' });

        if (typeof Sortable === 'undefined') {
          console.error('SortableJS is not loaded. Include the Sortable library before running the ordering task.');
          return;
        }

        // ---- Initialise drag-to-reorder ----
        var listEl = document.getElementById('order-list');
        sortableInstance = Sortable.create(listEl, {
          animation: 150,
          ghostClass: 'order-card-ghost',
          chosenClass: 'order-card-chosen',
          dragClass: 'order-card-drag',
          onStart: function (evt) {
            var eid = evt.item && evt.item.dataset ? evt.item.dataset.eventId : null;
            eventsLog.push({
              t: Math.round(performance.now() - t0),
              type: 'drag_start',
              event_id: eid,
              from: evt.oldIndex,
            });
          },
          onEnd: function (evt) {
            var eid = evt.item && evt.item.dataset ? evt.item.dataset.eventId : null;
            var moved = evt.oldIndex !== evt.newIndex;
            eventsLog.push({
              t: Math.round(performance.now() - t0),
              type: moved ? 'drag_end_moved' : 'drag_end_unchanged',
              event_id: eid,
              from: evt.oldIndex,
              to: evt.newIndex,
            });
          },
        });

        // ---- Wire up confidence slider ----
        var slider = document.getElementById('confidence-slider');
        var valueDisplay = document.getElementById('confidence-value');
        var continueBtn = document.getElementById('order-continue-btn');

        function markTouched() {
          if (!sliderTouched) {
            sliderTouched = true;
            currentSliderValue = parseInt(slider.value, 10);
            valueDisplay.textContent = String(currentSliderValue);
            continueBtn.removeAttribute('disabled');
            eventsLog.push({
              t: Math.round(performance.now() - t0),
              type: 'confidence_first_touch',
              value: currentSliderValue,
            });
          }
        }

        // Pointerdown catches first interaction even if value doesn't change.
        slider.addEventListener('pointerdown', markTouched);
        // Touchstart fallback for older mobile browsers that don't emit pointerdown.
        slider.addEventListener('touchstart', markTouched, { passive: true });
        // Keyboard: arrow keys also count as interaction.
        slider.addEventListener('keydown', function (e) {
          if (['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End'].indexOf(e.key) !== -1) {
            markTouched();
          }
        });

        // input: log subsequent value changes.
        slider.addEventListener('input', function () {
          if (!sliderTouched) markTouched();
          var v = parseInt(slider.value, 10);
          if (v !== currentSliderValue) {
            currentSliderValue = v;
            valueDisplay.textContent = String(v);
            eventsLog.push({
              t: Math.round(performance.now() - t0),
              type: 'confidence_change',
              value: v,
            });
          }
        });
      },
      on_finish: function (data) {
        var tEnd = performance.now();
        eventsLog.push({ t: Math.round(tEnd - t0), type: 'continue_clicked' });

        // Read final order from the DOM.
        var listEl = document.getElementById('order-list');
        var finalOrder = listEl
          ? Array.prototype.map.call(listEl.children, function (el) {
              return el.dataset && el.dataset.eventId ? el.dataset.eventId : null;
            })
          : [];

        if (sortableInstance && typeof sortableInstance.destroy === 'function') {
          sortableInstance.destroy();
        }

        var nDragsMoved = eventsLog.filter(function (e) { return e.type === 'drag_end_moved'; }).length;
        var nDragsTotal = eventsLog.filter(function (e) {
          return e.type === 'drag_end_moved' || e.type === 'drag_end_unchanged';
        }).length;

        // Compare with canonical chronology for a quick accuracy summary
        // (not used as gate, just as descriptive metadata).
        var canonical = ['E1','E2','E3','E4','E5','E6','E7','E8'];
        var kendallTau = kendallTauDistance(finalOrder, canonical);

        var row = DataHelpers.composeTrialRow({
          trial_type: 'ordering',
          task: 'ordering',
          story_id: storyId,
          initial_order: scrambledOrder.slice(),
          final_order: finalOrder,
          confidence_rating: currentSliderValue,
          confidence_scale_min: CONFIG.ordering.confidence_scale_min,
          confidence_scale_max: CONFIG.ordering.confidence_scale_max,
          total_time_ms: Math.round(tEnd - t0),
          n_drags_total: nDragsTotal,
          n_drags_moved: nDragsMoved,
          kendall_tau_to_canonical: kendallTau,
          events: eventsLog.slice(),
        });
        Object.keys(row).forEach(function (k) { data[k] = row[k]; });
      },
    };
  }

  /** Kendall tau distance between two permutations (same length). */
  function kendallTauDistance(a, b) {
    if (!a || !b || a.length !== b.length) return null;
    var posB = {};
    for (var i = 0; i < b.length; i++) posB[b[i]] = i;
    var d = 0;
    for (var i = 0; i < a.length; i++) {
      for (var j = i + 1; j < a.length; j++) {
        if ((posB[a[i]] - posB[a[j]]) * (i - j) < 0) d += 1;
      }
    }
    return d;
  }

  return {
    buildTrial: buildTrial,
    _kendallTauDistance: kendallTauDistance,
  };
})();
