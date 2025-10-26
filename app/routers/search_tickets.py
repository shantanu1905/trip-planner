from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from datetime import datetime
from app.database.models import Trip, TravelOptions, HotelPreferences
from app.utils.auth_helpers import user_dependency
from app.database.database import db_dependency
from app.database.schemas import TrainSearchRequest , BusSearchRequest , HotelSearchRequest
from app.utils.trains_utils import search_trains, get_all_station_code_name
from app.utils.bus_utils import get_all_city_autosuggest , get_all_bus_search_result
from app.utils.hotel_utils import search_hotels_easemytrip

from app.database.redis_client import r  # Redis client instance

import json

router = APIRouter(prefix="/search", tags=["Search Tickets & Hotel"])

# TTL for caching (10 minutes)
CACHE_TTL = 600


@router.post("/train", description="Search for trains between stations on a specific date , make sure enter date in DD/MM/YYYY format")
async def search_train_api(request: TrainSearchRequest):
    try:
        from_station = request.from_station.strip()
        to_station = request.to_station.strip()
        travel_date = request.travel_date.strip()
        coupon_code = request.coupon_code

        # --- Validate inputs ---
        if not from_station or not to_station or not travel_date:
            return {
                "status": False,
                "data": [],
                "message": "From station, to station, and travel date are required",
                "status_code": status.HTTP_400_BAD_REQUEST
            }

        # --- Format date ---
        try:
            if "-" in travel_date:
                travel_date = datetime.strptime(travel_date, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            return {
                "status": False,
                "data": [],
                "message": "Invalid date format. Please use DD/MM/YYYY or YYYY-MM-DD",
                "status_code": status.HTTP_400_BAD_REQUEST
            }

        # --- Create cache key ---
        cache_key = f"train_search:{from_station}:{to_station}:{travel_date}:{coupon_code or 'none'}"

        user_data = {
            "from_station": from_station,
            "to_station": to_station,
            "travel_date": travel_date,
            "booking_type": "Train"
        }

        # --- Check Redis cache ---
        cached_data = r.get(cache_key)
        if cached_data:
            cached_json = json.loads(cached_data)
            return {
                "status": True,
                "cached": True,
                "user_data" : user_data,
                "data": cached_json,
                "message": f"Cached results for {from_station} to {to_station} on {travel_date}",
                "status_code": status.HTTP_200_OK
            }

        # --- Call search function (live) ---
        trains_data = search_trains(from_station, to_station, travel_date, coupon_code)

        if trains_data is None:
            return {
                "status": False,
                "data": [],
                "message": "Error occurred while searching trains. Please try again.",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
            }

        if not trains_data:
            return {
                "status": True,
                "data": [],
                "message": "No trains found for the given route and date",
                "status_code": status.HTTP_200_OK
            }

        # --- Generate booking URL ---
        from_name_clean = from_station.replace(" ", "")
        to_name_clean = to_station.replace(" ", "")
        travel_date_formatted = datetime.strptime(travel_date, "%d/%m/%Y").strftime("%d-%m-%Y")
        booking_url = f"https://railways.easemytrip.com/TrainListInfo/{from_name_clean}({from_station})-to-{to_name_clean}({to_station})/2/{travel_date_formatted}"

        response_data = {
            "trains": trains_data,
            "booking_url": booking_url
        }

        # --- Save to Redis cache ---
        r.set(cache_key, json.dumps(response_data), ex=CACHE_TTL)

        return {
            "status": True,
            "cached": False,
            "user_data" : user_data,
            "data": response_data,
            "message": f"Found {len(trains_data)} trains for {from_station} to {to_station} on {travel_date}",
            "status_code": status.HTTP_200_OK
        }

    except Exception as e:
        return {
            "status": False,
            "data": [],
            "message": f"Error searching trains: {str(e)}",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
        }


@router.get("/autosuggest-stationname/{station_name}", description="Fetch all matching station codes and names from EaseMyTrip API")
async def get_station_code_api(station_name: str):
    try:
        station_name = station_name.strip()

        if not station_name:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "status": False,
                    "data": [],
                    "message": "Station name is required.",
                    "status_code": status.HTTP_400_BAD_REQUEST
                }
            )

        # --- Cache key ---
        cache_key = f"station_autosuggest:{station_name.lower()}"

        # --- Check Redis cache ---
        cached_data = r.get(cache_key)
        if cached_data:
            cached_json = json.loads(cached_data)
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": True,
                    "cached": True,
                    "data": cached_json,
                    "message": f"Cached result for '{station_name}'",
                    "status_code": status.HTTP_200_OK
                }
            )

        # --- Fetch all matching stations ---
        stations = get_all_station_code_name(station_name)

        if not stations:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "status": False,
                    "data": [],
                    "message": f"No stations found matching '{station_name}'.",
                    "status_code": status.HTTP_404_NOT_FOUND
                }
            )

        # --- Save result in Redis (TTL = 10 min) ---
        r.set(cache_key, json.dumps(stations), ex=CACHE_TTL)

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": True,
                "cached": False,
                "data": stations,
                "message": f"Found {len(stations)} station(s) matching '{station_name}'.",
                "status_code": status.HTTP_200_OK
            }
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": False,
                "data": [],
                "message": f"Error fetching station list: {str(e)}",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
            }
        )
    



