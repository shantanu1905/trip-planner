from app.celery_worker import celery_app
from app.database.database import SessionLocal
from app.database.models import Trip, TouristPlace , ItineraryPlace, Itinerary , TravelOptions
from app.aiworkflow.get_travelling_options_old import get_travel_options_gemini
from app.aiworkflow.get_travel_bookings import search_travel_tickets
from app.aiworkflow.get_travel_locations import get_tourist_places_for_destination
from app.aiworkflow.get_travel_itinerary import generate_trip_itinerary
from typing import List, Dict
from datetime import datetime, timedelta
import re
from dotenv import load_dotenv
load_dotenv()



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



@celery_app.task
def get_detailed_travelling_options(trip_id, user_id, start_date):
    db = SessionLocal()
    try:
        # Fetch Trip
        trip = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user_id).first()
        if not trip:
            print(f"[Trip {trip_id}] Trip not found. Skipping travel modes processing.")
            return

        # Fetch existing TravelOptions
        travel_opt = db.query(TravelOptions).filter(TravelOptions.trip_id == trip_id).first()
        if not travel_opt:
            print(f"[Trip {trip_id}] TravelOptions not found. Generate base travel modes.")
            return


        base_legs = travel_opt.travel_data
        if not isinstance(base_legs, list):
            print(f"[Trip {trip_id}] Invalid travel_data format, expected list of legs.")
            return

        # Wrap into required forma
        input_json= {
            "legs":base_legs,
            "start_date":str(start_date).split(" ")[0]
        }

        # Call LLM function
        try:
            detailed_travel_options_data = search_travel_tickets(input_json)
            print(f"[Trip {trip_id}] Raw Response: {detailed_travel_options_data}")
        except Exception as e:
            print(f"[Trip {trip_id}] Travel Options request failed: {str(e)}")
            return

        # ✅ Save full new JSON output instead of partial extraction
        travel_opt.travel_data = detailed_travel_options_data
        db.commit()
        db.refresh(travel_opt)
        print(f"[Trip {trip_id}] Travel options updated successfully : {detailed_travel_options_data}")


        # ✅ Compute final destination date
        final_date = None
        for leg in detailed_travel_options_data.get("travelling_options", []):
            journey_date_str = leg.get("journey_date")
            approx_time_str = leg.get("approx_time", "0 hours")

            # Parse journey_date
            if journey_date_str:
                leg_date = datetime.strptime(journey_date_str, "%Y-%m-%d")
            else:
                leg_date = datetime.strptime(str(start_date).split(" ")[0], "%Y-%m-%d")

            # Parse approx_time like "22 hours" or "1 day 5 hours"
            hours = 0
            days = 0
            match_hours = re.search(r"(\d+)\s*hours?", approx_time_str)
            match_days = re.search(r"(\d+)\s*days?", approx_time_str)
            if match_hours:
                hours = int(match_hours.group(1))
            if match_days:
                days = int(match_days.group(1))

            leg_end_datetime = leg_date + timedelta(days=days, hours=hours)
            final_date = leg_end_datetime  # Update final date for each leg

        if final_date:
            trip.itinerary_start_date = final_date.date()
            db.commit()
            print(f"[Trip {trip_id}] Itinerary start date updated to {trip.itinerary_start_date}")

    except Exception as e:
        db.rollback()
        print(f"[Trip {trip_id}] Error processing travel modes: {str(e)}")
    finally:
        db.close()





