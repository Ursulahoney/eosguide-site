#!/usr/bin/env python3
"""
TopClassActions.com Scraper
Fetches class action settlements
"""

import requests
from bs4 import BeautifulSoup
import hashlib
import re
from datetime import datetime
from typing import List, Dict, Optional


def calculate_days_left(deadline_str: str) -> int:
    """Calculate days until deadline"""
    try:
        # Try MM/DD/YYYY format
        deadline = datetime.strptime(deadline_str, "%m/%d/%Y")
        today = datetime.now()
        days = (deadline - today).days
        return max(0, days)
    except:
        return 999  # Unknown deadline


def extract_claim_url(soup: BeautifulSoup) -> Optional[str]:
    """Extract the official claim/settlement URL"""
    # Look for external settlement website links
    links = soup.find_all('a', href=True)
    
    for link in links:
        href = link['href']
        text = link.get_text().lower()
        
        # Skip TopClassActions internal links
        if 'topclassactions.com' in href:
            continue
        
        # Look for settlement site patterns
        if any(pattern in href.lower() for pattern in ['settlement.com', 'claims.com']):
            if any(word in text for word in ['claim', 'file', 'submit', 'here', 'visit']):
                return href
    
    return None


def scrape_settlement_page(url: str) -> Optional[Dict]:
    """Scrape individual settlement details"""
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract title
        title_elem = soup.find('h1')
        title = title_elem.get_text(strip=True) if title_elem else "Unknown"
        
        # Try to find key details (these vary by page layout)
        deadline = None
        amount = None
        proof_required = "Unknown"
        
        # Look for deadline
        text = soup.get_text()
        deadline_match = re.search(r'(?:deadline|file by)[:\s]+(\d{1,2}/\d{1,2}/\d{4})', text, re.I)
        if deadline_match:
            deadline = deadline_match.group(1)
        
        # Look for amount
        amount_match = re.search(r'\$[\d,]+(?:\.\d{2})?(?:\s*(?:million|billion))?', text, re.I)
        if amount_match:
            amount = amount_match.group(0)
        
        # Get claim URL
        claim_url = extract_claim_url(soup)
        
        # Generate ID
        settlement_id = hashlib.md5(f"{title}{url}".encode()).hexdigest()[:12]
        
        return {
            'id': settlement_id,
            'title': title,
            'category': 'Privacy',  # Could enhance with categorization
            'amount': amount or 'Varies',
            'deadline': deadline or 'TBD',
            'difficulty': 'Medium',  # Could enhance with analysis
            'description': f"Class action settlement. Visit official site for full eligibility details.",
            'url': claim_url or url,
            'detailsUrl': url,
            'state': 'Nationwide',  # Could enhance with location detection
            'urgency': 'medium',
            'urgencyDays': calculate_days_left(deadline) if deadline else 999,
            'value': 'fair',
            'featured': False,
            'source': 'topclassactions.com'
        }
    
    except Exception as e:
        print(f"  ❌ Error scraping {url}: {e}")
        return None


def scrape(max_settlements: int = 100) -> List[Dict]:
    """
    Main scraping function
    Returns list of settlement opportunities
    """
    print("\n🔄 TopClassActions Scraper")
    print("="*60)
    
    opportunities = []
    settlement_urls = []
    
    # Scrape multiple pages to get more settlements
    pages_to_scrape = min(5, (max_settlements // 20) + 1)  # ~20 settlements per page
    
    print(f"Fetching settlement URLs from {pages_to_scrape} pages...")
    
    for page in range(1, pages_to_scrape + 1):
        try:
            if page == 1:
                url = "https://topclassactions.com/category/lawsuit-settlements/open-lawsuit-settlements/"
            else:
                url = f"https://topclassactions.com/category/lawsuit-settlements/open-lawsuit-settlements/page/{page}/"
            
            print(f"  Page {page}...", end=" ")
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find settlement links on this page
            articles = soup.find_all('article')
            page_count = 0
            
            for article in articles:
                link = article.find('a', href=True)
                if link and '/lawsuit-settlements/' in link['href']:
                    if link['href'] not in settlement_urls:  # Avoid duplicates
                        settlement_urls.append(link['href'])
                        page_count += 1
            
            print(f"found {page_count} settlements")
            
            # Stop early if we have enough
            if len(settlement_urls) >= max_settlements:
                break
            
            # Be polite between page requests
            if page < pages_to_scrape:
                import time
                time.sleep(2)
                
        except Exception as e:
            print(f"Error on page {page}: {e}")
            break
    
    # Limit to max requested
    settlement_urls = settlement_urls[:max_settlements]
    print(f"\n📋 Total settlement URLs collected: {len(settlement_urls)}")
    print(f"⏱️  Estimated time: ~{len(settlement_urls) * 2 / 60:.1f} minutes")
    print()
    
    # Scrape each settlement
    for i, settlement_url in enumerate(settlement_urls, 1):
        print(f"  [{i}/{len(settlement_urls)}] Scraping settlement...", end=" ")
        
        settlement = scrape_settlement_page(settlement_url)
        if settlement:
            opportunities.append(settlement)
            print(f"✓ {settlement['title'][:40]}...")
        else:
            print("✗ Failed")
        
        # Be polite - wait between requests
        if i < len(settlement_urls):
            import time
            time.sleep(2)
    
    print(f"\n✅ Successfully scraped {len(opportunities)} settlements")
    
    return opportunities


if __name__ == "__main__":
    # Test the scraper
    results = scrape(max_settlements=5)
    print(f"\n📊 Results: {len(results)} opportunities")
    for opp in results[:3]:
        print(f"  - {opp['title'][:60]}...")