@router.get("/autosuggest-cityname-bus/{place_name}", description="Fetch bus source city auto-suggestions from EaseMyTrip API")
async def get_bus_auto_suggest(place_name: str):
    """
    🔍 Fetches a list of city suggestions for bus routes using EaseMyTrip API.
    Uses Redis caching for 10 minutes.
    """
    try:
        # --- Validate input ---
        if not place_name.strip():
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "status": False,
                    "data": [],
                    "message": "Place name is required.",
                    "status_code": status.HTTP_400_BAD_REQUEST
                }
            )

        # --- Normalize cache key ---
        cache_key = f"bus_autosuggest:{place_name.strip().lower()}"

        # --- Check Redis Cache ---
        cached_data = r.get(cache_key)
        if cached_data:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": True,
                    "data": json.loads(cached_data),
                    "cached": True,
                    "message": f"Bus suggestions for '{place_name}' fetched from cache.",
                    "status_code": status.HTTP_200_OK
                }
            )

        # --- Fetch live data from API ---
        suggestions = get_all_city_autosuggest(place_name)

        # --- Handle empty result ---
        if not suggestions:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "status": False,
                    "data": [],
                    "message": f"No bus stations found matching '{place_name}'.",
                    "status_code": status.HTTP_404_NOT_FOUND
                }
            )

        # --- Cache result for 10 minutes ---
        r.set(cache_key, json.dumps(suggestions), ex=600)  # 600 seconds = 10 minutes

        # --- Success response ---
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": True,
                "data": suggestions,
                "cached": False,
                "message": f"Found bus city suggestions for '{place_name}'.",
                "status_code": status.HTTP_200_OK
            }
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": False,
                "data": [],
                "message": f"Error fetching bus city auto-suggestions: {str(e)}",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
            }
        )

@router.post("/bus", description="Search available buses between two cities on a specific date . make sure enter date in DD-MM-YYYY format")
async def search_bus_api(request: BusSearchRequest):
    try:
        from_city = request.from_city.strip() if request.from_city else None
        to_city = request.to_city.strip() if request.to_city else None
        journey_date = request.journey_date
        from_city_id = request.from_city_id
        to_city_id = request.to_city_id

        # --- Validate inputs ---
        if not (from_city_id and to_city_id):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "status": False,
                    "data": None,
                    "message": "Provide both source and destination city IDs.",
                    "status_code": status.HTTP_400_BAD_REQUEST,
                },
            )

        # --- Normalize date ---
        if journey_date:
            try:
                if "-" in journey_date and journey_date.count("-") == 2:
                    # Accept both DD-MM-YYYY and YYYY-MM-DD formats
                    if journey_date.split("-")[0].isdigit() and len(journey_date.split("-")[0]) == 4:
                        # YYYY-MM-DD -> convert to DD-MM-YYYY
                        date_obj = datetime.strptime(journey_date, "%Y-%m-%d")
                        journey_date = date_obj.strftime("%d-%m-%Y")
            except ValueError:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "status": False,
                        "data": None,
                        "message": "Invalid date format. Use DD-MM-YYYY or YYYY-MM-DD.",
                        "status_code": status.HTTP_400_BAD_REQUEST,
                    },
                )

        # --- Generate cache key ---
        cache_key = f"bus_search:{from_city_id}:{to_city_id}:{journey_date or 'default'}"

        user_data = {
            "from_city": from_city,
            "to_city": to_city,
            "journey_date": journey_date,
            "from_city_id": from_city_id,
            "to_city_id": to_city_id,
            "booking_type": "Bus"
        }

        # --- Check cache ---
        cached = r.get(cache_key)
        if cached:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": True,
                    "user_data" : user_data,
                    "data": json.loads(cached),
                    "cached": True,
                    "message": f"Bus search results (cached) for IDs {from_city_id} → {to_city_id}",
                    "status_code": status.HTTP_200_OK,
                },
            )

        # --- Perform live search ---
        result = get_all_bus_search_result(from_city, to_city, journey_date, from_city_id, to_city_id)

        # --- Only cache if result is successful ---
        if result["status"] and result.get("data") is not None:
            r.setex(cache_key, 600, json.dumps(result["data"]))  # TTL 10 min

        # --- Return full API response as-is ---
        return JSONResponse(
            status_code=status.HTTP_200_OK if result["status"] else status.HTTP_400_BAD_REQUEST,
            content={
                "status": result["status"],
                "user_data" : user_data,
                "data": result.get("data"),  # full EaseMyTrip API response
                "cached": False,
                "message": result["message"],
                "status_code": status.HTTP_200_OK if result["status"] else status.HTTP_400_BAD_REQUEST,
            },
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": False,
                "data": None,
                "message": f"Error searching buses: {str(e)}",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
        )
    


