// ---------------------------------------------------------
//  PPV Scraper - JavaScript Version (NO PLAYWRIGHT)
//  Uses undetected Puppeteer to avoid Cloudflare blocks
// ---------------------------------------------------------

import fetch from "node-fetch";
import fs from "fs";
import path from "path";
import moment from "moment-timezone";
import puppeteer from "puppeteer-extra";
import StealthPlugin from "puppeteer-extra-plugin-stealth";

// enable stealth mode to bypass Cloudflare
puppeteer.use(StealthPlugin());

const API_URL = "https://old.ppv.to/api/streams";

const CUSTOM_HEADERS = [
  '#EXTVLCOPT:http-origin=https://ppv.to',
  '#EXTVLCOPT:http-referrer=https://ppv.to/',
  '#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:143.0)'
];

const CATEGORY_LOGOS = { /* same dictionary here */ };
const CATEGORY_TVG_IDS = { /* same dictionary */ };
const GROUP_RENAME_MAP = { /* same dictionary */ };

// =============== Utility Functions =====================

function formatTimestamp(ts) {
  try {
    return moment.unix(ts).tz("Asia/Manila").format("MMM DD @ hh:mm A") + " PHT";
  } catch (e) {
    return null;
  }
}

function detectBasketballType(name) {
  const lower = name.toLowerCase();
  if (NBA_TEAMS.some(t => lower.includes(t))) return "NBA";
  if (NCAA_KEYWORDS.some(k => lower.includes(k))) return "NCAA";
  return "Basketball";
}

function fixM3u8(url) {
  if (url.endsWith("index.m3u8"))
    return url.replace("index.m3u8", "tracks-v1a1/mono.ts.m3u8");
  return url;
}

// =============== Fetch API =============================

async function getStreams() {
  try {
    const res = await fetch(API_URL, {
      headers: { "User-Agent": "Mozilla/5.0" }
    });

    if (!res.ok) {
      console.log("❌ API failed", res.status);
      return null;
    }

    return await res.json();
  } catch (e) {
    console.log("❌ API error:", e);
    return null;
  }
}

// =============== Grab .m3u8 from iframe =================

async function grabM3u8FromIframe(browser, iframeURL) {
  const page = await browser.newPage();
  let found = new Set();

  page.on("response", async (resp) => {
    const url = resp.url();
    if (url.includes(".m3u8")) {
      found.add(url);
    }
  });

  try {
    await page.goto(iframeURL, { waitUntil: "domcontentloaded", timeout: 25000 });
    await page.waitForTimeout(6000);
  } catch {
    return new Set();
  }

  await page.close();

  // Filter preferred m3u8 forms
  let list = [...found].filter(u =>
    u.endsWith("index.m3u8") ||
    u.includes("tracks-v1a1/mono.ts.m3u8")
  );

  if (list.length === 0) list = [...found];

  return new Set(list.map(fixM3u8));
}

// =============== Build Playlist ========================

function buildPlaylist(streams, urlMap) {
  let out = [
    '#EXTM3U url-tvg="https://epgshare01.online/epgshare01/epg_ripper_DUMMY_CHANNELS.xml.gz"'
  ];

  const seen = new Set();

  for (const s of streams) {
    const name = s.name.trim();
    if (seen.has(name.toLowerCase())) continue;
    seen.add(name.toLowerCase());

    const cat = s.category;
    const urls = urlMap.get(`${s.name}::${s.category}::${s.iframe}`) || [];
    const group = GROUP_RENAME_MAP[cat] || `PPVLand - ${cat}`;
    const logo = s.poster || CATEGORY_LOGOS[cat] || "";
    const tvg = `${CATEGORY_TVG_IDS[cat] || "Misc.Dummy.us"}|${s.status}`;

    if (urls.size > 0) {
      for (const url of urls) {
        out.push(`#EXTINF:-1 tvg-id="${tvg}" tvg-logo="${logo}" group-title="${group}",${name}`);
        out.push(...CUSTOM_HEADERS);
        out.push(url);
      }
    } else {
      out.push(`#EXTINF:-1 tvg-id="${tvg}|NO_STREAM" tvg-logo="${logo}" group-title="${group}",❌ NO STREAM - ${name}`);
      out.push(...CUSTOM_HEADERS);
      out.push("https://example.com/stream_unavailable.m3u8");
    }
  }

  return out;
}

// =============== Merging (JS port) =====================

function mergeWithExisting(filePath, newLines) {
  if (!fs.existsSync(filePath)) return newLines;

  const oldLines = fs.readFileSync(filePath, "utf8").split("\n");
  const today = moment().tz("Asia/Manila").format("YYYY-MM-DD");

  if (!oldLines[0]?.includes(today)) {
    return [
      `#DATE: ${today}`,
      ...newLines
    ];
  }

  // JS version simplifies merging (FULL merging logic can be added here)
  return [
    `#DATE: ${today}`,
    ...newLines
  ];
}

// =============== Main ================================

async function main() {
  console.log("🚀 Starting JS PPV Scraper…");

  const data = await getStreams();
  if (!data?.streams) {
    console.log("❌ No valid API data");
    return;
  }

  const now = moment().tz("Asia/Manila");
  const startDay = now.clone().startOf("day").unix();
  const endTomorrow = now.clone().startOf("day").add(2, "days").unix();
  const nowTs = now.unix();

  let todayStreams = [];

  for (const category of data.streams) {
    const rawCat = category.category?.trim() || "Misc";
    if (rawCat.includes("24/7")) continue;

    for (const s of category.streams || []) {
      if (!s.starts_at) continue;

      const start = Number(s.starts_at);
      const end = Number(s.ends_at || start + 14400);

      if (start < startDay || start >= endTomorrow) continue;

      let name = s.name.trim();
      let cat = rawCat;

      if (rawCat.toLowerCase() === "basketball")
        cat = detectBasketballType(name);

      if (rawCat.toLowerCase() === "american football" && name.toLowerCase().includes("college"))
        cat = "College Football";

      const dateStr = formatTimestamp(start);
      if (dateStr) name += ` (${dateStr})`;
      if (s.tag) name += ` [${s.tag}]`;

      todayStreams.push({
        name,
        iframe: s.iframe,
        category: cat,
        poster: s.poster,
        starts_at: start,
        ends_at: end,
        status: nowTs >= end ? "ENDED" : (nowTs >= start ? "LIVE" : "UPCOMING")
      });
    }
  }

  console.log(`✅ Found ${todayStreams.length} streams`);

  // === Launch stealth browser ===
  const browser = await puppeteer.launch({
    headless: true,
    args: ["--no-sandbox"]
  });

  const urlMap = new Map();

  let idx = 1;
  for (const s of todayStreams) {
    console.log(`🔎 [${idx++}/${todayStreams.length}] Checking: ${s.name}`);
    const urls = await grabM3u8FromIframe(browser, s.iframe);
    urlMap.set(`${s.name}::${s.category}::${s.iframe}`, urls);
  }

  await browser.close();

  const playlistLines = buildPlaylist(todayStreams, urlMap);
  const merged = mergeWithExisting("SportsWebcast2.m3u8", playlistLines);

  fs.writeFileSync("SportsWebcast2.m3u8", merged.join("\n"));
  console.log("✅ Playlist updated!");
}

main();
