// synthetic_run.js — end-to-end simulated participant, data-shape verification.
//
// Simulates a full participant journey through the complete timeline and
// writes the resulting data to disk. Verifies that every emitted row
// conforms to the expected shape per DATA_SCHEMA.md.
//
// This is a DATA-SHAPE simulation, not a behavioural one. Responses are
// drawn from plausible distributions (not random) to exercise field
// semantics, but conclusions about the data PATTERN require real data.

const fs = require('fs');
const vm = require('vm');
const path = require('path');

// ============================================================
// 1. Build a browser-like sandbox with fake DOM bits
// ============================================================

function makeFakeElement(id) {
  const el = {
    id,
    _attrs: {},
    _children: [],
    _listeners: {},
    dataset: {},
    children: [],
    innerHTML: '',
    textContent: '',
    style: {},
    scrollHeight: 2000,
    clientHeight: 800,
    scrollTop: 0,
    setAttribute(k, v) { this._attrs[k] = v; if (k === 'disabled') this.disabled = v; },
    removeAttribute(k) { delete this._attrs[k]; if (k === 'disabled') delete this.disabled; },
    getAttribute(k) { return this._attrs[k]; },
    addEventListener(ev, fn) { (this._listeners[ev] = this._listeners[ev] || []).push(fn); },
    removeEventListener(ev, fn) {
      if (this._listeners[ev]) {
        this._listeners[ev] = this._listeners[ev].filter(f => f !== fn);
      }
    },
    appendChild(c) { this._children.push(c); this.children.push(c); },
  };
  return el;
}

// Fake performance.now with advancing clock
let simClockMs = 0;
function advanceClock(ms) { simClockMs += ms; }
function simPerfNow() { return simClockMs; }

function makeSandbox() {
  const elements = new Map();
  function getElement(id) {
    if (!elements.has(id)) elements.set(id, makeFakeElement(id));
    return elements.get(id);
  }
  const fakeDocument = {
    getElementById: (id) => elements.get(id) || null,
    scrollingElement: null,
    documentElement: { scrollHeight: 2000, clientHeight: 800, scrollTop: 0 },
  };
  const fakeWindow = {
    addEventListener: () => {},
    removeEventListener: () => {},
    scrollY: 0,
    innerWidth: 1440,
    innerHeight: 900,
    location: { search: '?PROLIFIC_PID=SIM_TEST_001&pIndex=0' },
  };
  fakeWindow.document = fakeDocument;
  return {
    console,
    performance: { now: simPerfNow },
    document: fakeDocument,
    window: fakeWindow,
    navigator: { userAgent: 'synthetic-test-runner/1.0' },
    setTimeout: (fn, ms) => { /* no-op; we advance the clock ourselves */ },
    clearTimeout: () => {},

    // jsPsych plugin stubs — recorded in trial.type for trial dispatch
    jsPsychHtmlButtonResponse: 'html-button-response',
    jsPsychCallFunction: 'call-function',
    jsPsychHtmlKeyboardResponse: 'html-keyboard-response',
    jsPsychSurveyHtmlForm: 'survey-html-form',
    jsPsychInstructions: 'instructions',

    // Sortable stub
    Sortable: {
      create: (el) => ({ destroy: () => {}, _el: el }),
    },

    // jsPsych stubs exposed via initJsPsych
    initJsPsych: (opts) => {
      return {
        data: {
          addProperties: (props) => { globalProps = { ...globalProps, ...props }; },
          displayData: () => {},
          get: () => ({ values: () => [] }),
        },
        abortExperiment: (html) => { simEnded = true; simEndHTML = html; },
        run: (timeline) => { simTimeline = timeline; },
      };
    },

    // Helper vars for the runner
    _makeElement: getElement,
    _elements: elements,
    _fakeWindow: fakeWindow,
    _fakeDocument: fakeDocument,
  };
}

let globalProps = {};
let simTimeline = null;
let simEnded = false;
let simEndHTML = '';

// ============================================================
// 2. Load the experiment source in order
// ============================================================

