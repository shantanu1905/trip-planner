from fastapi import APIRouter, HTTPException, status
from app.database.models import Trip , Settings, TouristPlace , Itinerary , ItineraryPlace, TravelOptions
from app.database.schemas import CreateTripRequest, UpdateTripRequest
from app.utils.auth_helpers import user_dependency
from app.database.database import db_dependency
from app.task.trip_tasks import process_trip_webhook , process_itinerary , get_travelling_options , get_detailed_travelling_options
from app.utils.language_translation import translate_with_cache
import datetime


router = APIRouter(prefix="/trips", tags=["Trips"])
from datetime import timedelta

from fastapi import APIRouter, Depends, status, HTTPException, Query
from app.database.models import Trip, UserPreferences
from app.database.database import db_dependency
from app.utils.auth_helpers import user_dependency
from app.database.schemas import CreateTripRequest
from typing import Optional

router = APIRouter(prefix="/trips", tags=["Trips"])


@router.post("/create")
async def create_trip(
    request: CreateTripRequest,
    db: db_dependency,
    user: user_dependency,
   
):
    try:
        # 0. Prevent duplicate trip names for same user
        existing_trip = db.query(Trip).filter(
            Trip.user_id == user.id,
            Trip.trip_name == request.trip_name
        ).first()
        if existing_trip:
            return {
                "status": False,
                "message": "Trip with this name already exists.",
                "status_code": status.HTTP_400_BAD_REQUEST
            }

        # request.start_date and request.end_date are expected as datetime objects
        start_date = request.start_date
        end_date = request.end_date

        # 1. Load preferences if requested
        preferences = None
        if request.use_preferences:
            preferences = db.query(UserPreferences).filter(UserPreferences.user_id == user.id).first()
            if not preferences:
                return {
                    "status": False,
                    "message": "No user preferences found. Please set your preferences first or call this endpoint with use_preferences=false.",
                    "status_code": status.HTTP_400_BAD_REQUEST
                }

            # --- Required fields that must be present either in request or preferences ---
            missing_fields = []
            if not (request.base_location or (getattr(preferences, "base_location", None))):
                missing_fields.append("base_location")
            if not (request.travel_mode or (getattr(preferences, "travel_mode", None))):
                missing_fields.append("travel_mode")

            if missing_fields:
                return {
                    "status": False,
                    "message": (
                        "Missing required data. The following fields are not provided in the request "
                        "and are not set in user preferences: " + ", ".join(missing_fields) +
                        ". Please update your user preferences or provide these fields in the request."
                    ),
                    "status_code": status.HTTP_400_BAD_REQUEST
                }

        # 2. Apply values: prefer request value, otherwise preference (if allowed), otherwise None
        budget = request.budget if request.budget is not None else (preferences.default_budget if preferences else None)
        base_location = request.base_location if request.base_location else (preferences.base_location if preferences else None)
        travel_mode = request.travel_mode if request.travel_mode is not None else (preferences.travel_mode if preferences else None)
        num_people = request.num_people if request.num_people is not None else (preferences.num_people if preferences and hasattr(preferences, "num_people") else None)
        activities = request.activities if request.activities is not None else (preferences.activities if preferences else [])
        travelling_with = request.travelling_with if request.travelling_with is not None else (preferences.travelling_with if preferences else None)

        # 3. Create trip record
        new_trip = Trip(
            user_id=user.id,
            trip_name=request.trip_name,
            budget=budget,
            start_date=start_date,
            end_date=end_date,
            destination=request.destination,
            base_location=base_location,
            travel_mode=travel_mode,
            num_people=num_people,
            activities=activities or [],
            travelling_with=travelling_with
        )

        db.add(new_trip)
        db.commit()
        db.refresh(new_trip)

        # 4. Kick off background jobs (serialize enum values safely when passing)
        travel_mode_value = new_trip.travel_mode.value if hasattr(new_trip.travel_mode, "value") else (new_trip.travel_mode if new_trip.travel_mode else None)

        # Example Celery tasks - adapt args/names to your project
        get_travelling_options.delay(new_trip.id, user.id, new_trip.base_location, new_trip.destination, travel_mode_value)
        get_detailed_travelling_options.delay(new_trip.id, user.id, start_date.isoformat() if start_date else None)

        return {
            "status": True,
            "data": {
                "trip_id": new_trip.id,
                "trip_name": new_trip.trip_name,
            },
            "message": "Trip created successfully. Processing in background.",
            "status_code": status.HTTP_201_CREATED
        }

    except Exception as e:
        # Keep useful error message, but avoid leaking internals in production
        return {
            "status": False,
            "message": f"Error creating trip: {str(e)}",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
        }



