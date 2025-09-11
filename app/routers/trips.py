from fastapi import APIRouter, HTTPException, status , BackgroundTasks
from app.database.models import Trip , Settings
from app.database.schemas import CreateTripRequest, UpdateTripRequest
from app.utils.auth_helpers import user_dependency
from app.database.database import db_dependency
from app.utils.n8n import call_webhook_and_save_places , call_webhook_and_save_places_on_update
from app.utils.language_translation import translate_with_cache
from fastapi.responses import JSONResponse
import json
import datetime
router = APIRouter(prefix="/trips", tags=["Trips"])


  
@router.post("/create") # without translation
async def create_trip(
    request: CreateTripRequest,
    db: db_dependency,
    user: user_dependency
):
    try:
        # 1. Check if trip with same name exists for this user
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

        # 2. Create new trip
        new_trip = Trip(
            user_id=user.id,
            trip_name=request.trip_name,
            budget=request.budget,
            start_date=request.start_date,
            end_date=request.end_date,
            destination=request.destination,
            base_location=request.base_location,
            travel_mode=request.travel_mode,
            num_people=request.num_people,
            activities=request.activities or [],  # ✅ store list of strings, default empty list
            travelling_with=request.travelling_with
        )

        db.add(new_trip)
        db.commit()
        db.refresh(new_trip)

        # Call webhook first → save places only if webhook succeeds
        result = await call_webhook_and_save_places(db, new_trip, user.id)   #Add to non blocking io
    

        return {
            "status": True,
            "data": {
                "trip_id": new_trip.id,
                "trip_name": new_trip.trip_name,
                "places_saved": result["places_saved"]
            },
            "message": "Trip created successfully",
            "status_code": status.HTTP_201_CREATED
        }

    except Exception as e:
        return {
            "status": False,
            "message": f"Error creating trip: {str(e)}",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
        }





# @router.post("/create")
# async def create_trip(
#     request: CreateTripRequest,
#     db: db_dependency,
#     user: user_dependency,
#     background_tasks: BackgroundTasks
# ):
#     try:
#         existing_trip = db.query(Trip).filter(
#             Trip.user_id == user.id,
#             Trip.trip_name == request.trip_name
#         ).first()
#         if existing_trip:
#             return {
#                 "status": False,
#                 "message": "Trip with this name already exists.",
#                 "status_code": status.HTTP_400_BAD_REQUEST
#             }

#         new_trip = Trip(
#             user_id=user.id,
#             trip_name=request.trip_name,
#             budget=request.budget,
#             start_date=request.start_date,
#             end_date=request.end_date,
#             destination=request.destination,
#             base_location=request.base_location,
#             travel_mode=request.travel_mode,
#             num_people=request.num_people,
#             activities=request.activities or [],
#             travelling_with=request.travelling_with
#         )

#         db.add(new_trip)
#         db.commit()
#         db.refresh(new_trip)

#         #background_tasks.add_task(call_webhook_and_save_places, db, new_trip, user.id)

#         settings = db.query(Settings).filter(Settings.user_id == user.id).first()
#         target_lang = settings.native_language if settings and settings.native_language else "English"

#         response_data = {
#             "trip_id": new_trip.id,
#             "trip_name": new_trip.trip_name
#         }

#         # ✅ Translate entire JSON block if language is not English
#         if target_lang != "English":
#             response_data = await translate_with_cache(db, response_data, target_lang)

#             # try:
#             #     response_data = json.loads(translated_string)
#             # except json.JSONDecodeError:
#             #     pass  # fallback to original if translation fails

#         return {
#             "status": True,
#             "data": response_data,
#             "message": "Trip created successfully. Places will be saved in the background.",
#             "status_code": status.HTTP_201_CREATED
#         }

#     except Exception as e:
#         return {
#             "status": False,
#             "message": f"Error creating trip: {str(e)}",
#             "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
#         }




