from fastapi import APIRouter, HTTPException, status, Query
from app.database.models import Trip , TravelOptions , HotelPreferences , TrainBookingInfo , BusBookingInfo, HotelBookingInfo
from app.utils.auth_helpers import user_dependency
from app.database.database import db_dependency
from app.database.schemas import TrainBookingCreate , TravellingOptionsRequest , SaveTravelOptionsRequest , HotelPreferencesCreate , Settings , BusBookingCreate , HotelBookingCreate
from app.task.trip_tasks import get_travelling_options
from app.utils.travel_options_analysis import analyze_trip_options
from app.utils.hotel_utils import search_hotels_easemytrip, analyze_hotels
from app.aiworkflow.get_trip_cost_breakdown import get_cost_breakdown
from fastapi.responses import JSONResponse
from app.utils.redis_utils import translate_with_cache
from app.utils.redis_utils import compute_trip_for_cost_breakdown_hash as compute_trip_hash
from app.database.redis_client import r, REDIS_TTL  
import json
from sqlalchemy.orm import joinedload
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
async def get_all_travelling_options(
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
            no_of_adult=trip.num_people,
            no_of_child=payload.no_of_child,
            min_price=payload.min_price,
            max_price=payload.max_price,
            selected_property_types=payload.selected_property_types,
            check_in_date=trip.start_date,
            check_out_date=trip.end_date
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






@router.post("/train", description="📘 Create a train booking entry for a trip.")
async def book_train(
    request: TrainBookingCreate,
    db: db_dependency,
    user: user_dependency
):
    """
    🚆 Book a train for a user's trip.
    
    This endpoint stores selected train booking details for the trip, ensuring:
    - ✅ User authentication
    - ✅ Ownership validation
    - ✅ Duplicate prevention

    **Example Request:**
    ```json
    {
        "trip_id": 1,
        "booking_type": "Train",
        "from_station": "MMCT",
        "to_station": "NGP",
        "travel_date": "2025-11-22",
        "train_name": "Ltt Bbs Express",
        "train_number": "12879",
        "arrival_time": "13:35",
        "departure_time": "00:15",
        "duration": "13:20",
        "distance": "821",
        "from_stn_name": "Lokmanyatilak Terminus Kurla",
        "from_stn_code": "LTT",
        "to_stn_name": "Nagpur",
        "to_stn_code": "NGP",
        "arrival_date": "22Nov2025",
        "departure_date": "22Nov2025",
        "enq_class": "2A",
        "quota_name": "General",
        "total_fare": 1715.0
    }
    ```
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
        trip = db.query(Trip).filter(
            Trip.id == request.trip_id,
            Trip.user_id == user.id
        ).first()

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

        # ✅ Prevent duplicate booking for same train on same date
        existing_booking = db.query(TrainBookingInfo).filter(
            TrainBookingInfo.trip_id == request.trip_id,
            TrainBookingInfo.train_number == request.train_number,
            TrainBookingInfo.from_station == request.from_station,
            TrainBookingInfo.to_station == request.to_station,
            TrainBookingInfo.travel_date == request.travel_date
        ).first()

        if existing_booking:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "status": False,
                    "data": {
                        "existing_booking_id": existing_booking.id,
                        "train_number": existing_booking.train_number,
                        "train_name": existing_booking.train_name
                    },
                    "message": "Train booking already exists for this trip.",
                    "status_code": status.HTTP_409_CONFLICT,
                },
            )

        # ✅ Create train booking entry
        booking = TrainBookingInfo(
            trip_id=request.trip_id,
            booking_type=request.booking_type,
            from_station=request.from_station,
            to_station=request.to_station,
            travel_date=request.travel_date,
            train_name=request.train_name,
            train_number=request.train_number,
            arrival_time=request.arrival_time,
            departure_time=request.departure_time,
            duration=request.duration,
            distance=request.distance,
            from_stn_name=request.from_stn_name,
            from_stn_code=request.from_stn_code,
            to_stn_name=request.to_stn_name,
            to_stn_code=request.to_stn_code,
            arrival_date=request.arrival_date,
            departure_date=request.departure_date,
            enq_class=request.enq_class,
            quota_name=request.quota_name,
            total_fare=request.total_fare,
        )

        db.add(booking)
        db.commit()
        db.refresh(booking)

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "status": True,
                "data": {
                    "booking_id": booking.id,
                    "train_number": booking.train_number,
                    "train_name": booking.train_name,
                    "travel_date": str(booking.travel_date)
                },
                "message": "Train booking created successfully.",
                "status_code": status.HTTP_201_CREATED,
            },
        )

    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": False,
                "data": None,
                "message": f"Error creating train booking: {str(e)}",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
        )
    



@router.post("/bus", description="🚌 Create a bus booking entry for a trip.")
async def book_bus(
    request: BusBookingCreate,
    db: db_dependency,
    user: user_dependency
):
    """
    🚌 Book a bus for a user's trip.
    
    This endpoint stores selected bus booking details for the trip.

    - ✅ Ensures user authentication  
    - ✅ Verifies trip ownership  
    - ✅ Prevents duplicate bookings  

    **Example Request:**
    ```json
    {
        "trip_id": 1,
        "booking_type": "Bus",
        "from_city": "Delhi",
        "to_city": "Dehradun",
        "journey_date": "01-11-2025",
        "from_city_id": 733,
        "to_city_id": 777,
        "boarding_point_name": "Kashmere Gate",
        "boarding_point_id": "303",
        "boarding_point_location": "Kashmere Gate,Platform no.59,60 Kashmiri Gate",
        "dropping_point_id": "26",
        "dropping_point_name": "Near ISBT Dehradun",
        "dropping_point_location": "Rao Travels,Near ISBT Dehradun, near rao Travels",
        "travels_name": "YOLO BUS",
        "bus_type": "Bharat Benz A/C Semi Sleeper (2+2)",
        "ac": true,
        "departure_time": "23:40",
        "arrival_time": "05:17",
        "duration": "05h 37m",
        "doj": "2025-11-01T11:40:00",
        "route_id": "2716",
        "bus_id": "5862188",
        "bus_key": "b5913",
        "total_fare": 299.0
    }
    ```
    """
    try:
        # ✅ Ensure user is authenticated
        if not user:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "status": False,
                    "message": "User not authenticated.",
                    "status_code": status.HTTP_401_UNAUTHORIZED,
                    "data": None,
                },
            )

        # ✅ Verify Trip Ownership
        trip = db.query(Trip).filter(
            Trip.id == request.trip_id,
            Trip.user_id == user.id
        ).first()

        if not trip:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "status": False,
                    "message": "Trip not found or doesn't belong to you.",
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "data": None,
                },
            )

        # ✅ Prevent duplicate booking
        existing_booking = db.query(BusBookingInfo).filter(
            BusBookingInfo.trip_id == request.trip_id,
            BusBookingInfo.bus_id == request.bus_id,
            BusBookingInfo.journey_date == request.journey_date
        ).first()

        if existing_booking:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "status": False,
                    "message": "Bus booking already exists for this trip.",
                    "status_code": status.HTTP_409_CONFLICT,
                    "data": {
                        "booking_id": existing_booking.id,
                        "bus_id": existing_booking.bus_id,
                        "travels_name": existing_booking.travels_name,
                        "journey_date": str(existing_booking.journey_date)
                    },
                },
            )

        # ✅ Create bus booking entry
        booking = BusBookingInfo(
            trip_id=request.trip_id,
            booking_type=request.booking_type,
            from_city=request.from_city,
            to_city=request.to_city,
            journey_date=request.journey_date,
            from_city_id=request.from_city_id,
            to_city_id=request.to_city_id,
            boarding_point_name=request.boarding_point_name,
            boarding_point_id=request.boarding_point_id,
            boarding_point_location=request.boarding_point_location,
            boarding_point_long_name=request.boarding_point_long_name,
            dropping_point_id=request.dropping_point_id,
            dropping_point_name=request.dropping_point_name,
            dropping_point_location=request.dropping_point_location,
            travels_name=request.travels_name,
            bus_type=request.bus_type,
            ac=request.ac,
            departure_time=request.departure_time,
            arrival_time=request.arrival_time,
            duration=request.duration,
            doj=request.doj,
            route_id=request.route_id,
            bus_id=request.bus_id,
            bus_key=request.bus_key,
            total_fare=request.total_fare,
        )

        db.add(booking)
        db.commit()
        db.refresh(booking)

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "status": True,
                "message": "Bus booking created successfully.",
                "status_code": status.HTTP_201_CREATED,
                "data": {
                    "booking_id": booking.id,
                    "bus_id": booking.bus_id,
                    "travels_name": booking.travels_name,
                    "journey_date": str(booking.journey_date)
                },
            },
        )

    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": False,
                "message": f"Error creating bus booking: {str(e)}",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "data": None,
            },
        )
    



@router.post("/hotel", description="🏨 Create a hotel booking entry for a trip.")
async def book_hotel(
    request: HotelBookingCreate,  # Pydantic schema (defined below)
    db: db_dependency,
    user: user_dependency
):
    """
    🏨 Create a hotel booking for a user's trip.

    This endpoint saves selected hotel details for a specific trip.
    It ensures:
    - The user is authenticated.
    - The trip belongs to the user.
    - The same hotel booking isn't duplicated.

    **Example Request:**
    ```json
    {
        "trip_id": 1,
        "booking_type": "Hotel",
        "destination": "Goa",
        "check_in": "2025-12-10",
        "check_out": "2025-12-13",
        "no_of_rooms": 2,
        "no_of_adult": 3,
        "no_of_child": 1,
        "adrs": "Calangute Beach Road, Goa",
        "nm": "The Beach Resort",
        "lat": 15.5523,
        "lon": 73.7551,
        "prc": 5899.0,
        "rat": "4.5",
        "tax": 500.0,
        "disc": 300.0,
        "hid": "H12345",
        "catgry": "Resort",
        "cName": "Deluxe Room",
        "ecid": "E56789",
        "durl": "https://example.com/hotel/the-beach-resort",
        "cinTime": "12:00 PM",
        "coutTime": "11:00 AM",
        "lnFare": 6199.0,
        "appfare": 5899.0
    }
    ```
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
        trip = db.query(Trip).filter(
            Trip.id == request.trip_id,
            Trip.user_id == user.id
        ).first()

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

        # ✅ Prevent duplicate hotel bookings for same trip + hotel + dates
        existing_booking = db.query(HotelBookingInfo).filter(
            HotelBookingInfo.trip_id == request.trip_id,
            HotelBookingInfo.hid == request.hid,
            HotelBookingInfo.check_in == request.check_in,
            HotelBookingInfo.check_out == request.check_out
        ).first()

        if existing_booking:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": True,
                    "data": {
                        "booking_id": existing_booking.id,
                        "hotel_name": existing_booking.nm,
                        "check_in": str(existing_booking.check_in),
                        "check_out": str(existing_booking.check_out),
                    },
                    "message": "Hotel booking already exists for this trip.",
                    "status_code": status.HTTP_200_OK,
                },
            )

        # ✅ Create new hotel booking entry
        booking = HotelBookingInfo(
            trip_id=request.trip_id,
            booking_type=request.booking_type,
            destination=request.destination,
            check_in=request.check_in,
            check_out=request.check_out,
            no_of_rooms=request.no_of_rooms,
            no_of_adult=request.no_of_adult,
            no_of_child=request.no_of_child,
            adrs=request.adrs,
            nm=request.nm,
            lat=request.lat,
            lon=request.lon,
            prc=request.prc,
            rat=request.rat,
            tax=request.tax,
            disc=request.disc,
            hid=request.hid,
            catgry=request.catgry,
            cName=request.cName,
            ecid=request.ecid,
            durl=request.durl,
            cinTime=request.cinTime,
            coutTime=request.coutTime,
            lnFare=request.lnFare,
            appfare=request.appfare,
        )

        db.add(booking)
        db.commit()
        db.refresh(booking)

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "status": True,
                "data": {
                    "booking_id": booking.id,
                    "hotel_name": booking.nm,
                    "check_in": str(booking.check_in),
                    "check_out": str(booking.check_out)
                },
                "message": "Hotel booking created successfully.",
                "status_code": status.HTTP_201_CREATED,
            },
        )

    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": False,
                "data": None,
                "message": f"Error creating hotel booking: {str(e)}",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
        )
    





