from fastapi import APIRouter, HTTPException, status, Depends
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from datetime import timedelta
from app.utils.auth_helpers import (
    create_access_token,
    create_refresh_token,
    create_user_from_google_info,
    get_user_by_google_sub
)
from app.database.schemas import GoogleUser
from app.database.database import db_dependency
import os
import logging
from pydantic import BaseModel, Field

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix='/reactauth',
    tags=['Authentication_react']
)

# Environment variables
GOOGLE_CLIENT_SECRET_REACT = os.getenv("GOOGLE_CLIENT_SECRET_REACT")
GOOGLE_CLIENT_ID_REACT = os.getenv("GOOGLE_CLIENT_ID_REACT")
ACCESS_TOKEN_EXPIRE_DAYS = 7
REFRESH_TOKEN_EXPIRE_DAYS = 14

# Model for the incoming Google ID token from the React frontend
class GoogleToken(BaseModel):
    credential: str = Field(..., description="Google ID token from frontend")

# Model for the custom JWT your application will issue
class AppToken(BaseModel):
    access_token: str
    token_type: str

@router.post("/google")
async def authenticate_google_user(token: GoogleToken, db: db_dependency):
    """
    Verifies Google ID token, creates user if necessary, and returns access/refresh tokens.
    """
    # Enhanced logging and validation
    logger.info(f"Authentication attempt started")
    logger.info(f"Token received: {token.credential[:50]}..." if len(token.credential) > 50 else f"Token received: {token.credential}")
    
    if not GOOGLE_CLIENT_ID_REACT:
        logger.error("Google Client ID not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google Client ID not configured on server."
        )
    
    logger.info(f"Using Google Client ID: {GOOGLE_CLIENT_ID_REACT}")

    try:
        # 1. Verify token with Google - Enhanced error handling
        logger.info("Starting token verification with Google")
        
        idinfo = id_token.verify_oauth2_token(
            token.credential,
            google_requests.Request(),
            GOOGLE_CLIENT_ID_REACT
        )
        
        logger.info(f"Token verification successful. User info: {idinfo}")

        # 2. Validate required fields
        if not idinfo.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token: missing 'sub' field"
            )
        
        if not idinfo.get("email"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not available in Google token"
            )

        # 3. Extract Google user info
        google_user = GoogleUser(
        sub=idinfo["sub"],
        email=idinfo.get("email"),
        name=idinfo.get("name", "Unknown User"),
        picture=idinfo.get("picture", ""),
        email_verified=idinfo.get("email_verified", False)  # <-- This was missing!
    )
        
        logger.info(f"Google user extracted: {google_user.email}")

        # 4. Check if user exists in DB
        logger.info(f"Checking if user exists with sub: {google_user.sub}")
        user = get_user_by_google_sub(google_user.sub, db)
        
        if not user:
            logger.info("User not found, creating new user")
            user = create_user_from_google_info(google_user, db)
            msg = "New user created successfully"
        else:
            logger.info(f"Existing user found: {user.username}")
            msg = "Existing user logged in successfully"

        # 5. Generate tokens
        logger.info("Generating access and refresh tokens")
        access_token = create_access_token(
            user.username, user.id, timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
        )
        refresh_token = create_refresh_token(
            user.username, user.id, timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        )

        logger.info("Authentication successful")

        # 6. Return JSON response
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

    except ValueError as ve:
        logger.error(f"Token verification failed: {str(ve)}")
        # More specific error handling for different ValueError cases
        error_msg = str(ve).lower()
        if "expired" in error_msg:
            detail = "Google token has expired. Please sign in again."
        elif "invalid" in error_msg:
            detail = "Invalid Google token format or signature."
        elif "audience" in error_msg:
            detail = "Token was not issued for this application."
        else:
            detail = f"Token verification failed: {str(ve)}"
            
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail
        )
    except HTTPException:
        # Re-raise HTTPExceptions as they are
        raise
    except Exception as e:
        logger.error(f"Unexpected error during Google authentication: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )
