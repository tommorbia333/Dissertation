// comprehension.js — 48 comprehension items (6 per story × 8 stories).
// Items audited against Research Notes §5 subtle-cue rules.
// See final documentation for per-story structure and per-item rationale.

var COMPREHENSION_ITEMS = {
  "schema_version": "1.0",
  "response_options": ["Yes", "No", "Unsure"],
  "per_story_structure": "3 compound (2 events) + 2 single (1 event) + 1 distractor",
  "balance_target": "4 Yes / 2 No",
  "response_time_flag_threshold_seconds": 1.5,
  "stories": {
    "hospital_incident": {
      "topology": "convergent",
      "items": [
        {"id": "hosp_1", "text": "Was a new overnight staffing policy announced, and was the nurse's patient list longer than usual during her night shift?", "events": ["E1", "E4"], "correct": "Yes", "role": "compound"},
        {"id": "hosp_2", "text": "Did the contractor disable the ventilator alarm to run diagnostics?", "events": ["E2"], "correct": "Yes", "role": "single"},
        {"id": "hosp_3", "text": "Did the contractor switch the alarm back on before leaving the hospital?", "events": ["E3"], "correct": "No", "role": "negative_recall"},
        {"id": "hosp_4", "text": "Did the ventilator tube partially detach at the mask end, with no alarm sounding from the machine?", "events": ["E5", "E6"], "correct": "Yes", "role": "compound"},
        {"id": "hosp_5", "text": "Was the patient stabilised with manual ventilation, and was a formal inquest convened?", "events": ["E7", "E8"], "correct": "Yes", "role": "compound"},
        {"id": "hosp_6", "text": "Did the patient experience a heart attack?", "events": [], "correct": "No", "role": "distractor"}
      ]
    },
    "care_home_incident": {
      "topology": "convergent_replicate",
      "items": [
        {"id": "care_1", "text": "Was the manager cutting back on overnight staffing, and was the care assistant covering rooms that had previously been shared?", "events": ["E1", "E4"], "correct": "Yes", "role": "compound"},
        {"id": "care_2", "text": "Did the visiting GP lower the sedative dose for one of the residents?", "events": ["E2"], "correct": "Yes", "role": "single"},
        {"id": "care_3", "text": "Did the GP update the medication chart before leaving?", "events": ["E3"], "correct": "No", "role": "negative_recall"},
        {"id": "care_4", "text": "Did the resident's breathing slow during the night, with the care assistant reaching her room only after checking the larger rooms first?", "events": ["E5", "E6"], "correct": "Yes", "role": "compound"},
        {"id": "care_5", "text": "Was the resident stabilised at the hospital, and did the manager call a meeting with a regional inspector?", "events": ["E7", "E8"], "correct": "Yes", "role": "compound"},
        {"id": "care_6", "text": "Did a fire alarm interrupt the evening medication round?", "events": [], "correct": "No", "role": "distractor"}
      ]
    },
    "community_fair": {
      "topology": "three_thread_convergence",
      "items": [
        {"id": "fair_1", "text": "Did the council approve the venue permit in early June, and was a first-aid team assigned by the volunteer coordination office for the day of the fair?", "events": ["E1", "E2"], "correct": "Yes", "role": "compound"},
        {"id": "fair_2", "text": "Was the first-aid team called away to another incident, and did their replacement take nearly two hours to arrive?", "events": ["E3", "E4"], "correct": "Yes", "role": "compound"},
        {"id": "fair_3", "text": "Was the temperature by midday well above what had been forecast, and did the organiser open the rest area earlier than planned?", "events": ["E5", "E6"], "correct": "Yes", "role": "compound"},
        {"id": "fair_4", "text": "Was a first-aid team present on site when the organiser called an ambulance for the elderly man?", "events": ["E7"], "correct": "No", "role": "negative_recall"},
        {"id": "fair_5", "text": "Did the council convene a review of the venue booking, volunteer scheduling, and weather conditions?", "events": ["E8"], "correct": "Yes", "role": "single"},
        {"id": "fair_6", "text": "Was the fair cancelled due to rain?", "events": [], "correct": "No", "role": "distractor"}
      ]
    },
    "restaurant_fire": {
      "topology": "long_chain",
      "items": [
        {"id": "rest_1", "text": "Did a health inspector tell the owner the ventilation system was not up to standard, and did the owner call the first available technician rather than the original installer?", "events": ["E1", "E2"], "correct": "Yes", "role": "compound"},
        {"id": "rest_2", "text": "Did the technician replace the old ducts behind the walls?", "events": ["E3"], "correct": "No", "role": "negative_recall"},
        {"id": "rest_3", "text": "Did the sous chef notice a faint smell near the back burner within hours of the technician's visit?", "events": ["E4"], "correct": "Yes", "role": "single"},
        {"id": "rest_4", "text": "Was the kitchen fully booked with all six burners running when a low whump came from inside the wall after a line cook lit the back burner?", "events": ["E5", "E6"], "correct": "Yes", "role": "compound"},
        {"id": "rest_5", "text": "Did smoke spread into the dining room through the ceiling, and did a fire investigation examine the technician's work order?", "events": ["E7", "E8"], "correct": "Yes", "role": "compound"},
        {"id": "rest_6", "text": "Did the restaurant's sprinkler system activate during the fire?", "events": [], "correct": "No", "role": "distractor"}
      ]
    },
    "school_trip": {
      "topology": "fan_out",
      "items": [
        {"id": "trip_1", "text": "Did the teacher choose a mountain trail that looped through a wooded section, and did she note that several students were wearing light jackets rather than waterproofs?", "events": ["E1", "E2"], "correct": "Yes", "role": "compound"},
        {"id": "trip_2", "text": "Did the teacher decide to turn the group back at the high point?", "events": ["E3"], "correct": "No", "role": "negative_recall"},
        {"id": "trip_3", "text": "Did a student injure her ankle after losing footing on a wet rock?", "events": ["E4"], "correct": "Yes", "role": "single"},
        {"id": "trip_4", "text": "Was there no phone signal in the valley, and did the teacher send two older students back toward the car park to call for rescue?", "events": ["E5", "E6"], "correct": "Yes", "role": "compound"},
        {"id": "trip_5", "text": "Did one of the younger students show early signs of hypothermia under the trees, and did a review board examine the teacher's decisions the following week?", "events": ["E7", "E8"], "correct": "Yes", "role": "compound"},
        {"id": "trip_6", "text": "Did a member of the group suffer a concussion from the fall?", "events": [], "correct": "No", "role": "distractor"}
      ]
    },
    "family_conflict": {
      "topology": "chain_with_feedback",
      "items": [
        {"id": "fam_1", "text": "Was the narrator's father diagnosed with early-stage dementia, and did the narrator move closer to home that summer?", "events": ["E1", "E2"], "correct": "Yes", "role": "compound"},
        {"id": "fam_2", "text": "Did the sister come every weekend through the autumn?", "events": ["E3"], "correct": "No", "role": "negative_recall"},
        {"id": "fam_3", "text": "Did the sister accuse the narrator of being controlling during a phone call?", "events": ["E4"], "correct": "Yes", "role": "single"},
        {"id": "fam_4", "text": "Did the father's doctor recommend changing his medication, and did the narrator sign the form for the new prescription without calling the sister?", "events": ["E5", "E6"], "correct": "Yes", "role": "compound"},
        {"id": "fam_5", "text": "Did the sister find out about the medication change from a neighbour, and did the siblings meet at a cafe a few weeks later?", "events": ["E7", "E8"], "correct": "Yes", "role": "compound"},
        {"id": "fam_6", "text": "Did the narrator consider moving their father into a nursing home?", "events": [], "correct": "No", "role": "distractor"}
      ]
    },
    "power_cut": {
      "topology": "chain_with_distal_enabler",
      "items": [
        {"id": "pow_1", "text": "Had the council deferred tree maintenance near the power lines for over a year?", "events": ["E1"], "correct": "Yes", "role": "single"},
        {"id": "pow_2", "text": "Did the healthcare provider supply a backup battery with the oxygen concentrator?", "events": ["E2"], "correct": "No", "role": "negative_recall"},
        {"id": "pow_3", "text": "Did the forecast warn of heavy winds overnight, and did a branch come down across the power line during the storm?", "events": ["E3", "E4"], "correct": "Yes", "role": "compound"},
        {"id": "pow_4", "text": "Did the local transformer trip, and did the neighbour's oxygen machine shut down when the power went out?", "events": ["E5", "E6"], "correct": "Yes", "role": "compound"},
        {"id": "pow_5", "text": "Did the narrator find the neighbour unresponsive, and did a council inquiry examine the budget meetings where tree work had been deferred?", "events": ["E7", "E8"], "correct": "Yes", "role": "compound"},
        {"id": "pow_6", "text": "Did the power company issue an apology to the street after the outage?", "events": [], "correct": "No", "role": "distractor"}
      ]
    },
    "missed_flight": {
      "topology": "hourglass",
      "items": [
        {"id": "flt_1", "text": "Did a truck jackknife on the main highway on the morning of the traveller's flight, and had the airline's check-in system gone offline overnight for scheduled maintenance?", "events": ["E1", "E2"], "correct": "Yes", "role": "compound"},
        {"id": "flt_2", "text": "Did the traveller leave the house later than planned, and did he hit traffic about twenty minutes from the airport?", "events": ["E3", "E4"], "correct": "Yes", "role": "compound"},
        {"id": "flt_3", "text": "Did the check-in desks reopen before the window for the traveller's flight had closed?", "events": ["E5"], "correct": "No", "role": "negative_recall"},
        {"id": "flt_4", "text": "Did the traveller miss the flight and call the client from the airport?", "events": ["E6", "E7"], "correct": "Yes", "role": "compound"},
        {"id": "flt_5", "text": "Did the traveller learn the following week that the client had signed with a competitor?", "events": ["E8"], "correct": "Yes", "role": "single"},
        {"id": "flt_6", "text": "Did the traveller manage to catch a later flight that same afternoon?", "events": [], "correct": "No", "role": "distractor"}
      ]
    }
  }
};
