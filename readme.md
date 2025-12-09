# AI Trip Planner

**TripCraft.AI** transforms travel planning from a chaotic chore into a seamless experience. We combine the reasoning power of **Google Gemini** with real-time **EaseMyTrip** inventory to create personalized, actionable itineraries that take you from "dreaming" to "booking" in minutes.

## Features
<img width="1920" height="1080" alt="23" src="https://github.com/user-attachments/assets/e7809154-afcc-4c3e-9323-c3af4838a3e8" />
<img width="1920" height="1080" alt="24" src="https://github.com/user-attachments/assets/a0f1561a-287b-44bd-943c-57ce62ce8496" />


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
   cd google_maps_scraper
   docker build --no-cache -t google_maps_scraper:latest .
   docker run -d --name google_maps_scraper -p 8002:8002 google_maps_scraper:latest
   ```

7. (Optional) Build and Run the Main Application with Docker:

   ```bash
   docker build --no-cache -t ai-trip-planner:latest .
   docker run -d --name tripplanner --env-file .env -p 8000:8000 ai-trip-planner:latest
   ```

   ## Resources 
   https://drive.google.com/drive/folders/1QwpTSaADXZY7JHXQ3ZIL5Z2DTXCG7YQK?usp=drive_link
