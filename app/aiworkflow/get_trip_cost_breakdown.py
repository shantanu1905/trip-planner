# ==================== STANDARD LIBRARIES ====================
from typing import List, Dict, Any
import json
import os
import re

# ==================== SQLALCHEMY / DATABASE ====================
from sqlalchemy.orm import Session
from app.database.database import SessionLocal
from app.database.models import UserPreferences, TravelOptions, Trip, HotelPreferences , Itinerary, ItineraryPlace

# ==================== UTILITY MODULES ====================
from app.utils.hotel_utils import calculate_average_hotel_price
from app.utils.trains_utils import search_trains, get_average_class_fares
from app.utils.bus_utils import search_buses, get_fare_analysis

# ==================== AI / LANGCHAIN ====================
import google.generativeai as genai
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_react_agent, AgentExecutor
from langchain import hub

# ==================== TOOL 1: Fetch User Preferences ====================


#UPDATES PENDING ADD LOGIC TO HANDLE FLIGHT LEG FARES SIMILAR TO TRAIN AND BUS. 


from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")




@tool
def get_user_preferences(user_id: str) -> Dict[str, Any]:
    """
    Fetch user preferences for budget tracking and travel planning.
    
    Args:
        user_id: The ID of the user whose preferences to fetch (as string)
    
    Returns:
        Dictionary containing user preferences including budget, food, activities, 
        travel class preferences, transport mode preferences, and number of travelers
    """
    from app.database.database import SessionLocal
    from app.database.models import UserPreferences, Trip
    import json

    # Convert user_id to int if needed
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        try:
            parsed = json.loads(user_id)
            user_id = int(parsed.get("user_id", user_id))
        except:
            return {"error": f"Invalid user_id format: {user_id}"}

    db = SessionLocal()
    try:
        # Fetch user preferences
        prefs = db.query(UserPreferences).filter(
            UserPreferences.user_id == user_id
        ).first()

        if not prefs:
            return {"error": f"No preferences found for user_id: {user_id}"}

        # Fetch latest trip to get num_people
        trip = db.query(Trip).filter(Trip.user_id == user_id).order_by(Trip.created_at.desc()).first()
        num_people = trip.num_people if trip else None

        result = {
            "user_id": user_id,
            "no_of_travelers": num_people,
            "default_budget": prefs.default_budget,
            "food_preference": prefs.food_preference.value if prefs.food_preference else None,
            "activities": prefs.activities if prefs.activities else [],
            "travelling_with": prefs.travelling_with.value if prefs.travelling_with else None,
            
            # Train preferences
            "preferred_train_class": prefs.preferred_train_class.value if prefs.preferred_train_class else None,
            
            # Bus preferences
            "bus_preferences": {
                "sleeper": prefs.bus_sleeper,
                "ac": prefs.bus_ac,
                "seater": prefs.bus_seater,
                "st_status": prefs.bus_ststatus
            },
            
            # Flight preferences
            "preferred_flight_class": prefs.preferred_flight_class.value if prefs.preferred_flight_class else None
        }

        return result

    except Exception as e:
        return {"error": f"Error fetching user preferences: {str(e)}"}
    finally:
        db.close()


# ==================== TOOL 2: Fetch Travel Legs Fares ====================

