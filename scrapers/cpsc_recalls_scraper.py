#!/usr/bin/env python3
"""
CPSC Product Recalls Scraper
Fetches consumer product recalls from CPSC
"""

import requests
from bs4 import BeautifulSoup
import hashlib
import re
from datetime import datetime
from typing import List, Dict


def scrape(max_recalls: int = 50) -> List[Dict]:
    """
    Scrape CPSC product recalls
    Returns list of recall opportunities
    """
    print("\n🔄 CPSC Recalls Scraper")
    print("="*60)
    
    opportunities = []
    
    # CPSC has an RSS feed which is easier to parse
    url = "https://www.cpsc.gov/Recalls"
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find recall items
        recall_items = soup.find_all(['div', 'article'], class_=re.compile(r'recall|product', re.I))
        
        if not recall_items:
            # Fallback: look for recall links
            recall_links = soup.find_all('a', href=re.compile(r'/Recalls/\d{4}/'))
            recall_items = [link.find_parent(['div', 'article']) for link in recall_links[:max_recalls]]
            recall_items = [item for item in recall_items if item]
        
        print(f"Found {len(recall_items)} recalls")
        
        for item in recall_items[:max_recalls]:
            try:
                # Extract title
                title_elem = item.find(['h2', 'h3', 'h4', 'a'])
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                
                # Get link
                link_elem = item.find('a', href=True)
                recall_url = link_elem['href'] if link_elem else url
                if recall_url.startswith('/'):
                    recall_url = 'https://www.cpsc.gov' + recall_url
                
                # Extract hazard/description
                desc_elem = item.find('p')
                description = desc_elem.get_text(strip=True) if desc_elem else "Product recall. Check if you own this item and file for refund/replacement."
                
                # Extract remedy (refund/replacement)
                remedy = "Refund or replacement available"
                if 'refund' in description.lower():
                    remedy = "Full refund available"
                elif 'replacement' in description.lower():
                    remedy = "Free replacement available"
                
                # Categorize product
                category = categorize_product(title)
                
                # Generate ID
                recall_id = hashlib.md5(f"{title}{recall_url}".encode()).hexdigest()[:12]
                
                opportunity = {
                    'id': recall_id,
                    'title': f"Recall: {title}",
                    'category': category,
                    'amount': remedy,
                    'deadline': 'Ongoing',
                    'difficulty': 'Easy',
                    'description': description[:200] + "..." if len(description) > 200 else description,
                    'url': recall_url,
                    'detailsUrl': recall_url,
                    'state': 'Nationwide',
                    'urgency': 'low',
                    'urgencyDays': 365,  # Recalls typically open for extended periods
                    'value': 'good',
                    'featured': False,
                    'source': 'cpsc.gov'
                }
                
                opportunities.append(opportunity)
                
            except Exception as e:
                print(f"  ⚠️  Error parsing recall: {e}")
                continue
        
        print(f"✅ Successfully scraped {len(opportunities)} product recalls")
        
    except Exception as e:
        print(f"❌ Error fetching CPSC recalls: {e}")
    
    return opportunities


def categorize_product(title: str) -> str:
    """Categorize recall by product type"""
    title_lower = title.lower()
    
    categories = {
        'Consumer Products': ['toy', 'furniture', 'appliance', 'mattress', 'clothing', 'bedding'],
        'Technology': ['charger', 'battery', 'electric', 'electronic', 'device', 'phone'],
        'Health & Safety': ['baby', 'child', 'infant', 'stroller', 'crib', 'seat'],
        'Home & Garden': ['ladder', 'tool', 'heater', 'fan', 'light', 'candle'],
    }
    
    for category, keywords in categories.items():
        if any(keyword in title_lower for keyword in keywords):
            return category
    
    return 'Consumer Products'


if __name__ == "__main__":
    # Test the scraper
    results = scrape(max_recalls=10)
    print(f"\n📊 Results: {len(results)} opportunities")
    for opp in results[:3]:
        print(f"  - {opp['title'][:60]}...")
