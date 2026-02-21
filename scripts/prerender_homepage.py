import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPPS_JSON = ROOT / "data" / "opportunities.json"
HOMEPAGE = ROOT / "index.html"

START = "<!-- OPPORTUNITIES:START -->"
END = "<!-- OPPORTUNITIES:END -->"


def safe(s):
    return (s or "").strip()


def parse_deadline_iso(s):
    s = safe(s)
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def days_left(deadline_date):
    if not deadline_date:
        return None
    today = datetime.now(timezone.utc).date()
    return (deadline_date - today).days


def escape_html(text):
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def format_deadline(deadline_iso):
    d = parse_deadline_iso(deadline_iso)
    if not d:
        return "Not listed"
    return d.strftime("%b %d, %Y")


def card_html(opp):
    title = escape_html(safe(opp.get("title")))
    desc = escape_html(safe(opp.get("description")))
    amount = escape_html(safe(opp.get("amount"))) or "—"
    state = escape_html(safe(opp.get("state"))) or "—"
    category = escape_html(safe(opp.get("category"))) or "Other"

    url = safe(opp.get("url"))
    if url.startswith("https://eosguidehub.com"):
        url = url.replace("https://eosguidehub.com", "")
    if url and not url.startswith("/"):
        url = "/" + url

    # Enforce internal article link format: /articles/<slug>.html
    if url.startswith("/articles/") and not url.endswith(".html"):
        url = url.rstrip("/") + ".html"

    deadline_raw = safe(opp.get("deadline"))
    deadline_display = escape_html(format_deadline(deadline_raw))

    return f"""
    <div class="bg-white rounded-3xl p-6 shadow-lg hover:shadow-2xl transition-all duration-300 hover:-translate-y-1">
      <div class="flex flex-wrap gap-2 mb-3">
        <span class="inline-flex items-center px-3 py-1 bg-gray-100 rounded-full text-xs font-bold text-gray-700">
          {category}
        </span>
        <span class="inline-flex items-center px-3 py-1 bg-gray-100 rounded-full text-xs font-bold text-gray-700">
          {state}
        </span>
      </div>

      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center space-x-1 text-green-600">
          <span class="font-black text-sm">{amount}</span>
        </div>
        <div class="text-sm text-gray-600">
          <span class="font-semibold">Deadline:</span> {deadline_display}
        </div>
      </div>

      <h3 class="text-lg font-bold text-gray-900 mb-2">{title}</h3>

      <p class="text-sm text-gray-600 mb-4">{desc}</p>

      <a href="{escape_html(url)}" class="block w-full text-center px-6 py-3 text-white rounded-2xl font-bold hover:shadow-lg transition-all duration-300"
         style="background: linear-gradient(135deg, #FF6B35 0%, #FF8C42 100%);">
        View Details →
      </a>
    </div>
    """.strip()


def main():
    if not OPPS_JSON.exists():
        raise SystemExit(f"Missing {OPPS_JSON}")

    opps = json.loads(OPPS_JSON.read_text(encoding="utf-8"))
    if not isinstance(opps, list):
        raise SystemExit("data/opportunities.json must be a JSON array")

    def sort_key(o):
        d = parse_deadline_iso(o.get("deadline"))
        dl = days_left(d)
        dl_sort = dl if (dl is not None) else 10**9
        featured = bool(o.get("featured"))
        return (0 if featured else 1, dl_sort, safe(o.get("title")).lower())

    opps_sorted = sorted(opps, key=sort_key)

    MAX_CARDS = 60
    opps_render = opps_sorted[:MAX_CARDS]

    cards = "\n".join(card_html(o) for o in opps_render)

    homepage = HOMEPAGE.read_text(encoding="utf-8")

    if START not in homepage or END not in homepage:
        raise SystemExit("Missing OPPORTUNITIES markers in index.html")

    pattern = re.compile(re.escape(START) + r"[\s\S]*?" + re.escape(END))
    homepage = pattern.sub(f"{START}\n{cards}\n{END}", homepage)

    # Update the initial count in raw HTML so it’s not “(0)”
    homepage = re.sub(
        r'(<span[^>]+id="oppCount"[^>]*>)([^<]*)(</span>)',
        rf"\g<1>({len(opps)})\g<3>",
        homepage,
        count=1,
    )

    HOMEPAGE.write_text(homepage, encoding="utf-8")
    print(f"Pre-rendered {len(opps_render)} cards into index.html (total in JSON: {len(opps)})")


if __name__ == "__main__":
    main()
