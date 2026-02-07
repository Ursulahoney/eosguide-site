/* eslint-disable no-console */
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

function safeStr(v) {
  if (v === null || v === undefined) return "";
  return String(v).trim();
}

function parseField(body, label) {
  // Matches GitHub issue form output like:
  // "### Title\nMy title\n"
  const re = new RegExp(`###\\s+${label}\\s*\\n([\\s\\S]*?)(\\n###\\s+|$)`, "i");
  const m = body.match(re);
  if (!m) return "";
  return safeStr(m[1]).replace(/\n+$/g, "");
}

function parseFeatured(body) {
  // checkbox section will include "- [x] Mark as featured" when checked
  return /- \[x\]\s+Mark as featured/i.test(body);
}

function toISODateOrEmpty(s) {
  const v = safeStr(s);
  if (!v) return "";
  // very light validation: YYYY-MM-DD
  if (!/^\d{4}-\d{2}-\d{2}$/.test(v)) return "";
  return v;
}

function isExpired(deadlineISO) {
  if (!deadlineISO) return false;
  // Compare in UTC by date string; good enough for “deadline passed”
  const today = new Date();
  const yyyy = String(today.getUTCFullYear());
  const mm = String(today.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(today.getUTCDate()).padStart(2, "0");
  const todayISO = `${yyyy}-${mm}-${dd}`;
  return deadlineISO < todayISO;
}

function makeId({ url, title, deadline }) {
  const raw = `${safeStr(url)}|${safeStr(title)}|${safeStr(deadline)}`;
  return crypto.createHash("sha1").update(raw).digest("hex").slice(0, 12);
}

function loadExisting(jsonPath) {
  if (!fs.existsSync(jsonPath)) return [];
  const raw = fs.readFileSync(jsonPath, "utf8").trim();
  if (!raw) return [];
  const parsed = JSON.parse(raw);
  if (!Array.isArray(parsed)) {
    throw new Error("data/opportunities.json must be an array.");
  }
  return parsed;
}

function writeJson(jsonPath, arr) {
  fs.mkdirSync(path.dirname(jsonPath), { recursive: true });
  fs.writeFileSync(jsonPath, JSON.stringify(arr, null, 2) + "\n", "utf8");
}

(function main() {
  const body = safeStr(process.env.ISSUE_BODY);
  if (!body) throw new Error("Missing ISSUE_BODY");

  const title = parseField(body, "Title");
  const category = parseField(body, "Category");
  const state = parseField(body, "State");
  const deadline = toISODateOrEmpty(parseField(body, "Deadline (YYYY-MM-DD)"));
  const amount = parseField(body, "Amount");
  const official_url = parseField(body, "Official info URL");
  const apply_url = parseField(body, "Apply URL (optional, if different)");
  const description = parseField(body, "Description (public)");
  const featured = parseFeatured(body);

  const url = safeStr(apply_url) || safeStr(official_url);

  if (!title || !url || !description) {
    throw new Error("Missing required fields: title, url, or description.");
  }

  const newItem = {
    id: makeId({ url, title, deadline }),
    title,
    category: category || "Other",
    amount,
    deadline,
    difficulty: "Medium",
    description,
    url,
    state: state || "Nationwide",
    value: null,
    featured: !!featured,
  };

  const jsonPath = path.join(process.cwd(), "data", "opportunities.json");
  let existing = loadExisting(jsonPath);

  // Remove expired items on every run (keeps live site clean)
  existing = existing.filter((x) => !isExpired(safeStr(x.deadline)));

  // Avoid duplicates by id or url
  const already = existing.some(
    (x) => safeStr(x.id) === newItem.id || safeStr(x.url) === newItem.url
  );

  if (!already) existing.unshift(newItem);

  // Sort by deadline soonest first, blanks last
  existing.sort((a, b) => {
    const ad = safeStr(a.deadline) || "9999-12-31";
    const bd = safeStr(b.deadline) || "9999-12-31";
    return ad.localeCompare(bd);
  });

  writeJson(jsonPath, existing);
  console.log(`Saved. Total opportunities: ${existing.length}`);
})();