@tool
def get_leg_fares(trip_id: str) -> List[Dict[str, Any]]:
    """
    For a trip, fetch all itinerary legs (train, bus, flight) and calculate average fares per class.

    Args:
        trip_id: Trip ID as string

    Returns:
        List of dicts, one per leg, with average fares and leg info.
    """
    from app.database.database import SessionLocal
    from app.database.models import TravelOptions
    import json
    from datetime import datetime

    db = SessionLocal()
    try:
        # Convert trip_id to int
        try:
            trip_id_int = int(trip_id)
        except (ValueError, TypeError):
            parsed = json.loads(trip_id)
            trip_id_int = int(parsed.get("trip_id", trip_id))

        travel_opts = db.query(TravelOptions).filter(
            TravelOptions.trip_id == trip_id_int
        ).first()

        if not travel_opts:
            return [{"error": f"No travel options found for trip_id: {trip_id}"}]

        legs = travel_opts.selected_travel_options.get("legs", [])
        if not legs:
            return [{"error": "No itinerary legs found"}]

        result_list = []

        for leg in legs:
            mode = leg.get("mode", "").lower()
            from_city = leg.get("from")
            to_city = leg.get("to") 
            journey_date = leg.get("journey_date")
            from_station = leg.get("from_code") or leg.get("from")
            to_station = leg.get("to_code") or leg.get("to")
            journey_date = leg.get("journey_date")

            # Convert YYYY-MM-DD to DD/MM/YYYY if needed
            formatted_date_bus = datetime.strptime(journey_date, "%Y-%m-%d").strftime("%d-%m-%Y")
            if "-" in journey_date:
                try:
                    journey_date = datetime.strptime(journey_date, "%Y-%m-%d").strftime("%d/%m/%Y")
                    
                except Exception:
                    pass  # Keep original if parsing fails

 
            if mode == "train":
                try:
                    trains_data = search_trains(from_station, to_station, journey_date)

                    if not trains_data:
                        result_list.append({
                            "from": from_station,
                            "to": to_station,
                            "journey_date": journey_date,
                            "error": "No trains found"
                        })
                        continue

                    # Calculate average class fares
                    avg_fares = get_average_class_fares(trains_data)

                    # Append leg info to avg fares
                    for class_name, fare_info in avg_fares.items():
                        fare_info.update({
                            "from": from_station,
                            "to": to_station,
                            "journey_date": journey_date,
                            "class_name": class_name
                        })
                        result_list.append(fare_info)

                except Exception as e:
                    result_list.append({
                        "from": from_station,
                        "to": to_station,
                        "journey_date": journey_date,
                        "error": str(e)
                    })

            elif mode == "bus":
                try:
                    bus_results = search_buses(from_city, to_city, formatted_date_bus)
                    if not bus_results:
                        result_list.append({
                            "from": from_city,
                            "to": to_city,
                            "journey_date": journey_date,
                            "error": "No buses found"
                        })
                        continue

                    avg_metrics = get_fare_analysis(bus_results)
                    avg_metrics.update({
                        "from": from_city,
                        "to": to_city,
                        "journey_date": journey_date,
                        "class_name": "Bus"
                    })
                    result_list.append(avg_metrics)

                except Exception as e:
                    result_list.append({
                        "from": from_city,
                        "to": to_city,
                        "journey_date": journey_date,
                        "error": str(e)
                    })

        return result_list

    finally:
        db.close()

# ==================== TOOL 3: Research Travel Prices with Gemini ====================
@tool
def research_travel_price(params: str) -> Dict[str, Any]:
    """
    Use Gemini's built-in search to research current travel prices.
    
    Args:
        params: JSON string with:
        {
            "from_location": str,
            "to_location": str,
            "mode": str (train/bus/flight),
            "travel_class": str (e.g., "3AC", "AC Sleeper", "Economy")
        }
    
    Returns:
        Dictionary with estimated price and source info
    """
    try:
        params_dict = json.loads(params)
        from_loc = params_dict.get("from_location")
        to_loc = params_dict.get("to_location")
        mode = params_dict.get("mode")
        travel_class = params_dict.get("travel_class", "")
        
        # Configure Gemini with grounding (search enabled)
        genai.configure(api_key=GEMINI_API_KEY)
        
        # Use Gemini 2.0 Flash with grounding for real-time search
        model = genai.GenerativeModel('models/gemini-2.0-flash')
        
        # Build search prompt
        search_prompt = f"""
        Search for the current approximate price for traveling from {from_loc} to {to_loc} by {mode}.
        Travel class/type: {travel_class}
        
        Please provide:
        1. Approximate price in INR (single number, no range)
        2. Source of information
        3. Any important notes about pricing
        
        Format your response as JSON:
        {{
            "estimated_price": <number in INR>,
            "source": "<website or platform>",
            "notes": "<any relevant info>"
        }}
        
        Search the web for current prices and provide realistic estimates based on recent data.
        """
        
        response = model.generate_content(
            search_prompt,
            tools='google_search_retrieval'  # Enable Gemini's grounding
        )
        
        return {
            "from": from_loc,
            "to": to_loc,
            "mode": mode,
            "travel_class": travel_class,
            "research_result": response.text
        }
        
    except Exception as e:
        return {"error": f"Error researching price: {str(e)}"}


# ==================== TOOL 4: Fetch Hotel Pricing ====================


