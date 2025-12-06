// ---------------------------------------------------------
//  PPV Scraper - JS (ESM) - No Playwright
//  Uses puppeteer-extra + stealth to bypass Cloudflare
//  Writes & merges SportsWebcast2.m3u8
// ---------------------------------------------------------

import fs from "fs";
import moment from "moment-timezone";
import puppeteer from "puppeteer-extra";
import StealthPlugin from "puppeteer-extra-plugin-stealth";

// Enable stealth mode to bypass Cloudflare
puppeteer.use(StealthPlugin());

const API_URL = "https://old.ppv.to/api/streams";

const CUSTOM_HEADERS = [
  "#EXTVLCOPT:http-origin=https://ppv.to",
  "#EXTVLCOPT:http-referrer=https://ppv.to/",
  "#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:143.0) Gecko/20100101 Firefox/143.0"
];

const CATEGORY_LOGOS = {
  Wrestling: "http://drewlive24.duckdns.org:9000/Logos/Wrestling.png",
  Football: "http://drewlive24.duckdns.org:9000/Logos/Football.png",
  Basketball: "http://drewlive24.duckdns.org:9000/Logos/NCAA.png",
  Baseball: "http://drewlive24.duckdns.org:9000/Logos/Baseball.png",
  "American Football": "http://drewlive24.duckdns.org:9000/Logos/NFL3.png",
  "Combat Sports": "http://drewlive24.duckdns.org:9000/Logos/CombatSports2.png",
  Darts: "http://drewlive24.duckdns.org:9000/Logos/Darts.png",
  Motorsports: "http://drewlive24.duckdns.org:9000/Logos/Motorsports2.png",
  "Ice Hockey": "http://drewlive24.duckdns.org:9000/Logos/Hockey.png",
  NBA: "http://drewlive24.duckdns.org:9000/Logos/NBA.png",
  NCAA: "http://drewlive24.duckdns.org:9000/Logos/NCAA.png",
  Cricket: "https://i.imgur.com/rA9TeSu.png"
};

const CATEGORY_TVG_IDS = {
  Wrestling: "PPV.EVENTS.Dummy.us",
  Football: "Soccer.Dummy.us",
  Basketball: "NCAA.Basketball.Dummy.us",
  NBA: "NBA.Basketball.Dummy.us",
  NCAA: "NCAA.Basketball.Dummy.us",
  Baseball: "MLB.Baseball.Dummy.us",
  "American Football": "NFL.Dummy.us",
  "College Football": "NCAA.Football.Dummy.us",
  "Combat Sports": "PPV.EVENTS.Dummy.us",
  Darts: "Darts.Dummy.us",
  Motorsports: "Racing.Dummy.us",
  "Ice Hockey": "NHL.Hockey.Dummy.us",
  Cricket: "Cricket.Dummy.us"
};

const GROUP_RENAME_MAP = {
  Wrestling: "Wrestling Events",
  Football: "Global Football Streams",
  Basketball: "NCAA College Basketball",
  NBA: "NBA Games",
  NCAA: "NCAA College Basketball",
  Baseball: "MLB",
  "American Football": "NFL Action",
  "College Football": "NCAA College Football",
  "Combat Sports": "Combat Sports",
  Darts: "Darts",
  Motorsports: "Racing Action",
  "Ice Hockey": "NHL Action",
  Cricket: "Cricket Games"
};

const NBA_TEAMS = [
  "hawks", "celtics", "nets", "hornets", "bulls", "cavaliers", "mavericks",
  "nuggets", "pistons", "warriors", "rockets", "pacers", "clippers", "lakers",
  "grizzlies", "heat", "bucks", "timberwolves", "pelicans", "knicks", "thunder",
  "magic", "sixers", "suns", "blazers", "kings", "spurs", "raptors", "jazz",
  "wizards"
];

