from app.database.models import TouristPlace
import httpx
from datetime import datetime

WEBHOOK_URL = "http://localhost:5678/webhook/places-using-gmap-scraper"

async def call_webhook_and_save_places(db, trip, user_id: int):
    """Call webhook first, then save tourist places only if data is returned."""

    # 1. Prepare payload for webhook
    payload = {
        "trip_id": trip.id,
        "user_id": user_id,
        "trip_name": trip.trip_name,
        "destination": trip.destination,
        "start_date": trip.start_date.isoformat() if isinstance(trip.start_date, datetime) else str(trip.start_date),
        "end_date": trip.end_date.isoformat() if isinstance(trip.end_date, datetime) else str(trip.end_date),
        "budget": trip.budget,
        "base_location": trip.base_location,
        "travel_mode": trip.travel_mode.value if trip.travel_mode else None,
        "num_people": trip.num_people,
        "activities": trip.activities or [],  # ✅ Updated to match JSONB list
        "travelling_with": trip.travelling_with.value if trip.travelling_with else None
    }

    try:
        # 2. Call webhook asynchronously
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(WEBHOOK_URL, json=payload)
            print(f"Webhook called: {response.status_code}")

        if response.status_code == 200:
            response_data = response.json()

            # Check for tourist places in response
            tourist_places = []
            if isinstance(response_data, list) and len(response_data) > 0:
                tourist_places = response_data[0].get("output", {}).get("TouristPlaces", [])

            # 3. Save tourist places if we got them
            if tourist_places:
                for place in tourist_places:
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

            return {"webhook_success": True, "places_saved": len(tourist_places)}

        return {"webhook_success": False, "places_saved": 0}

    except Exception as e:
        print(f"Error calling webhook: {e}")
        return {"webhook_success": False, "places_saved": 0}
    



async def call_webhook_and_save_places_on_update(db, trip, user_id: int):
    """Call webhook first, then save tourist places only if data is returned."""
    
    # 1. Prepare payload for webhook
    payload = {
        "trip_id": trip.id,
        "user_id": user_id,
        "trip_name": trip.trip_name,
        "destination": trip.destination,
        "start_date": trip.start_date.isoformat() if isinstance(trip.start_date, datetime) else str(trip.start_date),
        "end_date": trip.end_date.isoformat() if isinstance(trip.end_date, datetime) else str(trip.end_date),
        "budget": trip.budget,
        "base_location": trip.base_location,
        "travel_mode": trip.travel_mode.value if trip.travel_mode else None,
        "num_people": trip.num_people,
        "activities": trip.activities or [],
        "travelling_with": trip.travelling_with.value if trip.travelling_with else None
    }

    try:
        # 2. Call webhook asynchronously
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(WEBHOOK_URL, json=payload)
            print(f"Webhook called: {response.status_code}")

        if response.status_code != 200:
            return {"webhook_success": False, "places_saved": 0}

        response_data = response.json()

        # Check for tourist places in response
        tourist_places = []
        if isinstance(response_data, list) and len(response_data) > 0:
            tourist_places = response_data[0].get("output", {}).get("TouristPlaces", [])

        # 3. Save tourist places if we got them, avoiding duplicates
        saved_count = 0
        for place in tourist_places:
            lat = place.get("GeoCoordinates", {}).get("lat")
            lng = place.get("GeoCoordinates", {}).get("lng")

            if lat is None or lng is None:
                continue  # skip invalid coordinates

            # Check if this place already exists for the trip
            exists = db.query(TouristPlace).filter(
                TouristPlace.trip_id == trip.id,
                TouristPlace.latitude == lat,
                TouristPlace.longitude == lng
            ).first()

            if exists:
                continue  # skip duplicates

            # Save new place
            tourist_place = TouristPlace(
                trip_id=trip.id,
                name=place.get("Name"),
                description=place.get("Description"),
                latitude=lat,
                longitude=lng,
                image_url=place.get("ImageURL")
            )
            db.add(tourist_place)
            saved_count += 1

        if saved_count > 0:
            db.commit()

        return {"webhook_success": True, "places_saved": saved_count}

    except Exception as e:
        print(f"Error calling webhook: {e}")
        return {"webhook_success": False, "places_saved": 0}
