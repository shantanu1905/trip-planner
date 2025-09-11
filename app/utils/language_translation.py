import hashlib
import json
import httpx
import os
import datetime
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from app.database.models import TranslationCache
from langchain_core.output_parsers.json import JsonOutputParser
from langchain.prompts import PromptTemplate
from langchain.schema import OutputParserException
# Load environment variables from .env
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_URL =  os.getenv("GEMINI_URL")



parser = JsonOutputParser()
prompt_template = PromptTemplate(
    template="""
    You are a translation engine.
    Translate only the VALUES of this JSON object from {source_lang} to {target_lang}.
    DO NOT translate keys.
    Return valid JSON only, same structure.

    Input JSON:
    {json_string}

    Return JSON only, no explanations.
    """,
    input_variables=["source_lang", "target_lang", "json_string"]
)

async def call_gemini_translation_api(json_data: dict, source_lang: str, target_lang: str):
    json_string = json.dumps(json_data, ensure_ascii=False)
    prompt = prompt_template.format(
        source_lang=source_lang,
        target_lang=target_lang,
        json_string=json_string
    )

    # Call Gemini API
    headers = {"Content-Type": "application/json", "X-goog-api-key": GEMINI_API_KEY}
    body = {"contents": [{"parts": [{"text": prompt}]}]}

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(GEMINI_URL, headers=headers, json=body)

        if response.status_code == 200:
            result = response.json()
            raw_text = result["candidates"][0]["content"]["parts"][0]["text"]

            try:
                return parser.parse(raw_text)  # ✅ Enforce valid JSON
            except OutputParserException:
                print("⚠️ Gemini returned invalid JSON, using original data.")
                return json_data
        else:
            print("Gemini API Error:", response.status_code, response.text)
            return json_data


async def translate_with_cache(db: Session, json_data: dict, target_lang, source_lang="English"):
    """
    Checks translation cache. If not found, calls Gemini API and saves the result in DB.
    Works with JSONB and stores lang enums as plain strings.
    """

    # Convert Enums to plain strings
    source_lang_str = source_lang.value if hasattr(source_lang, "value") else str(source_lang)
    target_lang_str = target_lang.value if hasattr(target_lang, "value") else str(target_lang)

    if source_lang_str == target_lang_str:
        return json_data  # No translation needed

    # Hash must use string version for consistency
    text_hash = hashlib.md5(
        f"{json.dumps(json_data, ensure_ascii=False)}_{source_lang_str}_{target_lang_str}".encode()
    ).hexdigest()

    # Check cache
    cached = db.query(TranslationCache).filter(
        TranslationCache.source_text_hash == text_hash
    ).first()

    if cached:
        return cached.translated_text  # already dict because JSONB stores dicts

    # Call Gemini API → returns dict
    translated_dict = await call_gemini_translation_api(json_data, source_lang_str, target_lang_str)

    # Save dict directly as JSONB
    new_cache = TranslationCache(
        source_text_hash=text_hash,
        source_text=json.dumps(json_data, ensure_ascii=False),  # original request as string
        source_lang=source_lang_str,
        target_lang=target_lang_str,
        translated_text=translated_dict,  # dict goes here, JSONB accepts it
        created_at=datetime.datetime.utcnow()
    )

    db.add(new_cache)
    db.commit()

    return translated_dict