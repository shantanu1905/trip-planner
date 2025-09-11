from fastapi import APIRouter
from app.utils.auth_helpers import user_dependency
from app.database.database import db_dependency 
from app.database.models import Settings 

from app.database.schemas import SettingsRequest,SettingsResponse
from fastapi import status


router = APIRouter(prefix="/settings", tags=["Settings"])



# ---------- Add Settings ----------
@router.post("/add", response_model=SettingsResponse)
async def add_settings(
    request: SettingsRequest,
    db: db_dependency,
    user: user_dependency
):
    try:
        existing_settings = db.query(Settings).filter(Settings.user_id == user.id).first()
        if existing_settings:
            return {
                "status": False,
                "data": None,
                "message": "Settings already exist. Use update instead.",
                "status_code": status.HTTP_400_BAD_REQUEST
            }

        new_settings = Settings(
            user_id=user.id,
            native_language=request.native_language,
            real_time_updates=request.real_time_updates,
            auto_booking_enabled=request.auto_booking_enabled
        )
        db.add(new_settings)
        db.commit()
        db.refresh(new_settings)

        return {
            "status": True,
            "data": {
                "user_id": new_settings.user_id,
                "native_language": new_settings.native_language,
                "real_time_updates": new_settings.real_time_updates,
                "auto_booking_enabled": new_settings.auto_booking_enabled,
            },
            "message": "Settings added successfully",
            "status_code": status.HTTP_201_CREATED
        }

    except Exception as e:
        return {
            "status": False,
            "data": None,
            "message": f"Error adding settings: {str(e)}",
            "status_code": status.HTTP_400_BAD_REQUEST
        }


# ---------- Update Settings ----------
@router.put("/update", response_model=SettingsResponse)
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
@router.get("/get", response_model=SettingsResponse)
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
    




