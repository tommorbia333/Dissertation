// file://localhost:8000/
// http://localhost:8000/


// Code includes the following:
// - Get a randomized story from in-code text
// - Get the questions for the specific story
// - Comprehension check and disqualification
// - Demographics
// - Get the participant metadata
// - Get the runtime configuration from URL params
// - Feedback page


// To do:
// - Card task?
// - Make git repository for the project

function getParam(name) {
  return new URLSearchParams(window.location.search).get(name);
}

function getNumericParam(name, fallbackValue) {
  const rawValue = getParam(name);
  if (rawValue === null || rawValue.trim() === "") {
    return fallbackValue;
  }
  const value = Number(rawValue);
  return Number.isFinite(value) ? value : fallbackValue;
}

const runtimeConfig = {
  debug: getParam("debug") === "1" || window.location.hostname === "localhost" || window.location.protocol === "file:",
  completionUrl: getParam("completion_url") || "",
  disqualificationUrl: getParam("disqualify_url") || "disqualified.html",
  comprehensionMinCorrect: getNumericParam("comprehension_min_correct", 1),
  comprehensionMaxWrong: getNumericParam("comprehension_max_wrong", 2)
};

const participantMeta = {
  participant_id: getParam("participant_id") || getParam("PROLIFIC_PID") || "",
  study_id: getParam("study_id") || getParam("STUDY_ID") || "",
  session_id: getParam("session_id") || getParam("SESSION_ID") || ""
};

const temporal_scale = ["1 Definitely No", "2 Probably No", "3 Unsure", "4 Probably Yes", "5 Definitely Yes"];
const causal_scale = ["1 Not at all", "2 Slightly", "3 Moderately", "4 Strongly", "5 Very strongly"];
const counterfactual_scale = ["1 Much less likely", "2 Less likely", "3 No change/Unsure", "4 More likely", "5 Much more likely"];
const y_n_u = ["Yes", "No", "Unsure"];

// Fallback registration for Cognition deployments where external custom plugins can fail to load.
if (typeof window.jsPsychCausalPairScale === "undefined" && typeof window.jsPsychModule !== "undefined") {
  (function registerCausalPairScaleFallback(jspsych) {
    const info = {
      name: "causal-pair-scale",
      parameters: {
        instruction: {
          type: jspsych.ParameterType.HTML_STRING,
          default: "Indicate the likelihood that the event on the left causally contributed to the event on the right."
        },
        left_event: {
          type: jspsych.ParameterType.HTML_STRING,
          default: undefined
        },
        right_event: {
          type: jspsych.ParameterType.HTML_STRING,
          default: undefined
        },
        labels: {
          type: jspsych.ParameterType.STRING,
          array: true,
          default: []
        },
        required: {
          type: jspsych.ParameterType.BOOL,
          default: true
        },
        button_label: {
          type: jspsych.ParameterType.STRING,
          default: "Continue"
        }
      }
    };

    class CausalPairScalePlugin {
      constructor(jsPsych) {
        this.jsPsych = jsPsych;
      }

      trial(display_element, trial) {
        const trialStart = performance.now();
        const optionsHtml = trial.labels
          .map((label, i) => {
            return `
            <label class="causal-option">
              <input type="radio" name="causal_scale" value="${i}">
              <span>${label}</span>
            </label>
          `;
          })
          .join("");

        display_element.innerHTML = `
        <div class="causal-card">
          <h2>2) Pairwise Causal Contribution Questions</h2>
          <p class="causal-instruction">${trial.instruction}</p>
          <div class="causal-events">
            <div class="causal-event-box causal-left-event">${trial.left_event}</div>
            <div class="causal-arrow" aria-hidden="true">&rarr;</div>
            <div class="causal-event-box causal-right-event">${trial.right_event}</div>
          </div>
          <div class="causal-scale" role="group" aria-label="Causal contribution scale">
            ${optionsHtml}
          </div>
          <p id="causal-error" class="causal-error" style="display:none;">Please choose one response before continuing.</p>
          <button id="causal-next" class="jspsych-btn">${trial.button_label}</button>
        </div>
      `;

        display_element.querySelector("#causal-next").addEventListener("click", () => {
          const selected = display_element.querySelector('input[name="causal_scale"]:checked');
          if (!selected && trial.required) {
            display_element.querySelector("#causal-error").style.display = "block";
            return;
          }

          const rt = Math.round(performance.now() - trialStart);
          const responseIndex = selected ? Number(selected.value) : null;
          const trialData = {
            left_event: trial.left_event,
            right_event: trial.right_event,
            response_index: responseIndex,
            response_label: responseIndex !== null ? trial.labels[responseIndex] : null,
            rt: rt
          };

          display_element.innerHTML = "";
          this.jsPsych.finishTrial(trialData);
        });
      }
    }

    CausalPairScalePlugin.info = info;
    window.jsPsychCausalPairScale = CausalPairScalePlugin;
  })(window.jsPsychModule);
}

