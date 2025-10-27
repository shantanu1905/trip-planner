
import json
import requests
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# Define the keys from the JavaScript code.
# The original encKey is 10 bytes. AES-128 requires a 16-byte key.
# We'll pad it with null bytes to match the likely behavior of CryptoJS.
ENC_KEY_STR = "EDMEMT1234"
DEC_KEY_STR = "TMTOO1vDhT9aWsV1"

# The key and IV must be 16 bytes for AES-128. We encode the string and pad if necessary.
# Note: Using the same material for Key and IV is not a secure practice,
# but we are replicating the original code's behavior.
ENC_KEY = ENC_KEY_STR.encode('utf-8').ljust(16, b'\0')
DEC_KEY = DEC_KEY_STR.encode('utf-8')


# API URL
_USER_URL = "https://solr.easemytrip.com/v1/api/auto/GetHotelAutoSuggest_SolrUI"
# Replace with actual user IP if required
USER_IP = ""  




def encryption_v1(number_str: str) -> str:
    """
    Encrypts a string using AES CBC with the predefined DEC_KEY.

    This function corresponds to the `EncryptionV1` function in the JavaScript code.
    """
    print(f"Encrypting with DEC_KEY: {number_str}")
    
    # Data to be encrypted must be in bytes.
    data_bytes = number_str.encode('utf-8')
    
    # Create a new AES cipher object with the key and IV.
    # The key and IV are the same, as in the original script.
    cipher = AES.new(DEC_KEY, AES.MODE_CBC, iv=DEC_KEY)
    
    # Pad the data and encrypt it.
    ct_bytes = cipher.encrypt(pad(data_bytes, AES.block_size))
    
    # Encode to Base64.
    encrypted_message = base64.b64encode(ct_bytes).decode('utf-8')
    
    return encrypted_message


def decrypt_v1(encrypted_message: str) -> str:
    """
    Decrypts a Base64 encoded string using AES CBC with the predefined DEC_KEY.

    This function corresponds to the `decryptV1` function in the JavaScript code.
    """
    print(f"Decrypting with DEC_KEY: {encrypted_message}")
    
    # The encrypted message must be decoded from Base64.
    ct_bytes = base64.b64decode(encrypted_message)
    
    # Create a new AES cipher object with the same key and IV used for encryption.
    cipher = AES.new(DEC_KEY, AES.MODE_CBC, iv=DEC_KEY)
    
    # Decrypt the data and then unpad it.
    pt_bytes = unpad(cipher.decrypt(ct_bytes), AES.block_size)
    
    # Decode the decrypted bytes back to a string.
    decrypted_message = pt_bytes.decode('utf-8')
    
    return decrypted_message











def get_hotel_autosuggest(place: str, user_ip: str = USER_IP) -> list:
    """
    Fetch hotel/place suggestions for a given prefix.

    Args:
        place (str): Partial hotel or place name.
        user_ip (str): Optional user IP, used in encryption headers.

    Returns:
        list: List of suggested hotels/places (dicts).
    """
    # Request payload
    payload = {
        "Prefix": place,
        "_type": "Hotel"
    }

    # Encrypt payload
    encrypted_request = {"request": encryption_v1(json.dumps(payload))}

    # Headers with encrypted user identity
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Useridentity": "dwnCFBEJdZ9ET0la7HEEvg=="  # Can use encryption(f"EMTUSER|{user_ip}") if dynamic
    }

    try:
        response = requests.post(_USER_URL, headers=headers, data=json.dumps(encrypted_request))
        response.raise_for_status()

        # Decrypt API response
        decrypted_data_str = decrypt_v1(response.text)
        suggestions = json.loads(decrypted_data_str)

        return suggestions

    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return []

    except json.JSONDecodeError:
        print("Invalid JSON response from API")
        return []

# Example usage
if __name__ == "__main__":
    results = get_hotel_autosuggest("Nag")
    for r in results:
        print(r)





# import re
# import json
# import requests
# from datetime import datetime
# from fastapi import HTTPException



# EASEMYTRIP_URL = "https://hotelservice.easemytrip.com/api/HotelService/HotelListIdWiseNew"


# def search_hotels_easemytrip(
#     destination: str,
#     check_in: datetime,
#     check_out: datetime,
#     no_of_rooms: int,
#     no_of_adult: int,
#     no_of_child: int,
#     min_price: float = 1,
#     max_price: float = 1000000,
#     sort_type: str = "Popular|DESC",
# ) -> list:
#     """
#     Search hotels from EaseMyTrip API and return combined list of hotels.
#     """
#     clean_place = re.sub(r"\s+", "", destination.upper())

#     payload = {
#         "PageNo": 1,
#         "RoomDetails": [
#             {
#                 "NoOfRooms": no_of_rooms,
#                 "NoOfAdult": no_of_adult,
#                 "NoOfChild": no_of_child,
#                 "childAge": ""
#             }
#         ],
#         "SearchKey": f"15~INR~{clean_place}~{check_in.strftime('%Y-%m-%d')}~{check_out.strftime('%Y-%m-%d')}~{no_of_rooms}~{no_of_adult}_~~~EASEMYTRIP~NA~NA~NA~IN",
#         "HotelCount": 30,
#         "CheckInDate": check_in.strftime("%Y-%m-%d"),
#         "CheckOut": check_out.strftime("%Y-%m-%d"),
#         "CityCode": destination,
#         "CityName": destination,
#         "NoOfRooms": no_of_rooms,
#         "sorttype": sort_type,
#         "minPrice": min_price,
#         "maxPrice": max_price,
#         "auth": {
#             "AgentCode": 1,
#             "UserName": "EaseMyTrip",
#             "Password": "C2KYph9PJFy6XyF6GT7SAeTq2d5e9Psrq5vmH34S"
#         },
#         "hotelid": [],
#         "emtToken": "yBAP2WJqhwAQBMyu9kNBUZ3I1W6kSIuGcjFoLCku...",
#         "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
#         "traceid": "20251017152319",
#         "vid": "570ebd20da4411efb9cde7735702e199"
#     }

#     headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}

#     try:
#         response = requests.post(EASEMYTRIP_URL, headers=headers, data=json.dumps(payload))
#         response.raise_for_status()
#         data = response.json()
#         hotels = data.get("htllist", []) + data.get("lmrlist", [])
#         return hotels
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error fetching hotels: {str(e)}")





# if __name__ == "__main__":
#     check_in = datetime(2025, 11, 10)
#     check_out = datetime(2025, 11, 12)
#     hotels = search_hotels_easemytrip(
#         destination="Nagpur",
#         check_in=check_in,
#         check_out=check_out,
#         no_of_rooms=1,
#         no_of_adult=2,
#         no_of_child=0
#     )

#     for hotel in hotels:
#         print(hotel)
