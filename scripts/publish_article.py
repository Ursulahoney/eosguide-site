#!/usr/bin/env python3
"""
publish_article.py
------------------
Reads a GitHub issue body and generates a full article HTML file
for eosguidehub.com. Also updates articles/index.html.

HOW IT WORKS:
  1. Reads .tmp/issue_body.md (written by the workflow from the issue body)
  2. Parses all the structured fields from the form
  3. Builds a full HTML page matching the site's style
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
# GitHub issue forms render as sections separated by "### Field Label"
# ─────────────────────────────────────────────────────────────────

def parse_issue(body: str) -> dict:
    """
    Splits the issue body into a dictionary of { field_label: value }.
    GitHub forms render each field as:
        ### Field Label
        
        Value here
    """
    fields = {}
    # Split on "### " headers
    sections = re.split(r'\n###\s+', '\n' + body)
    for section in sections:
        if not section.strip():
            continue
        lines = section.strip().split('\n')
        label = lines[0].strip().lower()
        # Everything after the first line is the value
        value = '\n'.join(lines[1:]).strip()
        # Normalize the label to match our field IDs
        fields[label] = value
    return fields


def get_field(fields: dict, *possible_labels: str) -> str:
    """
    Looks up a field by trying multiple possible label strings.
    Returns empty string if not found.
    """
    for label in possible_labels:
        value = fields.get(label.lower(), '').strip()
        # Skip GitHub's "_No response_" placeholder
        if value and value != '_No response_':
            return value
    return ''


# ─────────────────────────────────────────────────────────────────
# STEP 2: PARSE STRUCTURED COMPONENTS
# Turn the raw text fields into structured Python data
# ─────────────────────────────────────────────────────────────────

def parse_eligibility(text: str) -> list:
    """
    Parses a bulleted list like:
        - You received a breach notice letter
        - You are a US resident
    Returns a list of strings.
    """
    items = []
    for line in text.strip().split('\n'):
        line = line.strip().lstrip('-').lstrip('*').strip()
        if line:
            items.append(line)
    return items


def parse_steps(text: str) -> list:
    """
    Parses numbered steps like:
        1. Visit the website
        2. Fill out the form
    Returns a list of strings (the step text without the number).
    """
    steps = []
    for line in text.strip().split('\n'):
        line = line.strip()
        # Match lines starting with a number and period: "1. " "2. " etc.
        match = re.match(r'^\d+\.\s+(.+)$', line)
        if match:
            steps.append(match.group(1).strip())
    return steps


def parse_faqs(text: str) -> list:
    """
    Parses Q: A: pairs like:
        Q: Do I need a lawyer?
        A: No, you can file yourself.
    Returns a list of (question, answer) tuples.
    """
    faqs = []
    current_q = None
    current_a_lines = []

    for line in text.strip().split('\n'):
        line = line.strip()
        if line.lower().startswith('q:'):
            # Save previous pair if exists
            if current_q and current_a_lines:
                faqs.append((current_q, ' '.join(current_a_lines)))
            current_q = line[2:].strip()
            current_a_lines = []
        elif line.lower().startswith('a:') and current_q:
            current_a_lines = [line[2:].strip()]
        elif line and current_a_lines is not None:
            current_a_lines.append(line)

    # Don't forget the last pair
    if current_q and current_a_lines:
        faqs.append((current_q, ' '.join(current_a_lines)))

    return faqs


def is_monetization_on(text: str) -> bool:
    """Checks if the monetization checkbox was ticked."""
    return '[x]' in text.lower() or '- [x]' in text.lower()


# ─────────────────────────────────────────────────────────────────
# STEP 3: HTML COMPONENT BUILDERS
# Each function returns an HTML string for one part of the article
# ─────────────────────────────────────────────────────────────────

def build_deadline_callout(deadline: str, official_website: str) -> str:
    if not deadline or deadline.lower() == 'none listed':
        return ''
    btn = ''
    if official_website:
        btn = f'''
          <a href="{official_website}" target="_blank" rel="noopener"
             class="inline-block bg-red-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-red-700 transition no-underline">
            File Your Claim Now →
          </a>'''
    return f'''
        <div class="bg-red-50 border-l-4 border-red-500 p-6 mb-8 rounded-r-lg">
          <div class="flex items-center mb-2">
            <svg class="w-6 h-6 text-red-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd"/>
            </svg>
            <h3 class="text-lg font-bold text-red-800 m-0">Claim Deadline: {deadline}</h3>
          </div>
          <p class="text-red-700 mb-3">Don't miss the deadline to file your claim.</p>
          {btn}
        </div>'''


def build_quick_summary(settlement_amount: str, max_payment: str, nodoc_payment: str, official_website: str) -> str:
    if not settlement_amount and not max_payment and not nodoc_payment:
        return ''

    amount_card = ''
    if settlement_amount:
        amount_card = f'''
            <div class="bg-white p-4 rounded-lg">
              <p class="text-sm text-gray-600 mb-1">Settlement Amount</p>
              <p class="text-2xl font-bold text-purple-600">{settlement_amount}</p>
            </div>'''

    payment_card = ''
    if max_payment:
        payment_card = f'''
            <div class="bg-white p-4 rounded-lg">
              <p class="text-sm text-gray-600 mb-1">Your Potential Payment</p>
              <p class="text-2xl font-bold text-green-600">{max_payment}</p>
            </div>'''
    elif nodoc_payment:
        payment_card = f'''
            <div class="bg-white p-4 rounded-lg">
              <p class="text-sm text-gray-600 mb-1">Cash Payment (no docs needed)</p>
              <p class="text-2xl font-bold text-green-600">{nodoc_payment}</p>
            </div>'''

    website_item = ''
    if official_website:
        # Extract a clean display name from the URL
        display = official_website.replace('https://', '').replace('http://', '').rstrip('/')
        website_item = f'''
            <li class="flex items-start">
              <svg class="w-5 h-5 text-green-500 mr-2 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
              </svg>
              <span><strong>Official Website:</strong> <a href="{official_website}" target="_blank" rel="noopener" class="text-blue-600 hover:underline">{display}</a></span>
            </li>'''

    return f'''
        <div class="bg-gradient-to-br from-blue-50 to-purple-50 border border-blue-200 rounded-xl p-6 mb-8 shadow-sm">
          <h2 class="text-2xl font-bold text-gray-900 mb-4 flex items-center">
            <svg class="w-6 h-6 text-blue-600 mr-2" fill="currentColor" viewBox="0 0 20 20">
              <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z"/>
              <path fill-rule="evenodd" d="M4 5a2 2 0 012-2 3 3 0 003 3h2a3 3 0 003-3 2 2 0 012 2v11a2 2 0 01-2 2H6a2 2 0 01-2-2V5zm3 4a1 1 0 000 2h.01a1 1 0 100-2H7zm3 0a1 1 0 000 2h3a1 1 0 100-2h-3zm-3 4a1 1 0 100 2h.01a1 1 0 100-2H7zm3 0a1 1 0 100 2h3a1 1 0 100-2h-3z" clip-rule="evenodd"/>
            </svg>
            Quick Summary
          </h2>
          <div class="grid md:grid-cols-2 gap-4">
            {amount_card}
            {payment_card}
          </div>
          <ul class="mt-4 space-y-2">
            {website_item}
          </ul>
        </div>'''


def build_eligibility_section(items: list) -> str:
    if not items:
        return ''
    rows = ''
    for item in items:
        rows += f'''
            <label class="flex items-start cursor-pointer hover:bg-green-100 p-2 rounded transition">
              <input type="checkbox" class="mt-1 mr-3 h-5 w-5 text-green-600" disabled>
              <span>{item}</span>
            </label>'''
    return f'''
        <h2 id="eligibility">Who Is Eligible?</h2>
        <div class="bg-green-50 border-l-4 border-green-500 p-6 mb-6 rounded-r-lg">
          <p class="font-semibold text-green-900 mb-3">You may qualify if the following apply:</p>
          <div class="space-y-2">
            {rows}
          </div>
        </div>'''


def build_steps_section(steps: list) -> str:
    if not steps:
        return ''
    step_html = ''
    for i, step in enumerate(steps, 1):
        step_html += f'''
            <div class="flex items-start">
              <div class="flex-shrink-0 w-10 h-10 bg-purple-600 text-white rounded-full flex items-center justify-center font-bold mr-4">{i}</div>
              <div>
                <p class="text-gray-700 mt-2">{step}</p>
              </div>
            </div>'''
    return f'''
        <h2 id="how-to-file">How to File a Claim</h2>
        <div class="bg-gradient-to-br from-gray-50 to-gray-100 rounded-xl p-6 mb-8 border border-gray-200">
          <div class="space-y-6">
            {step_html}
          </div>
        </div>'''


def build_faq_section(faqs: list) -> str:
    if not faqs:
        return ''
    items = ''
    for q, a in faqs:
        items += f'''
          <details class="bg-white border border-gray-200 rounded-lg p-4 cursor-pointer hover:shadow-md transition">
            <summary class="font-semibold text-gray-900">Q: {q}</summary>
            <p class="mt-2 text-gray-700">A: {a}</p>
          </details>'''
    return f'''
        <h2>Frequently Asked Questions</h2>
        <div class="space-y-4 mb-8">
          {items}
        </div>'''


def build_cta_section(deadline: str, official_website: str) -> str:
    if not official_website:
        return ''
    deadline_text = f'by <strong>{deadline}</strong>' if deadline and deadline.lower() != 'none listed' else ''
    display = official_website.replace('https://', '').replace('http://', '').rstrip('/')
    return f'''
        <div class="bg-gradient-to-br from-purple-600 to-blue-600 text-white rounded-xl p-8 mb-8 text-center shadow-lg">
          <h2 class="text-3xl font-black text-white mb-4">Don't Leave Money on the Table</h2>
          <p class="text-lg mb-6 text-purple-100">
            Check if you qualify and submit your claim {deadline_text}.
          </p>
          <a href="{official_website}" target="_blank" rel="noopener"
             class="inline-block bg-white text-purple-600 px-10 py-4 rounded-lg font-black text-xl hover:bg-gray-100 transition shadow-xl no-underline">
            File Your Claim at {display} →
          </a>
          <p class="mt-6 text-purple-100">
            eosguide is a directory. We're not affiliated with this settlement and we don't give legal advice.
            Always verify details at the official site.
          </p>
        </div>'''


# ─────────────────────────────────────────────────────────────────
# STEP 4: SHARED HEADER AND FOOTER
# Matches the existing site style exactly
# ─────────────────────────────────────────────────────────────────

SITE_HEADER = """
  <header class="relative z-10 px-4 py-6 sm:px-6 lg:px-8">
    <nav class="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center md:justify-between gap-4">
      <div class="flex flex-col md:flex-row md:items-center gap-3 md:gap-6 group cursor-pointer">
        <div class="relative flex-shrink-0">
          <a href="/" aria-label="Back to eosguide home">
            <img src="/Circular-badge-logo.png" alt="eosguide logo"
                 class="w-28 h-28 sm:w-32 sm:h-32 md:w-40 md:h-40">
          </a>
        </div>
        <blockquote class="text-xs sm:text-sm md:text-base font-semibold italic leading-snug text-gray-500 max-w-xs md:max-w-sm text-center md:text-left"
                    style="font-family: 'DM Sans', 'Montserrat', system-ui, sans-serif;">
          "We do the searching<br>
          so you don't have to<br>
          pretend it's fun."
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
"""

SITE_FOOTER = """
  <footer class="relative z-10 bg-gradient-to-br from-gray-900 to-gray-800 text-white py-12 px-4 sm:px-6 lg:px-8">
    <div class="max-w-7xl mx-auto">
      <div class="grid md:grid-cols-3 gap-8 mb-8">
        <div>
          <h4 class="font-black text-xl mb-4 bg-gradient-to-r from-cyan-300 via-purple-300 to-pink-300 bg-clip-text text-transparent">
            eosguide
          </h4>
          <p class="text-gray-400 text-sm font-light">
            We keep an eye on refunds, relief, and "you might have money out there" programs so you don't have to chase every headline.
          </p>
        </div>
        <div class="text-center md:text-left">
          <p class="text-gray-300 text-sm font-light">Have a question, suggestion, or request?</p>
          <p class="text-gray-200 text-sm font-light">
            Email: <a href="mailto:hello@eosguidehub.com" class="text-cyan-300 hover:text-cyan-400 underline">hello@eosguidehub.com</a>
          </p>
        </div>
      </div>
      <div class="text-center mb-6">
        <p class="text-gray-300 text-sm font-light">
          &copy; 2025 eosguide. Information only. We're not affiliated with the programs we link to and we don't give legal, financial, or tax advice.
        </p>
      </div>
      <div class="mt-4 text-sm">
        <a href="/legal/" class="text-cyan-300 hover:text-cyan-400 underline">Legal</a>
        <span class="text-gray-500 mx-2">&bull;</span>
        <a href="/legal/#privacy" class="text-cyan-300 hover:text-cyan-400 underline">Privacy</a>
        <span class="text-gray-500 mx-2">&bull;</span>
        <a href="/legal/#terms" class="text-cyan-300 hover:text-cyan-400 underline">Terms</a>
        <span class="text-gray-500 mx-2">&bull;</span>
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
        <h3 class="text-3xl font-black mb-2">Get alerts</h3>
        <p class="text-gray-600 font-normal">New settlement and refund updates. No spam.</p>
      </div>
      <form action="https://buttondown.com/api/emails/embed-subscribe/eosguidehub" method="post" class="space-y-4">
        <input type="hidden" name="embed" value="1" />
        <input type="email" name="email" placeholder="Enter your email" required
               class="w-full px-4 py-3 rounded-2xl border-2 border-gray-200 focus:border-purple-500 focus:outline-none transition-colors" />
        <button type="submit"
                class="w-full px-6 py-3 text-white rounded-2xl font-bold hover:shadow-lg hover:scale-105 transition-all duration-300"
                style="background: linear-gradient(135deg, #FF6B35 0%, #FF8C42 100%);">
          Subscribe free
        </button>
      </form>
      <p class="text-xs text-gray-500 text-center mt-4">Unsubscribe anytime.</p>
    </div>
  </div>

  <script>
    function openNewsletter() {
      document.getElementById('newsletterModal').classList.remove('hidden');
    }
    function closeNewsletter() {
      document.getElementById('newsletterModal').classList.add('hidden');
    }
    document.addEventListener('click', (e) => {
      const modal = document.getElementById('newsletterModal');
      if (!modal || modal.classList.contains('hidden')) return;
      if (e.target === modal) closeNewsletter();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeNewsletter();
    });
  </script>
