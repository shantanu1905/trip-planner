from fastapi import APIRouter, HTTPException, status, Query
from app.database.models import Trip , TravelOptions , HotelPreferences
from app.utils.auth_helpers import user_dependency
from app.database.database import db_dependency
from app.database.schemas import TrainSearchRequest , TravellingOptionsRequest , SaveTravelOptionsRequest , HotelPreferencesCreate , Settings
from datetime import datetime 
from typing import List, Optional
from app.utils.trains_utils import search_trains 
from app.task.trip_tasks import get_travelling_options
from app.utils.travel_options_analysis import analyze_trip_options
from app.utils.hotel_utils import search_hotels_easemytrip, analyze_hotels
from app.aiworkflow.get_trip_cost_breakdown import get_cost_breakdown
from fastapi.responses import JSONResponse
from app.utils.redis_utils import translate_with_cache
from app.utils.redis_utils import compute_trip_for_cost_breakdown_hash as compute_trip_hash
from app.database.redis_client import r, REDIS_TTL  
import json
router = APIRouter(prefix="/bookings", tags=["Get Booking Options & Recommendations"])

@router.post("/travellingoptions/create")
async def create_travelling_options(
    request: TravellingOptionsRequest,
    db: db_dependency,
    user: user_dependency
):
    """
    📘 Generate travelling options for a user's trip.

    This endpoint triggers a background Celery task that fetches available
    travel options (Train, Bus, Flight) based on the trip’s source and destination.
    
    ⚙️ This process may take a few seconds since it collects live travel data.
    """
    try:
        # ✅ Ensure user is authenticated
        if not user:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "status": False,
                    "data": None,
                    "message": "User not authenticated.",
                    "status_code": status.HTTP_401_UNAUTHORIZED,
                },
            )

        # ✅ Verify Trip Ownership
        trip = (
            db.query(Trip)
            .filter(Trip.id == request.trip_id, Trip.user_id == user.id)
            .first()
        )
        if not trip:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "status": False,
                    "data": None,
                    "message": "Trip not found or doesn't belong to you.",
                    "status_code": status.HTTP_404_NOT_FOUND,
                },
            )

        # ✅ Update journey dates
        trip.journey_start_date = request.journey_start_date
        trip.return_journey_date = request.return_journey_date
        db.commit()
        db.refresh(trip)

        # ✅ Check if travel options already exist
        existing_travel = (
            db.query(TravelOptions)
            .filter(TravelOptions.trip_id == trip.id)
            .first()
        )

        if existing_travel:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": True,
                    "data": existing_travel.original_travel_options,
                    "message": "Travel options already exist for this trip.",
                    "status_code": status.HTTP_200_OK,
                },
            )

        # ✅ Trigger Celery task for background processing
        get_travelling_options.delay(trip.id, user.id)

        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "status": True,
                "data": None,
                "message": "Processing travelling options for your selected destination.",
                "status_code": status.HTTP_202_ACCEPTED,
            },
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": False,
                "data": None,
                "message": f"Error creating travelling options: {str(e)}",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
        )

@router.get("/travellingoptions/{trip_id}")
async def get_travelling_options(
    trip_id: int,
    db: db_dependency,
    user: user_dependency
):
    """
    📘 Fetch all travelling options for a trip.

    Returns both user-selected and system-generated (original) travel options.
    If none are available, it provides a structured error message.
    Auto-translates response if user language != English.
    """
    try:
        # ✅ Verify Trip Ownership
        trip = (
            db.query(Trip)
            .filter(Trip.id == trip_id, Trip.user_id == user.id)
            .first()
        )

        if not trip:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "status": False,
                    "data": None,
                    "message": "Trip not found or doesn't belong to you.",
                    "status_code": status.HTTP_404_NOT_FOUND,
                },
            )

        # ✅ Fetch travel options
        existing_travel = (
            db.query(TravelOptions)
            .filter(TravelOptions.trip_id == trip.id)
            .first()
        )

        if not existing_travel:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "status": False,
                    "data": None,
                    "message": "No travel options found for this trip. Please create travelling options first.",
                    "status_code": status.HTTP_404_NOT_FOUND,
                },
            )

        # ✅ Build response data
        response_data = {
            "selected_travel_options": existing_travel.selected_travel_options,
            "all_travel_options": existing_travel.original_travel_options,
        }

        # ✅ Fetch user's preferred language
        settings = db.query(Settings).filter(Settings.user_id == user.id).first()
        target_lang = settings.native_language if settings and settings.native_language else "English"

        # ✅ Translate if needed
        if target_lang != "English":
            response_data = await translate_with_cache(response_data, target_lang)

        # ✅ Success
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": True,
                "data": response_data,
                "message": "Travel options fetched successfully.",
                "status_code": status.HTTP_200_OK,
            },
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": False,
                "data": None,
                "message": f"Error fetching travelling options: {str(e)}",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
        )

