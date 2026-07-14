// cf_probes.js — 64 counterfactual probes (8 per story × 8 stories).
// Each story: 6 anchor (E1..E6 → E7) + 1 sibling null + 1 reverse null (E8 → E7).
// Audited against Research Notes §5 for subtle-cue neutrality.
// Sibling null pairs: see Table 7.1 (with care_home and community_fair replacing obsolete server_outage / coastal_flooding entries).

var CF_PROBES = {
  "schema_version": "1.0",
  "n_probes_per_story": 8,
  "stories": {
    "hospital_incident": {
      "probes": [
        {
          "probe_id": "hospital_incident_anchor_E1",
          "role": "anchor",
          "antecedent_event_id": "E1",
          "consequent_event_id": "E7",
          "prompt": "If the hospital administrator had not announced reduced overnight staffing, would the patient still have ended up in respiratory distress?"
        },
        {
          "probe_id": "hospital_incident_anchor_E2",
          "role": "anchor",
          "antecedent_event_id": "E2",
          "consequent_event_id": "E7",
          "prompt": "If the contractor had not disabled the ventilator alarm during maintenance, would the patient still have ended up in respiratory distress?"
        },
        {
          "probe_id": "hospital_incident_anchor_E3",
          "role": "anchor",
          "antecedent_event_id": "E3",
          "consequent_event_id": "E7",
          "prompt": "If the contractor had switched the alarm back on before leaving, would the patient still have ended up in respiratory distress?"
        },
        {
          "probe_id": "hospital_incident_anchor_E4",
          "role": "anchor",
          "antecedent_event_id": "E4",
          "consequent_event_id": "E7",
          "prompt": "If the nurse had not been assigned a longer patient list than usual, would the patient still have ended up in respiratory distress?"
        },
        {
          "probe_id": "hospital_incident_anchor_E5",
          "role": "anchor",
          "antecedent_event_id": "E5",
          "consequent_event_id": "E7",
          "prompt": "If the ventilator tube had not partially detached from the patient's mask, would the patient still have ended up in respiratory distress?"
        },
        {
          "probe_id": "hospital_incident_anchor_E6",
          "role": "anchor",
          "antecedent_event_id": "E6",
          "consequent_event_id": "E7",
          "prompt": "If an alarm had sounded when the ventilator stopped delivering air, would the patient still have ended up in respiratory distress?"
        },
        {
          "probe_id": "hospital_incident_sibling_null",
          "role": "sibling_null",
          "antecedent_event_id": "E1",
          "consequent_event_id": "E2",
          "prompt": "If the hospital administrator had not announced reduced overnight staffing, would the contractor still have disabled the ventilator alarm during maintenance?"
        },
        {
          "probe_id": "hospital_incident_reverse_null",
          "role": "reverse_null",
          "antecedent_event_id": "E8",
          "consequent_event_id": "E7",
          "prompt": "If the hospital had not convened a formal inquest, would the patient still have ended up in respiratory distress?"
        }
      ]
    },
    "care_home_incident": {
      "probes": [
        {
          "probe_id": "care_home_incident_anchor_E1",
          "role": "anchor",
          "antecedent_event_id": "E1",
          "consequent_event_id": "E7",
          "prompt": "If the manager had not announced reduced overnight staffing, would the care assistant still have found the resident unresponsive?"
        },
        {
          "probe_id": "care_home_incident_anchor_E2",
          "role": "anchor",
          "antecedent_event_id": "E2",
          "consequent_event_id": "E7",
          "prompt": "If the visiting GP had not lowered the resident's sedative dose, would the care assistant still have found the resident unresponsive?"
        },
        {
          "probe_id": "care_home_incident_anchor_E3",
          "role": "anchor",
          "antecedent_event_id": "E3",
          "consequent_event_id": "E7",
          "prompt": "If the medication chart had been updated, would the care assistant still have found the resident unresponsive?"
        },
        {
          "probe_id": "care_home_incident_anchor_E4",
          "role": "anchor",
          "antecedent_event_id": "E4",
          "consequent_event_id": "E7",
          "prompt": "If the care assistant had given a different dose than the one written on the chart, would the care assistant still have found the resident unresponsive?"
        },
        {
          "probe_id": "care_home_incident_anchor_E5",
          "role": "anchor",
          "antecedent_event_id": "E5",
          "consequent_event_id": "E7",
          "prompt": "If the resident's breathing had not slowed during the night, would the care assistant still have found the resident unresponsive?"
        },
        {
          "probe_id": "care_home_incident_anchor_E6",
          "role": "anchor",
          "antecedent_event_id": "E6",
          "consequent_event_id": "E7",
          "prompt": "If the care assistant had reached the resident's room before checking the larger rooms, would the care assistant still have found the resident unresponsive?"
        },
        {
          "probe_id": "care_home_incident_sibling_null",
          "role": "sibling_null",
          "antecedent_event_id": "E1",
          "consequent_event_id": "E2",
          "prompt": "If the manager had not announced reduced overnight staffing, would the visiting GP still have lowered the resident's sedative dose?"
        },
        {
          "probe_id": "care_home_incident_reverse_null",
          "role": "reverse_null",
          "antecedent_event_id": "E8",
          "consequent_event_id": "E7",
          "prompt": "If the manager had not convened a meeting with a regional inspector, would the care assistant still have found the resident unresponsive?"
        }
      ]
    },
    "community_fair": {
      "probes": [
        {
          "probe_id": "community_fair_anchor_E1",
          "role": "anchor",
          "antecedent_event_id": "E1",
          "consequent_event_id": "E7",
          "prompt": "If the organiser had not booked an outdoor venue for the fair, would the elderly man still have become unresponsive in the sun?"
        },
        {
          "probe_id": "community_fair_anchor_E2",
          "role": "anchor",
          "antecedent_event_id": "E2",
          "consequent_event_id": "E7",
          "prompt": "If a first-aid team had not been assigned to the event, would the elderly man still have become unresponsive in the sun?"
        },
        {
          "probe_id": "community_fair_anchor_E3",
          "role": "anchor",
          "antecedent_event_id": "E3",
          "consequent_event_id": "E7",
          "prompt": "If the first-aid team had not been called away to another incident, would the elderly man still have become unresponsive in the sun?"
        },
        {
          "probe_id": "community_fair_anchor_E4",
          "role": "anchor",
          "antecedent_event_id": "E4",
          "consequent_event_id": "E7",
          "prompt": "If a replacement first-aid team had arrived within a few minutes, would the elderly man still have become unresponsive in the sun?"
        },
        {
          "probe_id": "community_fair_anchor_E5",
          "role": "anchor",
          "antecedent_event_id": "E5",
          "consequent_event_id": "E7",
          "prompt": "If the temperature by midday had not been higher than forecast, would the elderly man still have become unresponsive in the sun?"
        },
        {
          "probe_id": "community_fair_anchor_E6",
          "role": "anchor",
          "antecedent_event_id": "E6",
          "consequent_event_id": "E7",
          "prompt": "If the organiser had not opened the rest area and handed out water, would the elderly man still have become unresponsive in the sun?"
        },
        {
          "probe_id": "community_fair_sibling_null",
          "role": "sibling_null",
          "antecedent_event_id": "E2",
          "consequent_event_id": "E5",
          "prompt": "If a first-aid team had not been assigned to the event, would the temperature by midday still have been higher than forecast?"
        },
        {
          "probe_id": "community_fair_reverse_null",
          "role": "reverse_null",
          "antecedent_event_id": "E8",
          "consequent_event_id": "E7",
          "prompt": "If the council had not convened a review of the event, would the elderly man still have become unresponsive in the sun?"
        }
      ]
    },
    "restaurant_fire": {
      "probes": [
        {
          "probe_id": "restaurant_fire_anchor_E1",
          "role": "anchor",
          "antecedent_event_id": "E1",
          "consequent_event_id": "E7",
          "prompt": "If the health inspector had not flagged the ventilation as substandard, would smoke still have spread into the dining room and the restaurant been evacuated?"
        },
        {
          "probe_id": "restaurant_fire_anchor_E2",
          "role": "anchor",
          "antecedent_event_id": "E2",
          "consequent_event_id": "E7",
          "prompt": "If the owner had called the original installer rather than the first available technician, would smoke still have spread into the dining room and the restaurant been evacuated?"
        },
        {
          "probe_id": "restaurant_fire_anchor_E3",
          "role": "anchor",
          "antecedent_event_id": "E3",
          "consequent_event_id": "E7",
          "prompt": "If the technician had replaced the old ducts along with the fan, would smoke still have spread into the dining room and the restaurant been evacuated?"
        },
        {
          "probe_id": "restaurant_fire_anchor_E4",
          "role": "anchor",
          "antecedent_event_id": "E4",
          "consequent_event_id": "E7",
          "prompt": "If the sous chef had not noticed a faint smell near the back burner, would smoke still have spread into the dining room and the restaurant been evacuated?"
        },
        {
          "probe_id": "restaurant_fire_anchor_E5",
          "role": "anchor",
          "antecedent_event_id": "E5",
          "consequent_event_id": "E7",
          "prompt": "If the kitchen had not been fully booked with all burners running, would smoke still have spread into the dining room and the restaurant been evacuated?"
        },
        {
          "probe_id": "restaurant_fire_anchor_E6",
          "role": "anchor",
          "antecedent_event_id": "E6",
          "consequent_event_id": "E7",
          "prompt": "If the wall had not ignited when a cook lit the back burner, would smoke still have spread into the dining room and the restaurant been evacuated?"
        },
        {
          "probe_id": "restaurant_fire_sibling_null",
          "role": "sibling_null",
          "antecedent_event_id": "E3",
          "consequent_event_id": "E5",
          "prompt": "If the technician had replaced the old ducts along with the fan, would the kitchen still have been fully booked with all burners running?"
        },
        {
          "probe_id": "restaurant_fire_reverse_null",
          "role": "reverse_null",
          "antecedent_event_id": "E8",
          "consequent_event_id": "E7",
          "prompt": "If a fire investigation had not examined the sequence of events, would smoke still have spread into the dining room and the restaurant been evacuated?"
        }
      ]
    },
    "school_trip": {
      "probes": [
        {
          "probe_id": "school_trip_anchor_E1",
          "role": "anchor",
          "antecedent_event_id": "E1",
          "consequent_event_id": "E7",
          "prompt": "If the teacher had not chosen a mountain trail for the trip, would a student still have shown signs of hypothermia under the trees?"
        },
        {
          "probe_id": "school_trip_anchor_E2",
          "role": "anchor",
          "antecedent_event_id": "E2",
          "consequent_event_id": "E7",
          "prompt": "If the group had set out with full wet-weather gear for every student, would a student still have shown signs of hypothermia under the trees?"
        },
        {
          "probe_id": "school_trip_anchor_E3",
          "role": "anchor",
          "antecedent_event_id": "E3",
          "consequent_event_id": "E7",
          "prompt": "If heavy rain had not arrived on the ridge, would a student still have shown signs of hypothermia under the trees?"
        },
        {
          "probe_id": "school_trip_anchor_E4",
          "role": "anchor",
          "antecedent_event_id": "E4",
          "consequent_event_id": "E7",
          "prompt": "If the student had not lost footing on a wet rock and injured her ankle, would a student still have shown signs of hypothermia under the trees?"
        },
        {
          "probe_id": "school_trip_anchor_E5",
          "role": "anchor",
          "antecedent_event_id": "E5",
          "consequent_event_id": "E7",
          "prompt": "If the group had kept a phone signal in the valley, would a student still have shown signs of hypothermia under the trees?"
        },
        {
          "probe_id": "school_trip_anchor_E6",
          "role": "anchor",
          "antecedent_event_id": "E6",
          "consequent_event_id": "E7",
          "prompt": "If the teacher had not split the group to send two students for help, would a student still have shown signs of hypothermia under the trees?"
        },
        {
          "probe_id": "school_trip_sibling_null",
          "role": "sibling_null",
          "antecedent_event_id": "E2",
          "consequent_event_id": "E3",
          "prompt": "If the group had set out with full wet-weather gear for every student, would heavy rain still have arrived on the ridge?"
        },
        {
          "probe_id": "school_trip_reverse_null",
          "role": "reverse_null",
          "antecedent_event_id": "E8",
          "consequent_event_id": "E7",
          "prompt": "If a review board had not examined the teacher's decisions, would a student still have shown signs of hypothermia under the trees?"
        }
      ]
    },
    "family_conflict": {
      "probes": [
        {
          "probe_id": "family_conflict_anchor_E1",
          "role": "anchor",
          "antecedent_event_id": "E1",
          "consequent_event_id": "E7",
          "prompt": "If the narrator's father had not been diagnosed with early-stage dementia, would the sister still have found out from a neighbour and called the narrator?"
        },
        {
          "probe_id": "family_conflict_anchor_E2",
          "role": "anchor",
          "antecedent_event_id": "E2",
          "consequent_event_id": "E7",
          "prompt": "If the narrator had not moved closer to home to manage daily care, would the sister still have found out from a neighbour and called the narrator?"
        },
        {
          "probe_id": "family_conflict_anchor_E3",
          "role": "anchor",
          "antecedent_event_id": "E3",
          "consequent_event_id": "E7",
          "prompt": "If the sister had kept her weekend visits as arranged, would the sister still have found out from a neighbour and called the narrator?"
        },
        {
          "probe_id": "family_conflict_anchor_E4",
          "role": "anchor",
          "antecedent_event_id": "E4",
          "consequent_event_id": "E7",
          "prompt": "If the narrator and sister had not argued on the phone, would the sister still have found out from a neighbour and called the narrator?"
        },
        {
          "probe_id": "family_conflict_anchor_E5",
          "role": "anchor",
          "antecedent_event_id": "E5",
          "consequent_event_id": "E7",
          "prompt": "If the father's doctor had not recommended a medication change, would the sister still have found out from a neighbour and called the narrator?"
        },
        {
          "probe_id": "family_conflict_anchor_E6",
          "role": "anchor",
          "antecedent_event_id": "E6",
          "consequent_event_id": "E7",
          "prompt": "If the narrator had consulted the sister before authorising the change, would the sister still have found out from a neighbour and called the narrator?"
        },
        {
          "probe_id": "family_conflict_sibling_null",
          "role": "sibling_null",
          "antecedent_event_id": "E1",
          "consequent_event_id": "E3",
          "prompt": "If the narrator's father had not been diagnosed with early-stage dementia, would the sister still have cancelled her weekend visits?"
        },
        {
          "probe_id": "family_conflict_reverse_null",
          "role": "reverse_null",
          "antecedent_event_id": "E8",
          "consequent_event_id": "E7",
          "prompt": "If the siblings had not met weeks later at a cafe, would the sister still have found out from a neighbour and called the narrator?"
        }
      ]
    },
    "power_cut": {
      "probes": [
        {
          "probe_id": "power_cut_anchor_E1",
          "role": "anchor",
          "antecedent_event_id": "E1",
          "consequent_event_id": "E7",
          "prompt": "If the council had kept up tree maintenance along the lane, would the narrator still have found the neighbour unresponsive?"
        },
        {
          "probe_id": "power_cut_anchor_E2",
          "role": "anchor",
          "antecedent_event_id": "E2",
          "consequent_event_id": "E7",
          "prompt": "If the neighbour had not begun using a home oxygen concentrator, would the narrator still have found the neighbour unresponsive?"
        },
        {
          "probe_id": "power_cut_anchor_E3",
          "role": "anchor",
          "antecedent_event_id": "E3",
          "consequent_event_id": "E7",
          "prompt": "If an autumn storm had not brought heavy overnight winds, would the narrator still have found the neighbour unresponsive?"
        },
        {
          "probe_id": "power_cut_anchor_E4",
          "role": "anchor",
          "antecedent_event_id": "E4",
          "consequent_event_id": "E7",
          "prompt": "If no branch had fallen across the power line, would the narrator still have found the neighbour unresponsive?"
        },
        {
          "probe_id": "power_cut_anchor_E5",
          "role": "anchor",
          "antecedent_event_id": "E5",
          "consequent_event_id": "E7",
          "prompt": "If the local transformer had not tripped, would the narrator still have found the neighbour unresponsive?"
        },
        {
          "probe_id": "power_cut_anchor_E6",
          "role": "anchor",
          "antecedent_event_id": "E6",
          "consequent_event_id": "E7",
          "prompt": "If the neighbour's oxygen concentrator had kept running through the outage, would the narrator still have found the neighbour unresponsive?"
        },
        {
          "probe_id": "power_cut_sibling_null",
          "role": "sibling_null",
          "antecedent_event_id": "E2",
          "consequent_event_id": "E3",
          "prompt": "If the neighbour had not begun using a home oxygen concentrator, would an autumn storm still have brought heavy overnight winds?"
        },
        {
          "probe_id": "power_cut_reverse_null",
          "role": "reverse_null",
          "antecedent_event_id": "E8",
          "consequent_event_id": "E7",
          "prompt": "If the council had not convened an inquiry, would the narrator still have found the neighbour unresponsive?"
        }
      ]
    },
    "missed_flight": {
      "probes": [
        {
          "probe_id": "missed_flight_anchor_E1",
          "role": "anchor",
          "antecedent_event_id": "E1",
          "consequent_event_id": "E7",
          "prompt": "If a truck had not jackknifed on the highway to the airport, would the traveller still have called the client from the airport to explain?"
        },
        {
          "probe_id": "missed_flight_anchor_E2",
          "role": "anchor",
          "antecedent_event_id": "E2",
          "consequent_event_id": "E7",
          "prompt": "If the airline's check-in system had not gone offline for maintenance, would the traveller still have called the client from the airport to explain?"
        },
        {
          "probe_id": "missed_flight_anchor_E3",
          "role": "anchor",
          "antecedent_event_id": "E3",
          "consequent_event_id": "E7",
          "prompt": "If the traveller had left home earlier than planned, would the traveller still have called the client from the airport to explain?"
        },
        {
          "probe_id": "missed_flight_anchor_E4",
          "role": "anchor",
          "antecedent_event_id": "E4",
          "consequent_event_id": "E7",
          "prompt": "If the traveller had not been stuck in traffic near the airport, would the traveller still have called the client from the airport to explain?"
        },
        {
          "probe_id": "missed_flight_anchor_E5",
          "role": "anchor",
          "antecedent_event_id": "E5",
          "consequent_event_id": "E7",
          "prompt": "If the check-in system had come back online before the flight window closed, would the traveller still have called the client from the airport to explain?"
        },
        {
          "probe_id": "missed_flight_anchor_E6",
          "role": "anchor",
          "antecedent_event_id": "E6",
          "consequent_event_id": "E7",
          "prompt": "If the traveller had not missed the flight, would the traveller still have called the client from the airport to explain?"
        },
        {
          "probe_id": "missed_flight_sibling_null",
          "role": "sibling_null",
          "antecedent_event_id": "E1",
          "consequent_event_id": "E2",
          "prompt": "If a truck had not jackknifed on the highway to the airport, would the airline's check-in system still have gone offline for maintenance?"
        },
        {
          "probe_id": "missed_flight_reverse_null",
          "role": "reverse_null",
          "antecedent_event_id": "E8",
          "consequent_event_id": "E7",
          "prompt": "If the client had not signed with a competitor the following week, would the traveller still have called the client from the airport to explain?"
        }
      ]
    }
  }
};