const medicalShortQuestions = {
  temporal: [
    { prompt: "Did the hospital administrator approving a policy to reduce overnight staffing levels occur before the maintenance contractor disabling a ventilator alarm during a routine test?", labels: temporal_scale, required: true },
    { prompt: "Did the maintenance contractor disabling a ventilator alarm during a routine test occur before the contractor leaving the room without re-enabling the alarm?", labels: temporal_scale, required: true },
    { prompt: "Did the nurse being assigned more patients than usual occur before a brief interruption in power occurring on the ward?", labels: temporal_scale, required: true },
    { prompt: "Did a brief interruption in power occurring on the ward occur before the ventilator stopping without sounding an alarm?", labels: temporal_scale, required: true },
    { prompt: "Did the ventilator stopping without sounding an alarm occur before the nurse entering the room and finding a patient experiencing respiratory distress?", labels: temporal_scale, required: true },
    { prompt: "Did the nurse entering the room and finding a patient experiencing respiratory distress occur before an inquest reviewing the sequence of events?", labels: temporal_scale, required: true },
    { prompt: "Did the contractor leaving the room without re-enabling the alarm occur before the ventilator stopping without sounding an alarm?", labels: temporal_scale, required: true },
    { prompt: "Did the maintenance contractor disabling a ventilator alarm during a routine test occur before the nurse entering the room and finding a patient experiencing respiratory distress?", labels: temporal_scale, required: true }
  ],
  causal: [
    { left_event: "The hospital administrator approved a policy to reduce overnight staffing levels.", right_event: "The nurse was assigned more patients than usual.", labels: causal_scale, required: true },
    { left_event: "The contractor left the room without re-enabling the alarm.", right_event: "The ventilator stopped without sounding an alarm.", labels: causal_scale, required: true },
    { left_event: "A brief interruption in power occurred on the ward.", right_event: "The ventilator stopped without sounding an alarm.", labels: causal_scale, required: true },
    { left_event: "The ventilator stopped without sounding an alarm.", right_event: "The nurse entered the room and found a patient experiencing respiratory distress.", labels: causal_scale, required: true },
    { left_event: "The maintenance contractor disabled a ventilator alarm during a routine test.", right_event: "The ventilator stopped without sounding an alarm.", labels: causal_scale, required: true },
    { left_event: "The nurse was assigned more patients than usual.", right_event: "The nurse entered the room and found a patient experiencing respiratory distress.", labels: causal_scale, required: true }
  ],
  counterfactual: [
    { prompt: "If the contractor leaving the room without re-enabling the alarm had not occurred, how would the likelihood of the ventilator stopping without sounding an alarm change?", labels: counterfactual_scale, required: true },
    { prompt: "If a brief interruption in power occurring on the ward had not occurred, how would the likelihood of the ventilator stopping without sounding an alarm change?", labels: counterfactual_scale, required: true },
    { prompt: "If the nurse being assigned more patients than usual had not occurred, how would the likelihood of the nurse entering the room and finding a patient experiencing respiratory distress change?", labels: counterfactual_scale, required: true },
    { prompt: "If the maintenance contractor disabling a ventilator alarm during a routine test had not occurred, how would the likelihood of the ventilator stopping without sounding an alarm change?", labels: counterfactual_scale, required: true }
  ],
  comprehension: [
    { prompt: "Was an inquest mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" },
    { prompt: "Was a power interruption mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" },
    { prompt: "Was a maintenance contractor mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" },
    { prompt: "Was a ventilator alarm mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" }
  ]
};

