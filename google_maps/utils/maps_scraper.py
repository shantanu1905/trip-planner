import os
import json
import time
import re
from typing import List, Dict, Optional
from urllib.parse import unquote, quote_plus
from selenium.common.exceptions import TimeoutException
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException


# ===================== CONFIG =====================
CACHE_DIR = os.environ.get("CACHE_DIR", "./data")
os.makedirs(CACHE_DIR, exist_ok=True)


# ===================== CHROME SETUP =====================
def chrome_options_headless() -> Options:
    opts = Options()
    headless_env = os.environ.get("HEADLESS", "true").lower() not in ("false", "0", "no")
    if headless_env:
        opts.add_argument("--headless=new")

    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option('useAutomationExtension', False)

    chrome_bin = os.environ.get("CHROME_BIN")
    if chrome_bin:
        opts.binary_location = chrome_bin

    opts.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36")
    return opts

def get_driver():
    options = Options()
    options.add_argument("--headless")  # Run browser in headless mode
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    driver_path = ChromeDriverManager().install()
    service = Service(driver_path)
    return webdriver.Chrome(service=service, options=options)

def setup_driver_for_maps() -> webdriver.Chrome:
    """Create a Chrome driver using webdriver_manager."""
    options = chrome_options_headless()
    driver_path = ChromeDriverManager().install()
    service = Service(driver_path)
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver


# ===================== SCRAPING UTILS =====================
def _scroll_and_load_all_places(driver):
    """Scroll the left results pane to load all items."""
    scrollable_selectors = [
        "div.m6QErb.DxyBCb.kA9KIf.dS8AEf.XiKgde.ecceSd[role='feed']",
        "div[role='feed'][aria-label*='Results for']",
        "div.m6QErb[role='feed']",
        ".m6QErb.DxyBCb",
        "[role='feed']",
        ".m6QErb",
    ]

    scrollable_element = None
    for selector in scrollable_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                scrollable_element = elements[0]
                break
        except:
            continue

    if not scrollable_element:
        return

    last_height = driver.execute_script("return arguments[0].scrollHeight", scrollable_element)
    for _ in range(20):
        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_element)
        time.sleep(2)
        new_height = driver.execute_script("return arguments[0].scrollHeight", scrollable_element)
        if new_height == last_height:
            break
        last_height = new_height


def _extract_place_info(aria_label: str, href: str) -> Dict:
    """Extract and clean place info from Google Maps search result link."""
    name = aria_label.split(',')[0].strip() if ',' in aria_label else aria_label.strip()
    return {
        "name": name,
        "url": href,
    }


# ===================== MAIN SCRAPER =====================
def extract_tourist_places(destination: str) -> List[Dict]:
    """Scrape tourist places for a given destination from Google Maps."""
    q = f"tourist places in {destination}"
    maps_url = f"https://www.google.com/maps/search/{quote_plus(q)}"

    driver = setup_driver_for_maps()
    results = []

    try:
        driver.get(maps_url)
        time.sleep(8)  # Wait for page load

        _scroll_and_load_all_places(driver)
        time.sleep(2)

        links = driver.find_elements(By.CSS_SELECTOR, "a.hfpxzc")
        for link in links:
            aria_label = link.get_attribute("aria-label")
            href = link.get_attribute("href")
            if aria_label and href:
                results.append(_extract_place_info(aria_label, href))

        return results

    finally:
        try:
            driver.quit()
        except:
            pass


# ===================== CACHING =====================
def build_cache_filename(destination: str) -> str:
    safe_name = destination.lower().replace(" ", "_")
    return os.path.join(CACHE_DIR, f"places_{safe_name}.json")


def save_places_data(data: List[Dict], file_path: str):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_cached_places(file_path: str) -> Optional[List[Dict]]:
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return None
    return None




def extract_lat_lng_from_url(url: str):
    # Check for @lat,long first
    match_at = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', url)
    if match_at:
        return float(match_at.group(1)), float(match_at.group(2))
    
    # Fallback: look for !3d<lat>!4d<long>
    match_d = re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', url)
    if match_d:
        return float(match_d.group(1)), float(match_d.group(2))

    return None, None


# def extract_image_and_description(driver, url):
#     """
#     Opens a Google Maps place URL in Selenium and extracts:
#     - Main image URL
#     - Description text (if available)
#     Returns tuple: (image_url, description)
#     """
#     try:
#         driver.get(url)
#         time.sleep(5)  # Wait for page load, adjust as needed

#         # Extract main image
#         image_element = driver.find_element(By.CSS_SELECTOR, "img[decoding='async']")
#         image_url = image_element.get_attribute("src") if image_element else None

#         # Extract description
#         description_element = driver.find_element(By.CSS_SELECTOR, "div.PYvSYb")
#         description = description_element.text if description_element else None

#         return image_url, description
#     except TimeoutException:
#         return None, None
#     except Exception:
#         return None, None


def extract_image_and_description(driver, url):
    """
    Opens a Google Maps place URL in Selenium and extracts:
    - Main image URL from the constant class 'aoRNLd kn2E5e NMjTrf lvtCsd'
    - Description text (if available)
    Returns tuple: (image_url, description)
    """
    try:
        driver.get(url)
        time.sleep(5)  # Adjust wait time if page load is slow

        image_url, description = None, None

        # ---- Extract main image from the given button class ----
        try:
            button_element = driver.find_element(
                By.CSS_SELECTOR, "button.aoRNLd.kn2E5e.NMjTrf.lvtCsd img"
            )
            image_url = button_element.get_attribute("src")
        except NoSuchElementException:
            image_url = None

        # ---- Extract description if available ----
        try:
            description_element = driver.find_element(By.CSS_SELECTOR, "div.PYvSYb")
            description = description_element.text if description_element else None
        except NoSuchElementException:
            description = None

        return image_url, description

    except TimeoutException:
        return None, None
    except Exception as e:
        print(f"Error extracting data for {url}: {e}")
        return None, None

