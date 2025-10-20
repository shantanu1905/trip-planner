import requests
import json
import re

url = "https://hotelservice.easemytrip.com/api/HotelService/HotelListIdWiseNew"

def SearchHotelInPlace(place: str, checkindate: str = "2025-10-31", checkoutdate: str = "2025-11-04", currency: str = "INR", noofroom: int = 1, noofadult: int = 2, noofchild: int = 0):
    """
    Search hotels in a given place using EaseMyTrip API
    """

    # ✅ FIX: Run regex outside f-string to avoid escaping issue
    clean_place = re.sub(r"\s+", "", place.upper())

    payload = json.dumps({
        "PageNo": 1,
        "RoomDetails": [
            {
                "NoOfRooms": noofroom,
                "NoOfAdult": noofadult,
                "NoOfChild": noofchild,
                "childAge": ""
            }
        ],
        "SearchKey": f"15~{currency}~{clean_place}~{checkindate}~{checkoutdate}~1~2_~~~EASEMYTRIP~NA~NA~NA~IN",
        "HotelCount": 30,
        "CheckInDate": checkindate,
        "CheckOut": checkoutdate,
        "CityCode": place,
        "CityName": place,
        "EMTCommonID": "",
        "NoOfRooms": 1,
        "sorttype": "Popular|DESC",
        "auth": {
            "AgentCode": 1,
            "UserName": "EaseMyTrip",
            "Password": "C2KYph9PJFy6XyF6GT7SAeTq2d5e9Psrq5vmH34S",
            "loginInfo": ""
        },
        "minPrice": 1,
        "maxPrice": 10000000,
        "hotelid": [],
        "emtToken": "yBAP2WJqhwAQBMyu9kNBUZ3I1W6kSIuGcjFoLCku/QE7BkECtmM9PVH9c8hNl23BVBQmIcert31b2Z4qZ+rmabkDwv+c+ueRclp76OC64cDJs+Sekt9kwrYeTffFDw63dDeu+ouftE4b4TGh6luO2fFryNnQKUSFdq4f8ElhQ0IzWvVpwbh46WIn/KN4BDFrImax3uBpctbfHeW0osBOIw7eBEkU39FEX7E0xX6ng/JTMJ51Rehh9mDUVlWHfndZ+bJDIurkv2BqdNa/HTY5XGcsLz0zNjRhpZBPN7UvwzcoiTuQF2z6RUw80qpo2rLBaiuJN7D3BqSD0qSWlNhlLepkgxTuNzwto5xzfXQWS/0lwwXd70NlZI6Os11AtMo+4SAnX6lUGXdIiYaTBlrHkA==",
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1bmlxdWVfbmFtZSI6IkVBU0VNWVRSSVAiLCJuYmYiOjE3NjA2OTYyMjEsImV4cCI6MTc2MDY5ODAyMSwiaWF0IjoxNzYwNjk2MjIxfQ.-34c6OrKtHweoIXIvl6x7pTEZaw6kd5SPi4Uov39K3g",
        "traceid": "20251017152319",
        "vid": "570ebd20da4411efb9cde7735702e199",
        "ipaddress": "",
        "lat": "",
        "lon": "",
        "name": "",
        "Name": "",
        "lstLoc": [],
        "selectchain": [],
        "selectedAreas": [],
        "selectedAmen": [],
        "selectedProp": [],
        "selectedTARating": [],
        "selectedRating": [],
        "wlcode": "",
        "userprice": "",
        "isLMR": False
    })

    headers = {
        'sec-ch-ua-platform': '"Windows"',
        'Referer': 'https://www.easemytrip.com/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0',
        'Accept': 'application/json, text/plain, */*',
        'sec-ch-ua': '"Microsoft Edge";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
        'Content-Type': 'application/json',
        'sec-ch-ua-mobile': '?0',
    }

    response = requests.post(url, headers=headers, data=payload)
    data = response.json()

    return data

   




def parse_hotel_response(data: dict) -> list:
    """
    Parse EaseMyTrip hotel API response and extract only useful fields.
    """
    hotels = []

    for h in data.get("htllist", []):
        # Clean cancellation policy text
        cancellation_policy = re.sub(r"<.*?>", "", h.get("htlPlcy", "")).replace("\n", " ").strip()

        hotel_info = {
            "hotel_name": h.get("nm"),
            "chain_name": h.get("cName"),
            "category": h.get("catgry"),
            "address": h.get("adrs"),
            "distance_from_city": h.get("dist"),
            "price": {
                "currency": h.get("curr"),
                "base_price": h.get("prc"),
                "total_price": h.get("tPr"),
                "tax": h.get("tax"),
                "discount": h.get("disc"),
                "cashback": re.sub(r"<.*?>", "", h.get("cOffers", "")).strip() if h.get("cOffers") else None,
            },
            "rating": {
                "hotel_rating": h.get("rat"),
                "tripadvisor_rating": h.get("tr"),
                "total_reviews": h.get("tCount")
            },
            "checkin_time": h.get("cinTime"),
            "checkout_time": h.get("coutTime"),
            "cancellation_policy": cancellation_policy,
            "booking_url": h.get("durl"),
            "amenities": h.get("amen", []),
            "highlights": h.get("highlt", "").split("|") if h.get("highlt") else [],
            "images": h.get("imgarry", [])[:5]
        }

        hotels.append(hotel_info)

    return hotels








if __name__ == "__main__":
    data = SearchHotelInPlace("Mussoorie")
    clean_hotels = parse_hotel_response(data)

    print(json.dumps(clean_hotels, indent=2))
