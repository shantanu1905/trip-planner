from pydantic import BaseModel
from app.database.models import Settings, NativeLanguageEnum, ActivityEnum, TravellingWithEnum, TravelModeEnum
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


# ---------- Schemas ----------
class SettingsRequest(BaseModel):
    native_language: Optional[NativeLanguageEnum] = None
    activities: Optional[List[ActivityEnum]] = None


class SettingsResponse(BaseModel):
    status: bool
    data: dict
    message: str
    status_code: int


class CreateTripRequest(BaseModel):
    trip_name: str
    budget: Optional[int] = None
    start_date: datetime
    end_date: datetime
    destination: str
    base_location: Optional[str] = None
    travel_mode: Optional[TravelModeEnum] = None
    num_people: Optional[int] = 1
    activities: Optional[List] = None  # ✅ Updated field name
    travelling_with: Optional[TravellingWithEnum] = None


class UpdateTripRequest(BaseModel):
    budget: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    travel_mode: Optional[TravelModeEnum] = None
    num_people: Optional[int] = None
    activities: Optional[List] = None  # ✅ Updated field name
    travelling_with: Optional[TravellingWithEnum] = None
