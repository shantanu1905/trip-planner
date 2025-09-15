from fastapi import APIRouter, HTTPException, status, Query
from app.database.models import Trip , TravelOptions , UserPreferences
from app.utils.auth_helpers import user_dependency
from app.database.database import db_dependency

from typing import List, Optional
from app.utils.easemytrip import search_trains 
import httpx
import json


router = APIRouter(prefix="/travel_mode", tags=["Trains/Bus/Flight"])



# ---------- Search Trains ----------
@router.get("/searchtrain",
           description="Search for trains between stations on a specific date")
async def search_train(
    from_station: str = Query(..., description="From station code (e.g., 'NDLS' for New Delhi)"),
    to_station: str = Query(..., description="To station code (e.g., 'BCT' for Mumbai Central)"),
    travel_date: str = Query(..., description="Travel date in DD/MM/YYYY format"),
    coupon_code: Optional[str] = Query("", description="Optional coupon code")
):
    """
    Search for available trains between two stations for a specific date.
    
    Parameters:
    - from_station: Source station code
    - to_station: Destination station code  
    - travel_date: Date of travel in DD/MM/YYYY format
    - coupon_code: Optional discount coupon code
    
    Returns list of available trains with class-wise fare and availability information.
    """
    try:
        # Validate input parameters
        if not from_station or not to_station or not travel_date:
            return {
                "status": False,
                "data": None,
                "message": "From station, to station, and travel date are required",
                "status_code": status.HTTP_400_BAD_REQUEST
            }
        
        # Call the search function
        trains_data = search_trains(from_station, to_station, travel_date, coupon_code)
        
        if trains_data is None:
            return {
                "status": False,
                "data": None,
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
        
        # Return raw JSON data without schema validation
        return {
            "status": True,
            "data": trains_data,
            "message": f"Found {len(trains_data)} trains for {from_station} to {to_station} on {travel_date}",
            "status_code": status.HTTP_200_OK
        }
        
    except Exception as e:
        return {
            "status": False,
            "data": None,
            "message": f"Error searching trains: {str(e)}",
            "status_code": status.HTTP_500_INTER}
    





WEBHOOK_TRAVEL_MODE_URL = "http://localhost:5678/webhook/get-travel-mode"


@router.get("/get/{trip_id}")
async def get_travel_modes(trip_id: int, db: db_dependency, user: user_dependency):
    try:
        # 1. Fetch trip
        trip = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user.id).first()
        if not trip:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trip not found or doesn't belong to you."
            )

        # 2. Check if travel options already exist in DB
        existing_travel = db.query(TravelOptions).filter(TravelOptions.trip_id == trip.id).first()
        if existing_travel:
            return {
                "status": True,
                "data": existing_travel.travel_data,
                "message": "Travel options fetched from cache",
                "status_code": status.HTTP_200_OK
            }

        # 3. Prepare payload for webhook
        payload = {
            "trip_id": trip.id,
            "trip_name": trip.trip_name,
            "destination": trip.destination,
            "base_location": trip.base_location,
            "start_date": trip.start_date.isoformat() if trip.start_date else None,
            "end_date": trip.end_date.isoformat() if trip.end_date else None,
            "budget": trip.budget,
            "travel_mode": trip.travel_mode.value if trip.travel_mode else None,
            "num_people": trip.num_people,
            "activities": trip.activities or [],
            "travelling_with": trip.travelling_with.value if trip.travelling_with else None
        }

        # 4. Call webhook for travel modes
        async with httpx.AsyncClient(timeout=600.0) as client:
            response = await client.post(WEBHOOK_TRAVEL_MODE_URL, json=payload)

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch travel option for this trip"
            )

        full_data = response.json()

        # 5. Extract only `travel_options`
        travel_options = None
        if isinstance(full_data, list) and "output" in full_data[0]:
            travel_options = full_data[0]["output"].get("travel_options")
        elif "output" in full_data:
            travel_options = full_data["output"].get("travel_options")

        if not travel_options:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid travel options format received from webhook"
            )

        # 6. Save only travel_options in DB
        new_travel = TravelOptions(trip_id=trip.id, travel_data=travel_options)
        db.add(new_travel)
        db.commit()
        db.refresh(new_travel)

        # 7. Return saved response
        return {
            "status": True,
            "data": travel_options,
            "message": "Travel modes fetched and saved successfully",
            "status_code": status.HTTP_200_OK
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching travel modes: {str(e)}"
        )




@router.get("/get-travel-booking-suggestion/{trip_id}")
async def get_travel_booking_suggestion(
    trip_id: int,
    db: db_dependency,
    user: user_dependency
):
    try:
        # 1. Fetch Trip
        trip = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user.id).first()
        if not trip:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trip not found or doesn't belong to you."
            )

        # 2. Fetch User Preferences (Only required fields)
        user_pref = db.query(UserPreferences).filter(UserPreferences.user_id == user.id).first()
        user_pref_data = {
            "flexible_station_option": user_pref.flexible_station_option if user_pref else None,
            "preferred_from_station": user_pref.preferred_from_station if user_pref else None,
            "preferred_departure_time": user_pref.preferred_departure_time.value if user_pref and user_pref.preferred_departure_time else None,
            "preferred_train_class": user_pref.preferred_train_class.value if user_pref and user_pref.preferred_train_class else None
        }

        # 3. Fetch existing travel options if any
        existing_travel = db.query(TravelOptions).filter(TravelOptions.trip_id == trip.id).first()

        # 4. Prepare payload
        payload = {
            "trip": {
                "trip_id": trip.id,
                "trip_name": trip.trip_name,
                "destination": trip.destination,
                "base_location": trip.base_location,
                "start_date": trip.start_date.isoformat() if trip.start_date else None,
                "end_date": trip.end_date.isoformat() if trip.end_date else None,
                "budget": trip.budget,
                "travel_mode": trip.travel_mode.value if trip.travel_mode else None,
                "num_people": trip.num_people,
                "activities": trip.activities or [],
                "travelling_with": trip.travelling_with.value if trip.travelling_with else None
            },
            "user_preferences": user_pref_data,
            "existing_travel_options": existing_travel.travel_data if existing_travel else None
        }

        # 5. Call external webhook
        async with httpx.AsyncClient(timeout=600.0) as client:
            response = await client.post("http://localhost:5678/webhook/get-travel-booking-suggestion", json=payload)

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch travel booking suggestion"
            )

        full_data = response.json()

        # 6. Extract travel_options from response
        travel_options = full_data.get("travel_options")
        if not travel_options:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid response from travel booking suggestion webhook"
            )

        # 7. Save new travel options if not cached
        if not existing_travel:
            new_travel = TravelOptions(trip_id=trip.id, travel_data=travel_options)
            db.add(new_travel)
            db.commit()
            db.refresh(new_travel)

        return {
            "status": True,
            "data": travel_options,
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