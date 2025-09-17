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


