import stripe
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse , HTMLResponse, RedirectResponse, JSONResponse
from app.database.models import HotelBookingInfo, BusBookingInfo, TrainBookingInfo , Payment , Trip
from app.database.schemas import StripeCheckoutRequest
from decouple import config
from app.database.database import db_dependency
from app.utils.auth_helpers import user_dependency
import os
from fastapi import Request

stripe.api_key = config("STRIPE_SECRET_KEY")
# --- Configuration for Redirection ---
STRIPE_FINAL_REDIRECT_URL=os.getenv("STRIPE_FINAL_REDIRECT_URL")
BASE_SUCCESS_URL=os.getenv("BASE_SUCCESS_URL")
DELAY_SECONDS = 5

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("/create-session")
async def create_checkout_session(request: StripeCheckoutRequest):
    """
    💳 Create a Stripe Checkout session for booking (Hotel/Bus/Train)
    """
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "inr",
                    "product_data": {
                        "name": f"{request.booking_type} Booking - Trip {request.trip_id}"
                    },
                    "unit_amount": int(request.amount * 100),  # Stripe requires amount in paise
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=f"{BASE_SUCCESS_URL}/payments/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url="http://localhost:8000/payments/cancel",
            metadata={
                "trip_id": request.trip_id,
                "booking_id": request.booking_id,
                "booking_type": request.booking_type,
            }
        )

        return {
            "status": True,
            "checkout_url": session.url,
            "message": "Stripe checkout session created successfully."
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": False,
                "message": f"Error creating checkout session: {str(e)}"
            }
        )