const NCAA_KEYWORDS = [
  "wildcats", "falcons", "zips", "crimson tide", "bulldogs", "hornets",
  "great danes", "braves", "eagles", "mountaineers", "sun devils",
  "razorbacks", "golden lions", "red wolves", "black knights", "tigers",
  "governors", "cardinals", "bears", "bruins", "cougars", "bearcats",
  "broncos", "terriers", "bison", "bulls", "dawgs", "lions", "huskies",
  "matadors", "titans", "gauchos", "golden bears", "camels",
  "golden griffins", "mocs", "panthers", "spiders", "rams", "buffaloes",
  "bluejays", "big green", "flyers", "blue hens", "pioneers", "blue demons",
  "dukes", "pirates", "bucs", "vikings", "raiders", "red raiders", "gators",
  "seminoles", "paladins", "patriots", "colonials", "hoyas", "yellow jackets",
  "lopes", "crimson", "warriors", "phoenix", "crusaders", "vandals",
  "bengals", "fighting illini", "redbirds", "flames", "hoosiers",
  "sycamores", "gaels", "hawkeyes", "cyclones", "mastodons", "jaguars",
  "dolphins", "gamecocks", "jayhawks", "owls", "golden flashes",
  "explorers", "leopards", "mountain hawks", "bisons", "trojans",
  "ragin cajuns", "warhawks", "greyhounds", "black bears", "jaspers",
  "red foxes", "thundering herd", "terps", "hawks", "minutemen",
  "river hawks", "cowboys", "musketeers", "penguins"
];

// ---------- Utilities ----------

function formatTimestamp(ts) {
  try {
    return (
      moment.unix(Number(ts)).tz("Asia/Manila").format("MMM DD @ hh:mm A") +
      " PHT"
    );
  } catch (e) {
    console.error("❌ Time format error:", e);
    return null;
  }
}

function detectBasketballType(name) {
  const lower = name.toLowerCase();
  if (NBA_TEAMS.some((t) => lower.includes(t))) return "NBA";
  if (NCAA_KEYWORDS.some((k) => lower.includes(k))) return "NCAA";
  return "Basketball";
}

function fixM3u8(url) {
  if (url.endsWith("index.m3u8")) {
    return url.replace("index.m3u8", "tracks-v1a1/mono.ts.m3u8");
  }
  return url;
}

// ---------- Network ----------

async function getStreams() {
  try {
    const res = await fetch(API_URL, {
      headers: { "User-Agent": "Mozilla/5.0" }
    });

    if (!res.ok) {
      console.error("❌ API request failed:", res.status);
      return null;
    }
    return await res.json();
  } catch (e) {
    console.error("❌ Error fetching API:", e);
    return null;
  }
}

// ---------- Puppeteer Helper ----------

async function grabM3u8FromIframe(browser, iframeUrl) {
  const page = await browser.newPage();
  const foundStreams = new Set();

  page.on("response", (response) => {
    const url = response.url();
    if (url.includes(".m3u8")) {
      foundStreams.add(url);
    }
  });

  try {
    await page.goto(iframeUrl, {
      timeout: 25000,
      waitUntil: "domcontentloaded"
    });
  } catch (e) {
    await page.close();
    return new Set();
  }

  await page.waitForTimeout(6000);
  await page.close();

  let filtered = [...foundStreams].filter(
    (url) =>
      url.endsWith("index.m3u8") || url.includes("/tracks-v1a1/mono.ts.m3u8")
  );
  if (!filtered.length) {
    filtered = [...foundStreams];
  }

  const finalUrls = new Set();
  for (const u of filtered) {
    finalUrls.add(fixM3u8(u));
  }
  return finalUrls;
}

// ---------- Build Playlist ----------

function buildM3u(streams, urlMap) {
  const lines = [
    '#EXTM3U url-tvg="https://epgshare01.online/epgshare01/epg_ripper_DUMMY_CHANNELS.xml.gz"'
  ];
  const seen = new Set();

  for (const s of streams) {
    const name = s.name.trim();
    if (seen.has(name.toLowerCase())) continue;
    seen.add(name.toLowerCase());

    let cat = s.category || "Misc";
    if (cat === "Basketball") cat = detectBasketballType(name);

    const key = `${s.name}::${s.category}::${s.iframe}`;
    const urls = urlMap.get(key) || new Set();
    const group = GROUP_RENAME_MAP[cat] || `PPVLand - ${cat}`;
    const logo = s.poster || CATEGORY_LOGOS[cat] || "";
    const baseTvg = CATEGORY_TVG_IDS[cat] || "Misc.Dummy.us";
    const status = s.status || "UPCOMING"; // LIVE / ENDED / UPCOMING
    const tvg = `${baseTvg}|${status}`;

    if (urls.size > 0) {
      for (const url of urls) {
        const fixedUrl = fixM3u8(url);
        lines.push(
          `#EXTINF:-1 tvg-id="${tvg}" tvg-logo="${logo}" group-title="${group}",${name}`
        );
        lines.push(...CUSTOM_HEADERS);
        lines.push(fixedUrl);
      }
    } else {
      lines.push(
        `#EXTINF:-1 tvg-id="${baseTvg}|NO_STREAM" tvg-logo="${logo}" group-title="${group}",❌ NO STREAM - ${name}`
      );
      lines.push(...CUSTOM_HEADERS);
      lines.push("https://example.com/stream_unavailable.m3u8");
    }
  }

  return lines.join("\n");
}