@router.put("/update/{trip_id}")
async def update_trip(
    trip_id: int,
    request: UpdateTripRequest,
    db: db_dependency,
    user: user_dependency
):
    try:
        trip = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user.id).first()
        if not trip:
            return {
                "status": False,
                "message": "Trip not found or you don't have permission to update this trip.",
                "status_code": status.HTTP_404_NOT_FOUND
            }

        # request.start_date and request.end_date are already datetime objects
        start_date = request.start_date
        end_date = request.end_date

        # Update trip fields
        trip.budget = request.budget
        trip.start_date = start_date
        trip.end_date = end_date
        trip.travel_mode = request.travel_mode
        trip.num_people = request.num_people
        trip.activities = request.activities if request.activities else []
        trip.travelling_with = request.travelling_with

        db.commit()
        db.refresh(trip)

        process_trip_webhook.delay(trip.id, user.id)

        return {
            "status": True,
            "data": {
                "trip_id": trip.id,
                "trip_name": trip.trip_name,
                "activities": trip.activities
            },
            "message": "Trip updated successfully. Processing places in background.",
            "status_code": status.HTTP_200_OK
        }

    except Exception as e:
        return {
            "status": False,
            "message": f"Error updating trip: {str(e)}",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
        }

@router.get("/")
async def get_all_trips(db: db_dependency, user: user_dependency):
    try:
        trips = db.query(Trip).filter(Trip.user_id == user.id).all()
        if not trips:
            return {
                "status": False,
                "data": [],
                "message": "No trips found for this user.",
                "status_code": status.HTTP_404_NOT_FOUND
            }

        # Fetch user settings for target language
        settings = db.query(Settings).filter(Settings.user_id == user.id).first()
        target_lang = settings.native_language if settings and settings.native_language else "English"

        trips_data = [
            {
                "trip_id": t.id,
                "trip_name": t.trip_name,
                "destination": t.destination,
                "base_location": t.base_location,
                "start_date": t.start_date,
                "end_date": t.end_date,
                "budget": t.budget,
                "travel_mode": t.travel_mode.value if t.travel_mode else None,
                "num_people": t.num_people,
                "activities": t.activities or [],
                "travelling_with": t.travelling_with.value if t.travelling_with else None
            }
            for t in trips
        ]
        for trip in trips_data:
            if isinstance(trip.get("start_date"), datetime.datetime):
                trip["start_date"] = trip["start_date"].isoformat()
            if isinstance(trip.get("end_date"), datetime.datetime):
                trip["end_date"] = trip["end_date"].isoformat()

        # ✅ Translate entire trips list once if needed
        if target_lang != "English":
            trips_data = await translate_with_cache(db, trips_data, target_lang)

        return {
            "status": True,
            "data": trips_data,
            "message": "Trips fetched successfully",
            "status_code": status.HTTP_200_OK
        }

    except Exception as e:
        return {
            "status": False,
            "data": [],
            "message": f"Error fetching trips: {str(e)}",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
        }




@router.get("/{trip_id}")
async def get_trip(trip_id: int, db: db_dependency, user: user_dependency):
    try:
        # 1. Fetch trip
        trip = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user.id).first()
        if not trip:
            return {
                "status": False,
                "data": None,
                "message": "Trip not found or doesn't belong to you.",
                "status_code": status.HTTP_404_NOT_FOUND
            }

        # 2. Fetch tourist places
        tourist_places = [
            {
                "id": place.id,
                "name": place.name,
                "description": place.description,
                "latitude": place.latitude,
                "longitude": place.longitude,
                "image_url": place.image_url
            }
            for place in trip.tourist_places
        ]
        tourist_places_status = True
        tourist_places_status_message = "Tourist places fetched successfully!"
        if not tourist_places:
            tourist_places = []
            tourist_places_status = False
            tourist_places_status_message = "Fetching tourist places based on your preferences..."

        # 3. Fetch itineraries
        itineraries = []
        for itinerary in trip.itinerary:
            itineraries.append({
                "day": itinerary.day,
                "date": itinerary.date.isoformat() if itinerary.date else None,
                "travel_tips": itinerary.travel_tips,
                "food": itinerary.food or [],
                "culture": itinerary.culture or [],
                "places": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "description": p.description,
                        "latitude": p.latitude,
                        "longitude": p.longitude,
                        "best_time_to_visit": p.best_time_to_visit
                    }
                    for p in itinerary.places
                ]
            })

        itineraries_status = True
        itineraries_status_message = "Itineraries fetched successfully!"
        if not itineraries:
            itineraries_status = False
            itineraries_status_message = "No itineraries found. Please generate one first."

        # 4. Fetch travel options
        travel_options_data = None
        travel_options_status = True
        travel_options_status_message = "Recommended travel options fetched successfully! "

        travel_options = db.query(TravelOptions).filter(TravelOptions.trip_id == trip.id).first()
        if travel_options:
            travel_options_data = travel_options.travel_data
        else:
            travel_options_status = False
            travel_options_status_message = "No travel options found. Please generate travel Options for your trip first."

        # 5. Prepare trip data
        trip_data = {
            "trip_id": trip.id,
            "trip_name": trip.trip_name,
            "destination": trip.destination,
            "base_location": trip.base_location,
            "start_date": trip.start_date.isoformat() if trip.start_date else None,
            "end_date": trip.end_date.isoformat() if trip.end_date else None,
            "budget": trip.budget,
            "travel_mode": trip.travel_mode.value if trip.travel_mode else None,
            "num_people": trip.num_people,
            "activities": trip.activities or [],
            "travelling_with": trip.travelling_with.value if trip.travelling_with else None,
            "tourist_places_status": tourist_places_status,
            "tourist_places_status_message": tourist_places_status_message,
            "tourist_places_list": tourist_places,
            "itineraries_status": itineraries_status,
            "itineraries_status_message": itineraries_status_message,
            "itineraries": itineraries,
            "travel_options_status": travel_options_status,
            "travel_options_status_message": travel_options_status_message,
            "travel_options": travel_options_data
        }

        # 6. Translate if needed
        settings = db.query(Settings).filter(Settings.user_id == user.id).first()
        target_lang = settings.native_language if settings and settings.native_language else "English"

        if target_lang != "English":
            trip_data = await translate_with_cache(db, trip_data, target_lang)

        return {
            "status": True,
            "data": trip_data,
            "message": "Trip fetched successfully",
            "status_code": status.HTTP_200_OK
        }

    except Exception as e:
        return {
            "status": False,
            "data": None,
            "message": f"Error fetching trip: {str(e)}",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
        }





