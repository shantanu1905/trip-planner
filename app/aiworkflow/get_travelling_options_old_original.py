# # ticket_search_agent.py
# import json
# import re
# from datetime import datetime, timedelta
# from typing import Dict
# from langchain_core.tools import tool
# from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain.agents import create_react_agent, AgentExecutor
# from langchain.prompts import PromptTemplate
# from app.utils.easemytrip import search_trains, get_station_code
# from dotenv import load_dotenv
# import os

# load_dotenv()
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


# # ------------------ TOOLS ------------------

# @tool
# def search_train_tickets(params: str):
#     """Search train tickets. Required: {"from_station": "City", "to_station": "City", "date": "YYYY-MM-DD"}"""
#     try:
#         data = json.loads(params)
#         from_station = data["from_station"]
#         to_station = data["to_station"]
#         date = data["date"]

#         datetime.strptime(date, "%Y-%m-%d")

#         from_code, _ = get_station_code(from_station)
#         to_code, _ = get_station_code(to_station)

#         if not from_code or not to_code:
#             return json.dumps({
#                 "available_trains_count": 0,
#                 "error": f"Invalid stations: {from_station}/{to_station}"
#             })

#         trains = search_trains(from_code, to_code, datetime.strptime(date, "%Y-%m-%d").strftime("%d/%m/%Y"))

#         return json.dumps({
#             "available_trains_count": len(trains),
#             "from_station": from_station,
#             "to_station": to_station,
#             "from_station_code": from_code,
#             "to_station_code": to_code,
#             "date": date
#         })
#     except Exception as e:
#         return json.dumps({"error": str(e), "available_trains_count": 0})


# @tool
# def search_flight_tickets(params: str):
#     """Search flights. Required: {"from_city": "City", "to_city": "City", "date": "YYYY-MM-DD"}"""
#     try:
#         data = json.loads(params)
#         return json.dumps({
#             "available_flights_count": 0,
#             "from_city": data["from_city"],
#             "to_city": data["to_city"],
#             "date": data["date"]
#         })
#     except Exception as e:
#         return json.dumps({"error": str(e), "available_flights_count": 0})


# @tool
# def search_bus_tickets(params: str):
#     """Search buses. Required: {"from_city": "City", "to_city": "City", "date": "YYYY-MM-DD"}"""
#     try:
#         data = json.loads(params)
#         return json.dumps({
#             "available_buses_count": 3,
#             "from_city": data["from_city"],
#             "to_city": data["to_city"],
#             "date": data["date"]
#         })
#     except Exception as e:
#         return json.dumps({"error": str(e), "available_buses_count": 0})


# # ------------------ MAIN FUNCTION ------------------

# def search_travel_tickets(input_json: Dict) -> Dict:
#     """
#     Generate multiple travel options between base_location and destination.

#     Args:
#         {
#             "journey_start_date": "YYYY-MM-DD",
#             "journey_end_date": "YYYY-MM-DD",
#             "base_location": "City",
#             "destination": "City"
#         }

#     Returns:
#         {
#             "travelling_options": [...]
#         }
#     """

#     llm = ChatGoogleGenerativeAI(
#         model="models/gemini-2.0-flash",
#         temperature=0.3,
#         google_api_key=GEMINI_API_KEY
#     )

#     tools = [search_train_tickets, search_flight_tickets, search_bus_tickets]

#     prompt_template = PromptTemplate(
#         input_variables=["input", "agent_scratchpad", "tools", "tool_names"],
#         template="""You are a travel planning assistant that creates comprehensive multi-route travel plans.

#     AVAILABLE TOOLS:
#     {tools}

#     TOOL NAMES: {tool_names}

#     USE THIS EXACT FORMAT:
#     Thought: [what you need to do]
#     Action: tool name (one of: search_train_tickets, search_flight_tickets, search_bus_tickets)
#     Action Input: {{"from_station": "X", "to_station": "Y", "date": "YYYY-MM-DD"}}
#     Observation: [tool result appears here]
#     ... (repeat Thought/Action/Observation as needed)
#     Thought: I now have all the information needed
#     Final Answer: [JSON only - no other text]

#     TASK:
#     {input}

#     MANDATORY: Create EXACTLY 2 routes minimum:
#     1. "Fastest Route" - prioritize speed (flights preferred)
#     2. "Cost Effective Route" - prioritize budget (trains/buses preferred)

#     STEP-BY-STEP PROCESS:
#     Step 1: Check direct routes for both modes
#     - Search flights from base_location to destination
#     - Search trains from base_location to destination
#     - Search buses if needed

