import datetime as _dt
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, Float
)
from sqlalchemy.dialects.postgresql import ENUM as PGEnum, ARRAY
import enum
import sqlalchemy.orm as _orm
from app.database.database import Base
from sqlalchemy.dialects.postgresql import JSONB
# ------------------ ENUMS ------------------

class NativeLanguageEnum(enum.Enum):
    ENGLISH = "English"
    HINDI = "Hindi"
    TAMIL = "Tamil"
    TELUGU = "Telugu"
    BENGALI = "Bengali"
    MARATHI = "Marathi"
    GUJARATI = "Gujarati"
    MALAYALAM = "Malayalam"
    KANNADA = "Kannada"
    PUNJABI = "Punjabi"
    OTHER = "Other"


class ActivityEnum(enum.Enum):
    ADVENTURE = "Adventure"
    HERITAGE = "Heritage"
    NIGHTLIFE = "Nightlife"
    RELAXATION = "Relaxation"
    NATURE = "Nature"
    CULTURE = "Culture"


class TravellingWithEnum(enum.Enum):
    SOLO = "Solo"
    PARTNER = "Partner"
    FRIENDS = "Friends"
    FAMILY = "Family"

# New enum for travel modes
class TravelModeEnum(enum.Enum):
    BIKE = "Bike"
    CAR = "Car"
    FLIGHT = "Flight"
    TRAIN = "Train"

# ------------------ USER MODEL ------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    google_sub = Column(String, unique=True, nullable=True)  
    username = Column(String, unique=True, nullable=True)
    email = Column(String, unique=True, nullable=True)
    hashed_password = Column(String, nullable=True)

    name = Column(String, nullable=True)
    picture = Column(String, nullable=True)
    email_verified = Column(Boolean, default=False)
    date_created = Column(DateTime, default=_dt.datetime.utcnow, nullable=False)

    # Relationships
    trips = _orm.relationship("Trip", back_populates="user", cascade="all, delete-orphan")
    settings = _orm.relationship("Settings", back_populates="user", uselist=False, cascade="all, delete-orphan")


# ------------------ SETTINGS MODEL ------------------

class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    native_language = Column(PGEnum(NativeLanguageEnum, name="native_language_enum", create_type=True), nullable=True)
    
    # Multiple activities as array
    activities = Column(ARRAY(PGEnum(ActivityEnum, name="activity_enum", create_type=True)), nullable=True)

    user = _orm.relationship("User", back_populates="settings")


# ------------------ TRIP MODEL ------------------

class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    trip_name = Column(String, nullable=False)
    budget = Column(Integer, nullable=True)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    destination = Column(String, nullable=False)

    # New fields
    base_location = Column(String, nullable=True)
    travel_mode = Column(
        PGEnum(TravelModeEnum, name="travel_mode_enum", create_type=True),
        nullable=True
    )
    num_people = Column(Integer, nullable=True)

    activities = Column(JSONB, nullable=True, default=[])  # Will store ["Adventure", "Nightlife"]
    travelling_with = Column(PGEnum(TravellingWithEnum, name="travelling_with_enum", create_type=True), nullable=True)

    created_at = Column(DateTime, default=_dt.datetime.utcnow)

    user = _orm.relationship("User", back_populates="trips")
    itinerary = _orm.relationship("Itinerary", back_populates="trip", cascade="all, delete-orphan")
    tourist_places = _orm.relationship("TouristPlace", back_populates="trip", cascade="all, delete-orphan")


# ---------------- ITINERARY MODEL ----------------
class Itinerary(Base):
    __tablename__ = "itineraries"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    day_number = Column(Integer, nullable=False)
    date = Column(DateTime, nullable=False)
    place = Column(Text, nullable=True)
    description = Column(Text, nullable=True)

    food = Column(JSON, nullable=True)         
    culture = Column(Text, nullable=True)      
    travel_tips = Column(JSON, nullable=True)  
    sources = Column(JSON, nullable=True)      
    cost_breakdown = Column(JSON, nullable=True)

    total_cost = Column(Float, nullable=True)
    created_at = Column(DateTime, default=_dt.datetime.utcnow)

    trip = _orm.relationship("Trip", back_populates="itinerary")




class TouristPlace(Base):
    __tablename__ = "tourist_places"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    image_url = Column(String, nullable=True)


    created_at = Column(DateTime, default=_dt.datetime.utcnow, nullable=False)

    trip = _orm.relationship("Trip", back_populates="tourist_places")
