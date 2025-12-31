#!/usr/bin/env python3
"""
Master Scraper - Runs all individual scrapers and combines results
This is the ONE FILE you run to scrape everything
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Import individual scrapers
try:
    import topclassactions_scraper
    import ftc_refunds_scraper
    import cpsc_recalls_scraper
except ImportError:
    print("❌ Error: Could not import scraper modules.")
    print("Make sure you're running this from the scrapers/ directory")
    print("Run: cd scrapers && python master_scraper.py")
    sys.exit(1)


def remove_duplicates(opportunities):
    """Remove duplicate opportunities based on title"""
    seen = set()
    unique = []
    
    for opp in opportunities:
        # Create a key from title (lowercase, no extra spaces)
        key = opp['title'].lower().strip()
        
        if key not in seen:
            seen.add(key)
            unique.append(opp)
        else:
            print(f"  ℹ️  Skipping duplicate: {opp['title'][:50]}...")
    
    return unique


def save_opportunities(opportunities, output_path="../data/opportunities.json"):
    """Save all opportunities to JSON file"""
    
    # Remove duplicates
    unique_opportunities = remove_duplicates(opportunities)
    
    # Create output structure
    output = {
        "opportunities": unique_opportunities,
        "metadata": {
            "last_updated": datetime.now().isoformat(),
            "total_count": len(unique_opportunities),
            "sources": {
                "topclassactions": len([o for o in unique_opportunities if o['source'] == 'topclassactions.com']),
                "ftc": len([o for o in unique_opportunities if o['source'] == 'ftc.gov']),
                "cpsc": len([o for o in unique_opportunities if o['source'] == 'cpsc.gov'])
            },
            "by_category": {},
            "by_state": {}
        }
    }
    
    # Calculate category breakdown
    for opp in unique_opportunities:
        cat = opp.get('category', 'Other')
        output['metadata']['by_category'][cat] = output['metadata']['by_category'].get(cat, 0) + 1
        
        state = opp.get('state', 'Unknown')
        output['metadata']['by_state'][state] = output['metadata']['by_state'].get(state, 0) + 1
    
    # Ensure output directory exists
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Save to file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Saved {len(unique_opportunities)} opportunities to: {output_path}")
    return output


def run_all_scrapers():
    """
    Run all scrapers and combine results
    This is the main function
    """
    print("\n" + "="*70)
    print("🚀 eosguide Master Scraper")
    print("="*70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    all_opportunities = []
    
    # ===== 1. TopClassActions Scraper =====
    print("\n" + "="*70)
    try:
        # Get ALL available settlements (no limit)
        tca_opps = topclassactions_scraper.scrape(max_settlements=100)
        all_opportunities.extend(tca_opps)
        print(f"✅ TopClassActions: {len(tca_opps)} settlements")
    except Exception as e:
        print(f"❌ TopClassActions scraper failed: {e}")
        print("   Continuing with other scrapers...")
    
    # ===== 2. FTC Refunds Scraper =====
    print("\n" + "="*70)
    try:
        # Get ALL available refund programs
        ftc_opps = ftc_refunds_scraper.scrape(max_programs=100)
        all_opportunities.extend(ftc_opps)
        print(f"✅ FTC Refunds: {len(ftc_opps)} programs")
    except Exception as e:
        print(f"❌ FTC scraper failed: {e}")
        print("   Continuing with other scrapers...")
    
    # ===== 3. CPSC Recalls Scraper =====
    print("\n" + "="*70)
    try:
        # Get MANY recalls (200 is a good balance - more than this and it takes 20+ min)
        cpsc_opps = cpsc_recalls_scraper.scrape(max_recalls=200)
        all_opportunities.extend(cpsc_opps)
        print(f"✅ CPSC Recalls: {len(cpsc_opps)} recalls")
    except Exception as e:
        print(f"❌ CPSC scraper failed: {e}")
        print("   Continuing with other scrapers...")
    
    # ===== Save Combined Results =====
    print("\n" + "="*70)
    print("📊 COMBINING RESULTS")
    print("="*70)
    
    if not all_opportunities:
        print("❌ No opportunities scraped! All scrapers failed.")
        return None
    
    output = save_opportunities(all_opportunities)
    
    # ===== Summary =====
    print("\n" + "="*70)
    print("📈 SUMMARY")
    print("="*70)
    print(f"Total opportunities: {output['metadata']['total_count']}")
    print(f"\nBy Source:")
    for source, count in output['metadata']['sources'].items():
        print(f"  {source}: {count}")
    print(f"\nBy Category:")
    for cat, count in sorted(output['metadata']['by_category'].items()):
        print(f"  {cat}: {count}")
    
    print("\n" + "="*70)
    print("✅ SCRAPING COMPLETE")
    print("="*70)
    print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n💡 Next step: Upload data/opportunities.json to your GitHub repo")
    print("="*70 + "\n")
    
    return output


if __name__ == "__main__":
    run_all_scrapers()
