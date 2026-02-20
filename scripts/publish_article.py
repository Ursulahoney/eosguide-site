import os
import re
import json
import markdown
from datetime import datetime

# ─────────────────────────────────────────────────────────────────
# STEP 1: ISSUE BODY PARSER
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
        return ''
    val = m.group(1).strip()
    if val == "_No response_":
        return ''
    return val


def parse_steps(text: str) -> list:
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


def parse_eligibility(text: str) -> list:
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


def parse_faqs(text: str) -> list:
    """
    Format:
    Q: ...
    A: ...
    (blank line between pairs is OK)
    """
    if not text:
        return []

    blocks = re.split(r"\n\s*\n", text.strip())
    faqs = []

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


# ─────────────────────────────────────────────────────────────────
# STEP 2: HTML SECTION BUILDERS
# ─────────────────────────────────────────────────────────────────

def build_benefit_cards(max_payment: str, nodoc_payment: str, ca_payment: str, credit_monitoring: str) -> str:
    cards = ''
    if max_payment:
        cards += f'''
      <div class="benefit-card">
        <h3>Max payment</h3>
        <p class="big">{max_payment}</p>
      </div>'''
    if nodoc_payment:
        cards += f'''
      <div class="benefit-card">
        <h3>No-doc amount</h3>
        <p class="big">{nodoc_payment}</p>
      </div>'''
    if ca_payment:
        cards += f'''
      <div class="benefit-card">
        <h3>California amount</h3>
        <p class="big">{ca_payment}</p>
      </div>'''
    if credit_monitoring:
        cards += f'''
      <div class="benefit-card">
        <h3>Credit monitoring</h3>
        <p class="big">{credit_monitoring}</p>
      </div>'''

    if not cards:
        return ''

    return f'''
    <section class="benefit-grid" aria-label="Benefits">
      {cards}
    </section>'''


def build_deadline_table(deadline: str, optout_deadline: str, hearing_date: str) -> str:
    if not deadline and not optout_deadline and not hearing_date:
        return ''
    rows = ''
    if deadline:
        rows += f'''
        <tr>
          <td>File a Claim</td>
          <td class="date-cell urgent">{deadline}</td>
          <td>Only way to receive money or credit monitoring</td>
        </tr>'''
    if optout_deadline:
        rows += f'''
        <tr>
          <td>Opt Out</td>
          <td class="date-cell">{optout_deadline}</td>
          <td>Keep your right to sue on your own</td>
        </tr>'''
    if hearing_date:
        rows += f'''
        <tr>
          <td>Final Approval Hearing</td>
          <td class="date-cell">{hearing_date}</td>
          <td>Judge decides whether to approve the settlement</td>
        </tr>'''

    return f'''
    <section class="section">
      <h2 class="section-title">Key deadlines</h2>
      <div class="table-wrap">
        <table class="deadline-table">
          <thead>
            <tr>
              <th>Action</th>
              <th>Date</th>
              <th>What it means</th>
            </tr>
          </thead>
          <tbody>
            {rows}
          </tbody>
        </table>
      </div>
    </section>'''


# ─────────────────────────────────────────────────────────────────
# STEP 3B: AT-A-GLANCE BUILDER
# ─────────────────────────────────────────────────────────────────

def normalize_states(text: str) -> list[str]:
    """Accepts 'Nationwide' or a list of states from the issue form (often newline-separated)."""
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


def build_at_a_glance(
    eligible_states: str,
    deadline: str,
    optout_deadline: str,
    hearing_date: str,
    max_payment: str,
    nodoc_payment: str,
    official_website: str
) -> str:
    """Top summary card. Only renders rows that have values."""

    def row(label: str, value_html: str) -> str:
        return f'''
        <div class="glance-row">
          <span class="glance-label">{label}</span>
          <span class="glance-value">{value_html}</span>
        </div>'''

    rows = ''

    states = normalize_states(eligible_states)
    if states:
        rows += row("Applies to", ", ".join(states))

    if deadline:
        rows += row("Claim deadline", deadline)

    if optout_deadline:
        rows += row("Opt-out deadline", optout_deadline)

    if hearing_date:
        rows += row("Final hearing", hearing_date)

    if max_payment:
        rows += row("Max benefit", max_payment)

    if nodoc_payment:
        rows += row("No-doc amount", nodoc_payment)

    if official_website:
        rows += row(
            "Official site",
            f'<a href="{official_website}" target="_blank" rel="noopener noreferrer">{official_website}</a>'
        )

    if not rows:
        return ''

    return f'''
    <section class="glance-card" aria-label="At a glance">
      <h2 class="section-title">At a glance</h2>
      <div class="glance-grid">
        {rows}
      </div>
    </section>'''


