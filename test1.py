# from langchain_core.tools import tool
# from datetime import timedelta
# from app.utils.easemytrip import * 
# from app.routers.bookings import get_time_period
# from langchain_google_genai import ChatGoogleGenerativeAI 
# from langchain_core.tools import tool 
# import requests


# @tool
# def get_train_tickets(params: str):
#     """
#     Fetch train tickets between two stations within a given date range.
#     Input should be a JSON string with keys:
#     {
#         "from_station": "Nagpur",
#         "to_station": "Mumbai",
#         "start_date": "2025-10-10",
#         "end_date": "2025-10-11"
#     }
#     """
#     try:
#         # Parse JSON string to dict
#         params_dict = json.loads(params)
#         from_station = params_dict.get("from_station")
#         to_station = params_dict.get("to_station")
#         start_date = params_dict.get("start_date")
#         end_date = params_dict.get("end_date")

#         # Convert dates
#         start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
#         end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")

#         results = []
#         current_date = start_date_obj

#         # Search trains for each date
#         while current_date <= end_date_obj:
#             trains = search_trains(from_station, to_station, current_date.strftime("%d/%m/%Y"))
#             if trains:
#                 for train in trains:
#                     results.append({
#                         "date": current_date.strftime("%d-%m-%Y"),
#                         "train_name": train["trainName"],
#                         "train_number": train["trainNumber"],
#                         "departure": train["departureTime"],
#                         "arrival": train["arrivalTime"],
#                         "duration": train["duration"],
#                         "classes": train["classes"],
#                         "booking_url": f"https://railways.easemytrip.com/TrainListInfo/{train['fromStnName']}({train['fromStnCode']})-to-{train['toStnName']}({train['toStnCode']})/2/{current_date.strftime('%d-%m-%Y')}"
#                     })
#             current_date += timedelta(days=1)

#         return {"tickets": results}

#     except json.JSONDecodeError:
#         return {"error": "Invalid JSON input. Please provide a valid JSON string."}
#     except Exception as e:
#         return {"error": str(e)}



# # Initialize Gemini Flash model
# llm = ChatGoogleGenerativeAI(
#     model="models/gemini-2.0-flash",
#     temperature=0,
#     google_api_key="AIzaSyA7Gdawwd1fG7oXBcAQ2VQ4za8QgRVMH00"
# )

# from langchain.agents import create_react_agent, AgentExecutor
# from langchain import hub

# # Pull ReAct prompt
# prompt = hub.pull("hwchase17/react")

# # Register all tools
# tools = [get_train_tickets]

# # Create agent
# agent = create_react_agent(
#     llm=llm,
#     tools=tools,
#     prompt=prompt
# )

# # Wrap with executor
# agent_executor = AgentExecutor(
#     agent=agent,
#     tools=tools,
#     verbose=True
# )



# from datetime import datetime

# params = json.dumps({
#     "from_station": "NGP",
#     "to_station": "CSMT",
#     "start_date": "2025-10-10",
#     "end_date": "2025-10-11"
# })

# response = agent_executor.invoke({
#     "input": f"Get train tickets with params: {params}"
# })

# print(response["output"])


from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64
import requests

encKey = "EDMEMT1234"
decKey = "TMTOO1vDhT9aWsV1"

def EncryptionV1(plaintext):
    key = decKey.encode('utf-8')
    iv = decKey.encode('utf-8')
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded = pad(plaintext.encode('utf-8'), AES.block_size)
    encrypted = cipher.encrypt(padded)
    return base64.b64encode(encrypted).decode('utf-8')

def decryptV1(ciphertext):
    key = decKey.encode('utf-8')
    iv = decKey.encode('utf-8')
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = cipher.decrypt(base64.b64decode(ciphertext))
    return unpad(decrypted, AES.block_size).decode('utf-8')






def source_auto_suggest(place_name):
    url = "https://autosuggest.easemytrip.com/api/auto/bus?useby=popularu&key=jNUYK0Yj5ibO6ZVIkfTiFA=="
    jsonString = {
        "userName": "",
        "password": "",
        "Prefix": place_name,
        # Search buses using GetSearchResult API (POST)
        "country_code": "IN"
    }
    import json
    RQ = {"request": EncryptionV1(json.dumps(jsonString))}
    jsonrequest = {
        "request": RQ["request"],
        "isIOS": False,
        "ip": "49.249.40.58",
        "encryptedHeader": "7ZTtohPgMEKTZQZk4/Cn1mpXnyNZDJIRcrdCFo5ahIk="
    }
    response = requests.post(url, json=jsonrequest)
    # Decrypt and parse the response
    decrypted = decryptV1(response.text)
    try:
        return json.loads(decrypted)
    except Exception:
        return {"error": "Failed to decrypt or parse response", "raw": decrypted}




print(source_auto_suggest('Delhi'))