function loadExperiment(sandbox) {
  const files = [
    'src/config.js',
    'stimuli/stories.js',
    'stimuli/comprehension.js',
    'stimuli/event_cards.js',
    'stimuli/cf_probes.js',
    'stimuli/assignments.js',
    'src/utils.js',
    'src/condition.js',
    'src/selection.js',
    'src/data.js',
    'src/tasks/story_reading.js',
    'src/tasks/comprehension.js',
    'src/tasks/ordering.js',
    'src/tasks/pair_scaling.js',
    'src/tasks/counterfactual.js',
    'src/intro.js',
    'src/inter_story.js',
    'src/outro.js',
    'src/main.js',
  ];
  vm.createContext(sandbox);
  for (const f of files) {
    const code = fs.readFileSync(f, 'utf8');
    vm.runInContext(code, sandbox, { filename: f });
  }
}

// ============================================================
// 3. Simulate responses based on trial task + condition
// ============================================================

function simulateTrialResponse(trial, sandbox) {
  const task = (trial.data && trial.data.task) || trial.type;

  // Default response/rt (per-task overrides below)
  let response = 0;
  let rt = 1200;

  switch (task) {
    case 'browser_check':
    case 'welcome':
    case 'consent':
    case 'instructions':
    case 'inter_story_break':
    case 'debrief':
      response = 0; rt = 800;
      break;

    case 'demographics':
      response = { age: '32', english_l1: 'yes', education: 'bachelor' };
      rt = 4500;
      break;

    case 'attention_check':
      // Select "Orange" (correct)
      response = sandbox.CONFIG.attention_check.options.indexOf(sandbox.CONFIG.attention_check.correct_option);
      rt = 2200;
      break;

    case 'final_comments':
      response = { comments: '' };
      rt = 2000;
      break;

    case 'redirect':
      response = null;
      rt = sandbox.CONFIG.prolific.redirect_buffer_ms;
      break;

    case 'story_reading':
      response = 0; // Continue button
      rt = 75000; // 75s reading time
      break;

    case 'comprehension_item': {
      // Correct ~90% of the time, rushed 5%, otherwise plausible
      const correct = trial.data.correct_response;
      const options = sandbox.CONFIG.comprehension.response_options; // [Yes,No,Unsure]
      response = Math.random() < 0.9 ? options.indexOf(correct)
               : Math.random() < 0.5 ? (options.indexOf(correct) + 1) % 3
               : 2; // Unsure
      rt = 2500 + Math.random() * 2000;
      break;
    }

    case 'comprehension_summary':
      response = null; rt = 0;
      break;

    case 'ordering':
      // Simulated drag: arrive at near-canonical order (τ≈2-3 mistakes)
      response = 0;
      rt = 18000;
      break;

    case 'pair_scaling_item': {
      // Roughly: high rating if source index < target index (sensible chronology heuristic)
      const srcIdx = parseInt(trial.data.source_event_id.slice(1)) - 1;
      const tgtIdx = parseInt(trial.data.target_event_id.slice(1)) - 1;
      let baseRating = srcIdx < tgtIdx ? 3 : 1;
      baseRating += Math.floor(Math.random() * 3) - 1;
      response = Math.max(0, Math.min(6, baseRating));
      rt = 3500 + Math.random() * 2000;
      break;
    }

    case 'pair_scaling_summary':
      response = null; rt = 0;
      break;

    case 'counterfactual_item': {
      // Anchor: less likely (1 or 2); nulls: no change (3)
      if (trial.data.probe_role === 'anchor') response = Math.random() < 0.7 ? 0 : 1;
      else response = 2; // "No change"
      rt = 4000 + Math.random() * 2000;
      break;
    }

    case 'counterfactual_summary':
      response = null; rt = 0;
      break;

    default:
      response = 0; rt = 1000;
  }

  return { response, rt };
}

// ============================================================
// 4. Execute a single trial through its lifecycle
// ============================================================

function execTrial(trial, sandbox) {
  // Construct a fresh data object with all `data` fields merged in.
  const data = Object.assign({}, trial.data || {});
  data.trial_type = trial.type;
  data.trial_index = trialCounter++;
  data.time_elapsed = simPerfNow();

  // Ensure globalProps (from addProperties) are applied
  Object.assign(data, globalProps);

  // Fire on_load if present (some tasks set up state here)
  if (typeof trial.on_load === 'function') {
    try { trial.on_load(); } catch (e) { /* DOM issues — expected in sim */ }
  }

  // Simulate participant response
  const { response, rt } = simulateTrialResponse(trial, sandbox);
  data.response = response;
  data.rt = rt;
  advanceClock(rt);
  data.time_elapsed = simPerfNow();

  // For ordering trial, spoof the final DOM order on the #order-list
  if ((trial.data && trial.data.task) === 'ordering') {
    const listEl = sandbox._makeElement('order-list');
    // Simulate a reorder: permute scrambled to near-canonical
    // (E1,E2,E3,E4,E6,E5,E7,E8) — 1 mistake (E5/E6 swapped)
    listEl.children = ['E1','E2','E3','E4','E6','E5','E7','E8'].map(eid => {
      const el = { dataset: { eventId: eid } };
      return el;
    });
  }

  // Fire on_finish, passing the data object (it mutates data in place)
  if (typeof trial.on_finish === 'function') {
    try { trial.on_finish(data); } catch (e) {
      console.error(`on_finish failed for task=${data.task}:`, e.message);
    }
  }

  return data;
}

