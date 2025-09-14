from fastapi import APIRouter, HTTPException, status , BackgroundTasks
from app.database.models import Trip , Settings, TouristPlace , Itinerary , ItineraryPlace
from app.database.schemas import CreateTripRequest, UpdateTripRequest
from app.utils.auth_helpers import user_dependency
from app.database.database import db_dependency
from app.utils.n8n import call_webhook_and_save_places , call_webhook_and_save_places_on_update
from app.utils.language_translation import translate_with_cache
from fastapi.responses import JSONResponse
import json
import datetime
import httpx
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
#         # Default values first
#         tourist_places_status = True
#         tourist_places_status_message = "Tourist places fetched successfully!"

#         if not tourist_places:
#                 tourist_places = []
#                 tourist_places_status = False
#                 tourist_places_status_message = "Fetching tourist places based on your preferences..."



#         # Prepare trip data
#         trip_data = {
#             "trip_id": trip.id,
#             "trip_name": trip.trip_name,
#             "destination": trip.destination,
#             "base_location": trip.base_location,
#             "start_date": trip.start_date.isoformat() if trip.start_date else None,
#             "end_date": trip.end_date.isoformat() if trip.end_date else None,
#             "budget": trip.budget,
#             "travel_mode": trip.travel_mode.value if trip.travel_mode else None,
#             "num_people": trip.num_people,
#             "activities": trip.activities or [],
#             "travelling_with": trip.travelling_with.value if trip.travelling_with else None,
#             "tourist_places_status": tourist_places_status,
#             "tourist_places_status_message": tourist_places_status_message if tourist_places_status_message else "Tourist places saved successfully!",
#             "tourist_places_list": tourist_places
                        
#         }

#         # Fetch user's preferred language
#         settings = db.query(Settings).filter(Settings.user_id == user.id).first()
#         target_lang = settings.native_language if settings and settings.native_language else "English"

#         # Translate full JSON if needed
#         if target_lang != "English":
#             trip_data = await translate_with_cache(db, trip_data, target_lang)

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

        # Fetch tourist places
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

        # Fetch itineraries
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

        # Flags for itineraries
        itineraries_status = True
        itineraries_status_message = "Itineraries fetched successfully!"
        if not itineraries:
            itineraries_status = False
            itineraries_status_message = "No itineraries found. Please generate one first."

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
            "tourist_places_status": tourist_places_status,
            "tourist_places_status_message": tourist_places_status_message,
            "tourist_places_list": tourist_places,
            "itineraries_status": itineraries_status,
            "itineraries_status_message": itineraries_status_message,
            "itineraries": itineraries
        }

        # Translate if needed
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




WEBHOOK_ITINERARY_URL = "http://localhost:5678/webhook/generate-trip-itinerary"


# @router.get("/generate-itinerary/{trip_id}")
# async def generate_itinerary(
#     trip_id: int,
#     db: db_dependency, 
#     user: user_dependency
# ):
#     try:
#         # 1. Fetch trip details
#         trip = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user.id).first()
#         if not trip:
#             return {
#                 "status": False,
#                 "message": "Trip not found or doesn't belong to you.",
#                 "status_code": status.HTTP_404_NOT_FOUND
#             }

#         # 2. Fetch tourist places for this trip
#         tourist_places = db.query(TouristPlace).filter(TouristPlace.trip_id == trip_id).all()

#         # 3. Prepare data for webhook
#         payload = {
#             "trip_id": trip.id,
#             "trip_name": trip.trip_name,
#             "destination": trip.destination,
#             "base_location": trip.base_location,
#             "start_date": trip.start_date.isoformat() if trip.start_date else None,
#             "end_date": trip.end_date.isoformat() if trip.end_date else None,
#             "budget": trip.budget,
#             "travel_mode": trip.travel_mode.value if trip.travel_mode else None,
#             "num_people": trip.num_people,
#             "activities": trip.activities or [],
#             "travelling_with": trip.travelling_with.value if trip.travelling_with else None,
#             "tourist_places": [
#                 {
#                     "id": place.id,
#                     "name": place.name,
#                     "description": place.description,
#                     "latitude": place.latitude,
#                     "longitude": place.longitude,
#                     "image_url": place.image_url
#                 }
#                 for place in tourist_places
#             ]
#         }

#         # 4. Call the external webhook
#         async with httpx.AsyncClient(timeout=500.0) as client:
#             response = await client.post(WEBHOOK_ITINERARY_URL, json=payload)

#         # 5. Return the webhook response
#         return {
#             "status": True,
#             "data": response.json() if response.status_code == 200 else None,
#             "message": "Itinerary generated successfully" if response.status_code == 200 else "Failed to generate itinerary",
#             "status_code": response.status_code
#         }

#     except Exception as e:
#         return {
#             "status": False,
#             "message": f"Error generating itinerary: {str(e)}",
#             "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
#         }





@router.get("/generate-itinerary/{trip_id}")
async def generate_itinerary(trip_id: int,db: db_dependency,user: user_dependency):
    try:
        # 1. Fetch trip details
        trip = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user.id).first()
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found or doesn't belong to you.")

        # 2. Check if itinerary already exists
        existing_itinerary = db.query(Itinerary).filter(Itinerary.trip_id == trip_id).all()
        if existing_itinerary:
            # Load itinerary from DB
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

        # 3. Fetch tourist places for this trip
        tourist_places = db.query(TouristPlace).filter(TouristPlace.trip_id == trip_id).all()

        # 4. Prepare data for webhook
        payload = {
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
            "tourist_places": [
                {
                    "id": place.id,
                    "name": place.name,
                    "description": place.description,
                    "latitude": place.latitude,
                    "longitude": place.longitude,
                    "image_url": place.image_url
                }
                for place in tourist_places
            ]
        }

        # 5. Call the external webhook
        async with httpx.AsyncClient(timeout=500.0) as client:
            response = await client.post(WEBHOOK_ITINERARY_URL, json=payload)
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Failed to generate itinerary")

            response_json = response.json()
            if isinstance(response_json, list) and len(response_json) > 0:
                output_data = response_json[0].get("output", {})
                itinerary_data = output_data.get("itinerary", [])
            else:
                itinerary_data = []
            # 6. Save itinerary to DB
            for day_item in itinerary_data:
                itinerary_entry = Itinerary(
                    day=day_item["day"],
                    date=datetime.date.fromisoformat(day_item["date"]),
                    travel_tips=day_item.get("travel_tips"),
                    food=day_item.get("food", []),
                    culture=day_item.get("culture", []),
                    trip_id=trip_id
                )
                db.add(itinerary_entry)
                db.flush()  # Get the ID before adding places

                for place in day_item.get("places", []):
                    place_entry = ItineraryPlace(
                        name=place["name"],
                        description=place.get("description"),
                        latitude=place.get("latitude"),
                        longitude=place.get("longitude"),
                        best_time_to_visit=place.get("best_time_to_visit"),
                        itinerary_id=itinerary_entry.id
                    )
                    db.add(place_entry)

            db.commit()

        return {
            "status": True,
            "data": {
                "trip_id": trip_id,
                "itinerary": itinerary_data
            },
            "message": "Itinerary generated and saved successfully",
            "status_code": status.HTTP_200_OK
        }

    except Exception as e:
        db.rollback()
        return {
            "status": False,
            "message": f"Error generating itinerary: {str(e)}",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
        }
    










