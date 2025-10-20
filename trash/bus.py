
import requests
import json
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64
from datetime import datetime

BASE_URL = "https://bus.easemytrip.com/"
SERVICE_URL = "https://busservice.easemytrip.com/v1/api"

# --- AES Encryption/Decryption ---
encKey = "EDMEMT1234"
decKey = "TMTOO1vDhT9aWsV1"

def EncryptionV1(plaintext):
    key = decKey.encode('utf-8')
    iv = decKey.encode('utf-8')
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded = pad(plaintext.encode('utf-8'), AES.block_size)
    encrypted = cipher.encrypt(padded)
    return base64.b64encode(encrypted).decode('utf-8')

def decryptV1(ciphertext):
    key = decKey.encode('utf-8')
    iv = decKey.encode('utf-8')
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = cipher.decrypt(base64.b64decode(ciphertext))
    return unpad(decrypted, AES.block_size).decode('utf-8')

# --- API Functions ---
def source_auto_suggest(place_name):
    """
    Get city suggestions based on place name
    Returns the first matching city details
    """
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
        response = requests.post(url, json=jsonrequest, timeout=10)
        decrypted = decryptV1(response.text)
        result = json.loads(decrypted)
        
        # Return the first city-type result (not area)
        if result.get('list') and len(result['list']) > 0:
            for item in result['list']:
                if item.get('type') == 'city':
                    return {
                        'id': item['id'],
                        'name': item['name'],
                        'state': item.get('state', ''),
                        'full_data': item
                    }
            # If no city type found, return first item
            first_item = result['list'][0]
            return {
                'id': first_item['id'],
                'name': first_item['name'],
                'state': first_item.get('state', ''),
                'full_data': first_item
            }
        return None
    except Exception as e:
        print(f"Error in source_auto_suggest: {e}")
        return None

