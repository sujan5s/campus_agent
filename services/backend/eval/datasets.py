"""Labelled test sets for the agent evaluation (docs/12-AGENT-EVALUATION-RESULTS.md).

Every label follows the route definitions in `RouteDecision`
(app/agents/supervisor.py) — the same text the supervisor LLM is given:

  timetable    generate / regenerate / rebuild the weekly class timetable
  substitution plan substitutes for an approved leave (message names a leave id)
  scheduler    schedule conflicts, checks, teacher-leave status questions
  facility     booking / reserving / availability of rooms, halls, labs, grounds, events
  general      anything else (campus info, FAQs, greetings)

The sets were written by hand before either router was run against them, and
deliberately mix keyword-friendly phrasings with paraphrases that avoid the
obvious trigger words — a router that only matches keywords should not score
100%. 20 queries per class, 100 in total.
"""

ROUTING = [
    # ---- timetable (20) -------------------------------------------------
    ("Generate the timetable for this semester", "timetable"),
    ("Please regenerate the class timetable", "timetable"),
    ("Rebuild the weekly timetable from scratch", "timetable"),
    ("Create a new timetable for all sections", "timetable"),
    ("Make the timetable again with the new rules", "timetable"),
    ("Can you build the time table for CSE-7A and 7B?", "timetable"),
    ("Run the solver and produce next week's class schedule", "timetable"),
    ("Draw up a fresh weekly schedule of classes for every section", "timetable"),
    ("We added a subject — redo the timetable", "timetable"),
    ("Produce the weekly routine for semester 5", "timetable"),
    ("Re-plan the whole week's lectures for all classes", "timetable"),
    ("Generate a clash-free timetable", "timetable"),
    ("Recompute the class timetable after the rule changes", "timetable"),
    ("Timetable generate now", "timetable"),
    ("Allocate periods to all subjects and teachers for the week", "timetable"),
    ("Prepare the semester's period-wise schedule for each section", "timetable"),
    ("Regenerate timetable but keep what's already published", "timetable"),
    ("Build a new version of the timetable", "timetable"),
    ("Could you lay out the weekly lecture plan for 2A?", "timetable"),
    ("Create the class routine for CSE-5A", "timetable"),
    # ---- substitution (20) ----------------------------------------------
    ("Plan substitutions for approved leave #3", "substitution"),
    ("Arrange substitutes for leave 7", "substitution"),
    ("Substitution plan for leave #12 please", "substitution"),
    ("Dr. Anita Rao's leave #4 is approved, plan the cover", "substitution"),
    ("Find substitute teachers for leave id 9", "substitution"),
    ("Who will take the classes for leave #2? Make a substitution plan", "substitution"),
    ("Plan period exchanges for leave 15", "substitution"),
    ("Cover the lessons affected by leave #6", "substitution"),
    ("Organise replacements for the approved leave number 8", "substitution"),
    ("Leave 11 was approved, sort out the substitutions", "substitution"),
    ("Arrange cover for approved leave #21", "substitution"),
    ("Make a swap plan for leave #5 so no class is missed", "substitution"),
    ("Need substitute faculty for leave 14", "substitution"),
    ("Handle the classes of the teacher on leave #3", "substitution"),
    ("Substitute arrangement for leave #30", "substitution"),
    ("Please plan who covers Prof. Ravi Kumar's lectures, leave #6", "substitution"),
    ("Exchange periods for leave 19", "substitution"),
    ("Re-plan the substitution for leave #1", "substitution"),
    ("Assign substitutes — leave id 25 approved", "substitution"),
    ("Plan the cover for leave number 4", "substitution"),
    # ---- scheduler (20) -------------------------------------------------
    ("Check schedule conflicts for CSE-7A", "scheduler"),
    ("Are there any overlaps in the current timetable?", "scheduler"),
    ("Is any teacher double-booked this week?", "scheduler"),
    ("Show me conflicts in the schedule", "scheduler"),
    ("Is Dr. Meera Nair on leave tomorrow?", "scheduler"),
    ("Which teachers are on leave this week?", "scheduler"),
    ("Verify there are no clashes in CSE-5A's schedule", "scheduler"),
    ("What is the status of the academic schedule?", "scheduler"),
    ("Does Prof. Ravi Kumar have overlapping classes?", "scheduler"),
    ("Audit the timetable for teacher clashes", "scheduler"),
    ("List pending leave requests", "scheduler"),
    ("Check if 2A has two subjects in the same period", "scheduler"),
    ("How many teachers are absent on Friday?", "scheduler"),
    ("Is the schedule consistent with the teacher assignments?", "scheduler"),
    ("Has my leave been approved?", "scheduler"),
    ("Scan the current schedule for problems", "scheduler"),
    ("Do any sections have a conflict on Monday?", "scheduler"),
    ("Tell me the schedule status for semester 7", "scheduler"),
    ("Who is unavailable on Wednesday because of leave?", "scheduler"),
    ("Any timetable conflicts I should know about?", "scheduler"),
    # ---- facility (20) --------------------------------------------------
    ("Book Seminar Hall B for Friday 2-5pm", "facility"),
    ("Reserve the Main Auditorium on Monday morning", "facility"),
    ("Is CS Lab 1 free on Thursday afternoon?", "facility"),
    ("I need a room for 60 people tomorrow at 11", "facility"),
    ("Book the sports ground for the cricket event on Saturday", "facility"),
    ("What's the capacity of LT-302?", "facility"),
    ("Reserve LT-301 for a guest lecture", "facility"),
    ("Can I get the auditorium for the fest?", "facility"),
    ("Is the seminar hall available next Tuesday?", "facility"),
    ("Book a lab for the ML workshop", "facility"),
    ("Where can we hold a workshop for 150 students?", "facility"),
    ("Reserve a venue for the alumni meet", "facility"),
    ("Is LT-201 occupied during period 3 on Wednesday?", "facility"),
    ("Book CS Lab 2 for project demos", "facility"),
    ("Hold the Main Auditorium for convocation rehearsal", "facility"),
    ("Which halls are free this Friday?", "facility"),
    ("Schedule an event in the seminar hall on the 20th", "facility"),
    ("Can we use the ground for sports day?", "facility"),
    ("Reserve space for a hackathon this weekend", "facility"),
    ("Is there a free classroom for an extra class at 2pm?", "facility"),
    # ---- general (20) ---------------------------------------------------
    ("Hello!", "general"),
    ("What can you do?", "general"),
    ("What is the college's attendance policy?", "general"),
    ("When does the semester end?", "general"),
    ("Who is the principal of the college?", "general"),
    ("How do I reset my password?", "general"),
    ("Thanks, that was helpful", "general"),
    ("What are the library opening hours?", "general"),
    ("Tell me about the placement cell", "general"),
    ("What is the fee payment deadline?", "general"),
    ("Explain the grading system", "general"),
    ("Good morning", "general"),
    ("Where is the canteen?", "general"),
    ("What clubs can students join?", "general"),
    ("How many credits do I need to graduate?", "general"),
    ("Summarise the anti-ragging circular", "general"),
    ("Who should I contact for a bonafide certificate?", "general"),
    ("What is the minimum CGPA for honours?", "general"),
    ("Is there a hostel curfew?", "general"),
    ("Give me the exam rules for the internal assessment", "general"),
]