@tool
def get_hotel_pricing(trip_id: str) -> Dict[str, Any]:
    """
    Fetch hotel preferences and calculate estimated hotel cost using real search.
    
    Args:
        trip_id (str): The ID of the trip to fetch.
    
    Returns:
        dict: Detailed hotel pricing breakdown and estimates.
    """
    # --- Parse Trip ID ---
    try:
        trip_id = int(trip_id)
    except (ValueError, TypeError):
        try:
            parsed = json.loads(trip_id)
            trip_id = int(parsed.get("trip_id", trip_id))
        except Exception:
            return {"error": f"Invalid trip_id format: {trip_id}"}

    db: Session = SessionLocal()

    try:
        # --- Step 1️⃣: Fetch Trip and Preferences ---
        prefs = db.query(HotelPreferences).filter(HotelPreferences.trip_id == trip_id).first()
        trip = db.query(Trip).filter(Trip.id == trip_id).first()

        if not prefs or not trip:
            return {"error": f"No hotel preferences or trip found for trip_id: {trip_id}"}

        # --- Step 2️⃣: Extract all required arguments ---
        destination = trip.destination or trip.destination_full_name
        check_in = prefs.check_in_date
        check_out = prefs.check_out_date
        no_of_rooms = prefs.no_of_rooms or 1
        no_of_adult = prefs.no_of_adult or 2
        no_of_child = prefs.no_of_child or 0
        min_price = prefs.min_price or 1
        max_price = prefs.max_price or 1000000
        sort_type = prefs.sort_type or "Popular|DESC"

        # --- Step 3️⃣: Call the real-time price analyzer ---
        price_summary = calculate_average_hotel_price(
            destination=destination,
            check_in=check_in,
            check_out=check_out,
            no_of_rooms=no_of_rooms,
            no_of_adult=no_of_adult,
            no_of_child=no_of_child,
            min_price=min_price,
            max_price=max_price,
            sort_type=sort_type,
        )

        # --- Step 4️⃣: Add metadata ---
        if price_summary.get("status"):
            price_summary.update({
                "trip_id": trip_id,
                "selected_property_types": prefs.selected_property_types or [],
            })
        else:
            price_summary.update({
                "trip_id": trip_id,
                "error": "Could not compute average pricing — no hotels found or invalid API response."
            })

        return price_summary

    except Exception as e:
        return {"error": f"Error fetching hotel pricing: {str(e)}"}
    finally:
        db.close()


# ==================== TOOL 5: Fetch Trip Itineary ====================


@tool
def get_trip_itinerary(trip_id: str) -> Dict[str, Any]:
    """
    Fetch a complete trip itinerary for expense tracking.
    
    Args:
        trip_id (str): Trip ID as string or JSON.
    
    Returns:
        dict: Structured itinerary with days, places, food, culture, and travel tips.
    """
    import json

    # --- Parse Trip ID ---
    try:
        trip_id = int(trip_id)
    except (ValueError, TypeError):
        try:
            parsed = json.loads(trip_id)
            trip_id = int(parsed.get("trip_id", trip_id))
        except Exception:
            return {"error": f"Invalid trip_id format: {trip_id}"}

    db = SessionLocal()

    try:
        # --- Fetch all itinerary entries for the trip ---
        itinerary_entries = (
            db.query(Itinerary)
            .filter(Itinerary.trip_id == trip_id)
            .order_by(Itinerary.day.asc())
            .all()
        )

        if not itinerary_entries:
            return {"error": f"No itinerary found for trip_id {trip_id}"}

        # --- Build structured itinerary ---
        itinerary_data: List[Dict[str, Any]] = []
        for entry in itinerary_entries:
            places = [
                {
                    "id": place.id,
                    "name": place.name,
                    "description": place.description,
                    "latitude": place.latitude,
                    "longitude": place.longitude,
                    "best_time_to_visit": place.best_time_to_visit,
                }
                for place in entry.places
            ]

            itinerary_data.append({
                "day": entry.day,
                "date": entry.date.strftime("%Y-%m-%d"),
                "food": entry.food or [],
                "culture": entry.culture or [],
                "travel_tips": entry.travel_tips or [],
                "places": places
            })

        return {
            "trip_id": trip_id,
            "itinerary": itinerary_data,
            "total_days": len(itinerary_data)
        }

    except Exception as e:
        return {"error": f"Error fetching itinerary: {str(e)}"}

    finally:
        db.close()


def parse_agent_output(raw_output: str) -> Dict[str, Any]:
    """
    Safely parse the Gemini agent output into a Python dictionary.

    Handles:
    - Clean JSON blocks in markdown (```json ... ```)
    - Plain JSON-like strings
    - Malformed or extra text before/after JSON
    """

    if not raw_output:
        return {"error": "Empty response from AI agent"}

    # Extract JSON block if wrapped in markdown
    json_match = re.search(r"```json(.*?)```", raw_output, re.DOTALL)
    if json_match:
        raw_output = json_match.group(1).strip()

    # Try direct JSON load
    try:
        return json.loads(raw_output)
    except json.JSONDecodeError:
        pass

    # Attempt to clean up trailing text
    try:
        start_idx = raw_output.find("{")
        end_idx = raw_output.rfind("}") + 1
        json_str = raw_output[start_idx:end_idx]
        return json.loads(json_str)
    except Exception:
        return {"error": "Failed to parse JSON", "raw_output": raw_output}



