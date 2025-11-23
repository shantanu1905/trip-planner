# ==================== STANDARD LIBRARIES ====================
from typing import List, Dict, Any, Optional
import json
import os
from datetime import datetime
import re

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


# ==================== TOOL: Fetch Weather & Travel Intelligence with Google Search ====================
def fetch_weather_and_travel_intelligence(destination: str) -> Dict[str, Any]:
    """
    Fetch comprehensive weather and travel intelligence using Google Search grounding.
    Gets current day weather, alerts, and tourist place status.
    
    Args:
        destination: Destination name (e.g., "Nashik, Maharashtra")
    
    Returns:
        Dictionary with current weather, alerts, and tourist place status
    """
    try:
        today = datetime.now().strftime("%B %d, %Y")
        current_time = datetime.now().strftime("%I:%M %p")
        
        intelligence_prompt = f"""
        You are a travel intelligence expert. Search Google for CURRENT DAY information about {destination}, India.
        
        **TODAY'S DATE:** {today}
        **CURRENT TIME:** {current_time}
        
        **SEARCH FOR (CURRENT DAY ONLY):**
        
        1. **Current Weather** (Right Now):
           - Search: "{destination} weather today"
           - Search: "{destination} temperature right now"
           - Get: Current temperature, feels like, condition, humidity, wind speed
           - Get: TODAY's forecast (morning, afternoon, evening)
        
        2. **Weather Alerts** (Active Today):
           - Search: "{destination} weather alert IMD today"
           - Search: "{destination} weather warning {today}"
           - Get: Active IMD alerts, severity, valid until when
        
        3. **Tourist Places Status** (Today):
           - Search: "{destination} tourist places closed today"
           - Search: "{destination} [place name] open today"
           - Check Google Maps for recent reviews mentioning closures
           - Verify if major tourist spots are accessible TODAY
        
        **SEARCH QUERIES TO USE:**
        - "{destination} weather today {today}"
        - "{destination} temperature now"
        - "{destination} IMD weather alert"
        - "{destination} tourist places status today"
        - "{destination} [specific place name] open or closed"
        
        **OUTPUT FORMAT (JSON ONLY):**
        {{
          "destination": "{destination}",
          "date": "{today}",
          "time": "{current_time}",
          "data_sources": ["Google Search", "IMD", "Google Maps"],
          
          "current_weather": {{
              "temperature_c": "25",
              "feels_like_c": "27",
              "condition": "Partly Cloudy",
              "humidity_percent": "70",
              "wind_kph": "12",
              "visibility_km": "10",
              "today_forecast": {{
                  "morning": "Clear skies, 22°C",
                  "afternoon": "Partly cloudy, 28°C",
                  "evening": "Light rain possible, 24°C"
              }},
              "reference_links": [
                  "https://weather.com/...",
                  "https://timesofindia.com/weather/..."
              ]
          }},
          
          "weather_alerts": [
              {{
                  "type": "Heavy Rainfall Warning",
                  "severity": "Moderate",
                  "issued_by": "IMD",
                  "valid_from": "November 23, 2025 6:00 AM",
                  "valid_until": "November 23, 2025 11:59 PM",
                  "description": "Heavy rainfall expected in isolated areas. Thunderstorm activity likely.",
                  "affected_activities": ["Outdoor trekking", "Water sports", "Open-air sightseeing"],
                  "reference_links": [
                      "https://mausam.imd.gov.in/...",
                      "https://www.ndtv.com/..."
                  ]
              }}
          ],
          
          "tourist_place_alerts": [
              {{
                  "place_name": "Ramkund Ghat",
                  "status": "Restricted/Closed/Open",
                  "reason": "High water level in Godavari River",
                  "last_verified": "November 23, 2025, 10:00 AM",
                  "alternative_suggestion": "Kalaram Temple (covered area, safe)",
                  "source": "Local news, Google Maps reviews",
                  "reference_links": [
                      "https://www.thehindu.com/...",
                      "https://www.google.com/maps/place/..."
                  ]
              }}
          ],
          
          "overall_travel_status": "SAFE/CAUTION/NOT_RECOMMENDED/UNSAFE",
          "weather_impact_summary": "Light rain expected in evening. Morning and afternoon suitable for outdoor activities. Carry umbrella after 5 PM."
        }}
        
        **CRITICAL INSTRUCTIONS:**
        
        1. **CURRENT DAY ONLY**: Only fetch information for TODAY ({today})
           - No forecasts beyond today
           - No old news from previous days
           - Focus on "right now" and "today"
        
        2. **REFERENCE LINKS MANDATORY**:
           - Extract FULL URLs from Google Search results
           - Include 1-3 most credible sources per section
           - Prefer: Government sites (IMD), major news outlets, Google Maps
           - Format: ["https://full-url.com/article", ...]
           - If no URL found: []
        
        3. **Weather Alerts**:
           - Only include alerts ACTIVE today
           - Must have valid_until date/time
           - Specify which activities are affected
           - If no alerts: []
        
        4. **Tourist Places**:
           - Verify status via Google Maps (check recent reviews)
           - Only include if there's confirmed closure/restriction TODAY
           - Suggest alternatives in same area/category
           - If all places open normally: []
        
        5. **Overall Status Logic**:
           - "UNSAFE": Extreme weather alert, severe conditions
           - "NOT_RECOMMENDED": Heavy rain/storm, major closures
           - "CAUTION": Light rain, minor issues, proceed with care
           - "SAFE": Good weather, no alerts, all places accessible
        
        6. **Data Freshness**:
           - Search for "today", "now", "current"
           - Ignore news older than today
           - Use real-time Google Search data
        
        Return ONLY valid JSON. NO markdown, NO extra text.
        """
        
        # Configure with Google Search grounding
        search_tool = types.Tool(google_search=types.GoogleSearch())
        
        config = types.GenerateContentConfig(
            tools=[search_tool],
            temperature=0.1,  # Low temperature for factual accuracy
            response_modalities=["TEXT"]
        )
        
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=intelligence_prompt,
            config=config
        )
        
        return parse_json_response(response.text)
        
    except Exception as e:
        return {"error": f"Failed to fetch weather intelligence: {str(e)}"}