# Facility Agent venue resolution: query -> expected room name (None = no
# specific venue, the agent should list the registry instead).
FACILITY = [
    ("Book Seminar Hall B for Friday 2-5pm", "Seminar Hall B"),
    ("Reserve the Main Auditorium on Monday", "Main Auditorium"),
    ("Is CS Lab 1 free on Thursday?", "CS Lab 1"),
    ("Book CS Lab 2 for project demos", "CS Lab 2"),
    ("What's the capacity of LT-302?", "LT-302"),
    ("Reserve lt-301 for a guest lecture", "LT-301"),
    ("Is LT-201 occupied on Wednesday?", "LT-201"),
    ("book room 303 at 2pm", "LT-303"),
    ("Book the sports ground on Saturday", "Sports Ground"),
    ("Can I get the auditorium for the fest?", "Main Auditorium"),
    ("Is the seminar hall available next Tuesday?", "Seminar Hall B"),
    ("Book a lab for the ML workshop", "type:lab"),
    ("Hold LT-304 for a makeup class", "LT-304"),
    ("reserve the ground for sports day", "Sports Ground"),
    ("I need a hall for 150 people", "Seminar Hall B"),
    ("Book a room for the club meeting at 2pm", None),
    ("Reserve a venue for the alumni meet", None),
    ("What venues do you have?", None),
    ("Book LT 302 on Monday", "LT-302"),
    ("Is cs lab 2 free at 10?", "CS Lab 2"),
]