@celery_app.task
def process_tourist_places(trip_id: int, destination: str, activities: List[str]):
    """
    Celery task to fetch and store tourist places for a trip.
    
    Args:
        trip_id: ID of the trip to associate tourist places with
        destination: Destination city/location name
        activities: List of activities (e.g., ["adventure", "religious", "cultural"])
    """
    db = SessionLocal()
    try:
        # Verify trip exists
        trip = db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            print(f"[Trip {trip_id}] Trip not found. Skipping tourist places processing.")
            return

        print(f"[Trip {trip_id}] Processing tourist places for {destination}")

        # Determine primary activity type
        activity_type = activities[0] if activities else "general"
        
        # Call the AI function to get enriched tourist places
        try:
            result = get_tourist_places_for_destination(
                destination=destination,
                activity=activity_type,
                limit=15
            )
            print(f"[Trip {trip_id}] AI processing completed")
        except Exception as e:
            print(f"[Trip {trip_id}] AI processing failed: {str(e)}")
            return

        # Check for errors in result
        if "error" in result:
            print(f"[Trip {trip_id}] Error in AI result: {result['error']}")
            return

        # Extract tourist places from result
        tourist_places_data = result.get("TouristPlaces")
        
        if not tourist_places_data:
            print(f"[Trip {trip_id}] No tourist places found in AI result")
            return

        print(f"[Trip {trip_id}] Found {len(tourist_places_data)} tourist places")

        # Delete existing tourist places for this trip (if re-processing)
        deleted_count = db.query(TouristPlace).filter(TouristPlace.trip_id == trip_id).delete()
        if deleted_count > 0:
            print(f"[Trip {trip_id}] Deleted {deleted_count} existing tourist places")
        db.commit()

        # Save tourist places to database
        places_saved = 0
        for place_data in tourist_places_data:
            try:
                geo_coords = place_data.get("GeoCoordinates", {})
                
                tourist_place = TouristPlace(
                    trip_id=trip_id,
                    name=place_data.get("Name"),
                    description=place_data.get("Description"),
                    latitude=geo_coords.get("lat") if geo_coords else None,
                    longitude=geo_coords.get("lng") if geo_coords else None,
                    image_url=place_data.get("ImageURL")
                )
                
                db.add(tourist_place)
                places_saved += 1
                
            except Exception as e:
                print(f"[Trip {trip_id}] Error saving place '{place_data.get('Name', 'Unknown')}': {str(e)}")
                continue

        db.commit()
        print(f"[Trip {trip_id}] Successfully saved {places_saved}/{len(tourist_places_data)} tourist places to database")

    except Exception as e:
        db.rollback()
        print(f"[Trip {trip_id}] Error processing tourist places: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()




@celery_app.task
def process_trip_itinerary(trip_id: int):
    """
    Celery task to generate and store a day-wise trip itinerary using AI.

    Args:
        trip_id (int): Trip ID to generate itinerary for.
    """
    db = SessionLocal()
    try:
        # 1️⃣ Verify Trip Exists
        trip: Trip = db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            print(f"[Trip {trip_id}] Trip not found. Skipping itinerary generation.")
            return

        itinerary_start_date = trip.start_date
        itinerary_end_date = trip.end_date
        destination = trip.destination
        activities: List[str] = trip.activities or []
        travelling_with = trip.travelling_with.value

        print(f"[Trip {trip_id}] Generating itinerary from {itinerary_start_date} to {itinerary_end_date}")

        # 2️⃣ Load Tourist Places
        tourist_places: List[TouristPlace] = (
            db.query(TouristPlace).filter(TouristPlace.trip_id == trip_id).all()
        )
        if not tourist_places:
            print(f"[Trip {trip_id}] No tourist places found. Cannot generate itinerary.")
            return

        print(f"[Trip {trip_id}] Loaded {len(tourist_places)} tourist places")

        tourist_places_data: List[Dict] = []
        for place in tourist_places:
            tourist_places_data.append({
                "Name": place.name,
                "Description": place.description,
                "GeoCoordinates": {"lat": place.latitude, "lng": place.longitude},
                "ImageURL": place.image_url
            })

        # 3️⃣ Call AI Agent
        try:
            ai_result = generate_trip_itinerary(
                trip_id=trip_id,
                start_date=itinerary_start_date.strftime("%Y-%m-%d"),
                end_date=itinerary_end_date.strftime("%Y-%m-%d"),
                destination=destination,
                activities=activities,
                travelling_with=travelling_with,
                tourist_places=tourist_places_data
            )
            print(f"[Trip {trip_id}] AI itinerary generation completed")
        except Exception as e:
            print(f"[Trip {trip_id}] AI itinerary generation failed: {str(e)}")
            return

        # 4️⃣ Validate AI Result
        if "error" in ai_result:
            print(f"[Trip {trip_id}] Error in AI result: {ai_result['error']}")
            return

        itinerary_days = ai_result.get("itinerary") or []
        if not itinerary_days:
            print(f"[Trip {trip_id}] No itinerary days found in AI output")
            return

        print(f"[Trip {trip_id}] Received {len(itinerary_days)} days of itinerary")

        # 5️⃣ Delete existing itinerary for this trip
        deleted_count = db.query(Itinerary).filter(Itinerary.trip_id == trip_id).delete()
        if deleted_count > 0:
            print(f"[Trip {trip_id}] Deleted {deleted_count} existing itinerary entries")
        db.commit()

        # 6️⃣ Save itinerary to DB
        saved_days = 0
        for day_data in itinerary_days:
            try:
                itinerary_day = Itinerary(
                    trip_id=trip_id,
                    day=day_data.get("day"),
                    date=day_data.get("date"),
                    travel_tips=day_data.get("travel_tips", []),
                    food=day_data.get("food", []),
                    culture=day_data.get("culture", [])
                )
                db.add(itinerary_day)
                db.commit()
                db.refresh(itinerary_day)

                # Save itinerary places
                for place in day_data.get("places", []):
                    itinerary_place = ItineraryPlace(
                        name=place.get("name"),
                        description=place.get("description"),
                        latitude=str(place.get("latitude")) if place.get("latitude") else None,
                        longitude=str(place.get("longitude")) if place.get("longitude") else None,
                        best_time_to_visit=place.get("best_time_to_visit"),
                        itinerary_id=itinerary_day.id
                    )
                    db.add(itinerary_place)

                db.commit()
                saved_days += 1
            except Exception as e:
                db.rollback()
                print(f"[Trip {trip_id}] Error saving itinerary day {day_data.get('day')}: {str(e)}")
            
                continue

        print(f"[Trip {trip_id}] Successfully saved {saved_days}/{len(itinerary_days)} itinerary days to database")

    except Exception as e:
        db.rollback()
        print(f"[Trip {trip_id}] Error generating itinerary: {str(e)}")
    
    finally:
        db.close()