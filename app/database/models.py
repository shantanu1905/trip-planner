import datetime as _dt
from sqlalchemy import (Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, Float ,Date )
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

class TravelModeEnum(enum.Enum):
    BIKE = "Bike"
    CAR = "Car"
    FLIGHT = "Flight"
    TRAIN = "Train"
    TAXI = "Taxi"
class PropertyTypeEnum(enum.Enum):
    HOTEL = "Hotel"
    HOMESTAY = "Homestay"
    VILLA = "Villa"
    COTTAGE = "Cottage"
    APARTMENT = "Apartment"
    RESORT = "Resort"
    HOSTEL = "Hostel"
    CAMP = "Camp"
    GUEST_HOUSE = "Guest House"
    TREE_HOUSE = "Tree House"
    PALACE = "Palace"
    FARM_HOUSE = "Farm House"
    AIRBNB = "Airbnb"
class FoodPreferenceEnum(enum.Enum):
    VEG = "Veg"
    NON_VEG = "Non-Veg"
    VEGAN = "Vegan"
    ANYTHING = "Anything"
class TrainClassEnum(enum.Enum):
    Sleeper_Class="SL"
    AC_3_Tier="3A"
    AC_3_Tier_Economy="3E"
    AC_2_tier= "2A"
    First_AC="1A"




#---------------- USER MODEL ------------------
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
    preferences = _orm.relationship("UserPreferences", back_populates="user", uselist=False, cascade="all, delete-orphan", passive_deletes=True)


# ------------------ SETTINGS MODEL ------------------
class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    native_language = Column(PGEnum(NativeLanguageEnum, name="native_language_enum", create_type=True),nullable=True,default=NativeLanguageEnum.ENGLISH  )
    real_time_updates = Column(Boolean, default=True)      # Weather/delay alerts
    auto_booking_enabled = Column(Boolean, default=False)  # One-click booking

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
  
    journey_start_date = Column(DateTime, nullable=True)  # New field for journey start
    return_journey_date = Column(DateTime, nullable=True)  # New field for return journey
    
    destination = Column(String, nullable=False)

    base_location = Column(String, nullable=True)
    travel_mode = Column(PGEnum(TravelModeEnum, name="travel_mode_enum", create_type=True),nullable=True)
    num_people = Column(Integer, nullable=True)
    activities = Column(JSONB, nullable=True, default=[])  # Will store ["Adventure", "Nightlife"]
    travelling_with = Column(PGEnum(TravellingWithEnum, name="travelling_with_enum", create_type=True), nullable=True)
    created_at = Column(DateTime, default=_dt.datetime.utcnow)

    
    user = _orm.relationship("User", back_populates="trips")
    itinerary = _orm.relationship("Itinerary", back_populates="trip", cascade="all, delete-orphan")
    tourist_places = _orm.relationship("TouristPlace", back_populates="trip", cascade="all, delete-orphan")
    travel_options = _orm.relationship("TravelOptions", back_populates="trip", cascade="all, delete-orphan")
    hotel_preferences_metadata = _orm.relationship("HotelPreferences",back_populates="trip",cascade="all, delete-orphan")


# ---------------- ITINERARY MODEL ----------------
class Itinerary(Base):
    __tablename__ = "itinerary"

    id = Column(Integer, primary_key=True, index=True)
    day = Column(Integer, nullable=False)
    date = Column(Date, nullable=False)

    # JSON fields for storing arrays and tips
    travel_tips = Column(JSONB, nullable=True)  # Can store as {"tips": "..."} or array
    food = Column(JSONB, nullable=True)         # Array of food items
    culture = Column(JSONB, nullable=True)      # Array of cultural experiences

    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    trip = _orm.relationship("Trip", back_populates="itinerary")

    # One-to-many relationship with places
    places = _orm.relationship("ItineraryPlace", back_populates="itinerary", cascade="all, delete-orphan")


class ItineraryPlace(Base):
    __tablename__ = "itinerary_places"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    latitude = Column(String, nullable=True)
    longitude = Column(String, nullable=True)
    best_time_to_visit = Column(String, nullable=True)

    itinerary_id = Column(Integer, ForeignKey("itinerary.id", ondelete="CASCADE"), nullable=False)
    itinerary = _orm.relationship("Itinerary", back_populates="places")



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