# Natural-language prompts for the Timetable Assistant (LLM run only). Each is
# scored on whether the model's plan validates end to end (every op ok) and on
# the op kinds it was expected to contain.
ASSISTANT_PROMPTS = [
    ("Add a classroom called LT-401 with capacity 70", {"add_room"}),
    ("No classes for CSE-5A after period 4 on Friday", {"add_rule"}),
    ("Dr. Anita Rao is not available on Wednesday mornings", {"add_rule"}),
    ("Limit every teacher to 4 periods a day", {"add_rule"}),
    ("Pin Prof. Ravi Kumar to teach CS702 for CSE-7B", {"assign_teacher"}),
    ("Add a subject CS710 Natural Language Processing for semester 7, 3 periods a week, taught by Dr. Meera Nair",
     {"add_subject"}),
    ("Add a new teacher Dr. Priya Shah who teaches CS501 and CS502", {"add_teacher"}),
    ("Create a new class CSE-3A in semester 3 with 60 students", {"add_class"}),
    ("Make Tuesday a half day for semester 7, ending after period 4", {"add_rule"}),
    ("Prefer Machine Learning Lab in the afternoon periods 5 to 7", {"add_rule"}),
    ("Add 3 subjects CS601 Web Tech, CS602 Graphics and CS603 Theory of Computation for semester 6 with 4 periods each",
     {"add_subject"}),
    ("Regenerate the timetable", {"generate_timetable"}),
    ("Nobody should teach more than 2 periods back to back", {"add_rule"}),
    ("Add a lab called CS Lab 3 with 60 seats and then regenerate the timetable",
     {"add_room", "generate_timetable"}),
    ("Remove the rule that limits 2A to 6 periods a day", {"remove_rule"}),
]

# Constraint-registry validator: (kind, scope_type, scope_value, params, should_accept).
# Invalid cases each break exactly one thing: unknown kind, disallowed scope,
# missing entity, out-of-range value, malformed day/period.
CONSTRAINTS = [
    # valid
    ("half_day", "section", "CSE-5A", {"day": "FRI", "last_period": 4}, True),
    ("half_day", "semester", "7", {"day": "WED", "last_period": 5}, True),
    ("no_same_subject_consecutive", "global", "", {"value": True}, True),
    ("max_consecutive_teaching", "semester", "5", {"value": 3}, True),
    ("subject_daily_max", "global", "", {"value": 2}, True),
    ("max_periods_per_day", "section", "CSE-7A", {"value": 6}, True),
    ("class_slot_ban", "section", "2A", {"days": ["MON"], "periods": [1]}, True),
    ("teacher_unavailable", "global", "", {"teacher": "Dr. Anita Rao", "days": ["WED"], "periods": [1, 2]}, True),
    ("teacher_max_daily", "global", "", {"teacher": "Prof. Ravi Kumar", "value": 4}, True),
    ("teacher_max_weekly", "global", "", {"teacher": "Dr. Meera Nair", "value": 18}, True),
    ("teacher_max_consecutive", "global", "", {"teacher": "Dr. Kavya Hegde", "value": 2}, True),
    ("subject_slot_ban", "global", "", {"subject": "CS701", "days": ["FRI"], "periods": [7]}, True),
    ("subject_preferred_periods", "global", "", {"subject": "CS703", "periods": [5, 6, 7]}, True),
    ("elective_fixed_slots", "semester", "7", {"band": "OE-1", "days": ["MON", "TUE", "THU"], "periods": [3]}, True),
    ("avoid_gaps", "global", "", {"weight": 5}, True),
    # invalid
    ("lunch_break", "global", "", {"value": 1}, False),                                 # unknown kind
    ("teacher_unavailable", "section", "CSE-7A", {"teacher": "Dr. Anita Rao"}, False),  # bad scope
    ("half_day", "section", "CSE-9Z", {"day": "FRI", "last_period": 4}, False),         # no such class
    ("half_day", "semester", "3", {"day": "FRI", "last_period": 4}, False),             # no such semester
    ("half_day", "section", "CSE-5A", {"day": "FUNDAY", "last_period": 4}, False),      # bad day
    ("half_day", "section", "CSE-5A", {"day": "FRI", "last_period": 42}, False),        # bad period
    ("max_consecutive_teaching", "global", "", {"value": 0}, False),                    # below min
    ("teacher_max_daily", "global", "", {"teacher": "Dr. Nobody", "value": 4}, False),  # no such teacher
    ("teacher_max_weekly", "global", "", {"teacher": "Dr. Meera Nair", "value": 99}, False),  # above max
    ("subject_slot_ban", "global", "", {"subject": "XX999", "days": ["MON"]}, False),   # no such subject
    ("subject_daily_max", "global", "", {"value": 9}, False),                           # above max
    ("elective_fixed_slots", "semester", "7", {"band": "OE-9", "days": ["MON"], "periods": [3]}, False),  # no band
    ("elective_fixed_slots", "global", "", {"band": "OE-1", "days": ["MON"], "periods": [3]}, False),     # bad scope
    ("avoid_gaps", "global", "", {"weight": 50}, False),                                # above max
    ("class_slot_ban", "global", "", {"days": ["MON"], "periods": [1]}, False),         # bad scope
]

