import os
import json
import time
import re
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote_plus
# ===================== FAST HTTP EXTRACTOR =====================
import aiohttp
from bs4 import BeautifulSoup
import asyncio

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# ===================== CONFIG =====================
CACHE_DIR = os.environ.get("CACHE_DIR", "./data")
os.makedirs(CACHE_DIR, exist_ok=True)


# ===================== CHROME SETUP =====================
def setup_driver_for_maps() -> webdriver.Chrome:
    """Return lightweight, headless Chrome driver for Maps listing scraping."""
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-logging")
    opts.add_argument("--log-level=3")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--blink-settings=imagesEnabled=false")
    opts.page_load_strategy = "eager"

    driver_path = ChromeDriverManager().install()
    service = Service(driver_path)
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(15)
    return driver


# ===================== SCRAPING UTILS =====================
def _scroll_and_load_places(driver, target_count=15):
    """Scroll sidebar until enough places appear."""
    selectors = [
        "[role='feed']",
        "div.m6QErb.DxyBCb.kA9KIf.dS8AEf.XiKgde.ecceSd[role='feed']",
    ]
    scroll_el = None
    for sel in selectors:
        els = driver.find_elements(By.CSS_SELECTOR, sel)
        if els:
            scroll_el = els[0]
            break
    if not scroll_el:
        return

    last_height = 0
    for _ in range(5):
        links = driver.find_elements(By.CSS_SELECTOR, "a.hfpxzc")
        if len(links) >= target_count:
            break
        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scroll_el)
        time.sleep(0.7)
        new_height = driver.execute_script("return arguments[0].scrollHeight", scroll_el)
        if new_height == last_height:
            break
        last_height = new_height


def _extract_place_info(aria_label: str, href: str) -> Dict:
    name = aria_label.split(",")[0].strip() if "," in aria_label else aria_label.strip()
    return {"name": name, "url": href}


def extract_tourist_places(destination: str, limit: int = 15) -> List[Dict]:
    """Scrape top tourist places for a destination from Google Maps search."""
    q = f"tourist places in {destination}"
    url = f"https://www.google.com/maps/search/{quote_plus(q)}"
    driver = setup_driver_for_maps()
    results = []

    try:
        driver.get(url)
        time.sleep(4)
        _scroll_and_load_places(driver, target_count=limit)
        time.sleep(1)
        links = driver.find_elements(By.CSS_SELECTOR, "a.hfpxzc")

        for link in links[:limit]:
            aria = link.get_attribute("aria-label")
            href = link.get_attribute("href")
            if aria and href:
                results.append(_extract_place_info(aria, href))
            if len(results) >= limit:
                break
    finally:
        driver.quit()

    return results


# ===================== CACHING =====================
def build_cache_filename(destination: str) -> str:
    safe = destination.lower().replace(" ", "_")
    return os.path.join(CACHE_DIR, f"places_{safe}.json")


def save_places_data(data: List[Dict], path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_cached_places(path: str) -> Optional[List[Dict]]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ===================== DATA EXTRACTION HELPERS =====================
def extract_lat_lng_from_url(url: str) -> Tuple[Optional[float], Optional[float]]:
    match_at = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", url)
    if match_at:
        return float(match_at.group(1)), float(match_at.group(2))
    match_d = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", url)
    if match_d:
        return float(match_d.group(1)), float(match_d.group(2))
    return None, None




async def fetch_image_and_description(session, place: Dict) -> Dict:
    """Async extraction using page meta tags (no Selenium)."""
    url = place["url"]
    lat, lng = extract_lat_lng_from_url(url)

    try:
        async with session.get(url, timeout=10) as resp:
            html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")
            img = soup.find("meta", property="og:image")

            # ✅ Always set description to None (null in JSON)
            desc = None

            return {
                "Name": place["name"],
                "Description": desc,
                "GeoCoordinates": {"lat": lat, "lng": lng},
                "ImageURL": img["content"] if img else None,
                "Google_web_url": url,
            }
    except Exception as e:
        print(f"Error fetching {place['name']}: {e}")
        return {
            "Name": place["name"],
            "Description": None,
            "GeoCoordinates": {"lat": lat, "lng": lng},
            "ImageURL": None,
            "Google_web_url": url,
        }


async def gather_place_details(places: List[Dict]) -> List[Dict]:
    """Run parallel async requests for image + description."""
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_image_and_description(session, p) for p in places]
        return await asyncio.gather(*tasks)
