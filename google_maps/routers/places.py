from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional
import asyncio

from schemas import PlacesResponse
from utils.maps_scraper import (
    extract_tourist_places,
    load_cached_places,
    save_places_data,
    build_cache_filename,
    gather_place_details,
)

router = APIRouter()


@router.get("", response_model=PlacesResponse)
async def get_places(
    destination: str = Query(..., min_length=1, description="City or destination name"),
    refresh: Optional[bool] = Query(False, description="Force re-scrape and overwrite cache"),
):
    """
    Get tourist places for a destination.
    Uses async HTTP for metadata scraping and single Selenium run for listings.
    Expected runtime: ~20–30 s.
    """
    dest = destination.strip()
    cache_file = build_cache_filename(dest)

    # 1️⃣ Serve from cache
    if not refresh:
        cached = load_cached_places(cache_file)
        if cached is not None:
            return JSONResponse(content=cached)

    # 2️⃣ Fetch fresh listings (Selenium once)
    try:
        base_places = extract_tourist_places(dest, limit=15)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Failed to fetch from Google Maps: {e}")

    if not base_places:
        raise HTTPException(status_code=404, detail="No places found")

    # 3️⃣ Async fetch images + descriptions
    details = await gather_place_details(base_places)

    final_output = {"output": {"CorrectedDestination": dest, "TouristPlaces": details}}

    # 4️⃣ Save cache
    try:
        save_places_data([final_output], cache_file)
    except Exception as e:
        return JSONResponse(
            status_code=200,
            content={
                "output": final_output["output"],
                "note": f"Returned live data; failed to save cache: {e}",
            },
        )

    return JSONResponse(content=final_output)
