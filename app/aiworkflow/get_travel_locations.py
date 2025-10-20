# tourist_places_agent.py
from __future__ import annotations
import json
import re
import requests
import os
from datetime import datetime
from typing import Dict, List
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize Gemini model
llm = ChatGoogleGenerativeAI(
    model="models/gemini-2.0-flash",
    temperature=0.3,
    google_api_key=GEMINI_API_KEY
)


# ------------------ Helper Function ------------------
def fetch_places_from_api(destination: str, refresh: bool = False) -> Dict:
    """
    Fetch raw tourist places data from the /places API.
    """
    try:
        url = f"http://127.0.0.1:8002/places?destination={destination}&refresh={str(refresh).lower()}"
        response = requests.get(url, timeout=(10, 300))
        if response.status_code != 200:
            return {"error": f"Failed to fetch places ({response.status_code})"}

        return response.json()
    except Exception as e:
        return {"error": str(e)}


# ------------------ Main Function ------------------
def get_tourist_places_for_destination(destination: str, activity: List, limit: int = 15) -> Dict:
    """
    Fetch and enrich tourist places data for a given destination using Gemini.
    Returns structured JSON with enriched tourist place information.

    Args:
        destination: Name of the city/destination
        activity: Type of activity (e.g., "adventure", "general", "cultural", "religious")
        limit: Maximum number of places to return (default: 15)
    """
    try:
        # Step 1: Fetch raw data from API
        print(f"🔍 Fetching tourist places for: {destination}")
        api_response = fetch_places_from_api(destination, refresh=False)

        if "error" in api_response:
            return api_response

        # Extract the actual tourist places data
        # Handle both direct list and nested structure
        if isinstance(api_response, list) and len(api_response) > 0:
            api_data = api_response[0].get("output", {})
        else:
            api_data = api_response

        tourist_places = api_data.get("TouristPlaces", [])
        corrected_destination = api_data.get("CorrectedDestination", destination)

        if not tourist_places:
            return {"error": "No tourist places found in API response"}

        print(f"📊 Found {len(tourist_places)} places, selecting top {limit}")

        # Step 2: Filter and select top places
        # Prioritize places with descriptions and images
        scored_places = []
        for place in tourist_places:
            score = 0
            if place.get("Description"):
                score += 2
            if place.get("ImageURL"):
                score += 1
            if place.get("GeoCoordinates", {}).get("lat"):
                score += 1
            scored_places.append((score, place))
        
        # Sort by score and take top N
        scored_places.sort(reverse=True, key=lambda x: x[0])
        selected_places = [p[1] for p in scored_places[:limit]]

        # Step 3: Prepare enrichment prompt
        today = datetime.now().strftime("%B %d, %Y")
        
        query = f"""
You are a travel content expert. I have tourist places data for {corrected_destination}.

Raw data for selected places:
{json.dumps(selected_places, ensure_ascii=False, indent=2)}

Activity preference: {activity}

Your task:
1. For places WITHOUT descriptions (Description is null), write engaging 2-3 sentence descriptions highlighting what makes them special
2. For places WITH descriptions, keep them EXACTLY as provided - DO NOT modify
3. NEVER modify or update ImageURL - keep exactly as provided (even if null)
4. Keep all existing GeoCoordinates and Google_web_url EXACTLY unchanged
5. If activity is "{activity}", emphasize relevant aspects in NEW descriptions only

Output Format - Return ONLY valid JSON (no markdown, no code blocks):
{{
  "Destination": "{corrected_destination}",
  "ActivityType": "{activity}",
  "TotalPlaces": {limit},
  "TouristPlaces": [
    {{
      "Name": "string (exact copy)",
      "Description": "string (write new ONLY if original was null)",
      "GeoCoordinates": {{
        "lat": number (exact copy),
        "lng": number (exact copy)
      }},
      "ImageURL": "string or null (EXACT copy - NEVER change this)",
      "Google_web_url": "string (exact copy)"
    }}
  ]
}}

CRITICAL RULES:
- NEVER update ImageURL - copy exactly as is (even if null)
- NEVER modify existing descriptions - only add where Description is null
- Keep all place names exactly as provided
- Maintain all GeoCoordinates exactly
- Preserve all Google_web_url links exactly
- Only write NEW descriptions for places where Description field is null
- Return pure JSON only, no explanations
"""

        # Step 4: Invoke LLM
        print("🤖 Enriching data with Gemini...")
        response = llm.invoke(query)

        # Step 5: Parse LLM response
        try:
            # Remove markdown code blocks if present
            content = response.content.strip()
            
            # Try to extract JSON from markdown blocks
            if "```json" in content:
                match = re.search(r"```json\s*(\{.*?\})\s*```", content, re.DOTALL)
                if match:
                    content = match.group(1)
            elif "```" in content:
                match = re.search(r"```\s*(\{.*?\})\s*```", content, re.DOTALL)
                if match:
                    content = match.group(1)
            
            # Try direct JSON parse
            structured_output = json.loads(content)
            
            print(f"✅ Successfully enriched {len(structured_output.get('TouristPlaces', []))} places")
            return structured_output
            
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON parsing failed: {e}")
            # Try to extract JSON using regex as fallback
            match = re.search(r"\{.*\}", response.content, re.DOTALL)
            if match:
                try:
                    structured_output = json.loads(match.group(0))
                    return structured_output
                except:
                    pass
            
            return {
                "error": "Model did not return valid JSON.",
                "raw_response": response.content[:500]  # First 500 chars for debugging
            }

    except Exception as e:
        return {"error": str(e)}









# # ------------------ Example Run ------------------
# if __name__ == "__main__":
#     # Test with different activities
#     result = get_tourist_places_ai(
#         destination="rishikesh", 
#         activity="religious",
#         limit=10
#     )
    
#     print("\n" + "="*80)
#     print("📍 ENRICHED TOURIST PLACES")
#     print("="*80)
#     print(json.dumps(result, indent=2, ensure_ascii=False))
    
#     # Save to file
#     with open("enriched_places.json", "w", encoding="utf-8") as f:
#         json.dump(result, f, indent=2, ensure_ascii=False)
#     print("\n💾 Saved to enriched_places.json")