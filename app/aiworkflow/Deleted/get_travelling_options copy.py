# ticket_search_agent.py
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from dotenv import load_dotenv
import os

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

encKey = "EDMEMT1234"
decKey = "TMTOO1vDhT9aWsV1"


def EncryptionV1(plaintext: str) -> str:
    """Encrypt payload for EaseMyTrip APIs (AES-CBC)."""
    key = decKey.encode("utf-8")
    iv = decKey.encode("utf-8")
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded = pad(plaintext.encode("utf-8"), AES.block_size)
    encrypted = cipher.encrypt(padded)
    return base64.b64encode(encrypted).decode("utf-8")


def decryptV1(ciphertext: str) -> str:
    """Decrypt EaseMyTrip API responses."""
    key = decKey.encode("utf-8")
    iv = decKey.encode("utf-8")
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = cipher.decrypt(base64.b64decode(ciphertext))
    return unpad(decrypted, AES.block_size).decode("utf-8")

# ==================== EASEMYTRIP API HELPERS ====================

def source_auto_suggest(place_name: str) -> Dict:
    """Call EaseMyTrip's encrypted bus auto-suggest API to verify bus availability."""
    url = "https://autosuggest.easemytrip.com/api/auto/bus?useby=popularu&key=jNUYK0Yj5ibO6ZVIkfTiFA=="
    jsonString = {
        "userName": "",
        "password": "",
        "Prefix": place_name,
        "country_code": "IN"
    }
    RQ = {"request": EncryptionV1(json.dumps(jsonString))}
    jsonrequest = {
        "request": RQ["request"],
        "isIOS": False,
        "ip": "49.249.40.58",
        "encryptedHeader": "7ZTtohPgMEKTZQZk4/Cn1mpXnyNZDJIRcrdCFo5ahIk="
    }

    try:
        response = requests.post(url, json=jsonrequest, timeout=8)
        decrypted = decryptV1(response.text)
        data = json.loads(decrypted)
        return data
    except Exception as e:
        print(f"⚠️ Bus suggest error for {place_name}: {e}")
        return {"list": None, "type": ""}


def validate_bus_availability(from_city: str, to_city: str) -> bool:
    """
    Check if a bus route exists between from_city and to_city.
    Returns True if available, otherwise False.
    """
    src = source_auto_suggest(from_city)
    dest = source_auto_suggest(to_city)

    # If either list is None or empty, buses not available
    if not src.get("list") or not dest.get("list"):
        print(f"🚌 No buses found between {from_city} and {to_city}. Switching to cab option.")
        return False
    return True



