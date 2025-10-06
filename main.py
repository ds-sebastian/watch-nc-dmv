import asyncio
import logging
import os
import sys
from datetime import datetime

import aiohttp
from playwright.async_api import async_playwright

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Configuration from environment variables
BROWSERLESS_HOST = os.getenv("BROWSERLESS_HOST", "localhost")
BROWSERLESS_PORT = os.getenv("BROWSERLESS_PORT", "3000")
TOKEN = os.getenv("BROWSERLESS_TOKEN", "")
LONGITUDE = float(os.getenv("LONGITUDE", ""))
LATITUDE = float(os.getenv("LATITUDE", ""))
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "15"))
MAX_LOCATIONS = int(os.getenv("MAX_LOCATIONS", "25"))

# Home Assistant Configuration
HOME_ASSISTANT_URL = os.getenv("HOME_ASSISTANT_URL", "http://homeassistant.local:8123")
HA_WEBHOOK_ID = os.getenv("HA_WEBHOOK_ID", "dmv_appointment_found")

# Categories to monitor
CATEGORIES = {"Knowledge Test": 6, "Permits": 9}

# Cache for monitored locations
MONITORED_LOCATIONS = set()


async def send_ha_webhook(category, locations_info):
    """Trigger Home Assistant webhook with appointment data"""
    webhook_url = f"{HOME_ASSISTANT_URL}/api/webhook/{HA_WEBHOOK_ID}"

    locations_data = [
        {"name": name, "address": info["address"], "rank": info["rank"]}
        for name, info in sorted(locations_info.items(), key=lambda x: x[1]["rank"])
    ]

    payload = {
        "category": category,
        "location_count": len(locations_data),
        "locations": locations_data,
        "timestamp": datetime.now().isoformat(),
        "booking_url": "https://skiptheline.ncdot.gov/",
        "closest_location": locations_data[0]["name"] if locations_data else None,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload, timeout=10) as response:
                if response.status == 200:
                    logger.info("Webhook triggered successfully")
                    return True
                else:
                    logger.warning(f"Webhook failed: HTTP {response.status}")
                    return False
    except aiohttp.ClientError as e:
        logger.error(f"Webhook connection error: {e}")
        return False
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return False


async def fetch_nearby_locations():
    """Fetch only the closest N locations (already sorted by distance)"""
    ws_endpoint = f"ws://{BROWSERLESS_HOST}:{BROWSERLESS_PORT}?token={TOKEN}"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(ws_endpoint)
            context = await browser.new_context(
                geolocation={"longitude": LONGITUDE, "latitude": LATITUDE},
                permissions=["geolocation"],
            )
            page = await context.new_page()

            logger.debug("Navigating to homepage...")
            await page.goto(
                "https://skiptheline.ncdot.gov/", wait_until="domcontentloaded"
            )
            await page.wait_for_selector("#cmdMakeAppt", state="visible", timeout=30000)
            await page.wait_for_timeout(500)
            await page.click("#cmdMakeAppt")

            logger.debug("Selecting appointment type...")
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(1500)

            await page.wait_for_selector(
                '.QflowObjectItem[data-id="6"]', state="visible", timeout=30000
            )
            await page.click('.QflowObjectItem[data-id="6"]')
            await page.wait_for_timeout(1500)

            logger.debug("Loading locations...")
            await page.evaluate("document.querySelector('.next-button').click()")
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(3000)

            logger.debug("Switching to list view...")
            list_view_button = await page.query_selector("text=List view")
            if list_view_button:
                await list_view_button.click()
                await page.wait_for_timeout(2000)

            await page.wait_for_selector(
                ".QflowObjectItem", state="visible", timeout=10000
            )
            await page.wait_for_timeout(1000)

            all_locations = await page.query_selector_all(".QflowObjectItem")
            locations_to_process = all_locations[:MAX_LOCATIONS]

            logger.info(
                f"Processing {len(locations_to_process)} closest locations (out of {len(all_locations)} total)"
            )

            locations_list = []
            for idx, location in enumerate(locations_to_process, 1):
                try:
                    inner_div = await location.query_selector("div[title]")
                    if not inner_div:
                        continue

                    name_div = await inner_div.query_selector("div:first-child")
                    if not name_div:
                        continue

                    location_name = (await name_div.text_content()).strip()

                    address_div = await inner_div.query_selector(".form-control-child")
                    if not address_div:
                        continue

                    address = (await address_div.text_content()).strip()

                    if location_name and address:
                        locations_list.append(
                            {
                                "name": location_name,
                                "address": address,
                                "rank": idx,
                            }
                        )
                        logger.debug(f"#{idx:2d} {location_name}")

                except Exception as e:
                    logger.debug(f"Error parsing location: {e}")
                    continue

            await browser.close()
            return locations_list

    except Exception as e:
        logger.error(f"Error fetching locations: {e}", exc_info=True)
        return []


