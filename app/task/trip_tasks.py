from app.celery_worker import celery_app
from app.database.database import SessionLocal
from app.database.models import Trip, TouristPlace , ItineraryPlace, Itinerary , TravelOptions
from app.aiworkflow.get_travelling_options import get_travel_options_gemini
import datetime
import requests
from dotenv import load_dotenv
load_dotenv()
import os

# Loading N8N WebHook Url 
WEBHOOK_URL_GMAP_SCRAPPER_PLACEDESC_GEOCORDINATES=os.getenv("WEBHOOK_URL_GMAP_SCRAPPER_PLACEDESC_GEOCORDINATES")
WEBHOOK_ITINERARY_GENERATION_URL = os.getenv("WEBHOOK_ITINERARY_GENERATION_URL")
WEBHOOK_GET_TRAVEL_MODE_URL = os.getenv("WEBHOOK_GET_TRAVEL_MODE_URL")

@celery_app.task
def process_trip_webhook(trip_id: int, user_id: int):
    """
    Celery task to process a trip:
    1. Creates a new DB session
    2. Loads the trip
    3. Calls the webhook API
    4. Stores Tourist Places results in DB
    """
    db = SessionLocal()
    try:
        # --- Fetch trip ---
        trip = db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            print(f"[Trip {trip_id}] not found. Skipping webhook processing.")
            return

        # --- Call Webhook API ---
        try:
            payload = {
                "destination": trip.destination,
                "start_date": str(trip.start_date),
                "end_date": str(trip.end_date),
                "num_people": trip.num_people,
                "activities": trip.activities or []
            }
            response = requests.post(WEBHOOK_URL_GMAP_SCRAPPER_PLACEDESC_GEOCORDINATES, json=payload, timeout=1000)
            response.raise_for_status()
            webhook_data = response.json()
        except Exception as e:
            print(f"[Trip {trip_id}] Webhook call failed: {str(e)}")
            return

        # --- Parse webhook data ---
        if isinstance(webhook_data, list) and len(webhook_data) > 0:
            webhook_data = webhook_data[0]  # Get first element
        else:
            print(f"[Trip {trip_id}] Webhook response is empty or invalid.")
            return

        places_list = []
        if "output" in webhook_data and "TouristPlaces" in webhook_data["output"]:
            places_list = webhook_data["output"]["TouristPlaces"]

        if not places_list:
            print(f"[Trip {trip_id}] No tourist places found in webhook response.")
            return

        # --- Save Tourist Places to DB ---
        for place in places_list:
            tourist_place = TouristPlace(
                trip_id=trip.id,
                name=place.get("Name"),
                description=place.get("Description"),
                latitude=place.get("GeoCoordinates", {}).get("lat"),
                longitude=place.get("GeoCoordinates", {}).get("lng"),
                image_url=place.get("ImageURL")
            )
            db.add(tourist_place)

        db.commit()
        print(f"[Trip {trip_id}] Webhook processing completed successfully. {len(places_list)} places saved.")

    except Exception as e:
        db.rollback()
        print(f"[Trip {trip_id}] Error processing trip: {str(e)}")
        raise e
    finally:
        db.close()




@celery_app.task
def process_itinerary(trip_id: int, user_id: int):
    db = SessionLocal()
    try:
        # 1. Fetch trip
        trip = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user_id).first()
        if not trip:
            print(f"[Itinerary] Trip {trip_id} not found. Skipping.")
            return

        # 2. Fetch tourist places
        tourist_places = db.query(TouristPlace).filter(TouristPlace.trip_id == trip_id).all()

        # 3. Prepare payload
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

        # 4. Call webhook
        try:
            response = requests.post(WEBHOOK_ITINERARY_GENERATION_URL, json=payload, timeout=500)
            response.raise_for_status()
            response_json = response.json()
        except Exception as e:
            print(f"[Itinerary] Webhook call failed: {str(e)}")
            return

        # 5. Extract itinerary
        if isinstance(response_json, list) and len(response_json) > 0:
            output_data = response_json[0].get("output", {})
            itinerary_data = output_data.get("itinerary", [])
        else:
            itinerary_data = []

        if not itinerary_data:
            print(f"[Itinerary] No itinerary data for Trip {trip_id}.")
            return

        # 6. Save to DB
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
            db.flush()  # Get ID before adding places

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
        print(f"[Itinerary] Saved itinerary for Trip {trip_id}. Days: {len(itinerary_data)}")

    except Exception as e:
        db.rollback()
        print(f"[Itinerary] Error processing Trip {trip_id}: {str(e)}")
    finally:
        db.close()





