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
        # Convert inline markdown links to HTML
        line = re.sub(r'\[([^\]]+)\]\((mailto:[^\)]+)\)', r'<a href="\2">\1</a>', line)
        line = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)', r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>', line)
        out.append(line)
    return out


def parse_faqs(text: str) -> list[tuple[str, str]]:
    """
    Accepts repeated pairs like:

    Q: question
    A: answer
    Q: question
    A: answer

    Blank lines are optional. Extra lines after A: are included in the answer
    until the next Q: is found.
    """
    if not text:
        return []

    faqs: list[tuple[str, str]] = []
    q = ""
    a_lines: list[str] = []
    mode = None  # "q" or "a"

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            # keep blank lines inside answers (optional)
            if mode == "a":
                a_lines.append("")
            continue

        low = line.lower()

        if low.startswith("q:"):
            # save previous pair if complete
            if q and a_lines:
                a = " ".join([x for x in a_lines if x != ""]).strip()
                faqs.append((q.strip(), a))
            q = line[2:].strip()
            a_lines = []
            mode = "q"
            continue

        if low.startswith("a:"):
            mode = "a"
            a_lines.append(line[2:].strip())
            continue

        # continuation lines
        if mode == "q":
            q += " " + line
        elif mode == "a":
            a_lines.append(line)
        else:
            # if no Q:/A: yet, ignore stray text
            pass

    # flush last pair
    if q and a_lines:
        a = " ".join([x for x in a_lines if x != ""]).strip()
        faqs.append((q.strip(), a))

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
        return f"""
        <div class="glance-row">
          <span class="glance-label">{label}</span>
          <span class="glance-value">{value_html}</span>
        </div>"""

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

    return f"""
    <section class="glance-card" aria-label="At a glance">
      <h2 class="section-title">At a glance</h2>
      <div class="glance-grid">{rows}</div>
    </section>
    """


def build_key_dates_table(f: dict) -> str:
    deadline = f.get("deadline", "")
    optout = f.get("optout_deadline", "")
    objection = f.get("objection_deadline", "")
    hearing = f.get("hearing_date", "")

    if not any([deadline, optout, objection, hearing]):
        return ""

    rows = ""
    if deadline:
        rows += f"""
        <tr>
          <td>Submit / Claim</td>
          <td class="date-cell urgent">{deadline}</td>
          <td>Last day to submit</td>
        </tr>"""
    if optout:
        rows += f"""
        <tr>
          <td>Opt out</td>
          <td class="date-cell">{optout}</td>
          <td>Keep your right to sue separately</td>
        </tr>"""
    if objection:
        rows += f"""
        <tr>
          <td>Object</td>
          <td class="date-cell">{objection}</td>
          <td>Tell the court you disagree</td>
        </tr>"""
    if hearing:
        rows += f"""
        <tr>
          <td>Final hearing</td>
          <td class="date-cell">{hearing}</td>
          <td>Judge decides whether to approve</td>
        </tr>"""

    return f"""
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
    """


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

        big = value if value else (notes if notes else "")
        small = notes if (value and notes) else ""

        cards += f"""
        <div class="benefit-card">
          <h3>{label or "Benefit"}</h3>
          <p class="big">{big}</p>
          {f'<p class="small">{small}</p>' if small else ''}
        </div>
        """

    if not cards:
        return ""

    return f"""
    <section class="section">
      <h2 class="section-title">What you can get</h2>
      <div class="benefit-grid">
        {cards}
      </div>
    </section>
    """


def build_bullets_section(title: str, items: list[str]) -> str:
    if not items:
        return ""
    lis = "".join([f"<li>{i}</li>" for i in items])
    return f"""
    <section class="section">
      <h2 class="section-title">{title}</h2>
      <ul class="bullets">{lis}</ul>
    </section>
    """


def build_steps_section(title: str, steps: list[str]) -> str:
    if not steps:
        return ""
    lis = "".join([f"<li>{s}</li>" for s in steps])
    return f"""
    <section class="section">
      <h2 class="section-title">{title}</h2>
      <ol class="steps">{lis}</ol>
    </section>
    """


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

    return f"""
    <section class="section">
      <h2 class="section-title">Important links</h2>
      <ul class="bullets">{items}</ul>
    </section>
    """


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

    return f"""
    <section class="section">
      <h2 class="section-title">Contact</h2>
      <div class="callout">{rows}</div>
    </section>
    """