@router.post("/save-travelling-options")
async def save_travelling_options(
    request: SaveTravelOptionsRequest,
    db: db_dependency,
    user: user_dependency
):
    """
    📘 Save user's selected travelling option.

    This endpoint allows a user to select a preferred travelling option
    (Train, Bus, Flight, etc.) for a given trip and save it to the database.
    """
    try:
        # ✅ 1. Verify trip ownership
        trip = (
            db.query(Trip)
            .filter(Trip.id == request.trip_id, Trip.user_id == user.id)
            .first()
        )

        if not trip:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "status": False,
                    "data": None,
                    "message": "Trip not found or doesn't belong to you.",
                    "status_code": status.HTTP_404_NOT_FOUND,
                },
            )

        # ✅ 2. Fetch or create travel record
        travel_record = (
            db.query(TravelOptions)
            .filter(TravelOptions.trip_id == trip.id)
            .first()
        )

        if not travel_record:
            travel_record = TravelOptions(
                trip_id=trip.id,
                original_travel_options=[],
                selected_travel_options={}
            )
            db.add(travel_record)
            db.commit()
            db.refresh(travel_record)

        # ✅ 3. Save user's selected travel option
        selected_option = {
            "option_name": request.option_name,
            "legs": [leg.dict(by_alias=True) for leg in request.legs]
        }

        travel_record.selected_travel_options = selected_option
        db.commit()
        db.refresh(travel_record)

        # ✅ 4. Success response
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": True,
                "data": selected_option,
                "message": "Selected travelling option saved successfully.",
                "status_code": status.HTTP_200_OK,
            },
        )

    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": False,
                "data": None,
                "message": f"Error saving travelling options: {str(e)}",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
        )




@router.get("/analyze-travel-options/{trip_id}")
async def analyze_travel_options(
    trip_id: int,
    db: db_dependency,
    user: user_dependency
):
    """
    📊 Analyze user's selected travelling option.

    This endpoint performs analysis (like cost breakdown, duration, and mode efficiency)
    on the selected travelling option for a given trip.

    If no option is selected, the user is prompted to select one first.
    """
    try:
        # ✅ 1. Ensure user is authenticated
        if not user:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "status": False,
                    "data": None,
                    "message": "User not authenticated.",
                    "status_code": status.HTTP_401_UNAUTHORIZED,
                },
            )

        # ✅ 2. Verify Trip Ownership
        trip = (
            db.query(Trip)
            .filter(Trip.id == trip_id, Trip.user_id == user.id)
            .first()
        )

        if not trip:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "status": False,
                    "data": None,
                    "message": "Trip not found or doesn't belong to you.",
                    "status_code": status.HTTP_404_NOT_FOUND,
                },
            )

        # ✅ 3. Fetch Travel Options
        existing_travel = (
            db.query(TravelOptions)
            .filter(TravelOptions.trip_id == trip.id)
            .first()
        )

        if not existing_travel:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "status": False,
                    "data": None,
                    "message": "No travel options found for this trip.",
                    "status_code": status.HTTP_404_NOT_FOUND,
                },
            )

        # ✅ 4. Check if user selected any travel option
        if existing_travel.selected_travel_options:
            selected_options = existing_travel.selected_travel_options

            # 🔍 Perform Analysis (Custom business logic)
            travel_analysis = analyze_trip_options(selected_options)

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": True,
                    "data": {
                        "selected_travel_options": selected_options,
                        "travel_options_analysis": travel_analysis,
                    },
                    "message": "User-preferred travelling options analyzed successfully!",
                    "status_code": status.HTTP_200_OK,
                },
            )

        # ✅ 5. If user has not selected any option yet
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "status": False,
                "data": None,
                "message": "User has not selected travelling options. Please select options first.",
                "status_code": status.HTTP_202_ACCEPTED,
            },
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": False,
                "data": None,
                "message": f"Error processing travel options: {str(e)}",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
        )



@router.post("/hotel-preferences")
def create_or_update_hotel_preferences(
    payload: HotelPreferencesCreate, 
    db: db_dependency, 
    user: user_dependency
):
    """
    Create or update hotel preferences for a trip.
    """
    try:
        # ✅ Check if trip belongs to user
        trip = db.query(Trip).filter(Trip.id == payload.trip_id, Trip.user_id == user.id).first()
        if not trip:
            return {
                "status": False,
                "data": None,
                "message": "Trip not found or doesn't belong to the user.",
                "status_code": status.HTTP_404_NOT_FOUND,
            }

        # ✅ Check if preferences already exist for this trip
        existing_pref = db.query(HotelPreferences).filter(HotelPreferences.trip_id == payload.trip_id).first()

        if existing_pref:
            # --- Update existing preferences ---
            existing_pref.no_of_rooms = payload.no_of_rooms
            existing_pref.no_of_adult = trip.num_people    # Fetch from trip
            existing_pref.no_of_child = payload.no_of_child
            existing_pref.min_price = payload.min_price
            existing_pref.max_price = payload.max_price
            existing_pref.selected_property_types = payload.selected_property_types
            existing_pref.check_in_date = trip.start_date #fetch from trip
            existing_pref.check_out_date = trip.end_date #fetch from trip

            db.commit()
            db.refresh(existing_pref)

            return {
                "status": True,
                "data": existing_pref,
                "message": "Hotel preferences updated successfully.",
                "status_code": status.HTTP_200_OK,
            }

        # --- Create new preferences ---
        new_pref = HotelPreferences(
            trip_id=payload.trip_id,
            no_of_rooms=payload.no_of_rooms,
            no_of_adult=payload.no_of_adult,
            no_of_child=payload.no_of_child,
            min_price=payload.min_price,
            max_price=payload.max_price,
            selected_property_types=payload.selected_property_types,
            check_in_date=payload.check_in_date,
            check_out_date=payload.check_out_date
        )

        db.add(new_pref)
        db.commit()
        db.refresh(new_pref)

        return {
            "status": True,
            "data": new_pref,
            "message": "Hotel preferences created successfully.",
            "status_code": status.HTTP_201_CREATED,
        }

    except Exception as e:
        db.rollback()
        return {
            "status": False,
            "data": None,
            "message": f"Error processing hotel preferences: {str(e)}",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
        }


