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








# encKey = "EDMEMT1234"
# decKey = "TMTOO1vDhT9aWsV1"

# def EncryptionV1(plaintext):
#     key = decKey.encode('utf-8')
#     iv = decKey.encode('utf-8')
#     cipher = AES.new(key, AES.MODE_CBC, iv)
#     padded = pad(plaintext.encode('utf-8'), AES.block_size)
#     encrypted = cipher.encrypt(padded)
#     return base64.b64encode(encrypted).decode('utf-8')

# def decryptV1(ciphertext):
#     key = decKey.encode('utf-8')
#     iv = decKey.encode('utf-8')
#     cipher = AES.new(key, AES.MODE_CBC, iv)
#     decrypted = cipher.decrypt(base64.b64decode(ciphertext))
#     return unpad(decrypted, AES.block_size).decode('utf-8')



# # Example: Source AutoSuggest (GET)
# def source_auto_suggest(place_name):
#     url = "https://autosuggest.easemytrip.com/api/auto/bus?useby=popularu&key=jNUYK0Yj5ibO6ZVIkfTiFA=="
#     jsonString = {
#         "userName": "",
#         "password": "",
#         "Prefix": place_name,
#         # Search buses using GetSearchResult API (POST)
#         "country_code": "IN"
#     }
#     import json
#     RQ = {"request": EncryptionV1(json.dumps(jsonString))}
#     jsonrequest = {
#         "request": RQ["request"],
#         "isIOS": False,
#         "ip": "49.249.40.58",
#         "encryptedHeader": "7ZTtohPgMEKTZQZk4/Cn1mpXnyNZDJIRcrdCFo5ahIk="
#     }
#     response = requests.post(url, json=jsonrequest)
#     # Decrypt and parse the response
#     decrypted = decryptV1(response.text)
#     try:
#         return json.loads(decrypted)
#     except Exception:
#         return {"error": "Failed to decrypt or parse response", "raw": decrypted}

# # Example: Destination AutoSuggest (GET)
# def destination_auto_suggest(source_id):
#     url = f"{SERVICE_URL}/search/destinationAutoSuggest?sourceId={source_id}"
#     response = requests.get(url)
#     return response.json()

# # Example: Get Source City (GET)
# def get_source_city(city_name):
#     url = f"{SERVICE_URL}/search/getsourcecity?id={city_name}"
#     response = requests.get(url)
#     return response.json()