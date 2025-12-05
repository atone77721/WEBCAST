import asyncio
from playwright.async_api import async_playwright
import aiohttp
from datetime import datetime, timezone, timedelta
import pytz
import os

API_URL = "https://ppv.to/api/streams"

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
    "hawks", "celtics", "nets", "hornets", "bulls", "cavaliers", "mavericks", "nuggets",
    "pistons", "warriors", "rockets", "pacers", "clippers", "lakers", "grizzlies",
    "heat", "bucks", "timberwolves", "pelicans", "knicks", "thunder", "magic", "sixers",
    "suns", "blazers", "kings", "spurs", "raptors", "jazz", "wizards"
]

NCAA_KEYWORDS = [
    "wildcats", "falcons", "zips", "crimson tide", "bulldogs", "hornets", "great danes",
    "braves", "eagles", "mountaineers", "wildcats", "sun devils", "razorbacks",
    "golden lions", "red wolves", "black knights", "tigers", "governors",
    "cardinals", "bears", "bruins", "wildcats", "cougars", "bearcats",
    "broncos", "eagles", "terriers", "falcons", "braves", "cougars",
    "bears", "bison", "bulls", "dawgs", "lions", "huskies", "matadors",
    "titans", "gauchos", "golden bears", "camels", "golden griffins",
    "mocs", "panthers", "spiders", "tigers", "tigers", "rams",
    "buffaloes", "rams", "lions", "huskies", "eagles", "big red",
    "bluejays", "big green", "wildcats", "flyers", "blue hens",
    "hornets", "pioneers", "blue demons", "titans", "bulldogs",
    "dragons", "blue devils", "dukes", "pirates", "bucs",
    "panthers", "eagles", "vikings", "lions", "raiders",
    "red raiders", "gators", "seminoles", "rams", "bulldogs",
    "paladins", "runnin bulldogs", "patriots", "colonials",
    "hoyas", "bulldogs", "eagles", "panthers", "yellow jackets",
    "bulldogs", "lopes", "pirates", "crimson", "warriors",
    "panthers", "phoenix", "crusaders", "cougars", "bison",
    "vandals", "bengals", "fighting illini", "redbirds",
    "flames", "cardinals", "hoosiers", "sycamores",
    "gaels", "hawkeyes", "cyclones", "mastodons",
    "jaguars", "tigers", "dolphins", "gamecocks",
    "dukes", "jayhawks", "wildcats", "owls",
    "golden flashes", "wildcats", "explorers",
    "leopards", "cardinals", "mountain hawks",
    "flames", "bisons", "trojans", "beach", "sharks",
    "lancers", "ragin cajuns", "warhawks",
    "bulldogs", "cardinals", "cardinals",
    "tigers", "ramblers", "greyhounds", "lions",
    "tigers", "black bears", "jaspers", "red foxes",
    "thundering herd", "terps", "hawks", "minutemen",
    "river hawks", "cowboys", "tigers", "bears",
    "hurricanes", "redhawks", "wolverines",
    "spartans", "raiders", "panthers", "golden gophers",
    "rebels", "bulldogs", "tigers", "kangaroos",
    "bears", "hawks", "grizzlies", "bobcats",
    "bobcats", "lions", "mountaineers", "huskies",
    "tigers", "blue knights", "grizzlies",
    "tigers", "mountaineers", "brown bears",
    "cardinals", "jackrabbits", "mavericks", "lancers",
    "rams", "panthers", "spiders", "broncs",
    "vaqueros", "colonials", "scarlet knights",
    "hornets", "pioneers", "billikens", "gaels",
    "peacocks", "bearkats", "bulldogs", "toreros",
    "aztecs", "dons", "spartans", "tigers",
    "redhawks", "pirates", "saints", "siue cougars",
    "mustangs", "jaguars", "gamecocks", "cocks",
    "coyotes", "jackrabbits", "bulls", "redhawks",
    "lions", "trojans", "screaming eagles", "trojans",
    "eagles", "knights", "crusaders", "trojans",
    "seahawks", "mercer bears", "blue hoses", "tigers",
    "hoos", "rams", "owls", "spiders", "broncs",
    "highlanders", "highlanders", "spiders",
    "hornets", "tillicums", "cavaliers", "hokies",
    "keydets", "rams", "seahawks", "demon deacons",
    "huskies", "cougars", "wildcats", "dutchmen",
    "mountaineers", "hilltoppers", "broncos",
    "shockers", "tribe", "eagles", "badgers",
    "terriers", "raiders", "cowboys", "musketeers",
    "bulldogs", "penguins"
]


# ------- UTILITIES --------

def format_timestamp(ts):
    try:
        pac_tz = pytz.timezone('America/Los_Angeles')
        dt = datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone(pac_tz)
        return dt.strftime("%b %d @ %I:%M %p") + " PT"
    except Exception as e:
        print(f"❌ Time format error: {e}")
        return None


def detect_basketball_type(name: str):
    name_lower = name.lower()
    if any(team in name_lower for team in NBA_TEAMS):
        return "NBA"
    if any(keyword in name_lower for keyword in NCAA_KEYWORDS):
        return "NCAA"
    return "Basketball"


