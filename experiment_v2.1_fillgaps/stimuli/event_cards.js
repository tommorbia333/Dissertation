// event_cards.js — short per-event labels for the chronological ordering task.
//
// Drafted from scratch, audited against Research Notes §5 subtle-cue rules:
//   - No causal verbs, no counterfactual framing, no retrospective signals
//   - No characterising nouns or normative adjectives
//   - No temporal markers (since the task is to infer chronology)
// Third-person, present tense, ~6-12 words each.
//
// Each story has exactly 8 entries keyed by event ID (E1..E8).

var EVENT_CARDS = {
  "hospital_incident": {
    "E1": "The hospital administrator announces reduced overnight staffing levels",
    "E2": "A contractor disables the ventilator alarm during maintenance",
    "E3": "The contractor leaves with the alarm still switched off",
    "E4": "The nurse covers a longer patient list than usual",
    "E5": "A ventilator tube partially detaches from a patient's mask",
    "E6": "The ventilator continues running and no alarm sounds",
    "E7": "The nurse finds the patient in respiratory distress",
    "E8": "The hospital convenes a formal inquest"
  },
  "care_home_incident": {
    "E1": "The manager announces reduced overnight staffing",
    "E2": "A visiting GP lowers a resident's sedative dose",
    "E3": "The medication chart is not updated",
    "E4": "The care assistant gives the dose written on the chart",
    "E5": "The resident's breathing slows while asleep",
    "E6": "The care assistant reaches the resident's room after checking larger rooms first",
    "E7": "The care assistant finds the resident unresponsive; emergency services are called",
    "E8": "The manager convenes a meeting with a regional inspector"
  },
  "community_fair": {
    "E1": "The organiser books an outdoor venue for the community fair",
    "E2": "A first-aid team is assigned to the event",
    "E3": "The first-aid team is called away to another incident",
    "E4": "A replacement first-aid team takes longer than expected to arrive",
    "E5": "The temperature rises higher than forecast",
    "E6": "The organiser opens the rest area and hands out water",
    "E7": "An elderly man becomes unresponsive in the sun",
    "E8": "The council convenes a review of the event"
  },
  "restaurant_fire": {
    "E1": "A health inspector flags the ventilation as substandard",
    "E2": "The owner calls the first available technician for repairs",
    "E3": "The technician replaces the fan but not the old ducts",
    "E4": "The sous chef notices a faint smell near the back burner",
    "E5": "The kitchen is fully booked with all burners running",
    "E6": "A cook lights the back burner and the wall ignites",
    "E7": "Smoke spreads into the dining room and the restaurant is evacuated",
    "E8": "A fire investigation examines the sequence of events"
  },
  "school_trip": {
    "E1": "The teacher chooses a mountain trail for the trip",
    "E2": "The group sets out with some students in light jackets",
    "E3": "Heavy rain arrives on the ridge",
    "E4": "A student loses footing on a wet rock and injures her ankle",
    "E5": "The group has no phone signal in the valley",
    "E6": "The teacher splits the group to send two students for help",
    "E7": "A student under the trees shows signs of hypothermia",
    "E8": "A review board examines the teacher's decisions"
  },
  "family_conflict": {
    "E1": "The father is diagnosed with early-stage dementia",
    "E2": "The narrator moves closer to home and begins managing daily care",
    "E3": "The sister confirms weekend visits on Thursdays and cancels on Saturdays",
    "E4": "The narrator and sister argue; she says he is being controlling",
    "E5": "The father's doctor recommends a medication change",
    "E6": "The narrator authorises the change without consulting the sister",
    "E7": "The sister finds out about the change and calls the narrator",
    "E8": "The siblings meet at a cafe"
  },
  "power_cut": {
    "E1": "The council defers tree maintenance along the lane",
    "E2": "A neighbour begins using a home oxygen concentrator",
    "E3": "A storm brings heavy overnight winds",
    "E4": "A branch falls across the power line",
    "E5": "The local transformer trips and the street loses power",
    "E6": "The neighbour's oxygen concentrator stops running",
    "E7": "The narrator finds the neighbour unresponsive and calls emergency services",
    "E8": "The council convenes an inquiry"
  },
  "missed_flight": {
    "E1": "A truck jackknifes on the highway to the airport",
    "E2": "The airline's check-in system goes offline for maintenance",
    "E3": "The traveller leaves home",
    "E4": "The traveller gets stuck in traffic",
    "E5": "The check-in system comes back online",
    "E6": "The traveller misses the flight",
    "E7": "The traveller calls the client",
    "E8": "The client signs with a competitor"
  }
};
