from fastapi import APIRouter, HTTPException, status
from app.database.models import Trip , Settings, TouristPlace
from app.database.schemas import CreateTripRequest, UpdateTripRequest
from app.utils.auth_helpers import user_dependency
from app.database.database import db_dependency
from app.task.trip_tasks import process_tourist_places , process_trip_itinerary , fetch_and_save_destination_data
from app.utils.language_translation import translate_with_cache
from app.aiworkflow.get_current_weather_conditions import fetch_travel_update
import json
from app.database.models import Trip, UserPreferences

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

            missing_fields = []
            if not (request.base_location or getattr(preferences, "base_location", None)):
                missing_fields.append("base_location")

            if missing_fields:
                return {
                    "status": False,
                    "message": (
                        "Missing required data. The following fields are not provided in the request "
                        "and are not set in user preferences: " + ", ".join(missing_fields)
                    ),
                    "status_code": status.HTTP_400_BAD_REQUEST
                }

        # 2. Apply values (fallback logic)
        budget = request.budget if request.budget is not None else (preferences.default_budget if preferences else None)
        base_location = request.base_location if request.base_location else (preferences.base_location if preferences else None)
        num_people = request.num_people if request.num_people is not None else (preferences.num_people if preferences and hasattr(preferences, "num_people") else None)
        activities = request.activities if request.activities is not None else (preferences.activities if preferences else [])
        travelling_with = request.travelling_with if request.travelling_with is not None else (preferences.travelling_with if preferences else None)

        # 3. Create trip record WITHOUT destination info (will be fetched in background)
        new_trip = Trip(
            user_id=user.id,
            trip_name=request.trip_name,
            budget=budget,
            start_date=start_date,
            end_date=end_date,
            destination=request.destination,
            base_location=base_location,
            num_people=num_people,
            activities=activities or [],
            travelling_with=travelling_with
        )

        db.add(new_trip)
        db.commit()
        db.refresh(new_trip)

        # 4. Trigger Celery tasks
        fetch_and_save_destination_data.delay(new_trip.id)
        process_tourist_places.delay(new_trip.id, new_trip.destination, new_trip.activities if new_trip.activities else [])
        process_trip_itinerary.delay(new_trip.id)

        return {
            "status": True,
            "data": {
                "trip_id": new_trip.id,
                "trip_name": new_trip.trip_name,
            },
            "message": "Trip created successfully. Destination data and itinerary processing started in background.",
            "status_code": status.HTTP_201_CREATED
        }

    except Exception as e:
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
        trip.num_people = request.num_people
        trip.activities = request.activities if request.activities else []
        trip.travelling_with = request.travelling_with

        db.commit()
        db.refresh(trip)

        process_trip_itinerary.delay(trip.id,)

        return {
            "status": True,
            "data": {
                "trip_id": trip.id,
                "trip_name": trip.trip_name,
                "activities": trip.activities
            },
            "message": "Trip updated successfully. Processing Trip Itinerary in background.",
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
                "destination_full_name": t.destination_full_name,
                "destination_details": t.destination_details,
                "destination_image_url": t.destination_image_url or [],
                "base_location": t.base_location,
                "start_date": t.start_date.isoformat() if t.start_date else None,
                "end_date": t.end_date.isoformat() if t.end_date else None,
                "budget": t.budget,
                "num_people": t.num_people,
                "activities": t.activities or [],
                "travelling_with": t.travelling_with.value if t.travelling_with else None
            }
            for t in trips
        ]

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

        # 4. Prepare trip data with new fields
        trip_data = {
            "trip_id": trip.id,
            "trip_name": trip.trip_name,
            "destination": trip.destination,
            "destination_full_name": trip.destination_full_name,
            "destination_details": trip.destination_details,
            "destination_image_url": trip.destination_image_url or [],
            "base_location": trip.base_location,
            "start_date": trip.start_date.isoformat() if trip.start_date else None,
            "end_date": trip.end_date.isoformat() if trip.end_date else None,
            "budget": trip.budget,
            "num_people": trip.num_people,
            "activities": trip.activities or [],
            "travelling_with": trip.travelling_with.value if trip.travelling_with else None,
            "tourist_places_status": tourist_places_status,
            "tourist_places_status_message": tourist_places_status_message,
            "tourist_places_list": tourist_places,
            "itineraries_status": itineraries_status,
            "itineraries_status_message": itineraries_status_message,
            "itineraries": itineraries
        }

        # 5. Translate if needed
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




@router.get("/weather_conditions/{trip_id}")
async def get_trip_weather(trip_id: int, db: db_dependency, user: user_dependency):
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

        # 2. Fetch destination from Trip model
        destination = trip.destination
        if not destination:
            return {
                "status": False,
                "data": None,
                "message": "Trip destination not found.",
                "status_code": status.HTTP_400_BAD_REQUEST
            }

        # 3. Call fetch_travel_update() with destination
        params = json.dumps({"destination": destination})
        travel_update = fetch_travel_update(params)

        # 4. If error occurred in fetch_travel_update
        if "error" in travel_update:
            return {
                "status": False,
                "data": None,
                "message": f"Error fetching travel update: {travel_update['error']}",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
            }

        # 5. Include travel update in final response
        response_data = {
            "trip_id": trip.id,
            "trip_name": trip.trip_name,
            "destination": destination,
            "travel_update": travel_update
        }

        # 6. Optional translation (if user language != English)
        settings = db.query(Settings).filter(Settings.user_id == user.id).first()
        target_lang = settings.native_language if settings and settings.native_language else "English"

        if target_lang != "English":
            response_data = await translate_with_cache(db, response_data, target_lang)

        return {
            "status": True,
            "data": response_data,
            "message": "Weather and travel conditions fetched successfully",
            "status_code": status.HTTP_200_OK
        }

    except Exception as e:
        return {
            "status": False,
            "data": None,
            "message": f"Error fetching weather conditions: {str(e)}",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
        }