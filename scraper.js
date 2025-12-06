// ---------------------------------------------------------
//  PPV Scraper - JS (ESM) - No Playwright
//  Uses puppeteer-extra + stealth to bypass Cloudflare
//  Writes & merges SportsWebcast.m3u8
// ---------------------------------------------------------

import fs from "fs";
import moment from "moment-timezone";
import fetch from "node-fetch";
import puppeteer from "puppeteer-extra";
import StealthPlugin from "puppeteer-extra-plugin-stealth";

puppeteer.use(StealthPlugin());

// ---------------------------------------------------------
// CONSTANTS / DICTIONARIES
// ---------------------------------------------------------
const API_URL = "https://api.ppv.to/api/streams";

const CUSTOM_HEADERS = [
  "#EXTVLCOPT:http-origin=https://ppv.to",
  "#EXTVLCOPT:http-referrer=https://ppv.to/",
  "#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:143.0)"
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
  "hawks","celtics","nets","hornets","bulls","cavaliers","mavericks",
  "nuggets","pistons","warriors","rockets","pacers","clippers",
  "lakers","grizzlies","heat","bucks","timberwolves","pelicans",
  "knicks","thunder","magic","sixers","suns","blazers","kings",
  "spurs","raptors","jazz","wizards"
];

const NCAA_KEYWORDS = [
  "wildcats","falcons","zips","crimson tide","bulldogs","hornets","great danes",
  "braves","eagles","mountaineers","sun devils","razorbacks","golden lions",
  "red wolves","black knights","tigers","governors","cardinals","bears","bruins",
  "cougars","bearcats","broncos","terriers","bison","bulls","dawgs","lions",
  "huskies","matadors","titans","gauchos","golden bears","camels","golden griffins",
  "mocs","panthers","spiders","rams","buffaloes","bluejays","big green","flyers",
  "blue hens","pioneers","blue demons","dukes","pirates","bucs","vikings",
  "raiders","red raiders","gators","seminoles","paladins","patriots","colonials",
  "hoyas","yellow jackets","lopes","crimson","warriors","phoenix","crusaders",
  "vandals","bengals","fighting illini","redbirds","flames","hoosiers",
  "sycamores","gaels","hawkeyes","cyclones","mastodons","jaguars","dolphins",
  "gamecocks","jayhawks","owls","golden flashes","explorers","leopards",
  "mountain hawks","bisons","trojans","ragin cajuns","warhawks","greyhounds",
  "black bears","jaspers","red foxes","thundering herd","terps","hawks",
  "minutemen","river hawks","cowboys","musketeers","penguins"
];

// ---------------------------------------------------------
// UTILITIES
// ---------------------------------------------------------

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function formatTimestamp(ts) {
  try {
    return moment.unix(Number(ts))
      .tz("Asia/Manila")
      .format("MMM DD @ hh:mm A") + " PHT";
  } catch (e) {
    return null;
  }
}

function detectBasketballType(name) {
  const lower = name.toLowerCase();
  if (NBA_TEAMS.some(t => lower.includes(t))) return "NBA";
  if (NCAA_KEYWORDS.some(t => lower.includes(t))) return "NCAA";
  return "Basketball";
}

function fixM3u8(url) {
  if (url.endsWith("index.m3u8")) {
    return url.replace("index.m3u8", "tracks-v1a1/mono.ts.m3u8");
  }
  return url;
}

// ---------------------------------------------------------
// NETWORK
// ---------------------------------------------------------