@router.get("/success")
async def payment_success(session_id: str = Query(..., alias="session_id"), db: db_dependency = None):
    """
    ✅ Handle Stripe success callback — verify and finalize the payment.
    Processes the database update and then redirects the user to the bookings page.
    """
    
    # --- 1. Attempt Database and Stripe Processing ---
    try:
        # Retrieve checkout session from Stripe
        session = stripe.checkout.Session.retrieve(session_id)

        # Ensure payment is successful
        if session.payment_status != "paid":
            # If payment is not paid, redirect to a generic failure or pending page
            return RedirectResponse(url="/payments/pending-or-fail", status_code=303)

        # Extract metadata from session
        trip_id = session.metadata.get("trip_id")
        booking_id = session.metadata.get("booking_id")
        booking_type = session.metadata.get("booking_type")

        # ✅ Find or create payment record
        payment = (
            db.query(Payment)
            .filter(Payment.trip_id == trip_id, Payment.booking_id == booking_id)
            .first()
        )

        if not payment:
            # Create new record if it doesn’t exist (edge case)
            payment = Payment(
                trip_id=trip_id,
                booking_type=booking_type,
                booking_id=booking_id,
                amount=session.amount_total / 100 if session.amount_total else 0,
                currency=session.currency,
                stripe_payment_intent_id=session.payment_intent,
                # Use getattr for safer attribute access on dynamic objects
                stripe_client_secret=getattr(session, "client_secret", None),
                status="SUCCESS"
            )
            db.add(payment)
        else:
            # Update existing payment record
            payment.status = "SUCCESS"
            payment.stripe_payment_intent_id = session.payment_intent
            payment.stripe_client_secret = getattr(session, "client_secret", None)

        # Commit payment status update
        db.commit()

        # ✅ Update Booking Record
        if booking_type == "Hotel":
            booking = db.query(HotelBookingInfo).filter(HotelBookingInfo.id == booking_id).first()
        elif booking_type == "Bus":
            booking = db.query(BusBookingInfo).filter(BusBookingInfo.id == booking_id).first()
        elif booking_type == "Train":
            booking = db.query(TrainBookingInfo).filter(TrainBookingInfo.id == booking_id).first()
        else:
            booking = None

        if booking:
            booking.is_booked = True
            db.commit()

        # --- 2. SUCCESS: Return HTML with Delayed Redirect ---
        
        html_content = f"""
        <html>
            <head>
                <title>Payment Successful</title>
                <meta http-equiv="refresh" content="{DELAY_SECONDS};url={STRIPE_FINAL_REDIRECT_URL}">
                <style>
                    body {{ font-family: sans-serif; text-align: center; padding: 50px; background-color: #e6ffed; }}
                    .container {{ background-color: white; padding: 40px; border-radius: 10px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1); max-width: 450px; margin: 0 auto; border: 2px solid #28a745; }}
                    h1 {{ color: #28a745; }}
                    .loader {{ border: 4px solid #f3f3f3; border-top: 4px solid #28a745; border-radius: 50%; width: 24px; height: 24px; animation: spin 2s linear infinite; margin: 20px auto; }}
                    @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>✅ Payment Successful!</h1>
                    <p>Your **{booking_type}** booking is confirmed.</p>
                    <div class="loader"></div>
                    <p>Redirecting to your bookings page in {DELAY_SECONDS} seconds...</p>
                    <p style="font-size: 0.9em;">If the redirect doesn't happen, click <a href="{STRIPE_FINAL_REDIRECT_URL}">here</a>.</p>
                </div>
            </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)

    # --- 3. ERROR Handling ---
    except Exception as e:
        db.rollback()
        
        # If processing fails, we still show a page and redirect the user
        error_message = f"Booking processing error: {type(e).__name__}"
        
        html_error_content = f"""
        <html>
            <head>
                <title>Payment Error</title>
                <meta http-equiv="refresh" content="{DELAY_SECONDS};url={STRIPE_FINAL_REDIRECT_URL}">
                <style>
                    body {{ font-family: sans-serif; text-align: center; padding: 50px; background-color: #fff0f0; }}
                    .container {{ background-color: white; padding: 40px; border-radius: 10px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1); max-width: 450px; margin: 0 auto; border: 2px solid #dc3545; }}
                    h1 {{ color: #dc3545; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>❌ Verification Error!</h1>
                    <p>Payment was made, but there was an error updating your booking.</p>
                    <p>Details: {error_message}</p>
                    <p>Please check your booking status on the next page.</p>
                    <p>Redirecting in {DELAY_SECONDS} seconds...</p>
                </div>
            </body>
        </html>
        """
        return HTMLResponse(content=html_error_content, status_code=500)











# @router.get("/success")
# async def payment_success(session_id: str, db: db_dependency):
#     """
#     ✅ Handle Stripe success callback — verify and finalize the payment.
#     """
#     try:
#         # Retrieve checkout session from Stripe
#         session = stripe.checkout.Session.retrieve(session_id)

#         # Ensure payment is successful
#         if session.payment_status != "paid":
#             return JSONResponse(
#                 status_code=400,
#                 content={
#                     "status": False,
#                     "message": "Payment not completed yet.",
#                     "status_code": 400
#                 }
#             )

#         # Extract metadata from session
#         trip_id = session.metadata.get("trip_id")
#         booking_id = session.metadata.get("booking_id")
#         booking_type = session.metadata.get("booking_type")

#         # ✅ Find or create payment record
#         payment = (
#             db.query(Payment)
#             .filter(Payment.trip_id == trip_id, Payment.booking_id == booking_id)
#             .first()
#         )

#         if not payment:
#             # Create new record if it doesn’t exist (edge case)
#             payment = Payment(
#                 trip_id=trip_id,
#                 booking_type=booking_type,
#                 booking_id=booking_id,
#                 amount=session.amount_total / 100 if session.amount_total else 0,
#                 currency=session.currency,
#                 stripe_payment_intent_id=session.payment_intent,
#                 stripe_client_secret=session.client_secret if hasattr(session, "client_secret") else None,
#                 status="SUCCESS"
#             )
#             db.add(payment)
#         else:
#             # Update existing payment record
#             payment.status = "SUCCESS"
#             payment.stripe_payment_intent_id = session.payment_intent
#             payment.stripe_client_secret = (
#                 session.client_secret if hasattr(session, "client_secret") else None
#             )

#         db.commit()
#         db.refresh(payment)

#         # ✅ Update Booking Record
#         if booking_type == "Hotel":
#             booking = db.query(HotelBookingInfo).filter(HotelBookingInfo.id == booking_id).first()
#         elif booking_type == "Bus":
#             booking = db.query(BusBookingInfo).filter(BusBookingInfo.id == booking_id).first()
#         elif booking_type == "Train":
#             booking = db.query(TrainBookingInfo).filter(TrainBookingInfo.id == booking_id).first()
#         else:
#             booking = None

#         if booking:
#             booking.is_booked = True
#             db.commit()

#         return JSONResponse(
#             status_code=200,
#             content={
#                 "status": True,
#                 "message": f"Payment successful for {booking_type} booking.",
#                 "trip_id": trip_id,
#                 "booking_id": booking_id,
#                 "payment_id": payment.id,
#                 "status_code": 200
#             }
#         )

#     except Exception as e:
#         db.rollback()
#         return JSONResponse(
#             status_code=500,
#             content={
#                 "status": False,
#                 "message": f"Error verifying payment: {str(e)}",
#                 "status_code": 500
#             }
#         )
    



@router.get("/all")
async def get_all_payments(
    db: db_dependency,
    user: user_dependency
):
    """
    💳 Fetch all payment transactions for the logged-in user.
    Includes booking type, amount, status, and booking reference.
    """
    try:
        # ✅ Ensure user is authenticated
        if not user:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "status": False,
                    "data": None,
                    "message": "User not authenticated.",
                    "status_code": status.HTTP_401_UNAUTHORIZED,
                },
            )

        # ✅ Fetch all trips owned by this user
        user_trips = db.query(Trip.id).filter(Trip.user_id == user.id).all()
        trip_ids = [t.id for t in user_trips]

        if not trip_ids:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "status": False,
                    "data": [],
                    "message": "No trips found for this user.",
                    "status_code": status.HTTP_404_NOT_FOUND,
                },
            )

        # ✅ Get all payments related to user's trips
        payments = (
            db.query(Payment)
            .filter(Payment.trip_id.in_(trip_ids))
            .order_by(Payment.created_at.desc())
            .all()
        )

        if not payments:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": True,
                    "data": [],
                    "count": 0,
                    "message": "No payments found for this user.",
                    "status_code": status.HTTP_200_OK,
                },
            )

        # ✅ Format payment data (convert datetime to ISO string)
        response_data = []
        for p in payments:
            response_data.append({
                "payment_id": p.id,
                "trip_id": p.trip_id,
                "booking_id": p.booking_id,
                "booking_type": p.booking_type,
                "amount": p.amount,
                "currency": p.currency,
                "status": p.status,
                "stripe_payment_intent_id": p.stripe_payment_intent_id,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            })

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": True,
                "count": len(response_data),
                "data": response_data,
                "message": "All payments retrieved successfully.",
                "status_code": status.HTTP_200_OK,
            },
        )

    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": False,
                "data": None,
                "message": f"Error fetching payments: {str(e)}",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
        )



