#!/usr/bin/env python3
"""
Rapid100 CLI - Command line interface for the gaming news scraper
"""

import os
import sys
import time
import argparse
import json
from datetime import datetime
from rapid100 import Rapid100Scraper, Article


def print_article(article: Article, index: int = None, detailed: bool = False):
    """Pretty print an article."""
    prefix = f"[{index}] " if index else ""
    
    # Header with tags
    tags_str = " | ".join(article.tags[:4]) if article.tags else "Gaming"
    print(f"\n{'─' * 60}")
    print(f"🏷️  {tags_str}")
    print(f"📰 {prefix}{article.title}")
    print(f"🏢 {article.source} • 👤 {article.author}")
    print(f"📅 {article.published_at[:10]} • ⏱️  ~{article.read_time_seconds}s read")
    
    # 100-word summary
    print(f"\n   {article.summary_100w}")
    
    # Full summary if detailed
    if detailed:
        print(f"\n   📖 Full Summary:\n   {article.full_summary}")
    
    print(f"\n   🔗 {article.source_url}")
    print(f"{'─' * 60}")


def cmd_scrape(args):
    """Scrape fresh articles from RSS feeds."""
    api_key = args.api_key or os.getenv('GROQ_API_KEY')
    gemini_key = args.gemini_key or os.getenv('GEMINI_API_KEY')
    
    # Check if we need an API key
    if args.provider == 'groq' and not api_key:
        print("❌ Error: Groq API key required. Set GROQ_API_KEY or use --api-key")
        sys.exit(1)
    
    if args.provider == 'gemini' and not gemini_key:
        print("❌ Error: Gemini API key required. Set GEMINI_API_KEY or use --gemini-key")
        print("   Get a free key at: https://aistudio.google.com/app/apikey")
        sys.exit(1)
    
    print("🚀 Rapid100 Scraper")
    print(f"📁 Database: {args.db}")
    print(f"🤖 AI Provider: {args.provider}")
    print(f"📰 Max articles per feed: {args.max_per_feed}")
    print()
    
    sb_url = os.getenv("SUPABASE_URL")
    sb_key = os.getenv("SUPABASE_ANON_KEY")
    scraper = Rapid100Scraper(
        groq_api_key=api_key, db_path=args.db, ai_provider=args.provider,
        gemini_key=gemini_key, supabase_url=sb_url, supabase_key=sb_key,
    )
    
    articles = scraper.scrape_feeds(max_per_feed=args.max_per_feed, article_delay=args.article_delay)

    print(f"\n✅ Scraped {len(articles)} articles!")

    if args.show:
        print("\n📱 Latest Articles:")
        for i, art in enumerate(articles[:args.show], 1):
            print_article(art, i)


def cmd_feed(args):
    """Show personalized or chronological feed."""
    scraper = Rapid100Scraper(db_path=args.db)
    
    articles = scraper.get_feed(personalized=args.personalized, limit=args.limit)
    
    mode = "Personalized" if args.personalized else "Latest"
    print(f"\n📱 {mode} Feed ({len(articles)} articles)")
    
    for i, art in enumerate(articles, 1):
        print_article(art, i, detailed=args.detailed)


def cmd_read(args):
    """Record that you read an article."""
    scraper = Rapid100Scraper(db_path=args.db)
    scraper.record_read(args.article_id, args.dwell_seconds)
    print(f"✅ Recorded read: {args.article_id} ({args.dwell_seconds}s)")


def cmd_stats(args):
    """Show reading statistics."""
    scraper = Rapid100Scraper(db_path=args.db)
    stats = scraper.get_stats()
    
    print("\n📊 Rapid100 Statistics")
    print(f"{'─' * 40}")
    print(f"📚 Total articles: {stats['total_articles']}")
    print(f"👁️  Total reads: {stats['total_reads']}")
    
    if stats['top_interests']:
        print(f"\n🔥 Top Interests:")
        for interest in stats['top_interests'][:10]:
            bar = "█" * int(interest['score'])
            print(f"   {interest['tag']:<20} {bar} ({interest['score']})")


