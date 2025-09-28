# Get Travel Modes 
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import SystemMessage, HumanMessage
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from typing import List
import json
import re
import os 

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


# --- Updated Pydantic Models for New JSON Format ---
class TravelMode(BaseModel):
    """Model for individual travel mode/leg"""
    from_location: str = Field(alias="from", description="Starting point with code")
    to_location: str = Field(alias="to", description="Destination point with code")
    mode: str = Field(description="Transport mode")
    approx_time: str = Field(description="Approximate travel time")
    approx_cost: str = Field(description="Approximate cost")
    Note: str = Field(description="Important travel details")

class TravelPlanNew(BaseModel):
    """Updated travel plan model with new structure"""
    trip_id: str = Field(description="Trip identifier")
    Travelling_Modes: List[TravelMode] = Field(alias="Travelling _Modes", description="List of travel modes/legs")
    total_time: str = Field(description="Total travel time")
    total_cost: str = Field(description="Total travel cost")





# --- Alternative: Simple JSON Parser Function ---
def parse_json_from_response(response_content: str) -> dict:
    """
    Extract JSON from response content that might be wrapped in markdown code blocks
    """
    # Remove markdown code blocks if present
    content = response_content.strip()
    
    # Check if content is wrapped in ```json ... ``` or ``` ... ```
    if content.startswith('```'):
        # Find the actual JSON content between code blocks
        lines = content.split('\n')
        json_lines = []
        in_json = False
        
        for line in lines:
            if line.strip().startswith('```'):
                if not in_json:
                    in_json = True
                    continue
                else:
                    break
            elif in_json:
                json_lines.append(line)
        
        content = '\n'.join(json_lines).strip()
    
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"JSON Parse Error: {e}")
        print(f"Content to parse: {content[:200]}...")
        raise ValueError(f"Could not parse JSON: {e}")


# --- Function with Updated Pydantic Output Parser ---
def get_travel_options_gemini(trip_id: str, base_location: str, destination: str, travel_mode: str):
    """
    Generates travel route JSON using LangChain + Gemini 2.5 Flash with Updated Pydantic Parser
    """
    
    # Create Pydantic output parser for new format
    parser = PydanticOutputParser(pydantic_object=TravelPlanNew)
    
    # System instructions for AI with updated format instructions
    system_message = f"""
    You are an intelligent travel route planner AI that finds optimal routes and handles unavailable connections.

    {parser.get_format_instructions()}

    CRITICAL RULES:
    1. EVERY travel mode object MUST contain ALL 6 fields: from, to, mode, approx_time, approx_cost, Note
    2. The main structure has "Travelling _Modes" (note the space after underscore) as the array field name
    3. Each mode's "from" should be the starting point, "to" should be the destination point
    4. No duplicate modes allowed
    5. Modes should connect logically (each mode's "to" becomes next mode's "from")
    6. Include location codes in parentheses (e.g., "Mumbai (BOM)")
    7. Use ₹ symbol for all costs
    8. All time durations should include "hours" or "minutes"
    9. Calculate total_time and total_cost accurately
    10. Return valid JSON only, no markdown code blocks.

    INTELLIGENT ROUTING LOGIC - MINIMIZE TRAVEL TIME:
    🎯 PRIMARY GOAL: ALWAYS MINIMIZE TOTAL TRAVEL TIME
    - Analyze ALL available transport modes and select the FASTEST combination
    - If requested mode is not the fastest, suggest the optimal mode in Note field
    - Consider door-to-door time including transfers, waiting, and local transport
    - Prioritize time over cost unless specifically requested otherwise

    ROUTING PRIORITY (Fastest First):
    1. DIRECT FLIGHT (if available) - Usually fastest for 500+ km
    2. DIRECT TRAIN (High-speed/Express) - Good for 200-800 km routes  
    3. COMBINATION routes (Flight + local transport) - For destinations without airports
    4. DIRECT BUS (Only if significantly faster than alternatives)
    5. TAXI/CAR (Only for short distances <200 km or remote areas)

    OPTIMIZATION RULES:
    - If requested transport mode is available directly, use it BUT mention faster alternatives in Notes
    - If NO DIRECT connection available for requested mode:
    a) First try to find alternate stations/airports for the same mode
    b) If still not possible, suggest the FASTEST alternative transport mode
    c) Always provide the quickest practical routing solution

    SPECIFIC SCENARIOS TO HANDLE - TIME OPTIMIZATION FOCUS:
    🚂 TRAIN Scenarios:
    - If direct train available: Use it BUT compare with flight time and mention if flight is significantly faster
    - If NO DIRECT train: Find route via major railway junction (Delhi Jn, Mumbai Central, Chennai Central)
    - If destination has no railway: Go to nearest railway station + local transport
    - If train takes >12 hours: Always suggest flight alternative with time comparison
    - If NO train service at all: Suggest fastest alternative - "No train service available. FASTEST option: Flight (X hours, ₹Y) vs Bus (Z hours, ₹W)"

    ✈️ FLIGHT Scenarios:  
    - PRIORITY MODE for long distances (500+ km) - always check flight options first
    - If direct flight available: Use it (usually fastest option)
    - If NO DIRECT flight: Check connecting flights via major hubs (Delhi, Mumbai, Bangalore) and compare total time
    - If no airport at destination: Fly to nearest airport + ground transport (often still faster than train/bus)
    - If no flight service: Compare train vs bus and recommend faster option

    🚌 BUS Scenarios:
    - Only recommend bus if it's genuinely faster or if no flight/train available  
    - If direct bus available: Use it BUT mention faster alternatives if available
    - If NO DIRECT bus: Find routes via major terminals but compare with flight/train times
    - For long distances (>8 hours): Always mention flight alternative
    - If no bus service: Suggest fastest available mode

    🚕 TAXI/CAR Scenarios:
    - Best for short distances (<200 km) or reaching remote locations
    - Always possible but mention practical limitations for very long distances
    - For 200-500 km: Compare with train/bus and mention if slower
    - For 500+ km: Always suggest flight/train with time comparison: "Long distance - Flight (X hours, ₹Y) or Train (Z hours, ₹W) would be much faster"

    TIME COMPARISON EXAMPLES IN NOTES:
    - "Train available but Flight is 15 hours faster (2h vs 17h). Flight: ₹6000"
    - "Direct bus takes 12 hours. Faster option: Flight via Delhi (5h total, ₹8000)" 
    - "This train route takes 20 hours. Consider flight: Mumbai-Goa direct (1.5h, ₹4500)"

    EXAMPLE HANDLING:
    If user wants train from "Shimla to Goa":
    - Note: Shimla has no railway station
    - Solution: Train from nearby Kalka to Goa + local transport to/from Shimla
    - OR: Suggest alternatives if not practical

    FORMAT YOUR RESPONSES WITH PRACTICAL SOLUTIONS!
    """

    # Human input with dynamic values
    human_message = f"""
    Trip ID: {trip_id}
    From: {base_location}
    To: {destination}
    Mode: {travel_mode}
    """

    # Initialize Gemini 2.5 Flash LLM
    chat_model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0,
        convert_system_message_to_human=True,
        google_api_key= GEMINI_API_KEY  # Replace with your key
    )

    # Call Gemini model
    response = chat_model.invoke([SystemMessage(content=system_message), HumanMessage(content=human_message)])
    print("Raw Response:")
    print(response.content)
    print("-" * 50)
    
    try:
        # Parse with Pydantic
        parsed_output = parser.parse(response.content)
        return parsed_output.dict(by_alias=True)
    except Exception as e:
        print(f"Pydantic parsing failed: {e}")
        # Fallback to manual JSON parsing
        return parse_json_from_response(response.content)