@router.get("/bookings/show-trip-bookings", description="📘 Get all bookings (Train, Bus, Hotel) for the authenticated user.")
async def get_all_bookings_grouped(
    db: db_dependency,
    user: user_dependency
):
    """
    🧾 Fetch all bookings (Train, Bus, Hotel) grouped by each trip_id.
    Shows separate count and list for each trip.
    """
    try:
        # ✅ Ensure user authenticated
        if not user:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "status": False,
                    "data": None,
                    "message": "User not authenticated.",
                    "status_code": status.HTTP_401_UNAUTHORIZED
                },
            )

        # ✅ Fetch user trips with related bookings
        trips = (
            db.query(Trip)
            .options(
                joinedload(Trip.train_booking_info),
                joinedload(Trip.bus_booking_info),
                joinedload(Trip.hotel_booking_info)
            )
            .filter(Trip.user_id == user.id)
            .all()
        )

        if not trips:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "status": True,
                    "data": [],
                    "message": "No trips or bookings found for this user.",
                    "status_code": status.HTTP_404_NOT_FOUND
                },
            )

        # ✅ Group bookings by trip
        grouped_data = []

        for trip in trips:
            trip_bookings = []

            # 🟩 Train Bookings
            if trip.train_booking_info:
                for t in trip.train_booking_info:
                    trip_bookings.append({
                        "type": "Train",
                        "train_name": t.train_name,
                        "train_number": t.train_number,
                        "from_station": t.from_stn_name,
                        "to_station": t.to_stn_name,
                        "travel_date": str(t.travel_date),
                        "fare": t.total_fare,
                        "is_booked": t.is_booked
                    })

            # 🟦 Bus Bookings
            if trip.bus_booking_info:
                for b in trip.bus_booking_info:
                    trip_bookings.append({
                        "type": "Bus",
                        "travels_name": b.travels_name,
                        "bus_type": b.bus_type,
                        "from_city": b.from_city,
                        "to_city": b.to_city,
                        "journey_date": str(b.journey_date),
                        "fare": b.total_fare,
                        "is_booked": b.is_booked
                    })

            # 🟨 Hotel Bookings
            if trip.hotel_booking_info:
                for h in trip.hotel_booking_info:
                    trip_bookings.append({
                        "type": "Hotel",
                        "hotel_name": h.nm,
                        "destination": h.destination,
                        "check_in": str(h.check_in),
                        "check_out": str(h.check_out),
                        "price": h.prc,
                        "rating": h.rat,
                        "is_booked": h.is_booked
                    })

            grouped_data.append({
                "trip_id": trip.id,
                "trip_name": trip.trip_name if hasattr(trip, "trip_name") else None,
                "total_bookings": len(trip_bookings),
                "bookings": trip_bookings
            })

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": True,
                "data": grouped_data,
                "message": "All user bookings grouped by trip_id retrieved successfully.",
                "status_code": status.HTTP_200_OK
            },
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": False,
                "data": None,
                "message": f"Error fetching bookings: {str(e)}",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
            },
        )