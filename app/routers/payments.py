import stripe
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from app.database.models import HotelBookingInfo, BusBookingInfo, TrainBookingInfo , Payment , Trip
from app.database.schemas import StripeCheckoutRequest
from decouple import config
from app.database.database import db_dependency
from app.utils.auth_helpers import user_dependency

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
        # Retrieve checkout session from Stripe
        session = stripe.checkout.Session.retrieve(session_id)

        # Ensure payment is successful
        if session.payment_status != "paid":
            return JSONResponse(
                status_code=400,
                content={
                    "status": False,
                    "message": "Payment not completed yet.",
                    "status_code": 400
                }
            )

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
                stripe_client_secret=session.client_secret if hasattr(session, "client_secret") else None,
                status="SUCCESS"
            )
            db.add(payment)
        else:
            # Update existing payment record
            payment.status = "SUCCESS"
            payment.stripe_payment_intent_id = session.payment_intent
            payment.stripe_client_secret = (
                session.client_secret if hasattr(session, "client_secret") else None
            )

        db.commit()
        db.refresh(payment)

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

        return JSONResponse(
            status_code=200,
            content={
                "status": True,
                "message": f"Payment successful for {booking_type} booking.",
                "trip_id": trip_id,
                "booking_id": booking_id,
                "payment_id": payment.id,
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