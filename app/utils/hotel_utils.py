from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
import requests, json, re
from datetime import datetime

from app.database.models import HotelPreferences, Trip
from app.database.database import get_db
import json
import requests
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


EASEMYTRIP_URL = "https://hotelservice.easemytrip.com/api/HotelService/HotelListIdWiseNew"
USER_URL = "https://solr.easemytrip.com/v1/api/auto/GetHotelAutoSuggest_SolrUI"
USER_IDENTITY = "dwnCFBEJdZ9ET0la7HEEvg=="  # static identity for EaseMyTrip API
USER_IP = ""  # You can dynamically populate this if needed



# -------------------------------------------------------------------------
# 1️⃣ SEARCH FUNCTION – Fetch hotel list from EaseMyTrip
# -------------------------------------------------------------------------
def search_hotels_easemytrip(
    destination: str,
    check_in: datetime,
    check_out: datetime,
    no_of_rooms: int,
    no_of_adult: int,
    no_of_child: int,
    min_price: float = 1,
    max_price: float = 1000000,
    sort_type: str = "Popular|DESC",
    no_of_results: int = 30,
) -> list:
    """
    Search hotels from EaseMyTrip API and return combined list of hotels.
    """
    clean_place = re.sub(r"\s+", "", destination.upper())

    payload = {
        "PageNo": 1,
        "RoomDetails": [
            {
                "NoOfRooms": no_of_rooms,
                "NoOfAdult": no_of_adult,
                "NoOfChild": no_of_child,
                "childAge": ""
            }
        ],
        "SearchKey": f"15~INR~{clean_place}~{check_in.strftime('%Y-%m-%d')}~{check_out.strftime('%Y-%m-%d')}~{no_of_rooms}~{no_of_adult}_~~~EASEMYTRIP~NA~NA~NA~IN",
        "HotelCount": no_of_results,
        "CheckInDate": check_in.strftime("%Y-%m-%d"),
        "CheckOut": check_out.strftime("%Y-%m-%d"),
        "CityCode": destination,
        "CityName": destination,
        "NoOfRooms": no_of_rooms,
        "sorttype": sort_type,
        "minPrice": min_price,
        "maxPrice": max_price,
        "auth": {
            "AgentCode": 1,
            "UserName": "EaseMyTrip",
            "Password": "C2KYph9PJFy6XyF6GT7SAeTq2d5e9Psrq5vmH34S"
        },
        "hotelid": [],
        "emtToken": "yBAP2WJqhwAQBMyu9kNBUZ3I1W6kSIuGcjFoLCku...",
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "traceid": "20251017152319",
        "vid": "570ebd20da4411efb9cde7735702e199"
    }

    headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}

    try:
        response = requests.post(EASEMYTRIP_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        data = response.json()
        hotels = data.get("htllist", []) + data.get("lmrlist", [])
        return hotels
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching hotels: {str(e)}")


# -------------------------------------------------------------------------
# 2️⃣ ANALYSIS FUNCTION – Filter, structure, and rank hotel results
# -------------------------------------------------------------------------
def analyze_hotels(hotel_list: list) -> dict:
    """
    Analyze and recommend hotels based on ratings, price, and other metrics.
    """

    if not hotel_list:
        return {
            "status": False,
            "message": "No hotels found",
            "recommendations": {},
            "hotels": []
        }

    clean_hotels = []
    for h in hotel_list:
        try:
            clean_hotels.append({
                "name": h.get("nm"),
                "price": h.get("prc"),
                "rating": h.get("rat"),
                "trip_rating": float(h.get("tr") or 0),
                "category": h.get("catgry"),
                "address": h.get("adrs"),
                "check_in": h.get("cinTime"),
                "check_out": h.get("coutTime"),
                "latitude": h.get("lat"),
                "longitude": h.get("lon"),
                "booking_url": h.get("durl"),
                "policy": h.get("htlPlcy"),
                "images": h.get("imgarry") or [],
                "amenities": h.get("amen", []),
                "brand": h.get("cName"),
                "distance_km": h.get("distKM"),
                "is_couple_friendly": h.get("isCF", False),
            })
        except Exception:
            continue

    sorted_by_trip_rating = sorted(clean_hotels, key=lambda x: x["trip_rating"], reverse=True)
    sorted_by_price = sorted(clean_hotels, key=lambda x: x["price"] or 999999)

    recommendations = {
        "top_rated_hotels": sorted_by_trip_rating[:3],
        "best_value_for_money": sorted(sorted_by_trip_rating[:10], key=lambda x: x["price"])[:3],
        "luxury_stays": [h for h in sorted_by_price[-5:] if (float(h.get("rating") or 0) >= 4)],
        "budget_friendly": sorted_by_price[:3],
    }

    return {
        "status": True,
        "message": "Hotel analysis completed",
        "recommendations": recommendations,
        "hotels": clean_hotels[:15]  # limit results
    }



# -------------------------------------------------------------------------
# 3️⃣ HOTEL AVERAGE PRICE FUNCTION – Calculate average hotel price   (COST BREAKDOWN AI AGENT)
# -------------------------------------------------------------------------
def calculate_average_hotel_price(
    destination: str,
    check_in: datetime,
    check_out: datetime,
    no_of_rooms: int,
    no_of_adult: int,
    no_of_child: int,
    min_price: float = 1,
    max_price: float = 1000000,
    sort_type: str = "Popular|DESC",
) -> dict:
    """
    Fetch hotels and calculate average, min, and max prices for the search range.
    """

    # Step 1️⃣: Fetch hotel list from EaseMyTrip
    hotels = search_hotels_easemytrip(
        destination=destination,
        check_in=check_in,
        check_out=check_out,
        no_of_rooms=no_of_rooms,
        no_of_adult=no_of_adult,
        no_of_child=no_of_child,
        min_price=min_price,
        max_price=max_price,
        sort_type=sort_type
    )

    if not hotels:
        return {
            "status": False,
            "message": "No hotels found for given filters.",
            "average_price": 0,
            "total_hotels": 0
        }

    # Step 2️⃣: Extract valid prices
    prices = []
    for h in hotels:
        try:
            price = float(h.get("prc") or 0)
            if price > 0:
                prices.append(price)
        except (ValueError, TypeError):
            continue

    if not prices:
        return {
            "status": False,
            "message": "No valid prices found for hotels.",
            "average_price": 0,
            "total_hotels": len(hotels)
        }

    # Step 3️⃣: Compute basic statistics
    avg_price = round(sum(prices) / len(prices), 2)
    min_p = min(prices)
    max_p = max(prices)

    # Step 4️⃣: Estimate total stay cost
    nights = (check_out - check_in).days or 1
    total_estimated_cost = avg_price * nights * no_of_rooms

    return {
        "status": True,
        "message": "Hotel pricing analysis completed successfully.",
        "destination": destination,
        "check_in": check_in.strftime("%Y-%m-%d"),
        "check_out": check_out.strftime("%Y-%m-%d"),
        "nights": nights,
        "total_hotels": len(hotels),
        "average_price_per_night": avg_price,
        "min_price": min_p,
        "max_price": max_p,
        "estimated_total_stay_cost": round(total_estimated_cost, 2)
    }
