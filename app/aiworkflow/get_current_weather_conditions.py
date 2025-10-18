from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import tool, AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from datetime import datetime
from dotenv import load_dotenv
import requests
import json
import os 

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")


# Initialize Gemini model
llm = ChatGoogleGenerativeAI(
    model="models/gemini-2.0-flash",
    temperature=0.3,
    google_api_key=GEMINI_API_KEY
)

# -------------------------------------------------------------------
# 🌤️ Tool: Fetch Current Weather Data
# -------------------------------------------------------------------
@tool
def get_current_weather(location: str) -> dict:
    """
    Fetch current weather information for a given location using WeatherAPI.
    
    Args:
        location: City name or location (e.g., "Nagpur", "Delhi", "Mumbai")
    
    Returns:
        Dictionary containing weather data including temperature, conditions, humidity, etc.
    """
    try:
        url = f"https://api.weatherapi.com/v1/current.json?key={WEATHER_API_KEY}&q={location}&aqi=no"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Extract and structure relevant weather information
        weather_info = {
            "location": {
                "name": data["location"]["name"],
                "region": data["location"]["region"],
                "country": data["location"]["country"],
                "localtime": data["location"]["localtime"]
            },
            "current": {
                "temperature_c": data["current"]["temp_c"],
                "temperature_f": data["current"]["temp_f"],
                "condition": data["current"]["condition"]["text"],
                "feels_like_c": data["current"]["feelslike_c"],
                "feels_like_f": data["current"]["feelslike_f"],
                "humidity": data["current"]["humidity"],
                "wind_kph": data["current"]["wind_kph"],
                "wind_dir": data["current"]["wind_dir"],
                "pressure_mb": data["current"]["pressure_mb"],
                "visibility_km": data["current"]["vis_km"],
                "uv_index": data["current"]["uv"],
                "cloud_coverage": data["current"]["cloud"]
            }
        }
        
        return weather_info
        
    except requests.exceptions.RequestException as e:
        return {"error": f"Failed to fetch weather data: {str(e)}"}
    except KeyError as e:
        return {"error": f"Unexpected API response format: {str(e)}"}
    except Exception as e:
        return {"error": f"An error occurred: {str(e)}"}

# -------------------------------------------------------------------
# 🚨 Tool: Fetch Weather Alerts
# -------------------------------------------------------------------
@tool
def get_weather_alerts(location: str) -> dict:
    """
    Fetch weather alerts and warnings for a given location using WeatherAPI.
    
    Args:
        location: City name or location (e.g., "Rishikesh", "Delhi", "Mumbai")
    
    Returns:
        Dictionary containing weather alerts and warnings from meteorological departments
    """
    try:
        url = f"https://api.weatherapi.com/v1/alerts.json?key={WEATHER_API_KEY}&q={location}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Extract and structure alert information
        alerts_info = {
            "location": {
                "name": data["location"]["name"],
                "region": data["location"]["region"],
                "country": data["location"]["country"],
                "localtime": data["location"]["localtime"]
            },
            "alerts": data["alerts"]["alert"],
            "has_alerts": len(data["alerts"]["alert"]) > 0,
            "alert_count": len(data["alerts"]["alert"])
        }
        
        # If there are alerts, extract key information
        if alerts_info["has_alerts"]:
            alerts_summary = []
            for alert in alerts_info["alerts"]:
                summary = {
                    "headline": alert.get("headline", ""),
                    "severity": alert.get("severity", ""),
                    "urgency": alert.get("urgency", ""),
                    "areas": alert.get("areas", ""),
                    "category": alert.get("category", ""),
                    "event": alert.get("event", ""),
                    "effective": alert.get("effective", ""),
                    "expires": alert.get("expires", ""),
                    "desc": alert.get("desc", ""),
                    "instruction": alert.get("instruction", "")
                }
                alerts_summary.append(summary)
            alerts_info["alerts_summary"] = alerts_summary
        
        return alerts_info
        
    except requests.exceptions.RequestException as e:
        return {"error": f"Failed to fetch weather alerts: {str(e)}"}
    except KeyError as e:
        return {"error": f"Unexpected API response format: {str(e)}"}
    except Exception as e:
        return {"error": f"An error occurred: {str(e)}"}

# -------------------------------------------------------------------
# 🧭 Tool: Fetch Travel Intelligence with Exact Structure
# -------------------------------------------------------------------
@tool
def fetch_travel_advisory(destination: str) -> dict:
    """
    Fetch travel intelligence including road conditions and travel advisories for a destination.
    This uses AI to search for recent travel updates, road status, and advisories.
    
    Args:
        destination: Destination name (e.g., "Manali, Himachal Pradesh")
    
    Returns:
        Dictionary containing travel advisory, road conditions, and relevant alerts in specific structure
    """
    try:
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
        - Fill all fields with the best available data (if not found, leave blank "").
        - Use Celsius for temperatures.
        - Keep JSON clean, no Markdown, no explanations.
        - Mention official or media alerts (IMD, NDTV, BRO, Times of India, etc.) if relevant.
        - For "Roadblocks and Road Status", include multiple entries if there are multiple routes.
        - For "Travel Advisory", include each advisory as a separate string in the array.
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
                # Return default structure with error
                structured_output = {
                    "Destination": destination,
                    "Date": today,
                    "Weather": {
                        "Current Temperature": "",
                        "Min Temperature": "",
                        "Next 5 Days Forecast": "",
                        "IMD Alert": ""
                    },
                    "Roadblocks and Road Status": [],
                    "Travel Advisory": [f"Error: Could not parse response - {response.content[:200]}"]
                }

        return structured_output

    except Exception as e:
        today = datetime.now().strftime("%B %d, %Y")
        return {
            "Destination": destination,
            "Date": today,
            "Weather": {
                "Current Temperature": "",
                "Min Temperature": "",
                "Next 5 Days Forecast": "",
                "IMD Alert": ""
            },
            "Roadblocks and Road Status": [],
            "Travel Advisory": [f"Error: {str(e)}"]
        }

