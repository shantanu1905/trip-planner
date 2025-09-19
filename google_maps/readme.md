# 1) build & run
docker build -t places-api .
docker run --rm -p 8000:8000 -e HEADLESS=true -v "$PWD/data:/app/data" places-api

# 2) call it
curl "http://localhost:8000/places?destination=Rishikesh"
# force refresh (ignore cache)
curl "http://localhost:8000/places?destination=Rishikesh&refresh=true"


# Activate it
venv\Scripts\Activate


pip install -r requirements.txt