import os
import re
import markdown


# ─────────────────────────────────────────────────────────────────
# ISSUE BODY PARSER
# ─────────────────────────────────────────────────────────────────

def get_field(body: str, label: str) -> str:
    """
    GitHub issue forms render fields like:

    ### Label
    value

    Capture until next ### or end.
    """
    pattern = rf"### {re.escape(label)}\n(.*?)(?=\n### |\Z)"
    m = re.search(pattern, body, flags=re.S)
    if not m:
        return ""
    val = m.group(1).strip()
    if val == "_No response_":
        return ""
    return val


def parse_lines(text: str) -> list[str]:
    if not text:
        return []
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^[-*]\s*", "", line)
        out.append(line)
    return out


def parse_steps(text: str) -> list[str]:
    if not text:
        return []
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^\d+\)\s*", "", line)
        line = re.sub(r"^[-*]\s*", "", line)
        out.append(line)
    return out


def parse_faqs(text: str) -> list[tuple[str, str]]:
    """
    Format:
    Q: ...
    A: ...
    blank line between pairs is OK
    """
    if not text:
        return []

    blocks = re.split(r"\n\s*\n", text.strip())
    faqs: list[tuple[str, str]] = []

    for b in blocks:
        q = ""
        a = ""
        for line in b.splitlines():
            line = line.strip()
            if line.lower().startswith("q:"):
                q = line[2:].strip()
            elif line.lower().startswith("a:"):
                a = line[2:].strip()
            else:
                if a:
                    a += " " + line
                elif q:
                    q += " " + line
        if q and a:
            faqs.append((q, a))

    return faqs


def normalize_states(text: str) -> list[str]:
    if not text:
        return []
    parts = [p.strip() for p in re.split(r"[\n,]+", text) if p.strip() and p.strip() != "_No response_"]
    if any(p.lower() == "nationwide" for p in parts):
        return ["Nationwide"]
    seen = set()
    out = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def parse_pipe_rows(text: str) -> list[dict]:
    """
    For lines like:
      Label | Value | Notes(optional)
    Returns: [{"label":..., "value":..., "notes":...}, ...]
    """
    if not text:
        return []
    rows = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) == 1:
            # If they didn't use pipes, treat whole line as a label/value blob
            rows.append({"label": parts[0], "value": "", "notes": ""})
            continue
        label = parts[0] if len(parts) >= 1 else ""
        value = parts[1] if len(parts) >= 2 else ""
        notes = parts[2] if len(parts) >= 3 else ""
        rows.append({"label": label, "value": value, "notes": notes})
    return rows


# ─────────────────────────────────────────────────────────────────
# HTML BUILDERS (ONLY RENDER IF FILLED)
# ─────────────────────────────────────────────────────────────────

def build_at_a_glance(f: dict) -> str:
    def row(label: str, value_html: str) -> str:
        return f'''
        <div class="glance-row">
          <span class="glance-label">{label}</span>
          <span class="glance-value">{value_html}</span>
        </div>'''

    rows = ""

    states = normalize_states(f.get("eligible_states", ""))
    if states:
        rows += row("Applies to", ", ".join(states))

    if f.get("deadline"):
        rows += row("Main deadline", f["deadline"])

    benefit_summary = f.get("benefit_summary", "")
    if benefit_summary:
        rows += row("Benefit", benefit_summary)

    if f.get("official_website"):
        url = f["official_website"]
        rows += row("Official site", f'<a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a>')

    if not rows:
        return ""

    return f'''
    <section class="glance-card" aria-label="At a glance">
      <h2 class="section-title">At a glance</h2>
      <div class="glance-grid">{rows}</div>
    </section>
    '''


def build_key_dates_table(f: dict) -> str:
    deadline = f.get("deadline", "")
    optout = f.get("optout_deadline", "")
    objection = f.get("objection_deadline", "")
    hearing = f.get("hearing_date", "")

    if not any([deadline, optout, objection, hearing]):
        return ""

    rows = ""
    if deadline:
        rows += f'''
        <tr>
          <td>Submit / Claim</td>
          <td class="date-cell urgent">{deadline}</td>
          <td>Last day to submit</td>
        </tr>'''
    if optout:
        rows += f'''
        <tr>
          <td>Opt out</td>
          <td class="date-cell">{optout}</td>
          <td>Keep your right to sue separately</td>
        </tr>'''
    if objection:
        rows += f'''
        <tr>
          <td>Object</td>
          <td class="date-cell">{objection}</td>
          <td>Tell the court you disagree</td>
        </tr>'''
    if hearing:
        rows += f'''
        <tr>
          <td>Final hearing</td>
          <td class="date-cell">{hearing}</td>
          <td>Judge decides whether to approve</td>
        </tr>'''

    return f'''
    <section class="section">
      <h2 class="section-title">Key dates</h2>
      <div class="table-wrap">
        <table class="deadline-table">
          <thead>
            <tr>
              <th>Action</th>
              <th>Date</th>
              <th>What it means</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </section>
    '''


