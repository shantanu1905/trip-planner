from pydantic import BaseModel
from app.database.models import *
from typing import List, Optional
from pydantic import BaseModel , Field
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


class PreferencesRequest(BaseModel):
    # --- Budget & General Preferences ---
    default_budget: Optional[int] = None
    food_preference: Optional[FoodPreferenceEnum] = None
    base_location: Optional[str] = None
    activities: Optional[List[str]] = []
    travel_mode: Optional[TravelModeEnum] = None
    travelling_with: Optional[TravellingWithEnum] = None

    # --- Train Preferences ---
    preferred_train_class: Optional[TrainClassEnum] = None
    preferred_from_station: Optional[str] = None
    flexible_station_option: Optional[bool] = True

    # --- Bus Preferences ---
    bus_sleeper: Optional[bool] = True
    bus_ac: Optional[bool] = True
    bus_seater: Optional[bool] = True
    bus_ststatus: Optional[bool] = False

    # --- Flight Preferences ---
    preferred_flight_class: Optional[FlightClassEnum] = FlightClassEnum.ECONOMY


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



# --- Request Schema ---
class TravelLeg(BaseModel):
    to: str
    from_: str = Field(..., alias="from")
    mode: str
    to_code: str | None = None
    from_code: str | None = None
    approx_cost: str | None = None
    approx_time: str | None = None
    booking_url: str | None = None
    journey_date: str | None = None


class SaveTravelOptionsRequest(BaseModel):
    trip_id: int
    option_name: str
    legs: List[TravelLeg]



class HotelPreferencesCreate(BaseModel):
    trip_id: int
    no_of_rooms: Optional[int] = Field(default=1)
    no_of_child: Optional[int] = Field(default=0)
    min_price: Optional[float] = Field(default=1)
    max_price: Optional[float] = Field(default=1000000)
    selected_property_types: Optional[List[str]] = Field(default=["HOTEL"])

 
class BusSearchRequest(BaseModel):
    from_city: str = Field(example="Delhi", description="Source city name, e.g. Pune")
    to_city: str = Field(example="Dehtadun", description="Destination city name, e.g. Nagpur")
    journey_date: str = Field(example="11-11-2025", description="Journey date in DD-MM-YYYY or YYYY-MM-DD format (default: tomorrow)")
    from_city_id: int = Field(example=733, description="Source city ID from EaseMyTrip")
    to_city_id: int = Field(example=777, description="Destination city ID from EaseMyTrip")



class HotelSearchRequest(BaseModel):
    destination: str = Field(..., example="Nagpur")
    check_in: str = Field(..., example="10-11-2025")
    check_out: str = Field(..., example="12-11-2025")
    no_of_rooms: int = Field(..., ge=1, example=1)
    no_of_adult: int = Field(..., ge=1, example=2)
    no_of_child: int = Field(..., ge=0, example=0)
    min_price: Optional[float] = Field(1, example=1)
    max_price: Optional[float] = Field(1000000, example=1000000)
    sort_type: Optional[str] = Field("Popular|DESC", example="Popular|DESC")
    no_of_results: Optional[int] = Field(30, example=30)