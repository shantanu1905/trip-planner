# AI Trip Planner

**TripCraft.AI** transforms travel planning from a chaotic chore into a seamless experience. We combine the reasoning power of **Google Gemini** with real-time **EaseMyTrip** inventory to create personalized, actionable itineraries that take you from "dreaming" to "booking" in minutes.

## Features
<img width="1920" height="1080" alt="23" src="https://github.com/user-attachments/assets/36f4dc2c-c1fb-401d-9a8b-77a38c148fca" />
<img width="1920" height="1080" alt="24" src="https://github.com/user-attachments/assets/87a20d93-93b2-4bc0-807f-15ee232c32d3" />

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
## Resources 
https://drive.google.com/drive/folders/1QwpTSaADXZY7JHXQ3ZIL5Z2DTXCG7YQK?usp=drive_link
## Usage

1. Register a new account or log in with an existing account.
2. Create a new trip by providing a destination, dates, and preferences.
3. View the recommended tourist places, optimized itinerary, and suggested travel modes.
4. Update your trip details or delete the trip if no longer needed.
5. Manage your account settings and preferences.
