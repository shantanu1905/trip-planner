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
- Dockerized Google Maps  microservice


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
