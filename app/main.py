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



from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv
import logging
import os

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")

origins = ["*"]

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI()

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





auth_models.Base.metadata.create_all(bind=engine)



@app.get("/", status_code=status.HTTP_200_OK)
async def user(user: user_dependency, db: db_dependency):
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication failed.")

    return {"user": user}


@app.get("/test", status_code=status.HTTP_200_OK)
async def test(db: db_dependency):
    return "test"