class TranslationCache(Base):
    __tablename__ = "translation_cache"

    id = Column(Integer, primary_key=True, index=True)
    source_text_hash = Column(String(64), index=True, nullable=False)
    source_text = Column(Text, nullable=False)
    source_lang = Column(String(10), nullable=False)
    target_lang = Column(String(10), nullable=False)
    translated_text = Column(JSONB, nullable=False)
    created_at = Column(DateTime, default=_dt.datetime.utcnow, nullable=False)




class UserPreferences(Base):
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Budget preference
    default_budget = Column(Integer, nullable=True)
    food_preference = Column(PGEnum(FoodPreferenceEnum, name="food_preference_enum", create_type=True),nullable=False,default=FoodPreferenceEnum.VEG)
    base_location = Column(String, nullable=True)
    activities = Column(JSONB,nullable=False,default=lambda: [ActivityEnum.NATURE.value, ActivityEnum.HERITAGE.value])
    travel_mode = Column(PGEnum(TravelModeEnum, name="travel_mode_enum", create_type=True),nullable=False,default=TravelModeEnum.TRAIN)
    travelling_with = Column(PGEnum(TravellingWithEnum, name="travelling_with_enum", create_type=True),nullable=False,default=TravellingWithEnum.SOLO)

    #Train
    preferred_train_class = Column(PGEnum(TrainClassEnum, name="train_class_enum", create_type=True),nullable=False,default=TrainClassEnum.AC_3_Tier)
    # Station Preferences
    preferred_from_station = Column(String, nullable=True)  # e.g., "Nagpur"
    flexible_station_option = Column(Boolean, default=True)  # Allow nearby stations if main one not available

    #Hotels
    # Room details - individual fields
    no_of_rooms = Column(Integer, default=1)
    no_of_adult = Column(Integer, default=1)
    no_of_child = Column(Integer, default=0)

    accomodation_min_price = Column(Float,  default=1 , nullable=True)
    accomodation_max_price = Column(Float, default=1000000 ,nullable=True)

    selected_property_types = Column(JSONB(PGEnum(PropertyTypeEnum, name="property_type_enum", create_type=True)),nullable=False,default=lambda: [PropertyTypeEnum.HOTEL.value])

    
    # Relationship
    user = _orm.relationship("User", back_populates="preferences", passive_deletes=True)


















class TravelOptions(Base):
    __tablename__ = "travel_options"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    travel_data = Column(JSONB, nullable=False)  # Full JSON response from webhook
    created_at = Column(DateTime, default=_dt.datetime.utcnow, nullable=False)

    # Relationship with Trip
    trip = _orm.relationship("Trip", back_populates="travel_options")




class HotelPreferences(Base):
    __tablename__ = "hotel_preferences"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)

    # Room details - individual fields
    no_of_rooms = Column(Integer, default=1)
    no_of_adult = Column(Integer, default=2)
    no_of_child = Column(Integer, default=0)
    child_age = Column(String, default="")  # Comma separated ages if multiple children

    # Filters / limits
    hotel_count = Column(Integer, nullable=True)  # Number of hotels to fetch
    no_of_rooms = Column(Integer, nullable=True)  # Total rooms
    sort_type = Column(String, default="Popular|DESC", nullable=True)     # Example: "Popular|DESC"
    min_price = Column(Float,  default=1 , nullable=True)
    max_price = Column(Float, default=1000000 ,nullable=True)
    
    # Hotel selection filters
    select_chain = Column(JSON, nullable=True, default=[])      # Selected chains
    selected_areas = Column(JSON, nullable=True, default=[])
    selected_amenities = Column(JSON, nullable=True, default=[])
    selected_property_types = Column(JSON, nullable=True, default=[])
    selected_ratings = Column(JSON, nullable=True, default=[])
    # Dates
    check_in_date = Column(DateTime, nullable=False)
    check_out_date = Column(DateTime, nullable=False)

    # Metadata
    created_at = Column(DateTime, default=_dt.datetime.utcnow)

    # Relationship
    trip = _orm.relationship("Trip",back_populates="hotel_preferences_metadata")