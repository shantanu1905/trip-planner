import json
from datetime import datetime, timedelta
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_react_agent, AgentExecutor
from app.utils.easemytrip import search_trains, get_station_code
from langchain.prompts import PromptTemplate

@tool
def search_train_tickets(params: str):
    """
    Search train tickets between two stations on given date.
    Input JSON: { "from_station": "NGP", "to_station": "LTT", "date": "2025-10-10" }
    """
    try:
        data = json.loads(params)
        from_station = data["from_station"]
        to_station = data["to_station"]
        date = data["date"]

        # Convert station names to codes
        from_code, _ = get_station_code(from_station)
        to_code, _ = get_station_code(to_station)

        if not from_code or not to_code:
            return {"error": f"Invalid station codes for {from_station} or {to_station}"}

        trains = search_trains(from_code, to_code, datetime.strptime(date, "%Y-%m-%d").strftime("%d/%m/%Y"))
        train_count = len(trains) if trains else 0
        return {"available_trains_count": train_count , "from_station_code" :from_code , "to_station_code": to_code}

    except Exception as e:
        return {"error": str(e)}


@tool
def search_flight_tickets(params: str):
    """
    Search flight tickets between two city on given date.
    Input JSON: { "from_city": "Nagpur", "to_city": "delhi", "date": "2025-10-10" }
    """
    # Placeholder
    return {"flights": []}


@tool
def search_bus_tickets(params: str):
    """
    Search bus tickets between two city on given date.
    Input JSON: { "from_city": "Nagpur", "to_city": "delhi", "date": "2025-10-10" }
    """
    # Placeholder
    return {"buses": []}





# ------------------ GEMINI MODEL ------------------

llm = ChatGoogleGenerativeAI(
    model="models/gemini-2.0-flash",
    temperature=0,
    google_api_key="AIzaSyA7Gdawwd1fG7oXBcAQ2VQ4za8QgRVMH00"  # Replace with your real key
)






# ------------------ PROMPT ------------------

prompt_template = PromptTemplate(
    input_variables=["input", "agent_scratchpad", "tools", "tool_names"],
    template="""
You are a travel planning AI assistant.  
The user provides a multi-leg journey with start date/time and modes (Train/Flight/Bus).  

Your tasks:
1. For each leg, check the `mode` field:
   - If Train → search_train_tickets
   - If Flight → search_flight_tickets
   - If Bus → search_bus_tickets
2. Use the first leg's start_date as the journey start.
3. For each leg:
   - Search tickets for `from` → `to` on the given date.
   - Add travel time (`approx_time`) + 3 hours buffer → next leg's date.
4. Continue until all legs are processed sequentially.
5. Return **all ticket details** exactly as tool returns them.

Follow this exact reasoning format:

Question: The journey details  
Thought: Step by step reasoning  
Action: One of [{tool_names}]  
Action Input: JSON with correct params  
Observation: Tool result  
... repeat for each leg ...  
Thought: I now know the final answer  
Final Answer: Ticket details for all legs with all fields

Begin!

Return output strictly in the following JSON format:

{{
  "travelling_options": [
    {{
      "from": "<from>",
      "to": "<to>",
      "from_station_code": "<from>",
      "to_station_code": "<to>",
      "mode": "<Train/Flight/Bus>",
      "approx_time": "<duration>",
      "journey_date": "<datetime>",
      "available_trains_count": <int>,
      "available_flights_count": <int>,
      "available_buses_count": <int>
    }}
  ]
}}

Begin!

Question: {input}
{agent_scratchpad}
"""
)

# ------------------ AGENT SETUP ------------------

tools = [search_train_tickets, search_flight_tickets, search_bus_tickets]



# Extract tool names dynamically
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
    verbose=True
)

# ------------------ RUN AGENT ------------------

travelling_options = json.loads("""
{
    "legs": [
        {
            "from": "Nagpur",
            "to": "Mumbai",
            "mode": "Train",
            "approx_time": "14 hours"
        },
        {
            "from": "Mumbai",
            "to": "Ratnagiri",
            "mode": "Train",
            "approx_time": "7 hours"
        }
    ],
    "start_date": "2025-10-10 20:00"
}
""")

response = agent_executor.invoke({"input": json.dumps(travelling_options)})

# ------------------ PROCESS OUTPUT ------------------

# The agent output is usually a string, try to parse as JSON
try:
    agent_output = json.loads(response["output"])
except:
    agent_output = response["output"]

# Prepare dynamic final result per leg
final_result = {"travelling_options": []}