"""


# ─────────────────────────────────────────────────────────────────
# STEP 5: ASSEMBLE THE FULL PAGE
# ─────────────────────────────────────────────────────────────────

def build_page(f: dict) -> str:
    """
    Takes the parsed fields dictionary and returns the full HTML string.
    """
    title          = f.get('title', 'Article')
    slug           = f.get('slug', 'article')
    blurb          = f.get('blurb', '')
    deadline       = f.get('deadline', '')
    last_updated   = f.get('last_updated', '')
    settlement_amount = f.get('settlement_amount', '')
    max_payment    = f.get('max_payment', '')
    nodoc_payment  = f.get('nodoc_payment', '')
    official_website = f.get('official_website', '')
    hero_image     = f.get('hero_image', '')
    hero_credit    = f.get('hero_credit', '')
    article_body   = f.get('article_body', '')

    eligibility_items = parse_eligibility(f.get('eligibility', ''))
    steps = parse_steps(f.get('how_to_file', ''))
    faqs = parse_faqs(f.get('faqs', ''))

    # Convert Markdown article body to HTML
    body_html = markdown.markdown(
        article_body,
        extensions=['tables', 'fenced_code']
    ) if article_body else ''

    # Build structured components
    deadline_callout  = build_deadline_callout(deadline, official_website)
    quick_summary     = build_quick_summary(settlement_amount, max_payment, nodoc_payment, official_website)
    eligibility_block = build_eligibility_section(eligibility_items)
    steps_block       = build_steps_section(steps)
    faq_block         = build_faq_section(faqs)
    cta_block         = build_cta_section(deadline, official_website)

    # Hero image block
    hero_html = ''
    if hero_image:
        credit_html = f'<p class="text-xs text-gray-500 mb-6">{hero_credit}</p>' if hero_credit else ''
        hero_html = f'''
      <img src="/assets/articles/{hero_image}"
           alt="{title}"
           class="rounded-2xl mb-2 w-full">
      {credit_html}'''

    # Deadline + last updated meta row
    meta_html = ''
    if deadline or last_updated:
        deadline_span = f'<div class="text-sm text-gray-700"><span class="font-semibold">Deadline:</span> {deadline}</div>' if deadline else ''
        updated_span  = f'<div class="text-sm text-gray-500"><span class="font-semibold">Last updated:</span> {last_updated}</div>' if last_updated else ''
        meta_html = f'''
      <div class="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        {deadline_span}
        {updated_span}
      </div>'''

    # Canonical and OG URL
    canonical = f"https://eosguidehub.com/articles/{slug}.html"
    og_image  = f"https://eosguidehub.com/assets/articles/{hero_image}" if hero_image else "https://eosguidehub.com/Circular-badge-logo.png"

    # Share buttons
    encoded_title = title.replace(' ', '%20').replace(':', '%3A')
    share_url = canonical

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | eosguide</title>
  <meta name="description" content="{blurb}">
  <link rel="canonical" href="{canonical}">
  <link rel="icon" href="/Circular-badge-logo.png" type="image/png">
  <meta property="og:type" content="article">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{blurb}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="{og_image}">
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    .table-wrap {{ overflow-x: auto; }}
    .table-wrap table {{ width: 100%; border-collapse: collapse; }}
    .table-wrap th, .table-wrap td {{ padding: 10px 12px; border-bottom: 1px solid #e5e7eb; vertical-align: top; }}
    .prose h2 {{ font-size: 1.5rem; font-weight: 700; margin: 2rem 0 1rem; color: #111827; }}
    .prose h3 {{ font-size: 1.125rem; font-weight: 600; margin: 1.5rem 0 0.75rem; color: #374151; }}
    .prose p  {{ margin-bottom: 1rem; color: #374151; }}
    .prose ul {{ list-style: disc; padding-left: 1.5rem; margin-bottom: 1rem; color: #374151; }}
    .prose ol {{ list-style: decimal; padding-left: 1.5rem; margin-bottom: 1rem; color: #374151; }}
    .prose li {{ margin-bottom: 0.25rem; }}
    .prose a  {{ color: #2563eb; text-decoration: underline; }}
    .prose blockquote {{ border-left: 4px solid #d1d5db; padding-left: 1rem; font-style: italic; color: #6b7280; margin: 1rem 0; }}
    .prose strong {{ font-weight: 700; }}
    .prose table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
    .prose th {{ background: #f3f4f6; padding: 0.5rem 0.75rem; text-align: left; font-weight: 600; border: 1px solid #e5e7eb; }}
    .prose td {{ padding: 0.5rem 0.75rem; border: 1px solid #e5e7eb; }}
  </style>
</head>

<body class="min-h-screen bg-gradient-to-br from-cyan-50 via-purple-50 to-pink-50">

{SITE_HEADER}

  <main class="relative z-10 px-4 sm:px-6 lg:px-8 py-12">
    <article class="max-w-3xl mx-auto bg-white rounded-3xl shadow-sm p-6 sm:p-8">

      <h1 class="mt-3 text-3xl sm:text-4xl font-black text-gray-900 mb-3">
        {title}
      </h1>

      {meta_html}

      <p class="text-gray-700 mb-6 italic">{blurb}</p>

      {hero_html}

      <div class="prose max-w-none mt-8">

        {deadline_callout}

        {quick_summary}

        {body_html}

        {eligibility_block}

        {steps_block}

        {faq_block}

        {cta_block}

        <hr class="my-8 border-gray-300">

        <p class="text-sm text-gray-600">
          <em>Disclaimer: This article is for informational purposes only.
          eosguide is not affiliated with this settlement or its administrator.
          For official information, visit the settlement website linked above.
          Only file a claim if you genuinely qualify.</em>
        </p>

      </div>

      <p class="mt-10 text-xs text-gray-500">
        Info only. Verify details on the official site. Not legal, financial, or tax advice.
        <a href="/legal/" class="underline">Legal</a>
      </p>

      <div class="mt-6 pt-6 border-t border-gray-200">
        <p class="text-sm font-semibold text-gray-700 mb-3">Share this:</p>
        <div class="flex flex-wrap gap-2 text-sm">
          <button type="button" id="copyLinkBtn"
            class="px-3 py-2 rounded-xl bg-gray-100 hover:bg-gray-200 transition">
            Copy link
          </button>
          <a class="px-3 py-2 rounded-xl bg-gray-100 hover:bg-gray-200 transition"
             target="_blank" rel="noopener"
             href="https://twitter.com/intent/tweet?url={share_url}&text={encoded_title}">
            X
          </a>
          <a class="px-3 py-2 rounded-xl bg-gray-100 hover:bg-gray-200 transition"
             target="_blank" rel="noopener"
             href="https://www.facebook.com/sharer/sharer.php?u={share_url}">
            Facebook
          </a>
        </div>
        <p id="copyStatus" class="text-xs text-gray-500 mt-2" aria-live="polite"></p>
      </div>

      <script>
        (function () {{
          const btn = document.getElementById('copyLinkBtn');
          const status = document.getElementById('copyStatus');
          if (!btn) return;
          btn.addEventListener('click', async () => {{
            try {{
              await navigator.clipboard.writeText('{share_url}');
              status.textContent = 'Link copied.';
            }} catch (e) {{
              status.textContent = 'Copy failed — use the address bar.';
            }}
          }});
        }})();
      </script>

    </article>
  </main>

{SITE_FOOTER}

</body>
</html>"""