@router.put("/update/{trip_id}")
async def update_trip(trip_id: int, request: UpdateTripRequest, db: db_dependency, user: user_dependency):
    try:
        trip = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user.id).first()
        if not trip:
            return {
                "status": False,
                "message": "Trip not found or you don't have permission to update this trip.",
                "status_code": status.HTTP_404_NOT_FOUND
            }

        # Fully replace all fields
        trip.budget = request.budget
        trip.start_date = request.start_date
        trip.end_date = request.end_date
        trip.travel_mode = request.travel_mode
        trip.num_people = request.num_people
        trip.activities = request.activities if request.activities is not None else []
        trip.travelling_with = request.travelling_with

        db.commit()
        db.refresh(trip)

        # Call webhook and save tourist places, avoiding duplicates
        result = await call_webhook_and_save_places_on_update(db, trip, user.id)

        return {
            "status": True,
            "data": {
                "trip_id": trip.id,
                "trip_name": trip.trip_name,
                "activities": trip.activities,
                "new_places_saved": result["places_saved"]
            },
            "message": "Trip updated successfully",
            "status_code": status.HTTP_200_OK
        }

    except Exception as e:
        return {
            "status": False,
            "message": f"Error updating trip: {str(e)}",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
        }

# ✅ Get All Trips for a User - without translate 
# @router.get("/")
# async def get_all_trips(db: db_dependency, user: user_dependency):
#     try:
#         trips = db.query(Trip).filter(Trip.user_id == user.id).all()
#         if not trips:
#             return {
#                 "status": False,
#                 "data": [],
#                 "message": "No trips found for this user.",
#                 "status_code": status.HTTP_404_NOT_FOUND
#             }

#         trips_data = [
#             {
#                 "trip_id": t.id,
#                 "trip_name": t.trip_name,
#                 "destination": t.destination,
#                 "base_location": t.base_location,
#                 "start_date": t.start_date,
#                 "end_date": t.end_date,
#                 "budget": t.budget,
#                 "travel_mode": t.travel_mode.value if t.travel_mode else None,
#                 "num_people": t.num_people,
#                 "activities": t.activities or [],  # ✅ updated to JSONB list
#                 "travelling_with": t.travelling_with.value if t.travelling_with else None
#             }
#             for t in trips
#         ]

#         return {
#             "status": True,
#             "data": trips_data,
#             "message": "Trips fetched successfully",
#             "status_code": status.HTTP_200_OK
#         }

#     except Exception as e:
#         return {
#             "status": False,
#             "data": [],
#             "message": f"Error fetching trips: {str(e)}",
#             "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
#         }


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





# @router.get("/{trip_id}")
# async def get_trip(trip_id: int, db: db_dependency, user: user_dependency):
#     try:
#         trip = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user.id).first()
#         if not trip:
#             return {
#                 "status": False,
#                 "data": None,
#                 "message": "Trip not found or doesn't belong to you.",
#                 "status_code": status.HTTP_404_NOT_FOUND
#             }

#         # Fetch associated tourist places
#         tourist_places = [
#             {
#                 "id": place.id,
#                 "name": place.name,
#                 "description": place.description,
#                 "latitude": place.latitude,
#                 "longitude": place.longitude,
#                 "image_url": place.image_url
#             }
#             for place in trip.tourist_places
#         ]

#         if not tourist_places:
#             tourist_places = "No tourist places found for this trip."

#         trip_data = {
#             "trip_id": trip.id,
#             "trip_name": trip.trip_name,
#             "destination": trip.destination,
#             "base_location": trip.base_location,
#             "start_date": trip.start_date,
#             "end_date": trip.end_date,
#             "budget": trip.budget,
#             "travel_mode": trip.travel_mode.value if trip.travel_mode else None,
#             "num_people": trip.num_people,
#             "activities": trip.activities or [],
#             "travelling_with": trip.travelling_with.value if trip.travelling_with else None,
#             "tourist_places": tourist_places
#         }

#         return {
#             "status": True,
#             "data": trip_data,
#             "message": "Trip fetched successfully",
#             "status_code": status.HTTP_200_OK
#         }

#     except Exception as e:
#         return {
#             "status": False,
#             "data": None,
#             "message": f"Error fetching trip: {str(e)}",
#             "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
#         }



@router.get("/{trip_id}")
async def get_trip(trip_id: int, db: db_dependency, user: user_dependency):
    try:
        trip = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user.id).first()
        if not trip:
            return {
                "status": False,
                "data": None,
                "message": "Trip not found or doesn't belong to you.",
                "status_code": status.HTTP_404_NOT_FOUND
            }

        # Fetch associated tourist places
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
        if not tourist_places:
            tourist_places = "No tourist places found for this trip."

        # Prepare trip data
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
            "tourist_places": tourist_places
        }

        # Fetch user's preferred language
        settings = db.query(Settings).filter(Settings.user_id == user.id).first()
        target_lang = settings.native_language if settings and settings.native_language else "English"

        # Translate full JSON if needed
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