@celery_app.task
def process_travel_modes(trip_id: int, user_id: int):
    db = SessionLocal()
    try:
        trip = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user_id).first()
        if not trip:
            print(f"[Trip {trip_id}] Trip not found. Skipping travel modes processing.")
            return

        # Prepare payload for webhook
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
            "travelling_with": trip.travelling_with.value if trip.travelling_with else None
        }

        # Call webhook
        try:
            response = requests.post(WEBHOOK_GET_TRAVEL_MODE_URL, json=payload, timeout=500)
            response.raise_for_status()
            full_data = response.json()
        except Exception as e:
            print(f"[Trip {trip_id}] Webhook travel mode request failed: {str(e)}")
            return

        # Extract travel_options
        travel_options = None
        if isinstance(full_data, list) and "output" in full_data[0]:
            travel_options = full_data[0]["output"].get("travel_options")
        elif "output" in full_data:
            travel_options = full_data["output"].get("travel_options")

        if not travel_options:
            print(f"[Trip {trip_id}] Invalid or empty travel options in webhook response")
            return

        # Save travel options to DB
        new_travel = TravelOptions(trip_id=trip.id, travel_data=travel_options)
        db.add(new_travel)
        db.commit()
        print(f"[Trip {trip_id}] Travel options saved successfully.")

    except Exception as e:
        db.rollback()
        print(f"[Trip {trip_id}] Error processing travel modes: {str(e)}")
    finally:
        db.close()




# New Dependency 

@celery_app.task
def get_travelling_options(trip_id, user_id, base_location, destination, travel_mode):
    db = SessionLocal()
    try:
        trip = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user_id).first()
        if not trip:
            print(f"[Trip {trip_id}] Trip not found. Skipping travel modes processing.")
            return

        # Call webhook
        try:
            full_data = get_travel_options_gemini(trip_id, base_location, destination, travel_mode)
            # full_data is already a dict, no .json() needed
            print(f"[Trip {trip_id}] Raw Response: {full_data}")
        except Exception as e:
            print(f"[Trip {trip_id}] Travel Options request failed: {str(e)}")
            return

        # Extract travel_options safely
        travel_options = full_data.get("Travelling _Modes") or full_data.get("travel_options")
        if not travel_options:
            print(f"[Trip {trip_id}] Invalid or empty travel options in webhook response")
            return

        # Save travel options to DB
        new_travel = TravelOptions(trip_id=trip.id, travel_data=travel_options)
        db.add(new_travel)
        db.commit()
        print(f"[Trip {trip_id}] Travel options saved successfully.")

    except Exception as e:
        db.rollback()
        print(f"[Trip {trip_id}] Error processing travel modes: {str(e)}")
    finally:
        db.close()


def get_time_period(hour):
    """Return time period based on 24-hour time."""
    if 5 <= hour < 12:
        return "Morning"
    elif 12 <= hour < 17:
        return "Afternoon"
    elif 17 <= hour < 21:
        return "Evening"
    else:
        return "Night"
def extract_station_name(raw_name: str) -> str:
    """
    Extract the first word of the station/city name.
    Works for:
      - "Mumbai (CSTM)" → "Mumbai"
      - "Pune" → "Pune"
      - "Haridwar, Uttarakhand, India" → "Haridwar"
    """
    # Remove parentheses content first
    cleaned_name = raw_name.split("(")[0].strip()
    # Take first word before any comma or space
    first_word = cleaned_name.split(",")[0].split()[0].strip()
    return first_word