def build_benefits_section(f: dict) -> str:
    rows = parse_pipe_rows(f.get("benefits", ""))
    if not rows:
        return ""

    cards = ""
    for r in rows:
        label = r.get("label", "")
        value = r.get("value", "")
        notes = r.get("notes", "")
        if not (label or value or notes):
            continue

        big = value if value else notes if notes else ""
        small = notes if (value and notes) else ""

        cards += f'''
        <div class="benefit-card">
          <h3>{label or "Benefit"}</h3>
          <p class="big">{big}</p>
          {f'<p class="small">{small}</p>' if small else ''}
        </div>
        '''

    if not cards:
        return ""

    return f'''
    <section class="section">
      <h2 class="section-title">What you can get</h2>
      <div class="benefit-grid">
        {cards}
      </div>
    </section>
    '''


def build_bullets_section(title: str, items: list[str]) -> str:
    if not items:
        return ""
    lis = "".join([f"<li>{i}</li>" for i in items])
    return f'''
    <section class="section">
      <h2 class="section-title">{title}</h2>
      <ul class="bullets">{lis}</ul>
    </section>
    '''


def build_steps_section(title: str, steps: list[str]) -> str:
    if not steps:
        return ""
    lis = "".join([f"<li>{s}</li>" for s in steps])
    return f'''
    <section class="section">
      <h2 class="section-title">{title}</h2>
      <ol class="steps">{lis}</ol>
    </section>
    '''


def build_links_section(f: dict) -> str:
    links = []
    if f.get("official_website"):
        links.append(("Official website", f["official_website"]))
    if f.get("claim_form_url"):
        links.append(("Claim form", f["claim_form_url"]))
    if f.get("important_dates_url"):
        links.append(("Important dates", f["important_dates_url"]))
    if f.get("faqs_url"):
        links.append(("FAQs", f["faqs_url"]))
    if f.get("documents_url"):
        links.append(("Documents", f["documents_url"]))

    if not links:
        return ""

    items = ""
    for label, url in links:
        items += f'<li><a href="{url}" target="_blank" rel="noopener noreferrer">{label}</a></li>'

    return f'''
    <section class="section">
      <h2 class="section-title">Important links</h2>
      <ul class="bullets">{items}</ul>
    </section>
    '''


def build_contact_section(f: dict) -> str:
    phone = f.get("admin_phone", "")
    email = f.get("admin_email", "")
    addr = f.get("admin_address", "")

    if not any([phone, email, addr]):
        return ""

    rows = ""
    if phone:
        rows += f"<div class='mini-row'><strong>Phone:</strong> {phone}</div>"
    if email:
        rows += f"<div class='mini-row'><strong>Email:</strong> {email}</div>"
    if addr:
        rows += f"<div class='mini-row'><strong>Mail:</strong> {addr}</div>"

    return f'''
    <section class="section">
      <h2 class="section-title">Contact</h2>
      <div class="callout">{rows}</div>
    </section>
    '''


def build_faq_section(faqs: list[tuple[str, str]]) -> str:
    if not faqs:
        return ""
    blocks = ""
    for q, a in faqs:
        blocks += f'''
      <details class="faq">
        <summary>{q}</summary>
        <div class="faq-a">{a}</div>
      </details>'''
    return f'''
    <section class="section">
      <h2 class="section-title">FAQ</h2>
      {blocks}
    </section>
    '''


def build_cta_buttons(official_website: str, deadline: str) -> str:
    if not official_website:
        return ""
    deadline_note = f" (deadline: {deadline})" if deadline else ""
    return f'''
    <div class="cta-row">
      <a class="btn primary" href="{official_website}" target="_blank" rel="noopener noreferrer">
        Go to official website{deadline_note}
      </a>
      <a class="btn" href="/articles/">Browse more articles</a>
    </div>
    '''


