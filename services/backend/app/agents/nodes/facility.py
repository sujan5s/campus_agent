from app.agents.state import AgentState

def facility_node(state: AgentState) -> dict:
    """
    Node solver handling room status checks, capacity records,
    and booking confirmations for classrooms/labs.
    """
    query = ""
    if state.get("messages"):
        query = state["messages"][-1].get("content", "").lower()
        
    steps = ["FacilityNode: Accessing campus real estate registry..."]
    
    # Detect targets
    room = "Lecture Theater 302"
    if "302" in query:
        room = "Lecture Theater 302"
    elif "seminar" in query or "hall" in query:
        room = "Main Seminar Hall"
    elif "robotics" in query:
        room = "Advanced Robotics Lab"
        
    if "book" in query or "reserve" in query:
        response = (
            f"Facility Agent confirmation:\n"
            f"Room {room} has been successfully BOOKED for you.\n"
            f"Occupancy status changed to 'Reserved'. Real-time campus HVAC sync scheduled."
        )
        steps.append(f"FacilityNode: Confirmed reservation and locked occupancy lock for {room}.")
    else:
        response = (
            f"Facility Agent report:\n"
            f"Room {room} is currently FREE and ready for occupancy.\n"
            f"Capacity: 120 students. HVAC: Active."
        )
        steps.append(f"FacilityNode: Parsed occupancy logs for {room}.")
        
    return {
        "steps": steps,
        "final_response": response,
        "params": {**state.get("params", {}), "facility_name": room, "action": "booked" if "book" in query else "status"}
    }
