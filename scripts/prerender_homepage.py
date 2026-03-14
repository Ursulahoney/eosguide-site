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


def get_accent(category):
    c = (category or "").lower()
    if "class action" in c or "legal" in c or "settlement" in c:
        return "#0891b2"
    if "refund" in c or "unclaimed" in c:
        return "#7c3aed"
    if "relief" in c or "benefit" in c or "assistance" in c:
        return "#db2777"
    if "utility" in c or "energy" in c:
        return "#0d9488"
    if "health" in c or "medical" in c or "veteran" in c:
        return "#4f46e5"
    if "tax" in c or "property" in c:
        return "#e11d48"
    return "#7c3aed"


def urgency_badge(dl):
    if dl is None or dl < 0 or dl > 900:
        return ""
    if dl <= 7:
        return f'<span style="display:inline-flex;align-items:center;padding:2px 9px;border-radius:999px;font-size:11px;font-weight:700;background:linear-gradient(135deg,#ef4444,#ec4899);color:#fff;margin-bottom:6px;">🔥 {dl}d left</span>'
    if dl <= 30:
        return f'<span style="display:inline-flex;align-items:center;padding:2px 9px;border-radius:999px;font-size:11px;font-weight:700;background:linear-gradient(135deg,#f97316,#ef4444);color:#fff;margin-bottom:6px;">⏰ {dl}d left</span>'
    if dl <= 60:
        return f'<span style="display:inline-flex;align-items:center;padding:2px 9px;border-radius:999px;font-size:11px;font-weight:700;background:#fef9c3;color:#854d0e;margin-bottom:6px;">📅 {dl}d left</span>'
    return ""


def card_html(opp):
    title = escape_html(safe(opp.get("title")))
    desc = escape_html(safe(opp.get("description")))
    amount = escape_html(safe(opp.get("amount"))) or ""
    state = escape_html(safe(opp.get("state"))) or "Nationwide"
    category = safe(opp.get("category")) or "Other"
    accent = get_accent(category)

    url = safe(opp.get("url"))
    if url.startswith("https://eosguidehub.com"):
        url = url.replace("https://eosguidehub.com", "")
    if url and not url.startswith("/"):
        url = "/" + url
    if url.startswith("/articles/") and not url.endswith(".html"):
        url = url.rstrip("/") + ".html"

    deadline_raw = safe(opp.get("deadline"))
    d = parse_deadline_iso(deadline_raw)
    dl = days_left(d)
    deadline_display = escape_html(format_deadline(deadline_raw))

    is_national = state.lower() in ("nationwide", "national", "all states", "")
    state_badge = "🌐 Nationwide" if is_national else f"📍 {state}"

    urgency_html = urgency_badge(dl)
    amount_html = f'<div style="font-size:15px;font-weight:900;color:{accent};margin-bottom:4px;">{escape_html(amount)}</div>' if amount else ""

    return f"""<article style="background:#ffffff;border:1px solid #e5e7eb;border-left:4px solid {accent};border-radius:1.5rem;padding:1.25rem;display:flex;flex-direction:column;transition:transform 0.2s,box-shadow 0.2s;" class="animate-fadeInUp hover:-translate-y-1 hover:shadow-lg">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
    <span style="display:inline-flex;align-items:center;padding:3px 10px;border-radius:999px;font-size:11px;font-weight:600;color:#4b5563;background:#f3f4f6;">{escape_html(state_badge)}</span>
  </div>
  {amount_html}
  {urgency_html}
  <h4 style="font-size:14px;font-weight:700;color:#111827;margin:0 0 8px;line-height:1.35;">{title}</h4>
  <p style="font-size:12px;color:#374151;line-height:1.6;margin:0 0 10px;flex:1;">{desc}</p>
  <div style="border-top:1px solid #f3f4f6;padding-top:10px;margin-bottom:12px;display:flex;justify-content:space-between;font-size:11px;">
    <span style="color:#9ca3af;font-weight:500;">Deadline</span>
    <span style="font-weight:700;color:#374151;">{deadline_display}</span>
  </div>
  <a href="{escape_html(url)}" style="display:block;width:100%;text-align:center;padding:10px;color:#fff;border-radius:14px;font-size:13px;font-weight:700;text-decoration:none;background:{accent};">
    View Details →
  </a>
</article>"""


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
