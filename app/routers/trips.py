from fastapi import APIRouter, HTTPException, status
from app.database.models import Trip , Settings, TouristPlace , Itinerary , ItineraryPlace, TravelOptions
from app.database.schemas import CreateTripRequest, UpdateTripRequest
from app.utils.auth_helpers import user_dependency
from app.database.database import db_dependency
from app.utils.n8n import call_webhook_and_save_places , call_webhook_and_save_places_on_update
from app.task.trip_tasks import process_trip_webhook , process_itinerary
from app.utils.language_translation import translate_with_cache
import datetime
router = APIRouter(prefix="/trips", tags=["Trips"])


@router.post("/create")
async def create_trip(
    request: CreateTripRequest,
    db: db_dependency,
    user: user_dependency
):
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

    # Create trip
    new_trip = Trip(
        user_id=user.id,
        trip_name=request.trip_name,
        budget=request.budget,
        start_date=request.start_date,
        end_date=request.end_date,
        journey_start_date = request.journey_start_date,
        return_journey_date = request.return_journey_date,
        destination=request.destination,
        base_location=request.base_location,
        travel_mode=request.travel_mode,
        num_people=request.num_people,
        activities=request.activities or [],
        travelling_with=request.travelling_with
    )

    db.add(new_trip)
    db.commit()
    db.refresh(new_trip)

    # Run webhook processing in background
    process_trip_webhook.delay(new_trip.id, user.id)

    return {
        "status": True,
        "data": {
            "trip_id": new_trip.id,
            "trip_name": new_trip.trip_name
        },
        "message": "Trip created successfully. Processing places in background.",
        "status_code": status.HTTP_201_CREATED
    }






@router.put("/update/{trip_id}")
async def update_trip(
    trip_id: int,
    request: UpdateTripRequest,
    db: db_dependency,
    user: user_dependency
):
    try:
        # 1. Check if trip exists
        trip = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user.id).first()
        if not trip:
            return {
                "status": False,
                "message": "Trip not found or you don't have permission to update this trip.",
                "status_code": status.HTTP_404_NOT_FOUND
            }

        # 2. Update trip fields
        trip.budget = request.budget
        trip.start_date = request.start_date
        trip.end_date = request.end_date
        trip.journey_start_date = request.journey_start_date
        trip.return_journey_date = request.return_journey_date
        trip.travel_mode = request.travel_mode
        trip.num_people = request.num_people
        trip.activities = request.activities if request.activities else []
        trip.travelling_with = request.travelling_with

        db.commit()
        db.refresh(trip)

        # 3. Call webhook via Celery (Non-blocking)
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
                "journey_start_date" : t.journey_start_date,
                "return_journey_date" : t.return_journey_date,
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
            "journey_start_date" : trip.journey_start_date.isoformat() if trip.journey_start_date else None,
            "return_journey_date" : trip.return_journey_date.isoformat() if trip.return_journey_date else None,
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

