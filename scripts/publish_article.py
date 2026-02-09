import os
import re
import sys
from datetime import datetime

TEMPLATE_PATH = "templates/article.html"
ARTICLES_INDEX_PATH = "articles/index.html"
DRAFTS_DIR = "articles/drafts"
PUBLISHED_DIR = "articles"

MARKER = "<!-- ARTICLES_LIST_INSERT_HERE -->"

def die(msg: str):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)

def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_file(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9\- ]+", "", s)
    s = s.replace(" ", "-")
    s = re.sub(r"-{2,}", "-", s).strip("-")
    if not s:
        die("Slug is empty after cleanup.")
    return s

def extract_field(body: str, label: str) -> str:
    """
    GitHub Issue Forms can be inconsistent in how they render headings.
    This version is more forgiving (case-insensitive, whitespace-tolerant).
    """
    body = body.replace("\r\n", "\n")

    # Exact match first
    pattern = rf"^###\s+{re.escape(label)}\s*$\n(.*?)(?=\n###\s+|\Z)"
    m = re.search(pattern, body, flags=re.MULTILINE | re.DOTALL)
    if m:
        return m.group(1).strip()

    # Fallback: ignore case and allow extra/multiple spaces in the heading
    label_ws = re.sub(r"\s+", r"\\s+", re.escape(label))
    pattern2 = rf"^###\s+{label_ws}\s*$\n(.*?)(?=\n###\s+|\Z)"
    m2 = re.search(pattern2, body, flags=re.MULTILINE | re.DOTALL | re.IGNORECASE)
    if m2:
        return m2.group(1).strip()

    return ""


def checkbox_checked(body: str, label: str) -> bool:
    # Forms render checkboxes as "- [x] Include monetization block"
    return bool(re.search(rf"-\s+\[x\]\s+{re.escape(label)}\s*$", body, flags=re.MULTILINE | re.IGNORECASE))

def convert_markdown_to_html(md_text: str) -> str:
    """
    Convert Markdown/plain text to HTML.
    Uses Python-Markdown installed in the workflow.
    """
    try:
        import markdown  # type: ignore
    except Exception:
        die("Python markdown library not available. Make sure the workflow installs 'markdown'.")

    # If user pasted plain text, markdown will still handle it fine.
    html = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "sane_lists", "nl2br"]
    )
    return html

def wrap_hero_credit(credit: str) -> str:
    if not credit.strip():
        return ""
    # If they pasted full HTML, allow it. If plain text, wrap nicely.
    if "<a " in credit or "<p" in credit or "</" in credit:
        return credit
    return f'<p class="text-xs text-gray-500 mt-2">{credit}</p>'

def build_article(template_html: str, data: dict) -> str:
    # Basic fallbacks
    deadline = data["deadline"].strip() or "None listed"
    hero_image = data["hero_image"].strip()
    if hero_image:
        # Accept either full path or filename. If filename, assume /assets/articles/
        if hero_image.startswith("/"):
            hero_src = hero_image
        else:
            hero_src = f"/assets/articles/{hero_image}"
    else:
        # Safe fallback that always exists
        hero_src = "/Circular-badge-logo.png"

    hero_alt = data["hero_alt"].strip() or "Article image"

    hero_credit_html = wrap_hero_credit(data["hero_credit"])

    # Monetization stays empty unless turned on AND published later (we keep it ready)
    monetization_on = data["monetization_on"]
    monetization_block = ""
    if monetization_on:
        monetization_block = """
<div class="mt-10 p-4 rounded-2xl bg-gray-50 border border-gray-200">
  <p class="text-sm font-semibold text-gray-800 mb-1">Optional tools & links</p>
  <p class="text-sm text-gray-600">
    We may include sponsored or affiliate links here in the future. If we do, we’ll label them.
  </p>
</div>
""".strip()

    html_body = convert_markdown_to_html(data["article_body"])

    out = template_html
    out = out.replace("{{TITLE}}", data["title"])
    out = out.replace("{{META_DESCRIPTION}}", data["meta_description"])
    out = out.replace("{{CANONICAL_URL}}", data["canonical_url"])
    out = out.replace("{{INTRO_LINE}}", data["intro_line"])
    out = out.replace("{{DEADLINE}}", deadline)
    out = out.replace("{{LAST_UPDATED}}", data["last_updated"])
    out = out.replace("{{HERO_IMAGE}}", hero_src)
    out = out.replace("{{HERO_ALT}}", hero_alt)
    out = out.replace("{{HERO_CREDIT}}", hero_credit_html)
    out = out.replace("{{ARTICLE_BODY}}", html_body)
    out = out.replace("{{MONETIZATION_BLOCK}}", monetization_block)

    return out