# ─────────────────────────────────────────────────────────────────
# STEP 6: UPDATE THE ARTICLES INDEX PAGE
# Inserts a new article card into articles/index.html
# ─────────────────────────────────────────────────────────────────

INSERT_MARKER = '<!-- ARTICLES_LIST_INSERT_HERE -->'

def update_index(slug: str, title: str, deadline: str, last_updated: str, blurb: str) -> None:
    index_path = 'articles/index.html'
    if not os.path.exists(index_path):
        print(f"Warning: {index_path} not found — skipping index update.")
        return

    content = open(index_path, 'r', encoding='utf-8').read()

    # Build the new article card
    deadline_text = f'Deadline: {deadline} · ' if deadline and deadline.lower() != 'none listed' else ''
    new_card = f"""
<article class="bg-white rounded-2xl shadow-sm p-5">
  <h2 class="text-xl font-bold text-gray-900 mb-1">
    <a href="/articles/{slug}.html" class="hover:underline">{title}</a>
  </h2>
  <p class="text-sm text-gray-600 mb-2">{deadline_text}Updated {last_updated}</p>
  <p class="text-gray-700">{blurb}</p>
</article>
"""

    # Only insert if this slug isn't already in the index
    if f'/articles/{slug}.html' in content:
        print(f"Article {slug} already in index — skipping.")
        return

    # Insert the new card right after the marker
    updated = content.replace(INSERT_MARKER, INSERT_MARKER + new_card)

    open(index_path, 'w', encoding='utf-8').write(updated)
    print(f"✓ Added {slug} to articles/index.html")


