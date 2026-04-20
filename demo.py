#!/usr/bin/env python3
"""
Rapid100 Demo - Quick demonstration of the gaming news scraper
This is a simplified version that works without API keys (uses fallback summarization)
"""

import os
import sys
import re
import html
import requests
from datetime import datetime

# Demo RSS feeds
DEMO_FEEDS = [
    {"url": "https://www.vg247.com/feed", "source": "VG247"},
    {"url": "https://www.gematsu.com/feed", "source": "Gematsu"},
]


def clean_html(html_text):
    """Strip HTML tags."""
    text = re.sub(r'<[^>]+>', ' ', html_text)
    text = html.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def fetch_feed(url, source):
    """Fetch and parse a single RSS feed."""
    print(f"\n📰 Fetching {source}...")
    
    try:
        resp = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (compatible; Rapid100Demo/1.0)"
        })
        resp.raise_for_status()
        
        # Simple regex-based RSS parsing (no XML lib needed for demo)
        xml = resp.text
        items = []
        
        # Find all item blocks
        for match in re.finditer(r'<item>(.*?)</item>', xml, re.DOTALL):
            block = match.group(1)
            
            # Extract title
            title_match = re.search(r'<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>', block, re.DOTALL)
            title = clean_html(title_match.group(1)) if title_match else "No Title"
            
            # Extract link
            link_match = re.search(r'<link>(.*?)</link>', block)
            link = link_match.group(1).strip() if link_match else ""
            
            # Extract description
            desc_match = re.search(r'<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>', block, re.DOTALL)
            description = clean_html(desc_match.group(1)) if desc_match else ""
            
            # Clean up description
            description = re.sub(r'\s*The post .+ appeared first on .+\.?\s*$', '', description, flags=re.IGNORECASE)
            description = re.sub(r'\s*(Read more|Continue reading)[^.]*\.?\s*$', '', description, flags=re.IGNORECASE)
            
            if title and link:
                items.append({
                    'title': title,
                    'link': link,
                    'description': description,
                    'source': source
                })
        
        print(f"   ✓ Found {len(items)} articles")
        return items[:3]  # Return top 3 for demo
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return []


def simple_summarize(text, max_words=100):
    """Simple extractive summarization (fallback when no AI)."""
    words = text.split()
    
    if len(words) <= max_words:
        return text
    
    # Take first 100 words, try to end at sentence boundary
    summary_words = words[:max_words]
    summary = ' '.join(summary_words)
    
    # Try to find last sentence ending
    last_period = summary.rfind('.')
    if last_period > len(summary) * 0.7:  # If period is in last 30%
        summary = summary[:last_period + 1]
    else:
        summary += '...'
    
    return summary


def extract_simple_tags(title, description):
    """Simple tag extraction without AI."""
    text = f"{title} {description}".lower()
    tags = []
    
    # Known games
    games = [
        'gta', 'elden ring', 'baldur', 'counter-strike', 'valorant', 
        'fortnite', 'minecraft', 'zelda', 'mario', 'pokemon',
        'call of duty', 'apex', 'overwatch', 'league of legends'
    ]
    
    for game in games:
        if game in text:
            # Convert to PascalCase tag
            tag = game.title().replace(' ', '')
            tags.append(tag)
    
    # Platforms
    platforms = ['ps5', 'playstation', 'xbox', 'switch', 'nintendo', 'pc']
    for plat in platforms:
        if plat in text:
            tags.append(plat.title())
    
    return tags[:4]  # Max 4 tags


def main():
    print("=" * 60)
    print("🎮 RAPID60 DEMO - Gaming News Scraper")
    print("=" * 60)
    print("\nThis demo shows the scraper without requiring API keys.")
    print("For AI-powered 60-word summaries, get a free Groq API key:")
    print("https://console.groq.com")
    print()
    
    all_articles = []
    
    # Fetch from demo feeds
    for feed in DEMO_FEEDS:
        items = fetch_feed(feed['url'], feed['source'])
        all_articles.extend(items)
    
    if not all_articles:
        print("\n❌ No articles fetched. Check your internet connection.")
        return
    
    print(f"\n{'='*60}")
    print(f"📱 YOUR 60-WORD GAMING NEWS FEED")
    print(f"{'='*60}")
    
    # Process and display articles
    for i, item in enumerate(all_articles[:6], 1):
        # Create simple summary
        content = item['description'] or item['title']
        summary = simple_summarize(content, 60)
        tags = extract_simple_tags(item['title'], item['description'])
        
        print(f"\n{'─' * 60}")
        print(f"🏷️  {' | '.join(tags) if tags else 'Gaming'}")
        print(f"📰 [{i}] {item['title']}")
        print(f"🏢 {item['source']}")
        print(f"\n   {summary}")
        print(f"\n   🔗 {item['link']}")
    
    print(f"\n{'='*60}")
    print(f"✅ Demo complete! Scraped {len(all_articles[:6])} articles.")
    print()
    print("For AI-powered summaries and personalization:")
    print("1. Get Groq API key: https://console.groq.com")
    print("2. Run: export GROQ_API_KEY='your-key'")
    print("3. Run: python rapid100.py")
    print()


if __name__ == '__main__':
    main()