def build_faq_section(faqs: list[tuple[str, str]]) -> str:
    if not faqs:
        return ""
    blocks = ""
    for q, a in faqs:
        blocks += f"""
      <details class="faq">
        <summary>{q}</summary>
        <div class="faq-a">{a}</div>
      </details>"""
    return f"""
    <section class="section">
      <h2 class="section-title">FAQ</h2>
      {blocks}
    </section>
    """


def build_cta_buttons(official_website: str, deadline: str) -> str:
    if not official_website:
        return ""
    deadline_note = f" (deadline: {deadline})" if deadline else ""
    return f"""
    <div class="cta-row">
      <a class="btn primary" href="{official_website}" target="_blank" rel="noopener noreferrer">
        Go to official website{deadline_note}
      </a>
      <a class="btn" href="/articles/">Browse more articles</a>
    </div>
    """


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

    meta_description = blurb.strip().replace("\n", " ")
    meta_description = meta_description[:155].rstrip()
    canonical = f"https://eosguidehub.com/articles/{slug}.html"

    class_period_html = f"<p><strong>Class period:</strong> {class_period}</p>" if class_period else ""
    payment_timing_html = f"<p>{payment_timing}</p>" if payment_timing else ""

    what_happened_section = ""
    if what_happened_html or class_period_html:
        what_happened_section = f"""
        <section class="section">
          <h2 class="section-title">What happened</h2>
          {class_period_html}
          {what_happened_html}
        </section>
        """

    extra_details_section = ""
    if extra_details_html:
        extra_details_section = f"""
        <section class="section">
          <h2 class="section-title">Extra details</h2>
          {extra_details_html}
        </section>
        """

    payment_section = ""
    if payment_timing_html:
        payment_section = f"""
        <section class="section">
          <h2 class="section-title">Payment timing</h2>
          {payment_timing_html}
        </section>
        """

    deadline_banner = ""
    if f.get("deadline"):
        claim_url = f.get("claim_form_url") or official_website
        deadline_banner = f"""
        <div class="bg-red-50 border-l-4 border-red-500 p-5 mb-6 rounded-r-xl">
          <div class="flex items-center mb-2">
            <svg class="w-5 h-5 text-red-500 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd"/>
            </svg>
            <span class="font-bold text-red-800">Deadline: {f["deadline"]}</span>
          </div>
          {"" if not claim_url else f'<a href="{claim_url}" target="_blank" rel="noopener noreferrer" class="inline-block bg-red-600 text-white px-5 py-2 rounded-lg font-semibold hover:bg-red-700 transition text-sm no-underline">File Your Claim Now →</a>'}
        </div>"""

    share_buttons = f"""
        <div class="mt-8 pt-6 border-t border-gray-200">
          <p class="text-sm font-semibold text-gray-700 mb-3">Share this:</p>
          <div class="flex flex-wrap gap-2 text-sm">
            <button type="button" id="copyLinkBtn"
              class="px-3 py-2 rounded-xl bg-gray-100 hover:bg-gray-200 transition text-gray-700 font-medium">
              Copy link
            </button>
            <a class="px-3 py-2 rounded-xl bg-gray-100 hover:bg-gray-200 transition text-gray-700 font-medium"
               target="_blank" rel="noopener"
               href="https://twitter.com/intent/tweet?url={canonical}&text={title}">
              X / Twitter
            </a>
            <a class="px-3 py-2 rounded-xl bg-gray-100 hover:bg-gray-200 transition text-gray-700 font-medium"
               target="_blank" rel="noopener"
               href="https://www.facebook.com/sharer/sharer.php?u={canonical}">
              Facebook
            </a>
          </div>
          <p id="copyStatus" class="text-xs text-gray-500 mt-2" aria-live="polite"></p>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">

  <title>{title} | eosguide</title>
  <meta name="description" content="{meta_description}">
  <link rel="canonical" href="{canonical}">
  <link rel="icon" href="/Circular-badge-logo.png" type="image/png">

  <meta property="og:type" content="article">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{meta_description}">
  <meta property="og:url" content="{canonical}">
  {"" if not hero_image else f'<meta property="og:image" content="{hero_image}">'}

  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{title}">
  <meta name="twitter:description" content="{meta_description}">

  <script src="https://cdn.tailwindcss.com"></script>

  <style>
    /* Article section styles */
    .section {{ margin: 1.5rem 0; }}
    .section-title {{ font-size: 1.15rem; font-weight: 800; margin: 0 0 0.75rem; color: #111827; letter-spacing: -0.01em; }}
    .divider {{ border: none; border-top: 1px solid #e5e7eb; margin: 1.5rem 0; }}

    .table-wrap {{ overflow-x: auto; border: 1px solid #e5e7eb; border-radius: 14px; background: #fafaf9; }}
    .deadline-table {{ width: 100%; border-collapse: collapse; min-width: 500px; }}
    .deadline-table th, .deadline-table td {{ padding: 10px 12px; border-bottom: 1px solid #e5e7eb; text-align: left; vertical-align: top; font-size: 14px; }}
    .deadline-table th {{ background: #f5f5f4; color: #6b7280; font-weight: 700; }}
    .date-cell.urgent {{ color: #b91c1c; font-weight: 800; }}

    .benefit-grid {{ display: grid; grid-template-columns: 1fr; gap: 12px; margin-top: 10px; }}
    .benefit-card {{ background: #fafaf9; border: 1px solid #e5e7eb; border-radius: 16px; padding: 14px; }}
    .benefit-card h3 {{ margin: 0 0 4px; font-size: 0.9rem; color: #6b7280; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }}
    .benefit-card .big {{ margin: 0; font-size: 1.1rem; font-weight: 800; color: #111827; }}
    .benefit-card .small {{ margin: 6px 0 0; color: #6b7280; font-size: 0.9rem; }}

    .glance-card {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 18px; padding: 16px; margin: 16px 0; box-shadow: 0 4px 16px rgba(0,0,0,0.05); }}
    .glance-grid {{ display: grid; gap: 8px; margin-top: 10px; }}
    .glance-row {{ display: grid; grid-template-columns: 130px 1fr; gap: 8px; padding: 9px 12px; border-radius: 12px; background: #fafaf9; border: 1px solid #e5e7eb; }}
    .glance-label {{ font-weight: 700; color: #6b7280; font-size: 0.88rem; padding-top: 1px; }}
    .glance-value {{ font-weight: 600; color: #111827; font-size: 0.95rem; overflow-wrap: anywhere; }}
    .glance-value a {{ color: #2563eb; }}

    .bullets {{ padding-left: 1.25rem; }}
    .bullets li {{ margin: 6px 0; font-size: 0.95rem; color: #374151; }}
    .steps {{ padding-left: 1.25rem; }}
    .steps li {{ margin: 8px 0; font-size: 0.95rem; color: #374151; }}

    .callout {{ border-radius: 14px; padding: 14px 16px; border: 1px solid #e5e7eb; background: #fafaf9; }}
    .mini-row {{ margin-bottom: 6px; font-size: 0.9rem; color: #374151; }}

    .cta-row {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 1.5rem; }}
    .btn {{ border: 1px solid #d1d5db; border-radius: 999px; padding: 10px 18px; font-weight: 700; font-size: 0.9rem; background: #fafaf9; color: #111827; display: inline-flex; align-items: center; gap: 6px; text-decoration: none; transition: all 0.2s; }}
    .btn:hover {{ background: #f3f4f6; text-decoration: none; }}
    .btn.primary {{ background: #dcfce7; border-color: #86efac; color: #14532d; }}
    .btn.primary:hover {{ background: #bbf7d0; }}

    details.faq {{ border: 1px solid #e5e7eb; border-radius: 14px; padding: 12px 14px; background: #fafaf9; margin: 8px 0; }}
    details.faq summary {{ cursor: pointer; font-weight: 700; font-size: 0.95rem; color: #111827; list-style: none; display: flex; justify-content: space-between; align-items: center; }}
    details.faq summary::-webkit-details-marker {{ display: none; }}
    details.faq summary::after {{ content: '+'; font-size: 1.2rem; color: #6b7280; flex-shrink: 0; margin-left: 8px; }}
    details[open].faq summary::after {{ content: '−'; }}
    .faq-a {{ margin-top: 10px; color: #374151; font-size: 0.93rem; line-height: 1.6; padding-top: 10px; border-top: 1px solid #e5e7eb; }}

    @media (min-width: 768px) {{
      .benefit-grid {{ grid-template-columns: repeat(2, 1fr); }}
      .glance-row {{ grid-template-columns: 140px 1fr; }}
    }}
  </style>
</head>

<body class="min-h-screen bg-gradient-to-br from-cyan-50 via-purple-50 to-pink-50">

  <!-- Header -->
  <header class="relative z-10 px-4 py-6 sm:px-6 lg:px-8">
    <nav class="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center md:justify-between gap-4">
      <div class="flex flex-col md:flex-row md:items-center gap-3 md:gap-6 group cursor-pointer">
        <div class="relative flex-shrink-0">
          <a href="/" aria-label="Back to eosguide home">
            <img src="/Circular-badge-logo.png" alt="eosguide logo" class="w-28 h-28 sm:w-32 sm:h-32 md:w-40 md:h-40">
          </a>
        </div>
        <blockquote class="text-xs sm:text-sm md:text-base font-semibold italic leading-snug text-gray-500 max-w-xs md:max-w-sm text-center md:text-left"
                    style="font-family: 'DM Sans', 'Montserrat', system-ui, sans-serif;">
          "We do the searching<br>so you don't have to<br>pretend it's fun."
        </blockquote>
      </div>
      <div class="flex flex-col items-center gap-2 self-center md:self-auto">
        <button onclick="openNewsletter()"
                class="flex items-center space-x-2 px-6 py-3 text-white rounded-full font-semibold hover:shadow-lg hover:scale-105 transition-all duration-300"
                style="background: linear-gradient(135deg, #FF6B35 0%, #FF8C42 100%);">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
          </svg>
          <span>Get Alerts</span>
        </button>
        <a href="/articles/"
           class="text-sm font-semibold text-purple-600 hover:text-purple-700 px-3 py-1 rounded-full hover:bg-purple-50 flex items-center gap-1 transition">
          <span>Articles</span>
          <span aria-hidden="true">→</span>
        </a>
      </div>
    </nav>
  </header>

  <!-- Main content -->
  <main class="relative z-10 px-4 sm:px-6 lg:px-8 pb-16">
    <article class="max-w-3xl mx-auto bg-white rounded-3xl shadow-sm p-6 sm:p-8" id="main-content">

      <div class="mb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        {"" if not f.get("deadline") else f'<div class="text-sm text-gray-700"><span class="font-semibold">Deadline:</span> {f["deadline"]}</div>'}
        <div class="text-sm text-gray-500"><span class="font-semibold">Last updated:</span> {last_updated}</div>
      </div>

      <h1 class="text-3xl sm:text-4xl font-black text-gray-900 mb-3 leading-tight">{title}</h1>
      <p class="text-gray-600 mb-6 italic text-base leading-relaxed">{blurb}</p>

      {deadline_banner}

      {hero_html}

      {at_a_glance_html}

      <hr class="divider">

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

      <hr class="divider">

      {faq_html}

      <hr class="divider">

      <div class="callout">
        <strong class="font-bold text-gray-900 block mb-1">Use the official website</strong>
        <span class="text-sm text-gray-600">Always confirm details on the official site. If something feels off, stop and verify before sharing personal info.</span>
      </div>

      <p class="mt-6 text-xs text-gray-500">
        Info only. Verify details on the official site. Not legal, financial, or tax advice.
        <a href="/legal/" class="underline">Legal</a>
      </p>

      {share_buttons}

    </article>
  </main>

  <!-- Footer -->
<footer class="relative z-10 bg-gradient-to-br from-gray-900 to-gray-800 text-white py-12 px-4 sm:px-6 lg:px-8">
  <div class="max-w-7xl mx-auto">

    <div class="grid md:grid-cols-3 gap-8 mb-8 items-start">
      
      <!-- Left: Brand -->
      <div>
        <h4 class="font-black text-xl mb-4 bg-gradient-to-r from-cyan-300 via-purple-300 to-pink-300 bg-clip-text text-transparent">
          eosguide
        </h4>
        <p class="text-gray-400 text-sm font-light">
          We keep an eye on refunds, relief, and "you might have money out there" programs so you don't have to chase every headline.
        </p>
      </div>

      <!-- Center: Contact -->
      <div class="text-center">
        <p class="text-gray-300 text-sm font-light">
          Have a question, suggestion, or request?
        </p>
        <p class="text-gray-200 text-sm font-light">
          Email:
          <a href="mailto:hello@eosguidehub.com" class="text-cyan-300 hover:text-cyan-400 underline">
            hello@eosguidehub.com
          </a>
        </p>
      </div>

      <!-- Right: Disclaimer -->
      <div class="text-center md:text-right">
        <p class="text-gray-300 text-sm font-light">
          © 2025 eosguide. Information only. We're not affiliated with the programs we link to and we don't give legal, financial, or tax advice.
        </p>
      </div>

    </div>

    <!-- Bottom Links -->
    <div class="mt-4 text-sm flex flex-wrap gap-3 md:justify-start justify-center">
      <a href="/legal/" class="text-cyan-300 hover:text-cyan-400 underline">Legal</a>
      <span class="text-gray-500">•</span>
      <a href="/legal/#privacy" class="text-cyan-300 hover:text-cyan-400 underline">Privacy</a>
      <span class="text-gray-500">•</span>
      <a href="/legal/#terms" class="text-cyan-300 hover:text-cyan-400 underline">Terms</a>
      <span class="text-gray-500">•</span>
      <a href="/legal/#disclaimer" class="text-cyan-300 hover:text-cyan-400 underline">Disclaimer</a>
    </div>

  </div>
</footer>

  <!-- Newsletter Modal -->
  <div id="newsletterModal" class="hidden fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
    <div class="bg-white rounded-3xl p-8 max-w-md w-full relative shadow-2xl">
      <button onclick="closeNewsletter()" class="absolute top-4 right-4 p-2 hover:bg-gray-100 rounded-full transition-colors" aria-label="Close">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
        </svg>
      </button>
      <div class="text-center mb-6">
        <div class="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4"
             style="background: linear-gradient(135deg, #06B6D4 0%, #8B5CF6 50%, #EC4899 100%);">
          <svg class="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
          </svg>
        </div>
        <h3 class="text-3xl font-black mb-2">Get alerts</h3>
        <p class="text-gray-600 font-normal">New settlement and refund updates. No spam.</p>
      </div>
      <form action="https://buttondown.com/api/emails/embed-subscribe/eosguidehub" method="post" class="space-y-4">
        <input type="hidden" name="embed" value="1">
        <input type="email" name="email" id="emailInput" placeholder="Enter your email" required
               class="w-full px-4 py-3 rounded-2xl border-2 border-gray-200 focus:border-purple-500 focus:outline-none transition-colors font-light">
        <button type="submit"
                class="w-full px-6 py-3 text-white rounded-2xl font-bold hover:shadow-lg hover:scale-105 transition-all duration-300"
                style="background: linear-gradient(135deg, #FF6B35 0%, #FF8C42 100%);">
          Subscribe free
        </button>
      </form>
      <p class="text-xs text-gray-500 text-center mt-4 font-light">Unsubscribe anytime.</p>
    </div>
  </div>

  <script>
    function openNewsletter() {{
      const modal = document.getElementById('newsletterModal');
      if (!modal) return;
      modal.classList.remove('hidden');
      const email = document.getElementById('emailInput');
      if (email) setTimeout(() => email.focus(), 50);
    }}
    function closeNewsletter() {{
      const modal = document.getElementById('newsletterModal');
      if (!modal) return;
      modal.classList.add('hidden');
    }}
    document.addEventListener('click', (e) => {{
      const modal = document.getElementById('newsletterModal');
      if (!modal || modal.classList.contains('hidden')) return;
      if (e.target === modal) closeNewsletter();
    }});
    document.addEventListener('keydown', (e) => {{
      if (e.key === 'Escape') closeNewsletter();
    }});

    // Copy link
    (function () {{
      const btn = document.getElementById('copyLinkBtn');
      const status = document.getElementById('copyStatus');
      if (!btn) return;
      btn.addEventListener('click', async () => {{
        try {{
          await navigator.clipboard.writeText('{canonical}');
          status.textContent = 'Link copied.';
        }} catch (e) {{
          status.textContent = 'Copy failed. You can copy from the address bar.';
        }}
      }});
    }})();
  </script>

</body>
</html>
"""