# Timetable Assistant op compiler (deterministic half): plans as the LLM would
# emit them -> should every step validate?
ASSISTANT_PLANS = [
    ("add a room", [{"op": "add_room", "params": {"name": "LT-401", "type": "classroom", "capacity": 70}}], True),
    ("add subject", [{"op": "add_subject", "params": {"code": "CS710", "name": "NLP", "semester": 7}}], True),
    ("forward ref: subject then teacher then pin",
     [{"op": "add_subject", "params": {"code": "CS711", "name": "Robotics", "semester": 7}},
      {"op": "add_teacher", "params": {"name": "Dr. Priya Shah", "subjects": ["CS711"]}},
      {"op": "assign_teacher", "params": {"section": "CSE-7A", "subject": "CS711", "teacher": "Dr. Priya Shah"}}], True),
    ("forward ref: new class then a rule on it",
     [{"op": "add_class", "params": {"name": "CSE-3A", "semester": 3, "strength": 60}},
      {"op": "add_rule", "params": {"kind": "half_day", "scope_type": "section", "scope_value": "CSE-3A",
                                    "params": {"day": "FRI", "last_period": 4}}}], True),
    ("bulk subjects",
     [{"op": "add_subjects", "params": {"defaults": {"semester": 6, "periods_per_week": 4},
                                        "items": [{"code": "CS601", "name": "Web Tech"},
                                                  {"code": "CS602", "name": "Graphics"}]}}], True),
    ("bulk teachers with assign_to",
     [{"op": "add_subject", "params": {"code": "CS712", "name": "Quantum", "semester": 7}},
      {"op": "add_teachers", "params": {"items": [{"name": "Dr. Lee", "subjects": ["CS712"], "assign_to": "CSE-7B"}]}}], True),
    ("alias create_teacher", [{"op": "create_teacher", "params": {"name": "Prof. New Person"}}], True),
    ("unqualified pin adds qualification",
     [{"op": "assign_teacher", "params": {"section": "CSE-5A", "subject": "CS501", "teacher": "Sannidhan"}}], True),
    ("rule via add_rule", [{"op": "add_rule", "params": {"kind": "teacher_max_daily", "scope_type": "global",
                                                        "scope_value": "", "params": {"teacher": "Dr. Anita Rao", "value": 4}}}], True),
    ("regenerate", [{"op": "generate_timetable", "params": {}}], True),
    ("edit room", [{"op": "edit_room", "params": {"name": "LT-301", "capacity": 80}}], True),
    ("fields at top level", [{"op": "add_room", "name": "Hall X", "type": "seminar", "capacity": 120}], True),
    # invalid
    ("unknown op", [{"op": "teleport_teacher", "params": {"name": "Dr. Anita Rao"}}], False),
    ("pin to missing class", [{"op": "assign_teacher", "params": {"section": "CSE-9Z", "subject": "CS701", "teacher": "Dr. Anita Rao"}}], False),
    ("bad room type", [{"op": "add_room", "params": {"name": "Pool", "type": "swimming", "capacity": 30}}], False),
    ("duplicate subject code", [{"op": "add_subject", "params": {"code": "CS701", "name": "AI again", "semester": 7}}], False),
    ("edit missing room", [{"op": "edit_room", "params": {"name": "LT-999", "capacity": 50}}], False),
    ("rule on missing class", [{"op": "add_rule", "params": {"kind": "half_day", "scope_type": "section",
                                                            "scope_value": "CSE-9Z", "params": {"day": "FRI", "last_period": 4}}}], False),
    ("remove missing teacher", [{"op": "remove_teacher", "params": {"name": "Dr. Ghost"}}], False),
    ("rule with bad period", [{"op": "add_rule", "params": {"kind": "half_day", "scope_type": "global",
                                                           "scope_value": "", "params": {"day": "FRI", "last_period": 99}}}], False),
]
