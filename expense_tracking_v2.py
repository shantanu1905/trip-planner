from langchain_core.tools import tool
from datetime import datetime
from typing import Dict, Any, Optional
import json
from sqlalchemy.orm import Session
from app.database.database import SessionLocal
from app.database.models import UserPreferences, TravelOptions, Trip
import google.generativeai as genai

# ==================== TOOL 1: Fetch User Preferences ====================
@tool
def get_user_preferences(user_id: str) -> Dict[str, Any]:
    """
    Fetch user preferences for budget tracking and travel planning.
    
    Args:
        user_id: The ID of the user whose preferences to fetch (as string)
    
    Returns:
        Dictionary containing user preferences including budget, food, activities, 
        travel class preferences, and transport mode preferences
    """
    # Convert to int if needed
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        # If it's a JSON string, parse it
        try:
            import json
            parsed = json.loads(user_id)
            user_id = int(parsed.get("user_id", user_id))
        except:
            return {"error": f"Invalid user_id format: {user_id}"}
    db = SessionLocal()
    try:
        prefs = db.query(UserPreferences).filter(
            UserPreferences.user_id == user_id
        ).first()
        
        if not prefs:
            return {"error": f"No preferences found for user_id: {user_id}"}
        
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
def get_travel_options(trip_id: str) -> Dict[str, Any]:
    """
    Fetch selected travel options for a specific trip.
    
    Args:
        trip_id: The ID of the trip whose travel options to fetch (as string)
    
    Returns:
        Dictionary containing selected travel options with legs, modes, costs, and dates
    """
    # Convert to int if needed
    try:
        trip_id = int(trip_id)
    except (ValueError, TypeError):
        # If it's a JSON string, parse it
        try:
            import json
            parsed = json.loads(trip_id)
            trip_id = int(parsed.get("trip_id", trip_id))
        except:
            return {"error": f"Invalid trip_id format: {trip_id}"}
    db = SessionLocal()
    try:
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
        genai.configure(api_key="")
        
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


from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_react_agent, AgentExecutor
from langchain import hub

def create_expense_tracker_agent(google_api_key: str):
    """
    Create an AI agent that uses Gemini's internal search for real-time pricing.
    
    Args:
        google_api_key: Google API key for Gemini model
    """
    # Use Gemini with higher temperature for better reasoning
    llm = ChatGoogleGenerativeAI(
        model="models/gemini-2.0-flash",
        temperature=0.1,
        google_api_key=google_api_key
    )
    
    prompt = hub.pull("hwchase17/react")
    
    tools = [
        get_user_preferences,
        get_travel_options,
        research_travel_price
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
    
    return agent_executor


# ==================== Usage Example ====================
if __name__ == "__main__":
    USER_ID = 1
    TRIP_ID = 1
    
    print("="*80)
    print(f"🧳 AI EXPENSE TRACKER - Gemini Grounded Search")
    print(f"User ID: {USER_ID} | Trip ID: {TRIP_ID}")
    print("="*80 + "\n")
    
    agent = create_expense_tracker_agent(
        google_api_key=""
    )
    
    comprehensive_prompt = f"""
    Analyze trip expenses for user_id {USER_ID} and trip_id {TRIP_ID}.

    WORKFLOW:
    
    1. Call get_user_preferences
       Action Input: {USER_ID}
       Extract: default_budget, preferred_train_class, bus_preferences, preferred_flight_class
    
    2. Call get_travel_options
       Action Input: {TRIP_ID}
       Extract: all journey legs (from, to, mode)
    
    3. For EACH journey leg:
       - Determine the appropriate travel class based on user preferences
       - Call research_travel_price
       - Action Input: {{"from_location": "city1", "to_location": "city2", "mode": "train/bus/flight", "travel_class": "user preference"}}
       - Gemini will search internally and return current prices
       - Parse the price from the research result
    
    4. Build final expense report with:
       - Running total of expenses
       - Remaining budget after each leg
       - Source attribution for each price
    
    Final JSON output:
    {{
        "total_budget": <number>,
        "expenses": [
            {{
                "trip_id": {TRIP_ID},
                "expense_type": "Travel",
                "expense_name": "Train: Nagpur → Delhi",
                "estimated_cost": <researched price>,
                "remaining_budget": <calculated>,
                "travel_class": "3AC",
                "price_source": "<from Gemini research>"
            }}
        ],
        "total_expenses": <sum>,
        "budget_remaining": <total_budget - total_expenses>
    }}
    
    IMPORTANT: 
    - For get_user_preferences and get_travel_options, pass just the number (not JSON)
    - For research_travel_price, pass JSON string
    - Use research_travel_price for EACH leg to get real prices
    - Don't make up prices - let Gemini search and tell you
    """
    
    response = agent.invoke({
        "input": comprehensive_prompt
    })
    
    print("\n" + "="*80)
    print("📊 FINAL ANALYSIS (Gemini Grounded Research):")
    print("="*80)
    print(response["output"])
    print("\n" + "="*80)