# ==================== MAIN: Update Itinerary Based on Weather ====================
def update_itinerary_based_on_weather(trip_id: int) -> Dict[str, Any]:
    """
    Analyze current weather and update itinerary accordingly.
    Returns ONLY updated itinerary (no original itinerary).
    
    Args:
        trip_id: Trip ID from database
    
    Returns:
        Dictionary with weather intelligence and updated itinerary only
    """
    
    db = SessionLocal()
    
    try:
        print(f"🚀 Starting weather-based itinerary update for trip_id: {trip_id}")
        print("="*80)
        
        # STEP 1: Fetch trip and destination
        print("\n📋 STEP 1: Fetching trip details...")
        trip = db.query(Trip).filter(Trip.id == trip_id).first()
        
        if not trip:
            return {"error": f"No trip found for trip_id {trip_id}"}
        
        destination = trip.destination or trip.destination_full_name
        print(f"✅ Destination: {destination}")
        
        # STEP 2: Fetch original itinerary
        print("\n📅 STEP 2: Fetching original itinerary...")
        itinerary_entries = (
            db.query(Itinerary)
            .filter(Itinerary.trip_id == trip_id)
            .order_by(Itinerary.day.asc())
            .all()
        )
        
        if not itinerary_entries:
            return {"error": f"No itinerary found for trip_id {trip_id}"}
        
        # Build original itinerary structure
        original_itinerary = []
        all_places = []
        
        for entry in itinerary_entries:
            places = []
            for place in entry.places:
                place_data = {
                    "id": place.id,
                    "name": place.name,
                    "description": place.description,
                    "latitude": place.latitude,
                    "longitude": place.longitude,
                    "best_time_to_visit": place.best_time_to_visit
                }
                places.append(place_data)
                all_places.append(place.name)
            
            original_itinerary.append({
                "day": entry.day,
                "date": entry.date.strftime("%Y-%m-%d") if entry.date else None,
                "food": entry.food or [],
                "culture": entry.culture or [],
                "travel_tips": entry.travel_tips or [],
                "places": places
            })
        
        print(f"✅ Found {len(original_itinerary)} days with {len(all_places)} places")
        
        # STEP 3: Fetch current weather and travel intelligence via Google Search
        print(f"\n🌤️ STEP 3: Fetching current weather via Google Search...")
        weather_intelligence = fetch_weather_and_travel_intelligence(destination)
        
        if "error" in weather_intelligence:
            print(f"⚠️ Weather fetch error: {weather_intelligence['error']}")
            weather_intelligence = {
                "destination": destination,
                "overall_travel_status": "UNKNOWN",
                "current_weather": {},
                "weather_alerts": [],
                "tourist_place_alerts": []
            }
        else:
            status = weather_intelligence.get("overall_travel_status", "N/A")
            temp = weather_intelligence.get("current_weather", {}).get("temperature_c", "N/A")
            print(f"✅ Status: {status} | Temperature: {temp}°C")
        
        # STEP 4: AI Analysis and Itinerary Update
        print("\n🤖 STEP 4: AI analyzing impact and generating updated itinerary...")
        updated_itinerary = generate_updated_itinerary_with_ai(
            destination=destination,
            original_itinerary=original_itinerary,
            weather_intelligence=weather_intelligence
        )
        
        if "error" in updated_itinerary:
            return updated_itinerary
        
        print("✅ Updated itinerary generated")
        if updated_itinerary.get("changes_made"):
            print(f"   → Removed: {updated_itinerary.get('places_removed', 0)} places")
            print(f"   → Added: {updated_itinerary.get('places_added', 0)} alternatives")
        
        # STEP 5: Compile final result (NO ORIGINAL ITINERARY)
        print("\n" + "="*80)
        print("✅ ANALYSIS COMPLETE")
        print("="*80)
        
        result = {
            "trip_id": trip_id,
            "destination": destination,
            "analysis_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            
            "weather_intelligence": weather_intelligence,
            
            "updated_itinerary": updated_itinerary,
            
            "requires_update": updated_itinerary.get("changes_made", False)
        }
        
        return result
        
    except Exception as e:
        return {"error": f"Itinerary update failed: {str(e)}"}
    
    finally:
        db.close()


