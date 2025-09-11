from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time
import json
import csv
from datetime import datetime
from urllib.parse import unquote

def setup_driver_for_maps():
    """
    Set up Chrome WebDriver optimized for Google Maps
    """
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver
    except Exception as e:
        print(f"Failed to set up ChromeDriver: {e}")
        return None

def scroll_and_load_all_places(driver):
    """
    Scroll through the left sidebar to load all tourist places
    """
    print("Scrolling to load all places...")
    
    try:
        # Specific selectors based on your dev tools findings
        scrollable_containers = [
            "div.m6QErb.DxyBCb.kA9KIf.dS8AEf.XiKgde.ecceSd[role='feed']",  # Your exact element
            "div[role='feed'][aria-label*='Results for']",  # More generic version
            "div.m6QErb[role='feed']",  # Shortened version
            ".m6QErb.DxyBCb",  # Even shorter
            "[role='feed']",  # Most generic
            ".m6QErb",  # Fallback
        ]
        
        scrollable_element = None
        for i, selector in enumerate(scrollable_containers):
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    # Get the one that's actually scrollable (has overflow)
                    for element in elements:
                        computed_height = driver.execute_script(
                            "return arguments[0].scrollHeight > arguments[0].clientHeight;", 
                            element
                        )
                        if computed_height:
                            scrollable_element = element
                            print(f"✓ Found scrollable container: {selector}")
                            break
                    if scrollable_element:
                        break
            except Exception as e:
                print(f"  Selector {i+1} failed: {e}")
                continue
        
        if not scrollable_element:
            print("❌ Could not find scrollable container, trying page scroll...")
            # Fallback to page scrolling
            for i in range(10):
                driver.execute_script("window.scrollBy(0, 1000);")
                time.sleep(2)
                print(f"  Page scroll {i+1}/10")
        else:
            print(f"✓ Using scrollable element: {scrollable_element.tag_name}")
            
            # Get initial state
            initial_scroll_height = driver.execute_script("return arguments[0].scrollHeight;", scrollable_element)
            print(f"  Initial scroll height: {initial_scroll_height}px")
            
            current_scroll_position = 0
            scroll_step = 500
            no_change_count = 0
            max_no_change = 3
            
            for attempt in range(20):  # Max 20 scroll attempts
                # Set absolute scroll position (not relative)
                new_scroll_position = current_scroll_position + scroll_step
                
                driver.execute_script(f"""
                    arguments[0].scrollTop = {new_scroll_position};
                """, scrollable_element)
                
                time.sleep(2)  # Wait for content to load
                
                # Check actual position after scroll
                actual_scroll_top = driver.execute_script("return arguments[0].scrollTop;", scrollable_element)
                scroll_height = driver.execute_script("return arguments[0].scrollHeight;", scrollable_element)
                client_height = driver.execute_script("return arguments[0].clientHeight;", scrollable_element)
                
                print(f"  Attempt {attempt + 1}: Set={new_scroll_position}, Actual={actual_scroll_top}, Height={scroll_height}")
                
                # Check if scroll actually moved
                if actual_scroll_top == current_scroll_position:
                    no_change_count += 1
                    print(f"    No movement ({no_change_count}/{max_no_change})")
                    
                    if no_change_count >= max_no_change:
                        print("  ✓ Reached bottom - can't scroll further")
                        break
                else:
                    no_change_count = 0
                    movement = actual_scroll_top - current_scroll_position
                    print(f"    ✓ Moved {movement}px down")
                
                # Update current position to actual position
                current_scroll_position = actual_scroll_top
                
                # Check if we're at the bottom
                if actual_scroll_top + client_height >= scroll_height - 10:  # 10px buffer
                    print("  ✓ Reached bottom of container")
                    break
                
                # Look for "Show more" buttons
                try:
                    show_more_buttons = driver.find_elements(By.CSS_SELECTOR, 
                        "button[aria-label*='more'], button[aria-label*='Show'], .HlvSq")
                    for button in show_more_buttons:
                        if button.is_displayed() and button.is_enabled():
                            print("  Found 'Show more' button, clicking...")
                            driver.execute_script("arguments[0].click();", button)
                            time.sleep(3)
                            break
                except:
                    pass
        
        print("✓ Finished scrolling")
        time.sleep(3)  # Final wait for content to stabilize
        
        # Final count of places found
        try:
            place_links = driver.find_elements(By.CSS_SELECTOR, "a.hfpxzc")
            print(f"  Total places found after scrolling: {len(place_links)}")
        except:
            pass
            
    except Exception as e:
        print(f"Scrolling error: {e}")
        print("Continuing without scrolling...")
        import traceback
        traceback.print_exc()

