import stripe
from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse , HTMLResponse, RedirectResponse, JSONResponse
from app.database.models import HotelBookingInfo, BusBookingInfo, TrainBookingInfo , Payment , Trip
from app.database.schemas import StripeCheckoutRequest
from decouple import config
from app.database.database import db_dependency
from app.utils.auth_helpers import user_dependency

import os


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
















