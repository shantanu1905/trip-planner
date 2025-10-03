from fastapi import APIRouter
from app.utils.auth_helpers import user_dependency
from app.database.database import db_dependency 
from app.database.models import *
from typing import List, Dict, Any
from app.database.schemas import SettingsRequest,SettingsResponse
from fastapi import status
from enum import Enum

router = APIRouter(prefix="/settings", tags=["Settings"])




# ---------- Update Settings ----------
@router.put("/", response_model=SettingsResponse)
async def update_settings(
    request: SettingsRequest,
    db: db_dependency,
    user: user_dependency
):
    try:
        settings = db.query(Settings).filter(Settings.user_id == user.id).first()
        if not settings:
            return {
                "status": False,
                "data": None,
                "message": "Settings not found. Please add settings first.",
                "status_code": status.HTTP_404_NOT_FOUND
            }

        if request.native_language is not None:
            settings.native_language = request.native_language 
            settings.real_time_updates  = request.real_time_updates
            settings.auto_booking_enabled  = request.auto_booking_enabled
    

        db.commit()
        db.refresh(settings)

        return {
            "status": True,
            "data": {
                "user_id": settings.user_id,
                "native_language": settings.native_language,
                "real_time_updates": settings.real_time_updates,
                "auto_booking_enabled": settings.auto_booking_enabled,
            },
            "message": "Settings updated successfully",
            "status_code": status.HTTP_200_OK
        }

    except Exception as e:
        return {
            "status": False,
            "data": None,
            "message": f"Error updating settings: {str(e)}",
            "status_code": status.HTTP_400_BAD_REQUEST
        }


# ---------- Get Settings ----------
@router.get("/", response_model=SettingsResponse,
            description="Fetch the user settings. Returns native language, real-time updates, and auto-booking preferences.")
async def get_settings(
    db: db_dependency,
    user: user_dependency
):
    try:
        settings = db.query(Settings).filter(Settings.user_id == user.id).first()
        if not settings:
            return {
                "status": False,
                "data": None,
                "message": "Settings not found for this user.",
                "status_code": status.HTTP_404_NOT_FOUND
            }

        return {
            "status": True,
            "data": {
                "user_id": settings.user_id,
                "native_language": settings.native_language,
                "real_time_updates": settings.real_time_updates,
                "auto_booking_enabled": settings.auto_booking_enabled,
                
            },
            "message": "Settings fetched successfully",
            "status_code": status.HTTP_200_OK
        }

    except Exception as e:
        return {
            "status": False,
            "data": None,
            "message": f"Error fetching settings: {str(e)}",
            "status_code": status.HTTP_400_BAD_REQUEST
        }
    


def get_enum_values_list(enum_class: Enum) -> List[str]:
    """Convert Enum class to a simple list of values."""
    return [e.value for e in enum_class]


@router.get("/getenums", response_model=Dict[str, Any])
def get_all_enums(
    db: db_dependency,
    user: user_dependency
):
    """Endpoint to send all enum values as simple lists with user auth."""

    try:
        # Return enum values as lists
        return {
            "status": True,
            "data": {
                "native_languages": get_enum_values_list(NativeLanguageEnum),
                "activities": get_enum_values_list(ActivityEnum),
                "travelling_with": get_enum_values_list(TravellingWithEnum),
                "travel_modes": get_enum_values_list(TravelModeEnum),
                "property_types": get_enum_values_list(PropertyTypeEnum),
                "food_preferences": get_enum_values_list(FoodPreferenceEnum),
                "train_classes": get_enum_values_list(TrainClassEnum),
            },
            "message": "Settings fetched successfully",
            "status_code": status.HTTP_200_OK
        }

    except Exception as e:
        return {
            "status": False,
            "data": None,
            "message": f"Error fetching settings: {str(e)}",
            "status_code": status.HTTP_400_BAD_REQUEST
        }