def build_card(data: dict) -> str:
    deadline = data["deadline"].strip() or "None listed"
    line = f"Deadline: {deadline} · Updated {data['last_updated']}"
    href = f"/articles/{data['slug']}.html"

    return f"""
<article class="bg-white rounded-2xl shadow-sm p-5">
  <h2 class="text-xl font-bold text-gray-900 mb-1">
    <a href="{href}" class="hover:underline">{data['title']}</a>
  </h2>
  <p class="text-sm text-gray-600 mb-2">{line}</p>
  <p class="text-gray-700">{data['blurb']}</p>
</article>
""".strip()

def insert_into_articles_index(index_html: str, new_card_html: str) -> str:
    if MARKER not in index_html:
        die(f"Marker not found in {ARTICLES_INDEX_PATH}: {MARKER}")
    # Insert newest first: right after marker
    return index_html.replace(MARKER, MARKER + "\n\n" + new_card_html + "\n")

def main():
    mode = os.environ.get("MODE", "").strip().lower()
    if mode not in ("draft", "publish"):
        die("MODE must be 'draft' or 'publish'")

    issue_body_path = os.environ.get("ISSUE_BODY_PATH")
    if not issue_body_path or not os.path.exists(issue_body_path):
        die("ISSUE_BODY_PATH missing or file not found")

    issue_body = read_file(issue_body_path)

    # Field labels must match your Issue Form labels exactly:
    title = extract_field(issue_body, "Article title")
    slug = extract_field(issue_body, "URL slug")
    blurb = extract_field(issue_body, "Short blurb")
    deadline = extract_field(issue_body, "Deadline")
    last_updated = extract_field(issue_body, "Last updated")
    hero_image = extract_field(issue_body, "Hero image filename")
    hero_credit = extract_field(issue_body, "Hero image credit (optional)")
    article_body = extract_field(issue_body, "Article body")
    status = extract_field(issue_body, "Publish status")

    if not title:
        die("Missing Article title")
    if not slug:
        # fallback to title slug if empty
        slug = slugify(title)
    else:
        slug = slugify(slug)

    if not blurb:
        die("Missing Short blurb")
    if not last_updated:
        # fallback to today
        last_updated = datetime.utcnow().strftime("%B %d, %Y")
    if not article_body:
        die("Missing Article body")

    monetization_on = checkbox_checked(issue_body, "Include monetization block")

    # meta/intro fallbacks
    meta_description = blurb
    intro_line = blurb

    canonical_url = f"https://eosguidehub.com/articles/{slug}.html"

    data = {
        "title": title.strip(),
        "slug": slug,
        "blurb": blurb.strip(),
        "deadline": deadline.strip(),
        "last_updated": last_updated.strip(),
        "hero_image": hero_image.strip(),
        "hero_alt": "Article image",
        "hero_credit": hero_credit.strip(),
        "article_body": article_body.strip(),
        "meta_description": meta_description.strip(),
        "intro_line": intro_line.strip(),
        "canonical_url": canonical_url,
        "monetization_on": monetization_on,
        "status": (status.strip() or "Draft"),
    }

    template_html = read_file(TEMPLATE_PATH)
    article_html = build_article(template_html, data)

    draft_path = os.path.join(DRAFTS_DIR, f"{slug}.html")
    published_path = os.path.join(PUBLISHED_DIR, f"{slug}.html")

    if mode == "draft":
        write_file(draft_path, article_html)
        print(f"Wrote draft: {draft_path}")
        return

    # publish mode
    write_file(published_path, article_html)
    print(f"Wrote published: {published_path}")

    # update articles index
    index_html = read_file(ARTICLES_INDEX_PATH)
    new_card_html = build_card(data)
    updated_index = insert_into_articles_index(index_html, new_card_html)
    write_file(ARTICLES_INDEX_PATH, updated_index)
    print(f"Updated index: {ARTICLES_INDEX_PATH}")

if __name__ == "__main__":
    main()