# | Step | Action                     | Description                                   |
# | ---- | -------------------------- | ----------------------------------------------|
# | 1️⃣  | User clicks “Pay”          | Calls `/payments/create-session`               |
# | 2️⃣  | Stripe Checkout page opens | User pays                                      |
# | 3️⃣  | Stripe Webhook fires       | `/payments/webhook` updates `is_booked = True` |
# | 4️⃣  | You show confirmation      | Success page `/payments/success`               |




# | Card Number           | Brand | Result           | Expiry                       | CVC          |
# | --------------------- | ----- | ---------------- | ---------------------------- | ------------ |
# | `4242 4242 4242 4242` | Visa  | Payment succeeds | Any future date (e.g. 12/30) | Any 3 digits |



#https://dashboard.stripe.com/ac\Bx1r/test/payments


















from fastapi import APIRouter, HTTPException, status
from app.database.models import Trip , Settings, TouristPlace , Itinerary , TravelOptions
from app.database.schemas import CreateTripRequest, UpdateTripRequest
from app.utils.auth_helpers import user_dependency
from app.database.database import db_dependency
from app.task.trip_tasks import process_tourist_places , process_trip_itinerary , fetch_and_save_destination_data
from app.aiworkflow.get_current_weather_conditions import fetch_travel_update
from app.utils.redis_utils import translate_with_cache
from app.database.redis_client import r
import json
from app.aiworkflow.get_trip_cost_breakdown import get_cost_breakdown