def fix_m3u8(url: str) -> str:
    if url.endswith("index.m3u8"):
        return url.replace("index.m3u8", "tracks-v1a1/mono.ts.m3u8")
    return url


# ------- NETWORK --------

async def get_streams():
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        headers = {'User-Agent': 'Mozilla/5.0'}
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(API_URL) as resp:
                if resp.status != 200:
                    print(f"❌ API request failed: {resp.status}")
                    return None
                return await resp.json()
    except Exception as e:
        print(f"❌ Error fetching API: {e}")
        return None


# ------- PLAYWRIGHT --------

async def grab_m3u8_from_iframe(page, iframe_url):
    found_streams = set()

    def handle_response(response):
        if ".m3u8" in response.url:
            found_streams.add(response.url)

    page.on("response", handle_response)
    try:
        await page.goto(iframe_url, timeout=25000, wait_until="domcontentloaded")
    except Exception:
        return set()

    await asyncio.sleep(6)
    page.remove_listener("response", handle_response)

    filtered = [url for url in found_streams
                if url.endswith("index.m3u8") or "/tracks-v1a1/mono.ts.m3u8" in url]
    if not filtered:
        filtered = list(found_streams)

    final_urls = set()
    for u in filtered:
        final_urls.add(fix_m3u8(u))

    return final_urls


# ------- M3U BUILDER --------

def build_m3u(streams, url_map):
    lines = ['#EXTM3U url-tvg="https://epgshare01.online/epgshare01/epg_ripper_DUMMY_CHANNELS.xml.gz"']
    seen = set()

    for s in streams:
        name = s["name"].strip()
        if name.lower() in seen:
            continue
        seen.add(name.lower())

        cat = s.get("category") or "Misc"
        if cat == "Basketball":
            cat = detect_basketball_type(name)

        urls = url_map.get(f"{s['name']}::{s['category']}::{s['iframe']}", [])
        group = GROUP_RENAME_MAP.get(cat, f"PPVLand - {cat}")
        logo = s.get("poster") or CATEGORY_LOGOS.get(cat, "")
        base_tvg = CATEGORY_TVG_IDS.get(cat, "Misc.Dummy.us")

        status = s.get("status", "UPCOMING")
        tvg = f"{base_tvg}|{status}"

        if urls:
            for url in urls:
                fixed_url = fix_m3u8(url)
                lines.append(f'#EXTINF:-1 tvg-id="{tvg}" tvg-logo="{logo}" group-title="{group}",{name}')
                lines.extend(CUSTOM_HEADERS)
                lines.append(fixed_url)
        else:
            lines.append(f'#EXTINF:-1 tvg-id="{base_tvg}|NO_STREAM" tvg-logo="{logo}" group-title="{group}",❌ NO STREAM - {name}')
            lines.extend(CUSTOM_HEADERS)
            lines.append("https://example.com/stream_unavailable.m3u8")

    return "\n".join(lines)


# ------- MERGE WITH EXISTING --------

def merge_with_existing(existing_file, new_playlist_lines):
    import re
    import pytz
    from datetime import datetime

    def normalize_name(line):
        name = line.split(",", 1)[-1].lower()
        name = re.sub(r"[🟢🔴❌]|(^live\s*-\s*)|(^ended\s*-\s*)", "", name)
        name = re.sub(r"\(.*?\)", "", name)
        name = re.sub(r"\[.*?\]", "", name)
        name = re.sub(r"[^a-z0-9\s]", " ", name)
        name = re.sub(r"\s+", " ", name).strip()
        return name

    def today_pt():
        tz = pytz.timezone("America/Los_Angeles")
        return datetime.now(tz).strftime("%Y-%m-%d")

    def get_status_from_line(line: str) -> str:
        l = line.lower()
        if "🟢 live" in l:
            return "LIVE"
        if "🔴 ended" in l:
            return "ENDED"

        m = re.search(r'tvg-id="([^"]*)"', line)
        if m:
            val = m.group(1)
            parts = val.split("|")
            if len(parts) > 1:
                status = parts[-1].upper()
                if status in ("LIVE", "ENDED", "UPCOMING", "NO_STREAM"):
                    return status

        return "UPCOMING"

    def set_status_in_line(line: str, new_status: str) -> str:
        new_status = new_status.upper()
        m = re.search(r'tvg-id="([^"]*)"', line)
        if not m:
            return line

        full_val = m.group(1)
        parts = full_val.split("|")
        base = parts[0] if parts else full_val
        new_val = f'{base}|{new_status}'
        return line[:m.start(1)] + new_val + line[m.end(1):]

    today = today_pt()
    date_marker = f"#DATE: {today}"

    old_lines = []
    if os.path.exists(existing_file):
        with open(existing_file, "r", encoding="utf-8") as f:
            old_lines = [l.rstrip("\n") for l in f]

    if not old_lines or not old_lines[0].startswith("#DATE") or today not in old_lines[0]:
        print("🕛 New day detected — starting fresh playlist.")
        old_lines = []

    def extract_blocks(lines):
        blocks = {}
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("#EXTINF"):
                key = normalize_name(line)
                block = [line]
                j = i + 1
                while j < len(lines) and not lines[j].startswith("#EXTINF"):
                    block.append(lines[j])
                    j += 1
                blocks[key] = block
                i = j
            else:
                i += 1
        return blocks

    old_body_lines = [l for l in old_lines if not l.startswith("#EXTM3U") and not l.startswith("#DATE")]
    new_body_lines = [l for l in new_playlist_lines if not l.startswith("#EXTM3U") and not l.startswith("#DATE")]

    old_blocks = extract_blocks(old_body_lines)
    new_blocks = extract_blocks(new_body_lines)

    merged = {}

    for key, block in old_blocks.items():
        merged[key] = block

    for key, block in new_blocks.items():
        merged[key] = block

    for key, block in list(merged.items()):
        if key not in new_blocks:
            line = block[0]
            status = get_status_from_line(line)
            if status != "ENDED":
                ended_line = set_status_in_line(line, "ENDED")
                ended_line = re.sub(r'group-title="[^"]*"', 'group-title="Ended Games"', ended_line)
                block[0] = ended_line
                merged[key] = block

    def sort_key(block):
        l0 = block[0]
        status = get_status_from_line(l0)
        name_key = normalize_name(l0)
        if status == "LIVE":
            return (0, name_key)
        elif status == "ENDED":
            return (2, name_key)
        else:
            return (1, name_key)

    sorted_blocks = sorted(merged.values(), key=sort_key)

    final_lines = [
        '#EXTM3U url-tvg="https://epgshare01.online/epgshare01/epg_ripper_DUMMY_CHANNELS.xml.gz"',
        date_marker,
    ]
    for block in sorted_blocks:
        final_lines.extend(block)

    print(f"✅ Playlist merged: {len(sorted_blocks)} total games (LIVE/upcoming/ENDED).")
    return final_lines


