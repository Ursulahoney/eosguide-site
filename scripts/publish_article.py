#!/usr/bin/env python3
"""
publish_article.py
------------------
Reads a GitHub issue body and generates a full article HTML file
for eosguidehub.com. Also updates articles/index.html.

HOW IT WORKS:
  1. Reads .tmp/issue_body.md (written by the workflow from the issue body)
  2. Parses all the structured fields from the form
  3. Builds a full HTML page matching the site's eosguide style
  4. Writes to articles/{slug}.html (or articles/drafts/{slug}.html for drafts)
  5. Updates articles/index.html with a new article card (publish only)

DEPENDENCIES:
  pip install markdown
"""

import os
import re
import sys
import markdown


# ─────────────────────────────────────────────────────────────────
# STEP 1: PARSE THE ISSUE BODY
# ─────────────────────────────────────────────────────────────────

def parse_issue(body: str) -> dict:
    fields = {}
    sections = re.split(r'\n###\s+', '\n' + body)
    for section in sections:
        if not section.strip():
            continue
        lines = section.strip().split('\n')
        label = lines[0].strip().lower()
        value = '\n'.join(lines[1:]).strip()
        fields[label] = value
    return fields


def get_field(fields: dict, *possible_labels: str) -> str:
    for label in possible_labels:
        value = fields.get(label.lower(), '').strip()
        if value and value != '_No response_':
            return value
    return ''


# ─────────────────────────────────────────────────────────────────
# STEP 2: PARSE STRUCTURED COMPONENTS
# ─────────────────────────────────────────────────────────────────

def parse_eligibility(text: str) -> list:
    items = []
    for line in text.strip().split('\n'):
        line = line.strip().lstrip('-').lstrip('*').strip()
        if line:
            items.append(line)
    return items


def parse_steps(text: str) -> list:
    steps = []
    for line in text.strip().split('\n'):
        line = line.strip()
        match = re.match(r'^\d+\.\s+(.+)$', line)
        if match:
            steps.append(match.group(1).strip())
    return steps


def parse_faqs(text: str) -> list:
    faqs = []
    current_q = None
    current_a_lines = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if line.lower().startswith('q:'):
            if current_q and current_a_lines:
                faqs.append((current_q, ' '.join(current_a_lines)))
            current_q = line[2:].strip()
            current_a_lines = []
        elif line.lower().startswith('a:') and current_q:
            current_a_lines = [line[2:].strip()]
        elif line and current_a_lines is not None:
            current_a_lines.append(line)
    if current_q and current_a_lines:
        faqs.append((current_q, ' '.join(current_a_lines)))
    return faqs


def is_monetization_on(text: str) -> bool:
    return '[x]' in text.lower() or '- [x]' in text.lower()


# ─────────────────────────────────────────────────────────────────
# STEP 3: HTML COMPONENT BUILDERS
# ─────────────────────────────────────────────────────────────────

def build_eligibility_section(items: list) -> str:
    if not items:
        return ''
    rows = ''.join(f'<li>{item}</li>' for item in items)
    return f'''
    <h2>Do I Qualify?</h2>
    <div class="callout info">
      <strong>You may be eligible if:</strong>
      <ul style="margin-top:8px;padding-left:20px;list-style:disc;">
        {rows}
      </ul>
    </div>'''


def build_steps_section(steps: list) -> str:
    if not steps:
        return ''
    step_html = ''
    for i, step in enumerate(steps, 1):
        step_html += f'''
      <div class="step">
        <div class="step-num">{i}</div>
        <div class="step-body"><p>{step}</p></div>
      </div>'''
    return f'''
    <h2>How to File a Claim</h2>
    <div class="steps">
      {step_html}
    </div>'''


def build_faq_section(faqs: list) -> str:
    if not faqs:
        return ''
    items = ''
    for q, a in faqs:
        items += f'''
      <details style="border:1px solid var(--border);border-radius:var(--radius);padding:14px 16px;margin-bottom:8px;">
        <summary style="font-weight:600;cursor:pointer;color:var(--text);">{q}</summary>
        <p style="margin-top:10px;color:var(--muted);">{a}</p>
      </details>'''
    return f'''
    <h2>Frequently Asked Questions</h2>
    {items}'''


