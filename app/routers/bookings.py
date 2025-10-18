from fastapi import APIRouter, HTTPException, status, Query
from app.database.models import Trip , TravelOptions , UserPreferences
from app.utils.auth_helpers import user_dependency
from app.database.database import db_dependency
from app.database.schemas import TrainSearchRequest , TravellingOptionsRequest
from datetime import datetime 
from typing import List, Optional
from app.utils.easemytrip import search_trains 
from app.task.trip_tasks import get_travelling_options

router = APIRouter(prefix="/bookings", tags=["Trains/Bus/Flight"])

@router.post("/travellingoptions")
async def get_travel_options(
    request: TravellingOptionsRequest,
    db: db_dependency,
    user: user_dependency
):
    try:
        # ✅ 1. Ensure user is authenticated
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not authenticated."
            )

        # ✅ 2. Fetch trip & verify ownership
        trip = (
            db.query(Trip)
            .filter(Trip.id == request.trip_id, Trip.user_id == user.id)
            .first()
        )
        if not trip:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trip not found or doesn't belong to you."
            )

        # ✅ 3. Save journey dates to trip (if updated in request)
        trip.journey_start_date = request.journey_start_date
        trip.return_journey_date = request.return_journey_date
        db.commit()
        db.refresh(trip)

        # ✅ 4. Check if travel options already exist
        existing_travel = (
            db.query(TravelOptions)
            .filter(TravelOptions.trip_id == trip.id)
            .first()
        )

        if existing_travel:
            # Prefer user-selected options if available
            if existing_travel.selected_travel_options:
                return {
                    "status": True,
                    "data": existing_travel.selected_travel_options,
                    "message": "User-preferred travelling options fetched successfully!",
                    "status_code": status.HTTP_200_OK,
                }
            else:
                return {
                    "status": True,
                    "data": existing_travel.original_travel_options,
                    "message": "Travel options fetched from cache.",
                    "status_code": status.HTTP_200_OK,
                }

        # ✅ 5. Trigger Celery task to fetch travel options
        get_travelling_options.delay(trip.id, user.id)

        return {
            "status": True,
            "data": None,
            "message": "Processing travelling options for your selected destination.",
            "status_code": status.HTTP_202_ACCEPTED,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing travel options: {str(e)}",
        )


@router.get("/travellingoptions/{trip_id}")
async def fetch_travel_options(
    trip_id: int,
    db: db_dependency,
    user: user_dependency
):
    """
    Fetch stored travel options (selected or original) for a given trip.
    Does NOT trigger Celery or modify data.
    """
    try:
        # ✅ 1. Ensure user is authenticated
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not authenticated."
            )

        # ✅ 2. Fetch trip and verify ownership
        trip = (
            db.query(Trip)
            .filter(Trip.id == trip_id, Trip.user_id == user.id)
            .first()
        )
        if not trip:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trip not found or doesn't belong to you."
            )

        # ✅ 3. Fetch travel options
        travel_options = (
            db.query(TravelOptions)
            .filter(TravelOptions.trip_id == trip.id)
            .first()
        )

        if not travel_options:
            return {
                "status": False,
                "data": None,
                "message": "No travel options found for this trip yet.",
                "status_code": status.HTTP_404_NOT_FOUND,
            }

        # ✅ 4. Prefer user-selected if available
        data = (
            travel_options.selected_travel_options
            if travel_options.selected_travel_options
            else travel_options.original_travel_options
        )

        source = (
            "user-selected options"
            if travel_options.selected_travel_options
            else "original options"
        )

        return {
            "status": True,
            "data": data,
            "message": f"Successfully fetched {source}.",
            "status_code": status.HTTP_200_OK,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching travel options: {str(e)}",
        )




















@router.post("/searchtrain", description="Search for trains between stations on a specific date")
async def search_train(request: TrainSearchRequest):
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


