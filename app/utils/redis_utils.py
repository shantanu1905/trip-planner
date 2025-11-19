import hashlib
import json
from app.database.redis_client import r, REDIS_TTL
from app.aiworkflow.get_trip_cost_breakdown import get_cost_breakdown
from app.database.models import Trip, UserPreferences, HotelPreferences, Itinerary
from app.database.database import db_dependency
from app.database.redis_client import r
from app.utils.language_translation import call_gemini_translation_api  # or correct import
import enum
from dotenv import load_dotenv
from langchain_core.output_parsers.json import JsonOutputParser
from langchain.schema import OutputParserException
import httpx
import os 
# Load environment variables from .env

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_URL =  os.getenv("GEMINI_URL")

parser = JsonOutputParser()





def compute_trip_for_cost_breakdown_hash(db: db_dependency, trip_id: int ) -> str:
    # Fetch only required Trip fields
    trip = db.query(Trip.destination, Trip.start_date, Trip.end_date, Trip.user_id).filter(Trip.id == trip_id).first()

    if not trip:
        return ""  # or some default hash

    # Fetch only required UserPreferences fields
    prefs = db.query(
        UserPreferences.default_budget,
        UserPreferences.food_preference,
        UserPreferences.base_location,
        UserPreferences.travel_mode,
        UserPreferences.travelling_with
    ).filter(UserPreferences.user_id == trip.user_id).first()

    # Fetch only required HotelPreferences fields
    hotel = db.query(
        HotelPreferences.no_of_rooms,
        HotelPreferences.no_of_adult,
        HotelPreferences.no_of_child
    ).filter(HotelPreferences.trip_id == trip_id).first()

    # Fetch itinerary dates
    itinerary_dates = [i.date.isoformat() for i in db.query(Itinerary.date).filter(Itinerary.trip_id == trip_id).all()]

    # Helper to convert enums to their values
    def enum_to_value(val):
        return val.value if isinstance(val, enum.Enum) else val

    combined = {
        "trip": trip.destination,
        "dates": trip.start_date.isoformat() + trip.end_date.isoformat(),
        "preferences": {k: enum_to_value(v) for k, v in dict(prefs._mapping).items()} if prefs else {},
        "hotel": dict(hotel._mapping) if hotel else {},
        "itinerary": itinerary_dates
    }

    # Return SHA256 hash
    return hashlib.sha256(json.dumps(combined, sort_keys=True).encode()).hexdigest()



def get_cached_expense_analysis(db: db_dependency, user_id: int, trip_id: int, force_refresh: bool = False):
    cache_key = f"expense_analysis:{trip_id}:{user_id}"
    source_hash = compute_trip_for_cost_breakdown_hash(db, trip_id)

    cached_data = r.get(cache_key)
    if cached_data:
        cached_json = json.loads(cached_data)
        if cached_json.get("source_hash") == source_hash and not force_refresh:
            # Cache valid
            return {"cached": True, "data": cached_json["data"]}

    # Cache invalid or missing → generate fresh
    fresh_data = get_cost_breakdown(user_id, trip_id)
    r.set(cache_key, json.dumps({
        "source_hash": source_hash,
        "data": fresh_data
    }), ex=REDIS_TTL)

    return {"cached": False, "data": fresh_data}





# Redis Utils for Language Translation Caching




# async def translate_with_cache(json_data: dict, target_lang, source_lang="English"):
#     """
#     Translates the given JSON using Gemini API, with Redis-only caching.
#     Caches translations per (source_text + source_lang + target_lang) hash.
#     """

#     source_lang_str = source_lang.value if hasattr(source_lang, "value") else str(source_lang)
#     target_lang_str = target_lang.value if hasattr(target_lang, "value") else str(target_lang)

#     if source_lang_str == target_lang_str:
#         return json_data  # No translation needed

