# File: main.py
from fastapi import FastAPI
from routers.places import router as places_router


app = FastAPI(title="Places Scraper API", version="1.0.0")


app.include_router(places_router, prefix="/places", tags=["places"])


@app.get("/")
def root():
    return {"status": "ok", "message": "Places Scraper API is running"}