@router.post("/search_hotels", description="Search hotels on EaseMyTrip, date format DD/MM/YYYY or YYYY-MM-DD")
async def search_hotels_api(request: HotelSearchRequest):
    try:
        destination = request.destination.strip()
        check_in = request.check_in.strip()
        check_out = request.check_out.strip()
        no_of_rooms = request.no_of_rooms
        no_of_adult = request.no_of_adult
        no_of_child = request.no_of_child
        no_of_results = request.no_of_results

        # --- Validate inputs ---
        if not destination or not check_in or not check_out:
            return {
                "status": False,
                "data": [],
                "message": "Destination, check-in and check-out dates are required",
                "status_code": status.HTTP_400_BAD_REQUEST
            }

        # --- Format dates ---
        try:
            if "-" in check_in:
                check_in_date = datetime.strptime(check_in, "%d-%m-%Y")
            else:
                check_in_date = datetime.strptime(check_in, "%d/%m/%Y")
            
            if "-" in check_out:
                check_out_date = datetime.strptime(check_out, "%d-%m-%Y")
            else:
                check_out_date = datetime.strptime(check_out, "%d/%m/%Y")
        except ValueError:
            return {
                "status": False,
                "data": [],
                "message": "Invalid date format. Please use DD/MM/YYYY or YYYY-MM-DD",
                "status_code": status.HTTP_400_BAD_REQUEST
            }

        # --- Create cache key ---
        cache_key = f"hotel_search:{destination}:{check_in}:{check_out}:{no_of_rooms}:{no_of_adult}:{no_of_child}:{destination}:{no_of_results}"

        user_data = {
            "destination": destination,
            "check_in": check_in,
            "check_out": check_out,
            "no_of_rooms": no_of_rooms,
            "no_of_adult": no_of_adult,
            "no_of_child": no_of_child,
            "no_of_results": no_of_results ,
            "booking_type": "Hotel" 
        }

        # --- Check Redis cache ---
        cached_data = r.get(cache_key)
        if cached_data:
            cached_json = json.loads(cached_data)
            return {
                "status": True,
                "cached": True,
                "user_data" : user_data,
                "data": cached_json,
                "message": f"Cached results for hotels in {destination} from {check_in} to {check_out}",
                "status_code": status.HTTP_200_OK
            }

        # --- Call search function (live) ---
        hotels_data = search_hotels_easemytrip(
            destination=destination,
            check_in=check_in_date,
            check_out=check_out_date,
            no_of_rooms=no_of_rooms,
            no_of_adult=no_of_adult,
            no_of_child=no_of_child,
            no_of_results=no_of_results
        )

        if hotels_data is None:
            return {
                "status": False,
                "data": [],
                "message": "Error occurred while searching hotels. Please try again.",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
            }

        if not hotels_data:
            return {
                "status": True,
                "data": [],
                "message": "No hotels found for the given search criteria",
                "status_code": status.HTTP_200_OK
            }

        # --- Save to Redis cache ---
        r.set(cache_key, json.dumps(hotels_data), ex=CACHE_TTL)

        return {
            "status": True,
            "cached": False,
            "user_data" : user_data,
            "data": hotels_data,
            "message": f"Found {len(hotels_data)} hotels in {destination} from {check_in} to {check_out}",
            "status_code": status.HTTP_200_OK
        }

    except Exception as e:
        return {
            "status": False,
            "data": [],
            "message": f"Error searching hotels: {str(e)}",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
        }