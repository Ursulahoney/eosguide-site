/* eslint-disable no-console */
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

function safeStr(v) {
  if (v === null || v === undefined) return "";
  return String(v).trim();
}

function parseField(body, label) {
  const re = new RegExp(`###\\s+${label}\\s*\\n([\\s\\S]*?)(\\n###\\s+|$)`, "i");
  const m = body.match(re);
  if (!m) return "";
  return safeStr(m[1]).replace(/\n+$/g, "");
}

function parseFeatured(body) {
  return /- \[x\]\s+Mark as featured/i.test(body);
}

function toISODateOrEmpty(s) {
  const v = safeStr(s);
  if (!v) return "";
  if (!/^\d{4}-\d{2}-\d{2}$/.test(v)) return "";
  return v;
}

function isExpired(deadlineISO) {
  if (!deadlineISO) return false;
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
  if (!Array.isArray(parsed)) throw new Error("data/opportunities.json must be an array.");
  return parsed;
}

function writeJson(jsonPath, arr) {
  fs.mkdirSync(path.dirname(jsonPath), { recursive: true });
  fs.writeFileSync(jsonPath, JSON.stringify(arr, null, 2) + "\n", "utf8");
}

function stripHtml(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<noscript[\s\S]*?<\/noscript>/gi, " ")
    .replace(/<\/(p|div|li|h1|h2|h3|br|tr|td)>/gi, "\n")
    .replace(/<[^>]+>/g, " ")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

async function fetchPageText(url) {
  // Node 20 has global fetch
  const res = await fetch(url, {
    method: "GET",
    headers: {
      "user-agent":
        "Mozilla/5.0 (compatible; eosguidehubbot/1.0; +https://eosguidehub.com/)",
      "accept": "text/html,application/xhtml+xml",
    },
  });

  if (!res.ok) throw new Error(`Fetch failed: ${res.status}`);
  const ct = safeStr(res.headers.get("content-type"));
  if (!ct.includes("text/html")) throw new Error(`Not HTML: ${ct}`);
  const html = await res.text();
  const text = stripHtml(html);

  // If it’s too short, treat as failure
  if (text.length < 800) throw new Error("Fetched text too short (likely blocked or thin).");
  return text.slice(0, 12000); // keep it reasonable
}

async function callOpenAI({ detailsUrl, rawText, existingCardDescription }) {
  const apiKey = safeStr(process.env.OPENAI_API_KEY);
  if (!apiKey) return null;

  // Responses API
  const prompt = `
You write clean, non-plagiarized summaries for a website that routes users to official claim pages.

Rules:
- Do NOT copy sentences from the source.
- Use fresh wording.
- If a detail is not in the source, say "Not stated".
- Keep it simple, short sentences.
- No legal advice.

Return JSON only with:
{
  "card_description": "2-4 sentences",
  "article_markdown": "# Title\\n\\n... (400-900 words)\\n\\n## Links\\n- Details: ...\\n- Apply: ...\\n\\n## Disclaimer\\n..."
}

Context:
- Details URL: ${detailsUrl}
- Current card description (may be empty): ${existingCardDescription}

Source text:
${rawText}
`.trim();

  const res = await fetch("https://api.openai.com/v1/responses", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: "gpt-5.2-mini",
      input: prompt,
      // If the model returns extra text, we’ll try to parse JSON anyway.
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`OpenAI error ${res.status}: ${err.slice(0, 300)}`);
  }

  const data = await res.json();
  const out = safeStr(data.output_text || "");
  if (!out) return null;

  // Try to extract JSON from output_text
  const start = out.indexOf("{");
  const end = out.lastIndexOf("}");
  if (start === -1 || end === -1) return null;

  const jsonStr = out.slice(start, end + 1);
  return JSON.parse(jsonStr);
}

function writeDraft(issueNumber, md) {
  const dir = path.join(process.cwd(), "drafts");
  fs.mkdirSync(dir, { recursive: true });
  const p = path.join(dir, `issue-${issueNumber}.md`);
  fs.writeFileSync(p, md + "\n", "utf8");
  return p;
}

(async function main() {
  const body = safeStr(process.env.ISSUE_BODY);
  const issueNumber = safeStr(process.env.ISSUE_NUMBER) || "unknown";
  if (!body) throw new Error("Missing ISSUE_BODY");

  const title = parseField(body, "Opportunity title (shows on site)");
  const category = parseField(body, "Category");
  const state = parseField(body, "State");
  const deadline = toISODateOrEmpty(parseField(body, "Deadline (YYYY-MM-DD)"));
  const amount = parseField(body, "Amount");
  const details_url = parseField(body, "Details URL (info page)");
  const apply_url = parseField(body, "Apply URL (where user files claim)");
  const card_description = parseField(body, "Card description (shows on site)");
  const source_text = parseField(body, "Source text (optional fallback)");
  const featured = parseFeatured(body);

  const url = safeStr(apply_url) || safeStr(details_url);

  if (!title || !details_url || !card_description || !url) {
    throw new Error("Missing required fields: title, details_url, card_description, or url.");
  }

  // Build new item for your site (keeps current keys)
  const newItem = {
    id: makeId({ url, title, deadline }),
    title,
    category: category || "Other",
    amount: safeStr(amount),
    deadline,
    difficulty: "Medium",
    description: card_description,
    url, // apply_url preferred
    state: state || "Nationwide",
    value: null,
    featured: !!featured,
    // extra fields for your future use (won’t break anything if UI ignores them)
    details_url: safeStr(details_url),
    apply_url: safeStr(apply_url),
  };

  const jsonPath = path.join(process.cwd(), "data", "opportunities.json");
  let existing = loadExisting(jsonPath);

  // Keep the live site clean: remove expired on every run
  existing = existing.filter((x) => !isExpired(safeStr(x.deadline)));

  // Dedupe
  const already = existing.some(
    (x) => safeStr(x.id) === newItem.id || safeStr(x.url) === newItem.url
  );
  if (!already) existing.unshift(newItem);

  // Sort by deadline soonest, blanks last
  existing.sort((a, b) => {
    const ad = safeStr(a.deadline) || "9999-12-31";
    const bd = safeStr(b.deadline) || "9999-12-31";
    return ad.localeCompare(bd);
  });

  writeJson(jsonPath, existing);
  console.log(`Saved opportunities.json. Total active: ${existing.length}`);

  // Try to generate an AI article draft
  let rawText = "";
  try {
    rawText = await fetchPageText(details_url);
    console.log("Fetched details_url text for drafting.");
  } catch (e) {
    console.log(`Fetch failed (${e.message}). Using source_text fallback if present.`);
    rawText = safeStr(source_text);
  }

  if (rawText) {
    try {
      const ai = await callOpenAI({
        detailsUrl: details_url,
        rawText,
        existingCardDescription: card_description,
      });

      if (ai && ai.article_markdown) {
        const md = ai.article_markdown
          .replace(/\r\n/g, "\n")
          .trim();
        const savedPath = writeDraft(issueNumber, md);
        console.log(`Draft saved: ${savedPath}`);
      } else {
        console.log("No AI draft generated (empty output).");
      }
    } catch (e) {
      console.log(`AI draft skipped/failed: ${e.message}`);
    }
  } else {
    console.log("No source text available. Skipping AI draft.");
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
