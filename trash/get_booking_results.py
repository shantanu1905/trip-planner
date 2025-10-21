import json
import re
from datetime import datetime, timedelta
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_react_agent, AgentExecuto
from langchain.prompts import PromptTemplate


def parse_time_to_hours(time_str: str) -> float:
    """Convert time string like '17 hours' or '1 hour 30 minutes' to hours"""
    hours = 0
    minutes = 0
    
    hour_match = re.search(r'(\d+)\s*hours?', time_str)
    minute_match = re.search(r'(\d+)\s*minutes?', time_str)
    
    if hour_match:
        hours = int(hour_match.group(1))
    if minute_match:
        minutes = int(minute_match.group(1))
    
    return hours + (minutes / 60.0)


@tool
def search_train_tickets(params: str):
    """
    Search train tickets between two stations on given date.
    REQUIRED params: {"from_station": "CityName", "to_station": "CityName", "date": "YYYY-MM-DD"}
    Example: {"from_station": "Nagpur", "to_station": "New Delhi", "date": "2025-10-06"}
    """
    try:
        data = json.loads(params)
        from_station = data["from_station"]
        to_station = data["to_station"]
        date = data["date"]
        
        # Validate date format
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return json.dumps({"error": "Date must be in YYYY-MM-DD format"})

        # Convert station names to codes
        from_code, _ = get_station_code(from_station)
        to_code, _ = get_station_code(to_station)

        if not from_code or not to_code:
            return json.dumps({
                "error": f"Invalid station codes for {from_station} or {to_station}",
                "available_trains_count": 0,
                "from_station_code": "UNKNOWN",
                "to_station_code": "UNKNOWN"
            })

        trains = search_trains(from_code, to_code, datetime.strptime(date, "%Y-%m-%d").strftime("%d/%m/%Y"))
        train_count = len(trains) if trains else 0
        
        return json.dumps({
            "available_trains_count": train_count,
            "from_station_code": from_code,
            "to_station_code": to_code
        })

    except KeyError as e:
        return json.dumps({"error": f"Missing required parameter: {str(e)}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def search_flight_tickets(params: str):
    """
    Search flight tickets between two cities on given date.
    REQUIRED params: {"from_city": "CityName", "to_city": "CityName", "date": "YYYY-MM-DD"}
    Example: {"from_city": "Nagpur", "to_city": "Delhi", "date": "2025-10-06"}
    """
    try:
        data = json.loads(params)
        from_city = data["from_city"]
        to_city = data["to_city"]
        date = data["date"]
        
        return json.dumps({
            "available_flights_count": 0,
            "from_city": from_city,
            "to_city": to_city
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def search_bus_tickets(params: str):
    """
    Search bus tickets between two cities on given date.
    REQUIRED params: {"from_city": "CityName", "to_city": "CityName", "date": "YYYY-MM-DD"}
    Example: {"from_city": "Kathgodam", "to_city": "Nainital", "date": "2025-10-07"}
    """
    try:
        data = json.loads(params)
        from_city = data["from_city"]
        to_city = data["to_city"]
        date = data["date"]
        
        return json.dumps({
            "available_bus_count": 0,
            "from_city": from_city,
            "to_city": to_city
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


# ------------------ GEMINI MODEL ------------------

llm = ChatGoogleGenerativeAI(
    model="models/gemini-2.0-flash",
    temperature=0,
    google_api_key="AIzaSyDDG2QGser0XZ7GgvmXf_KbbaMDDfNDHsw"
)


# ------------------ PROMPT ------------------

prompt_template = PromptTemplate(
    input_variables=["input", "agent_scratchpad", "tools", "tool_names"],
    template="""
You are a travel planning AI assistant that searches for ticket availability across multiple legs of a journey.

TOOL USAGE RULES (CRITICAL):
1. search_train_tickets: {{"from_station": "CityName", "to_station": "CityName", "date": "YYYY-MM-DD"}}
2. search_flight_tickets: {{"from_city": "CityName", "to_city": "CityName", "date": "YYYY-MM-DD"}}
3. search_bus_tickets: {{"from_city": "CityName", "to_city": "CityName", "date": "YYYY-MM-DD"}}

DATE CALCULATION:
- Extract start_date from input (format: YYYY-MM-DD or YYYY-MM-DD HH:MM:SS.mmm)
- For start_date with timestamp, extract only YYYY-MM-DD part
- For each subsequent leg: previous_date + approx_time + 3 hours buffer
- Always use YYYY-MM-DD format in tool calls

PROCESS EACH LEG:
1. Parse the start_date and extract YYYY-MM-DD
2. For leg 1: Use extracted date
3. For leg 2+: Add previous leg's travel time + 3 hours to get next date
4. Call appropriate tool based on mode field
5. Collect all results

IMPORTANT:
- NEVER pass timestamps to tools, only YYYY-MM-DD
- Handle "Taxi/Bus" mode by using search_bus_tickets
- Always return complete JSON with all fields

Available tools: {tool_names}

Follow this reasoning format:
Thought: [Your reasoning about what to do next]
Action: [One of {tool_names}]
Action Input: [Correct JSON with required fields in YYYY-MM-DD format]
Observation: [Tool result]
... (repeat for each leg)
Thought: I now have all the information
Final Answer: [Pure JSON output below]

OUTPUT FORMAT (NO MARKDOWN):
{{
  "travelling_options": [
    {{
      "from": "string",
      "to": "string",
      "from_station_code": "string",
      "to_station_code": "string",
      "mode": "string",
      "approx_time": "string",
      "journey_date": "YYYY-MM-DD",
      "available_trains_count": 0,
      "available_flights_count": 0,
      "available_buses_count": 0
    }}
  ]
}}

Question: {input}
{agent_scratchpad}
"""
)

# ------------------ AGENT SETUP ------------------

tools = [search_train_tickets, search_flight_tickets, search_bus_tickets]
tool_names = [t.name for t in tools]

agent = create_react_agent(
    llm=llm,
    tools=tools,
    prompt=prompt_template.partial(
        tools=", ".join([t.name for t in tools]),
        tool_names=", ".join(tool_names)
    )
)

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True,
    max_iterations=15
)


# ------------------ OUTPUT PARSER FUNCTION ------------------

def parse_agent_output(output_text: str) -> dict:
    """Parse agent output and extract clean JSON"""
    try:
        return json.loads(output_text)
    except json.JSONDecodeError:
        pass
    
    # Remove markdown code blocks
    json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
    match = re.search(json_pattern, output_text, re.DOTALL)
    
    if match:
        json_str = match.group(1)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
    
    # Find JSON anywhere in text
    json_pattern2 = r'\{[^{}]*"travelling_options"[^{}]*\[.*?\]\s*\}'
    match2 = re.search(json_pattern2, output_text, re.DOTALL)
    
    if match2:
        json_str = match2.group(0)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
    
    print(f"Warning: Could not parse output: {output_text[:200]}...")
    return {"travelling_options": []}


# ------------------ RUN AGENT ------------------

travelling_options = {
    "legs": [
        {
            "from": "Nagpur",
            "to": "New Delhi",
            "mode": "Train",
            "approx_cost": "₹1500",
            "approx_time": "17 hours",
            "Note": "No direct train service to Nainital."
        },
        {
            "from": "New Delhi",
            "to": "Kathgodam",
            "mode": "Train",
            "approx_cost": "₹600",
            "approx_time": "7 hours",
            "Note": "Kathgodam is the nearest railway station."
        },
        {
            "from": "Kathgodam",
            "to": "Nainital",
            "mode": "Taxi/Bus",
            "approx_cost": "₹500",
            "approx_time": "1 hour 30 minutes",
            "Note": "Local transport required."
        }
    ],
    "start_date": "2025-10-06"
}

try:
    response = agent_executor.invoke({"input": json.dumps(travelling_options)})
    agent_output_text = response.get("output", "")
    final_result = parse_agent_output(agent_output_text)
    
    print("\n" + "="*60)
    print("FINAL RESULT:")
    print("="*60)
    print(json.dumps(final_result, indent=2))
    
except Exception as e:
    print(f"Error: {str(e)}")
    final_result = {"travelling_options": [], "error": str(e)}