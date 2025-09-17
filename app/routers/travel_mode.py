from fastapi import APIRouter, HTTPException, status, Query
from app.database.models import Trip , TravelOptions , UserPreferences
from app.utils.auth_helpers import user_dependency
from app.database.database import db_dependency
from app.task.trip_tasks import process_travel_modes
from app.database.schemas import TrainSearchRequest
import datetime
from typing import List, Optional
from app.utils.easemytrip import search_trains , get_station_code
import httpx
import json


router = APIRouter(prefix="/travel_mode", tags=["Trains/Bus/Flight"])


def get_time_period(hour):
    """Return time period based on 24-hour time."""
    if 5 <= hour < 12:
        return "Morning"
    elif 12 <= hour < 17:
        return "Afternoon"
    elif 17 <= hour < 21:
        return "Evening"
    else:
        return "Night"

@router.post("/searchtrain", description="Search for trains between stations on a specific date")
async def search_train(request: TrainSearchRequest):
    try:
        from_station = request.from_station
        to_station = request.to_station
        travel_date = request.travel_date
        coupon_code = request.coupon_code
        time_filter = request.time_filter  # Optional: Morning, Afternoon, Evening, Night

        # --- Convert date if in YYYY-MM-DD format ---
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

        # --- Validate inputs ---
        if not from_station or not to_station or not travel_date:
            return {
                "status": False,
                "data": [],
                "message": "From station, to station, and travel date are required",
                "status_code": status.HTTP_400_BAD_REQUEST
            }

        # --- Call search function ---
        trains_data = search_trains(from_station, to_station, travel_date, coupon_code)

        # --- Handle API errors ---
        if trains_data is None:
            return {
                "status": False,
                "data": [],
                "message": "Error occurred while searching trains. Please try again.",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
            }

        # --- No trains found ---
        if not trains_data:
            return {
                "status": True,
                "data": [],
                "message": "No trains found for the given route and date",
                "status_code": status.HTTP_200_OK
            }

        # --- Apply Time Filter if requested and departureTime exists ---
        if time_filter:
            filtered_trains = []
            for train in trains_data:
                dep_time = train.get("departureTime")
                if dep_time:  # Only if departure time is available
                    hour = int(dep_time.split(":")[0])
                    if get_time_period(hour) == time_filter:
                        filtered_trains.append(train)
            trains_data = filtered_trains

        # --- Success Response ---
        return {
            "status": True,
            "data": trains_data,
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



@router.get("/get/{trip_id}")
async def get_travel_modes(trip_id: int, db: db_dependency, user: user_dependency):
    try:
        trip = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user.id).first()
        if not trip:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trip not found or doesn't belong to you."
            )

        # Check if travel options already exist
        existing_travel = db.query(TravelOptions).filter(TravelOptions.trip_id == trip.id).first()
        if existing_travel:
            return {
                "status": True,
                "data": existing_travel.travel_data,
                "message": "Travel options fetched from cache",
                "status_code": status.HTTP_200_OK
            }

        # Trigger background task for travel modes
        process_travel_modes.delay(trip.id, user.id)

        return {
            "status": True,
            "data": None,
            "message": "Travel modes processing started in background",
            "status_code": status.HTTP_202_ACCEPTED
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error triggering travel modes processing: {str(e)}"
        )














# @router.get("/get-travel-booking-suggestion/{trip_id}")
# async def get_travel_booking_suggestion(
#     trip_id: int,
#     db: db_dependency,
#     user: user_dependency
# ):
#     try:
#         # 1. Fetch Trip
#         trip = db.query(Trip).filter(
#             Trip.id == trip_id,
#             Trip.user_id == user.id
#         ).first()

#         if not trip:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="Trip not found or doesn't belong to you."
#             )

#         # 2. Minimal Trip data
#         trip_data = {
#             "trip_id": trip.id,
#             "journey_start_date": trip.journey_start_date.isoformat() if trip.journey_start_date else None,
#             "return_journey_date": trip.return_journey_date.isoformat() if trip.return_journey_date else None,
#             "travel_mode": trip.travel_mode.value if trip.travel_mode else None
#         }

