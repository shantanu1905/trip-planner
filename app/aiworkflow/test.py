import os
from langchain.agents import Tool, initialize_agent
from langchain.prompts import PromptTemplate
from langchain.schema import BaseOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI  # wrapper for Gemini

# 1. Setup Gemini LLM
api_key = os.getenv("GEMINI_API_KEY")
model_id = "gemini-2.5-flash"  # or preview model id  
llm = ChatGoogleGenerativeAI(model=model_id, api_key=api_key)

# 2. Define your tool functions

def tool_train_search(from_station: str, to_station: str, date: str, preferred_time: str = None):
    """Call your existing search_trains, return structured JSON."""
    trains = search_trains(from_station, to_station, date)
    if trains is None:
        return []
    # optionally filter on preferred_time if given
    if preferred_time:
        filtered = []
        for t in trains:
            dep = t.get("departureTime")
            if dep:
                hour = int(dep.split(":")[0])
                if get_time_period(hour) == preferred_time:
                    filtered.append(t)
        return filtered
    return trains

def tool_flight_search(from_city: str, to_city: str, date: str):
    """Call your flight API (mock example)."""
    return search_flights(from_city, to_city, date)

def tool_bus_search(from_city: str, to_city: str, date: str):
    return search_buses(from_city, to_city, date)

# 3. Wrap them as LangChain Tools

tools = [
    Tool(
        name="TrainSearch",
        func=tool_train_search,
        description="Search trains between two stations on a given date, optionally filtering by preferred time."
    ),
    Tool(
        name="FlightSearch",
        func=tool_flight_search,
        description="Search flights between two cities for a given date."
    ),
    Tool(
        name="BusSearch",
        func=tool_bus_search,
        description="Search buses between two cities for a given date."
    ),
]

# 4. Initialize the agent  
agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent="zero-shot-react-description",
    verbose=True
)

# 5. Use the agent

prompt = """
You are a travel planning assistant.  
I want to travel from Nagpur to Ratnagiri on 10 October 2025.  
I prefer evening departures for train legs.  
If one leg takes 14 hours, you must plan the next leg accordingly (with 3-5 hours buffer or evening preference).  
Suggest an itinerary (train / flight / bus) with class-wise fares, departure & arrival times.  
"""
response = agent.run(prompt)
print(response)
