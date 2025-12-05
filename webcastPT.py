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

CATEGORY_LOGOS = {
    "Wrestling": "http://drewlive24.duckdns.org:9000/Logos/Wrestling.png",
    "Football": "http://drewlive24.duckdns.org:9000/Logos/Football.png",
    "Basketball": "http://drewlive24.duckdns.org:9000/Logos/NCAA.png",
    "Baseball": "http://drewlive24.duckdns.org:9000/Logos/Baseball.png",
    "American Football": "http://drewlive24.duckdns.org:9000/Logos/NFL3.png",
    "Combat Sports": "http://drewlive24.duckdns.org:9000/Logos/CombatSports2.png",
    "Darts": "http://drewlive24.duckdns.org:9000/Logos/Darts.png",
    "Motorsports": "http://drewlive24.duckdns.org:9000/Logos/Motorsports2.png",
    "Ice Hockey": "http://drewlive24.duckdns.org:9000/Logos/Hockey.png",
    "NBA": "http://drewlive24.duckdns.org:9000/Logos/NBA.png",
    "NCAA": "http://drewlive24.duckdns.org:9000/Logos/NCAA.png",
    "Cricket": "https://i.imgur.com/rA9TeSu.png"
}

CATEGORY_TVG_IDS = {
    "Wrestling": "PPV.EVENTS.Dummy.us",
    "Football": "Soccer.Dummy.us",
    "Basketball": "NCAA.Basketball.Dummy.us",
    "NBA": "NBA.Basketball.Dummy.us",
    "NCAA": "NCAA.Basketball.Dummy.us",
    "Baseball": "MLB.Baseball.Dummy.us",
    "American Football": "NFL.Dummy.us",
    "College Football": "NCAA.Football.Dummy.us",
    "Combat Sports": "PPV.EVENTS.Dummy.us",
    "Darts": "Darts.Dummy.us",
    "Motorsports": "Racing.Dummy.us",
    "Ice Hockey": "NHL.Hockey.Dummy.us",
    "Cricket": "Cricket.Dummy.us"
}

GROUP_RENAME_MAP = {
    "Wrestling": "Wrestling Events",
    "Football": "Global Football Streams",
    "Basketball": "NCAA College Basketball",
    "NBA": "NBA Games",
    "NCAA": "NCAA College Basketball",
    "Baseball": "MLB",
    "American Football": "NFL Action",
    "College Football": "NCAA College Football",
    "Combat Sports": "Combat Sports",
    "Darts": "Darts",
    "Motorsports": "Racing Action",
    "Ice Hockey": "NHL Action",
    "Cricket": "Cricket Games"
}

NBA_TEAMS = [
    "hawks","celtics","nets","hornets","bulls","cavaliers","mavericks","nuggets",
    "pistons","warriors","rockets","pacers","clippers","lakers","grizzlies",
    "heat","bucks","timberwolves","pelicans","knicks","thunder","magic","sixers",
    "suns","blazers","kings","spurs","raptors","jazz","wizards"
]

NCAA_KEYWORDS = ["wildcats","falcons","zips","crimson tide","bulldogs","hornets","great danes","braves","eagles"]
# (list shortened for space – functional)

# PT timezone
PT = pytz.timezone("America/Los_Angeles")


# --- Utilities ---
def format_timestamp(ts):
    """Format timestamp into Pacific Time (PST/PDT)."""
    try:
        dt = datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone(PT)
        return dt.strftime("%b %d @ %I:%M %p %Z")
    except:
        return None


def detect_basketball_type(name: str):
    name_lower = name.lower()
    if any(team in name_lower for team in NBA_TEAMS):
        return "NBA"
    if any(keyword in name_lower for keyword in NCAA_KEYWORDS):
        return "NCAA"
    return "Basketball"


def clean_tvg_id(tvg_id: str) -> str:
    """Remove any |status from tvg-id."""
    if not tvg_id:
        return tvg_id
    return tvg_id.split("|")[0].strip()


def fix_m3u8(url: str) -> str:
    if url.endswith("index.m3u8"):
        return url.replace("index.m3u8", "tracks-v1a1/mono.ts.m3u8")
    return url