def cmd_export(args):
    """Export articles to JSON."""
    scraper = Rapid100Scraper(db_path=args.db)
    articles = scraper.get_feed(personalized=False, limit=args.limit)
    
    data = [{
        'id': art.id,
        'title': art.title,
        'summary_100w': art.summary_100w,
        'full_summary': art.full_summary,
        'source': art.source,
        'source_url': art.source_url,
        'image_url': art.image_url,
        'author': art.author,
        'published_at': art.published_at,
        'tags': art.tags,
        'category': art.category,
    } for art in articles]
    
    with open(args.output, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"✅ Exported {len(data)} articles to {args.output}")


def cmd_watch(args):
    """Run scraper on a loop — live feed mode."""
    interval = args.interval * 60  # convert minutes to seconds
    api_key = args.api_key or os.getenv('GROQ_API_KEY')
    gemini_key = args.gemini_key or os.getenv('GEMINI_API_KEY')
    provider = args.provider or 'auto'

    sb_url = os.getenv("SUPABASE_URL")
    sb_key = os.getenv("SUPABASE_ANON_KEY")

    print(f"👁️  Live feed mode — scraping every {args.interval} minute(s). Ctrl+C to stop.\n")

    run = 0
    while True:
        run += 1
        now = datetime.now().strftime('%H:%M:%S')
        print(f"\n{'=' * 60}")
        print(f"🔄 Run #{run} — {now}")
        print(f"{'=' * 60}")

        try:
            scraper = Rapid100Scraper(
                groq_api_key=api_key, db_path=args.db, ai_provider=provider,
                gemini_key=gemini_key, supabase_url=sb_url, supabase_key=sb_key,
            )
            articles = scraper.scrape_feeds(max_per_feed=args.max_per_feed, article_delay=args.article_delay)
            print(f"\n✅ Run #{run} done — {len(articles)} new articles synced")
        except KeyboardInterrupt:
            print("\n\n👋 Live feed stopped.")
            sys.exit(0)
        except Exception as e:
            print(f"\n⚠️  Run #{run} failed: {e}")

        next_run = datetime.now().strftime('%H:%M:%S')
        print(f"\n⏳ Next run in {args.interval} minute(s) (at ~{next_run})... Ctrl+C to stop.")
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\n👋 Live feed stopped.")
            sys.exit(0)


def cmd_search(args):
    """Search articles by keyword."""
    import sqlite3
    
    conn = sqlite3.connect(args.db)
    cursor = conn.execute("""
        SELECT * FROM articles 
        WHERE title LIKE ? OR summary_100w LIKE ? OR tags LIKE ?
        ORDER BY fetched_at DESC
        LIMIT ?
    """, (f'%{args.query}%', f'%{args.query}%', f'%{args.query}%', args.limit))
    
    rows = cursor.fetchall()
    conn.close()
    
    print(f"\n🔍 Search results for '{args.query}' ({len(rows)} found)")
    
    for i, row in enumerate(rows, 1):
        art = Article(
            id=row[0], title=row[1], summary_100w=row[2], full_summary=row[3],
            source=row[4], source_url=row[5], image_url=row[6], author=row[7],
            published_at=row[8], tags=json.loads(row[9]), category=row[10],
            read_time_seconds=len(row[2].split()) * 3, fetched_at=row[11]
        )
        print_article(art, i)


