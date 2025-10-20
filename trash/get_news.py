from langchain_google_genai import ChatGoogleGenerativeAI
from datetime import datetime
import json

# Initialize Gemini model
llm = ChatGoogleGenerativeAI(
    model="models/gemini-2.0-flash",
    temperature=0.3,
    google_api_key="YOUR_GEMINI_API_KEY"  # Replace with your key
)

# -------------------------------------------------------------------
# 🧭 Function: Fetch Combined Travel Intelligence (Weather + Alerts)
# -------------------------------------------------------------------
def fetch_travel_update(params: str):
    """
    Fetch structured travel-related information for a given destination.
    Returns JSON with weather details, road status, and travel advisories.

    Input (JSON string):
    {
        "destination": "Manali, Himachal Pradesh"
    }
    """
    try:
        params_dict = json.loads(params)
        destination = params_dict.get("destination")

        if not destination:
            return {"error": "Missing 'destination' in input JSON."}

        today = datetime.now().strftime("%B %d, %Y")

        query = f"""
        Fetch the most recent (past 3 days) travel intelligence for {destination}, India.

        Include and format the final output strictly as **valid JSON** with the following schema:
        {{
          "Destination": "{destination}",
          "Date": "{today}",
          "Weather": {{
              "Current Temperature": "",
              "Min Temperature": "",
              "Next 5 Days Forecast": "",
              "IMD Alert": ""
          }},
          "Roadblocks and Road Status": [
              {{
                "Source": "",
                "Destination": "",
                "Road Status": "",
                "Advisory": ""
              }}
          ],
          "Travel Advisory": [
              ""
          ]
        }}

        Rules:
        - Only include facts from the last 3 days.
        - Fill all fields with the best available data (if not found, leave blank).
        - Use Celsius for temperatures.
        - Keep JSON clean, no Markdown, no explanations.
        - Mention official or media alerts (IMD, NDTV, BRO, Times of India, etc.) if relevant.
        """

        response = llm.invoke(query)

        # Try to parse model output as JSON safely
        try:
            structured_output = json.loads(response.content)
        except json.JSONDecodeError:
            # If model outputs text around JSON, try to extract JSON using regex
            import re
            match = re.search(r"\{.*\}", response.content, re.DOTALL)
            if match:
                structured_output = json.loads(match.group(0))
            else:
                structured_output = {"error": "Model did not return valid JSON.", "raw_response": response.content}

        return structured_output

    except Exception as e:
        return {"error": str(e)}


# -------------------------------------------------------------------
# 🚀 Example Usage
# -------------------------------------------------------------------
if __name__ == "__main__":
    params = json.dumps({"destination": "Chilika,odisha"})

    print("🧭 Fetching latest travel updates...\n")
    result = fetch_travel_update(params)
    print(json.dumps(result, indent=2))
