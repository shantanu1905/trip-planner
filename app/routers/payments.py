import stripe
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.database.models import HotelBookingInfo, BusBookingInfo, TrainBookingInfo , Payment
from app.database.schemas import StripeCheckoutRequest
from decouple import config
from app.database.database import db_dependency
from fastapi import Request

stripe.api_key = config("STRIPE_SECRET_KEY")
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
            success_url=f"http://localhost:8000/payments/success?session_id={{CHECKOUT_SESSION_ID}}",
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



# @router.post("/webhook")
# async def stripe_webhook(request: Request, db: db_dependency):
#     payload = await request.body()
#     sig_header = request.headers.get("stripe-signature")

#     endpoint_secret = config("STRIPE_WEBHOOK_SECRET")

#     try:
#         event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
#     except ValueError:
#         raise HTTPException(status_code=400, detail="Invalid payload")
#     except stripe.error.SignatureVerificationError:
#         raise HTTPException(status_code=400, detail="Invalid signature")

#     if event["type"] == "checkout.session.completed":
#         session = event["data"]["object"]
#         booking_id = session["metadata"]["booking_id"]
#         booking_type = session["metadata"]["booking_type"]

#         # ✅ Update booking in DB
#         if booking_type == "Hotel":
#             booking = db.query(HotelBookingInfo).filter_by(id=booking_id).first()
#         elif booking_type == "Bus":
#             booking = db.query(BusBookingInfo).filter_by(id=booking_id).first()
#         elif booking_type == "Train":
#             booking = db.query(TrainBookingInfo).filter_by(id=booking_id).first()
#         else:
#             booking = None

#         if booking:
#             booking.is_booked = True
#             db.commit()

#     return {"status": "success"}







@router.get("/success")
async def payment_success(session_id: str, db: db_dependency):
    """
    ✅ Handle Stripe success callback — verify and finalize the payment.
    """
    try:
        # Retrieve the checkout session from Stripe
        session = stripe.checkout.Session.retrieve(session_id)

        # Verify payment status
        if session.payment_status != "paid":
            return JSONResponse(
                status_code=400,
                content={
                    "status": False,
                    "message": "Payment not completed yet.",
                    "status_code": 400
                }
            )

        # Extract metadata
        trip_id = session.metadata.get("trip_id")
        booking_id = session.metadata.get("booking_id")
        booking_type = session.metadata.get("booking_type")

        # ✅ Update Payment Record in DB (optional if you saved it before)
        payment = (
            db.query(Payment)
            .filter(Payment.trip_id == trip_id, Payment.booking_id == booking_id)
            .first()
        )

        if payment:
            payment.status = "SUCCESS"
            payment.stripe_payment_id = session.payment_intent
            db.commit()

        # ✅ Update Booking Table
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

        return JSONResponse(
            status_code=200,
            content={
                "status": True,
                "message": f"Payment successful for {booking_type} booking.",
                "booking_type": booking_type,
                "trip_id": trip_id,
                "booking_id": booking_id,
                "status_code": 200
            }
        )

    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={
                "status": False,
                "message": f"Error verifying payment: {str(e)}",
                "status_code": 500
            }
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