def extract_place_info(aria_label, href):
    """
    Extract clean place name from aria-label and decode href
    """
    try:
        # Clean the place name from aria-label
        # Example: "Maa Mansa Devi Temple, niranjani akhadaHaridwar" -> "Maa Mansa Devi Temple"
        if ',' in aria_label:
            place_name = aria_label.split(',')[0].strip()
        else:
            place_name = aria_label.strip()
        
        # Decode the href URL
        decoded_href = unquote(href)
        
        return {
            'name': place_name,
            'full_aria_label': aria_label,
            'url': href,
            'decoded_url': decoded_href
        }
    except Exception as e:
        return {
            'name': 'Error extracting name',
            'full_aria_label': aria_label,
            'url': href,
            'decoded_url': href,
            'error': str(e)
        }

def extract_tourist_places(url):
    """
    Extract all tourist places from Google Maps search results
    """
    driver = setup_driver_for_maps()
    if not driver:
        return []
    
    places_data = []
    
    try:
        print(f"Opening URL: {url}")
        driver.get(url)
        
        # Wait for initial load
        print("Waiting for initial page load...")
        time.sleep(10)
        
        # Scroll to load all content
        scroll_and_load_all_places(driver)
        
        # Find all place links with class 'hfpxzc'
        print("Extracting place data...")
        place_links = driver.find_elements(By.CSS_SELECTOR, "a.hfpxzc")
        
        print(f"Found {len(place_links)} place links")
        
        for i, link in enumerate(place_links, 1):
            try:
                aria_label = link.get_attribute('aria-label')
                href = link.get_attribute('href')
                
                if aria_label and href:
                    place_info = extract_place_info(aria_label, href)
                    places_data.append(place_info)
                    print(f"  {i:2d}. {place_info['name']}")
                else:
                    print(f"  {i:2d}. [Missing data]")
                    
            except Exception as e:
                print(f"  {i:2d}. Error extracting place {i}: {e}")
        
        print(f"\n✓ Successfully extracted {len(places_data)} places")
        
    except Exception as e:
        print(f"Error occurred: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        driver.quit()
    
    return places_data

def save_places_data(places_data, base_filename=None):
    """
    Save extracted places data to multiple formats
    """
    if not places_data:
        print("No data to save")
        return
    
    if not base_filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"haridwar_tourist_places_{timestamp}"
    
    # Save as JSON
    json_file = f"{base_filename}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(places_data, f, indent=2, ensure_ascii=False)
    print(f"✓ Saved JSON: {json_file}")
    
    

def main():
    """
    Main function to extract tourist places data
    """
    maps_url = "https://www.google.com/maps/search/tourist+places+in+Reshikesh"
    
    print("=" * 70)
    print("TOURIST PLACES EXTRACTOR - HARIDWAR")
    print("=" * 70)
    print("This will extract place names and URLs from Google Maps")
    print("-" * 70)
    
    # Extract places data
    places_data = extract_tourist_places(maps_url)
    
    if places_data:
        print(f"\n📍 EXTRACTED {len(places_data)} PLACES:")
        print("-" * 50)
        for i, place in enumerate(places_data[:10], 1):  # Show first 10
            print(f"{i:2d}. {place['name']}")
        
        if len(places_data) > 10:
            print(f"    ... and {len(places_data) - 10} more places")
        
        # Save data to files
        print("\n💾 SAVING DATA...")
        save_places_data(places_data)
        
        print(f"\n✅ SUCCESS!")
        print(f"   Total places extracted: {len(places_data)}")
        print(f"   Files saved in current directory")
    else:
        print("❌ No places data extracted")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()