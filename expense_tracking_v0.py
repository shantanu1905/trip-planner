from langchain_core.tools import tool
from datetime import datetime
from typing import Dict, Any, Optional
import json
from sqlalchemy.orm import Session
from app.database.database import SessionLocal
from app.database.models import UserPreferences, TravelOptions, Trip

# ==================== TOOL 1: Fetch User Preferences ====================
@tool
def get_user_preferences(user_id: int) -> Dict[str, Any]:
    """
    Fetch user preferences for budget tracking and travel planning.
    
    Args:
        user_id: The ID of the user whose preferences to fetch
    
    Returns:
        Dictionary containing user preferences including budget, food, activities, 
        travel class preferences, and transport mode preferences
    """
    db = SessionLocal()
    try:
        # Fetch user preferences
        prefs = db.query(UserPreferences).filter(
            UserPreferences.user_id == user_id
        ).first()
        
        if not prefs:
            return {"error": f"No preferences found for user_id: {user_id}"}
        
        # Extract relevant fields
        result = {
            "user_id": user_id,
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


# ==================== TOOL 2: Fetch Travel Options ====================
@tool
def get_travel_options(trip_id: int) -> Dict[str, Any]:
    """
    Fetch selected travel options for a specific trip.
    
    Args:
        trip_id: The ID of the trip whose travel options to fetch
    
    Returns:
        Dictionary containing selected travel options with legs, modes, costs, and dates
    """
    db = SessionLocal()
    try:
        # Fetch travel options
        travel_opts = db.query(TravelOptions).filter(
            TravelOptions.trip_id == trip_id
        ).first()
        
        if not travel_opts:
            return {"error": f"No travel options found for trip_id: {trip_id}"}
        
        result = {
            "trip_id": trip_id,
            "selected_travel_options": travel_opts.selected_travel_options
        }
        
        return result
        
    except Exception as e:
        return {"error": f"Error fetching travel options: {str(e)}"}
    finally:
        db.close()


# ==================== TOOL 3: Calculate Travel Expenses ====================
@tool
def calculate_travel_expenses(params: str) -> Dict[str, Any]:
    """
    Calculate estimated travel expenses for a trip based on user preferences and travel options.

    Input: JSON string
    {
        "user_id": int,
        "trip_id": int
    }

    Output format:
    {
        "expenses": [
            {
                "trip_id": int,
                "expense_type": "Travel" | "Hotel" | "Other",
                "expense_name": str,
                "total_budget": int,
                "estimated_cost": int,
                "remaining_budget": int
            },
            ...
        ]
    }
    """
    import json
    from sqlalchemy.orm import Session
    from app.database.database import SessionLocal
    from app.database.models import UserPreferences, TravelOptions

    db: Session = SessionLocal()
    try:
        params_dict = json.loads(params)
        user_id = params_dict.get("user_id")
        trip_id = params_dict.get("trip_id")

        if not user_id or not trip_id:
            return {"error": "Both user_id and trip_id are required"}

        # Fetch user preferences
        prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        if not prefs:
            return {"error": f"No preferences found for user_id {user_id}"}

        # Fetch travel options
        travel_opts = db.query(TravelOptions).filter(TravelOptions.trip_id == trip_id).first()
        if not travel_opts or not travel_opts.selected_travel_options:
            return {"error": f"No selected travel options found for trip_id {trip_id}"}

        selected_options = travel_opts.selected_travel_options
        legs = selected_options.get("legs", [])

        total_budget = prefs.default_budget or 0
        total_estimated_cost = 0
        expenses_list = []

        for idx, leg in enumerate(legs, 1):
            from_loc = leg.get("from", "")
            to_loc = leg.get("to", "")
            mode = leg.get("mode", "Travel").title()
            approx_cost = leg.get("approx_cost", 1000)  # fallback default

            try:
                estimated_cost = int(approx_cost.replace("INR", "").replace(",", "").strip())
            except:
                estimated_cost = 1000

            remaining_budget = total_budget - (total_estimated_cost + estimated_cost)
            total_estimated_cost += estimated_cost

            expenses_list.append({
                "trip_id": trip_id,
                "expense_type": "Travel",
                "expense_name": f"{mode}: {from_loc} → {to_loc}",
                "total_budget": total_budget,
                "estimated_cost": estimated_cost,
                "remaining_budget": remaining_budget
            })

        return {"expenses": expenses_list}

    except Exception as e:
        return {"error": f"Error calculating expenses: {str(e)}"}
    finally:
        db.close()


from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_react_agent, AgentExecutor
from langchain import hub

def create_expense_tracker_agent(google_api_key: str):
    """
    Create an AI agent for tracking trip expenses.
    
    Args:
        google_api_key: Google API key for Gemini model
    
    Returns:
        AgentExecutor ready to handle expense tracking queries
    """
    # Initialize Gemini model
    llm = ChatGoogleGenerativeAI(
        model="models/gemini-2.0-flash",
        temperature=0,
        google_api_key=google_api_key
    )
    
    # Pull ReAct prompt
    prompt = hub.pull("hwchase17/react")
    
    # Register tools
    tools = [
        get_user_preferences,
        get_travel_options,
        calculate_travel_expenses
    ]
    
    # Create agent
    agent = create_react_agent(
        llm=llm,
        tools=tools,
        prompt=prompt
    )
    
    # Wrap with executor
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True
    )
    
    return agent_executor


