#!/usr/bin/env python3
"""
Rapid100 API Server - REST API for the gaming news scraper
"""

import os
import json
from flask import Flask, jsonify, request
from flask_cors import CORS
from rapid100 import Rapid100Scraper, Article

app = Flask(__name__)
CORS(app)

# Config from environment
DB_PATH = os.getenv('RAPID100_DB', 'rapid100.db')
GROQ_KEY = os.getenv('GROQ_API_KEY')
GEMINI_KEY = os.getenv('GEMINI_API_KEY')
AI_PROVIDER = os.getenv('AI_PROVIDER', 'auto')
ARTICLE_DELAY = float(os.getenv('ARTICLE_DELAY', '8'))  # seconds between articles (Groq rate limit)
SB_URL = os.getenv('SUPABASE_URL')
SB_KEY = os.getenv('SUPABASE_ANON_KEY')

scraper = Rapid100Scraper(
    groq_api_key=GROQ_KEY,
    db_path=DB_PATH,
    ai_provider=AI_PROVIDER,
    gemini_key=GEMINI_KEY,
    supabase_url=SB_URL,
    supabase_key=SB_KEY,
)


def article_to_dict(art: Article) -> dict:
    """Convert Article to dictionary."""
    return {
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
        'read_time_seconds': art.read_time_seconds,
    }


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok', 'service': 'Rapid100 API'})


@app.route('/api/scrape', methods=['POST'])
def scrape():
    """Trigger article scraping."""
    data = request.get_json() or {}
    max_per_feed = data.get('max_per_feed', 3)
    article_delay = float(data.get('article_delay', ARTICLE_DELAY))

    if AI_PROVIDER == 'groq' and not GROQ_KEY:
        return jsonify({'error': 'GROQ_API_KEY not configured'}), 500

    try:
        articles = scraper.scrape_feeds(max_per_feed=max_per_feed, article_delay=article_delay)
        return jsonify({
            'success': True,
            'articles_scraped': len(articles),
            'supabase_sync': SB_URL is not None,
            'articles': [article_to_dict(a) for a in articles[:10]]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/feed', methods=['GET'])
def get_feed():
    """Get news feed."""
    personalized = request.args.get('personalized', 'false').lower() == 'true'
    limit = int(request.args.get('limit', 20))
    
    articles = scraper.get_feed(personalized=personalized, limit=limit)
    
    return jsonify({
        'personalized': personalized,
        'count': len(articles),
        'articles': [article_to_dict(a) for a in articles]
    })


@app.route('/api/article/<article_id>', methods=['GET'])
def get_article(article_id):
    """Get single article by ID."""
    import sqlite3
    
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT * FROM articles WHERE id = ?", (article_id,)
    ).fetchone()
    conn.close()
    
    if not row:
        return jsonify({'error': 'Article not found'}), 404
    
    art = Article(
        id=row[0], title=row[1], summary_100w=row[2], full_summary=row[3],
        source=row[4], source_url=row[5], image_url=row[6], author=row[7],
        published_at=row[8], tags=json.loads(row[9]), category=row[10],
        read_time_seconds=len(row[2].split()) * 3, fetched_at=row[11]
    )
    
    return jsonify(article_to_dict(art))


@app.route('/api/article/<article_id>/read', methods=['POST'])
def record_read(article_id):
    """Record article read."""
    data = request.get_json() or {}
    dwell_seconds = data.get('dwell_seconds', 30)
    
    scraper.record_read(article_id, dwell_seconds)
    
    return jsonify({'success': True, 'article_id': article_id})


@app.route('/api/search', methods=['GET'])
def search():
    """Search articles."""
    query = request.args.get('q', '')
    limit = int(request.args.get('limit', 10))
    
    if not query:
        return jsonify({'error': 'Query required'}), 400
    
    import sqlite3
    
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT * FROM articles 
        WHERE title LIKE ? OR summary_100w LIKE ? OR tags LIKE ?
        ORDER BY fetched_at DESC
        LIMIT ?
    """, (f'%{query}%', f'%{query}%', f'%{query}%', limit)).fetchall()
    conn.close()
    
    articles = []
    for row in rows:
        art = Article(
            id=row[0], title=row[1], summary_100w=row[2], full_summary=row[3],
            source=row[4], source_url=row[5], image_url=row[6], author=row[7],
            published_at=row[8], tags=json.loads(row[9]), category=row[10],
            read_time_seconds=len(row[2].split()) * 3, fetched_at=row[11]
        )
        articles.append(article_to_dict(art))
    
    return jsonify({
        'query': query,
        'count': len(articles),
        'articles': articles
    })


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get reading statistics."""
    stats = scraper.get_stats()
    return jsonify(stats)


@app.route('/api/tags', methods=['GET'])
def get_tags():
    """Get all unique tags."""
    import sqlite3
    
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT tags FROM articles").fetchall()
    conn.close()
    
    all_tags = set()
    for row in rows:
        tags = json.loads(row[0])
        all_tags.update(tags)
    
    return jsonify({
        'count': len(all_tags),
        'tags': sorted(list(all_tags))
    })


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'false').lower() == 'true'
    
    print(f"🚀 Rapid100 API Server starting on port {port}")
    print(f"📁 Database: {DB_PATH}")
    print(f"🤖 AI Provider: {AI_PROVIDER}")
    print(f"🔑 Groq API: {'Configured' if GROQ_KEY else 'NOT CONFIGURED'}")
    print(f"🔑 Gemini API: {'Configured' if GEMINI_KEY else 'NOT CONFIGURED'}")
    print(f"☁️  Supabase: {'Configured' if SB_URL else 'NOT CONFIGURED (articles won\'t sync to Pixel Pulse)'}")
    print(f"⏱️  Article delay: {ARTICLE_DELAY}s")

    app.run(host='0.0.0.0', port=port, debug=debug)