#     Step 2: If NO direct trains/buses (available_count = 0):
#     - Route via Delhi as hub city
#     - Search base_location -> Delhi
#     - Search Delhi -> destination
#     - Add both as separate legs with dates (2nd leg = 1 day later)

#     Step 3: Create Final Answer with 2 complete routes

#     CRITICAL RULES:
#     ✓ For trains: use "from_station" and "to_station" in Action Input
#     ✓ For flights/buses: use "from_city" and "to_city" in Action Input
#     ✓ Use "date" parameter (YYYY-MM-DD format)
#     ✓ Keep dates between journey_start_date and journey_end_date
#     ✓ Multi-leg journeys: 2nd leg date = 1st leg date + 1 day
#     ✓ NO RUPEE SYMBOL - use "INR 3000 - INR 6000" format
#     ✓ ALWAYS include these fields in EVERY leg:
#     - approx_time
#     - approx_cost
#     - journey_date
#     - available_trains_count
#     - available_flights_count
#     - available_buses_count

#     EXAMPLES OF LEGS:

#     Single leg (direct):
#     {{
#     "from": "Nagpur",
#     "to": "Delhi",
#     "mode": "Flight",
#     "approx_time": "2 hours",
#     "approx_cost": "INR 3000 - INR 6000",
#     "journey_date": "2025-05-10",
#     "available_trains_count": 0,
#     "available_flights_count": 5,
#     "available_buses_count": 0
#     }}

#     Multi-leg (via hub):
#     [
#     {{
#         "from": "Nagpur",
#         "to": "Delhi",
#         "mode": "Train",
#         "approx_time": "16 hours",
#         "approx_cost": "INR 1000 - INR 2500",
#         "journey_date": "2025-05-10",
#         "available_trains_count": 8,
#         "available_flights_count": 0,
#         "available_buses_count": 0
#     }},
#     {{
#         "from": "Delhi",
#         "to": "Dehradun",
#         "mode": "Train",
#         "approx_time": "6 hours",
#         "approx_cost": "INR 500 - INR 1500",
#         "journey_date": "2025-05-11",
#         "available_trains_count": 12,
#         "available_flights_count": 0,
#         "available_buses_count": 0
#     }}
#     ]

#     FINAL OUTPUT (must have 2 routes):
#     {{
#     "travelling_options": [
#         {{
#         "option_name": "Fastest Route",
#         "legs": [...]
#         }},
#         {{
#         "option_name": "Cost Effective Route",
#         "legs": [...]
#         }}
#     ]
#     }}

#     Now start planning! Search for availability and create 2 complete routes.

# {agent_scratchpad}"""
#     )

#     agent = create_react_agent(
#         llm=llm,
#         tools=tools,
#         prompt=prompt_template
#     )

#     executor = AgentExecutor(
#         agent=agent,
#         tools=tools,
#         verbose=True,
#         handle_parsing_errors=True,
#         max_iterations=10,
#         early_stopping_method="force"
    
#     )

#     try:
#         response = executor.invoke({"input": json.dumps(input_json, indent=2)})
#         output_text = response.get("output", "")

#         # Try direct JSON parse first
#         try:
#             parsed = json.loads(output_text)
#             if "travelling_options" in parsed and len(parsed["travelling_options"]) >= 1:
#                 return parsed
#         except json.JSONDecodeError:
#             pass

#         # Clean up markdown code fences
#         output_text = re.sub(r'```(?:json)?\s*', '', output_text)
#         output_text = output_text.strip()

#         # Try parsing again after cleanup
#         try:
#             parsed = json.loads(output_text)
#             if "travelling_options" in parsed and len(parsed["travelling_options"]) >= 1:
#                 return parsed
#         except json.JSONDecodeError:
#             pass

#         # Extract JSON from text - look for travelling_options specifically
#         # More robust pattern that handles nested structures
#         pattern = r'\{\s*"travelling_options"\s*:\s*\[.*?\]\s*\}'
#         matches = re.findall(pattern, output_text, re.DOTALL)
        
#         if matches:
#             for match in matches:
#                 try:
#                     parsed = json.loads(match)
#                     if "travelling_options" in parsed and len(parsed["travelling_options"]) >= 1:
#                         return parsed
#                 except json.JSONDecodeError:
#                     continue

#         # Fallback: create a basic structure
#         return {
#             "travelling_options": [],
#             "error": "Could not parse agent output - agent may not have completed both routes",
#             "raw_output": output_text[:500]
#         }

