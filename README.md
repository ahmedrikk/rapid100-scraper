# 🎮 Rapid100 - Gaming News Scraper

An **Inshorts-style** gaming news aggregator that scrapes articles from major gaming sites and uses AI to condense them into tight **100-word summaries**.

## Features

- 📡 **RSS Feed Aggregation** - Fetches from 11+ gaming news sources
- 🤖 **AI Summarization** - Uses Groq API (Llama 3.3) for 100-word summaries
- 🏷️ **Smart Tagging** - Extracts game titles, studios, people, events
- 📱 **Personalization** - Learns from your reading habits
- 🗄️ **Local Database** - SQLite storage with full-text search
- 🔌 **REST API** - Flask API for integration

## Quick Start

### 1. Install Dependencies

```bash
cd scraper
pip install -r requirements.txt
```

### 2. Get API Key (Choose One)

**Option A: Google Gemini (CHEAPEST - $0.075/1M tokens!)**
1. Get free key at https://aistudio.google.com/app/apikey
2. Set as environment variable:
```bash
export GEMINI_API_KEY="your-key-here"
```

**Option B: Groq API (Fast, free tier)**
1. Sign up at https://console.groq.com (free tier available)
2. Set as environment variable:
```bash
export GROQ_API_KEY="gsk_..."
```

**Option C: Ollama (FREE - Local AI)**
1. Install Ollama: https://ollama.com
2. Pull a model: `ollama pull deepseek-r1:8b`
3. No API key needed!

### 3. Run the Scraper

```bash
# With Gemini (cheapest!)
python cli.py scrape --provider gemini --max-per-feed 5 --show 5

# With Ollama (free local AI)
python cli.py scrape --provider ollama --max-per-feed 5 --show 5

# With Groq
export GROQ_API_KEY="gsk_..."
python cli.py scrape --provider groq --max-per-feed 5 --show 5

# Auto-detect (tries Gemini → Ollama → Groq)
python cli.py scrape --max-per-feed 5 --show 5
```

## CLI Usage

```bash
# Scrape fresh articles
python cli.py scrape --max-per-feed 5

# View personalized feed
python cli.py feed --personalized --limit 10

# View latest feed (chronological)
python cli.py feed --limit 20

# Search articles
python cli.py search "GTA6" --limit 5

# View reading stats
python cli.py stats

# Export to JSON
python cli.py export --output articles.json --limit 50

# Record that you read an article
python cli.py read <article_id> --dwell-seconds 45
```

## API Server

Start the REST API:

```bash
python api.py
```

Endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/scrape` | POST | Trigger scraping |
| `/api/feed` | GET | Get news feed |
| `/api/article/<id>` | GET | Get single article |
| `/api/article/<id>/read` | POST | Record read |
| `/api/search?q=query` | GET | Search articles |
| `/api/stats` | GET | Reading stats |
| `/api/tags` | GET | All unique tags |

### Example API Usage

```bash
# Trigger scraping
curl -X POST http://localhost:5000/api/scrape \
  -H "Content-Type: application/json" \
  -d '{"max_per_feed": 3}'

# Get personalized feed
curl "http://localhost:5000/api/feed?personalized=true&limit=10"