def get_bus_search_results(
    source_city_id,
    destination_city_id,
    source_city_name,
    destination_city_name,
    journey_date,
    vid="da20a2d09e9611f09fd55d45d3936493",
    sid="da2096a09e9611f0a091e1af1f28887f",
    agent_code="NAN",
    agent_type="NAN",
    currency_domain="IN",
    snap_app="Emt",
    is_inventory=0,
    travel_policy=None
):
    """
    Search for buses between source and destination
    """
    url = "https://busservice.easemytrip.com/v1/api/Home/GetSearchResult/"

    headers = {
        "Content-Type": "application/json",
        "Origin": "https://bus.easemytrip.com",
        "Referer": "https://bus.easemytrip.com/",
        "User-Agent": "Mozilla/5.0"
    }

    payload = {
        "SourceCityId": source_city_id,
        "DestinationCityId": destination_city_id,
        "SourceCityName": source_city_name,
        "DestinatinCityName": destination_city_name,
        "JournyDate": journey_date,
        "Vid": vid,
        "agentCode": agent_code,
        "agentType": agent_type,
        "CurrencyDomain": currency_domain,
        "Sid": sid,
        "snapApp": snap_app,
        "TravelPolicy": travel_policy if travel_policy else [],
        "isInventory": is_inventory
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()

        result = response.json()
        
        # Save to file
        with open("bus_search_results.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        return result
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return None

# --- Main Search Function ---
def search_buses(from_city, to_city, journey_date=None):
    """
    Main function to search buses
    
    Args:
        from_city: Source city name (e.g., "Pune")
        to_city: Destination city name (e.g., "Nagpur")
        journey_date: Date in DD-MM-YYYY format (default: tomorrow)
    
    Returns:
        Bus search results or None
    """
    # Set default date if not provided (tomorrow)
    if not journey_date:
        from datetime import datetime, timedelta
        tomorrow = datetime.now() + timedelta(days=1)
        journey_date = tomorrow.strftime("%d-%m-%Y")
    
    print(f"\n🔍 Searching buses from {from_city} to {to_city} on {journey_date}...")
    
    # Get source city details
    print(f"\n📍 Finding source city: {from_city}")
    source_details = source_auto_suggest(from_city)
    if not source_details:
        print(f"❌ Could not find source city: {from_city}")
        return None
    
    print(f"✅ Found: {source_details['name']} (ID: {source_details['id']})")
    
    # Get destination city details
    print(f"\n📍 Finding destination city: {to_city}")
    destination_details = source_auto_suggest(to_city)
    if not destination_details:
        print(f"❌ Could not find destination city: {to_city}")
        return None
    
    print(f"✅ Found: {destination_details['name']} (ID: {destination_details['id']})")
    
    # Search for buses
    print(f"\n🚌 Fetching bus results...")
    results = get_bus_search_results(
        source_city_id=source_details['id'],
        destination_city_id=destination_details['id'],
        source_city_name=source_details['name'],
        destination_city_name=destination_details['name'],
        journey_date=journey_date
    )
    
    if results:
        print(f"\n✅ Results saved to bus_search_results.json")
        # Display summary
        if isinstance(results, dict) and 'BusList' in results:
            bus_count = len(results.get('BusList', []))
            print(f"📊 Found {bus_count} buses")
        return results
    else:
        print(f"\n❌ Failed to get bus results")
        return None

# --- Analytics Function ---
def get_bus_insights(search_result):
    """
    Analyze bus search results and provide comprehensive insights
    
    Args:
        search_result: The JSON response from get_bus_search_results()
    
    Returns:
        Dictionary containing various insights and statistics
    """
    if not search_result or 'Response' not in search_result:
        return {"error": "Invalid search result"}
    
    response = search_result['Response']
    available_trips = response.get('AvailableTrips', [])
    
    if not available_trips:
        return {
            "total_buses": 0,
            "message": "No buses available for this route"
        }
    
    # Initialize counters
    ac_buses = []
    non_ac_buses = []
    sleeper_buses = []
    seater_buses = []
    all_durations = []
    
    # Process each trip
    for trip in available_trips:
        fare = float(trip.get('amount', 0))
        # Handle AC/Non-AC properly - check both fields
        is_ac = trip.get('AC', False) and not trip.get('nonAC', False)
        is_non_ac = trip.get('nonAC', False)
        is_sleeper = trip.get('sleeper', False)
        is_seater = trip.get('seater', False)
        
        # Duration parsing (e.g., "27h 30m")
        duration_str = trip.get('duration', '0h 0m')
        hours = 0
        minutes = 0
        if 'h' in duration_str:
            parts = duration_str.split('h')
            hours = int(parts[0].strip())
            if len(parts) > 1 and 'm' in parts[1]:
                minutes = int(parts[1].replace('m', '').strip())
        total_minutes = hours * 60 + minutes
        
        trip_info = {
            'operator': trip.get('Travels', 'Unknown'),
            'type': trip.get('busType', 'Unknown'),
            'fare': fare,
            'duration': duration_str,
            'duration_minutes': total_minutes,
            'departure': trip.get('departureTime', ''),
            'arrival': trip.get('ArrivalTime', ''),
            'seats_available': trip.get('AvailableSeats', '0'),
            'is_ac': is_ac,
            'is_non_ac': is_non_ac,
            'is_sleeper': is_sleeper,
            'is_seater': is_seater,
            'discount': trip.get('Discount', 0),
            'original_price': trip.get('priceWithOutDiscount', fare),
            'rating': trip.get('rt', ''),
            'live_tracking': trip.get('liveTrackingAvailable', False)
        }
        
        # Categorize by AC type
        if is_ac:
            ac_buses.append(trip_info)
        if is_non_ac:
            non_ac_buses.append(trip_info)
        
        if is_sleeper:
            sleeper_buses.append(trip_info)
        if is_seater:
            seater_buses.append(trip_info)
        
        all_durations.append(trip_info)
    
    # Calculate averages
    avg_fare_ac = sum(b['fare'] for b in ac_buses) / len(ac_buses) if ac_buses else 0
    avg_fare_non_ac = sum(b['fare'] for b in non_ac_buses) / len(non_ac_buses) if non_ac_buses else 0
    avg_fare_overall = sum(b['fare'] for b in all_durations) / len(all_durations) if all_durations else 0
    
    # Find cheapest buses
    sorted_by_price = sorted(all_durations, key=lambda x: x['fare'])
    cheapest_buses = sorted_by_price[:3]
    
    # Find fastest buses
    sorted_by_duration = sorted(all_durations, key=lambda x: x['duration_minutes'])
    fastest_buses = sorted_by_duration[:3]
    
    # Find buses with best discounts
    sorted_by_discount = sorted(all_durations, key=lambda x: x['discount'], reverse=True)
    best_discount_buses = sorted_by_discount[:3]
    
    # Find buses with live tracking
    buses_with_tracking = [b for b in all_durations if b.get('live_tracking', False)]
    
    # Find highest rated buses
    rated_buses = [b for b in all_durations if b.get('rating') and b['rating'] != '']
    sorted_by_rating = sorted(rated_buses, key=lambda x: float(x['rating']), reverse=True) if rated_buses else []
    highest_rated_buses = sorted_by_rating[:3]
    
    # Price range
    min_price = min(b['fare'] for b in all_durations) if all_durations else 0
    max_price = max(b['fare'] for b in all_durations) if all_durations else 0
    
    # Operator statistics
    operators = {}
    for trip in all_durations:
        op = trip['operator']
        if op not in operators:
            operators[op] = {'count': 0, 'avg_fare': 0, 'total_fare': 0}
        operators[op]['count'] += 1
        operators[op]['total_fare'] += trip['fare']
    
    for op in operators:
        operators[op]['avg_fare'] = round(operators[op]['total_fare'] / operators[op]['count'], 2)
    
    # Build insights
    insights = {
        "route_info": {
            "source": response.get('Source', ''),
            "destination": response.get('Destination', ''),
            "journey_date": response.get('JourneyDate', '')
        },
        "summary": {
            "total_buses": len(available_trips),
            "ac_buses": len(ac_buses),
            "non_ac_buses": len(non_ac_buses),
            "sleeper_buses": len(sleeper_buses),
            "seater_buses": len(seater_buses)
        },
        "fare_analysis": {
            "average_fare_overall": round(avg_fare_overall, 2),
            "average_fare_ac": round(avg_fare_ac, 2) if avg_fare_ac > 0 else "N/A",
            "average_fare_non_ac": round(avg_fare_non_ac, 2) if avg_fare_non_ac > 0 else "N/A",
            "min_fare": min_price,
            "max_fare": max_price,
            "price_range": f"₹{min_price} - ₹{max_price}"
        },
        "cheapest_buses": [
            {
                "operator": bus['operator'],
                "type": bus['type'],
                "fare": bus['fare'],
                "duration": bus['duration'],
                "departure": bus['departure'],
                "seats": bus['seats_available']
            }
            for bus in cheapest_buses
        ],
        "fastest_buses": [
            {
                "operator": bus['operator'],
                "type": bus['type'],
                "duration": bus['duration'],
                "fare": bus['fare'],
                "departure": bus['departure'],
                "seats": bus['seats_available']
            }
            for bus in fastest_buses
        ],
        "best_discounts": [
            {
                "operator": bus['operator'],
                "type": bus['type'],
                "discount": bus['discount'],
                "original_price": bus['original_price'],
                "final_fare": bus['fare'],
                "savings": round(float(bus['original_price']) - bus['fare'], 2) if bus['original_price'] != bus['fare'] else 0
            }
            for bus in best_discount_buses if bus['discount'] > 0
        ],
        "highest_rated": [
            {
                "operator": bus['operator'],
                "type": bus['type'],
                "rating": bus['rating'],
                "fare": bus['fare'],
                "duration": bus['duration'],
                "departure": bus['departure']
            }
            for bus in highest_rated_buses
        ],
        # "live_tracking_available": {
        #     "count": len(buses_with_tracking),
        #     "buses": [
        #         {
        #             "operator": bus['operator'],
        #             "type": bus['type'],
        #             "fare": bus['fare'],
        #             "departure": bus['departure']
        #         }
        #         for bus in buses_with_tracking[:3]
        #     ]
        # },
        "operators": dict(sorted(operators.items(), key=lambda x: x[1]['count'], reverse=True))
    }
    
    return insights

# --- Example Usage ---
if __name__ == "__main__":
    # Search for buses
    result = search_buses(
        from_city="Delhi",
        to_city="Dehradun",
        journey_date="31-10-2025"
    )
    
    # Get and display insights
    if result:
        print("\n" + "="*80)
        print("Analyzing results...")
        print("="*80)
        
        insights = get_bus_insights(result)
        print(insights)
        
        # You can also access insights programmatically
        # print(f"\nTotal buses: {insights['summary']['total_buses']}")
        # print(f"Cheapest fare: ₹{insights['fare_analysis']['min_fare']}")
    
    # Example with different cities
    # result = search_buses(
    #     from_city="Pune",
    #     to_city="Mumbai",
    #     journey_date="25-10-2025"
    # )
    # if result:
    #     insights = get_bus_insights(result)
    #     print_insights(insights)