def get_train_station_code(city_name: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Fetch train station code from EaseMyTrip API.
    Returns (station_code, station_name) or (None, None)
    """
    try:
        url = f"https://solr.easemytrip.com/v1/api/auto/GetTrainAutoSuggest/{city_name.lower()}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                station = data[0]
                return station.get("Code"), station.get("Name")
        return None, None
    except Exception as e:
        print(f"⚠️ Error fetching train code for {city_name}: {e}")
        return None, None


def get_airport_code(city_name: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Fetch airport code from EaseMyTrip API.
    Returns (airport_code, city_name) or (None, None)
    """
    try:
        url = "https://www.easemytrip.com/api/Flight/GetAutoSuggestNew"
        payload = {"Prefix": city_name.lower()}
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                india_airports = [a for a in data if a.get("Country") == "India"]
                airport = india_airports[0] if india_airports else data[0]
                city_field = airport.get("City", "")
                if "(" in city_field and ")" in city_field:
                    code = city_field.split("(")[1].split(")")[0]
                    return code, airport.get("CityName")
        return None, None
    except Exception as e:
        print(f"⚠️ Error fetching airport code for {city_name}: {e}")
        return None, None


def validate_and_correct_codes(travel_leg: dict) -> dict:
    """
    Validate and auto-correct airport/station codes using EaseMyTrip APIs.
    Added logic for buses → if bus route unavailable, mode becomes 'Cab'.
    """
    mode = travel_leg.get("mode", "").lower()
    from_city = travel_leg.get("from", "")
    to_city = travel_leg.get("to", "")

    if mode == "bus":
        available = validate_bus_availability(from_city, to_city)
        if not available:
            travel_leg["mode"] = "Cab"  # 🚕 Replace Bus with Cab
            travel_leg["from_code"] = ""
            travel_leg["to_code"] = ""
            travel_leg["approx_cost"] = "INR 1000 - INR 3000"
            travel_leg["approx_time"] = travel_leg.get("approx_time", "Depends on distance")
            travel_leg["booking_url"] = ""  # No EaseMyTrip URL for cabs
        return travel_leg

    # --- existing flight/train validation logic below ---
    if mode == "flight":
        from_code = travel_leg.get("from_code", "")
        to_code = travel_leg.get("to_code", "")
        if not from_code or len(from_code) > 3:
            code, _ = get_airport_code(from_city)
            if code:
                travel_leg["from_code"] = code
        if not to_code or len(to_code) > 3:
            code, _ = get_airport_code(to_city)
            if code:
                travel_leg["to_code"] = code

    elif mode == "train":
        from_code = travel_leg.get("from_code", "")
        to_code = travel_leg.get("to_code", "")
        if not from_code:
            code, _ = get_train_station_code(from_city)
            if code:
                travel_leg["from_code"] = code
        if not to_code:
            code, _ = get_train_station_code(to_city)
            if code:
                travel_leg["to_code"] = code

    return travel_leg
# ==================== BOOKING URL GENERATORS ====================

def build_easemytrip_flight_url(
    from_code: str,
    from_city: str,
    to_code: str,
    to_city: str,
    journey_date: str,  # YYYY-MM-DD format
    adults: int = 1,
    children: int = 0,
    infants: int = 0,
    cabin_class: str = "Economy",
    one_way: bool = True,
    direct_only: bool = False,
    country: str = "India"
) -> str:
    """Build EaseMyTrip flight booking URL"""
    from urllib.parse import urlencode
    
    # Convert date format: YYYY-MM-DD -> DD/MM/YYYY
    date_obj = datetime.strptime(journey_date, "%Y-%m-%d")
    formatted_date = date_obj.strftime("%d/%m/%Y")
    
    # Build search string
    srch = f"{from_code}-{from_city}-{country}|{to_code}-{to_city}-{country}|{formatted_date}"
    px = f"{adults}-{children}-{infants}"
    
    cabin_map = {"Economy": 0, "Premium Economy": 1, "Business": 2, "First": 3}
    cbn = cabin_map.get(cabin_class, 0)
    
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
    """Build EaseMyTrip train booking URL"""
    
    # Convert date format: YYYY-MM-DD -> DD-MM-YYYY
    date_obj = datetime.strptime(journey_date, "%Y-%m-%d")
    formatted_date = date_obj.strftime("%d-%m-%Y")
    
    # Remove spaces from city names
    from_name_clean = from_name.replace(" ", "")
    to_name_clean = to_name.replace(" ", "")
    
    # Build URL format: /TrainListInfo/FromCity(CODE)-to-ToCity(CODE)/2/DD-MM-YYYY
    url = f"https://railways.easemytrip.com/TrainListInfo/{from_name_clean}({from_code})-to-{to_name_clean}({to_code})/2/{formatted_date}"
    
    return url


def build_easemytrip_bus_url(
    from_city: str,
    to_city: str,
    journey_date: str  # YYYY-MM-DD format
) -> str:
    """
    Build EaseMyTrip bus booking URL
    
    Args:
        from_city: Origin city name (e.g., "Guwahati")
        to_city: Destination city name (e.g., "Shillong")
        journey_date: Date in YYYY-MM-DD format
    
    Returns:
        Complete EaseMyTrip bus booking URL
        
    Example:
        https://bus.easemytrip.com/home/list?org=Guwahati&des=Shillong&date=24-10-2025&searchid=74701_92578&CCode=IN&AppCode=Emt
    """
    from urllib.parse import urlencode
    import random
    
    # Convert date format: YYYY-MM-DD -> DD-MM-YYYY
    date_obj = datetime.strptime(journey_date, "%Y-%m-%d")
    formatted_date = date_obj.strftime("%d-%m-%Y")
    
    # Generate random searchid (format: 5digits_5digits)
    search_id = f"{random.randint(10000, 99999)}_{random.randint(10000, 99999)}"
    
    # Build query parameters
    params = {
        "org": from_city,
        "des": to_city,
        "date": formatted_date,
        "searchid": search_id,
        "CCode": "IN",
        "AppCode": "Emt"
    }
    
    base_url = "https://bus.easemytrip.com/home/list"
    query_string = urlencode(params)
    
    return f"{base_url}?{query_string}"


def generate_booking_url(travel_leg: dict) -> Optional[str]:
    """Generate booking URL from travel leg data"""
    
    try:
        mode = travel_leg.get("mode", "").lower()
        
        if mode == "flight":
            if not travel_leg.get("from_code") or not travel_leg.get("to_code"):
                return None
            return build_easemytrip_flight_url(
                from_code=travel_leg["from_code"],
                from_city=travel_leg["from"],
                to_code=travel_leg["to_code"],
                to_city=travel_leg["to"],
                journey_date=travel_leg["journey_date"]
            )
        
        elif mode == "train":
            if not travel_leg.get("from_code") or not travel_leg.get("to_code"):
                return None
            return build_easemytrip_train_url(
                from_code=travel_leg["from_code"],
                from_name=travel_leg["from"],
                to_code=travel_leg["to_code"],
                to_name=travel_leg["to"],
                journey_date=travel_leg["journey_date"]
            )
        
        elif mode == "bus":
            # Bus booking URL - no codes needed, just city names
            return build_easemytrip_bus_url(
                from_city=travel_leg["from"],
                to_city=travel_leg["to"],
                journey_date=travel_leg["journey_date"]
            )
        
        elif mode == "ferry":
            # Ferry booking URLs are platform-specific
            # You can add specific ferry booking platforms here
            return None
        
        return None
        
    except Exception as e:
        print(f"Error generating booking URL: {str(e)}")
        return None


# ==================== MAIN SEARCH FUNCTION ====================

def search_travel_tickets(input_json: Dict) -> Dict:
    """
    Generate multiple travel options between base_location and destination using Gemini's search.

    Args:
        {
            "journey_start_date": "YYYY-MM-DD",
            "journey_end_date": "YYYY-MM-DD",
            "base_location": "City",
            "destination": "City"
        }

    Returns:
        {
            "travelling_options": [
                {
                    "option_name": "Fastest Route",
                    "legs": [
                        {
                            "from": "City A",
                            "to": "City B",
                            "mode": "Flight",
                            "from_code": "CODE",
                            "to_code": "CODE",
                            "approx_time": "2 hours",
                            "approx_cost": "INR 3000 - INR 6000",
                            "journey_date": "2025-11-10",
                            "booking_url": "https://..."
                        }
                    ]
                }
            ]
        }
    """

    # Initialize Gemini with search grounding enabled
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-exp",
        temperature=0.3,
        google_api_key=GEMINI_API_KEY,
        model_kwargs={
            "tools": [{"google_search_retrieval": {}}]
        }
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a travel planning assistant that creates comprehensive multi-route travel plans.

Use Google Search to find real-time information about:
- Flight routes, airport codes, and approximate prices
- Train routes, station codes, and approximate prices  
- Bus routes and approximate prices
- Ferry/boat routes for coastal/island destinations
- Travel times and distances

TASK: Create EXACTLY 2 travel route options:
1. "Fastest Route" - prioritize speed (flights/express trains preferred)
2. "Cost Effective Route" - prioritize budget (trains/buses/ferries preferred)

ROUTING LOGIC:
- Search for direct routes first (flights, trains, buses, ferries)
- For coastal/island destinations (like Alibaug, Goa, Andaman), consider ferry/boat options
- If no direct options exist, create multi-leg journey via major hub city
- For multi-leg journeys: 2nd leg date = 1st leg date + 1 day

MANDATORY FIELDS for each leg:
- from: string (city name)
- to: string (city name)
- mode: "Flight" | "Train" | "Bus" | "Ferry"
- from_code: string (station code for trains, airport code for flights, port name for ferries, empty string "" for buses)
- to_code: string (station code for trains, airport code for flights, port name for ferries, empty string "" for buses)
- approx_time: string (e.g., "2 hours", "16 hours")
- approx_cost: string (format: "INR 1000 - INR 2000", NO rupee symbols)
- journey_date: string (YYYY-MM-DD format)

EXAMPLES:

Flight leg:
{{
  "from": "Mumbai",
  "to": "Delhi",
  "mode": "Flight",
  "from_code": "BOM",
  "to_code": "DEL",
  "approx_time": "2 hours 15 minutes",
  "approx_cost": "INR 3500 - INR 8000",
  "journey_date": "2025-11-10"
}}

Train leg:
{{
  "from": "Nagpur",
  "to": "Mumbai",
  "mode": "Train",
  "from_code": "NGP",
  "to_code": "CSMT",
  "approx_time": "14 hours",
  "approx_cost": "INR 800 - INR 2500",
  "journey_date": "2025-11-10"
}}

Ferry leg:
{{
  "from": "Mumbai",
  "to": "Alibaug",
  "mode": "Ferry",
  "from_code": "Gateway of India",
  "to_code": "Mandwa Jetty",
  "approx_time": "1 hour",
  "approx_cost": "INR 200 - INR 500",
  "journey_date": "2025-11-11"
}}

Bus leg:
{{
  "from": "Mandwa",
  "to": "Alibaug",
  "mode": "Bus",
  "from_code": "",
  "to_code": "",
  "approx_time": "30 minutes",
  "approx_cost": "INR 50 - INR 100",
  "journey_date": "2025-11-11"
}}

OUTPUT FORMAT (strict JSON):
{{
  "travelling_options": [
    {{
      "option_name": "Fastest Route",
      "legs": [...]
    }},
    {{
      "option_name": "Cost Effective Route",
      "legs": [...]
    }}
  ]
}}

CRITICAL RULES FOR CODES:
- **FLIGHTS**: Use IATA airport codes (3 letters)
  Examples: NAG (Nagpur Airport), BOM (Mumbai), DEL (Delhi), CCU (Kolkata), IXZ (Port Blair), SHL (Shillong)
  IMPORTANT: NAG is for flights, NGP is for trains - DO NOT MIX THEM UP!
  
- **TRAINS**: Use Indian Railway station codes (3-5 letters)
  Examples: NGP (Nagpur Junction), CSMT (Mumbai CST), NDLS (New Delhi), HWH (Howrah Kolkata)
  
- **FERRIES**: Use jetty/port names as strings
  Examples: "Gateway of India", "Mandwa Jetty", "Port Blair Jetty"
  
- **BUSES**: Use empty string "" for both from_code and to_code

**VERIFY BEFORE RESPONDING:**
- Double-check airport codes vs train station codes
- Nagpur: NAG (flight) vs NGP (train)
- Mumbai: BOM (flight) vs CSMT/LTT (train)
- Delhi: DEL (flight) vs NDLS/NZM (train)
- Kolkata: CCU (flight) vs HWH/SDAH (train)

Return ONLY the JSON object, no markdown formatting or explanations."""),
        ("human", """Plan travel routes for:

Journey Start Date: {journey_start_date}
Journey End Date: {journey_end_date}
From: {base_location}
To: {destination}

Search for current travel options and create 2 complete routes (Fastest and Cost Effective).
Consider ferry/boat options if the destination is coastal or island-based.""")
    ])

    try:
        chain = prompt | llm
        
        response = chain.invoke({
            "journey_start_date": input_json["journey_start_date"],
            "journey_end_date": input_json["journey_end_date"],
            "base_location": input_json["base_location"],
            "destination": input_json["destination"]
        })
        
        output_text = response.content.strip()
        
        # Remove markdown code fences if present
        if output_text.startswith("```"):
            lines = output_text.split("\n")
            output_text = "\n".join(lines[1:-1]) if len(lines) > 2 else output_text
            if output_text.startswith("json"):
                output_text = output_text[4:].strip()
        
        # Parse JSON
        result = json.loads(output_text)
        
        # Validate structure
        if "travelling_options" in result and len(result["travelling_options"]) >= 1:
            # Validate and correct codes, then add booking URLs to each leg
            for option in result["travelling_options"]:
                for leg in option.get("legs", []):
                    # Validate and auto-correct codes
                    leg = validate_and_correct_codes(leg)
                    
                    # Generate booking URL
                    booking_url = generate_booking_url(leg)
                    leg["booking_url"] = booking_url if booking_url else ""
            
            return result
        else:
            return {
                "travelling_options": [],
                "error": "Invalid response structure from AI",
                "raw_output": output_text[:500]
            }
            
    except json.JSONDecodeError as e:
        return {
            "travelling_options": [],
            "error": f"JSON parsing failed: {str(e)}",
            "raw_output": output_text[:500] if 'output_text' in locals() else ""
        }
    except Exception as e:
        return {
            "travelling_options": [],
            "error": f"Request failed: {str(e)}"
        }


      




if __name__ == "__main__":
    # Suppress ALTS warning (Google Cloud internal warning - safe to ignore)
    import warnings
    warnings.filterwarnings('ignore', category=UserWarning)
    
    input_json = {
        "journey_start_date": "2025-11-10",
        "journey_end_date": "2025-11-15",
        "base_location": "Nagpur",
        "destination": "Mussorie"
    }

    result = search_travel_tickets(input_json)
    print("\n=== TRAVEL OPTIONS RESULT ===")
    print(json.dumps(result, indent=2))