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
                    'ArrivalDate': train.get('ArrivalDate'),
                    'departuredate': train.get('departuredate'),
                    'avlClasses': train.get('avlClasses', []),
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

# # Example usage:
# if __name__ == "__main__":
   
#     result = search_trains("NGP", "NDLS", "30/10/2025")

#     print(result)
    
#     # if result:
#     #     for train in result:
#     #         print(f"\nTrain: {train['trainName']} ({train['trainNumber']})")
#     #         print(f"Route: {train['fromStnName']} to {train['toStnName']}")
#     #         print(f"Departure: {train['departureTime']} | Arrival: {train['arrivalTime']}")
#     #         print(f"Duration: {train['duration']} | Distance: {train['distance']} km")
#     #         print(f"Classes available:")
#     #         for cls in train['classes']:
#     #             print(f"  - {cls['className']}: ₹{cls['totalFare']} | Status: {cls['availablityStatus']}")
#     # else:
#     #     print("Failed to get train data")