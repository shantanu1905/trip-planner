# ticket_search_agent.py
import json
import re
from datetime import datetime
from typing import Dict
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_react_agent, AgentExecutor
from langchain.prompts import PromptTemplate
from app.utils.easemytrip import search_trains, get_station_code
from dotenv import load_dotenv
import os 


load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# ------------------ TOOLS ------------------

@tool
def search_train_tickets(params: str):
    """Search train tickets. Required: {"from_station": "City", "to_station": "City", "date": "YYYY-MM-DD"}"""
    try:
        data = json.loads(params)
        from_station = data["from_station"]
        to_station = data["to_station"]
        date = data["date"]

        datetime.strptime(date, "%Y-%m-%d")  # Validate format

        from_code, _ = get_station_code(from_station)
        to_code, _ = get_station_code(to_station)

        if not from_code or not to_code:
            return json.dumps({
                "available_trains_count": 0,
                "from_station_code": "UNKNOWN",
                "to_station_code": "UNKNOWN",
                "error": f"Invalid stations: {from_station}/{to_station}"
            })

        trains = search_trains(
            from_code,
            to_code,
            datetime.strptime(date, "%Y-%m-%d").strftime("%d/%m/%Y")
        )

        return json.dumps({
            "available_trains_count": len(trains) if trains else 0,
            "from_station_code": from_code,
            "to_station_code": to_code
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def search_flight_tickets(params: str):
    """Search flights. Required: {"from_city": "City", "to_city": "City", "date": "YYYY-MM-DD"}"""
    try:
        data = json.loads(params)
        return json.dumps({
            "available_flights_count": 0,
            "from_city": data["from_city"],
            "to_city": data["to_city"]
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def search_bus_tickets(params: str):
    """Search buses. Required: {"from_city": "City", "to_city": "City", "date": "YYYY-MM-DD"}"""
    try:
        data = json.loads(params)
        return json.dumps({
            "available_buses_count": 0,
            "from_city": data["from_city"],
            "to_city": data["to_city"]
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


# ------------------ MAIN FUNCTION ------------------

def search_travel_tickets(input_json: Dict) -> Dict:
    """
    Search ticket availability for multi-leg journey.

    Args:
        input_json: {
            "legs": [...],
            "start_date": "YYYY-MM-DD"
        }

    Returns:
        {
            "travelling_options": [...],
            "error": "optional error message"
        }
    """

    # Setup LLM (API key picked from env/config)
    llm = ChatGoogleGenerativeAI(
        model="models/gemini-2.0-flash",
        temperature=0,
        google_api_key= GEMINI_API_KEY  # Replace with your key

    )

    # Setup tools
    tools = [search_train_tickets, search_flight_tickets, search_bus_tickets]
    tool_names = [t.name for t in tools]

    # Setup prompt
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

    # Create agent
    agent = create_react_agent(
        llm=llm,
        tools=tools,
        prompt=prompt_template.partial(
            tools=", ".join([t.name for t in tools]),
            tool_names=", ".join(tool_names)
        )
    )

    # Create executor
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=15
    )

    try:
        # Run agent
        print("INSIDE SEARCH TICKETS")
        print("INSIDE SEARCH TICKETS@@@@@@@@@@@@@@@@@@@@@@@")
        print(input_json)


        response = executor.invoke({"input": json.dumps(input_json)})
        output_text = response.get("output", "")

        # Try to parse JSON cleanly
        try:
            return json.loads(output_text)
        except:
            pass

        # Remove markdown fences if any
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', output_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass

        # Find JSON anywhere
        match = re.search(r'\{.*"travelling_options".*\}', output_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                pass

        return {"travelling_options": [], "error": "Could not parse output"}

    except Exception as e:
        return {"travelling_options": [], "error": str(e)}
