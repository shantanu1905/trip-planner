# ==================== STANDARD LIBRARIES ====================
from typing import List, Dict, Any
import json
import os
import re
from datetime import datetime

# ==================== SQLALCHEMY / DATABASE ====================
from sqlalchemy.orm import Session
from app.database.database import SessionLocal
from app.database.models import Trip, Itinerary, ItineraryPlace

# ==================== GOOGLE GENAI WITH GROUNDING ====================
from google import genai
from google.genai import types

from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize Genai Client
client = genai.Client(api_key=GEMINI_API_KEY)


# ==================== TOOL 1: Fetch Trip Itinerary Places ====================
def get_itinerary_places(trip_id: int) -> Dict[str, Any]:
    """
    Fetch only place names from trip itinerary.
    
    Args:
        trip_id (int): Trip ID.
    
    Returns:
        dict: City and list of tourist place names.
    """
    db = SessionLocal()

    try:
        # Fetch trip details
        trip = db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            return {"error": f"No trip found for trip_id {trip_id}"}

        # Fetch itinerary
        itinerary_entries = (
            db.query(Itinerary)
            .filter(Itinerary.trip_id == trip_id)
            .order_by(Itinerary.day.asc())
            .all()
        )

        if not itinerary_entries:
            return {"error": f"No itinerary found for trip_id {trip_id}"}

        # Extract only place names
        place_names = []
        for entry in itinerary_entries:
            for place in entry.places:
                if place.name and place.name not in place_names:
                    place_names.append(place.name)

        return {
            "trip_id": trip_id,
            "destination": trip.destination or trip.destination_full_name,
            "places": place_names,
            "total_places": len(place_names)
        }

    except Exception as e:
        return {"error": f"Error fetching itinerary: {str(e)}"}
    finally:
        db.close()


# ==================== TOOL 2: Research Localities with Complete Details ====================
def research_hotel_localities(city: str, places: List[str]) -> Dict[str, Any]:
    """
    Research hotel localities with complete connectivity, safety, and location details.
    
    Args:
        city (str): Destination city
        places (List[str]): List of tourist place names
    
    Returns:
        dict: Complete locality recommendations in exact format
    """
    try:
        places_text = ", ".join(places)
        
        search_prompt = f"""
        For tourists visiting {city}, India who plan to visit these tourist places: {places_text}
        
        Identify the top 5 best hotel localities/neighborhoods that provide optimal coverage to visit ALL these places.
        
        For EACH locality, research and provide COMPLETE details in this EXACT JSON format:
        
        {{
            "city": "{city}",
            "places_to_cover": {places},
            "recommended_localities": [
                {{
                    "rank_id": 1,
                    "locality_name": "Full locality name with city, state, country (e.g., Laxman Jhula, Rishikesh, Uttarakhand, India)",
                    "strategic_positioning": "Detailed explanation of why this locality is strategically best to cover the tourist places: {places_text}. Mention specific places it's near and travel advantages.",
                    
                    "connectivity": {{
                        "metro_stations": ["Metro Station Name 1", "Metro Station Name 2"] or [] if no metro exists in the city,
                        "bus_connectivity": {{
                            "rating": "Good" or "Average" or "Worst",
                            "frequency": "Every 10-15 minutes" or "Every 30 minutes" or specific frequency
                        }},
                        "auto_taxi_availability": "Good" or "Average" or "Worst",
                        "overall_connectivity_rating": "Good" or "Average" or "Worst"
                    }},
                    
                    "safety": {{
                        "overall_rating": "Good" or "Average" or "Worst",
                        "police_station": [
                            "Police Station Name 1, Full Address",
                            "Police Station Name 2, Full Address"
                        ] or [] if no police station data found,
                        "nearby_hospitals": [
                            {{"name": "Hospital Name 1", "address": "Full Address", "rating": "4.2/5"}},
                            {{"name": "Hospital Name 2", "address": "Full Address", "rating": "4.5/5"}}
                        ] or [] if NO ACTUAL HOSPITALS exist in or very near the locality,
                        "safety_concerns": [
                            "Specific concern 1 if any",
                            "Specific concern 2 if any"
                        ] or [] if no significant concerns,
                        "positive_reviews": [
                            "Positive safety aspect 1 from reviews",
                            "Positive safety aspect 2 from reviews"
                        ] or [] if no positive reviews found
                    }},
                    
                    "location_info": {{
                        "restaurants_cafes": [
                            {{"name": "Restaurant/Cafe Name 1", "rating": "4.3/5"}},
                            {{"name": "Restaurant/Cafe Name 2", "rating": "4.5/5"}},
                            {{"name": "Restaurant/Cafe Name 3", "rating": "4.1/5"}}
                        ] or [] if no restaurant data available,
                        "hotel_budget_range": "₹1500-₹4000 per night" (realistic range for this locality),
                        "tourist_suitability_score": "8/10" (realistic score out of 10)
                    }}
                }}
            ]
        }}
        
        CRITICAL INSTRUCTIONS:
        
        1. **locality_name**: MUST include Area, City, State, Country (e.g., "Tapovan, Rishikesh, Uttarakhand, India")
        
        2. **strategic_positioning**: Explain how this locality helps cover the SPECIFIC places: {places_text}
        
        3. **Ratings**: ONLY use "Good", "Average", or "Worst" for connectivity and safety ratings
        
        4. **HOSPITALS - VERY IMPORTANT**:
           - ONLY include ACTUAL HOSPITALS (medical facilities with emergency services)
           - DO NOT include: Hotels, Lodges, Guest Houses, Dharamshalas, Ashrams, Restaurants
           - If a locality is remote/mountainous and has NO hospitals nearby, use [] (empty array)
           - Examples of VALID hospitals: "District Hospital", "Community Health Center", "Primary Health Center", "Medical College", "Apollo Hospital"
           - Examples of INVALID (DO NOT INCLUDE): "Hotel Kedarnath", "GMVN Rest House", "Tourist Lodge"
           - If unsure, leave the array empty []
        
        5. **Police Stations**:
           - Include actual police stations/police posts with addresses
           - If no police station data found, use [] (empty array)
        
        6. **Metro Stations**:
           - ONLY if the city has a metro system
           - For cities like Kedarnath, Rishikesh (no metro), use [] (empty array)
        
        7. **Restaurants/Cafes**:
           - Include ONLY actual restaurants, cafes, dhabas, eateries
           - DO NOT include hospitals or hotels here
           - If no restaurant data found, use [] (empty array)
        
        8. **Safety Concerns**:
           - Include REAL concerns like: "Landslides during monsoon", "High altitude sickness", "Limited medical facilities"
           - Use [] if the locality is generally safe with no specific concerns
        
        9. **hotel_budget_range**: Realistic price range in INR for hotels in this locality
        
        10. **tourist_suitability_score**: Realistic score out of 10
        
        Search Google and Google Maps for ACCURATE and CURRENT information about:
        - Hotel booking areas and localities in {city}
        - Public transport connectivity (metro, bus routes)
        - ACTUAL hospitals and medical facilities (not hotels!)
        - Police stations and security infrastructure
        - Restaurants, cafes, and dining options
        - Safety reviews from tourists
        - Hotel price ranges in different areas
        
        Provide REAL, FACTUAL data from your search. 
        If you cannot find specific information (like hospitals in a remote area), use empty arrays [] instead of making up names.
        DO NOT confuse hotels with hospitals.
        
        Return ONLY valid JSON with NO repetition, NO additional text.
        The response should be EXACTLY ONE JSON object.
        """
        
        # Configure with Google Search + Google Maps grounding
        search_tool = types.Tool(google_search=types.GoogleSearch())
        
        config = types.GenerateContentConfig(
            tools=[search_tool],
            temperature=0.1  # Low temperature for factual accuracy
        )
        
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=search_prompt,
            config=config
        )
        
        return parse_json_response(response.text)
        
    except Exception as e:
        return {"error": f"Error researching localities: {str(e)}"}