# --- Network ---
async def get_streams():
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        headers = {"User-Agent": "Mozilla/5.0"}
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(API_URL) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()
    except:
        return None


# --- Playwright helper ---
async def grab_m3u8_from_iframe(page, iframe_url):
    found = set()

    def handler(r):
        if ".m3u8" in r.url:
            found.add(r.url)

    page.on("response", handler)
    try:
        await page.goto(iframe_url, timeout=25000, wait_until="domcontentloaded")
    except:
        return set()

    await asyncio.sleep(6)
    page.remove_listener("response", handler)

    preferred = [u for u in found if u.endswith("index.m3u8") or "tracks-v1a1" in u]
    if not preferred:
        preferred = list(found)

    return {fix_m3u8(u) for u in preferred}


# --- Build playlist ---
def build_m3u(streams, url_map):
    lines = ['#EXTM3U url-tvg="https://epgshare01.online/epgshare01/epg_ripper_DUMMY_CHANNELS.xml.gz"']
    seen = set()

    for s in streams:
        name = s["name"]
        if name.lower() in seen:
            continue
        seen.add(name.lower())

        cat = s["category"]
        if cat == "Basketball":
            cat = detect_basketball_type(name)

        logo = s.get("poster") or CATEGORY_LOGOS.get(cat, "")
        base_tvg = clean_tvg_id(CATEGORY_TVG_IDS.get(cat, "Misc.Dummy.us"))
        group = GROUP_RENAME_MAP.get(cat, f"PPVLand - {cat}")
        status = s["status"]

        key = f"{s['name']}::{s['category']}::{s['iframe']}"
        urls = url_map.get(key, [])

        if urls:
            for url in urls:
                lines.append(
                    f'#EXTINF:-1 tvg-id="{base_tvg}" tvg-logo="{logo}" group-title="{group}" status="{status}",{name}'
                )
                lines.extend(CUSTOM_HEADERS)
                lines.append(url)
        else:
            lines.append(
                f'#EXTINF:-1 tvg-id="{base_tvg}" tvg-logo="{logo}" group-title="{group}" status="NO_STREAM",❌ NO STREAM - {name}'
            )
            lines.extend(CUSTOM_HEADERS)
            lines.append("https://example.com/stream_unavailable.m3u8")

    return "\n".join(lines)


# --- Merge playlist ---
def merge_with_existing(existing_file, new_lines):
    import re

    def normalize_name(line):
        name = line.split(",", 1)[-1].lower()
        name = re.sub(r"[🟢🔴❌]", "", name)
        return re.sub(r"[^a-z0-9 ]", " ", name).strip()

    def get_status(line):
        m = re.search(r'status="([^"]*)"', line)
        if m:
            return m.group(1).upper()
        return "UPCOMING"

    def set_status(line, status):
        if 'status="' in line:
            return re.sub(r'status="[^"]*"', f'status="{status}"', line)
        return line.replace(",", f' status="{status}",')

    def clean_tvg(line):
        return re.sub(r'tvg-id="([^"]*)"', lambda m: f'tvg-id="{clean_tvg_id(m.group(1))}"', line)

    # Load old playlist
    old = []
    if os.path.exists(existing_file):
        with open(existing_file, "r", encoding="utf-8") as f:
            old = [x.rstrip("\n") for x in f]

    today = datetime.now(PT).strftime("%Y-%m-%d")
    date_marker = f"#DATE: {today}"

    if not old or not old[0].startswith("#DATE") or today not in old[0]:
        old = []

    # Extract blocks
    def extract(lines):
        out = {}
        i = 0
        while i < len(lines):
            if lines[i].startswith("#EXTINF"):
                key = normalize_name(lines[i])
                block = [lines[i]]
                j = i + 1
                while j < len(lines) and not lines[j].startswith("#EXTINF"):
                    block.append(lines[j])
                    j += 1
                out[key] = block
                i = j
            else:
                i += 1
        return out

    old_body = [l for l in old if not l.startswith("#DATE") and not l.startswith("#EXTM3U")]
    new_body = [l for l in new_lines if not l.startswith("#DATE") and not l.startswith("#EXTM3U")]

    old_blocks = extract(old_body)
    new_blocks = extract(new_body)

    merged = dict(old_blocks)
    merged.update(new_blocks)

    # Mark disappeared as ENDED
    for key, block in list(merged.items()):
        if key not in new_blocks:
            status = get_status(block[0])
            if status != "ENDED":
                line = set_status(block[0], "ENDED")
                line = re.sub(r'group-title="[^"]*"', 'group-title="Ended Games"', line)
                block[0] = line
                merged[key] = block

    # Sort live → upcoming → ended
    def sort_key(block):
        st = get_status(block[0])
        name = normalize_name(block[0])
        if st == "LIVE":
            return (0, name)
        elif st == "ENDED":
            return (2, name)
        return (1, name)

    sorted_blocks = sorted(merged.values(), key=sort_key)

    final = [
        '#EXTM3U url-tvg="https://epgshare01.online/epgshare01/epg_ripper_DUMMY_CHANNELS.xml.gz"',
        date_marker
    ]

    for block in sorted_blocks:
        block[0] = clean_tvg(block[0])
        final.extend(block)

    return final


