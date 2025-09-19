# This is a Individual Fastapi Server for Scrapping Google Maps 


# Basic Requirement 
- Make sure you have crome drive installed / install crome browser
- create new envvironment 
- uvicorn main:app --reload --port 8002





# docker build

docker build -t google_maps_scrapper:v1.0 .

docker run -d -p 8002:8002 my-python-app