const medicalMediumQuestions = {
  temporal: [
    { prompt: "Did the hospital administrator approving a policy to reduce overnight staffing levels on the ward occur before the maintenance contractor disabling a ventilator alarm while performing a standard test?", labels: temporal_scale, required: true },
    { prompt: "Did the maintenance contractor disabling a ventilator alarm while performing a standard test occur before the contractor leaving without re-enabling the alarm?", labels: temporal_scale, required: true },
    { prompt: "Did the nurse being assigned more patients than usual occur before a brief interruption in power occurring on the ward?", labels: temporal_scale, required: true },
    { prompt: "Did a brief interruption in power occurring on the ward occur before the ventilator stopping operating without sounding an alarm?", labels: temporal_scale, required: true },
    { prompt: "Did the ventilator stopping operating without sounding an alarm occur before the nurse entering the room and finding a patient experiencing respiratory distress?", labels: temporal_scale, required: true },
    { prompt: "Did the nurse entering the room and finding a patient experiencing respiratory distress occur before an inquest reviewing the sequence of events?", labels: temporal_scale, required: true },
    { prompt: "Did the contractor leaving without re-enabling the alarm occur before the ventilator stopping operating without sounding an alarm?", labels: temporal_scale, required: true },
    { prompt: "Did the maintenance contractor disabling a ventilator alarm while performing a standard test occur before the nurse entering the room and finding a patient experiencing respiratory distress?", labels: temporal_scale, required: true }
  ],
  causal: [
    { left_event: "The hospital administrator approved a policy to reduce overnight staffing levels on the ward.", right_event: "The nurse was assigned more patients than usual.", labels: causal_scale, required: true },
    { left_event: "The contractor left without re-enabling the alarm.", right_event: "The ventilator stopped operating without sounding an alarm.", labels: causal_scale, required: true },
    { left_event: "A brief interruption in power occurred on the ward.", right_event: "The ventilator stopped operating without sounding an alarm.", labels: causal_scale, required: true },
    { left_event: "The ventilator stopped operating without sounding an alarm.", right_event: "The nurse entered the room and found a patient experiencing respiratory distress.", labels: causal_scale, required: true },
    { left_event: "The maintenance contractor disabled a ventilator alarm while performing a standard test.", right_event: "The ventilator stopped operating without sounding an alarm.", labels: causal_scale, required: true },
    { left_event: "The nurse was assigned more patients than usual.", right_event: "The nurse entered the room and found a patient experiencing respiratory distress.", labels: causal_scale, required: true }
  ],
  counterfactual: [
    { prompt: "If the contractor leaving without re-enabling the alarm had not occurred, how would the likelihood of the ventilator stopping operating without sounding an alarm change?", labels: counterfactual_scale, required: true },
    { prompt: "If a brief interruption in power occurring on the ward had not occurred, how would the likelihood of the ventilator stopping operating without sounding an alarm change?", labels: counterfactual_scale, required: true },
    { prompt: "If the nurse being assigned more patients than usual had not occurred, how would the likelihood of the nurse entering the room and finding a patient experiencing respiratory distress change?", labels: counterfactual_scale, required: true },
    { prompt: "If the maintenance contractor disabling a ventilator alarm while performing a standard test had not occurred, how would the likelihood of the ventilator stopping operating without sounding an alarm change?", labels: counterfactual_scale, required: true }
  ],
  comprehension: [
    { prompt: "Was an inquest mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" },
    { prompt: "Was a power interruption mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" },
    { prompt: "Was a maintenance contractor mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" },
    { prompt: "Was a ventilator alarm mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" }
  ]
};