// ============================================================
// 5. Run one simulated participant
// ============================================================

let trialCounter = 0;

function runSyntheticParticipant(pIndex, forceCondition) {
  // Reset globals
  simClockMs = 0;
  trialCounter = 0;
  globalProps = {};
  simTimeline = null;
  simEnded = false;
  simEndHTML = '';

  const sandbox = makeSandbox();
  sandbox._fakeWindow.location.search = `?PROLIFIC_PID=SIM_TEST_${String(pIndex).padStart(3, '0')}&pIndex=${pIndex}`;

  loadExperiment(sandbox);

  // If the IIFE in main.js already ran during loading, simTimeline is populated.
  if (!simTimeline) {
    throw new Error('simTimeline not set after loading main.js');
  }

  // Optionally override condition
  const pid = `SIM_TEST_${String(pIndex).padStart(3, '0')}`;
  const cond = forceCondition || sandbox.Condition.assignCondition(pIndex, pid);
  const assignment = sandbox.Selection.assignStories(pIndex);

  const rows = [];
  for (const trial of simTimeline) {
    const data = execTrial(trial, sandbox);
    rows.push(data);
    if (simEnded) break;  // consent refusal, attention-check fail, etc.
  }

  return { pid, condition: cond, assignment_id: assignment.assignment_id, rows };
}

// ============================================================
// 6. Verify shape against DATA_SCHEMA.md
// ============================================================

function verifyParticipantRows(rows) {
  const issues = [];
  const required_universal = ['participant_id', 'condition', 'assignment_id', 'experiment_version'];
  for (const r of rows) {
    // Universal props
    for (const f of required_universal) {
      if (r[f] === undefined) issues.push(`row ${r.trial_index} (${r.task}): missing ${f}`);
    }
  }

  // Group by task
  const byTask = {};
  for (const r of rows) {
    const t = r.task || r.trial_type;
    (byTask[t] = byTask[t] || []).push(r);
  }

  // Intro presence
  for (const t of ['browser_check','welcome','consent','demographics','attention_check','instructions']) {
    if (!byTask[t] || byTask[t].length === 0) issues.push(`intro: no ${t} row`);
  }

  // Per-story blocks
  const storyReadingRows = byTask['story_reading'] || [];
  if (storyReadingRows.length !== 4) issues.push(`expected 4 story_reading rows, got ${storyReadingRows.length}`);

  const compItemRows = byTask['comprehension_item'] || [];
  if (compItemRows.length !== 24) issues.push(`expected 24 comprehension_item rows, got ${compItemRows.length}`);
  const compSumRows = byTask['comprehension_summary'] || [];
  if (compSumRows.length !== 4) issues.push(`expected 4 comprehension_summary rows, got ${compSumRows.length}`);

  const orderingRows = byTask['ordering'] || [];
  if (orderingRows.length !== 4) issues.push(`expected 4 ordering rows, got ${orderingRows.length}`);
  for (const r of orderingRows) {
    if (!Array.isArray(r.initial_order) || r.initial_order.length !== 8) issues.push(`ordering: initial_order wrong shape`);
    if (!Array.isArray(r.final_order) || r.final_order.length !== 8) issues.push(`ordering: final_order wrong shape`);
    if (JSON.stringify(r.initial_order) !== JSON.stringify(['E2','E4','E5','E8','E6','E7','E3','E1']))
      issues.push(`ordering: initial_order not preregistered`);
    if (typeof r.kendall_tau_to_canonical !== 'number') issues.push(`ordering: missing kendall_tau_to_canonical`);
  }

  const pairItemRows = byTask['pair_scaling_item'] || [];
  if (pairItemRows.length !== 4 * 56) issues.push(`expected ${4*56} pair_scaling_item rows, got ${pairItemRows.length}`);
  const pairSumRows = byTask['pair_scaling_summary'] || [];
  if (pairSumRows.length !== 4) issues.push(`expected 4 pair_scaling_summary rows, got ${pairSumRows.length}`);
  for (const r of pairSumRows) {
    if (!Array.isArray(r.directed_matrix) || r.directed_matrix.length !== 8)
      issues.push(`pair_scaling_summary: directed_matrix wrong outer shape`);
    else {
      for (let i = 0; i < 8; i++) {
        if (!Array.isArray(r.directed_matrix[i]) || r.directed_matrix[i].length !== 8) {
          issues.push(`pair_scaling_summary: matrix row ${i} wrong length`);
        } else if (r.directed_matrix[i][i] !== null) {
          issues.push(`pair_scaling_summary: diagonal [${i}][${i}] not null`);
        }
      }
    }
    // Count null cells — should be exactly 8 (diagonal only)
    const nullCount = r.directed_matrix.flat().filter(v => v === null).length;
    if (nullCount !== 8) issues.push(`pair_scaling_summary: ${nullCount} null cells (expected 8 diagonal)`);
  }

  // Counterfactual probes are NOT part of the participant-facing timeline as
  // of experiment_version 0.1.0-dev (rev. 2026-05-21). Verify their absence.
  const cfItemRows = byTask['counterfactual_item'] || [];
  if (cfItemRows.length !== 0) issues.push(`expected 0 counterfactual_item rows on the human side, got ${cfItemRows.length}`);
  const cfSumRows = byTask['counterfactual_summary'] || [];
  if (cfSumRows.length !== 0) issues.push(`expected 0 counterfactual_summary rows on the human side, got ${cfSumRows.length}`);

  // Outro presence
  for (const t of ['final_comments','debrief','redirect']) {
    if (!byTask[t] || byTask[t].length === 0) issues.push(`outro: no ${t} row`);
  }

  return issues;
}

