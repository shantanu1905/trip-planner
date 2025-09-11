from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database.models import UserPreferences 
from app.database.database import db_dependency
from app.utils.auth_helpers import user_dependency
from app.database.schemas import CreateTripRequest, UpdateTripRequest , PreferencesRequest

from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

router = APIRouter(prefix="/preferences", tags=["User Preferences"])

# ---- Create or Update Preferences ----
@router.post("/set")
async def set_user_preferences(
    request: PreferencesRequest,
    db: db_dependency,
    user: user_dependency
):
    try:
        # Check if preferences exist for this user
        preferences = db.query(UserPreferences).filter(UserPreferences.user_id == user.id).first()

        if preferences:
            # Update existing preferences
            preferences.default_budget = request.default_budget
            preferences.property_type = request.property_type
            preferences.hotel_room_price_per_night = request.hotel_room_price_per_night
            preferences.num_people = request.num_people
            preferences.food_preference = request.food_preference
            preferences.base_location = request.base_location
            preferences.activities = request.activities or []
            preferences.travel_mode = request.travel_mode
            preferences.travelling_with = request.travelling_with
            message = "Preferences updated successfully"
        else:
            # Create new preferences
            preferences = UserPreferences(
                user_id=user.id,
                default_budget=request.default_budget,
                property_type=request.property_type,
                hotel_room_price_per_night=request.hotel_room_price_per_night,
                num_people=request.num_people,
                food_preference=request.food_preference,
                base_location=request.base_location,
                activities=request.activities or [],
                travel_mode=request.travel_mode,
                travelling_with=request.travelling_with
            )
            db.add(preferences)
            message = "Preferences created successfully"

        db.commit()
        db.refresh(preferences)

        return {
            "status": True,
            "data": {
                "preferences_id": preferences.id,
                "user_id": preferences.user_id
            },
            "message": message,
            "status_code": status.HTTP_200_OK
        }

    except Exception as e:
        return {
            "status": False,
            "message": f"Error saving preferences: {str(e)}",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
        }


# ---- Get Preferences ----
@router.get("/")
async def get_user_preferences(db: db_dependency, user: user_dependency):
    try:
        preferences = db.query(UserPreferences).filter(UserPreferences.user_id == user.id).first()

        if not preferences:
            return {
                "status": False,
                "data": None,
                "message": "No preferences set for this user.",
                "status_code": status.HTTP_404_NOT_FOUND
            }

        preferences_data = {
            "default_budget": preferences.default_budget,
            "property_type": preferences.property_type,
            "hotel_room_price_per_night": preferences.hotel_room_price_per_night,
            "num_people": preferences.num_people,
            "food_preference": preferences.food_preference,
            "base_location": preferences.base_location,
            "activities": preferences.activities,
            "travel_mode": preferences.travel_mode,
            "travelling_with": preferences.travelling_with
        }

        return {
            "status": True,
            "data": preferences_data,
            "message": "Preferences fetched successfully",
            "status_code": status.HTTP_200_OK
        }

    except Exception as e:
        return {
            "status": False,
            "data": None,
            "message": f"Error fetching preferences: {str(e)}",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
        }