@router.get("share/{trip_id}")
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

        #fetching Travelling options 
       
        existing_travel = (
            db.query(TravelOptions)
            .filter(TravelOptions.trip_id == trip.id)
            .first()
        )

        if not existing_travel:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "status": False,
                    "data": None,
                    "message": "No travel options found for this trip. Please create travelling options first.",
                    "status_code": status.HTTP_404_NOT_FOUND,
                },
            )

        # Fetch Cost Breakdown (AI-powered) - Placeholder
        # Cache miss or data changed → run AI analysis
        # fresh_data = get_cost_breakdown(user_id=user.id, trip_id=trip_id)
        # print(fresh_data)

        fresh_data = {'total_budget': 10000, 'expenses': [{'expense_type': 'Travel', 'expense_name': 'Train: Nagpur → Delhi (3A)', 'details': 'Sleeper overnight journey, includes base fare and service charges.', 'estimated_cost': 2965.72, 'cost_per_person': 1482.86}, {'expense_type': 'Travel', 'expense_name': 'Train: Delhi → Dehradun (3A)', 'details': 'Train journey, includes base fare and service charges.', 'estimated_cost': 1220.0, 'cost_per_person': 610.0}, {'expense_type': 'Hotel', 'expense_name': 'Hotel Stay (4 Nights)', 'details': 'Includes room charges and applicable taxes for the stay duration.', 'estimated_cost': 7249.6, 'cost_per_person': 3624.8}, {'expense_type': 'Trip Itinerary', 'expense_name': 'Day 1 Itinerary - Food', 'details': 'Chotiwala Restaurant and Local street food near Triveni Ghat.', 'estimated_cost': 1200.0, 'cost_per_person': 600.0}, {'expense_type': 'Trip Itinerary', 'expense_name': 'Day 1 Itinerary - Local Transport', 'details': 'Auto fare and shared cab to tourist spots around the city.', 'estimated_cost': 400.0, 'cost_per_person': 200.0}, {'expense_type': 'Trip Itinerary', 'expense_name': 'Day 1 Itinerary - Entry Fees', 'details': 'Entry tickets for Triveni Ghat and local temple visits.', 'estimated_cost': 600.0, 'cost_per_person': 300.0}, {'expense_type': 'Trip Itinerary', 'expense_name': 'Day 2 Itinerary - Food', 'details': 'Little Buddha Cafe and German Bakery.', 'estimated_cost': 1400.0, 'cost_per_person': 700.0}, {'expense_type': 'Trip Itinerary', 'expense_name': 'Day 2 Itinerary - Local Transport', 'details': 'Auto fare and shared cab to tourist spots around the city.', 'estimated_cost': 400.0, 'cost_per_person': 200.0}, {'expense_type': 'Trip Itinerary', 'expense_name': 'Day 2 Itinerary - Entry Fees', 'details': 'Entry fees for Parmarth Niketan Ashram.', 'estimated_cost': 400.0, 'cost_per_person': 200.0}, {'expense_type': 'Trip Itinerary', 'expense_name': 'Day 3 Itinerary - Food', 'details': 'Local dhabas near the waterfalls and Cafes near Tapovan.', 'estimated_cost': 1200.0, 'cost_per_person': 600.0}, {'expense_type': 'Trip Itinerary', 'expense_name': 'Day 3 Itinerary - Local Transport', 'details': 'Auto fare and shared cab to tourist spots around the city.', 'estimated_cost': 400.0, 'cost_per_person': 200.0}, {'expense_type': 'Trip Itinerary', 'expense_name': 'Day 3 Itinerary - Entry Fees', 'details': 'Entry fees for waterfalls.', 'estimated_cost': 400.0, 'cost_per_person': 200.0}, {'expense_type': 'Trip Itinerary', 'expense_name': 'Day 4 Itinerary - Food', 'details': 'Pack a picnic lunch and Small eateries near the main road leading to Nilkanth Mahadev Temple.', 'estimated_cost': 1000.0, 'cost_per_person': 500.0}, {'expense_type': 'Trip Itinerary', 'expense_name': 'Day 4 Itinerary - Local Transport', 'details': 'Auto fare and shared cab to tourist spots around the city.', 'estimated_cost': 400.0, 'cost_per_person': 200.0}, {'expense_type': 'Trip Itinerary', 'expense_name': 'Day 4 Itinerary - Entry Fees', 'details': 'Entry fees for waterfalls.', 'estimated_cost': 400.0, 'cost_per_person': 200.0}, {'expense_type': 'Trip Itinerary', 'expense_name': 'Day 5 Itinerary - Food', 'details': "Ramana's Garden Organic Cafe.", 'estimated_cost': 800.0, 'cost_per_person': 400.0}, {'expense_type': 'Trip Itinerary', 'expense_name': 'Day 5 Itinerary - Local Transport', 'details': 'Auto fare and shared cab to tourist spots around the city.', 'estimated_cost': 400.0, 'cost_per_person': 200.0}, {'expense_type': 'Trip Itinerary', 'expense_name': 'Day 5 Itinerary - Entry Fees', 'details': 'Souvenirs and other shopping.', 'estimated_cost': 600.0, 'cost_per_person': 300.0}], 'total_expenses': 20835.32, 'budget_remaining': -10835.32}
       
        # destination = trip.destination
        # params = json.dumps({"destination": destination})
        # travel_update = fetch_travel_update(params)
        # print(travel_update)

        travel_update = {'Destination': 'Rishikesh', 'Date': 'October 29, 2025', 'Weather': {'Current Temperature': '28°C', 'Min Temperature': '18°C', 'Next 5 Days Forecast': 'Mostly sunny with temperatures ranging from 18°C to 30°C. No rainfall expected. (Source: Local Weather Channel)', 'IMD Alert': 'No alerts issued by IMD for Rishikesh in the past 3 days.'}, 'Roadblocks and Road Status': [{'Source': 'Rishikesh', 'Destination': 'Badrinath', 'Road Status': 'Open', 'Advisory': 'Pilgrims are advised to check weather conditions before travelling. (Source: BRO)'}, {'Source': 'Rishikesh', 'Destination': 'Kedarnath', 'Road Status': 'Open', 'Advisory': 'Road is open but subject to closure due to landslides during heavy rainfall. Check with local authorities before travel. (Source: Local News)'}, {'Source': 'Rishikesh', 'Destination': 'Dehradun', 'Road Status': 'Open', 'Advisory': 'Normal traffic flow. (Source: Local Traffic Authority)'}], 'Travel Advisory': ['Carry sufficient warm clothing as temperatures can drop significantly in the evenings.', 'Be aware of potential landslides, especially during or after rainfall.', 'Check road conditions with local authorities before starting your journey.', 'Carry necessary medications and a first-aid kit.', 'Respect local customs and traditions.']}

        # 4. Prepare trip data with new fields
        trip_data = {
            "trip_id": trip.id,
            "trip_name": trip.trip_name,
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
            "your_travel_options":  existing_travel.selected_travel_options,
            "itineraries_status": itineraries_status,
            "itineraries_status_message": itineraries_status_message,
            "itineraries": itineraries,
            "cost_breakdown": fresh_data,
            "travel_update": travel_update  
            
        }

        # 5. Translate if needed
        settings = db.query(Settings).filter(Settings.user_id == user.id).first()
        target_lang = settings.native_language if settings and settings.native_language else "English"

        if target_lang != "English":
             trip_data = await translate_with_cache(trip_data, target_lang)

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