def main():
    parser = argparse.ArgumentParser(
        description="Rapid100 - Gaming news scraper with 100-word AI summaries",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape with Gemini (CHEAPEST - $0.075/1M tokens!)
  export GEMINI_API_KEY="..."
  python cli.py scrape --provider gemini --max-per-feed 5
  
  # Scrape with Ollama (local AI)
  python cli.py scrape --provider ollama --max-per-feed 5
  
  # Scrape with Groq API
  export GROQ_API_KEY="gsk_..."
  python cli.py scrape --provider groq --max-per-feed 5
  
  # Auto-detect (tries Gemini > Ollama > Groq)
  python cli.py scrape --max-per-feed 5
  
  # View personalized feed
  python cli.py feed --personalized --limit 10
  
  # Search articles
  python cli.py search "GTA6" --limit 5
  
  # View stats
  python cli.py stats
  
  # Export to JSON
  python cli.py export --output articles.json --limit 50

  # Live feed — scrape every 30 minutes forever
  python cli.py watch --interval 30 --max-per-feed 3

  # Live feed with Ollama every 15 minutes
  python cli.py watch --interval 15 --provider ollama
        """
    )
    
    parser.add_argument('--db', default='rapid100.db', help='Database file path')
    parser.add_argument('--api-key', help='Groq API key (or set GROQ_API_KEY env var)')
    parser.add_argument('--gemini-key', help='Google Gemini API key (or set GEMINI_API_KEY env var)')
    parser.add_argument('--provider', choices=['auto', 'groq', 'ollama', 'gemini'], default='auto',
                        help='AI provider: auto (default), groq, ollama, or gemini (cheapest!)')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Scrape command
    scrape_parser = subparsers.add_parser('scrape', help='Scrape articles from RSS feeds')
    scrape_parser.add_argument('--max-per-feed', type=int, default=5, help='Max articles per feed')
    scrape_parser.add_argument('--show', type=int, help='Show N latest articles after scraping')
    scrape_parser.add_argument('--provider', choices=['auto', 'groq', 'ollama', 'gemini'], default=None,
                               help='Override AI provider for this run')
    scrape_parser.add_argument('--gemini-key', help='Gemini API key for this run')
    scrape_parser.add_argument('--article-delay', type=float, default=0,
                               help='Seconds to wait between articles (use ~3 for Groq free tier)')
    scrape_parser.set_defaults(func=cmd_scrape)
    
    # Feed command
    feed_parser = subparsers.add_parser('feed', help='Show news feed')
    feed_parser.add_argument('--personalized', action='store_true', help='Show personalized feed')
    feed_parser.add_argument('--limit', type=int, default=20, help='Number of articles')
    feed_parser.add_argument('--detailed', action='store_true', help='Show full summaries')
    feed_parser.set_defaults(func=cmd_feed)
    
    # Read command
    read_parser = subparsers.add_parser('read', help='Record article read')
    read_parser.add_argument('article_id', help='Article ID')
    read_parser.add_argument('--dwell-seconds', type=int, default=30, help='Time spent reading')
    read_parser.set_defaults(func=cmd_read)
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show reading statistics')
    stats_parser.set_defaults(func=cmd_stats)
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export articles to JSON')
    export_parser.add_argument('--output', '-o', default='articles.json', help='Output file')
    export_parser.add_argument('--limit', type=int, default=100, help='Number of articles')
    export_parser.set_defaults(func=cmd_export)
    
    # Watch command (live feed)
    watch_parser = subparsers.add_parser('watch', help='Live feed — scrape on a schedule')
    watch_parser.add_argument('--interval', type=int, default=30, help='Minutes between scrape runs (default: 30)')
    watch_parser.add_argument('--max-per-feed', type=int, default=3, help='Max articles per feed per run')
    watch_parser.add_argument('--provider', choices=['auto', 'groq', 'ollama', 'gemini'], default=None,
                              help='AI provider override')
    watch_parser.add_argument('--gemini-key', help='Gemini API key for this session')
    watch_parser.add_argument('--article-delay', type=float, default=8,
                              help='Seconds to wait between articles (default: 8 for Groq free tier)')
    watch_parser.set_defaults(func=cmd_watch)

    # Search command
    search_parser = subparsers.add_parser('search', help='Search articles')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--limit', type=int, default=10, help='Max results')
    search_parser.set_defaults(func=cmd_search)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == '__main__':
    main()
