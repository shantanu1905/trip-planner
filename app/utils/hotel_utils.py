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
    no_of_results: int = 50,
) -> list:

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
        "emtToken": "...",
        "token": "...",
        "traceid": "20251017152319",
        "vid": "570ebd20da4411efb9cde7735702e199"
    }

    headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}

    try:
        response = requests.post(EASEMYTRIP_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        data = response.json()
        if not data:
            raise HTTPException(status_code=404, detail="No data received from hotel API")

        # Get lists safely
        htllist = data.get("htllist") or []
        lmrlist = data.get("lmrlist") or []

        # Combine
        hotels = htllist + lmrlist

        if not hotels:
            raise HTTPException(
                status_code=404,
                detail=f"No hotels found for '{destination}'. Try changing dates or filters."
            )

        return hotels

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching hotels: {str(e)}")
    


    
# -------------------------------------------------------------------------
# 2️⃣ ANALYSIS FUNCTION – Filter, structure, and rank hotel results
# -------------------------------------------------------------------------


def analyze_hotels(hotel_list: list) -> dict:

    """
    Analyze and recommend hotels based on ratings, price, and other metrics.
    Includes every available field in the hotel API response.
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
            price = float(h.get("prc") or 0)
            rating = float(h.get("rat") or 0)
            trip_rating = float(h.get("tr") or 0)

            clean_hotels.append({
                # -------------------------
                # BASIC HOTEL INFO  
                # -------------------------
                "hotel_id": h.get("hid"),
                "name": h.get("nm"),
                "category": h.get("catgry"),
                "brand": h.get("cName"),
                "description": h.get("desc"),
                "highlight": h.get("highlt"),
                "rank": h.get("rank"),

                # -------------------------
                # LOCATION INFO  
                # -------------------------
                "address": h.get("adrs"),
                "location": h.get("loc"),
                "area": h.get("area"),
                "latitude": h.get("lat"),
                "longitude": h.get("lon"),
                "distance_km": h.get("distKM"),
                "distance_raw": h.get("dist"),
                "hotel_distance": h.get("htlDist"),

                # -------------------------
                # PRICING INFO  
                # -------------------------
                "price": price,
                "tax": h.get("tax"),
                "discount": h.get("disc"),
                "hotel_discount": h.get("hDisc"),
                "strike_price": h.get("strk"),
                "total_price": h.get("tPr"),
                "lowest_app_fare": h.get("appfare"),
                "lowest_ln_fare": h.get("lnFare"),
                "currency": h.get("curr"),
                "discount_markup": h.get("discMrkup"),
                "cd_value": h.get("cdvalue"),
                "df_value": h.get("dfvalue"),
                "is_df_apply": h.get("isDfApply"),
                "discount_type_text": h.get("notecpndiscount"),
                "coupon_code": h.get("cpn"),
                "coupon_list": h.get("cpnLst"),
                "coupon_offers": h.get("cpnOffers"),
                "is_lowest_price": h.get("isLowestPrice"),
                "is_pay_zero": h.get("isPayZero"),

                # -------------------------
                # RATING INFO  
                # -------------------------
                "rating": rating,
                "trip_rating": trip_rating,
                "trip_review_count": h.get("tCount"),
                "trip_rating_url": h.get("trUrl"),

                # -------------------------
                # IMAGES  
                # -------------------------
                "image_url": h.get("imgU"),
                "image_list": h.get("imglst"),
                "images": h.get("imgarry") or [],

                # -------------------------
                # AMENITIES  
                # -------------------------
                "amenities": h.get("amen") or [],
                "amenities_text": h.get("hAmen"),
                "meal": h.get("meal"),

                # -------------------------
                # BOOKING INFO  
                # -------------------------
                "check_in": h.get("cinTime"),
                "check_out": h.get("coutTime"),
                "booking_url": h.get("durl"),
                "web_url": h.get("weburl"),
                "hotel_policy": h.get("htlPlcy"),
                "policy": h.get("plcy"),
                "external_url": h.get("nUrl"),

                # -------------------------
                # SAFETY & FRIENDLY  
                # -------------------------
                "is_couple_friendly": h.get("isCF", False),
                "is_safety": h.get("isSafety"),
                "is_dnd": h.get("isDND"),
                "is_bank_dnd": h.get("isBankDND"),

                # -------------------------
                # AVAILABILITY & BOOKING FLOW  
                # -------------------------
                "is_sold_out": h.get("isSold"),
                "mark_up": h.get("markup"),
                "commission": h.get("cmison"),
                "cashback": h.get("cback"),

                # -------------------------
                # EXTRA INFO  
                # -------------------------
                "m_view_no": h.get("mViewNo"),
                "mobile_view": h.get("mview"),

                "locality_ids": h.get("location_ids"),
                "payment_ids": h.get("payment_ids"),
                "tags": h.get("tags"),

                # -------------------------
                # VIEW COUNT  
                # -------------------------
                "total_view": h.get("totalView"),

                # -------------------------
                # INTERNAL / TECH FIELDS  
                # -------------------------
                "ar": h.get("ar"),
                "proDes": h.get("proDes"),
                "sort_id": h.get("sortID"),
                "page_no": h.get("pageNo"),
                "tid": h.get("tid"),
                "mid": h.get("mid"),
                "ttype": h.get("ttype"),
                "bap_uri": h.get("bap_uri"),
                "bpp_uri": h.get("bpp_uri"),
                "bap_id": h.get("bap_id"),
                "bpp_id": h.get("bpp_id"),

                # -------------------------
                # VALUE SCORE (your scoring)
                # -------------------------
                "value_score": round((trip_rating / price), 4) if price > 0 else 0,
            })

        except Exception as e:
            print("Error cleaning hotel: ", e)
            continue

    # -------------------------
    # SORTING & RECOMMENDATIONS
    # -------------------------
    sorted_by_rating = sorted(clean_hotels, key=lambda x: x["trip_rating"], reverse=True)
    sorted_by_price = sorted(clean_hotels, key=lambda x: x["price"] or 999999)
    sorted_by_value = sorted(clean_hotels, key=lambda x: x["value_score"], reverse=True)

    recommendations = {
        "top_rated_hotels": sorted_by_rating[:10],
        "best_value_for_money": sorted_by_value[:10],
        "luxury_stays": [h for h in clean_hotels if h["rating"] >= 4][-10:],
        "budget_friendly": sorted_by_price[:10],
        "closest_hotels": sorted(clean_hotels, key=lambda x: float(x["distance_km"] or 999))[:10],
    }

    return {
        "status": True,
        "message": "Hotel analysis completed",
        "recommendations": recommendations,
        "hotels": clean_hotels[:50]  # return first 50
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