#         # 3. UserPreferences only for Train or Train&Road
#         user_pref_data = {}
#         if trip.travel_mode and trip.travel_mode.value in ["Train", "Train&Road"]:
#             user_pref = db.query(UserPreferences).filter(
#                 UserPreferences.user_id == user.id
#             ).first()
#             if user_pref:
#                 user_pref_data = {
#                     "preferred_train_class": user_pref.preferred_train_class.value if user_pref.preferred_train_class else None,
#                     "preferred_departure_time": user_pref.preferred_departure_time.value if user_pref.preferred_departure_time else None,
#                     "preferred_from_station": user_pref.preferred_from_station,
#                     "flexible_station_option": user_pref.flexible_station_option
#                 }

#         # 4. Fetch saved TravelOptions (if any)
#         saved_travel_options = db.query(TravelOptions).filter(
#             TravelOptions.trip_id == trip.id
#         ).first()
#         travel_options_data = saved_travel_options.travel_data if saved_travel_options else None

#         # 5. Prepare final payload
#         payload = {
#             "trip": trip_data,
#             "user_preferences": user_pref_data,
#             "saved_travel_options": travel_options_data
#         }

#         # 6. Call external webhook
#         async with httpx.AsyncClient(timeout=600.0) as client:
#             response = await client.post(
#                 "http://localhost:5678/webhook/Get-booking-suggestions",
#                 json=payload
#             )

#         if response.status_code != 200:
#             raise HTTPException(
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#                 detail="Failed to fetch travel booking suggestion"
#             )

#         full_data = response.json()

#         # 7. Extract travel_options
#         travel_options = full_data.get("travel_options")
#         if not travel_options:
#             raise HTTPException(
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#                 detail="Invalid response from travel booking suggestion webhook"
#             )

#         # 8. Save new travel options if not already cached
#         if not saved_travel_options:
#             new_travel = TravelOptions(trip_id=trip.id, travel_data=travel_options)
#             db.add(new_travel)
#             db.commit()
#             db.refresh(new_travel)

#         return {
#             "status": True,
#             "data": {
#                 "trip": trip_data,
#                 "user_preferences": user_pref_data,
#                 "travel_options": travel_options
#             },
#             "message": "Travel booking suggestions fetched successfully",
#             "status_code": status.HTTP_200_OK
#         }

#     except HTTPException as e:
#         raise e
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Error fetching travel booking suggestions: {str(e)}"
#         )
def extract_station_name(raw_name: str) -> str:
    """
    Extract the first word of the station/city name.
    Works for:
      - "Mumbai (CSTM)" → "Mumbai"
      - "Pune" → "Pune"
      - "Haridwar, Uttarakhand, India" → "Haridwar"
    """
    # Remove parentheses content first
    cleaned_name = raw_name.split("(")[0].strip()
    # Take first word before any comma or space
    first_word = cleaned_name.split(",")[0].split()[0].strip()
    return first_word