// ============================================================
// 7. Main
// ============================================================

console.log('==================================================');
console.log('Synthetic end-to-end participant run');
console.log('==================================================');

const allParticipants = [];
// Run one participant per condition. Force conditions to exercise all branches.
// pIndex 0, 1, 2 naturally cycle through the 3 conditions given our permutation scheme;
// but we force to be safe.
const runs = [
  { pIndex: 0, forceCondition: 'linear' },
  { pIndex: 1, forceCondition: 'nonlinear' },
  { pIndex: 2, forceCondition: 'atemporal' },
];

for (const r of runs) {
  const result = runSyntheticParticipant(r.pIndex, r.forceCondition);
  const issues = verifyParticipantRows(result.rows);

  console.log(`\n--- Participant ${result.pid} (${r.forceCondition}, assignment #${result.assignment_id}) ---`);
  console.log(`  Rows emitted: ${result.rows.length}`);
  const byTask = {};
  for (const row of result.rows) {
    const t = row.task || row.trial_type;
    byTask[t] = (byTask[t] || 0) + 1;
  }
  console.log('  By task:');
  for (const t of Object.keys(byTask).sort()) {
    console.log(`    ${t.padEnd(28)} ${byTask[t]}`);
  }
  if (issues.length === 0) {
    console.log('  Shape verification: ALL PASS ✓');
  } else {
    console.log(`  Shape verification: ${issues.length} issue(s):`);
    for (const iss of issues) console.log(`    ✗ ${iss}`);
  }

  allParticipants.push({ meta: r, result, issues });
}

// Save one participant's data to disk for inspection
const outputPath = path.join(__dirname, 'synthetic_output.json');
const p0 = allParticipants[0];
fs.writeFileSync(
  outputPath,
  JSON.stringify(
    {
      meta: {
        participant_id: p0.result.pid,
        condition: p0.result.condition,
        assignment_id: p0.result.assignment_id,
        n_rows: p0.result.rows.length,
        simulation_timestamp: new Date().toISOString(),
      },
      rows: p0.result.rows,
    },
    null,
    2
  )
);
console.log(`\n✓ Full trial-by-trial data for participant 1 saved to ${outputPath}`);

// Totals
const totalRows = allParticipants.reduce((a, p) => a + p.result.rows.length, 0);
const totalIssues = allParticipants.reduce((a, p) => a + p.issues.length, 0);
console.log('\n==================================================');
console.log(`Total rows emitted:  ${totalRows}`);
console.log(`Total shape issues:  ${totalIssues}`);
console.log('==================================================');
if (totalIssues > 0) process.exit(1);
