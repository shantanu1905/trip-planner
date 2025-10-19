from fastapi import APIRouter, Depends, status
from app.database.models import UserPreferences 
from app.database.database import db_dependency
from app.utils.auth_helpers import user_dependency
from app.database.schemas import PreferencesRequest
from enum import Enum

router = APIRouter(prefix="/preferences", tags=["User Preferences"])
@router.put("/")
async def set_user_preferences(
    request: PreferencesRequest,
    db: db_dependency,
    user: user_dependency
):
    try:
        preferences = db.query(UserPreferences).filter(UserPreferences.user_id == user.id).first()

        if preferences:
            # ---- Update existing preferences ----
            preferences.default_budget = request.default_budget
            preferences.food_preference = request.food_preference
            preferences.base_location = request.base_location
            preferences.activities = request.activities or []
            preferences.travel_mode = request.travel_mode
            preferences.travelling_with = request.travelling_with

            # ---- Train Preferences ----
            preferences.preferred_train_class = request.preferred_train_class
            preferences.preferred_from_station = request.preferred_from_station
            preferences.flexible_station_option = request.flexible_station_option

            # ---- Bus Preferences ----
            preferences.bus_sleeper = request.bus_sleeper
            preferences.bus_ac = request.bus_ac
            preferences.bus_seater = request.bus_seater
            preferences.bus_ststatus = request.bus_ststatus

            # ---- Flight Preferences ----
            preferences.preferred_flight_class = request.preferred_flight_class

            message = "Preferences updated successfully."

        else:
            # ---- Create new preferences ----
            preferences = UserPreferences(
                user_id=user.id,
                default_budget=request.default_budget,
                food_preference=request.food_preference,
                base_location=request.base_location,
                activities=request.activities or [],
                travel_mode=request.travel_mode,
                travelling_with=request.travelling_with,

                # Train
                preferred_train_class=request.preferred_train_class,
                preferred_from_station=request.preferred_from_station,
                flexible_station_option=request.flexible_station_option,

                # Bus
                bus_sleeper=request.bus_sleeper,
                bus_ac=request.bus_ac,
                bus_seater=request.bus_seater,
                bus_ststatus=request.bus_ststatus,

                # Flight
                preferred_flight_class=request.preferred_flight_class
            )
            db.add(preferences)
            message = "Preferences created successfully."

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
            # General
            "default_budget": preferences.default_budget,
            "food_preference": preferences.food_preference.value if preferences.food_preference else None,
            "base_location": preferences.base_location,
            "activities": preferences.activities,
            "travel_mode": preferences.travel_mode.value if preferences.travel_mode else None,
            "travelling_with": preferences.travelling_with.value if preferences.travelling_with else None,

            # Train Preferences
            "preferred_train_class": preferences.preferred_train_class.value if preferences.preferred_train_class else None,
            "preferred_from_station": preferences.preferred_from_station,
            "flexible_station_option": preferences.flexible_station_option,

            # Bus Preferences
            "bus_sleeper": preferences.bus_sleeper,
            "bus_ac": preferences.bus_ac,
            "bus_seater": preferences.bus_seater,
            "bus_ststatus": preferences.bus_ststatus,

            # Flight Preferences
            "preferred_flight_class": preferences.preferred_flight_class.value if preferences.preferred_flight_class else None,
        }

        return {
            "status": True,
            "data": preferences_data,
            "message": "Preferences fetched successfully.",
            "status_code": status.HTTP_200_OK
        }

    except Exception as e:
        return {
            "status": False,
            "data": None,
            "message": f"Error fetching preferences: {str(e)}",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
        }