#     # Create deterministic hash for caching
#     text_hash = hashlib.md5(
#         f"{json.dumps(json_data, ensure_ascii=False)}_{source_lang_str}_{target_lang_str}".encode()
#     ).hexdigest()

#     redis_key = f"translation:{text_hash}"

#     # 1️⃣ Try Redis cache
#     cached_data = r.get(redis_key)
#     if cached_data:
#         print(f"✅ Redis translation cache hit: {target_lang_str}")
#         return json.loads(cached_data)

#     # 2️⃣ Call Gemini API if cache miss
#     print(f"🚀 Cache miss, calling Gemini API for {target_lang_str} translation...")
#     translated_dict = await call_gemini_translation_api(json_data, source_lang_str, target_lang_str)

#     # 3️⃣ Save translation in Redis (with TTL)
#     r.set(redis_key, json.dumps(translated_dict), ex=REDIS_TTL_TRANSLATION)

#     return translated_dict









# Cache each translation for 30 days
REDIS_TTL_TRANSLATION = 7 * 24 * 3600  # 7 days
async def translate_with_cache(json_data: dict, target_lang, source_lang="English", prompt_template: str = None):
    """
    Translate JSON values using Gemini API with Redis caching.
    Now includes built-in Gemini call and supports custom prompt.
    """

    # Normalize language values (support Enum / str)
    source_lang_str = source_lang.value if hasattr(source_lang, "value") else str(source_lang)
    target_lang_str = target_lang.value if hasattr(target_lang, "value") else str(target_lang)

    # No translation needed
    if source_lang_str.lower() == target_lang_str.lower():
        return json_data

    # Default prompt (if not provided)
    if not prompt_template:
        prompt_template = """
                            You are a translation engine.
                            Translate only the VALUES of this JSON object from {source_lang} to {target_lang}.
                            DO NOT translate keys.
                            Return valid JSON only with the same structure.

                            Input JSON:
                            {json_string}

                            Return JSON only. No explanations.
                            """

    # Create deterministic hash key for Redis
    sorted_json = json.dumps(json_data, ensure_ascii=False, sort_keys=True)
    text_hash = hashlib.md5(
        f"{sorted_json}_{source_lang_str}_{target_lang_str}".encode()
    ).hexdigest()

    redis_key = f"translation:{text_hash}"

    # 1️⃣ Check Redis cache
    cached_data = r.get(redis_key)
    if cached_data:
        print(f"✅ Redis cache hit → {target_lang_str}")
        return json.loads(cached_data)

    print(f"🚀 Cache miss → Calling Gemini for {target_lang_str} translation")

    # Build prompt
    prompt = prompt_template.format(
        source_lang=source_lang_str,
        target_lang=target_lang_str,
        json_string=sorted_json
    )

    # Gemini HTTP request
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": GEMINI_API_KEY
    }

    body = {
        "contents": [
            {"parts": [{"text": prompt}]}
        ]
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(GEMINI_URL, headers=headers, json=body)

        if response.status_code != 200:
            print("❌ Gemini API Error:", response.status_code, response.text)
            return json_data  # Safe fallback

        result = response.json()
        raw_text = result["candidates"][0]["content"]["parts"][0]["text"]

        # Try parsing structured JSON
        try:
            translated = parser.parse(raw_text)
        except OutputParserException:
            print("⚠️ Gemini returned invalid JSON → Using original data")
            translated = json_data

    # 3️⃣ Store in Redis
    r.set(redis_key, json.dumps(translated), ex=REDIS_TTL_TRANSLATION)

    return translated



#USEAGE EXAMPLE OF Gemini CALL INSIDE TRANSLATION UTILS:
# custom_prompt = """
# Translate JSON values from {source_lang} to {target_lang}.
# Keep tone friendly and simple.
# Do NOT translate keys.
# Return only JSON.

# Input:
# {json_string}
# """

# translated = await translate_with_cache(
#     json_data={"greeting": "Welcome to the travel planner"},
#     target_lang="Spanish",
#     prompt_template=custom_prompt
# )