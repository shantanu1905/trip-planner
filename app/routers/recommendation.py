
from fastapi import APIRouter, Depends, status
from app.database.models import UserPreferences , Settings
from app.utils.redis_utils import translate_with_cache
from app.utils.auth_helpers import user_dependency
from app.database.database import db_dependency
import random
import pandas as pd
import numpy as np 

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


dataset_path = "./travel_dataset.csv"
df = pd.read_csv(dataset_path)  # Make sure CSV file exists in data/ folder

# Replace invalid values (NaN, inf) with None for JSON safety
df.replace([np.inf, -np.inf], np.nan, inplace=True)
df = df.where(pd.notnull(df), None)

# Columns we want in output
required_columns = [
    "name",
    "city",
    "state",
    "activitytype",
    "Best_time_to_visit",
    "Image_url",
    "description"
]

@router.get("/travelplaces")
async def get_user_recommendations(
    db: db_dependency,
    user: user_dependency
):
    try:
        # 1️⃣ Fetch user preferences instead of settings
        preferences = db.query(UserPreferences).filter(UserPreferences.user_id == user.id).first()
        if not preferences or not preferences.activities:
            response_data = {
                "status": False,
                "data": [],
                "message": "No activities found in user preferences. Please update your preferences in USER Settings.",
                "status_code": status.HTTP_404_NOT_FOUND
            }

            # Translation
            settings = db.query(Settings).filter(Settings.user_id == user.id).first()
            target_lang = settings.native_language if settings and settings.native_language else "English"
            if target_lang != "English":
                response_data = await translate_with_cache(response_data, target_lang)

            return response_data

        # 2️⃣ Extract user activities as strings
        user_activities = [
            a.value if hasattr(a, "value") else a
            for a in preferences.activities
        ]

        # 3️⃣ Group recommendations by activity
        recommendations = {}

        for activity in user_activities:
            activity_data = df[df["activitytype"] == activity.upper()]

            if activity_data.empty:
                recommendations[activity] = []
            else:
                random_records = activity_data.sample(
                    n=min(5, len(activity_data)),
                    random_state=random.randint(1, len(activity_data))
                )

                filtered_records = (
                    random_records[required_columns]
                    .replace([np.inf, -np.inf], None)
                    .where(pd.notnull(random_records[required_columns]), None)
                )

                recommendations[activity] = filtered_records.to_dict(orient="records")

        # 4️⃣ Handle case when all lists are empty
        if all(len(v) == 0 for v in recommendations.values()):
            response_data = {
                "status": False,
                "data": [],
                "message": "No recommendations found for your preferences.",
                "status_code": status.HTTP_404_NOT_FOUND
            }

            # Translation
            settings = db.query(Settings).filter(Settings.user_id == user.id).first()
            target_lang = settings.native_language if settings and settings.native_language else "English"
            if target_lang != "English":
                response_data = await translate_with_cache(response_data, target_lang)

            return response_data

        # 5️⃣ Prepare success response
        response_data = {
            "status": True,
            "data": recommendations,
            "message": "Recommendations fetched successfully.",
            "status_code": status.HTTP_200_OK
        }

        # 6️⃣ Translation (same style as your other endpoint)
        settings = db.query(Settings).filter(Settings.user_id == user.id).first()
        target_lang = settings.native_language if settings and settings.native_language else "English"

        if target_lang != "English":
            response_data = await translate_with_cache(response_data, target_lang)

        # Final return
        return response_data

    except Exception as e:
        response_data = {
            "status": False,
            "data": [],
            "message": f"Error fetching recommendations: {str(e)}",
            "status_code": status.HTTP_400_BAD_REQUEST
        }

        # Error translation too
        settings = db.query(Settings).filter(Settings.user_id == user.id).first()
        target_lang = settings.native_language if settings and settings.native_language else "English"
        if target_lang != "English":
            response_data = await translate_with_cache(response_data, target_lang)

        return response_data