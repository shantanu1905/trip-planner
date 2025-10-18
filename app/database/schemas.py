from pydantic import BaseModel
from app.database.models import *
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime


class CreateUserRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class GoogleUser(BaseModel):
    sub: int
    email: str
    name: str
    picture: str
    email_verified: bool


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# ---------- Settings ----------
class SettingsRequest(BaseModel):
    native_language: Optional[NativeLanguageEnum] = None
    real_time_updates: Optional[bool] = True
    auto_booking_enabled: Optional[bool] = False

class SettingsResponse(BaseModel):
    status: bool
    data: Optional[dict] = None  # ✅ allow None if no settings
    message: str
    status_code: int


# ---------- Trips ----------
class CreateTripRequest(BaseModel):
    trip_name: str
    budget: Optional[int] = None
    start_date: datetime
    end_date: datetime
    destination: str
    base_location: Optional[str] = None
    num_people: Optional[int] = 1
    activities: Optional[List] = None  # ✅ Updated field name
    travelling_with: Optional[TravellingWithEnum] = None
    use_preferences: bool = False


class UpdateTripRequest(BaseModel):
    budget: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    num_people: Optional[int] = None
    activities: Optional[List] = None  # ✅ Updated field name
    travelling_with: Optional[TravellingWithEnum] = None



# ---- Request Schema ----
class PreferencesRequest(BaseModel):
    # Budget & food
    default_budget: Optional[int] = None
    food_preference: Optional[FoodPreferenceEnum] = None
    base_location: Optional[str] = None
    activities: Optional[List[str]] = []
    travelling_with: Optional[TravellingWithEnum] = None

    # Train preferences
    preferred_train_class: Optional[TrainClassEnum] = None
    preferred_from_station: Optional[str] = None
    flexible_station_option: Optional[bool] = None

    # Hotel preferences
    no_of_rooms: Optional[int] = 1
    no_of_adult: Optional[int] = 1
    no_of_child: Optional[int] = 0
    accomodation_min_price: Optional[float] = 1
    accomodation_max_price: Optional[float] = 1000000
    selected_property_types: Optional[List[PropertyTypeEnum]] = []
    

# --- Request Body Schema ---
class TrainSearchRequest(BaseModel):
    from_station: str
    to_station: str
    travel_date: str  # Accepts DD/MM/YYYY or YYYY-MM-DD
    coupon_code: Optional[str] = ""



class TravellingOptionsRequest(BaseModel):
    trip_id: int
    journey_start_date: datetime
    return_journey_date: datetime