# ─────────────────────────────────────────────────────────────────
# STEP 7: MAIN — WIRE IT ALL TOGETHER
# ─────────────────────────────────────────────────────────────────

def main():
    # Read the issue body saved by the workflow
    issue_body_path = os.environ.get('ISSUE_BODY_PATH', '.tmp/issue_body.md')
    if not os.path.exists(issue_body_path):
        print(f"Error: Issue body not found at {issue_body_path}")
        sys.exit(1)

    body = open(issue_body_path, 'r', encoding='utf-8').read()

    # Parse all fields from the issue body
    raw = parse_issue(body)

    # Map parsed fields to clean names
    # (We try multiple label variants in case GitHub renders them slightly differently)
    fields = {
        'title':             get_field(raw, 'article title'),
        'slug':              get_field(raw, 'url slug'),
        'blurb':             get_field(raw, 'short blurb'),
        'deadline':          get_field(raw, 'claim deadline', 'deadline'),
        'last_updated':      get_field(raw, 'last updated'),
        'settlement_amount': get_field(raw, 'total settlement fund'),
        'max_payment':       get_field(raw, 'maximum payment per person'),
        'nodoc_payment':     get_field(raw, 'no-documentation cash payment'),
        'official_website':  get_field(raw, 'official settlement website'),
        'hero_image':        get_field(raw, 'hero image filename'),
        'hero_credit':       get_field(raw, 'hero image credit (optional)', 'hero image credit'),
        'eligibility':       get_field(raw, 'who is eligible? (bulleted list)', 'who is eligible?'),
        'how_to_file':       get_field(raw, 'how to file a claim (numbered steps)', 'how to file a claim'),
        'faqs':              get_field(raw, 'frequently asked questions (q: a: format)', 'frequently asked questions'),
        'article_body':      get_field(raw, 'article body (markdown)', 'article body'),
        'monetization':      get_field(raw, 'monetization'),
        'status':            get_field(raw, 'publish status'),
    }

    # Validate required fields
    if not fields['title'] or not fields['slug']:
        print("Error: 'Article title' and 'URL slug' are required.")
        sys.exit(1)

    # Determine publish mode
    mode = os.environ.get('MODE', 'draft').lower()

    # Build the HTML
    html = build_page(fields)

    # Write the article file
    if mode == 'publish':
        os.makedirs('articles', exist_ok=True)
        out_path = f"articles/{fields['slug']}.html"
    else:
        os.makedirs('articles/drafts', exist_ok=True)
        out_path = f"articles/drafts/{fields['slug']}.html"

    open(out_path, 'w', encoding='utf-8').write(html)
    print(f"✓ Article written to {out_path}")

    # Update the index (only for published articles)
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