def build_faq_schema(faqs: list, canonical: str) -> str:
    if not faqs:
        return ''
    qa_items = ',\n'.join(
        f'''      {{
        "@type": "Question",
        "name": "{q.replace('"', '&quot;')}",
        "acceptedAnswer": {{
          "@type": "Answer",
          "text": "{a.replace('"', '&quot;')}"
        }}
      }}'''
        for q, a in faqs
    )
    return f'''  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": [
{qa_items}
    ]
  }}
  </script>'''


def build_monetization_block(official_website: str) -> str:
    return '''
    <div class="callout info" style="margin-top:32px;">
      <strong>Protect yourself going forward</strong>
      Consider signing up for a credit monitoring service to stay on top of your personal data.
      Many services offer free tiers that alert you to new inquiries, account openings, and dark web activity.
    </div>'''


def build_benefit_cards(max_payment: str, nodoc_payment: str, ca_payment: str, credit_monitoring: str) -> str:
    cards = ''
    if max_payment:
        cards += f'''
      <div class="benefit-card">
        <div class="benefit-label">Documented Losses</div>
        <div class="benefit-amount">{max_payment}</div>
        <div class="benefit-desc">Max reimbursement with receipts or supporting documents.</div>
      </div>'''
    if nodoc_payment:
        cards += f'''
      <div class="benefit-card">
        <div class="benefit-label">Pro Rata Cash</div>
        <div class="benefit-amount">{nodoc_payment}</div>
        <div class="benefit-desc">No documentation needed. Amount may adjust based on total claims.</div>
      </div>'''
    if ca_payment:
        cards += f'''
      <div class="benefit-card">
        <div class="benefit-label">CA Statutory (CA only)</div>
        <div class="benefit-amount">{ca_payment}</div>
        <div class="benefit-desc">Additional payment for California residents, subject to pro-rata adjustment.</div>
      </div>'''
    if credit_monitoring:
        cards += f'''
      <div class="benefit-card">
        <div class="benefit-label">Credit Monitoring</div>
        <div class="benefit-amount">{credit_monitoring}</div>
        <div class="benefit-desc">Free credit and identity monitoring included with your claim.</div>
      </div>'''
    if not cards:
        return ''
    return f'''
    <h2>What Can I Get?</h2>
    <div class="benefit-grid">
      {cards}
    </div>'''


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
          <td>Opt Out (Exclude Yourself)</td>
          <td class="date-cell">{optout_deadline}</td>
          <td>Preserves your right to sue the defendant separately</td>
        </tr>'''
    if optout_deadline:
        rows += f'''
        <tr>
          <td>Submit an Objection</td>
          <td class="date-cell">{optout_deadline}</td>
          <td>Tell the court you oppose the settlement terms</td>
        </tr>'''
    if hearing_date:
        rows += f'''
        <tr>
          <td>Final Approval Hearing</td>
          <td class="date-cell">{hearing_date}</td>
          <td>Court decides whether to approve the settlement</td>
        </tr>'''
    return f'''
    <h2>Key Deadlines</h2>
    <table class="deadline-table">
      <thead>
        <tr>
          <th>Action</th>
          <th>Deadline</th>
          <th>Why It Matters</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>
    <div class="callout warning">
      <strong>Heads up on timing</strong>
      Even after the court approves the settlement, actual payments could take a year or more if there are appeals.
      File your claim before the deadline and then be patient.
    </div>'''


# ─────────────────────────────────────────────────────────────────
# STEP 4: SIDEBAR BUILDER
# ─────────────────────────────────────────────────────────────────

def build_sidebar(f: dict) -> str:
    settlement_amount = f.get('settlement_amount', '')
    max_payment       = f.get('max_payment', '')
    nodoc_payment     = f.get('nodoc_payment', '')
    ca_payment        = f.get('ca_payment', '')
    incident_date     = f.get('incident_date', '')
    defendant         = f.get('defendant', '')
    court             = f.get('court', '')
    deadline          = f.get('deadline', '')
    optout_deadline   = f.get('optout_deadline', '')
    hearing_date      = f.get('hearing_date', '')
    official_website  = f.get('official_website', '')

    # Quick Facts rows
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
        <span class="sidebar-label">No-Doc Cash</span>
        <span class="sidebar-value">{nodoc_payment}</span>
      </div>'''
    if ca_payment:
        facts_rows += f'''
      <div class="sidebar-row">
        <span class="sidebar-label">CA Residents</span>
        <span class="sidebar-value">+{ca_payment} extra</span>
      </div>'''
    if incident_date:
        facts_rows += f'''
      <div class="sidebar-row">
        <span class="sidebar-label">Incident Date</span>
        <span class="sidebar-value">{incident_date}</span>
      </div>'''
    if defendant:
        facts_rows += f'''
      <div class="sidebar-row">
        <span class="sidebar-label">Defendant</span>
        <span class="sidebar-value">{defendant}</span>
      </div>'''
    if court:
        facts_rows += f'''
      <div class="sidebar-row">
        <span class="sidebar-label">Court</span>
        <span class="sidebar-value">{court}</span>
      </div>'''

    quick_facts = f'''
    <div class="sidebar-card">
      <div class="sidebar-card-header green">Quick Facts</div>
      {facts_rows}
    </div>''' if facts_rows else ''

    # Deadline card
    deadline_rows = ''
    if deadline:
        deadline_rows += f'''
      <div class="sidebar-row">
        <span class="sidebar-label">File By</span>
        <span class="sidebar-value amber">{deadline}</span>
      </div>'''
    if optout_deadline:
        deadline_rows += f'''
      <div class="sidebar-row">
        <span class="sidebar-label">Opt-Out By</span>
        <span class="sidebar-value">{optout_deadline}</span>
      </div>'''
    if hearing_date:
        deadline_rows += f'''
      <div class="sidebar-row">
        <span class="sidebar-label">Final Hearing</span>
        <span class="sidebar-value">{hearing_date}</span>
      </div>'''

    deadline_card = f'''
    <div class="sidebar-card">
      <div class="sidebar-card-header amber">&#9888; Claim Deadline</div>
      {deadline_rows}
    </div>''' if deadline_rows else ''

    # CTA card
    cta_card = ''
    if official_website:
        display = official_website.replace('https://', '').replace('http://', '').rstrip('/')
        cta_card = f'''
    <div class="sidebar-card">
      <div class="sidebar-card-header">Official Resources</div>
      <div class="sidebar-cta">
        <a class="cta-btn" href="{official_website}" target="_blank" rel="noopener noreferrer">File a Claim</a>
        <a class="cta-btn secondary" href="{official_website}" target="_blank" rel="noopener noreferrer">Settlement Website</a>
      </div>
      <p class="sidebar-disclaimer">eosguide is a directory. We don\'t run this settlement. Always verify details at the official site.</p>
    </div>'''

    return quick_facts + deadline_card + cta_card