def update_articles_index(title: str, slug: str, blurb: str, last_updated: str, deadline: str = ""):
    index_path = os.path.join("articles", "index.html")
    if not os.path.exists(index_path):
        return

    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()

    marker = "<!-- ARTICLES_LIST_INSERT_HERE -->"
    if marker not in html:
        return

    deadline_str = f"Deadline: {deadline} · " if deadline else ""
    card = f"""
      <article class="bg-white rounded-2xl shadow-sm p-5">
        <h2 class="text-xl font-bold text-gray-900 mb-1">
          <a href="/articles/{slug}.html" class="hover:underline">{title}</a>
        </h2>
        <p class="text-sm text-gray-600 mb-2">{deadline_str}Updated {last_updated}</p>
        <p class="text-gray-700">{blurb}</p>
      </article>
    """

    html = html.replace(marker, marker + card)

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    # Prefer ISSUE_BODY, but your workflow writes the body to a file, so support both.
    issue_body = os.environ.get("ISSUE_BODY", "").strip()
    if not issue_body:
        path = os.environ.get("ISSUE_BODY_PATH", "").strip()
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                issue_body = f.read().strip()
    if not issue_body:
        raise SystemExit("Missing ISSUE_BODY (and ISSUE_BODY_PATH was empty/unreadable)")

    issue_body = issue_body.replace('\r\n', '\n').replace('\r', '\n')  # ← ADD THIS LINE

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

    update_articles_index(fields["title"], slug, fields["blurb"], fields["last_updated"], fields.get("deadline", ""))
    print(f"Published: {out_path}")


if __name__ == "__main__":
    main()