# -------------------------------------------------------------------
# 🎯 Main Function: Get Travel Intelligence for Destination
# -------------------------------------------------------------------
def fetch_travel_update(params: str) -> dict:
    """
    Fetch structured travel-related information for a given destination.
    Returns JSON with weather details, road status, and travel advisories.

    Input (JSON string):
    {
        "destination": "Manali, Himachal Pradesh"
    }
    
    Args:
        params: JSON string containing destination information
    
    Returns:
        Dictionary with the exact structure:
        {
          "Destination": "",
          "Date": "",
          "Weather": {...},
          "Roadblocks and Road Status": [...],
          "Travel Advisory": [...],
          "Alerts": [...] (only if alerts exist)
        }
    """
    try:
        # Parse JSON string input
        params_dict = json.loads(params)
        destination = params_dict.get("destination")
        
        if not destination:
            return {"error": "Missing 'destination' in input JSON."}
        
        print(f"🔍 Fetching travel intelligence for: {destination}")
        
        # Get weather data directly from API
        weather_data = get_current_weather.invoke(destination)
        
        # Get weather alerts from API
        alerts_data = get_weather_alerts.invoke(destination)
        
        # Get travel advisory with structured format
        travel_data = fetch_travel_advisory.invoke(destination)
        
        # If travel_data already has the correct structure, enhance it with API weather
        if "Weather" in travel_data and not weather_data.get("error"):
            travel_data["Weather"]["Current Temperature"] = f"{weather_data['current']['temperature_c']}°C (Feels like {weather_data['current']['feels_like_c']}°C)"
            
            # Add real-time weather condition
            condition = weather_data['current']['condition']
            
            # Check for weather alerts and add separate "Alerts" key if they exist
            if not alerts_data.get("error") and alerts_data.get("has_alerts"):
                # Create Alerts array
                alerts_list = []
                
                for alert in alerts_data.get("alerts_summary", []):
                    alert_item = {
                        "headline": alert.get("headline", ""),
                        "severity": alert.get("severity", ""),
                        "urgency": alert.get("urgency", ""),
                        "event": alert.get("event", ""),
                        "effective": alert.get("effective", ""),
                        "expires": alert.get("expires", ""),
                        "areas": alert.get("areas", ""),
                        "description": alert.get("desc", ""),
                        "instruction": alert.get("instruction", "")
                    }
                    alerts_list.append(alert_item)
                
                # Add Alerts key to travel_data
                travel_data["Alerts"] = alerts_list
                
                # Also update IMD Alert field with summary
                alert_headlines = [alert.get("headline", "") for alert in alerts_data.get("alerts_summary", [])]
                if alert_headlines:
                    travel_data["Weather"]["IMD Alert"] = " | ".join(filter(None, alert_headlines))
            
            elif condition and condition != "Clear":
                if not travel_data["Weather"]["IMD Alert"]:
                    travel_data["Weather"]["IMD Alert"] = f"Current condition: {condition}"
        
        return travel_data
        
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON input: {str(e)}"}
    except Exception as e:
        today = datetime.now().strftime("%B %d, %Y")
        return {
            "Destination": params_dict.get("destination", "Unknown") if 'params_dict' in locals() else "Unknown",
            "Date": today,
            "Weather": {
                "Current Temperature": "",
                "Min Temperature": "",
                "Next 5 Days Forecast": "",
                "IMD Alert": ""
            },
            "Roadblocks and Road Status": [],
            "Travel Advisory": [f"Error: {str(e)}"]
        }

# -------------------------------------------------------------------
# 🚀 Example Usage
# -------------------------------------------------------------------
# if __name__ == "__main__":
#     # Example 1: Destination without alerts
#     print("=" * 80)
#     print("🧭 Example 1: Destination WITHOUT Alerts")
#     print("=" * 80)
    
#     params1 = json.dumps({"destination": "Rishikesh"})
#     result1 = fetch_travel_update(params1)
#     print(json.dumps(result1, indent=2))
    
#     print("\n\n" + "=" * 80)
#     print("🧭 Example 2: Testing Multiple Destinations")
#     print("=" * 80)
    
#     test_destinations = [
#         {"destination": "Manali, Himachal Pradesh"},
#         {"destination": "Mumbai"},
#         {"destination": "Nagpur"}
#     ]
    
#     for dest_dict in test_destinations:
#         params = json.dumps(dest_dict)
#         print(f"\n📍 Destination: {dest_dict['destination']}")
#         print("-" * 80)
        
#         result = fetch_travel_update(params)
#         print(json.dumps(result, indent=2))
#         print("=" * 80)