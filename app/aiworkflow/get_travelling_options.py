# ticket_search_agent_optimized.py
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
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


# ==================== VALIDATION HELPERS ====================

def get_bus_city_details(city_name: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Get bus city details from EaseMyTrip autosuggest API.
    Returns (city_id, city_name, state) or (None, None, None)
    """
    try:
        url = "https://autosuggest.easemytrip.com/api/auto/bus?useby=popularu&key=jNUYK0Yj5ibO6ZVIkfTiFA=="
        
        jsonString = {
            "userName": "",
            "password": "",
            "Prefix": city_name,
            "country_code": "IN"
        }
        RQ = {"request": EncryptionV1(json.dumps(jsonString))}
        jsonrequest = {
            "request": RQ["request"],
            "isIOS": False,
            "ip": "49.249.40.58",
            "encryptedHeader": "7ZTtohPgMEKTZQZk4/Cn1mpXnyNZDJIRcrdCFo5ahIk="
        }
        
        response = requests.post(url, json=jsonrequest, timeout=8)
        decrypted = decryptV1(response.text)
        data = json.loads(decrypted)
        
        bus_list = data.get("list")
        if bus_list and len(bus_list) > 0:
            city_data = bus_list[0]
            city_id = city_data.get("id")
            name = city_data.get("name")
            state = city_data.get("state", "")
            return city_id, name, state
        
        return None, None, None
        
    except Exception as e:
        print(f"⚠️ Error getting bus details for {city_name}: {e}")
        return None, None, None


def validate_bus_availability(from_city: str, to_city: str) -> dict:
    """Validate if bus route exists by checking if both cities are in bus network."""
    
    src_id, src_name, src_state = get_bus_city_details(from_city)
    dest_id, dest_name, dest_state = get_bus_city_details(to_city)
    
    print(f"🔍 Bus validation: {from_city} -> {to_city}")
    print(f"   Source: id={src_id}, name={src_name}, state={src_state}")
    print(f"   Dest: id={dest_id}, name={dest_name}, state={dest_state}")
    
    if src_id is None or dest_id is None:
        return {
            "available": False,
            "from_city": from_city,
            "to_city": to_city,
            "reason": f"City not in bus network (src={src_id is not None}, dest={dest_id is not None})"
        }
    
    return {
        "available": True,
        "from_city": from_city,
        "to_city": to_city,
        "src_id": src_id,
        "dest_id": dest_id,
        "src_name": src_name,
        "dest_name": dest_name,
        "dest_state": dest_state
    }


def get_train_station_code(city_name: str) -> Tuple[Optional[str], Optional[str]]:
    """Fetch train station code. Returns (station_code, station_name) or (None, None)"""
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
    """Fetch airport code. Returns (airport_code, city_name) or (None, None)"""
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


# ==================== BOOKING URL GENERATORS ====================

def build_easemytrip_flight_url(
    from_code: str, from_city: str, to_code: str, to_city: str, journey_date: str
) -> str:
    """Build EaseMyTrip flight booking URL"""
    from urllib.parse import urlencode
    
    date_obj = datetime.strptime(journey_date, "%Y-%m-%d")
    formatted_date = date_obj.strftime("%d/%m/%Y")
    
    srch = f"{from_code}-{from_city}-India|{to_code}-{to_city}-India|{formatted_date}"
    
    params = {
        "srch": srch,
        "px": "1-0-0",
        "cbn": "0",
        "ar": "undefined",
        "isow": "true",
        "isdm": "false",
        "lang": "en-us",
        "IsDoubleSeat": "false",
        "CCODE": "IN",
        "curr": "INR",
        "apptype": "B2C"
    }
    
    return f"https://flight.easemytrip.com/FlightList/Index?{urlencode(params, safe='-|/')}"


def build_easemytrip_train_url(
    from_code: str, from_name: str, to_code: str, to_name: str, journey_date: str
) -> str:
    """Build EaseMyTrip train booking URL"""
    date_obj = datetime.strptime(journey_date, "%Y-%m-%d")
    formatted_date = date_obj.strftime("%d-%m-%Y")
    
    from_name_clean = from_name.replace(" ", "")
    to_name_clean = to_name.replace(" ", "")
    
    return f"https://railways.easemytrip.com/TrainListInfo/{from_name_clean}({from_code})-to-{to_name_clean}({to_code})/2/{formatted_date}"


def build_easemytrip_bus_url(
    from_city: str, to_city: str, journey_date: str
) -> str:
    """Build EaseMyTrip bus booking URL with proper city IDs and state"""
    from urllib.parse import urlencode
    
    date_obj = datetime.strptime(journey_date, "%Y-%m-%d")
    formatted_date = date_obj.strftime("%d-%m-%Y")
    
    # Get city details
    src_id, src_name, src_state = get_bus_city_details(from_city)
    dest_id, dest_name, dest_state = get_bus_city_details(to_city)
    
    # Build destination with state
    if dest_state:
        destination = f"{dest_name},{dest_state}"
    else:
        destination = dest_name if dest_name else to_city
    
    # Build searchid
    if src_id and dest_id:
        search_id = f"{src_id}_{dest_id}"
    else:
        import random
        search_id = f"{random.randint(10000, 99999)}_{random.randint(10000, 99999)}"
    
    params = {
        "org": src_name if src_name else from_city,
        "des": destination,
        "date": formatted_date,
        "searchid": search_id,
        "CCode": "IN",
        "AppCode": "Emt"
    }
    
    return f"https://bus.easemytrip.com/home/list?{urlencode(params)}"


# ==================== MAIN SEARCH FUNCTION (NO AGENT) ====================

def search_travel_tickets(input_json: Dict) -> Dict:
    """
    Generate travel options using direct Gemini API (no agent framework).
    Validates all routes after generation.
    """
    
    # Initialize Gemini
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-exp",
        temperature=0.3,
        google_api_key=GEMINI_API_KEY
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a travel planning assistant. Create EXACTLY 2 travel route options.

CRITICAL RULES:
- Return ONLY valid JSON, no markdown, no explanations
- For buses: from_code and to_code must be empty strings ""
- For trains: use station codes (NGP, NDLS, etc.)
- For flights: use airport codes (NAG, DEL, etc.)

OUTPUT FORMAT:
{{
  "travelling_options": [
    {{
      "option_name": "Fastest Route",
      "legs": [
        {{
          "from": "City A",
          "to": "City B",
          "mode": "Flight/Train/Bus",
          "from_code": "CODE or empty string",
          "to_code": "CODE or empty string",
          "approx_time": "X hours",
          "approx_cost": "INR X - INR Y",
          "journey_date": "YYYY-MM-DD"
        }}
      ]
    }},
    {{
      "option_name": "Cost Effective Route",
      "legs": [...]
    }}
  ]
}}"""),
        ("human", """Plan travel from {base_location} to {destination}, starting {journey_start_date}.

Create:
1. Fastest Route (flights/express trains preferred)
2. Cost Effective Route (trains/buses preferred)

Return ONLY the JSON object.""")
    ])
    
    try:
        print("🤖 Generating initial travel routes...")
        
        chain = prompt | llm
        response = chain.invoke({
            "journey_start_date": input_json["journey_start_date"],
            "base_location": input_json["base_location"],
            "destination": input_json["destination"]
        })
        
        output_text = response.content.strip()
        
        # Clean response
        if output_text.startswith("```"):
            lines = output_text.split("\n")
            output_text = "\n".join(lines[1:-1]) if len(lines) > 2 else output_text
            if output_text.startswith("json"):
                output_text = output_text[4:].strip()
        
        result = json.loads(output_text)
        
        # Validate and fix each leg
        print("\n✅ Validating and fixing routes...")
        
        for option in result.get("travelling_options", []):
            for leg in option.get("legs", []):
                mode = leg.get("mode", "").lower()
                from_city = leg.get("from", "")
                to_city = leg.get("to", "")
                
                if mode == "bus":
                    # Validate bus route
                    bus_check = validate_bus_availability(from_city, to_city)
                    
                    if not bus_check["available"]:
                        # Try nearby city alternatives
                        alternatives = {
                            "Mussoorie": ["Dehradun"],
                            "Rishikesh": ["Haridwar"]
                        }
                        
                        tried_alternative = False
                        if to_city in alternatives:
                            for alt_city in alternatives[to_city]:
                                alt_check = validate_bus_availability(from_city, alt_city)
                                if alt_check["available"]:
                                    print(f"   ✅ Using alternate city: {alt_city} instead of {to_city}")
                                    leg["to"] = alt_city
                                    tried_alternative = True
                                    break
                        
                        if not tried_alternative:
                            # Switch to Cab
                            print(f"   🚕 Switching to Cab: {from_city} -> {to_city}")
                            leg["mode"] = "Cab"
                            leg["from_code"] = ""
                            leg["to_code"] = ""
                            leg["approx_cost"] = "INR 1500 - INR 3500"
                            leg["approx_time"] = leg.get("approx_time", "Depends on distance")
                            leg["booking_url"] = ""
                            continue
                    
                    # Bus available - set empty codes
                    leg["from_code"] = ""
                    leg["to_code"] = ""
                    
                elif mode == "train":
                    # Get train codes
                    from_code, from_name = get_train_station_code(from_city)
                    to_code, to_name = get_train_station_code(to_city)
                    
                    if from_code:
                        leg["from_code"] = from_code
                    if to_code:
                        leg["to_code"] = to_code
                    
                elif mode == "flight":
                    # Get airport codes
                    from_code, _ = get_airport_code(from_city)
                    to_code, _ = get_airport_code(to_city)
                    
                    if from_code:
                        leg["from_code"] = from_code
                    if to_code:
                        leg["to_code"] = to_code
                
                # Generate booking URL
                booking_url = None
                if mode == "flight" and leg.get("from_code") and leg.get("to_code"):
                    booking_url = build_easemytrip_flight_url(
                        leg["from_code"], from_city, leg["to_code"], to_city, leg["journey_date"]
                    )
                elif mode == "train" and leg.get("from_code") and leg.get("to_code"):
                    booking_url = build_easemytrip_train_url(
                        leg["from_code"], from_city, leg["to_code"], to_city, leg["journey_date"]
                    )
                elif mode == "bus":
                    booking_url = build_easemytrip_bus_url(from_city, to_city, leg["journey_date"])
                
                leg["booking_url"] = booking_url if booking_url else ""
        
        print("✅ All routes validated and URLs generated!\n")
        return result
        
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
    import warnings
    warnings.filterwarnings('ignore', category=UserWarning)
    
    input_json = {
        "journey_start_date": "2025-11-10",
        "journey_end_date": "2025-11-15",
        "base_location": "Nagpur",
        "destination": "Rishikesh"
    }

    result = search_travel_tickets(input_json)
    print("="*70)
    print("=== FINAL TRAVEL OPTIONS ===")
    print("="*70)
    print(json.dumps(result, indent=2))