// ---------- Merge with Existing ----------

function mergeWithExisting(existingFile, newPlaylistLines) {
  const today = moment().tz("Asia/Manila").format("YYYY-MM-DD");
  const dateMarker = `#DATE: ${today}`;

  let oldLines = [];
  if (fs.existsSync(existingFile)) {
    oldLines = fs.readFileSync(existingFile, "utf-8").split(/\r?\n/);
  }

  // If file is missing or date mismatch → reset
  if (oldLines.length < 2 || !oldLines[1].startsWith("#DATE") || !oldLines[1].includes(today)) {
    console.log("🕛 New day detected — starting fresh playlist.");
    oldLines = [];
  }

  function normalizeName(line) {
    // grab everything after the comma
    const parts = line.split(",", 1);
    const namePart = line.split(",", 2)[1] || "";
    let name = namePart.toLowerCase();

    // remove emojis / prefixes
    name = name.replace(/[🟢🔴❌]/g, "");
    name = name.replace(/(^live\s*-\s*)|(^ended\s*-\s*)/g, "");
    name = name.replace(/\(.*?\)/g, "");
    name = name.replace(/\[.*?\]/g, "");
    name = name.replace(/[^a-z0-9\s]/g, " ");
    name = name.replace(/\s+/g, " ").trim();
    return name;
  }

  function getStatusFromLine(line) {
    const lower = line.toLowerCase();

    // Legacy emoji
    if (lower.includes("🟢 live")) return "LIVE";
    if (lower.includes("🔴 ended")) return "ENDED";

    // New tvg-id form
    const match = line.match(/tvg-id="([^"]*)"/);
    if (match) {
      const val = match[1];
      const parts = val.split("|");
      if (parts.length > 1) {
        const status = parts[parts.length - 1].toUpperCase();
        if (["LIVE", "ENDED", "UPCOMING", "NO_STREAM"].includes(status)) {
          return status;
        }
      }
    }
    return "UPCOMING";
  }

  function setStatusInLine(line, newStatus) {
    const match = line.match(/tvg-id="([^"]*)"/);
    if (!match) return line;
    const fullVal = match[1];
    const base = fullVal.split("|")[0] || fullVal;
    const newVal = `${base}|${newStatus.toUpperCase()}`;
    return line.replace(/tvg-id="([^"]*)"/, `tvg-id="${newVal}"`);
  }

  function extractBlocks(lines) {
    const blocks = {};
    let i = 0;
    while (i < lines.length) {
      const line = lines[i];
      if (line.startsWith("#EXTINF")) {
        const key = normalizeName(line);
        const block = [line];
        let j = i + 1;
        while (j < lines.length && !lines[j].startsWith("#EXTINF")) {
          block.push(lines[j]);
          j++;
        }
        blocks[key] = block;
        i = j;
      } else {
        i++;
      }
    }
    return blocks;
  }

  // Remove headers/date from both sets
  const oldBodyLines = oldLines.filter(
    (l) => !l.startsWith("#EXTM3U") && !l.startsWith("#DATE")
  );
  const newBodyLines = newPlaylistLines.filter(
    (l) => !l.startsWith("#EXTM3U") && !l.startsWith("#DATE")
  );

  const oldBlocks = extractBlocks(oldBodyLines);
  const newBlocks = extractBlocks(newBodyLines);

  const merged = { ...oldBlocks };

  // Step 2 — update/add from new API data
  for (const [key, block] of Object.entries(newBlocks)) {
    merged[key] = block;
  }

  // Step 3 — mark disappeared games as ENDED and move group
  for (const [key, block] of Object.entries(merged)) {
    if (!(key in newBlocks)) {
      const firstLine = block[0];
      const status = getStatusFromLine(firstLine);
      if (status !== "ENDED") {
        let endedLine = setStatusInLine(firstLine, "ENDED");
        endedLine = endedLine.replace(
          /group-title="[^"]*"/,
          'group-title="Ended Games"'
        );
        block[0] = endedLine;
        merged[key] = block;
      }
    }
  }

  // Step 4 — sort LIVE → UPCOMING → ENDED
  function sortKey(block) {
    const l0 = block[0];
    const status = getStatusFromLine(l0);
    const nameKey = normalizeName(l0);
    if (status === "LIVE") return [0, nameKey];
    if (status === "ENDED") return [2, nameKey];
    return [1, nameKey];
  }

  const sortedBlocks = Object.values(merged).sort((a, b) => {
    const [sa, na] = sortKey(a);
    const [sb, nb] = sortKey(b);
    if (sa !== sb) return sa - sb;
    return na.localeCompare(nb);
  });

  const finalLines = [
    '#EXTM3U url-tvg="https://epgshare01.online/epgshare01/epg_ripper_DUMMY_CHANNELS.xml.gz"',
    dateMarker
  ];

  for (const block of sortedBlocks) {
    finalLines.push(...block);
  }

  console.log(
    `✅ Playlist merged: ${sortedBlocks.length} total games (LIVE/upcoming/ENDED).`
  );
  return finalLines;
}

