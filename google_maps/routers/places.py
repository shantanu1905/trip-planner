from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional
from schemas import PlacesResponse
from utils.maps_scraper import extract_tourist_places, load_cached_places, save_places_data, build_cache_filename, extract_lat_lng_from_url, extract_image_and_description, get_driver

router = APIRouter()

@router.get("", response_model=PlacesResponse)
async def get_places(
    destination: str = Query(..., min_length=1, description="City or destination name"),
    refresh: Optional[bool] = Query(False, description="Force re-scrape and overwrite cache")
):
    """
    Get tourist places for a destination.
    Save final JSON in the required format.
    """
    dest = destination.strip()
    cache_file = build_cache_filename(dest)

    # 1. Return cached data if available
    if not refresh:
        cached = load_cached_places(cache_file)
        if cached is not None:
            return JSONResponse(content=cached)

    # 2. Scrape live data
    try:
        data = extract_tourist_places(dest)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Scrape failed: {e}")

    if not data:
        raise HTTPException(status_code=404, detail="No places found")

    driver = get_driver()  # Create Selenium driver once

    # 3. Process all places
    tourist_places = []
    for idx, place in enumerate(data):
        lat, lng = extract_lat_lng_from_url(place.get("url"))

        # Extract image & description for first 15 URLs
        if idx < 15 :
            image_url, description = extract_image_and_description(driver, place.get("url"))
        else:
            image_url, description = None, None

        tourist_places.append({
            "Name": place["name"],
            "Description": description,
            "GeoCoordinates": {"lat": lat, "lng": lng},
            "ImageURL": image_url,
            "Google_web_url": place["url"]
        })

    driver.quit()

    # 4. Create final JSON format
    final_output = {
        "output": {
            "CorrectedDestination": dest,
            "TouristPlaces": tourist_places
        }
    }

    # 5. Save JSON file in new format
    try:
        save_places_data([final_output], cache_file)
    except Exception as e:
        return JSONResponse(status_code=200, content={
            "output": {
                "CorrectedDestination": dest,
                "TouristPlaces": tourist_places
            },
            "note": f"Returned live data; failed to save cache: {e}"
        })

    return JSONResponse(content=final_output)