# ------- MAIN --------

async def main():
    print("🚀 Starting PPV scraper")
    data = await get_streams()
    if not data or "streams" not in data:
        print("❌ No valid data from API.")
        return

    pac_tz = pytz.timezone('America/Los_Angeles')
    local_now = datetime.now(pac_tz)

    start_of_today = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_tomorrow = start_of_today + timedelta(days=2)

    start_ts = int(start_of_today.timestamp())
    end_ts = int(end_of_tomorrow.timestamp())
    now_ts = int(local_now.timestamp())

    today_streams = []

    for category in data["streams"]:
        raw_cat = category.get("category", "Misc").strip()
        if "24/7" in raw_cat:
            continue

        for s in category.get("streams", []):
            starts_at = s.get("starts_at")
            if not starts_at:
                continue

            starts_at = int(starts_at)
            ends_at = int(s.get("ends_at", starts_at + 4 * 3600))

            if start_ts <= starts_at < end_ts:
                name = s.get("name", "Unnamed Event").strip()
                cat_name = raw_cat

                if raw_cat.lower() == "basketball":
                    cat_name = detect_basketball_type(name)
                if raw_cat.lower() == "american football" and "college" in name.lower():
                    cat_name = "College Football"

                iframe = s.get("iframe")
                poster = s.get("poster")
                tag = s.get("tag")

                date_str = format_timestamp(starts_at)
                if date_str:
                    name += f" ({date_str})"
                if tag:
                    name += f" [{tag}]"

                is_live = starts_at <= now_ts < ends_at
                is_ended = ends_at <= now_ts

                status = "LIVE" if is_live else ("ENDED" if is_ended else "UPCOMING")

                today_streams.append({
                    "name": name,
                    "iframe": iframe,
                    "category": cat_name,
                    "poster": poster,
                    "starts_at": starts_at,
                    "ends_at": ends_at,
                    "is_live": is_live,
                    "is_ended": is_ended,
                    "status": status,
                })

    today_streams.sort(
        key=lambda x: (
            0 if x["is_live"] else (2 if x["is_ended"] else 1),
            x.get("starts_at", 0)
        )
    )

    print(f"✅ Found {len(today_streams)} live/scheduled/ended games for {local_now.strftime('%b %d, %Y')} PT")

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        url_map = {}
        total = len(today_streams)
        for idx, s in enumerate(today_streams, start=1):
            key = f"{s['name']}::{s['category']}::{s['iframe']}"
            print(f"🔎 [{idx}/{total}] Checking: {s['name']}")
            urls = await grab_m3u8_from_iframe(page, s["iframe"])
            url_map[key] = urls

        await browser.close()

    new_playlist = build_m3u(today_streams, url_map).splitlines()
    merged_playlist = merge_with_existing("SportsWebcastPT.m3u8", new_playlist)

    with open("SportsWebcastPT.m3u8", "w", encoding="utf-8") as f:
        f.write("\n".join(merged_playlist))

    print(f"✅ Updated SportsWebcastPT.m3u8 ({len(today_streams)} streams) at {datetime.now(pac_tz).strftime('%I:%M %p %Z')}")


if __name__ == "__main__":
    asyncio.run(main())