const workplaceQuestions = {
  temporal: [
    { prompt: "Did the manager approving a plan to consolidate server resources occur before the technician updating configuration settings on a backup system?", labels: temporal_scale, required: true },
    { prompt: "Did the technician updating configuration settings on a backup system occur before the technician not restarting one of the services?", labels: temporal_scale, required: true },
    { prompt: "Did the analyst beginning to process a large dataset occur before system load increasing across the network?", labels: temporal_scale, required: true },
    { prompt: "Did system load increasing across the network occur before a critical service stopping responding?", labels: temporal_scale, required: true },
    { prompt: "Did a critical service stopping responding occur before users reporting they were unable to access shared files?", labels: temporal_scale, required: true },
    { prompt: "Did users reporting they were unable to access shared files occur before an internal review examining the incident?", labels: temporal_scale, required: true },
    { prompt: "Did the technician not restarting one of the services occur before a critical service stopping responding?", labels: temporal_scale, required: true },
    { prompt: "Did the technician updating configuration settings on a backup system occur before users reporting they were unable to access shared files?", labels: temporal_scale, required: true }
  ],
  causal: [
    { left_event: "The manager approved a plan to consolidate server resources.", right_event: "The technician updated configuration settings on a backup system.", labels: causal_scale, required: true },
    { left_event: "The technician did not restart one of the services.", right_event: "A critical service stopped responding.", labels: causal_scale, required: true },
    { left_event: "System load increased across the network.", right_event: "A critical service stopped responding.", labels: causal_scale, required: true },
    { left_event: "A critical service stopped responding.", right_event: "Users reported they were unable to access shared files.", labels: causal_scale, required: true },
    { left_event: "The analyst began processing a large dataset.", right_event: "System load increased across the network.", labels: causal_scale, required: true },
    { left_event: "The technician updated configuration settings on a backup system.", right_event: "The technician did not restart one of the services.", labels: causal_scale, required: true }
  ],
  counterfactual: [
    { prompt: "If the technician not restarting one of the services had not occurred, how would the likelihood of a critical service stopping responding change?", labels: counterfactual_scale, required: true },
    { prompt: "If the analyst beginning to process a large dataset had not occurred, how would the likelihood of system load increasing across the network change?", labels: counterfactual_scale, required: true },
    { prompt: "If system load increasing across the network had not occurred, how would the likelihood of users reporting they were unable to access shared files change?", labels: counterfactual_scale, required: true },
    { prompt: "If a critical service stopping responding had not occurred, how would the likelihood of an internal review examining the incident change?", labels: counterfactual_scale, required: true }
  ],
  comprehension: [
    { prompt: "Was an internal review mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" },
    { prompt: "Was a backup system mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" },
    { prompt: "Was a large dataset mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" },
    { prompt: "Were shared files mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" }
  ]
};

const coastalQuestions = {
  temporal: [
    { prompt: "Did the city council approving a pilot floodgate project for the coastal road occur before contractors installing temporary barriers and signage near the road?", labels: temporal_scale, required: true },
    { prompt: "Did contractors installing temporary barriers and signage near the road occur before a utilities team scheduling a routine inspection of a pump station?", labels: temporal_scale, required: true },
    { prompt: "Did a utilities team scheduling a routine inspection of a pump station occur before the inspection requiring a temporary shutdown of the pump station?", labels: temporal_scale, required: true },
    { prompt: "Did the inspection requiring a temporary shutdown of the pump station occur before a weather service issuing a coastal surge warning?", labels: temporal_scale, required: true },
    { prompt: "Did a weather service issuing a coastal surge warning occur before the floodgate being activated during the warning period?", labels: temporal_scale, required: true },
    { prompt: "Did the floodgate being activated during the warning period occur before water entering the road area and traffic being halted?", labels: temporal_scale, required: true },
    { prompt: "Did water entering the road area and traffic being halted occur before a municipal review examining the sequence of events?", labels: temporal_scale, required: true },
    { prompt: "Did contractors installing temporary barriers and signage near the road occur before water entering the road area and traffic being halted?", labels: temporal_scale, required: true }
  ],
  causal: [
    { left_event: "The city council approved a pilot floodgate project for the coastal road.", right_event: "Contractors installed temporary barriers and signage near the road.", labels: causal_scale, required: true },
    { left_event: "The inspection required a temporary shutdown of the pump station.", right_event: "The floodgate was activated during the warning period.", labels: causal_scale, required: true },
    { left_event: "A weather service issued a coastal surge warning.", right_event: "The floodgate was activated during the warning period.", labels: causal_scale, required: true },
    { left_event: "The floodgate was activated during the warning period.", right_event: "Water entered the road area and traffic was halted.", labels: causal_scale, required: true },
    { left_event: "Contractors installed temporary barriers and signage near the road.", right_event: "Water entered the road area and traffic was halted.", labels: causal_scale, required: true },
    { left_event: "Water entered the road area and traffic was halted.", right_event: "A municipal review examined the sequence of events.", labels: causal_scale, required: true }
  ],
  counterfactual: [
    { prompt: "If a weather service issuing a coastal surge warning had not occurred, how would the likelihood of the floodgate being activated during the warning period change?", labels: counterfactual_scale, required: true },
    { prompt: "If the inspection requiring a temporary shutdown of the pump station had not occurred, how would the likelihood of the floodgate being activated during the warning period change?", labels: counterfactual_scale, required: true },
    { prompt: "If the floodgate being activated during the warning period had not occurred, how would the likelihood of water entering the road area and traffic being halted change?", labels: counterfactual_scale, required: true },
    { prompt: "If contractors installing temporary barriers and signage near the road had not occurred, how would the likelihood of water entering the road area and traffic being halted change?", labels: counterfactual_scale, required: true }
  ],
  comprehension: [
    { prompt: "Was a coastal surge warning mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" },
    { prompt: "Was a pump station mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" },
    { prompt: "Were temporary barriers or signage mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" },
    { prompt: "Was a municipal review mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" }
  ]
};