# ─────────────────────────────────────────────────────────────────
# MAIN PAGE BUILDER
# ─────────────────────────────────────────────────────────────────

def build_page(f: dict) -> str:
    title = f.get("title", "Article")
    slug = f.get("slug", "article")
    blurb = f.get("blurb", "")
    last_updated = f.get("last_updated", "")
    official_website = f.get("official_website", "")
    hero_image = f.get("hero_image", "")
    hero_credit = f.get("hero_credit", "")

    what_happened_md = f.get("what_happened", "")
    class_period = f.get("class_period", "")
    payment_timing = f.get("payment_timing", "")
    extra_details_md = f.get("extra_details", "")

    eligibility_items = parse_lines(f.get("eligibility", ""))
    proof_items = parse_lines(f.get("proof_required", ""))
    steps = parse_steps(f.get("how_to_file", ""))
    faqs = parse_faqs(f.get("faqs", ""))

    # Convert markdown-ish areas
    what_happened_html = markdown.markdown(what_happened_md) if what_happened_md else ""
    extra_details_html = markdown.markdown(extra_details_md) if extra_details_md else ""

    at_a_glance_html = build_at_a_glance(f)
    key_dates_html = build_key_dates_table(f)
    benefits_html = build_benefits_section(f)
    links_html = build_links_section(f)
    eligibility_html = build_bullets_section("Who may qualify", eligibility_items)
    steps_html = build_steps_section("How to file", steps)
    proof_html = build_bullets_section("Proof required", proof_items)
    contact_html = build_contact_section(f)
    faq_html = build_faq_section(faqs)

    hero_html = ""
    if hero_image:
        credit_html = f"<p style='font-size:12px;color:var(--muted);margin-top:6px;'>{hero_credit}</p>" if hero_credit else ""
        hero_html = f"""
    <figure class="hero">
      <img src="{hero_image}" alt="{title}" loading="lazy" />
      {credit_html}
    </figure>
        """

    # Meta
    meta_description = blurb.strip().replace("\n", " ")
    meta_description = meta_description[:155].rstrip()
    canonical = f"https://eosguidehub.com/articles/{slug}.html"

    # Optional simple sections
    class_period_html = f"<p><strong>Class period:</strong> {class_period}</p>" if class_period else ""
    payment_timing_html = f"<p>{payment_timing}</p>" if payment_timing else ""

    what_happened_section = ""
    if what_happened_html or class_period_html:
        what_happened_section = f'''
        <section class="section">
          <h2 class="section-title">What happened</h2>
          {class_period_html}
          {what_happened_html}
        </section>
        '''

    extra_details_section = ""
    if extra_details_html:
        extra_details_section = f'''
        <section class="section">
          <h2 class="section-title">Extra details</h2>
          {extra_details_html}
        </section>
        '''

    payment_section = ""
    if payment_timing_html:
        payment_section = f'''
        <section class="section">
          <h2 class="section-title">Payment timing</h2>
          {payment_timing_html}
        </section>
        '''

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />

  <title>{title} | eosguidehub</title>
  <meta name="description" content="{meta_description}" />
  <link rel="canonical" href="{canonical}" />

  <meta property="og:type" content="article" />
  <meta property="og:title" content="{title}" />
  <meta property="og:description" content="{meta_description}" />
  <meta property="og:url" content="{canonical}" />

  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{title}" />
  <meta name="twitter:description" content="{meta_description}" />

  <style>
    :root {{
      --bg:          #F9F8F5;
      --surface:     #FFFFFF;
      --border:      #E8E5DF;
      --text:        #1C1A17;
      --muted:       #6B6560;
      --accent:      #2A6B4A;
      --accent-2:    #143E2A;
      --urgent:      #B42318;
      --shadow:      0 10px 30px rgba(0,0,0,0.06);
      --radius:      22px;
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.6;
    }}

    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}

    .site-header {{
      background: var(--surface);
      border-bottom: 1px solid var(--border);
    }}
    .site-header-inner {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 14px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }}
    .logo {{
      font-weight: 900;
      letter-spacing: -0.02em;
      font-size: 18px;
    }}
    .logo span {{ color: var(--accent); }}
    .breadcrumb {{ color: var(--muted); font-size: 14px; }}

    .layout {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 18px 16px 60px;
      display: grid;
      grid-template-columns: 1fr;
      gap: 16px;
    }}

    .article {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 18px 16px;
      box-shadow: var(--shadow);
    }}

    .article-meta {{
      display: flex;
      align-items: center;
      gap: 10px;
      color: var(--muted);
      font-size: 14px;
      margin-bottom: 6px;
    }}

    .article-title {{
      margin: 6px 0 10px;
      font-size: 1.9rem;
      line-height: 1.15;
      letter-spacing: -0.02em;
    }}

    .article-deck {{
      margin: 0 0 10px;
      color: var(--muted);
      font-size: 1.05rem;
    }}

    .divider {{
      border: none;
      border-top: 1px solid var(--border);
      margin: 18px 0;
    }}

    .hero img {{
      width: 100%;
      height: auto;
      border-radius: 18px;
      border: 1px solid var(--border);
      display: block;
    }}

    .section-title {{
      font-size: 1.2rem;
      margin: 0 0 10px;
      letter-spacing: -0.01em;
    }}

    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--border);
      border-radius: 18px;
      background: #FBFAF8;
    }}

    .deadline-table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 620px;
    }}
    .deadline-table th, .deadline-table td {{
      padding: 12px 12px;
      border-bottom: 1px solid var(--border);
      text-align: left;
      vertical-align: top;
      font-size: 14px;
    }}
    .deadline-table th {{
      background: #F5F2EC;
      color: var(--muted);
      font-weight: 800;
    }}
    .date-cell.urgent {{
      color: var(--urgent);
      font-weight: 900;
    }}

    .benefit-grid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 12px;
      margin-top: 10px;
    }}

    .benefit-card {{
      background: #FBFAF8;
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 14px;
    }}
    .benefit-card h3 {{
      margin: 0 0 6px;
      font-size: 1rem;
      color: var(--muted);
    }}
    .benefit-card .big {{
      margin: 0;
      font-size: 1.15rem;
      font-weight: 800;
    }}
    .benefit-card .small {{
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 0.95rem;
    }}

    .bullets li {{ margin: 6px 0; }}
    .steps li {{ margin: 8px 0; }}

    .cta-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 14px;
    }}
    .btn {{
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 10px 14px;
      font-weight: 800;
      background: #FBFAF8;
      color: var(--text);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }}
    .btn.primary {{
      background: rgba(42,107,74,0.12);
      border-color: rgba(42,107,74,0.30);
      color: var(--accent-2);
    }}

    details.faq {{
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 12px 14px;
      background: #FBFAF8;
      margin: 10px 0;
    }}
    details.faq summary {{
      cursor: pointer;
      font-weight: 900;
    }}
    .faq-a {{
      margin-top: 8px;
      color: var(--text);
    }}

    .callout {{
      border-radius: 18px;
      padding: 14px;
      border: 1px solid var(--border);
      background: #FBFAF8;
      color: var(--text);
    }}
    .callout strong {{ display: block; margin-bottom: 4px; }}

    /* At-a-glance */
    .glance-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 18px;
      margin: 18px 0;
      box-shadow: 0 6px 20px rgba(0,0,0,0.05);
    }}
    .glance-grid {{
      display: grid;
      gap: 10px;
      margin-top: 10px;
    }}
    .glance-row {{
      display: grid;
      grid-template-columns: 140px 1fr;
      gap: 10px;
      padding: 10px 12px;
      border-radius: 14px;
      background: #FBFAF8;
      border: 1px solid var(--border);
    }}
    .glance-label {{
      font-weight: 700;
      color: var(--muted);
      font-size: 0.95rem;
    }}
    .glance-value {{
      font-weight: 600;
      color: var(--text);
      font-size: 0.98rem;
      overflow-wrap: anywhere;
    }}

    @media (min-width: 960px) {{
      .layout {{
        grid-template-columns: 1fr;
      }}
      .benefit-grid {{
        grid-template-columns: repeat(2, 1fr);
      }}
    }}
  </style>
