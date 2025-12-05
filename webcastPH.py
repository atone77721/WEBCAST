import asyncio
from playwright.async_api import async_playwright
import aiohttp
from datetime import datetime, timezone, timedelta
import pytz
import os

API_URL = "https://api.ppv.to/api/streams"

CUSTOM_HEADERS = [
    '#EXTVLCOPT:http-origin=https://ppv.to',
    '#EXTVLCOPT:http-referrer=https://ppv.to/',
    '#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:143.0) Gecko/20100101 Firefox/143.0'
]

# ---------------------------------------------------------------------
# UTILITIES
# ---------------------------------------------------------------------

def format_timestamp(ts):
    try:
        phil_tz = pytz.timezone('Asia/Manila')
        dt = datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone(phil_tz)
        return dt.strftime("%b %d @ %I:%M %p") + " PHT"
    except Exception:
        return None


def fix_m3u8(url: str):
    if url.endswith("index.m3u8"):
        return url.replace("index.m3u8", "tracks-v1a1/mono.ts.m3u8")
    return url


# ---------------------------------------------------------------------
# API CALL
# ---------------------------------------------------------------------

async def get_streams():
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        headers = {"User-Agent": "Mozilla/5.0"}
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(API_URL) as r:
                if r.status != 200:
                    print("❌ API error:", r.status)
                    return None
                return await r.json()
    except Exception as e:
        print("❌ API fetch error:", e)
        return None


# ---------------------------------------------------------------------
# M3U8 SCRAPER
# ---------------------------------------------------------------------

async def grab_m3u8_from_iframe(page, iframe_url):
    print(f"   → Loading iframe: {iframe_url}")
    found = set()

    def on_response(resp):
        if ".m3u8" in resp.url:
            print("   🎯 Found stream:", resp.url)
            found.add(resp.url)

    page.on("response", on_response)

    try:
        await page.goto(iframe_url, timeout=25000, wait_until="load")
    except Exception as e:
        print("   ❌ Iframe load failed:", e)
        return set()

    await asyncio.sleep(8)

    page.remove_listener("response", on_response)

    if not found:
        print("   ❌ No .m3u8 detected")

    return {fix_m3u8(u) for u in found}


# ---------------------------------------------------------------------
# M3U BUILDER
# ---------------------------------------------------------------------

def build_m3u(streams, url_map):
    lines = ['#EXTM3U']

    for s in streams:
        key = f"{s['name']}::{s['category']}::{s['iframe']}"
        urls = url_map.get(key, [])

        if urls:
            for u in urls:
                lines.append(f'#EXTINF:-1,{s["name"]}')
                lines.extend(CUSTOM_HEADERS)
                lines.append(u)
        else:
            lines.append(f'#EXTINF:-1,❌ NO STREAM - {s["name"]}')
            lines.extend(CUSTOM_HEADERS)
            lines.append("https://example.com/nostream.m3u8")

    return "\n".join(lines)


# ---------------------------------------------------------------------
# MAIN WORKFLOW
# ---------------------------------------------------------------------

async def main():

    print("🚀 Starting scraper...")

    api = await get_streams()
    if not api or "streams" not in api:
        print("❌ No API data received")
        return

    phil_tz = pytz.timezone("Asia/Manila")
    now = datetime.now(phil_tz)

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_end = today_start + timedelta(days=2)

    start_ts = int(today_start.timestamp())
    end_ts = int(tomorrow_end.timestamp())
    now_ts = int(now.timestamp())

    all_streams = []

    for cat in api["streams"]:
        for s in cat.get("streams", []):
            st = int(s.get("starts_at", 0))

            if start_ts <= st < end_ts:
                name = s.get("name", "Event")
                stamp = format_timestamp(st)
                if stamp:
                    name = f"{name} ({stamp})"

                is_live = st <= now_ts < int(s.get("ends_at", st + 7200))

                all_streams.append({
                    "name": name,
                    "iframe": s.get("iframe"),
                    "category": cat.get("category", "Misc"),
                    "status": "LIVE" if is_live else "UPCOMING"
                })

    print(f"📌 Streams today & tomorrow: {len(all_streams)}")

    if not all_streams:
        print("⚠ No stream events found")
        return

    url_map = {}

    # Import stealth
    from playwright_stealth import stealth

    # Playwright
    async with async_playwright() as p:

        # -----------------------------------------
        # HEADLESS FIX + CLOUDFLARE BYPASS PATCHES
        # -----------------------------------------
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-extensions",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--disable-ipc-flooding-protection",
                "--disable-popup-blocking"
            ]
        )

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:143.0) Gecko/20100101 Firefox/143.0",
        )

        page = await context.new_page()

        # Remove webdriver property
        await page.add_init_script("""
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});
""")

        # Apply stealth patches
        await stealth(page)

        # Scrape each iframe
        for s in all_streams:
            key = f"{s['name']}::{s['category']}::{s['iframe']}"

            iframe_url = s["iframe"]
            if not iframe_url:
                print(f"❌ No iframe for {s['name']}")
                url_map[key] = []
                continue

            print(f"\n🔎 Scraping: {s['name']} ({s['category']})")
            urls = await grab_m3u8_from_iframe(page, iframe_url)
            url_map[key] = list(urls)

        await browser.close()

    # Build playlist
    playlist = build_m3u(all_streams, url_map)

    with open("SportsWebcast.m3u8", "w", encoding="utf-8") as f:
        f.write(playlist)

    print("\n✅ Playlist written: SportsWebcast.m3u8\n")


if __name__ == "__main__":
    asyncio.run(main())
