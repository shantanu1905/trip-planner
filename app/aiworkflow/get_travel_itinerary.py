from typing import List, Dict
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import SystemMessage, HumanMessage
from dotenv import load_dotenv
import os
import json
import re

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


def generate_trip_itinerary(
    trip_id: int,
    start_date: str,
    end_date: str,
    destination: str,
    activities: List[str],
    travelling_with: str,
    tourist_places: List[Dict]
) -> Dict:
    """
    Generate a detailed day-wise trip itinerary using Gemini AI.

    Args:
        trip_id: Trip ID
        start_date: Trip start date (YYYY-MM-DD)
        end_date: Trip end date (YYYY-MM-DD)
        destination: Destination city
        activities: List of activities (["adventure", "cultural", ...])
        travelling_with: Description (e.g., "family", "friends")
        tourist_places: List of tourist places with details

    Returns:
        Dict containing itinerary (JSON)
    """
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.2,
            google_api_key=GEMINI_API_KEY,
        )

        # Updated prompt with instructions for limited days / many places
        human_prompt = f"""
        You are a travel itinerary planner AI.  
        You will receive the following details:
        - Trip ID: {trip_id}
        - Start Date: {start_date}
        - End Date: {end_date}
        - Destination: {destination}
        - Activities: {activities}
        - Travelling With: {travelling_with}
        - Tourist Places: {json.dumps(tourist_places, ensure_ascii=False)}

        Your tasks:
        1. Calculate the number of days in the trip using start_date and end_date.
        2. Group tourist places based on proximity (latitude & longitude) so nearby places are visited on the same day.
        3. If there are more tourist places than available days, prioritize grouping places so that in limited time, as many places as possible are covered.
        - Include a note in the output if any places are skipped due to insufficient time.
        4. Plan the trip day by day:
        - Assign date for each day.
        - List places to visit in logical sequence.
        - Include "Best time to visit" for each place.
        - Suggest travel tips for the day.
        - Recommend local food spots.
        - Suggest cultural experiences or nearby activities.
        - Optionally include approximate travel time between places.

        Output must be valid JSON in this format:
        {{
        "trip_id": {trip_id},
        "itinerary": [
            {{
            "day": 1,
            "date": "YYYY-MM-DD",
            "places": [
                {{"name": "Place 1", "description": "...", "latitude": "..", "longitude": "..", "best_time_to_visit": "Morning/Evening etc."}},
                {{"name": "Place 2", "description": "...", "best_time_to_visit": "Morning/Evening etc."}}
            ],
            "travel_tips": "Some travel tips",
            "food": ["Food Spot 1", "Food Spot 2"],
            "culture": ["Cultural Experience 1", "Cultural Experience 2"]
            }}
        ],
        "note": "Optional note if some places are skipped due to less available time"
        }}

        Ensure JSON is always valid with no missing commas or extra text. Return only JSON, nothing else.
        """

        response = llm.invoke([
            SystemMessage(content="You are a travel itinerary planning assistant."),
            HumanMessage(content=human_prompt)
        ])

        ai_output = response.content

        # Attempt to parse JSON cleanly
        try:
            return json.loads(ai_output)
        except json.JSONDecodeError:
            # fallback: extract JSON with regex
            match = re.search(r'\{.*\}', ai_output, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return {"error": "Could not parse AI output as JSON", "raw_output": ai_output}

    except Exception as e:
        return {"error": str(e), "raw_output": ai_output if 'ai_output' in locals() else None}


# # ✅ Usage Example:
# itinerary = generate_trip_itinerary(
#     trip_id=123,
#     start_date="2025-10-20",
#     end_date="2025-10-22",
#     destination="Rishikesh",
#     activities=["adventure", "spiritual"],
#     travelling_with="friends",
#     tourist_places=[
#         {"Name": "Laxman Jhula", "Description": "Famous suspension bridge", "GeoCoordinates": {"lat": 30.056, "lng": 78.267}, "ImageURL": "http://example.com/image1.jpg"},
#         {"Name": "Neer Garh Waterfall", "GeoCoordinates": {"lat": 30.075, "lng": 78.257}},
#         {"Name": "Ram Jhula", "GeoCoordinates": {"lat": 30.0565, "lng": 78.272}},
#         {"Name": "Triveni Ghat", "GeoCoordinates": {"lat": 30.0568, "lng": 78.274}},
#         {"Name": "Beatles Ashram", "GeoCoordinates": {"lat": 30.051, "lng": 78.269}}
#     ]
# )
# print(json.dumps(itinerary, indent=2, ensure_ascii=False))