# ==================== AI: Generate Updated Itinerary ====================
def generate_updated_itinerary_with_ai(
    destination: str,
    original_itinerary: List[Dict],
    weather_intelligence: Dict
) -> Dict[str, Any]:
    """
    Use AI to analyze weather intelligence and update itinerary.
    
    Args:
        destination: Trip destination
        original_itinerary: Original day-wise itinerary
        weather_intelligence: Current weather and alerts data
    
    Returns:
        Updated itinerary with modifications, removals, and alternatives
    """
    
    try:
        update_prompt = f"""
        You are an expert travel planner with real-time weather intelligence.
        
        **DESTINATION:** {destination}
        
        **ORIGINAL ITINERARY:**
        {json.dumps(original_itinerary, indent=2)}
        
        **CURRENT WEATHER INTELLIGENCE:**
        {json.dumps(weather_intelligence, indent=2)}
        
        **YOUR TASK:**
        Analyze the current weather conditions and determine if the original itinerary needs modifications.
        
        **DECISION RULES:**
        
        1. **UNSAFE Status / Extreme Alerts** → 
           - REMOVE all outdoor activities
           - CANCEL water-based activities
           - Suggest only indoor alternatives
        
        2. **NOT_RECOMMENDED / Heavy Weather** → 
           - Remove risky outdoor activities (trekking, rafting, riverside areas)
           - Remove activities at locations in tourist_place_alerts
           - Keep covered temples, museums, indoor attractions
           - Add weather-specific tips
        
        3. **Tourist Place Alerts** → 
           - REMOVE places marked as Closed/Restricted
           - Use suggested alternatives from alerts
           - Find similar category replacements
        
        4. **CAUTION Status** → 
           - KEEP original plan
           - ADD weather precautions (umbrella, timing adjustments)
           - Modify visit timings based on today's forecast
        
        5. **SAFE Status** → 
           - Keep original itinerary unchanged
           - set changes_made = false
        
        **ALTERNATIVE SELECTION:**
        - Use Google Search to find alternatives in {destination}
        - Match categories: Temple→Temple, Museum→Museum, Nature→Park
        - Prioritize covered/indoor during bad weather
        - Only suggest REAL places (verify via search)
        
        **OUTPUT FORMAT (MAINTAIN EXACT STRUCTURE):**
        {{
          "changes_made": true/false,
          "overall_status": "SAFE/CAUTION/NOT_RECOMMENDED/UNSAFE",
          "total_days": {len(original_itinerary)},
          "places_removed": 0,
          "places_added": 0,
          
          "itinerary": [
              {{
                  "day": 1,
                  "date": "2025-11-25",
                  "status": "MODIFIED/UNCHANGED",
                  "weather_impact": "Heavy rainfall, outdoor activities unsafe",
                  
                  "food": ["Keep original or update"],
                  "culture": ["Keep original or update"],
                  "travel_tips": "Original tips + weather-specific additions",
                  
                  "places": [
                      {{
                          "id": 105,
                          "name": "Ramkund Panchwati",
                          "description": "Original description",
                          "latitude": "20.0080653",
                          "longitude": "73.7922971",
                          "best_time_to_visit": "Original timing",
                          
                          "weather_status": "NOT_RECOMMENDED",
                          "removed": true,
                          "removal_reason": "High water level, ghat area restricted",
                          "alternative_place": "Kalaram Temple",
                          "modifications": []
                      }},
                      {{
                          "id": 105,
                          "name": "Kalaram Temple",
                          "description": "Covered temple, safe during rain",
                          "latitude": "20.0064",
                          "longitude": "73.7898",
                          "best_time_to_visit": "10 AM - 6 PM",
                          
                          "weather_status": "SAFE",
                          "removed": false,
                          "removal_reason": null,
                          "alternative_place": null,
                          "is_alternative": true,
                          "replaces_place_id": 105,
                          "replaces_place_name": "Ramkund Panchwati",
                          "reason_for_replacement": "Original unsafe due to high water. Temple offers spiritual experience without weather risk.",
                          "modifications": []
                      }},
                      {{
                          "id": 106,
                          "name": "Coin Museum",
                          "description": "Original description",
                          "latitude": "20.xxxx",
                          "longitude": "73.xxxx",
                          "best_time_to_visit": "Original",
                          
                          "weather_status": "SAFE",
                          "removed": false,
                          "removal_reason": null,
                          "alternative_place": null,
                          "modifications": [
                              "Indoor activity, perfect for rainy day"
                          ]
                      }}
                  ],
                  
                  "removed_places": [
                      {{
                          "id": 105,
                          "name": "Ramkund Panchwati",
                          "removal_reason": "High water level, restricted access",
                          "weather_status": "NOT_RECOMMENDED",
                          "alternative_suggested": "Kalaram Temple",
                          "reference_links": []
                      }}
                  ]
              }}
          ],
          
          "rescheduled_activities": [
              {{
                  "place_name": "Ramkund Panchwati",
                  "original_day": 1,
                  "moved_to_day": 4,
                  "reason": "Weather expected to improve by Day 4"
              }}
          ]
        }}
        
        **CRITICAL RULES:**
        - Maintain EXACT original structure (id, name, description, lat, long, best_time_to_visit)
        - Add: weather_status, removed, removal_reason, alternative_place, modifications
        - **IMPORTANT**: Alternative places MUST keep the same ID as the removed place they replace
        - Example: If place with id=105 is removed, the alternative should also have id=105
        - Set: is_alternative=true, replaces_place_id=105, replaces_place_name="Original Name"
        - If SAFE and no issues: changes_made=false
        - Use tourist_place_alerts for specific closures
        - Count removed/added accurately
        - Include reference_links in removed_places when available
        
        **DO NOT INCLUDE:**
        - summary field
        - safety_recommendations field
        - packing_additions field
        
        Use Google Search to verify alternatives exist.
        Return ONLY valid JSON. NO markdown.
        """
        
        # Configure with Google Search
        search_tool = types.Tool(google_search=types.GoogleSearch())
        
        config = types.GenerateContentConfig(
            tools=[search_tool],
            temperature=0.2
        )
        
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=update_prompt,
            config=config
        )
        
        return parse_json_response(response.text)
        
    except Exception as e:
        return {"error": f"Failed to generate updated itinerary: {str(e)}"}


