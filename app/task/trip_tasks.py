from app.celery_worker import celery_app
from app.database.database import SessionLocal
from app.database.models import Trip, TouristPlace
import requests
from dotenv import load_dotenv
load_dotenv()
import os


WEBHOOK_URL_GMAP_SCRAPPER_PLACEDESC_GEOCORDINATES=os.getenv("WEBHOOK_URL_GMAP_SCRAPPER_PLACEDESC_GEOCORDINATES")

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
            response = requests.post(WEBHOOK_URL_GMAP_SCRAPPER_PLACEDESC_GEOCORDINATES, json=payload, timeout=120)
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