from app.database.database import SessionLocal
from app.database.models import Trip, TravelOptions, UserPreferences
from app.utils.easemytrip import search_trains, get_station_code
from datetime import datetime, timedelta
@celery_app.task
def generate_travel_booking_suggestions(trip_id, user_id):
    """Generate detailed travel booking suggestions for all modes: Train, Bus, Flight, Taxi."""
    db = SessionLocal()
    try:
        trip = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user_id).first()
        if not trip:
            print(f"[Trip {trip_id}] Trip not found")
            return

        # Fetch user preferences
        user_pref = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        preferred_departure_time = (
            user_pref.preferred_departure_time.value if user_pref and user_pref.preferred_departure_time else None
        )

        # Fetch saved TravelOptions
        saved_travel_options = db.query(TravelOptions).filter(TravelOptions.trip_id == trip_id).first()
        travel_options_data = saved_travel_options.travel_data if saved_travel_options else []

        suggestions = []

        for leg in travel_options_data:
            mode = leg.get("mode")
            from_loc = leg.get("from")
            to_loc = leg.get("to")

            leg_suggestions = []

            # ---------------- Train ----------------
            if mode == "Train":
                from_station = extract_station_name(from_loc)
                to_station = extract_station_name(to_loc)
                from_code, from_name = get_station_code(from_station)
                to_code, to_name = get_station_code(to_station)

                if not from_code or not to_code:
                    print(f"[Trip {trip_id}] Invalid station codes for leg {from_loc} -> {to_loc}")
                    continue

                current_date = trip.journey_start_date
                while current_date <= trip.return_journey_date:
                    trains = search_trains(from_code, to_code, current_date.strftime("%d/%m/%Y"))
                    if not trains:
                        current_date += timedelta(days=1)
                        continue

                    # Filter by preferred departure time
                    if preferred_departure_time:
                        trains = [
                            t for t in trains
                            if t.get("departureTime") and
                            get_time_period(int(t["departureTime"].split(":")[0])) == preferred_departure_time
                        ]

                    for train in trains:
                        leg_suggestions.append({
                            "train_name": train.get("trainName"),
                            "train_number": train.get("trainNumber"),
                            "departure_time": train.get("departureTime"),
                            "arrival_time": train.get("arrivalTime"),
                            "duration": train.get("duration"),
                            "source": from_loc,
                            "destination": to_loc,
                            "classes": train.get("classes", []),
                            "booking_url": f"https://railways.easemytrip.com/TrainListInfo/{from_name.replace(' ','')}({from_code})-to-{to_name.replace(' ','')}({to_code})/2/{current_date.strftime('%d-%m-%Y')}"
                        })
                    current_date += timedelta(days=1)

            # ---------------- Bus ----------------
            elif mode == "Bus":
                leg_suggestions.append({
                    "bus_name": leg.get("Note") or "Bus service",
                    "from_city": from_loc,
                    "to_city": to_loc,
                    "approx_time": leg.get("approx_time"),
                    "approx_cost": leg.get("approx_cost"),
                    "booking_url": None
                })

            # ---------------- Flight ----------------
            elif mode == "Flight":
                leg_suggestions.append({
                    "airline": leg.get("airline") or "Flight",
                    "flight_number": leg.get("flight_number"),
                    "from_city": from_loc,
                    "to_city": to_loc,
                    "departure_time": leg.get("departure_time"),
                    "arrival_time": leg.get("arrival_time"),
                    "duration": leg.get("approx_time"),
                    "fare": leg.get("approx_cost"),
                    "booking_url": leg.get("booking_url")
                })

            # ---------------- Taxi / Cab / Other ----------------
            elif mode in ["Taxi", "Cab", "Trek"]:
                leg_suggestions.append({
                    "service": mode,
                    "from_city": from_loc,
                    "to_city": to_loc,
                    "approx_time": leg.get("approx_time"),
                    "approx_cost": leg.get("approx_cost"),
                    "note": leg.get("Note")
                })

            suggestions.append({
                "from": from_loc,
                "to": to_loc,
                "mode": mode,
                "options": leg_suggestions
            })

        return {
            "trip_id": trip_id,
            "travel_booking_suggestions": suggestions
        }

    except Exception as e:
        print(f"[Trip {trip_id}] Error generating travel suggestions: {e}")
    finally:
        db.close()