# --- Utility Functions for New Format ---
def validate_travel_plan_new(plan: dict) -> bool:
    """
    Validate the new travel plan format
    """
    required_fields = ["trip_id", "Travelling _Modes", "total_time", "total_cost"]
    
    # Check main structure
    for field in required_fields:
        if field not in plan:
            print(f"Missing required field: {field}")
            return False
    
    # Check travelling modes
    if not isinstance(plan["Travelling _Modes"], list):
        print("Travelling _Modes must be a list")
        return False
    
    if len(plan["Travelling _Modes"]) == 0:
        print("At least one travelling mode is required")
        return False
    
    # Check each mode
    required_mode_fields = ["from", "to", "mode", "approx_time", "approx_cost", "Note"]
    for i, mode in enumerate(plan["Travelling _Modes"]):
        for field in required_mode_fields:
            if field not in mode:
                print(f"Mode {i+1} missing required field: {field}")
                return False
    
    print("Travel plan validation passed!")
    return True


def calculate_totals_new(plan: dict) -> dict:
    """
    Calculate and verify totals for the new format
    """
    total_time_minutes = 0
    total_cost_amount = 0
    
    for mode in plan["Travelling _Modes"]:
        # Parse time
        time_str = mode["approx_time"].lower()
        hours = 0
        minutes = 0
        
        hour_match = re.search(r'(\d+)\s*hour[s]?', time_str)
        if hour_match:
            hours = int(hour_match.group(1))
        
        minute_match = re.search(r'(\d+)\s*minute[s]?', time_str)
        if minute_match:
            minutes = int(minute_match.group(1))
        
        total_time_minutes += (hours * 60) + minutes
        
        # Parse cost
        cost_str = mode["approx_cost"].replace('₹', '').replace(',', '')
        cost_match = re.search(r'(\d+)', cost_str)
        if cost_match:
            total_cost_amount += int(cost_match.group(1))
    
    # Format total time
    total_hours = total_time_minutes // 60
    remaining_minutes = total_time_minutes % 60
    
    if total_hours > 0 and remaining_minutes > 0:
        formatted_time = f"{total_hours} hours {remaining_minutes} minutes"
    elif total_hours > 0:
        formatted_time = f"{total_hours} hours"
    else:
        formatted_time = f"{remaining_minutes} minutes"
    
    return {
        "calculated_total_time": formatted_time,
        "calculated_total_cost": f"₹{total_cost_amount}",
        "total_time_minutes": total_time_minutes,
        "total_cost_amount": total_cost_amount
    }

























# # --- Enhanced Example Usage with Challenging Routes ---
# if __name__ == "__main__":
#     print("=== Testing New Format with Pydantic Output Parser ===")

#     plan1 = get_travel_options_gemini(
#         trip_id="TRIP_001",
#         base_location="Shimla",  # No direct railway
#         destination="Goa", 
#         travel_mode="train"  # Challenging scenario
#     )
#     print("Pydantic Result (New Format - Challenging Route):")
#     print(json.dumps(plan1, indent=2, ensure_ascii=False))
    
        
      