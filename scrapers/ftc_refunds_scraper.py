#!/usr/bin/env python3
"""
FTC Consumer Refunds Scraper
Fetches active FTC refund programs
"""

import requests
from bs4 import BeautifulSoup
import hashlib
import re
from datetime import datetime
from typing import List, Dict


def scrape(max_programs: int = 20) -> List[Dict]:
    """
    Scrape FTC refund programs
    Returns list of refund opportunities
    """
    print("\n🔄 FTC Refunds Scraper")
    print("="*60)
    
    opportunities = []
    
    url = "https://www.ftc.gov/enforcement/refunds"
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find refund program listings
        # FTC typically lists active refund programs with specific patterns
        refund_sections = soup.find_all(['div', 'article'], class_=re.compile(r'refund|program', re.I))
        
        if not refund_sections:
            # Fallback: look for links to refund pages
            refund_links = soup.find_all('a', href=re.compile(r'/enforcement/refunds/'))
            refund_sections = [link.find_parent(['div', 'article']) for link in refund_links[:max_programs]]
            refund_sections = [s for s in refund_sections if s]
        
        print(f"Found {len(refund_sections)} potential refund programs")
        
        for section in refund_sections[:max_programs]:
            try:
                # Extract title
                title_elem = section.find(['h2', 'h3', 'h4', 'a'])
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                
                # Skip if not a refund program
                if not any(word in title.lower() for word in ['refund', 'settlement', 'redress']):
                    continue
                
                # Get link
                link_elem = section.find('a', href=True)
                refund_url = link_elem['href'] if link_elem else url
                if refund_url.startswith('/'):
                    refund_url = 'https://www.ftc.gov' + refund_url
                
                # Extract description
                desc_elem = section.find('p')
                description = desc_elem.get_text(strip=True) if desc_elem else f"FTC consumer refund program. Visit official site for eligibility and claim details."
                
                # Extract amount if mentioned
                amount_match = re.search(r'\$[\d,]+(?:\.\d{2})?\s*(?:million|billion)?', section.get_text(), re.I)
                amount = amount_match.group(0) if amount_match else "Varies"
                
                # Generate ID
                program_id = hashlib.md5(f"{title}{refund_url}".encode()).hexdigest()[:12]
                
                opportunity = {
                    'id': program_id,
                    'title': f"FTC: {title}",
                    'category': 'Unclaimed money & refunds',
                    'amount': amount,
                    'deadline': 'Check program',
                    'difficulty': 'Medium',
                    'description': description[:200] + "..." if len(description) > 200 else description,
                    'url': refund_url,
                    'detailsUrl': refund_url,
                    'state': 'Nationwide',
                    'urgency': 'medium',
                    'urgencyDays': 90,  # FTC programs typically have long claim periods
                    'value': 'good',
                    'featured': False,
                    'source': 'ftc.gov'
                }
                
                opportunities.append(opportunity)
                print(f"  ✓ Found: {title[:50]}...")
                
            except Exception as e:
                print(f"  ⚠️  Error parsing section: {e}")
                continue
        
        print(f"✅ Successfully scraped {len(opportunities)} FTC refund programs")
        
    except Exception as e:
        print(f"❌ Error fetching FTC refunds: {e}")
    
    return opportunities


if __name__ == "__main__":
    # Test the scraper
    results = scrape()
    print(f"\n📊 Results: {len(results)} opportunities")
    for opp in results[:3]:
        print(f"  - {opp['title'][:60]}...")
