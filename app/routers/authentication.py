from authlib.integrations.base_client import OAuthError
from authlib.oauth2.rfc6749 import OAuth2Token
from fastapi import APIRouter, Depends, HTTPException
from datetime import timedelta
from typing import Annotated
from starlette import status
from fastapi.security import OAuth2PasswordRequestForm
from app.database.models import User
from app.database.schemas import CreateUserRequest, GoogleUser, Token, RefreshTokenRequest
from app.utils.auth_helpers import create_access_token, authenticate_user, bcrypt_context, create_refresh_token, \
    create_user_from_google_info, get_user_by_google_sub, token_expired, decode_token, user_dependency
from app.database.database import db_dependency
from app.utils.auth_helpers import oauth
from fastapi import Request
from fastapi.responses import RedirectResponse
import os
from sqlalchemy.exc import IntegrityError


router = APIRouter(
    prefix='/auth',
    tags=['Authentication']
)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")    

FRONTEND_URL = os.getenv("FRONTEND_URL")    


@router.get("/google")
async def login_google(request: Request):
    return await oauth.google.authorize_redirect(request, GOOGLE_REDIRECT_URI)


@router.get("/callback/google")
async def auth_google(request: Request, db: db_dependency):
    try:
        # Get OAuth2 token from Google
        print("#"*10)
        
        user_response: OAuth2Token = await oauth.google.authorize_access_token(request)
        print(user_response)
    except OAuthError:
        return {
            "status": False,
            "data": None,
            "message": "Could not validate credentials",
            "status_code": status.HTTP_401_UNAUTHORIZED
        }

    user_info = user_response.get("userinfo")
    if not user_info:
        return {
            "status": False,
            "data": None,
            "message": "No user information received from Google",
            "status_code": status.HTTP_400_BAD_REQUEST
        }

    google_user = GoogleUser(**user_info)

    # Check if user already exists
    existing_user = get_user_by_google_sub(google_user.sub, db)

    if existing_user:
        user = existing_user
        msg = "Existing user logged in successfully"
    else:
        user = create_user_from_google_info(google_user, db)
        msg = "New user created successfully"

    # Generate tokens
    access_token = create_access_token(user.username, user.id, timedelta(days=7))
    refresh_token = create_refresh_token(user.username, user.id, timedelta(days=14))

    # Return JSON response
    return {
        "status": True,
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "name": user.name,
                "picture": user.picture
            }
        },
        "message": msg,
        "status_code": status.HTTP_200_OK
    }



@router.post("/create-user")
async def create_user(db: db_dependency, create_user_request: CreateUserRequest):
    try:
        # Check if username already exists
        existing_user = db.query(User).filter(User.username == create_user_request.username).first()
        if existing_user:
            return {
                "status": False,
                "data": None,
                "message": "Username already taken. Please choose a different username.",
                "status_code": status.HTTP_400_BAD_REQUEST
            }

        # Create new user if username is available
        create_user_model = User(
            username=create_user_request.username,
            hashed_password=bcrypt_context.hash(create_user_request.password)
        )
        db.add(create_user_model)
        db.commit()

        return {
            "status": True,
            "data": "User Registration Done",
            "message": "User created successfully",
            "status_code": status.HTTP_201_CREATED
        }

    except IntegrityError:
        db.rollback()
        return {
            "status": False,
            "data": None,
            "message": "Database integrity error. Possibly duplicate data.",
            "status_code": status.HTTP_400_BAD_REQUEST
        }

    except Exception as e:
        db.rollback()
        return {
            "status": False,
            "data": None,
            "message": f"Unexpected error: {str(e)}",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
        }

# ----------------------------
# Get User
# ----------------------------
@router.get("/get-user")
async def get_user(db: db_dependency, user: user_dependency):
    try:
        return {
            "status": True,
            "data": user,
            "message": "User fetched successfully",
            "status_code": status.HTTP_200_OK
        }
    except Exception as e:
        return {
            "status": False,
            "data": None,
            "message": f"Error fetching user: {str(e)}",
            "status_code": status.HTTP_400_BAD_REQUEST
        }


# ----------------------------
# Login with Username & Password
# ----------------------------
@router.post("/token")
async def login_for_access_token(db: db_dependency, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    try:
        user = authenticate_user(form_data.username, form_data.password, db)
        if not user:
            return {
                "status": False,
                "data": None,
                "message": "Could not validate user.",
                "status_code": status.HTTP_401_UNAUTHORIZED
            }

        access_token = create_access_token(user.username, user.id, timedelta(days=7))
        refresh_token = create_refresh_token(user.username, user.id, timedelta(days=14))

        return {
            "status": True,
            "data": {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"},
            "message": "Login successful",
            "status_code": status.HTTP_200_OK
        }
    except Exception as e:
        return {
            "status": False,
            "data": None,
            "message": f"Error during login: {str(e)}",
            "status_code": status.HTTP_400_BAD_REQUEST
        }


# ----------------------------
# Refresh Token
# ----------------------------
@router.post("/refresh")
async def refresh_access_token(db: db_dependency, refresh_token_request: RefreshTokenRequest):
    try:
        token = refresh_token_request.refresh_token
        if token_expired(token):
            return {
                "status": False,
                "data": None,
                "message": "Refresh token is expired.",
                "status_code": status.HTTP_401_UNAUTHORIZED
            }

        user = decode_token(token)
        access_token = create_access_token(user["sub"], user["id"], timedelta(days=7))
        refresh_token = create_refresh_token(user["sub"], user["id"], timedelta(days=14))

        return {
            "status": True,
            "data": {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"},
            "message": "Token refreshed successfully",
            "status_code": status.HTTP_200_OK
        }
    except Exception as e:
        return {
            "status": False,
            "data": None,
            "message": f"Error refreshing token: {str(e)}",
            "status_code": status.HTTP_400_BAD_REQUEST
        }