def get_cost_breakdown(user_id: int, trip_id: int):
    """
    Create a Gemini-based AI agent and run a complete expense analysis for a trip,
    including travel, hotel, and itinerary-based (activities/food) expenses.

    Args:
        user_id (int): User ID for fetching preferences and budget.
        trip_id (int): Trip ID for fetching travel and hotel options.

    Returns:
        dict: Final AI-generated expense breakdown and analysis.
    """

    # ========== 1️⃣ Initialize LLM + Agent ==========
    llm = ChatGoogleGenerativeAI(
        model="models/gemini-2.0-flash",
        temperature=0.1,
        google_api_key=GEMINI_API_KEY
    )

    prompt = hub.pull("hwchase17/react")

    tools = [
        get_user_preferences,
        get_leg_fares,
        get_hotel_pricing,
        get_trip_itinerary
    ]

    agent = create_react_agent(
        llm=llm,
        tools=tools,
        prompt=prompt
    )

    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=15
    )

    # ========== 2️⃣ Construct Workflow Prompt ==========
    comprehensive_prompt = f"""
    Analyze and summarize the complete trip expenses for user_id {user_id} and trip_id {trip_id}.

    WORKFLOW:

    1. Call get_user_preferences
       Input: {user_id}
       - Extract total budget, travel preferences, class preferences, and number of travelers (no_of_travelers).

    2. Call get_leg_fares
       Input: {trip_id}
       - Fetch all itinerary legs (train, bus, flight) and calculate per-person cost based on preferred class.

    3. For each travel leg:
       - If mode = "train": Use research_travel_price to fetch accurate 3A/SL fares.
       - If mode = "bus": Use search_buses and get_fare_analysis.
       - If mode = "flight": Use research_travel_price for flight class.

    4. Call get_hotel_pricing
       Input: {trip_id}
       - Compute total and per-person hotel cost.

    5. Call get_trip_itinerary
       Input: {trip_id}
       - For each day in itinerary:
           - Identify food experiences → estimate daily meal costs (₹300–₹800 per meal per person)
           - Identify cultural or tourist spots → add entry/activity costs (₹200–₹500 per spot per person)
           - Include local transport (₹100–₹400 per person)
       - For each expense category, create separate JSON items like:

           {{
               "expense_type": "Trip Itinerary",
               "expense_name": "Day 1 Itinerary - Food",
               "details": "Breakfast and lunch at local cafes, includes bottled water and light snacks.",
               "estimated_cost": 1600.0,
               "cost_per_person": 800.0
           }},
           {{
               "expense_type": "Trip Itinerary",
               "expense_name": "Day 1 Itinerary - Local Transport",
               "details": "Auto fare and shared cab to tourist spots around the city.",
               "estimated_cost": 400.0,
               "cost_per_person": 200.0
           }},
           {{
               "expense_type": "Trip Itinerary",
               "expense_name": "Day 1 Itinerary - Entry Fees",
               "details": "Entry tickets for Triveni Ghat and local temple visits.",
               "estimated_cost": 600.0,
               "cost_per_person": 300.0
           }}

    6. Combine all expenses into a final structured JSON:

    {{
        "total_budget": <user_total_budget>,
        "expenses": [
            {{
                "expense_type": "Travel",
                "expense_name": "Train: Nagpur → Delhi (3A)",
                "details": "Sleeper overnight journey, includes base fare and service charges.",
                "estimated_cost": <fare_per_person * no_of_travelers>,
                "cost_per_person": <fare_per_person>
            }},
            {{
                "expense_type": "Hotel",
                "expense_name": "Hotel Stay (4 Nights)",
                "details": "Includes room charges and applicable taxes for the stay duration.",
                "estimated_cost": <total_hotel_cost>,
                "cost_per_person": <total_hotel_cost / no_of_travelers>
            }},
            {{
                "expense_type": "Trip Itinerary",
                "expense_name": "Day 2 Itinerary - Food",
                "details": "Breakfast at hotel and dinner near riverfront cafes.",
                "estimated_cost": 1800.0,
                "cost_per_person": 900.0
            }},
            ...
        ],
        "total_expenses": <sum_of_all_expenses>,
        "budget_remaining": <total_budget - total_expenses>
    }}

    IMPORTANT:
    - Always include the `details` field describing the context of each expense.
    - Each itinerary day must appear with separate expense entries.
    - Ensure output JSON is valid and structured properly.
    """

    # ========== 3️⃣ Run Agent ==========
    response = agent_executor.invoke({"input": comprehensive_prompt})

    # ========== 4️⃣ Parse Output ==========
    parsed_output = parse_agent_output(response.get("output", ""))

    return parsed_output


# if __name__ == "__main__":
#     result = run_expense_analysis(user_id=1, trip_id=1)
#     print(result)
