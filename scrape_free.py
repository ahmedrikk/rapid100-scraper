#!/usr/bin/env python3
"""
Rapid100 Free Scraper - Rotates between free tiers to maximize usage

Strategy:
1. Try Gemini first (1,500 req/day free) - fastest & cheapest
2. Fallback to Ollama (unlimited free) - uses local GPU
3. Fallback to Groq (20 req/min free) - reliable backup

No API costs!
"""

import os
import sys
import time
from rapid100 import Rapid100Scraper

def get_working_provider():
    """Find a working AI provider."""
    providers = []
    
    # Check Gemini
    if os.getenv('GEMINI_API_KEY'):
        providers.append(('gemini', os.getenv('GEMINI_API_KEY')))
    
    # Check Ollama
    try:
        import requests
        resp = requests.get("http://localhost:11434/api/tags", timeout=2)
        if resp.status_code == 200:
            providers.append(('ollama', None))
    except:
        pass
    
    # Check Groq
    if os.getenv('GROQ_API_KEY'):
        providers.append(('groq', os.getenv('GROQ_API_KEY')))
    
    return providers

def main():
    print("🚀 Rapid100 Free Scraper (No API Costs!)")
    print("=" * 60)
    
    # Check available providers
    providers = get_working_provider()
    
    if not providers:
        print("\n❌ No AI providers configured!")
        print("\nSet at least one of these environment variables:")
        print("  export GEMINI_API_KEY='...'  # Get free key: https://aistudio.google.com/app/apikey")
        print("  export GROQ_API_KEY='gsk_...'  # Get free key: https://console.groq.com")
        print("\nOr install Ollama for local AI:")
        print("  https://ollama.com")
        sys.exit(1)
    
    print("\n📡 Available providers:")
    for name, _ in providers:
        if name == 'gemini':
            print(f"  ✅ Gemini (1,500 free requests/day)")
        elif name == 'ollama':
            print(f"  ✅ Ollama (unlimited local AI)")
        elif name == 'groq':
            print(f"  ✅ Groq (20 requests/min free)")
    
    # Try each provider
    for provider_name, api_key in providers:
        print(f"\n🤖 Trying {provider_name.upper()}...")
        print("-" * 40)
        
        try:
            scraper = Rapid100Scraper(
                groq_api_key=api_key if provider_name == 'groq' else None,
                ai_provider=provider_name
            )
            if provider_name == 'gemini':
                scraper.ai.gemini_key = api_key
            
            articles = scraper.scrape_feeds(max_per_feed=3)
            
            if articles:
                print(f"\n✅ SUCCESS! Scraped {len(articles)} articles with {provider_name}")
                
                # Display results
                print("\n📱 Latest Articles:")
                for art in articles[:3]:
                    word_count = len(art.summary_100w.split())
                    print(f"\n  🏷️  {' | '.join(art.tags[:3])}")
                    print(f"  📰 {art.title}")
                    print(f"  📝 {word_count} words | {art.source}")
                
                return
            
        except Exception as e:
            print(f"  ⚠️  {provider_name} failed: {e}")
            continue
    
    print("\n❌ All providers failed. Try again later.")
    print("\nTip: Gemini quota resets daily at midnight Pacific Time")

if __name__ == '__main__':
    main()
