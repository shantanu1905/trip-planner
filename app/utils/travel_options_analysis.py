from typing import Dict, List, Optional
from datetime import datetime
import re
from statistics import mean, median
import json
from app.utils.trains_utils import search_trains, analyze_train_info 

from app.utils.bus_utils import search_buses , get_bus_insights


def analyze_trip_options(legs_data: dict) -> dict:
    """
    Analyze all legs (Train, Bus, etc.) and attach respective analysis inside each leg.
    Output format matches user's requested structure.
    """
    option_name = legs_data.get("option_name", "Unknown Route")
    legs = legs_data.get("legs", [])

    analyzed_legs = []

    for leg in legs:
        mode = leg.get("mode", "").lower()
        journey_date = leg.get("journey_date")
        from_city = leg.get("from")
        to_city = leg.get("to")
        from_code = leg.get("from_code")
        to_code = leg.get("to_code")

        # Default
        analyzed_leg = leg.copy()

        # --- 🚌 BUS MODE ---
        if mode == "bus":
            try:
                print(f"🚌 Analyzing Bus: {from_city} → {to_city} on {journey_date}")

                # Format date for API
                try:
                    formatted_date = datetime.strptime(journey_date, "%Y-%m-%d").strftime("%d-%m-%Y")
                except:
                    formatted_date = journey_date

                bus_data = search_buses(from_city, to_city, journey_date=formatted_date)

                if bus_data:
                    insights = get_bus_insights(bus_data)
                    analyzed_leg["bus_data_analysis"] = insights
                else:
                    analyzed_leg["bus_data_analysis"] = {
                        "status": False,
                        "message": "No bus data found or API failed"
                    }

            except Exception as e:
                analyzed_leg["bus_data_analysis"] = {
                    "status": False,
                    "error": str(e),
                    "message": "Bus analysis failed"
                }

        # --- 🚆 TRAIN MODE ---
        elif mode == "train":
            try:
                print(f"🚆 Analyzing Train: {from_city} → {to_city} on {journey_date}")

                # Prepare single-leg input for analyze_train_info
                single_leg_input = {
                    "option_name": f"Train {from_city}-{to_city}",
                    "legs": [leg]
                }

                train_result = analyze_train_info(single_leg_input, search_trains_func=search_trains)
                analyzed_leg["train_data_analysis"] = train_result

            except Exception as e:
                analyzed_leg["train_data_analysis"] = {
                    "status": False,
                    "error": str(e),
                    "message": "Train analysis failed"
                }

        else:
            # For future support (Flights, Cabs, etc.)
            analyzed_leg["analysis"] = {
                "status": False,
                "message": f"No analyzer implemented for mode '{mode}'"
            }

        analyzed_legs.append(analyzed_leg)

    return {
        "status": True,
        "option_name": option_name,
        "total_legs": len(analyzed_legs),
        "legs": analyzed_legs,
        "generated_on": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }




# if __name__ == "__main__":
#     sample_legs = {
#         "option_name": "Smart Route Plan",
#         "legs": [
#             {
#                 "from": "Nagpur",
#                 "to": "Pune",
#                 "from_code": "NGP",
#                 "to_code": "NDLS",
#                 "mode": "Bus",
#                 "journey_date": "2025-11-01"
#             },
#             {
#                 "from": "Delhi",
#                 "to": "Haridwar",
#                 "from_code": "NDLS",
#                 "to_code": "HW",
#                 "mode": "Train",
#                 "journey_date": "2025-11-02"
#             }
#         ]
#     }

#     unified_result = analyze_trip_options(sample_legs)
#     print(json.dumps(unified_result, indent=2))



