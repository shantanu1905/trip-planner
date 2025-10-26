from starlette.middleware.sessions import SessionMiddleware
from fastapi import FastAPI, status, HTTPException
from app.database.database import engine, db_dependency
from app.utils.auth_helpers import user_dependency
from app.database import models as auth_models
from app.routers.authentication import router as authentication_router
from app.routers.settings import router as settings
from app.routers.recommendation import router as recommendation
from app.routers.trips import router as trips
from app.routers.authentication_react import router as react
from app.routers.user_preferences import router as user_preferences
from app.routers.bookings import router as travel_mode
from app.routers.search_tickets import router as search_tickets

from fastapi.middleware.cors import CORSMiddleware
from app.database import events
from dotenv import load_dotenv
import logging
import os
from fastapi.openapi.models import OAuthFlows as OAuthFlowsModel, SecurityScheme as SecuritySchemeModel
from fastapi.openapi.utils import get_openapi

# This is automatically generated if you use OAuth2PasswordBearer in Depends,
# but to add it globally in Swagger UI:

def custom_openapi(app):
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="My API",
        version="1.0.0",
        description="API with JWT authentication",
        routes=app.routes,
    )
    
    # Define OAuth2 Password flow (for Bearer JWT token)
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }
    
    # Apply to all endpoints globally
    for path in openapi_schema["paths"].values():
        for method in path.values():
            method["security"] = [{"BearerAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema



load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")

origins = ["*"]

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI()
# Replace the default OpenAPI function
app.openapi = lambda: custom_openapi(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True, 
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

app.include_router(authentication_router)
app.include_router(recommendation)
app.include_router(settings)
app.include_router(trips)
app.include_router(react)
app.include_router(user_preferences)
app.include_router(travel_mode)
app.include_router(search_tickets)


auth_models.Base.metadata.create_all(bind=engine)



@app.get("/", status_code=status.HTTP_200_OK)
async def user(user: user_dependency, db: db_dependency):
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication failed.")

    return {"user": user}


@app.get("/test", status_code=status.HTTP_200_OK)
async def test(db: db_dependency):
    return "test"

