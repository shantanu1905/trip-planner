from pydantic import BaseModel
from app.database.models import *
from typing import List, Optional
from pydantic import BaseModel , Field
from datetime import datetime
from typing import Literal

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




class TrainBookingCreate(BaseModel):
    trip_id: int = Field(..., example=1)
    booking_type: str = Field("Train", example="Train")

    from_station: str = Field(..., example="MMCT")
    to_station: str = Field(..., example="NGP")
    travel_date: str = Field(..., example="2025-11-22")

    train_name: str = Field(..., example="Ltt Bbs Express")
    train_number: str = Field(..., example="12879")

    arrival_time: Optional[str] = Field(None, example="13:35")
    departure_time: Optional[str] = Field(None, example="00:15")
    duration: Optional[str] = Field(None, example="13:20")
    distance: Optional[str] = Field(None, example="821")

    from_stn_name: Optional[str] = Field(None, example="Lokmanyatilak Terminus Kurla")
    from_stn_code: Optional[str] = Field(None, example="LTT")
    to_stn_name: Optional[str] = Field(None, example="Nagpur")
    to_stn_code: Optional[str] = Field(None, example="NGP")

    arrival_date: Optional[str] = Field(None, example="22Nov2025")
    departure_date: Optional[str] = Field(None, example="22Nov2025")

    enq_class: Optional[str] = Field(None, example="2A")
    quota_name: Optional[str] = Field(None, example="General")
    total_fare: Optional[float] = Field(None, example=1715.0)

    class Config:
        from_attributes = True

    


class BusBookingCreate(BaseModel):
    trip_id: int = Field(..., example=1)
    booking_type: str = Field("Bus", example="Bus")
    from_city: str = Field(..., example="Delhi")
    to_city: str = Field(..., example="Dehradun")
    journey_date: str = Field(..., example="01-11-2025")
    from_city_id: int = Field(..., example=733)
    to_city_id: int = Field(..., example=777)

    boarding_point_name: Optional[str] = Field(None, example="Kashmere Gate")
    boarding_point_id: Optional[str] = Field(None, example="303")
    boarding_point_location: Optional[str] = Field(None, example="Kashmere Gate,Platform no.59,60 Kashmiri Gate")
    boarding_point_long_name: Optional[str] = Field(None, example="Kashmere Gate")

    dropping_point_id: Optional[str] = Field(None, example="26")
    dropping_point_name: Optional[str] = Field(None, example="Near ISBT Dehradun")
    dropping_point_location: Optional[str] = Field(None, example="Rao Travels,Near ISBT Dehradun, near rao Travels")

    travels_name: Optional[str] = Field(None, example="YOLO BUS")
    bus_type: Optional[str] = Field(None, example="Bharat Benz A/C Semi Sleeper (2+2)")
    ac: Optional[bool] = Field(None, example=True)

    departure_time: Optional[str] = Field(None, example="23:40")
    arrival_time: Optional[str] = Field(None, example="05:17")
    duration: Optional[str] = Field(None, example="05h 37m")
    doj: Optional[str] = Field(None, example="2025-11-01T11:40:00")
    route_id: Optional[str] = Field(None, example="2716")
    bus_id: Optional[str] = Field(None, example="5862188")
    bus_key: Optional[str] = Field(None, example="b5913")

    total_fare: Optional[float] = Field(None, example=299.0)







class HotelBookingCreate(BaseModel):
    trip_id: int = Field(..., example=1)
    booking_type: str = Field("Hotel", example="Hotel")
    destination: str = Field(..., example="Pune")
    check_in: str = Field(..., example="2025-11-10")
    check_out: str = Field(..., example="2025-11-13")
    no_of_rooms: int = Field(1, example=1)
    no_of_adult: int = Field(2, example=2)
    no_of_child: int = Field(0, example=0)

    adrs: Optional[str] = Field(None, example="Pune > MIDC > Pimpri Colony")
    nm: Optional[str] = Field(None, example="Spree Shivai Hotel Pimpri")
    lat: Optional[float] = Field(None, example=18.6405563)
    lon: Optional[float] = Field(None, example=73.8066185)
    prc: Optional[float] = Field(None, example=5131.0)
    rat: Optional[str] = Field(None, example="4")
    tax: Optional[float] = Field(None, example=233.0)
    disc: Optional[float] = Field(None, example=746.0)
    hid: Optional[str] = Field(None, example="SHL-19112806256009")
    catgry: Optional[str] = Field(None, example="Hotel")
    cName: Optional[str] = Field(None, example="SPREE HOTELS")
    ecid: Optional[str] = Field(None, example="EMTHOTEL-190793")
    durl: Optional[str] = Field(
        None,
        example="https://www.easemytrip.com/hotels/spree-shivai-hotel-pimpri-190793/?e=27102025120814"
    )
    cinTime: Optional[str] = Field(None, example="12:00 PM")
    coutTime: Optional[str] = Field(None, example="10:00 AM")
    lnFare: Optional[float] = Field(None, example=4665.0)
    appfare: Optional[float] = Field(None, example=3965.0)





class StripeCheckoutRequest(BaseModel):
    trip_id: int = Field(..., example=1, description="Trip ID for which booking is made")
    booking_id: int = Field(..., example=101, description="Unique booking record ID")
    booking_type: Literal["Train", "Bus", "Hotel"] = Field(
        ..., example="Hotel", description="Type of booking (Train, Bus, Hotel)"
    )
    amount: float = Field(..., example=4999.00, description="Amount to be charged in INR")