# ─────────────────────────────────────────────────────────────────
# STEP 5: ASSEMBLE THE FULL PAGE
# ─────────────────────────────────────────────────────────────────

def build_page(f: dict) -> str:
    title            = f.get('title', 'Article')
    slug             = f.get('slug', 'article')
    blurb            = f.get('blurb', '')
    deadline         = f.get('deadline', '')
    last_updated     = f.get('last_updated', '')
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
    show_monetization = is_monetization_on(f.get('monetization', ''))

    # Convert Markdown body to HTML
    body_html = markdown.markdown(
        article_body,
        extensions=['tables', 'fenced_code']
    ) if article_body else ''

    # Build components
    benefit_cards     = build_benefit_cards(max_payment, nodoc_payment, ca_payment, credit_monitoring)
    deadline_table    = build_deadline_table(deadline, optout_deadline, hearing_date)
    eligibility_block = build_eligibility_section(eligibility_items)
    steps_block       = build_steps_section(steps)
    faq_block         = build_faq_section(faqs)
    monetization_block = build_monetization_block(official_website) if show_monetization else ''
    sidebar_html      = build_sidebar(f)

    # Hero image
    hero_html = ''
    if hero_image:
        credit_html = f'<p style="font-size:12px;color:var(--muted);margin-top:6px;">{hero_credit}</p>' if hero_credit else ''
        hero_html = f'''
      <img src="/assets/articles/{hero_image}" alt="{title}"
           style="width:100%;border-radius:var(--radius);margin-bottom:4px;">
      {credit_html}'''

    # CTA buttons in article body
    cta_buttons = ''
    if official_website:
        cta_buttons = f'''
      <a class="cta-btn" href="{official_website}" target="_blank" rel="noopener noreferrer">
        &#8594; File a Claim at Official Site
      </a>'''

    # Canonical and meta
    canonical = f"https://eosguidehub.com/articles/{slug}.html"
    og_image  = f"https://eosguidehub.com/assets/articles/{hero_image}" if hero_image else "https://eosguidehub.com/Circular-badge-logo.png"
    encoded_title = title.replace(' ', '%20').replace(':', '%3A')

    # FAQ schema
    faq_schema = build_faq_schema(faqs, canonical)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />

  <!-- Primary SEO -->
  <title>{title} | eosguide</title>
  <meta name="description" content="{blurb}" />
  <link rel="canonical" href="{canonical}" />
  <link rel="icon" href="/Circular-badge-logo.png" type="image/png" />

  <!-- Open Graph -->
  <meta property="og:type" content="article" />
  <meta property="og:title" content="{title}" />
  <meta property="og:description" content="{blurb}" />
  <meta property="og:url" content="{canonical}" />
  <meta property="og:image" content="{og_image}" />
  <meta property="og:site_name" content="eosguide" />

  <!-- Twitter Card -->
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{title}" />
  <meta name="twitter:description" content="{blurb}" />

  <!-- Article Schema -->
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "{title.replace('"', '&quot;')}",
    "description": "{blurb.replace('"', '&quot;')}",
    "dateModified": "{last_updated}",
    "author": {{"@type": "Organization", "name": "eosguide", "url": "https://eosguidehub.com"}},
    "publisher": {{"@type": "Organization", "name": "eosguide", "url": "https://eosguidehub.com"}},
    "mainEntityOfPage": {{"@type": "WebPage", "@id": "{canonical}"}}
  }}
  </script>
  {faq_schema}

  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,600;0,700;1,400&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet" />

  <style>
    :root {{
      --bg:          #F9F8F5;
      --surface:     #FFFFFF;
      --border:      #E8E5DF;
      --text:        #1C1A17;
      --muted:       #6B6560;
      --accent:      #2A6B4A;
      --accent-soft: #EAF4EE;
      --amber:       #C8782A;
      --amber-soft:  #FDF3E7;
      --radius:      10px;
      --max-w:       1080px;
    }}

    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      background: var(--bg);
      color: var(--text);
      font-family: 'DM Sans', sans-serif;
      font-size: 16px;
      line-height: 1.7;
      -webkit-font-smoothing: antialiased;
    }}

    /* Header */
    .site-header {{
      border-bottom: 1px solid var(--border);
      background: var(--surface);
      padding: 0 24px;
    }}
    .site-header-inner {{
      max-width: var(--max-w);
      margin: 0 auto;
      display: flex;
      align-items: center;
      gap: 12px;
      height: 56px;
    }}
    .logo {{
      font-family: 'Lora', serif;
      font-weight: 700;
      font-size: 18px;
      color: var(--text);
      text-decoration: none;
    }}
    .logo span {{ color: var(--accent); }}
    .breadcrumb {{
      margin-left: auto;
      font-size: 13px;
      color: var(--muted);
    }}
    .breadcrumb a {{ color: var(--accent); text-decoration: none; }}

    /* Layout */
    .layout {{
      max-width: var(--max-w);
      margin: 0 auto;
      padding: 40px 24px 80px;
      display: grid;
      grid-template-columns: 1fr 300px;
      gap: 48px;
      align-items: start;
    }}

    /* Article meta */
    .article-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      margin-bottom: 20px;
    }}
    .meta-date {{ font-size: 13px; color: var(--muted); }}

    /* Title */
    h1.article-title {{
      font-family: 'Lora', serif;
      font-size: clamp(26px, 4vw, 38px);
      font-weight: 700;
      line-height: 1.2;
      margin-bottom: 16px;
      letter-spacing: -.02em;
    }}

    /* Deck */
    .article-deck {{
      font-size: 17px;
      color: var(--muted);
      line-height: 1.6;
      margin-bottom: 28px;
      border-left: 3px solid var(--accent);
      padding-left: 16px;
    }}

    /* Section headings */
    .article h2 {{
      font-family: 'Lora', serif;
      font-size: 22px;
      font-weight: 600;
      margin: 40px 0 14px;
      letter-spacing: -.01em;
    }}
    .article h3 {{
      font-size: 16px;
      font-weight: 600;
      margin: 24px 0 8px;
      color: var(--accent);
    }}
    .article p {{ margin-bottom: 16px; }}
    .article ul, .article ol {{ padding-left: 20px; margin-bottom: 16px; }}
    .article li {{ margin-bottom: 6px; }}
    .article a {{ color: var(--accent); text-decoration: underline; }}
    .article strong {{ font-weight: 600; }}
    .article table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14.5px; }}
    .article th {{ background: var(--bg); padding: 8px 12px; text-align: left; font-size: 11px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); border-bottom: 2px solid var(--border); }}
    .article td {{ padding: 12px; border-bottom: 1px solid var(--border); vertical-align: top; }}

    /* Divider */
    .divider {{ border: none; border-top: 1px solid var(--border); margin: 32px 0; }}

    /* Benefit cards */
    .benefit-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 12px;
      margin: 20px 0;
    }}
    .benefit-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 18px;
    }}
    .benefit-label {{ font-size: 11px; font-weight: 600; letter-spacing: .07em; text-transform: uppercase; color: var(--muted); margin-bottom: 6px; }}
    .benefit-amount {{ font-family: 'Lora', serif; font-size: 26px; font-weight: 700; color: var(--accent); }}
    .benefit-desc {{ font-size: 13px; color: var(--muted); margin-top: 6px; line-height: 1.5; }}

    /* Deadline table */
    .deadline-table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14.5px; }}
    .deadline-table th {{ text-align: left; font-size: 11px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); padding: 8px 12px; border-bottom: 2px solid var(--border); }}
    .deadline-table td {{ padding: 12px; border-bottom: 1px solid var(--border); vertical-align: top; }}
    .deadline-table tr:last-child td {{ border-bottom: none; }}
    .deadline-table td:first-child {{ font-weight: 500; }}
    .date-cell {{ font-weight: 600; white-space: nowrap; }}
    .urgent {{ color: var(--amber); }}
    .deadline-table tr:hover td {{ background: var(--bg); }}

    /* Steps */
    .steps {{ margin: 16px 0; }}
    .step {{ display: flex; gap: 16px; margin-bottom: 20px; align-items: flex-start; }}
    .step-num {{
      flex-shrink: 0; width: 32px; height: 32px; border-radius: 50%;
      background: var(--accent); color: white; font-size: 14px; font-weight: 700;
      display: flex; align-items: center; justify-content: center;
    }}
    .step-body {{ flex: 1; }}
    .step-body strong {{ display: block; margin-bottom: 4px; }}
    .step-body p {{ margin: 0; }}

    /* Callouts */
    .callout {{
      border-radius: var(--radius);
      padding: 16px 20px;
      margin: 20px 0;
      font-size: 14.5px;
      line-height: 1.6;
    }}
    .callout.info {{ background: var(--accent-soft); border-left: 4px solid var(--accent); }}
    .callout.warning {{ background: var(--amber-soft); border-left: 4px solid var(--amber); }}
    .callout strong {{ display: block; margin-bottom: 4px; font-size: 13px; text-transform: uppercase; letter-spacing: .05em; }}

    /* CTA buttons */
    .cta-btn {{
      display: inline-flex; align-items: center; gap: 8px;
      background: var(--accent); color: white; font-weight: 600; font-size: 15px;
      padding: 12px 24px; border-radius: var(--radius); text-decoration: none;
      margin: 8px 8px 8px 0; transition: opacity .15s;
    }}
    .cta-btn:hover {{ opacity: .88; }}
    .cta-btn.secondary {{
      background: var(--surface); color: var(--text);
      border: 1.5px solid var(--border);
    }}

    /* Sidebar */
    .sidebar {{ position: sticky; top: 24px; }}
    .sidebar-card {{
      background: var(--surface); border: 1px solid var(--border);
      border-radius: var(--radius); overflow: hidden; margin-bottom: 16px;
    }}
    .sidebar-card-header {{
      background: var(--text); color: white; padding: 14px 18px;
      font-size: 12px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase;
    }}
    .sidebar-card-header.green {{ background: var(--accent); }}
    .sidebar-card-header.amber {{ background: var(--amber); }}
    .sidebar-row {{
      padding: 14px 18px; border-bottom: 1px solid var(--border);
      display: flex; flex-direction: column; gap: 2px;
    }}
    .sidebar-row:last-child {{ border-bottom: none; }}
    .sidebar-label {{ font-size: 11px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); }}
    .sidebar-value {{ font-size: 15px; font-weight: 500; color: var(--text); }}
    .sidebar-value.accent {{ color: var(--accent); font-family: 'Lora', serif; font-size: 18px; font-weight: 700; }}
    .sidebar-value.amber {{ color: var(--amber); font-weight: 700; }}
    .sidebar-cta {{ padding: 18px; display: flex; flex-direction: column; gap: 8px; }}
    .sidebar-cta .cta-btn {{ width: 100%; justify-content: center; margin: 0; }}
    .sidebar-disclaimer {{ font-size: 11.5px; color: var(--muted); text-align: center; padding: 0 18px 14px; line-height: 1.5; }}

    /* Footer */
    .site-footer {{
      background: var(--text); color: #ccc;
      padding: 40px 24px; font-size: 13px; line-height: 1.6;
    }}
    .site-footer-inner {{
      max-width: var(--max-w); margin: 0 auto;
      display: flex; flex-wrap: wrap; gap: 24px; justify-content: space-between;
    }}
    .site-footer a {{ color: #aaa; text-decoration: underline; }}

    /* Mobile */
    @media (max-width: 720px) {{
      .layout {{ grid-template-columns: 1fr; padding: 24px 16px 60px; gap: 32px; }}
      .sidebar {{ position: static; }}
      .benefit-grid {{ grid-template-columns: 1fr 1fr; }}
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

    {cta_buttons}

    <hr class="divider" />

    {faq_block}

    {monetization_block}

    <hr class="divider" />

    <div class="callout info">
      <strong>eosguide is a directory, not a law firm</strong>
      This article summarizes public information from the official settlement notice.
      We don't administer this settlement or give legal advice.
      Always verify details at the official settlement website before filing.
      Only file a claim if you actually qualify.
    </div>

  </main>

  <aside class="sidebar" aria-label="Settlement quick facts">
    {sidebar_html}
  </aside>

</div>

<footer class="site-footer">
  <div class="site-footer-inner">
    <div>
      <strong style="color:white;">eos<span style="color:var(--accent);">guide</span></strong><br />
      We keep an eye on settlements, refunds, and relief programs so you don't have to.
    </div>
    <div>
      <a href="/legal/">Legal</a> &nbsp;&bull;&nbsp;
      <a href="/legal/#privacy">Privacy</a> &nbsp;&bull;&nbsp;
      <a href="/legal/#terms">Terms</a>
      <br />
      &copy; 2026 eosguide. Information only. Not legal or financial advice.
    </div>
  </div>
</footer>

</body>
</html>"""


# ─────────────────────────────────────────────────────────────────
# STEP 6: UPDATE THE ARTICLES INDEX PAGE
# ─────────────────────────────────────────────────────────────────

INSERT_MARKER = '<!-- ARTICLES_LIST_INSERT_HERE -->'

def update_index(slug: str, title: str, deadline: str, last_updated: str, blurb: str) -> None:
    index_path = 'articles/index.html'
    if not os.path.exists(index_path):
        print(f"Warning: {index_path} not found — skipping index update.")
        return

    content = open(index_path, 'r', encoding='utf-8').read()

    deadline_text = f'Deadline: {deadline} &bull; ' if deadline and deadline.lower() != 'none listed' else ''
    new_card = f"""
<article class="bg-white rounded-2xl shadow-sm p-5">
  <h2 class="text-xl font-bold text-gray-900 mb-1">
    <a href="/articles/{slug}.html" class="hover:underline">{title}</a>
  </h2>
  <p class="text-sm text-gray-600 mb-2">{deadline_text}Updated {last_updated}</p>
  <p class="text-gray-700">{blurb}</p>
</article>
"""

    if f'/articles/{slug}.html' in content:
        print(f"Article {slug} already in index — skipping.")
        return

    updated = content.replace(INSERT_MARKER, INSERT_MARKER + new_card)
    open(index_path, 'w', encoding='utf-8').write(updated)
    print(f"✓ Added {slug} to articles/index.html")


# ─────────────────────────────────────────────────────────────────
# STEP 7: MAIN
# ─────────────────────────────────────────────────────────────────

def main():
    issue_body_path = os.environ.get('ISSUE_BODY_PATH', '.tmp/issue_body.md')
    if not os.path.exists(issue_body_path):
        print(f"Error: Issue body not found at {issue_body_path}")
        sys.exit(1)

    body = open(issue_body_path, 'r', encoding='utf-8').read()
    raw = parse_issue(body)

    fields = {
        'title':             get_field(raw, 'article title'),
        'slug':              get_field(raw, 'url slug'),
        'blurb':             get_field(raw, 'short blurb'),
        'deadline':          get_field(raw, 'claim deadline', 'deadline'),
        'optout_deadline':   get_field(raw, 'opt-out deadline'),
        'hearing_date':      get_field(raw, 'final approval hearing date'),
        'last_updated':      get_field(raw, 'last updated'),
        'settlement_amount': get_field(raw, 'total settlement fund'),
        'max_payment':       get_field(raw, 'maximum payment per person'),
        'nodoc_payment':     get_field(raw, 'no-documentation cash payment'),
        'ca_payment':        get_field(raw, 'california statutory payment'),
        'credit_monitoring': get_field(raw, 'credit monitoring'),
        'official_website':  get_field(raw, 'official settlement website'),
        'defendant':         get_field(raw, 'defendant / company name', 'defendant'),
        'incident_date':     get_field(raw, 'when did the incident occur?', 'incident date'),
        'court':             get_field(raw, 'court & jurisdiction', 'court'),
        'hero_image':        get_field(raw, 'hero image filename'),
        'hero_credit':       get_field(raw, 'hero image credit (optional)', 'hero image credit'),
        'eligibility':       get_field(raw, 'who is eligible? (bulleted list)', 'who is eligible?'),
        'how_to_file':       get_field(raw, 'how to file a claim (numbered steps)', 'how to file a claim'),
        'faqs':              get_field(raw, 'frequently asked questions', 'faqs'),
        'article_body':      get_field(raw, 'article body (markdown)', 'article body'),
        'monetization':      get_field(raw, 'monetization'),
        'status':            get_field(raw, 'publish status'),
    }

    if not fields['title'] or not fields['slug']:
        print("Error: 'Article title' and 'URL slug' are required.")
        sys.exit(1)

    mode = os.environ.get('MODE', 'draft').lower()
    html = build_page(fields)

    if mode == 'publish':
        os.makedirs('articles', exist_ok=True)
        out_path = f"articles/{fields['slug']}.html"
    else:
        os.makedirs('articles/drafts', exist_ok=True)
        out_path = f"articles/drafts/{fields['slug']}.html"

    open(out_path, 'w', encoding='utf-8').write(html)
    print(f"✓ Article written to {out_path}")

    if mode == 'publish':
        update_index(
            slug=fields['slug'],
            title=fields['title'],
            deadline=fields['deadline'],
            last_updated=fields['last_updated'],
            blurb=fields['blurb'],
        )


if __name__ == '__main__':
    main()