# ─────────────────────────────────────────────────────────────────
# STEP 4: SIDEBAR BUILDER
# ─────────────────────────────────────────────────────────────────

def build_sidebar(f: dict) -> str:
    eligible_states   = f.get('eligible_states', '')
    deadline          = f.get('deadline', '')
    optout_deadline   = f.get('optout_deadline', '')
    hearing_date      = f.get('hearing_date', '')
    official_website  = f.get('official_website', '')
    settlement_amount = f.get('settlement_amount', '')
    max_payment       = f.get('max_payment', '')
    nodoc_payment     = f.get('nodoc_payment', '')
    ca_payment        = f.get('ca_payment', '')
    credit_monitoring = f.get('credit_monitoring', '')
    admin_phone       = f.get('admin_phone', '')
    admin_email       = f.get('admin_email', '')
    attorney_fees     = f.get('attorney_fees', '')
    service_awards    = f.get('service_awards', '')

    facts_rows = ''
    if settlement_amount:
        facts_rows += f'''
      <div class="sidebar-row">
        <span class="sidebar-label">Total Fund</span>
        <span class="sidebar-value accent">{settlement_amount}</span>
      </div>'''
    if max_payment:
        facts_rows += f'''
      <div class="sidebar-row">
        <span class="sidebar-label">Max Per Person</span>
        <span class="sidebar-value">{max_payment}</span>
      </div>'''
    if nodoc_payment:
        facts_rows += f'''
      <div class="sidebar-row">
        <span class="sidebar-label">No-doc Amount</span>
        <span class="sidebar-value">{nodoc_payment}</span>
      </div>'''
    if ca_payment:
        facts_rows += f'''
      <div class="sidebar-row">
        <span class="sidebar-label">California Amount</span>
        <span class="sidebar-value">{ca_payment}</span>
      </div>'''
    if credit_monitoring:
        facts_rows += f'''
      <div class="sidebar-row">
        <span class="sidebar-label">Credit Monitoring</span>
        <span class="sidebar-value">{credit_monitoring}</span>
      </div>'''
    if eligible_states:
        states = normalize_states(eligible_states)
        facts_rows += f'''
      <div class="sidebar-row">
        <span class="sidebar-label">Applies To</span>
        <span class="sidebar-value">{", ".join(states) if states else eligible_states}</span>
      </div>'''
    if deadline:
        facts_rows += f'''
      <div class="sidebar-row">
        <span class="sidebar-label">Claim Deadline</span>
        <span class="sidebar-value urgent">{deadline}</span>
      </div>'''
    if optout_deadline:
        facts_rows += f'''
      <div class="sidebar-row">
        <span class="sidebar-label">Opt-out Deadline</span>
        <span class="sidebar-value">{optout_deadline}</span>
      </div>'''
    if hearing_date:
        facts_rows += f'''
      <div class="sidebar-row">
        <span class="sidebar-label">Final Hearing</span>
        <span class="sidebar-value">{hearing_date}</span>
      </div>'''
    if official_website:
        facts_rows += f'''
      <div class="sidebar-row">
        <span class="sidebar-label">Official Site</span>
        <span class="sidebar-value"><a href="{official_website}" target="_blank" rel="noopener noreferrer">Visit</a></span>
      </div>'''

    admin_rows = ''
    if admin_phone:
        admin_rows += f'<div class="mini-row"><strong>Phone:</strong> {admin_phone}</div>'
    if admin_email:
        admin_rows += f'<div class="mini-row"><strong>Email:</strong> {admin_email}</div>'

    fees_rows = ''
    if attorney_fees:
        fees_rows += f'<div class="mini-row"><strong>Attorney Fees:</strong> {attorney_fees}</div>'
    if service_awards:
        fees_rows += f'<div class="mini-row"><strong>Service Awards:</strong> {service_awards}</div>'

    blocks = ''
    if facts_rows:
        blocks += f'''
    <aside class="sidebar-card">
      <h2>Quick Facts</h2>
      {facts_rows}
    </aside>'''
    if admin_rows:
        blocks += f'''
    <aside class="sidebar-card">
      <h2>Contact</h2>
      {admin_rows}
    </aside>'''
    if fees_rows:
        blocks += f'''
    <aside class="sidebar-card">
      <h2>Fees</h2>
      {fees_rows}
    </aside>'''

    return blocks