#     except Exception as e:
#         return {
#             "travelling_options": [],
#             "error": f"Agent execution failed: {str(e)}"
#         }


# # if __name__ == "__main__":
# #     input_json = {
# #         "journey_start_date": "2025-11-10",
# #         "journey_end_date": "2025-11-15",
# #         "base_location": "Nagpur",
# #         "destination": "Alibaug, Maharastra"
# #     }

# #     result = search_travel_tickets(input_json)
# #     print("\n=== TRAVEL OPTIONS RESULT ===")
# #     print(json.dumps(result, indent=2))

















# easemytrip_url_builder.py
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode

"""
EaseMyTrip Flight URL Decoder & Builder

DECODED URL STRUCTURE:
Base: https://flight.easemytrip.com/FlightList/Index

PARAMETERS:
- srch: DEL-Delhi-India|BOM-Mumbai-India|18/10/2025
  Format: FROM_CODE-FROM_CITY-COUNTRY|TO_CODE-TO_CITY-COUNTRY|DATE
  
- px: 1-0-0
  Format: ADULTS-CHILDREN-INFANTS
  Example: 1-0-0 = 1 adult, 0 children, 0 infants
  
- cbn: 0
  Cabin class (0=Economy, 1=Premium Economy, 2=Business, 3=First)
  
- ar: undefined
  Airline preference (undefined = any airline)
  
- isow: true
  One-way flight (true=one-way, false=round-trip)
  
- isdm: true
  Direct/non-stop flights only (true=direct, false=with stops)
  
- lang: en-us
  Language
  
- IsDoubleSeat: false
  Book adjacent seats
  
- CCODE: IN
  Country code
  
- curr: INR
  Currency
  
- apptype: B2C
  Application type (B2C = Business to Consumer)
"""


def build_easemytrip_flight_url(
    from_code: str,
    from_city: str,
    to_code: str,
    to_city: str,
    journey_date: str,  # YYYY-MM-DD format
    adults: int = 1,
    children: int = 0,
    infants: int = 0,
    cabin_class: str = "Economy",  # Economy, Premium Economy, Business, First
    one_way: bool = True,
    direct_only: bool = False,
    country: str = "India"
) -> str:
    """
    Build dynamic EaseMyTrip flight search URL
    
    Args:
        from_code: Airport code (e.g., "DEL")
        from_city: City name (e.g., "Delhi")
        to_code: Airport code (e.g., "BOM")
        to_city: City name (e.g., "Mumbai")
        journey_date: Date in YYYY-MM-DD format
        adults: Number of adults (default: 1)
        children: Number of children (default: 0)
        infants: Number of infants (default: 0)
        cabin_class: "Economy", "Premium Economy", "Business", "First"
        one_way: True for one-way, False for round-trip
        direct_only: True for non-stop flights only
        country: Country name (default: "India")
    
    Returns:
        Complete EaseMyTrip flight search URL
    """
    
    # Convert date format: YYYY-MM-DD -> DD/MM/YYYY
    date_obj = datetime.strptime(journey_date, "%Y-%m-%d")
    formatted_date = date_obj.strftime("%d/%m/%Y")
    
    # Build search string: FROM_CODE-FROM_CITY-COUNTRY|TO_CODE-TO_CITY-COUNTRY|DATE
    srch = f"{from_code}-{from_city}-{country}|{to_code}-{to_city}-{country}|{formatted_date}"
    
    # Passenger count: ADULTS-CHILDREN-INFANTS
    px = f"{adults}-{children}-{infants}"
    
    # Cabin class mapping
    cabin_map = {
        "Economy": 0,
        "Premium Economy": 1,
        "Business": 2,
        "First": 3
    }
    cbn = cabin_map.get(cabin_class, 0)
    
    # Build query parameters
    params = {
        "srch": srch,
        "px": px,
        "cbn": cbn,
        "ar": "undefined",
        "isow": "true" if one_way else "false",
        "isdm": "true" if direct_only else "false",
        "lang": "en-us",
        "IsDoubleSeat": "false",
        "CCODE": "IN",
        "curr": "INR",
        "apptype": "B2C"
    }
    
    # Build full URL
    base_url = "https://flight.easemytrip.com/FlightList/Index"
    query_string = urlencode(params, safe='-|/')
    
    return f"{base_url}?{query_string}"