# --- Main ---
async def main():
    print("🚀 Starting PPV scraper")

    data = await get_streams()
    if not data or "streams" not in data:
        print("❌ API returned no data.")
        return

    now = datetime.now(PT)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_tomorrow = start_of_today + timedelta(days=2)

    start_ts = int(start_of_today.timestamp())
    end_ts = int(end_of_tomorrow.timestamp())
    now_ts = int(now.timestamp())

    today_streams = []

    for category in data["streams"]:
        raw_cat = category.get("category", "Misc")
        if "24/7" in raw_cat:
            continue

        for s in category.get("streams", []):
            starts = s.get("starts_at")
            if not starts:
                continue

            starts = int(starts)
            ends = int(s.get("ends_at", starts + 4 * 3600))

            if not (start_ts <= starts < end_ts):
                continue

            name = s.get("name", "Unnamed Event")
            cat = raw_cat

            if cat.lower() == "basketball":
                cat = detect_basketball_type(name)
            if cat.lower() == "american football" and "college" in name.lower():
                cat = "College Football"

            timestamp = format_timestamp(starts)
            if timestamp:
                name += f" ({timestamp})"

            tag = s.get("tag")
            if tag:
                name += f" [{tag}]"

            is_live = starts <= now_ts < ends
            is_ended = ends <= now_ts
            status = "LIVE" if is_live else ("ENDED" if is_ended else "UPCOMING")

            today_streams.append({
                "name": name,
                "iframe": s["iframe"],
                "category": cat,
                "poster": s.get("poster"),
                "status": status,
                "starts_at": starts,
                "ends_at": ends,
                "is_live": is_live,
                "is_ended": is_ended,
            })

    today_streams.sort(
        key=lambda x: (
            0 if x["is_live"] else (2 if x["is_ended"] else 1),
            x["starts_at"],
        )
    )

    print(f"✅ Found {len(today_streams)} events for {now.strftime('%b %d, %Y %Z')}")

    async with async_playwright() as pw:
        browser = await pw.firefox.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        url_map = {}
        total = len(today_streams)

        for i, s in enumerate(today_streams, 1):
            key = f"{s['name']}::{s['category']}::{s['iframe']}"
            print(f"🔎 [{i}/{total}] Checking stream: {s['name']}")
            urls = await grab_m3u8_from_iframe(page, s["iframe"])
            url_map[key] = urls

        await browser.close()

    new_playlist = build_m3u(today_streams, url_map).splitlines()
    merged = merge_with_existing("SportsWebcast.m3u8", new_playlist)

    with open("SportsWebcast.m3u8", "w", encoding="utf-8") as f:
        f.write("\n".join(merged))

    print(f"✅ Playlist updated at {datetime.now(PT).strftime('%I:%M %p %Z')}")


if __name__ == "__main__":
    asyncio.run(main())