@router.get("/hotel-recommendations/{trip_id}")
def get_hotel_recommendations(trip_id: int,  db: db_dependency, user: user_dependency):
    """
    Endpoint to get analyzed hotel recommendations for a trip.
    """

    try:
        # Fetch preferences and trip details
        pref = db.query(HotelPreferences).filter(HotelPreferences.trip_id == trip_id).first()
        if not pref:
            raise HTTPException(status_code=404, detail=f"No hotel preferences found for trip_id {trip_id}")

        trip = db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            raise HTTPException(status_code=404, detail=f"No trip found with id {trip_id}")

        # Fetch hotel data
        hotels = search_hotels_easemytrip(
            destination=trip.destination,
            check_in=pref.check_in_date,
            check_out=pref.check_out_date,
            no_of_rooms=pref.no_of_rooms or 1,
            no_of_adult=pref.no_of_adult or 2,
            no_of_child=pref.no_of_child or 0,
            min_price=pref.min_price or 1,
            max_price=pref.max_price or 1000000,
            sort_type=pref.sort_type or "Popular|DESC"
        )

        # Analyze data
        analysis_result = analyze_hotels(hotels)

        return {
            "status": True,
            "data": analysis_result,
            "trip_info": {
                "trip_id": trip.id,
                "destination": trip.destination,
                "check_in": pref.check_in_date.strftime("%Y-%m-%d"),
                "check_out": pref.check_out_date.strftime("%Y-%m-%d")
            },
            "status_code": status.HTTP_200_OK
        }

    except Exception as e:
        return {
            "status": False,
            "data": None,
            "message": f"Error processing hotel recommendations: {str(e)}",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
        }




@router.get("/trip-cost-breakdown/{trip_id}")
def get_trip_cost_breakdown(trip_id: int, db: db_dependency, user : user_dependency , force_refresh: bool = False):
    """
    Endpoint to fetch detailed AI-driven trip cost breakdown including
    travel, hotel, and itinerary day-wise expenses, with caching.
    """
    try:
        # Validate trip exists
        trip = db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            raise HTTPException(status_code=404, detail=f"No trip found with id {trip_id}")

        user_id = user.id
        cache_key = f"expense_analysis:{trip_id}:{user_id}"
        source_hash = compute_trip_hash(db, trip_id)

        # Check Redis cache
        cached_data = r.get(cache_key)
        if cached_data:
            cached_json = json.loads(cached_data)
            if cached_json.get("source_hash") == source_hash and not force_refresh:
                return {
                    "status": True,
                    "cached": True,
                    "message": "Trip cost breakdown retrieved from cache",
                    "data": cached_json["data"],
                    "status_code": status.HTTP_200_OK
                }

        # Cache miss or data changed → run AI analysis
        fresh_data = get_cost_breakdown(user_id=user_id, trip_id=trip_id)

        if not fresh_data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI expense analysis returned empty result."
            )

        # Store in Redis
        r.set(cache_key, json.dumps({
            "source_hash": source_hash,
            "data": fresh_data
        }))

        return {
            "status": True,
            "cached": False,
            "message": "Trip cost breakdown generated successfully",
            "data": fresh_data,
            "status_code": status.HTTP_200_OK
        }

    except HTTPException as e:
        raise e

    except Exception as e:
        return {
            "status": False,
            "message": f"Error while generating trip cost breakdown: {str(e)}",
            "data": None,
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
        }






@router.post("/searchtrain", description="Search for trains between stations on a specific date")
async def search_train_api(request: TrainSearchRequest):
    try:
        from_station = request.from_station
        to_station = request.to_station
        travel_date = request.travel_date
        coupon_code = request.coupon_code

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

        # --- Generate booking URL ---
        from_name_clean = from_station.replace(" ", "")
        to_name_clean = to_station.replace(" ", "")
        travel_date_formatted = datetime.strptime(travel_date, "%d/%m/%Y").strftime("%d-%m-%Y")
        booking_url = f"https://railways.easemytrip.com/TrainListInfo/{from_name_clean}({from_station})-to-{to_name_clean}({to_station})/2/{travel_date_formatted}"

        # --- Success Response ---
        return {
            "status": True,
            "data": {
                "trains": trains_data,
                "booking_url": booking_url
            },
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






