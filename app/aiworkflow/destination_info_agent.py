import os
import json
import requests
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

# --- API KEYS ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")


# --- Initialize Gemini Model ---
llm = ChatGoogleGenerativeAI(
    model="models/gemini-2.0-flash",
    temperature=0.3,
    google_api_key=GEMINI_API_KEY
)


# ------------------ Helper: Fetch Destination Info ------------------
def get_destination_description(destination: str) -> str:
    """
    Uses Gemini to generate a short, factual travel description about the destination.
    """
    prompt = f"""
    Provide a short, 5-10 sentence travel description for the destination "{destination}".
    Focus on what makes it special — geography, attractions, culture, or climate.
    Output ONLY the description text.
    """

    try:
        response = llm.invoke(prompt)
        description = response.content.strip()
        # Remove any unwanted formatting
        description = description.replace("\n", " ").strip()
        return description
    except Exception as e:
        return f"Error fetching description: {e}"


# ------------------ Helper: Fetch Images from Pixabay ------------------
def fetch_pixabay_images(destination: str, limit: int = 5) -> list:
    """
    Fetches image URLs from Pixabay for the given destination.
    """
    url = "https://pixabay.com/api/"
    params = {
        "key": PIXABAY_API_KEY,
        "q": destination,
        "image_type": "photo",
        "per_page": limit,
        "safesearch": "true"
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        hits = data.get("hits", [])
        image_urls = [hit["largeImageURL"] for hit in hits]
        return image_urls
    except Exception as e:
        print(f"Error fetching images: {e}")
        return []


# ------------------ Main Function ------------------
def get_destination_data(destination: str) -> dict:
    """
    Combines Gemini description and Pixabay images into a structured JSON response.
    """
    print(f"🔍 Gathering info for: {destination}")

    description = get_destination_description(destination)
    image_urls = fetch_pixabay_images(destination, limit=5)

    result = {
        "destination": destination,
        "destination_details": description,
        "image_url": image_urls
    }

    return result


# ------------------ Example Run ------------------
# if __name__ == "__main__":
#     destination = "Manali, Himachal Pradesh, India"
#     data = get_destination_data(destination)
#     print(json.dumps(data, indent=2, ensure_ascii=False))