# ==================== HELPER: Parse JSON Response ====================
def parse_json_response(text: str) -> Dict[str, Any]:
    """
    Parse JSON from AI response, handling duplicates and malformed responses.
    """
    if not text:
        return {"error": "Empty response"}
    
    # Remove markdown code blocks if present
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    text = text.strip()
    
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Find FIRST complete JSON object (handles duplicate responses)
    try:
        # Find first opening brace
        start_idx = text.find("{")
        if start_idx == -1:
            return {"error": "No JSON object found", "raw_text": text[:500]}
        
        # Find matching closing brace for first object
        brace_count = 0
        end_idx = start_idx
        for i in range(start_idx, len(text)):
            if text[i] == "{":
                brace_count += 1
            elif text[i] == "}":
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break
        
        if end_idx > start_idx:
            json_str = text[start_idx:end_idx]
            return json.loads(json_str)
        
    except Exception as e:
        return {"error": f"Failed to parse JSON: {str(e)}", "raw_text": text[:500]}
    
    return {"error": "Could not extract valid JSON", "raw_text": text[:500]}


# ==================== MAIN: Get Hotel Locality Recommendations ====================
def get_hotel_locality_recommendations(trip_id: int) -> Dict[str, Any]:
    """
    Get hotel locality recommendations with complete details.
    
    Args:
        trip_id (int): Trip ID
    
    Returns:
        dict: Comprehensive locality recommendations in specified format
    """
    
    try:
        print(f"📍 Fetching places for trip_id: {trip_id}...")
        
        # Step 1: Get itinerary places
        itinerary_data = get_itinerary_places(trip_id)
        
        if "error" in itinerary_data:
            return itinerary_data
        
        city = itinerary_data.get("destination")
        places = itinerary_data.get("places", [])
        
        if not city or not places:
            return {"error": "Missing destination or places in itinerary"}
        
        print(f"✅ Found {len(places)} places: {', '.join(places)}")
        print(f"🔍 Researching hotel localities in {city}...")
        
        # Step 2: Research localities with Google Search grounding
        result = research_hotel_localities(city, places)
        
        if "error" in result:
            return result
        
        print("✅ Analysis complete!")
        
        # Add metadata
        result["analysis_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        result["trip_id"] = trip_id
        
        return result
        
    except Exception as e:
        return {"error": f"Analysis failed: {str(e)}"}


# # ==================== EXAMPLE USAGE ====================
# if __name__ == "__main__":
#     # Test with your trip_id
#     result = get_hotel_locality_recommendations(trip_id=1)
    
#     # Pretty print
#     print("\n" + "="*80)
#     print("HOTEL LOCALITY RECOMMENDATIONS")
#     print("="*80)
#     print(json.dumps(result, indent=2, ensure_ascii=False))