def build_steps_section(steps: list) -> str:
    if not steps:
        return ''
    items = ''.join([f'<li>{s}</li>' for s in steps])
    return f'''
    <section class="section">
      <h2 class="section-title">How to file</h2>
      <ol class="steps">{items}</ol>
    </section>'''


def build_eligibility_section(items: list) -> str:
    if not items:
        return ''
    lis = ''.join([f'<li>{i}</li>' for i in items])
    return f'''
    <section class="section">
      <h2 class="section-title">Who may qualify</h2>
      <ul class="bullets">{lis}</ul>
    </section>'''


def build_faq_section(faqs: list) -> str:
    if not faqs:
        return ''
    blocks = ''
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
    </section>'''


def build_cta_buttons(official_website: str, deadline: str) -> str:
    if not official_website:
        return ''
    deadline_note = f' (deadline: {deadline})' if deadline else ''
    return f'''
    <div class="cta-row">
      <a class="btn primary" href="{official_website}" target="_blank" rel="noopener noreferrer">
        Go to official website{deadline_note}
      </a>
      <a class="btn" href="/articles/">Browse more articles</a>
    </div>'''


def build_monetization_block(official_website: str) -> str:
    if not official_website:
        return ''
    return f'''
    <section class="section">
      <h2 class="section-title">Helpful tools</h2>
      <p class="muted">
        This section is a placeholder for future tools and recommendations. For now, always use the official site when filing.
      </p>
    </section>'''


# ─────────────────────────────────────────────────────────────────
# STEP 5: MAIN PAGE BUILDER
# ─────────────────────────────────────────────────────────────────

def build_page(f: dict) -> str:
    title            = f.get('title', 'Article')
    slug             = f.get('slug', 'article')
    blurb            = f.get('blurb', '')
    deadline         = f.get('deadline', '')
    last_updated     = f.get('last_updated', '')
    eligible_states  = f.get('eligible_states', '')
    settlement_amount = f.get('settlement_amount', '')
    max_payment      = f.get('max_payment', '')
    nodoc_payment    = f.get('nodoc_payment', '')
    ca_payment       = f.get('ca_payment', '')
    credit_monitoring = f.get('credit_monitoring', '')
    official_website = f.get('official_website', '')
    hero_image       = f.get('hero_image', '')
    hero_credit      = f.get('hero_credit', '')
    article_body     = f.get('article_body', '')
    optout_deadline  = f.get('optout_deadline', '')
    hearing_date     = f.get('hearing_date', '')

    eligibility_items = parse_eligibility(f.get('eligibility', ''))
    steps             = parse_steps(f.get('how_to_file', ''))
    faqs              = parse_faqs(f.get('faqs', ''))

    body_html = markdown.markdown(
        article_body,
        extensions=['tables', 'fenced_code']
    ) if article_body else ''

    # Build components
    benefit_cards     = build_benefit_cards(max_payment, nodoc_payment, ca_payment, credit_monitoring)
    deadline_table    = build_deadline_table(deadline, optout_deadline, hearing_date)
    at_a_glance_html  = build_at_a_glance(eligible_states, deadline, optout_deadline, hearing_date, max_payment, nodoc_payment, official_website)
    eligibility_block = build_eligibility_section(eligibility_items)
    steps_block       = build_steps_section(steps)
    faq_block         = build_faq_section(faqs)
    monetization_block = ''
    sidebar_html      = build_sidebar(f)

    hero_html = ''
    if hero_image:
        credit_html = f'<p style="font-size:12px;color:var(--muted);margin-top:6px;">{hero_credit}</p>' if hero_credit else ''
        hero_html = f'''
    <figure class="hero">
      <img src="{hero_image}" alt="{title}" loading="lazy" />
      {credit_html}
    </figure>'''

    meta_description = blurb.strip().replace("\n", " ")
    meta_description = meta_description[:155].rstrip()

    canonical = f"https://eosguidehub.com/articles/{slug}.html"

    return f'''<!doctype html>
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

    .section {{
      margin: 0;
    }}
    .section-title {{
      font-size: 1.2rem;
      margin: 0 0 10px;
      letter-spacing: -0.01em;
    }}

    .benefit-grid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 12px;
      margin-top: 18px;
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
      font-size: 1.25rem;
      font-weight: 800;
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

    .layout aside {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 14px;
      box-shadow: var(--shadow);
    }}
    .sidebar-card + .sidebar-card {{ margin-top: 12px; }}
    .sidebar-card h2 {{
      margin: 0 0 12px;
      font-size: 1.05rem;
    }}
    .sidebar-row {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 10px;
      padding: 10px 0;
      border-top: 1px solid var(--border);
    }}
    .sidebar-row:first-of-type {{ border-top: none; padding-top: 0; }}
    .sidebar-label {{ color: var(--muted); font-weight: 800; font-size: 13px; }}
    .sidebar-value {{ font-weight: 900; font-size: 13px; }}
    .sidebar-value.urgent {{ color: var(--urgent); }}
    .sidebar-value.accent {{ color: var(--accent); }}

    /* At-a-glance card */
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
        grid-template-columns: 1fr 320px;
        align-items: start;
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
      <a href="/articles/">Articles</a> &rsaquo; Settlements
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

    {body_html}

    {benefit_cards}

    <hr class="divider" />

    {deadline_table}

    <hr class="divider" />

    {eligibility_block}

    <hr class="divider" />

    {steps_block}

    {build_cta_buttons(official_website, deadline)}

    <hr class="divider" />

    {faq_block}

    {monetization_block}

    <hr class="divider" />

    <div class="callout info">
      <strong>eosguide is a directory, not a law firm</strong>
      We share public info and plain-language summaries. Always confirm details on the official settlement website.
    </div>

  </main>

  <aside class="sidebar" aria-label="Sidebar">
    {sidebar_html}
  </aside>