# --- Main Endpoint ---
@router.get("/get-travel-booking-suggestion/{trip_id}")
async def get_travel_booking_suggestion(
    trip_id: int,
    db: db_dependency,
    user: user_dependency
):
    try:
        # 1. Fetch Trip
        trip = db.query(Trip).filter(
            Trip.id == trip_id,
            Trip.user_id == user.id
        ).first()

        if not trip:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trip not found or doesn't belong to you."
            )

        # 2. Trip data
        trip_data = {
            "trip_id": trip.id,
            "journey_start_date": trip.journey_start_date.isoformat() if trip.journey_start_date else None,
            "return_journey_date": trip.return_journey_date.isoformat() if trip.return_journey_date else None,
            "travel_mode": trip.travel_mode.value if trip.travel_mode else None
        }

        # 3. UserPreferences for Train or Train&Road
        user_pref_data = {}
        preferred_departure_time = None
        if trip.travel_mode and trip.travel_mode.value in ["Train", "Train&Road"]:
            user_pref = db.query(UserPreferences).filter(
                UserPreferences.user_id == user.id
            ).first()
            if user_pref:
                preferred_departure_time = user_pref.preferred_departure_time.value if user_pref.preferred_departure_time else None
                user_pref_data = {
                    "preferred_train_class": user_pref.preferred_train_class.value if user_pref.preferred_train_class else None,
                    "preferred_departure_time": preferred_departure_time,
                    "preferred_from_station": user_pref.preferred_from_station,
                    "flexible_station_option": user_pref.flexible_station_option
                }

        # 4. Fetch saved TravelOptions
        saved_travel_options = db.query(TravelOptions).filter(
            TravelOptions.trip_id == trip.id
        ).first()
        travel_options_data = saved_travel_options.travel_data if saved_travel_options else None

        # --- Process each leg ---
        booking_recommendation = {"from": None, "to": []}

        if travel_options_data and "legs" in travel_options_data:
            booking_recommendation["from"] = travel_options_data.get("from")
            
            for leg in travel_options_data["legs"]:
                mode = leg.get("mode")
                from_station_raw = leg.get("from")
                to_station_raw = leg.get("to")
                travel_date = trip.journey_start_date.strftime("%d/%m/%Y") if trip.journey_start_date else None

                leg_result = {
                    "destination": to_station_raw,
                    "travel_mode": mode,
                    "date": travel_date,
                    "status": "not_found",
                    "details": {},
                    "booking_url": None
                }

                # --- Train ---
                if mode == "Train":
                    from_station_clean = extract_station_name(from_station_raw)
                    to_station_clean = extract_station_name(to_station_raw)

                    


                    from_code, from_name = get_station_code(from_station_clean)
                    to_code, to_name = get_station_code(to_station_clean)

                

                    

                    if from_code and to_code:
                        trains = search_trains(from_code, to_code, travel_date)

                        # Apply preferred departure time filter
                        if preferred_departure_time and trains:
                            filtered_trains = []
                            for train in trains:
                                dep_time = train.get("departureTime")
                                if dep_time:
                                    dep_hour = int(dep_time.split(":")[0])
                                    train_period = get_time_period(dep_hour)
                                    if train_period == preferred_departure_time:
                                        filtered_trains.append(train)
                            trains = filtered_trains

                        if trains:
                            leg_result["status"] = "success"
                            leg_result["details"]["Trains"] = trains
                        else:
                            leg_result["status"] = "not_found"

                        from_name_clean = from_name.replace(" ", "")
                        to_name_clean = to_name.replace(" ", "")
                        # Format date as DD-MM-YYYY
                        # Format travel date as DD-MM-YYYY
                        travel_date_formatted = trip.journey_start_date.strftime("%d-%m-%Y") if trip.journey_start_date else ""
                        # --- Add booking URL ---
                        leg_result["booking_url"] = f"https://railways.easemytrip.com/TrainListInfo/{from_name_clean}({from_code})-to-{to_name_clean}({to_code})/2/{travel_date_formatted}"

                    else:
                        leg_result["status"] = "not_found"

                # --- Bus ---
                elif mode == "Bus":
                    leg_result["status"] = "success"
                    leg_result["details"]["Buses"] = [{
                        "busName": leg.get("Note"),
                        "fromCity": from_station_raw,
                        "toCity": to_station_raw,
                        "approx_cost": leg.get("approx_cost"),
                        "approx_time": leg.get("approx_time")
                    }]

                # --- Trek / Cab ---
                elif mode in ["Trek", "Cab"]:
                    leg_result["status"] = "not_available"
                    leg_result["details"]["Note"] = leg.get("Note")

                booking_recommendation["to"].append(leg_result)

        return {
            "status": True,
            "data": booking_recommendation,
            "message": "Travel booking suggestions fetched successfully",
            "status_code": status.HTTP_200_OK
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching travel booking suggestions: {str(e)}"
        )