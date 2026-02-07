/* eslint-disable no-console */
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

function safeStr(v) {
  if (v === null || v === undefined) return "";
  return String(v).trim();
}

function escapeRegExp(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function parseField(body, label) {
  // Matches GitHub issue form output like:
  // "### Label\nvalue\n"
  const escaped = escapeRegExp(label);
  const re = new RegExp(
    `###\\s+${escaped}\\s*\\n([\\s\\S]*?)(\\n###\\s+|$)`,
    "i"
  );
  const m = body.match(re);
  if (!m) return "";
  return safeStr(m[1]).replace(/\n+$/g, "");
}

function parseFeatured(body) {
  // Checkbox section includes "- [x] Mark as featured" when checked
  return /- \[x\]\s+Mark as featured/i.test(body);
}

function toISODateOrEmpty(s) {
  const v = safeStr(s);
  if (!v) return "";
  // light validation: YYYY-MM-DD
  if (!/^\d{4}-\d{2}-\d{2}$/.test(v)) return "";
  return v;
}

function isExpired(deadlineISO) {
  if (!deadlineISO) return false;

  // Compare by date string in UTC. Good enough for "deadline passed".
  const now = new Date();
  const yyyy = String(now.getUTCFullYear());
  const mm = String(now.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(now.getUTCDate()).padStart(2, "0");
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

  // Labels MUST match your issue form headings exactly.
  const title = parseField(body, "Opportunity title (shows on site)");
  const category = parseField(body, "Category");
  const state = parseField(body, "State");
  const deadline = toISODateOrEmpty(parseField(body, "Deadline (YYYY-MM-DD)"));
  const amount = parseField(body, "Amount");
  const details_url = parseField(body, "Details URL (info page)");
  const apply_url = parseField(body, "Apply URL (where user files claim)");
  const card_description = parseField(body, "Card description (shows on site)");
  const featured = parseFeatured(body);

  const url = safeStr(apply_url) || safeStr(details_url);

  if (!title || !details_url || !card_description || !url) {
    throw new Error(
      "Missing required fields: title, details_url, card_description, or url."
    );
  }

  const newItem = {
    id: makeId({ url, title, deadline }),
    title,
    category: category || "Other",
    amount: safeStr(amount),
    deadline,
    difficulty: "Medium",
    description: card_description,
    url, // apply_url preferred, else details_url
    state: state || "Nationwide",
    value: null,
    featured: !!featured,

    // extra fields (won’t break anything if your UI ignores them)
    details_url: safeStr(details_url),
    apply_url: safeStr(apply_url),
  };

  const jsonPath = path.join(process.cwd(), "data", "opportunities.json");
  let existing = loadExisting(jsonPath);

  // Keep live JSON clean: drop expired on every run
  existing = existing.filter((x) => !isExpired(safeStr(x.deadline)));

  // Avoid duplicates by id OR url
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
  console.log(`Saved opportunities.json. Total active: ${existing.length}`);
})();