def build_easemytrip_train_url(
    from_code: str,
    from_name: str,
    to_code: str,
    to_name: str,
    journey_date: str  # YYYY-MM-DD format
) -> str:
    """
    Build EaseMyTrip train booking URL
    
    Args:
        from_code: Station code (e.g., "NDLS")
        from_name: Station name (e.g., "New Delhi")
        to_code: Station code (e.g., "BCT")
        to_name: Station name (e.g., "Mumbai Central")
        journey_date: Date in YYYY-MM-DD format
    
    Returns:
        Complete EaseMyTrip train booking URL
        
    Example:
        https://railways.easemytrip.com/TrainListInfo/NewDelhi(NDLS)-to-MumbaiCentral(BCT)/2/15-11-2025
    """
    
    # Convert date format: YYYY-MM-DD -> DD-MM-YYYY
    date_obj = datetime.strptime(journey_date, "%Y-%m-%d")
    formatted_date = date_obj.strftime("%d-%m-%Y")
    
    # Remove spaces from city names
    from_name_clean = from_name.replace(" ", "")
    to_name_clean = to_name.replace(" ", "")
    
    # Build URL: /TrainListInfo/FromCity(CODE)-to-ToCity(CODE)/2/DD-MM-YYYY
    url = f"https://railways.easemytrip.com/TrainListInfo/{from_name_clean}({from_code})-to-{to_name_clean}({to_code})/2/{formatted_date}"
    
    return url


def generate_booking_urls_from_travel_option(travel_leg: dict) -> Optional[str]:
    """
    Generate booking URL from travel option leg
    
    Args:
        travel_leg: Dictionary with travel leg information
        Example:
        {
            "from": "Delhi",
            "to": "Mumbai",
            "mode": "Flight",
            "from_code": "DEL",
            "to_code": "BOM",
            "journey_date": "2025-11-10"
        }
    
    Returns:
        Booking URL string or None
    """
    
    mode = travel_leg.get("mode", "").lower()
    
    if mode == "flight":
        return build_easemytrip_flight_url(
            from_code=travel_leg["from_code"],
            from_city=travel_leg["from"],
            to_code=travel_leg["to_code"],
            to_city=travel_leg["to"],
            journey_date=travel_leg["journey_date"]
        )
    
    elif mode == "train":
        return build_easemytrip_train_url(
            from_code=travel_leg["from_code"],
            from_name=travel_leg["from"],
            to_code=travel_leg["to_code"],
            to_name=travel_leg["to"],
            journey_date=travel_leg["journey_date"]
        )
    
    elif mode == "bus":
        # EaseMyTrip bus URL format (if available)
        # Example: https://bus.easemytrip.com/...
        return None
    
    elif mode == "ferry":
        # Ferry booking URLs (platform specific)
        return None
    
    return None


# Example usage
if __name__ == "__main__":
    
    # Example 1: Basic flight search
    url1 = build_easemytrip_flight_url(
        from_code="DEL",
        from_city="Delhi",
        to_code="BOM",
        to_city="Mumbai",
        journey_date="2025-10-18"
    )
    print("Example 1 - Basic Flight:")
    print(url1)
    print()
    
    # Example 2: Business class with multiple passengers
    url2 = build_easemytrip_flight_url(
        from_code="BLR",
        from_city="Bangalore",
        to_code="GOI",
        to_city="Goa",
        journey_date="2025-12-20",
        adults=2,
        children=1,
        cabin_class="Business",
        direct_only=True
    )
    print("Example 2 - Business Class:")
    print(url2)
    print()
    
    # Example 3: Train search
    url3 = build_easemytrip_train_url(
        from_code="NDLS",
        from_name="New Delhi",
        to_code="BCT",
        to_name="Mumbai Central",
        journey_date="2025-11-15"
    )
    print("Example 3 - Train:")
    print(url3)
    print()
    
    # Example 4: From travel option leg
    travel_leg = {
        "from": "Nagpur",
        "to": "Mumbai",
        "mode": "Flight",
        "from_code": "NAG",
        "to_code": "BOM",
        "journey_date": "2025-11-10"
    }
    url4 = generate_booking_urls_from_travel_option(travel_leg)
    print("Example 4 - From Travel Leg (Flight):")
    print(url4)
    print()
    
    # Example 5: Train travel leg
    train_leg = {
        "from": "New Delhi",
        "to": "Mumbai Central",
        "mode": "Train",
        "from_code": "NDLS",
        "to_code": "BCT",
        "journey_date": "2025-11-15"
    }
    url5 = generate_booking_urls_from_travel_option(train_leg)
    print("Example 5 - From Travel Leg (Train):")
    print(url5)