// ---------- Main ----------

async function main() {
  console.log("🚀 Starting PPV scraper (JS)");

  const data = await getStreams();
  if (!data || !data.streams) {
    console.error("❌ No valid data from API.");
    return;
  }

  const philTz = "Asia/Manila";
  const localNow = moment().tz(philTz);

  const startOfToday = localNow.clone().startOf("day");
  const endOfTomorrow = startOfToday.clone().add(2, "days");

  const startTs = startOfToday.unix();
  const endTs = endOfTomorrow.unix();
  const nowTs = localNow.unix();

  const todayStreams = [];

  for (const category of data.streams) {
    const rawCat = (category.category || "Misc").trim();
    if (rawCat.includes("24/7")) continue;

    for (const s of category.streams || []) {
      let startsAt = s.starts_at;
      if (!startsAt) continue;

      startsAt = Number(startsAt);
      let endsAt = Number(s.ends_at || startsAt + 4 * 3600);

      if (!(startTs <= startsAt && startsAt < endTs)) continue;

      let name = (s.name || "Unnamed Event").trim();
      let catName = rawCat;

      if (rawCat.toLowerCase() === "basketball") {
        catName = detectBasketballType(name);
      }
      if (
        rawCat.toLowerCase() === "american football" &&
        name.toLowerCase().includes("college")
      ) {
        catName = "College Football";
      }

      const iframe = s.iframe;
      const poster = s.poster;
      const tag = s.tag;

      const dateStr = formatTimestamp(startsAt);
      if (dateStr) name += ` (${dateStr})`;
      if (tag) name += ` [${tag}]`;

      const isLive = startsAt <= nowTs && nowTs < endsAt;
      const isEnded = endsAt <= nowTs;
      const status = isLive ? "LIVE" : isEnded ? "ENDED" : "UPCOMING";

      todayStreams.push({
        name,
        iframe,
        category: catName,
        poster,
        starts_at: startsAt,
        ends_at: endsAt,
        is_live: isLive,
        is_ended: isEnded,
        status
      });
    }
  }

  // sort by LIVE → UPCOMING → ENDED, then by start time
  todayStreams.sort((a, b) => {
    const statusOrder = (x) =>
      x.is_live ? 0 : x.is_ended ? 2 : 1;
    const sa = statusOrder(a);
    const sb = statusOrder(b);
    if (sa !== sb) return sa - sb;
    return (a.starts_at || 0) - (b.starts_at || 0);
  });

  console.log(
    `✅ Found ${todayStreams.length} live/scheduled/ended games for ${localNow.format(
      "MMM DD, YYYY"
    )} PHT`
  );

  const browser = await puppeteer.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"]
  });

  const urlMap = new Map();
  const total = todayStreams.length;

  let idx = 1;
  for (const s of todayStreams) {
    const key = `${s.name}::${s.category}::${s.iframe}`;
    console.log(`🔎 [${idx++}/${total}] Checking: ${s.name}`);
    if (!s.iframe) {
      urlMap.set(key, new Set());
      continue;
    }
    const urls = await grabM3u8FromIframe(browser, s.iframe);
    urlMap.set(key, urls);
  }

  await browser.close();

  const newPlaylistStr = buildM3u(todayStreams, urlMap);
  const newPlaylistLines = newPlaylistStr.split(/\r?\n/);

  const mergedPlaylistLines = mergeWithExisting(
    "SportsWebcast2.m3u8",
    newPlaylistLines
  );

  fs.writeFileSync("SportsWebcast2.m3u8", mergedPlaylistLines.join("\n"), {
    encoding: "utf-8"
  });

  console.log(
    `✅ Updated SportsWebcast2.m3u8 (${todayStreams.length} streams) at ${localNow.format(
      "hh:mm A z"
    )}`
  );
}

if (import.meta.url === `file://${process.argv[1]}`) {
  // executed directly
  main().catch((err) => {
    console.error("❌ Fatal error:", err);
    process.exit(1);
  });
}