const storyBank = {
  "Stories/Medical Short Linear.pdf": {
    title: "Hospital Ward Incident",
    paragraphs: [
      "Several weeks before the incident, a hospital administrator approved a policy to reduce overnight staffing levels on the ward.",
      "On a later day, a maintenance contractor disabled a ventilator alarm while performing a routine test.",
      "After completing the test, the contractor left the room without re-enabling the alarm.",
      "On the night of the incident, a nurse was assigned more patients than usual.",
      "Later that night, a brief interruption in power occurred on the ward.",
      "Following the power interruption, the ventilator stopped operating without sounding an alarm.",
      "Some time later, the nurse entered the room and found a patient experiencing respiratory distress.",
      "In the months that followed, an inquest reviewed the sequence of events."
    ],
    questions: medicalShortQuestions
  },
  "Stories/Medical Short Linear.copy.pdf": {
    title: "Hospital Ward Incident",
    paragraphs: [
      "Several weeks before the incident, a hospital administrator approved a policy to reduce overnight staffing levels on the ward.",
      "On a later day, a maintenance contractor disabled a ventilator alarm while performing a routine test.",
      "After completing the test, the contractor left the room without re-enabling the alarm.",
      "On the night of the incident, a nurse was assigned more patients than usual.",
      "Later that night, a brief interruption in power occurred on the ward.",
      "Following the power interruption, the ventilator stopped operating without sounding an alarm.",
      "Some time later, the nurse entered the room and found a patient experiencing respiratory distress.",
      "In the months that followed, an inquest reviewed the sequence of events."
    ],
    questions: medicalShortQuestions
  },
  "Stories/Medical Short NonLinear.pdf": {
    title: "Hospital Ward Incident",
    paragraphs: [
      "In the months that followed, an inquest reviewed the sequence of events.",
      "Some time earlier, the nurse entered the room and found a patient experiencing respiratory distress.",
      "Later that night, the ventilator stopped operating without sounding an alarm.",
      "Several weeks before the incident, a hospital administrator approved a policy to reduce overnight staffing levels on the ward.",
      "On the night of the incident, a nurse was assigned more patients than usual.",
      "On a later day, a maintenance contractor disabled a ventilator alarm while performing a routine test.",
      "After completing the test, the contractor left the room without re-enabling the alarm.",
      "Earlier that same night, a brief interruption in power occurred on the ward."
    ],
    questions: medicalShortQuestions
  },
  "Stories/Medical Medium Fluff.pdf": {
    title: "Hospital Ward Incident (Detailed)",
    paragraphs: [
      "Several weeks before the incident, during a routine administrative review of hospital operations, a hospital administrator approved a policy to reduce overnight staffing levels on the ward as part of a broader efficiency plan.",
      "On a later day, during scheduled equipment maintenance in one of the patient rooms, a maintenance contractor disabled a ventilator alarm while performing a standard test of the machine's functions.",
      "After completing the test and documenting the procedure, the contractor left the room without re-enabling the alarm before moving on to another task elsewhere in the building.",
      "On the night of the incident, as staff assignments were being finalized at the start of the shift, a nurse was assigned more patients than usual across several rooms on the ward.",
      "Later that night, while activity on the ward remained relatively quiet, a brief interruption in power occurred, affecting several pieces of equipment for a short period of time.",
      "Following the power interruption, the ventilator stopped operating without sounding an alarm, and the room remained otherwise undisturbed for some time.",
      "Some time later, during a scheduled round, the nurse entered the room and found a patient experiencing respiratory distress.",
      "In the months that followed, after records and logs had been collected, an inquest reviewed the sequence of events surrounding the incident."
    ],
    questions: medicalMediumQuestions
  },
  "Stories/Medical Medium Fluff NonLinear.pdf": {
    title: "Hospital Ward Incident (Detailed)",
    paragraphs: [
      "In the months that followed, after records and logs had been collected, an inq