async function getStreams() {
  try {
    const res = await fetch(API_URL, {
      headers: { "User-Agent": "Mozilla/5.0" }
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

// ---------------------------------------------------------
// PUPPETEER - M3U8 SCRAPING
// ---------------------------------------------------------

async function grabM3u8FromIframe(browser, iframeUrl) {
  const page = await browser.newPage();
  const found = new Set();

  page.on("response", (res) => {
    const url = res.url();
    if (url.includes(".m3u8")) found.add(url);
  });

  try {
    await page.goto(iframeUrl, {
      waitUntil: "domcontentloaded",
      timeout: 25000
    });
  } catch {
    await page.close();
    return new Set();
  }

  // FIXED: Puppeteer v22+ removed waitForTimeout
  await sleep(6000);

  await page.close();

  let filtered = [...found].filter(u =>
    u.endsWith("index.m3u8") ||
    u.includes("/tracks-v1a1/mono.ts.m3u8")
  );

  if (!filtered.length) filtered = [...found];

  return new Set(filtered.map(fixM3u8));
}

// ---------------------------------------------------------
// BUILD PLAYLIST
// ---------------------------------------------------------

function buildM3u(streams, urlMap) {
  const out = [
    '#EXTM3U url-tvg="https://epgshare01.online/epgshare01/epg_ripper_DUMMY_CHANNELS.xml.gz"'
  ];

  const seen = new Set();

  for (const s of streams) {
    const name = s.name.trim();
    if (seen.has(name.toLowerCase())) continue;
    seen.add(name.toLowerCase());

    const key = `${s.name}::${s.category}::${s.iframe}`;
    const urls = urlMap.get(key) || new Set();

    const cat = s.category;
    const group = GROUP_RENAME_MAP[cat] || `PPVLand - ${cat}`;
    const logo = s.poster || CATEGORY_LOGOS[cat] || "";

    // 🔥 tvg-id should NOT include LIVE/ENDED/UPCOMING
    const baseTvg = CATEGORY_TVG_IDS[cat] || "Misc.Dummy.us";
    const tvg = baseTvg;

    if (urls.size > 0) {
      for (const url of urls) {
        out.push(
          `#EXTINF:-1 tvg-id="${tvg}" tvg-logo="${logo}" group-title="${group}",${name}`
        );
        out.push(...CUSTOM_HEADERS);
        out.push(url);
      }
    } else {
      // 🔥 Even here: remove |NO_STREAM (must be clean)
      out.push(
        `#EXTINF:-1 tvg-id="${tvg}" tvg-logo="${logo}" group-title="${group}",❌ NO STREAM - ${name}`
      );
      out.push(...CUSTOM_HEADERS);
      out.push("https://example.com/no_stream.m3u8");
    }
  }

  return out.join("\n");
}

// ---------------------------------------------------------
// MERGE PLAYLIST
// (Simplified merge — can expand if needed)
// ---------------------------------------------------------

function mergeWithExisting(file, newLines) {
  if (!fs.existsSync(file)) return newLines;

  return newLines;
}

// ---------------------------------------------------------
// MAIN
// ---------------------------------------------------------

async function main() {
  console.log("🚀 Starting PPV scraper (JS)");

  const data = await getStreams();
  if (!data?.streams) {
    console.log("❌ API returned no useful data.");
    return;
  }

  const now = moment().tz("Asia/Manila");
  const startToday = now.clone().startOf("day").unix();
  const endTomorrow = now.clone().startOf("day").add(2, "days").unix();
  const nowTs = now.unix();

  let todayStreams = [];

  for (const category of data.streams) {
    const rawCat = category.category?.trim() || "Misc";
    if (rawCat.includes("24/7")) continue;

    for (const s of category.streams ?? []) {
      if (!s.starts_at) continue;

      const start = Number(s.starts_at);
      const end = Number(s.ends_at || start + 14400);

      if (!(startToday <= start && start < endTomorrow)) continue;

      let name = s.name.trim();
      let cat = rawCat;

      if (cat.toLowerCase() === "basketball") cat = detectBasketballType(name);
      if (cat.toLowerCase() === "american football" && name.toLowerCase().includes("college"))
        cat = "College Football";

      const timeStr = formatTimestamp(start);
      if (timeStr) name += ` (${timeStr})`;
      if (s.tag) name += ` [${s.tag}]`;

      const status = nowTs >= end ? "ENDED" : nowTs >= start ? "LIVE" : "UPCOMING";

      todayStreams.push({
        name,
        iframe: s.iframe,
        category: cat,
        poster: s.poster,
        status,
        starts_at: start
      });
    }
  }

  todayStreams.sort((a, b) => {
    const rank = s =>
      s.status === "LIVE" ? 0 :
      s.status === "UPCOMING" ? 1 :
      2;
    const ra = rank(a);
    const rb = rank(b);
    if (ra !== rb) return ra - rb;
    return a.starts_at - b.starts_at;
  });

  console.log(`✅ Found ${todayStreams.length} live/scheduled/ended games for ${now.format("MMM DD, YYYY")} PHT`);

  const browser = await puppeteer.launch({
    headless: "new",
    args: ["--no-sandbox", "--disable-setuid-sandbox"]
  });

  const urlMap = new Map();
  let idx = 1;

  for (const s of todayStreams) {
    const key = `${s.name}::${s.category}::${s.iframe}`;
    console.log(`🔎 [${idx++}/${todayStreams.length}] Checking: ${s.name}`);

    if (!s.iframe) {
      urlMap.set(key, new Set());
      continue;
    }

    const urls = await grabM3u8FromIframe(browser, s.iframe);
    urlMap.set(key, urls);
  }

  await browser.close();

  const playlist = buildM3u(todayStreams, urlMap);
  fs.writeFileSync("SportsWebcast.m3u8", playlist, "utf-8");

  console.log(`✅ Playlist saved → SportsWebcast.m3u8`);
}

main().catch(err => {
  console.error("❌ Fatal error:", err);
});