</div>

</body>
</html>'''


# ─────────────────────────────────────────────────────────────────
# STEP 6: UPDATE /articles/index.html LIST
# ─────────────────────────────────────────────────────────────────

def update_articles_index(title: str, slug: str, blurb: str, last_updated: str):
    index_path = os.path.join('articles', 'index.html')
    if not os.path.exists(index_path):
        return

    with open(index_path, 'r', encoding='utf-8') as f:
        html = f.read()

    marker = "<!-- ARTICLES_LIST_INSERT_HERE -->"
    if marker not in html:
        return

    card = f'''
      <article class="article-card">
        <h2><a href="/articles/{slug}.html">{title}</a></h2>
        <p class="meta">Updated {last_updated}</p>
        <p class="desc">{blurb}</p>
        <a class="read-more" href="/articles/{slug}.html">Read article</a>
      </article>
    '''

    html = html.replace(marker, marker + card)

    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(html)


# ─────────────────────────────────────────────────────────────────
# STEP 7: MAIN SCRIPT ENTRY
# ─────────────────────────────────────────────────────────────────

def main():
    issue_body = os.environ.get("ISSUE_BODY", "")
    if not issue_body:
        raise SystemExit("Missing ISSUE_BODY env var")

    fields = {
        "title": get_field(issue_body, "Article title"),
        "slug": get_field(issue_body, "URL slug"),
        "blurb": get_field(issue_body, "Short blurb (for the /articles list + article intro)"),
        "last_updated": get_field(issue_body, "Last updated"),
        "eligible_states": get_field(issue_body, "Eligible states / location"),
        "official_website": get_field(issue_body, "Official settlement website"),
        "hero_image": get_field(issue_body, "Hero image URL (optional)"),
        "hero_credit": get_field(issue_body, "Hero image credit (optional)"),
        "deadline": get_field(issue_body, "Claim deadline (optional)"),
        "optout_deadline": get_field(issue_body, "Opt-out deadline (optional)"),
        "hearing_date": get_field(issue_body, "Final approval hearing (optional)"),
        "settlement_amount": get_field(issue_body, "Total fund (optional)"),
        "max_payment": get_field(issue_body, "Max payment per person (optional)"),
        "nodoc_payment": get_field(issue_body, "No-doc amount (optional)"),
        "ca_payment": get_field(issue_body, "California-only amount (optional)"),
        "credit_monitoring": get_field(issue_body, "Credit monitoring (optional)"),
        "article_body": get_field(issue_body, "Main article body (optional)"),
        "eligibility": get_field(issue_body, "Eligibility checklist (optional)"),
        "how_to_file": get_field(issue_body, "How to file (steps, optional)"),
        "faqs": get_field(issue_body, "FAQs (optional)"),
        "admin_phone": get_field(issue_body, "Administrator phone (optional)"),
        "admin_email": get_field(issue_body, "Administrator email (optional)"),
        "attorney_fees": get_field(issue_body, "Attorney fees (optional)"),
        "service_awards": get_field(issue_body, "Service awards (optional)"),
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