# ==================== HELPER: Parse JSON Response ====================
def parse_json_response(text: str) -> Dict[str, Any]:
    """Parse JSON from AI response, handling markdown and malformed responses."""
    
    if not text:
        return {"error": "Empty response"}
    
    # Remove markdown code blocks
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    text = text.strip()
    
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract first complete JSON object
        try:
            start_idx = text.find("{")
            if start_idx == -1:
                return {"error": "No JSON object found", "raw_text": text[:500]}
            
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


# ==================== EXAMPLE USAGE ====================
# if __name__ == "__main__":
#     # Test with trip_id
#     print("\n🧪 TESTING WEATHER-BASED ITINERARY UPDATE")
#     print("="*80)
    
#     result = update_itinerary_based_on_weather(trip_id=9)

#     print(result)
    
    # # Pretty print
    # print("\n" + "="*80)
    # print("📊 FINAL RESULT")
    # print("="*80)
    # print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # # Save to file
    # output_file = f"itinerary_update_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    # with open(output_file, "w", encoding="utf-8") as f:
    #     json.dump(result, f, indent=2, ensure_ascii=False)
    
    # print(f"\n✅ Result saved to: {output_file}")
    
    # # Print summary
    # if not result.get("error"):
    #     print("\n" + "="*80)
    #     print("📋 QUICK SUMMARY")
    #     print("="*80)
    #     print(f"Destination: {result['destination']}")
        
    #     weather = result['weather_intelligence']
    #     print(f"Weather Status: {weather.get('overall_travel_status', 'N/A')}")
        
    #     current = weather.get('current_weather', {})
    #     if current:
    #         print(f"Temperature: {current.get('temperature_c', 'N/A')}°C")
    #         print(f"Condition: {current.get('condition', 'N/A')}")
        
    #     print(f"\nChanges Required: {result['requires_update']}")
        
    #     if result['requires_update']:
    #         updated = result['updated_itinerary']
    #         print(f"Places Removed: {updated.get('places_removed', 0)}")
    #         print(f"Places Added: {updated.get('places_added', 0)}")