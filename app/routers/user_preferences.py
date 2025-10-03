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

        # Convert enums list → list of values (strings) for JSONB
        selected_property_types = (
            [ptype.value if hasattr(ptype, "value") else ptype for ptype in (request.selected_property_types or [])]
        )

        if preferences:
            # ---- Update existing ----
            preferences.default_budget = request.default_budget
            preferences.food_preference = request.food_preference
            preferences.base_location = request.base_location
            preferences.activities = request.activities or []
            preferences.travel_mode = request.travel_mode
            preferences.travelling_with = request.travelling_with

            # Train
            preferences.preferred_train_class = request.preferred_train_class
            preferences.preferred_from_station = request.preferred_from_station
            preferences.flexible_station_option = request.flexible_station_option

            # Hotel
            preferences.no_of_rooms = request.no_of_rooms
            preferences.no_of_adult = request.no_of_adult
            preferences.no_of_child = request.no_of_child
            preferences.accomodation_min_price = request.accomodation_min_price
            preferences.accomodation_max_price = request.accomodation_max_price
            preferences.selected_property_types = selected_property_types

            message = "Preferences updated successfully"
        else:
            # ---- Create new ----
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

                # Hotel
                no_of_rooms=request.no_of_rooms,
                no_of_adult=request.no_of_adult,
                no_of_child=request.no_of_child,
                accomodation_min_price=request.accomodation_min_price,
                accomodation_max_price=request.accomodation_max_price,
                selected_property_types=selected_property_types
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
            "food_preference": preferences.food_preference,
            "base_location": preferences.base_location,
            "activities": preferences.activities,
            "travel_mode": preferences.travel_mode,
            "travelling_with": preferences.travelling_with,

            # Train
            "preferred_train_class": preferences.preferred_train_class,
            "preferred_from_station": preferences.preferred_from_station,
            "flexible_station_option": preferences.flexible_station_option,

            # Hotel
            "no_of_rooms": preferences.no_of_rooms,
            "no_of_adult": preferences.no_of_adult,
            "no_of_child": preferences.no_of_child,
            "accomodation_min_price": preferences.accomodation_min_price,
            "accomodation_max_price": preferences.accomodation_max_price,
            "selected_property_types": preferences.selected_property_types,
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