# Search
curl "http://localhost:5000/api/search?q=Elden+Ring&limit=5"
```

## Data Model

### Article

```python
{
    "id": "unique-hash",
    "title": "Article Title",
    "summary_100w": "100-word summary...",
    "full_summary": "Longer 100-120 word summary...",
    "source": "IGN",
    "source_url": "https://ign.com/...",
    "image_url": "https://...",
    "author": "Author Name",
    "published_at": "2024-01-15T10:30:00",
    "tags": ["GTA6", "RockstarGames"],
    "category": "Gaming",
    "read_time_seconds": 15
}
```

## Supported RSS Sources

- IGN
- GameSpot
- Kotaku
- Polygon
- Dexerto
- Eurogamer
- PC Gamer
- Rock Paper Shotgun
- Gematsu
- VG247
- Nintendo Life

## How It Works

1. **RSS Fetching** - Fetches article metadata from RSS feeds
2. **Content Extraction** - If RSS description is too short (<50 words), extracts full article text
   - Uses `newspaper3k` if available (better extraction, auto-detects article body)
   - Falls back to regex-based scraper with content selectors
   - Truncates to first 600 words (key facts are usually here, saves API tokens)
3. **AI Summarization** - Sends content to Groq API for 100-word summary
   - **3-sentence structure**: What happened | Why it matters | What's next
   - **Validation + Retry Loop**: Checks word count (55-75 target), retries if invalid
   - **Title validation**: Ensures 3-12 word headlines
   - Falls back to truncated text if AI fails after 3 retries
4. **Tag Extraction** - AI extracts named entities (games, studios, people)
5. **Storage** - Saves to SQLite database
6. **Personalization** - Ranks articles based on your reading history

## Personalization Algorithm

The scraper tracks:
- Articles you read (and for how long)
- Tags in those articles
- Builds a preference score per tag
- Ranks new articles by relevance to your interests

## Configuration

Environment variables:

```bash
GEMINI_API_KEY=your-key        # Google Gemini API (cheapest option!)
GROQ_API_KEY=your-api-key      # Groq API key
RAPID100_DB=rapid100.db          # Database path (default: rapid100.db)
PORT=5000                      # API server port
DEBUG=false                    # Flask debug mode
```

### AI Provider Pricing Comparison (per 1M tokens)

| Provider | Input Cost | Output Cost | Est. Monthly Cost* | Speed |
|----------|------------|-------------|-------------------|-------|
| **Gemini 2.0 Flash** | **$0.075** | **$0.30** | **~$6** | Fast |
| DeepSeek V3 | $0.28 | $0.42 | ~$15 | Moderate |
| Groq (Llama) | ~$0.59 | ~$0.79 | ~$18 | ⚡ Fastest |
| Kimi K2.5 | $0.60 | $2.50 | ~$45 | Moderate |
| Claude Haiku | $0.80 | $4.00 | ~$66 | Fast |
| GPT-4o mini | $0.15 | $0.60 | ~$12 | Fast |
| GPT-4o | $2.50 | $10.00 | ~$168 | Fast |

*Based on 1,000 articles/day (~600 input + 100 output tokens each)

**💡 Recommendation: Use Gemini Flash** — It's 10-20x cheaper than competitors with excellent quality for summarization.

### Optional: Better Article Extraction

For improved article text extraction, install `newspaper3k`:

```bash
pip install newspaper3k lxml_html_clean
```

This provides better content detection and boilerplate removal than the regex-based fallback.

## Why 3 Sentences Instead of Word Count?

LLMs process tokens, not words. Asking for "exactly 100 words" produces inconsistent results (±25 words). 

**The fix**: Ask for **3 sentences**. Three well-formed sentences naturally produce 55-75 words — within the Inshorts-style range. The validation loop then counts words and retries if outside the target range (55-75 words).

This approach is inspired by how Inshorts actually worked: human editors wrote tight 3-sentence summaries, not AI word-counting.

## Word Count Validation

The summarizer implements a **validation + retry loop** to ensure consistent output:

| Check | Target | Action if Failed |
|-------|--------|------------------|
| Summary length | 55-75 words | Retry with corrective prompt |
| Title length | 3-12 words | Retry with title feedback |
| Tag count | 2+ tags | Retry if too few |
| JSON format | Valid JSON | Retry with same prompt |

Max 3 retries per article before falling back to truncated text.

## Integration with Pixel Pulse

To use this scraper with the Pixel Pulse project:

1. Run the scraper to populate the database
2. Export articles to JSON:
   ```bash
   python cli.py export --output ../pixel-pulse/public/articles.json
   ```
3. Or modify Pixel Pulse to call the API directly

## Architecture Notes

### The Inshorts Insight

Inshorts didn't use AI in their early days — they had human editors writing 3-sentence summaries. The "technology" was editorial discipline, not automation. 

This scraper replicates that approach:
- **3-sentence structure** → Consistent length without counting words
- **Validation loop** → Machine-checks what humans would catch
- **Retry with feedback** → Iterative improvement like an editor would do

### Token Efficiency

- Input capped at 600 words (key facts are in the first 2/3 of articles)
- 3-sentence output ≈ 100 tokens vs. unlimited prose
- Reduces API costs by ~40% vs. processing full articles

## License

MIT