# ==================== Usage Example ====================
if __name__ == "__main__":
    # ===== INITIALIZE VARIABLES =====
    USER_ID = 1
    TRIP_ID = 1
    
    print("="*80)
    print(f"🧳 EXPENSE TRACKER AGENT - Trip Analysis")
    print(f"User ID: {USER_ID} | Trip ID: {TRIP_ID}")
    print("="*80 + "\n")
    
    # Initialize agent
    agent = create_expense_tracker_agent(
        google_api_key=""
    )
    
    # Single comprehensive prompt that gathers all info
    comprehensive_prompt = f"""
    Analyze the complete trip expenses for user_id {USER_ID} and trip_id {TRIP_ID}.

    Steps:
    1. Fetch user preferences to get total budget.
    2. Fetch selected travel options to see journey legs.
    3. Calculate estimated travel expenses for each leg.

    Output format MUST be JSON with:

    expenses: [
        {{
            "trip_id": int,
            "expense_type": "Travel" | "Hotel" | "Other",
            "expense_name": str,
            "total_budget": int,
            "estimated_cost": int,
            "remaining_budget": int
        }}
    ]

    Do NOT add extra text outside the JSON.
    """

    
    # Invoke agent with single comprehensive prompt
    response = agent.invoke({
        "input": comprehensive_prompt
    })
    
    print("\n" + "="*80)
    print("📊 FINAL ANALYSIS:")
    print("="*80)
    print(response["output"])
    print("\n" + "="*80)






















    # def calculate_travel_expenses(params: str) -> Dict[str, Any]:
#     """
#     Calculate detailed travel expenses based on user preferences and travel options.
    
#     Input should be a JSON string with keys:
#     {
#         "user_id": 123,
#         "trip_id": 456
#     }
    
#     Returns:
#         Detailed breakdown of estimated expenses for each leg of the journey
#     """
#     try:
#         # Parse input
#         params_dict = json.loads(params)
#         user_id = params_dict.get("user_id")
#         trip_id = params_dict.get("trip_id")
        
#         if not user_id or not trip_id:
#             return {"error": "Both user_id and trip_id are required"}
        
#         # Fetch user preferences
#         prefs_result = get_user_preferences.invoke({"user_id": user_id})
#         if "error" in prefs_result:
#             return prefs_result
        
#         # Fetch travel options
#         travel_result = get_travel_options.invoke({"trip_id": trip_id})
#         if "error" in travel_result:
#             return travel_result
        
#         # Extract data
#         preferences = prefs_result
#         selected_options = travel_result.get("selected_travel_options", {})
#         legs = selected_options.get("legs", [])
        
#         if not legs:
#             return {"error": "No travel legs found in selected options"}
        
#         # Calculate expenses for each leg
#         expenses = []
#         total_estimated_cost = 0
        
#         for idx, leg in enumerate(legs, 1):
#             mode = leg.get("mode", "").lower()
#             from_loc = leg.get("from")
#             to_loc = leg.get("to")
#             journey_date = leg.get("journey_date")
#             approx_cost_str = leg.get("approx_cost", "")
            