from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import json

templates = Jinja2Templates(directory="templates")
@router.get("/sharetrip/{trip_id}", response_class=HTMLResponse)
async def share_trip(
    request: Request,
    trip_id: int,
    db: db_dependency,
    user: user_dependency
):
    try:
        # 1️⃣ Fetch trip
        trip = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user.id).first()
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found or not owned by user")

        # 2️⃣ Build itineraries
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

        # 3️⃣ Get travel options
        existing_travel = (
            db.query(TravelOptions)
            .filter(TravelOptions.trip_id == trip.id)
            .first()
        )
        if not existing_travel:
            raise HTTPException(status_code=404, detail="No travel options found for this trip")

        # 4️⃣ Get cost breakdown
        fresh_data = {
            'total_budget': 10000,
            'expenses': [
                {'expense_type': 'Travel', 'expense_name': 'Train: Nagpur → Delhi (3A)', 'estimated_cost': 2965.72, 'cost_per_person': 1482.86},
                {'expense_type': 'Hotel', 'expense_name': 'Hotel Stay (4 Nights)', 'estimated_cost': 7249.6, 'cost_per_person': 3624.8},
                {'expense_type': 'Food', 'expense_name': 'Local Cafes & Street Food', 'estimated_cost': 2200.0, 'cost_per_person': 1100.0},
            ],
            'total_expenses': 12415.32,
            'budget_remaining': -2415.32
        }

        # 5️⃣ Get travel & weather update
        travel_update = {
            'Destination': trip.destination_full_name,
            'Weather': {
                'Current Temperature': '28°C',
                'Next 5 Days Forecast': 'Mostly sunny, no rainfall expected.'
            },
            'Roadblocks': [
                {'Route': 'Rishikesh → Kedarnath', 'Status': 'Open', 'Advisory': 'Check before traveling during rain.'}
            ],
            'Travel Advisory': [
                'Carry warm clothing.',
                'Avoid night drives in hilly areas.'
            ]
        }

        # 6️⃣ Merge trip data
        trip_data = {
            "trip_id": trip.id,
            "trip_name": trip.trip_name,
            "destination_full_name": trip.destination_full_name,
            "destination_image_url": trip.destination_image_url or [],
            "base_location": trip.base_location,
            "start_date": trip.start_date.isoformat() if trip.start_date else None,
            "end_date": trip.end_date.isoformat() if trip.end_date else None,
            "budget": trip.budget,
            "num_people": trip.num_people,
            "activities": trip.activities or [],
            "your_travel_options": existing_travel.selected_travel_options,
            "itineraries": itineraries,
            "cost_breakdown": fresh_data,
            "travel_update": travel_update
        }

        # 7️⃣ (Optional) Translate
        settings = db.query(Settings).filter(Settings.user_id == user.id).first()
        target_lang = settings.native_language if settings and settings.native_language else "English"
        if target_lang != "English":
            trip_data = await translate_with_cache(trip_data, target_lang)

        # 8️⃣ Render dynamic HTML page
        return templates.TemplateResponse(
            "trip_share.html",
            {"request": request, "trip_data": json.dumps(trip_data)}
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching trip: {str(e)}")


# def share_trip(
#     trip_id: int,
#     user: user_dependency, 
#     db: db_dependency
# ):
#     """
#     Generate a sharable HTML summary for a trip.
#     Includes itinerary, selected travel options, cost breakdown, and weather info.
#     """

#     user_id = user.id

    
#     # 1️⃣ Validate and Fetch Trip
#     trip = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user_id).first()
#     if not trip:
#         raise HTTPException(status_code=404, detail="Trip not found or not owned by user")

#     # 2️⃣ Fetch related data
#     itinerary = db.query(Itinerary).filter(Itinerary.trip_id == trip_id).order_by(Itinerary.day.asc()).all()
#     travel_options = db.query(TravelOptions).filter(TravelOptions.trip_id == trip_id).first()

#     print(itinerary)

#     # # 3️⃣ Get Cost Breakdown (AI-powered)
#     # try:
#     #     cost_data = get_cost_breakdown(user_id=user_id, trip_id=trip_id)
#     #     if "error" in cost_data:
#     #         raise Exception(cost_data["error"])

#     #     expenses = cost_data.get("expenses", [])
#     #     total_budget = cost_data.get("total_budget", 0)
#     #     total_expenses = cost_data.get("total_expenses", 0)
#     #     budget_remaining = cost_data.get("budget_remaining", 0)
#     # except Exception as e:
#     #     expenses = []
#     #     total_budget = total_expenses = budget_remaining = 0
#     #     print(f"[⚠️] Cost breakdown failed: {e}")

#     # # 4️⃣ Basic Weather Info (can later replace with API)
#     # weather_info = {
#     #     "avg_temp": "28°C",
#     #     "condition": "Clear and sunny",
#     #     "humidity": "55%",
#     # }
#     return HTMLResponse(content=html, status_code=200)