# ✅ Delete Trip Endpoint
@router.delete("/{trip_id}")
async def delete_trip(trip_id: int, db: db_dependency, user: user_dependency):
    try:
        trip = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user.id).first()
        if not trip:
            return {
                "status": False,
                "message": "Trip not found or doesn't belong to you.",
                "status_code": status.HTTP_404_NOT_FOUND
            }

        db.delete(trip)
        db.commit()

        return {
            "status": True,
            "message": "Trip deleted successfully",
            "status_code": status.HTTP_200_OK
        }

    except Exception as e:
        return {
            "status": False,
            "message": f"Error deleting trip: {str(e)}",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
        }
    


# ✅ Delete Tourist Place Endpoint
@router.delete("/place/{place_id}")
async def delete_tourist_place(place_id: int, db: db_dependency, user: user_dependency):
    try:
        # Check if tourist place exists and belongs to the user's trip
        tourist_place = (
            db.query(TouristPlace)
            .join(Trip)  # join with trips table to check ownership
            .filter(TouristPlace.id == place_id, Trip.user_id == user.id)
            .first()
        )

        if not tourist_place:
            return {
                "status": False,
                "message": "Tourist place not found or doesn't belong to your trip.",
                "status_code": status.HTTP_404_NOT_FOUND
            }

        # Delete the tourist place
        db.delete(tourist_place)
        db.commit()

        return {
            "status": True,
            "message": "Tourist place deleted successfully",
            "status_code": status.HTTP_200_OK
        }

    except Exception as e:
        return {
            "status": False,
            "message": f"Error deleting tourist place: {str(e)}",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
        }




@router.get("/generate-itinerary/{trip_id}")
async def generate_itinerary(trip_id: int, db: db_dependency, user: user_dependency):
    try:
        # 1. Check trip exists
        trip = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user.id).first()
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found or doesn't belong to you.")

        # 2. Check if already exists
        existing_itinerary = db.query(Itinerary).filter(Itinerary.trip_id == trip_id).all()
        if existing_itinerary:
            result = []
            for item in existing_itinerary:
                places = [
                    {
                        "name": p.name,
                        "description": p.description,
                        "latitude": p.latitude,
                        "longitude": p.longitude,
                        "best_time_to_visit": p.best_time_to_visit
                    }
                    for p in item.places
                ]
                result.append({
                    "day": item.day,
                    "date": item.date.isoformat(),
                    "places": places,
                    "travel_tips": item.travel_tips,
                    "food": item.food,
                    "culture": item.culture
                })
            return {
                "status": True,
                "data": {
                    "trip_id": trip_id,
                    "itinerary": result
                },
                "message": "Itinerary loaded from database",
                "status_code": status.HTTP_200_OK
            }

        # 3. Run background task if not cached
        process_itinerary.delay(trip_id, user.id)

        return {
            "status": True,
            "data": None,
            "message": "Itinerary generation started. Please check back later.",
            "status_code": status.HTTP_202_ACCEPTED
        }

    except Exception as e:
        return {
            "status": False,
            "message": f"Error starting itinerary generation: {str(e)}",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
        }