#             # Parse approximate cost range
#             estimated_cost = _parse_cost_range(approx_cost_str, mode, preferences)
            
#             expense_detail = {
#                 "expense_id": idx,
#                 "leg": f"{from_loc} to {to_loc}",
#                 "mode": mode.title(),
#                 "journey_date": journey_date,
#                 "estimated_cost": estimated_cost,
#                 "cost_basis": _get_cost_basis(mode, preferences),
#                 "booking_url": leg.get("booking_url", "")
#             }
            
#             expenses.append(expense_detail)
#             total_estimated_cost += estimated_cost
        
#         # Prepare final output
#         result = {
#             "trip_id": trip_id,
#             "user_id": user_id,
#             "total_budget": preferences.get("default_budget"),
#             "total_estimated_travel_cost": total_estimated_cost,
#             "remaining_budget": preferences.get("default_budget") - total_estimated_cost if preferences.get("default_budget") else None,
#             "expenses": expenses,
#             "summary": {
#                 "number_of_legs": len(legs),
#                 "travelling_with": preferences.get("travelling_with"),
#                 "food_preference": preferences.get("food_preference")
#             }
#         }
        
#         return result
        
#     except json.JSONDecodeError:
#         return {"error": "Invalid JSON input"}
#     except Exception as e:
#         return {"error": f"Error calculating expenses: {str(e)}"}


# # ==================== Helper Functions ====================
# def _parse_cost_range(cost_str: str, mode: str, preferences: Dict) -> float:
#     """
#     Parse cost range string and return estimated cost based on user preferences.
#     Example: "INR 800 - INR 2500" -> returns appropriate value based on class preference
#     """
#     try:
#         # Remove "INR" and split by "-"
#         cost_str = cost_str.replace("INR", "").replace(",", "").strip()
        
#         if "-" in cost_str:
#             parts = cost_str.split("-")
#             min_cost = float(parts[0].strip())
#             max_cost = float(parts[1].strip())
            
#             # Adjust based on mode and preferences
#             if mode == "train":
#                 train_class = preferences.get("preferred_train_class", "").lower()
#                 if "sleeper" in train_class or "sl" in train_class:
#                     return min_cost
#                 elif "3a" in train_class or "3_tier" in train_class:
#                     return (min_cost + max_cost) / 2
#                 elif "2a" in train_class or "2_tier" in train_class:
#                     return max_cost * 0.8
#                 else:
#                     return (min_cost + max_cost) / 2
                    
#             elif mode == "bus":
#                 bus_prefs = preferences.get("bus_preferences", {})
#                 if bus_prefs.get("ac") and bus_prefs.get("sleeper"):
#                     return max_cost * 0.9
#                 elif bus_prefs.get("ac"):
#                     return (min_cost + max_cost) / 2
#                 else:
#                     return min_cost * 1.2
                    
#             elif mode == "flight":
#                 flight_class = preferences.get("preferred_flight_class", "").lower()
#                 if "economy" in flight_class:
#                     return (min_cost + max_cost) / 2
#                 elif "business" in flight_class:
#                     return max_cost
#                 else:
#                     return (min_cost + max_cost) / 2
            
#             # Default to average
#             return (min_cost + max_cost) / 2
#         else:
#             return float(cost_str)
            
#     except:
#         return 1000.0  # Default fallback


# def _get_cost_basis(mode: str, preferences: Dict) -> str:
#     """Get human-readable description of how cost was calculated"""
#     if mode == "train":
#         train_class = preferences.get("preferred_train_class", "Unknown")
#         return f"Based on {train_class} class preference"
#     elif mode == "bus":
#         bus_prefs = preferences.get("bus_preferences", {})
#         features = []
#         if bus_prefs.get("ac"):
#             features.append("AC")
#         if bus_prefs.get("sleeper"):
#             features.append("Sleeper")
#         if bus_prefs.get("seater"):
#             features.append("Seater")
#         return f"Based on bus preferences: {', '.join(features) if features else 'Standard'}"
#     elif mode == "flight":
#         flight_class = preferences.get("preferred_flight_class", "Economy")
#         return f"Based on {flight_class} class preference"
#     return "Average cost estimate"


# ==================== AI Agent Setup ====================