</head>
<body>

<header class="site-header">
  <div class="site-header-inner">
    <a class="logo" href="/">eos<span>guide</span></a>
    <nav class="breadcrumb" aria-label="Breadcrumb">
      <a href="/articles/">Articles</a> &rsaquo; Opportunity
    </nav>
  </div>
</header>

<div class="layout">
  <main class="article" id="main-content">
    <div class="article-meta">
      <time class="meta-date" datetime="{last_updated}">Updated {last_updated}</time>
    </div>

    <h1 class="article-title">{title}</h1>
    <p class="article-deck">{blurb}</p>

    {at_a_glance_html}

    {hero_html}

    <hr class="divider" />

    {what_happened_section}

    {benefits_html}

    {key_dates_html}

    {eligibility_html}

    {steps_html}

    {proof_html}

    {payment_section}

    {links_html}

    {contact_html}

    {extra_details_section}

    {build_cta_buttons(official_website, f.get("deadline", ""))}

    <hr class="divider" />

    {faq_html}

    <hr class="divider" />

    <div class="callout info">
      <strong>Use the official website</strong>
      Always confirm details on the official site. If something feels off, stop and verify before sharing personal info.
    </div>

  </main>
</div>

</body>
</html>
"""


# ─────────────────────────────────────────────────────────────────
# UPDATE /articles/index.html LIST
# ─────────────────────────────────────────────────────────────────

def update_articles_index(title: str, slug: str, blurb: str, last_updated: str):
    index_path = os.path.join("articles", "index.html")
    if not os.path.exists(index_path):
        return

    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()

    marker = "<!-- ARTICLES_LIST_INSERT_HERE -->"
    if marker not in html:
        return

    card = f"""
      <article class="article-card">
        <h2><a href="/articles/{slug}.html">{title}</a></h2>
        <p class="meta">Updated {last_updated}</p>
        <p class="desc">{blurb}</p>
        <a class="read-more" href="/articles/{slug}.html">Read article</a>
      </article>
    """

    html = html.replace(marker, marker + card)

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────

def main():
   issue_body = os.environ.get("ISSUE_BODY", "").strip()

if not issue_body:
    path = os.environ.get("ISSUE_BODY_PATH", "").strip()
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            issue_body = f.read().strip()

if not issue_body:
    raise SystemExit("Missing ISSUE_BODY (and ISSUE_BODY_PATH was empty/unreadable)")
    fields = {
        "title": get_field(issue_body, "Article title"),
        "slug": get_field(issue_body, "URL slug"),
        "blurb": get_field(issue_body, "Short blurb (used on listing page + near top of article)"),
        "last_updated": get_field(issue_body, "Last updated"),
        "eligible_states": get_field(issue_body, "Eligible states / location"),
        "official_website": get_field(issue_body, "Official website"),
        "claim_form_url": get_field(issue_body, "Claim form URL (optional)"),
        "important_dates_url": get_field(issue_body, "Important dates URL (optional)"),
        "faqs_url": get_field(issue_body, "FAQs URL (optional)"),
        "documents_url": get_field(issue_body, "Documents URL (optional)"),
        "hero_image": get_field(issue_body, "Hero image URL (optional)"),
        "hero_credit": get_field(issue_body, "Hero image credit (optional)"),
        "what_happened": get_field(issue_body, "What happened (optional)"),
        "benefit_summary": get_field(issue_body, "Benefit summary (optional)"),
        "benefits": get_field(issue_body, "Benefits list (optional)"),
        "deadline": get_field(issue_body, "Main deadline (optional)"),
        "optout_deadline": get_field(issue_body, "Opt-out deadline (optional)"),
        "objection_deadline": get_field(issue_body, "Objection deadline (optional)"),
        "hearing_date": get_field(issue_body, "Final approval hearing (optional)"),
        "eligibility": get_field(issue_body, "Who may qualify (optional checklist)"),
        "class_period": get_field(issue_body, "Class period (optional)"),
        "how_to_file": get_field(issue_body, "How to file (optional steps)"),
        "proof_required": get_field(issue_body, "Proof required (optional)"),
        "payment_timing": get_field(issue_body, "Payment timing / method (optional)"),
        "admin_phone": get_field(issue_body, "Administrator phone (optional)"),
        "admin_email": get_field(issue_body, "Administrator email (optional)"),
        "admin_address": get_field(issue_body, "Administrator mailing address (optional)"),
        "extra_details": get_field(issue_body, "Extra details (optional)"),
        "faqs": get_field(issue_body, "FAQs (optional)"),
    }

    slug = fields.get("slug") or "article"
    out_path = os.path.join("articles", f"{slug}.html")

    page_html = build_page(fields)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page_html)

    update_articles_index(fields["title"], slug, fields["blurb"], fields["last_updated"])
    print(f"Published: {out_path}")


if __name__ == "__main__":
    main()
