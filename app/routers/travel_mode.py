from fastapi import APIRouter, HTTPException, status, Query
from app.database.models import Trip , TravelOptions , UserPreferences
from app.utils.auth_helpers import user_dependency
from app.database.database import db_dependency
from app.task.trip_tasks import process_travel_modes
from app.database.schemas import TrainSearchRequest
from datetime import datetime 
from typing import List, Optional
from app.utils.easemytrip import search_trains , get_station_code
import httpx
import json


router = APIRouter(prefix="/get-tickets", tags=["Trains/Bus/Flight"])


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


