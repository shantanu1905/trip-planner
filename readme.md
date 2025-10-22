# AI Trip Planner

AI Trip Planner is a full-stack travel planning application that helps users create, manage, and optimize trips using AI-powered recommendations, Google Maps, and real-time travel data.

## Features

- User authentication (Google OAuth & password)
- Trip creation, update, and deletion
- Automated tourist place extraction via Google Maps
- Itinerary generation using AI
- Travel mode suggestions (train, bus, flight)
- User preferences and settings management
- Language translation for trip details
- RESTful API endpoints (FastAPI)
- Background task processing (Celery)
- Dockerized Google Maps microservice

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/shantanu1905/trip-planner.git
   cd ai-trip-planner
   ```

2. Install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Set up the environment variables:

   ```bash
   cp .env.example .env
   nano .env
   ```

4. Run the application:

   ```bash
   uvicorn app.main:app --reload
   ```

5. In a separate terminal, run the Celery worker:

   ```bash
   celery -A app.celery_worker.celery_app worker --loglevel=info --pool=solo
   ```

6. (Optional) Build and run the Google Maps scraper microservice:

   ```bash
   cd app/google_maps_scraper
   docker build -t google_maps_scraper .
   docker run -d google_maps_scraper
   ```

## Usage

1. Register a new account or log in with an existing account.
2. Create a new trip by providing a destination, dates, and preferences.
3. View the recommended tourist places, optimized itinerary, and suggested travel modes.
4. Update your trip details or delete the trip if no longer needed.
5. Manage your account settings and preferences.

ChatGPT said:

Sure! Here's a clear step-by-step explanation of the caching logic implemented in your get_trip_cost_breakdown endpoint:

Generate a cache key:

Combine the trip_id and a hash of the source data (trip, user preferences, itinerary, etc.) to create a unique Redis key.

This ensures the cache is tied specifically to the current state of the trip and user.

Check Redis for cached data:

Look up the key in Redis.

If found, compare the stored source_hash with the current hash of the data.

If they match → cached data is still valid → return cached result directly.

If they differ → data has changed → need fresh AI computation.

Run AI computation if no valid cache exists:

Call the AI agent (get_cost_breakdown) to generate the detailed trip expense breakdown.

This includes travel, hotel, and day-wise itinerary expenses.

Cache the fresh result in Redis:

Store the AI output along with the current source_hash in Redis.

Set a TTL (REDIS_TTL) so the cache automatically expires after a certain duration.

Return the result to the client:

Either retrieved from cache or freshly computed.

This ensures users get fast responses if data hasn’t changed, while still updating automatically when the trip or preferences change.

Key benefits of this logic:

Reduces unnecessary AI calls → saves compute and cost.

Automatically invalidates outdated data using source_hash.

TTL ensures even unused cache eventually expires → prevents stale data accumulation.

If you want, I can also make a small diagram explaining flow from request → cache → AI → cache update → response, which is very helpful for explaining to others.

Do you want me to make that diagram?