async def check_category(category_name, category_id):
    """Check a single category for availability (only monitored locations)"""
    ws_endpoint = f"ws://{BROWSERLESS_HOST}:{BROWSERLESS_PORT}?token={TOKEN}"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(ws_endpoint)
            context = await browser.new_context(
                geolocation={"longitude": LONGITUDE, "latitude": LATITUDE},
                permissions=["geolocation"],
            )
            page = await context.new_page()

            logger.debug(f"Checking {category_name}...")
            await page.goto(
                "https://skiptheline.ncdot.gov/", wait_until="domcontentloaded"
            )
            await page.wait_for_selector("#cmdMakeAppt", state="visible", timeout=30000)
            await page.wait_for_timeout(500)
            await page.click("#cmdMakeAppt")

            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(1500)

            category_selector = f'.QflowObjectItem[data-id="{category_id}"]'
            await page.wait_for_selector(
                category_selector, state="visible", timeout=30000
            )
            await page.click(category_selector)
            await page.wait_for_timeout(1500)

            await page.evaluate("document.querySelector('.next-button').click()")

            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except:
                await page.wait_for_load_state("domcontentloaded", timeout=10000)

            await page.wait_for_timeout(2000)

            try:
                list_view_button = await page.wait_for_selector(
                    "text=List view", state="visible", timeout=5000
                )
                if list_view_button:
                    await list_view_button.click()
                    await page.wait_for_timeout(2000)
            except:
                logger.debug("List view button not found, may already be in list view")

            await page.wait_for_selector(
                ".QflowObjectItem", state="visible", timeout=10000
            )
            await page.wait_for_timeout(1000)

            all_locations = await page.query_selector_all(".QflowObjectItem")
            locations_to_check = all_locations[:MAX_LOCATIONS]

            locations_with_availability = []

            for location in locations_to_check:
                try:
                    inner_div = await location.query_selector("div[title]")
                    if not inner_div:
                        continue

                    name_div = await inner_div.query_selector("div:first-child")
                    if not name_div:
                        continue

                    location_name = (await name_div.text_content()).strip()

                    if location_name not in MONITORED_LOCATIONS:
                        continue

                    no_avail = await inner_div.query_selector(".No-Availability")

                    if no_avail:
                        is_visible = await no_avail.is_visible()
                        if not is_visible:
                            locations_with_availability.append(location_name)
                            logger.debug(f"Availability found at: {location_name}")
                    else:
                        locations_with_availability.append(location_name)
                        logger.debug(f"Availability found at: {location_name}")

                except Exception as e:
                    logger.debug(f"Error checking location: {e}")
                    continue

            await browser.close()
            return locations_with_availability

    except Exception as e:
        logger.error(f"{category_name} check failed: {str(e)[:100]}")
        return []


async def monitor_categories():
    """Monitor both categories in parallel"""
    global MONITORED_LOCATIONS

    logger.info("=" * 70)
    logger.info("🚀 Starting NC DMV Appointment Monitor")
    logger.info(f"📍 Location: ({LATITUDE}, {LONGITUDE})")
    logger.info(f"🔄 Check interval: {CHECK_INTERVAL} seconds")
    logger.info(f"📏 Monitoring closest: {MAX_LOCATIONS} locations")
    logger.info(f"📋 Categories: {', '.join(CATEGORIES.keys())}")
    logger.info(f"🏠 Home Assistant: {HOME_ASSISTANT_URL}")
    logger.info(f"🪝 Webhook ID: {HA_WEBHOOK_ID}")
    logger.info(f"📊 Log Level: {LOG_LEVEL}")
    logger.info("=" * 70)

    logger.info("🗺️  Fetching nearby DMV locations...")
    locations_list = await fetch_nearby_locations()

    if not locations_list:
        logger.error("No locations found. Exiting...")
        return

    location_info = {}
    for loc in locations_list:
        MONITORED_LOCATIONS.add(loc["name"])
        location_info[loc["name"]] = {"address": loc["address"], "rank": loc["rank"]}

    logger.info(f"✓ Monitoring {len(MONITORED_LOCATIONS)} locations")
    logger.info("🎯 Starting availability monitoring...")

    while True:
        tasks = [check_category(name, cat_id) for name, cat_id in CATEGORIES.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, (category_name, _) in enumerate(CATEGORIES.items()):
            if isinstance(results[i], Exception):
                logger.error(f"{category_name}: Error - {results[i]}")
                continue

            available_locations = results[i]

            if available_locations:
                logger.info("=" * 70)
                logger.info("🎉 AVAILABILITY FOUND!")
                logger.info(f"📅 Category: {category_name}")
                logger.info("📍 Locations with openings:")

                sorted_locations = sorted(
                    available_locations, key=lambda x: location_info[x]["rank"]
                )

                webhook_locations_info = {
                    loc_name: location_info[loc_name] for loc_name in sorted_locations
                }

                for loc_name in sorted_locations:
                    info = location_info[loc_name]
                    logger.info(f"   #{info['rank']:2d} {loc_name}")
                    logger.info(f"       {info['address']}")

                logger.info("📤 Sending notification to Home Assistant...")
                await send_ha_webhook(category_name, webhook_locations_info)
                logger.info("=" * 70)
            else:
                logger.info(f"❌ {category_name}: No availability")

        logger.debug(f"Sleeping for {CHECK_INTERVAL} seconds...")
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    try:
        asyncio.run(monitor_categories())
    except KeyboardInterrupt:
        logger.info("👋 Monitor stopped by user")
