from typing import Dict, List
from datetime import datetime
import re
from statistics import mean, median
import requests
import json

def search_trains(from_station, to_station, travel_date, coupon_code=""):
    """
    Search for trains between stations and return simplified data structure
    """
    
    url = "https://railways.easemytrip.com/Train/_TrainBtwnStationList"
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    payload = {
        "fromSec": from_station,
        "toSec": to_station,
        "fromdate": travel_date,
        "couponCode": coupon_code
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        trains = []
        
        if 'trainBtwnStnsList' in data:
            for train in data['trainBtwnStnsList']:
                train_data = {
                    'trainName': train.get('trainName'),
                    'trainNumber': train.get('trainNumber'),
                    'arrivalTime': train.get('arrivalTime'),
                    'departureTime': train.get('departureTime'),
                    'duration': train.get('duration'),
                    'distance': train.get('distance'),
                    'fromStnName': train.get('fromStnName'),
                    'fromStnCode': train.get('fromStnCode'),
                    'toStnName': train.get('toStnName'),
                    'toStnCode': train.get('toStnCode'),
                    'ArrivalDate': train.get('ArrivalDate'),
                    'departuredate': train.get('departuredate'),
                    # 'avlClasses': train.get('avlClasses', []),
                    'classes': []
                }
                
                # Add class details
                if 'TrainClassWiseFare' in train:
                    for fare in train['TrainClassWiseFare']:
                        class_data = {
                            'className': fare.get('enqClassName'),
                            'enqClass':fare.get('enqClass'),
                            'quotaName': fare.get('quotaName'),
                            'totalFare': fare.get('totalFare'),
                            'availablityDate': None,
                            'availablityStatus': None
                        }
                        
                        # Get availability info
                        if 'avlDayList' in fare and fare['avlDayList']:
                            avl = fare['avlDayList'][0]  # Take first availability
                            class_data['availablityDate'] = avl.get('availablityDate')
                            class_data['availablityStatus'] = avl.get('availablityStatus')
                        
                        train_data['classes'].append(class_data)
                
                trains.append(train_data)
        
        return trains
        
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return None




def get_station_code(station_name: str):
    """
    Fetch station code using EaseMyTrip Train AutoSuggest API.
    Returns the first station object with Code if available.
    """
    url = f"https://solr.easemytrip.com/v1/api/auto/GetTrainAutoSuggest/{station_name}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        stations = response.json()

        if stations and isinstance(stations, list):
            first_station = stations[0]  # Take first object
            return first_station["Code"] , first_station["Name"]
        return None  # If no station found

    except requests.exceptions.RequestException as e:
        print(f"Error fetching station code: {e}")
        return None




def analyze_train_availability(trains_data: List[Dict]) -> Dict:
    """
    Analyze train availability status to determine if tickets are available.
    
    Returns dict with:
    - is_available: bool
    - available_classes: list of class names with tickets
    - total_seats: int (sum of available seats across all classes)
    """
    if not trains_data:
        return {"is_available": False, "available_classes": [], "total_seats": 0}
    
    available_classes = []
    total_seats = 0
    
    for train in trains_data:
        for cls in train.get("classes", []):
            status = cls.get("availablityStatus", "")
            
            # Check if tickets are available (not waitlisted/RAC/not available)
            if "AVAILABLE" in status.upper():
                # Extract seat count from status like "AVAILABLE-10"
                match = re.search(r'AVAILABLE-(\d+)', status, re.IGNORECASE)
                if match:
                    seats = int(match.group(1))
                    total_seats += seats
                    available_classes.append(cls.get("className"))
    
    return {
        "is_available": len(available_classes) > 0,
        "available_classes": list(set(available_classes)),
        "total_seats": total_seats
    }


def calculate_average_fares(trains_data: List[Dict]) -> Dict:
    """
    Calculate average fares for each class across all trains.
    """
    class_fares = {
        "3A": [],  # AC 3 Tier
        "2A": [],  # AC 2 Tier
        "1A": [],  # First AC
        "SL": [],  # Sleeper
        "3E": [],  # AC 3 Economy
        "CC": [],  # Chair Car
        "2S": [],  # Second Sitting
    }
    
    for train in trains_data:
        for cls in train.get("classes", []):
            enq_class = cls.get("enqClass", "")
            fare = cls.get("totalFare")
            
            if fare and enq_class in class_fares:
                try:
                    class_fares[enq_class].append(float(fare))
                except (ValueError, TypeError):
                    continue
    
    # Calculate averages
    averages = {}
    class_names = {
        "3A": "AC 3 Tier",
        "2A": "AC 2 Tier", 
        "1A": "First AC",
        "SL": "Sleeper",
        "3E": "AC 3 Economy",
        "CC": "Chair Car",
        "2S": "Second Sitting"
    }
    
    for code, fares in class_fares.items():
        if fares:
            averages[class_names[code]] = {
                "average": round(mean(fares), 2),
                "min": round(min(fares), 2),
                "max": round(max(fares), 2),
                "median": round(median(fares), 2),
                "count": len(fares)
            }
    
    return averages


def get_trains_with_available_tickets(trains_data: List[Dict]) -> List[Dict]:
    """
    Get list of trains that have confirmed tickets available.
    """
    available_trains = []
    
    for train in trains_data:
        available_classes = []
        total_available_seats = 0
        
        for cls in train.get("classes", []):
            status = cls.get("availablityStatus", "")
            
            if "AVAILABLE" in status.upper() and "RLWL" not in status and "WL" not in status:
                match = re.search(r'AVAILABLE-(\d+)', status, re.IGNORECASE)
                seats = int(match.group(1)) if match else 0
                
                available_classes.append({
                    "class_name": cls.get("className"),
                    "class_code": cls.get("enqClass"),
                    "fare": cls.get("totalFare"),
                    "available_seats": seats,
                    "status": status
                })
                total_available_seats += seats
        
        if available_classes:
            available_trains.append({
                "train_name": train.get("trainName"),
                "train_number": train.get("trainNumber"),
                "departure_time": train.get("departureTime"),
                "arrival_time": train.get("arrivalTime"),
                "duration": train.get("duration"),
                "from_station": f"{train.get('fromStnName')} ({train.get('fromStnCode')})",
                "to_station": f"{train.get('toStnName')} ({train.get('toStnCode')})",
                "total_available_seats": total_available_seats,
                "available_classes": available_classes
            })
    
    return available_trains


def get_fastest_trains(trains_data: List[Dict], limit: int = 3) -> List[Dict]:
    """
    Get the fastest trains based on journey duration.
    """
    trains_with_duration = []
    
    for train in trains_data:
        duration_str = train.get("duration", "00:00")
        try:
            # Parse duration like "04:55" to minutes
            hours, mins = map(int, duration_str.split(":"))
            total_minutes = hours * 60 + mins
            
            trains_with_duration.append({
                "train_name": train.get("trainName"),
                "train_number": train.get("trainNumber"),
                "duration": duration_str,
                "duration_minutes": total_minutes,
                "departure_time": train.get("departureTime"),
                "arrival_time": train.get("arrivalTime")
            })
        except (ValueError, AttributeError):
            continue
    
    # Sort by duration and return top N
    trains_with_duration.sort(key=lambda x: x["duration_minutes"])
    return trains_with_duration[:limit]


def get_cheapest_trains(trains_data: List[Dict], class_preference: str = "SL", limit: int = 3) -> List[Dict]:
    """
    Get cheapest trains for a specific class.
    """
    trains_with_fare = []
    
    for train in trains_data:
        for cls in train.get("classes", []):
            if cls.get("enqClass") == class_preference:
                try:
                    fare = float(cls.get("totalFare", 0))
                    trains_with_fare.append({
                        "train_name": train.get("trainName"),
                        "train_number": train.get("trainNumber"),
                        "fare": fare,
                        "class": cls.get("className"),
                        "availability": cls.get("availablityStatus"),
                        "departure_time": train.get("departureTime"),
                        "duration": train.get("duration")
                    })
                except (ValueError, TypeError):
                    continue
    
    # Sort by fare and return top N
    trains_with_fare.sort(key=lambda x: x["fare"])
    return trains_with_fare[:limit]


def analyze_train_info(legs_data: Dict, search_trains_func=search_trains) -> Dict:
    """
    Main function to analyze train information from itinerary legs.
    
    Args:
        legs_data: Dictionary containing 'legs' and 'option_name'
        search_trains_func: Function to call for searching trains (must be provided)
    
    Returns:
        Comprehensive train analysis
    """
    legs = legs_data.get("legs", [])
    option_name = legs_data.get("option_name", "Unknown Route")
    
    # Filter only train legs
    train_legs = [leg for leg in legs if leg.get("mode", "").lower() == "train"]
    
    if not train_legs:
        return {
            "status": False,
            "message": "No train journeys found in this route",
            "option_name": option_name
        }
    
    if search_trains_func is None:
        return {
            "status": False,
            "message": "search_trains_func must be provided to fetch actual train data",
            "option_name": option_name
        }
    
    # Analyze each train leg
    leg_analysis = []
    
    for idx, leg in enumerate(train_legs, 1):
        from_station = leg.get("from")
        to_station = leg.get("to")
        from_code = leg.get("from_code")
        to_code = leg.get("to_code")
        journey_date = leg.get("journey_date")
        booking_url = leg.get("booking_url")
        
        # Parse date
        try:
            date_obj = datetime.strptime(journey_date, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%d/%m/%Y")
        except:
            formatted_date = journey_date
        
        print(f"🔍 Searching trains: {from_code} → {to_code} on {formatted_date}")
        
        # Actually call search_trains function
        try:
            trains_data = search_trains_func(from_code, to_code, formatted_date)
            
            if trains_data and len(trains_data) > 0:
                # Create response structure for analyzer
                trains_response = {
                    "status": True,
                    "data": {
                        "trains": trains_data,
                        "booking_url": booking_url
                    }
                }
                
                # Process with detailed analyzer
                leg_details = process_train_search_results(trains_response)
                leg_details["journey_date"] = formatted_date

                leg_analysis.append(leg_details)
            else:
                # No trains found
                leg_analysis.append({
                  
                    "route": f"{from_station} ({from_code}) → {to_station} ({to_code})",
                    "journey_date": formatted_date,
                    "status": False,
                    "message": "No trains found for this route",
        
                })
        
        except Exception as e:
            print(f"❌ Error searching trains for leg {idx}: {e}")
            leg_analysis.append({
                "route": f"{from_station} ({from_code}) → {to_station} ({to_code})",
                "journey_date": formatted_date,
                "status": False,
                "error": str(e),
                "message": f"Error fetching train data: {str(e)}"
            })
    
    # Calculate overall statistics
    total_trains = sum(
        leg.get("summary", {}).get("total_trains", 0) 
        for leg in leg_analysis if leg.get("status", False)
    )
    total_available = sum(
        leg.get("summary", {}).get("trains_with_available_tickets", 0) 
        for leg in leg_analysis if leg.get("status", False)
    )
    
    return {
        "status": True,
        "option_name": option_name,
        "overall_statistics": {
            "total_trains_found": total_trains,
            "trains_with_available_tickets": total_available
        },
        "leg_wise_analysis": leg_analysis
    }


def process_train_search_results(trains_response: Dict) -> Dict:
    """
    Process the output from search_train endpoint and provide comprehensive analysis.
    
    Args:
        trains_response: Response from /searchtrain endpoint
    
    Returns:
        Detailed analysis with statistics
    """
    if not trains_response.get("status"):
        return {
            "status": False,
            "message": trains_response.get("message", "No data available"),
            "error": True
        }
    
    trains_data = trains_response.get("data", {}).get("trains", [])
    booking_url = trains_response.get("data", {}).get("booking_url", "")
    
    if not trains_data:
        return {
            "status": False,
            "message": "No trains found",
            "available_trains_count": 0
        }
    
    # Get all analysis
    available_trains = get_trains_with_available_tickets(trains_data)
    average_fares = calculate_average_fares(trains_data)
    fastest_trains = get_fastest_trains(trains_data)
    cheapest_sl = get_cheapest_trains(trains_data, "SL")
    cheapest_3a = get_cheapest_trains(trains_data, "3A")
    
    # Calculate total available seats across all trains
    total_available_seats = sum(train["total_available_seats"] for train in available_trains)
    
    # Build comprehensive response
    return {
        "status": True,
        "summary": {
            "total_trains": len(trains_data),
            "trains_with_available_tickets": len(available_trains),
            "total_available_seats": total_available_seats,
        },
        "available_trains": [
            {
                "train_name": train["train_name"],
                "train_number": train["train_number"],
                "departure": train["departure_time"],
                "arrival": train["arrival_time"],
                "duration": train["duration"],
                "route": f"{train['from_station']} → {train['to_station']}",
                "available_seats": train["total_available_seats"],
                "available_classes_count": len(train["available_classes"]),
                "classes": train["available_classes"]
            }
            for train in available_trains
        ],
        "fare_analysis": {
            "by_class": average_fares,
            "cheapest_options": {
                "sleeper_class": cheapest_sl,
                "ac_3_tier": cheapest_3a
            }
        },
        "fastest_trains": fastest_trains,
        "recommendations": {
            "best_for_speed": fastest_trains[0] if fastest_trains else None,
            "best_for_budget": cheapest_sl[0] if cheapest_sl else None,
            "most_available": max(available_trains, key=lambda x: x["total_available_seats"]) if available_trains else None
        }
    }



#------------------------------------------------------------------------
# Train Travel Average Cost Function – Calculate average train travel cost
#------------------------------------------------------------------------

from typing import List, Dict
from statistics import mean, median

def get_average_class_fares(trains_data: List[Dict]) -> Dict:
    """
    Calculate average, min, max, and median fare for each train class 
    (e.g., 3A, 2A, 1A, SL, 3E, CC, 2S) from all available trains.

    Args:
        trains_data (List[Dict]): List of train dictionaries containing 'classes' and 'totalFare'.

    Returns:
        Dict: A dictionary with average fare statistics for each class.
    """
    
    # --- Step 1️⃣: Define supported train classes ---
    class_fares = {
        "3A": [],  # AC 3 Tier
        "2A": [],  # AC 2 Tier
        "1A": [],  # First AC
        "SL": [],  # Sleeper
        "3E": [],  # AC 3 Economy
        "CC": [],  # Chair Car
        "2S": [],  # Second Sitting
    }
    
    # --- Step 2️⃣: Aggregate fares from all trains ---
    for train in trains_data:
        for cls in train.get("classes", []):
            enq_class = cls.get("enqClass", "").upper()
            fare = cls.get("totalFare")
            if enq_class in class_fares and fare:
                try:
                    class_fares[enq_class].append(float(fare))
                except (ValueError, TypeError):
                    continue
    
    # --- Step 3️⃣: Compute statistical summary for each class ---
    class_display_names = {
        "3A": "AC 3 Tier",
        "2A": "AC 2 Tier",
        "1A": "First AC",
        "SL": "Sleeper",
        "3E": "AC 3 Economy",
        "CC": "Chair Car",
        "2S": "Second Sitting"
    }
    
    fare_summary = {}
    for code, fares in class_fares.items():
        if fares:
            fare_summary[class_display_names[code]] = {
                "average_fare": round(mean(fares), 2),
                "min_fare": round(min(fares), 2),
                "max_fare": round(max(fares), 2),
                "median_fare": round(median(fares), 2),
                "sample_size": len(fares)
            }
    
    return fare_summary















# # Example usage
# if __name__ == "__main__":
#     # Import your actual search_trains function
#     from app.utils.easemytrip import search_trains
#     # Example 1: Analyze itinerary legs with actual train search
#     sample_legs = {
#         "legs": [
#             {
#                 "to": "Delhi",
#                 "from": "Nagpur",
#                 "mode": "Bus",
#                 "to_code": "NDLS",
#                 "from_code": "NGP",
#                 "approx_cost": "INR 800 - INR 2500",
#                 "approx_time": "15 hours",
#                 "booking_url": "https://railways.easemytrip.com/TrainListInfo/Nagpur(NGP)-to-Delhi(NDLS)/2/01-11-2025",
#                 "journey_date": "2025-11-01"
#             },
#             {
#                 "to": "Haridwar",
#                 "from": "Delhi",
#                 "mode": "Train",
#                 "to_code": "HW",
#                 "from_code": "NDLS",
#                 "approx_cost": "INR 500 - INR 1500",
#                 "approx_time": "4 hours",
#                 "booking_url": "https://railways.easemytrip.com/TrainListInfo/Delhi(NDLS)-to-Haridwar(HW)/2/02-11-2025",
#                 "journey_date": "2025-11-02"
#             }
#         ],
#         "option_name": "Cost Effective Route"
#     }
    
#     # IMPORTANT: Pass your search_trains function
#     result = analyze_train_info(sample_legs, search_trains_func=search_trains)
#     print("=== ITINERARY ANALYSIS ===")
#     print(json.dumps(result, indent=2))
    
#     # Example 2: Process search results directly
#     sample_search_response = {
#         "status": True,
#         "data": {
#             "trains": [
#                 # Your train data here
#             ],
#             "booking_url": "https://example.com"
#         }
#     }
    
#     detailed_analysis = process_train_search_results(sample_search_response)
#     print("\n=== DETAILED TRAIN ANALYSIS ===")
#     print(json.dumps(detailed_analysis, indent=2))