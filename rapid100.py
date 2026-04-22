#!/usr/bin/env python3
"""
Rapid100 - Gaming News Scraper
An Inshorts-style news aggregator for gaming articles.
Condenses articles into 100-word summaries using AI.
"""

import os
import re
import json
import sqlite3
import hashlib
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Set, Tuple
from urllib.parse import urlparse
from collections import Counter
import html

# RSS Feed sources
RSS_FEEDS = [
    {"url": "https://www.ign.com/rss/articles/feed?tags=news", "source": "IGN"},
    {"url": "https://www.gamespot.com/feeds/news/", "source": "GameSpot"},
    {"url": "https://kotaku.com/feed", "source": "Kotaku"},
    {"url": "https://www.polygon.com/rss/index.xml", "source": "Polygon"},
    {"url": "https://www.dexerto.com/gaming/feed/", "source": "Dexerto"},
    {"url": "https://www.eurogamer.net/feed/news", "source": "Eurogamer"},
    {"url": "https://www.pcgamer.com/rss/", "source": "PCGamer"},
    {"url": "https://www.rockpapershotgun.com/feed", "source": "RPS"},
    {"url": "https://www.gematsu.com/feed", "source": "Gematsu"},
    {"url": "https://www.vg247.com/feed", "source": "VG247"},
    {"url": "https://www.nintendolife.com/feeds/news", "source": "NintendoLife"},
]


@dataclass
class Article:
    """Represents a processed gaming article."""
    id: str
    title: str
    summary_100w: str  # 100-word summary (Inshorts style)
    full_summary: str  # Longer summary for detail view
    source: str
    source_url: str
    image_url: Optional[str]
    author: str
    published_at: str
    tags: List[str]
    category: str
    read_time_seconds: int  # Estimated reading time
    fetched_at: str


class RSSParser:
    """Parse RSS feeds to extract article metadata."""
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (compatible; Rapid100Bot/1.0; +https://rapid100.app)",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }
    
    def fetch_feed(self, feed_url: str, timeout: int = 10) -> Optional[str]:
        """Fetch RSS feed content."""
        try:
            resp = requests.get(feed_url, headers=self.HEADERS, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            print(f"  ✗ Failed to fetch {feed_url}: {e}")
            return None
    
    def parse(self, xml_content: str, source: str, max_items: int = 5) -> List[Dict]:
        """Parse RSS XML and extract items."""
        items = []
        try:
            # Handle both RSS and Atom formats
            root = ET.fromstring(xml_content.encode('utf-8'))
            
            # Try RSS 2.0 first
            channel = root.find('channel')
            if channel is not None:
                rss_items = channel.findall('item')[:max_items]
            else:
                # Atom format
                ns = {'atom': 'http://www.w3.org/2005/Atom'}
                rss_items = root.findall('atom:entry', ns)[:max_items]
            
            for item in rss_items:
                parsed = self._parse_item(item, source)
                if parsed:
                    items.append(parsed)
        except Exception as e:
            print(f"  ✗ Parse error for {source}: {e}")
        
        return items
    
    def _parse_item(self, item: ET.Element, source: str) -> Optional[Dict]:
        """Parse a single RSS item."""
        try:
            # Helper to get text from element
            def get_text(tag: str, ns: str = "") -> str:
                if ns:
                    elem = item.find(f"{{{ns}}}{tag}")
                else:
                    elem = item.find(tag)
                return html.unescape(elem.text.strip()) if elem is not None and elem.text else ""
            
            # Try RSS 2.0
            title = get_text('title')
            link = get_text('link')
            
            # If no link, try atom format
            if not link:
                link_elem = item.find('{http://www.w3.org/2005/Atom}link')
                if link_elem is not None:
                    link = link_elem.get('href', '')
            
            if not title or not link:
                return None
            
            # Get description/content
            description = get_text('description') or get_text('encoded', 'http://purl.org/rss/1.0/modules/content/')
            
            # Get pub date
            pub_date = get_text('pubDate') or get_text('published', 'http://www.w3.org/2005/Atom')
            
            # Get author
            author = get_text('creator', 'http://purl.org/dc/elements/1.1/') or get_text('author') or "Staff Writer"
            
            # Get image from enclosure or content
            image_url = None
            enclosure = item.find('enclosure')
            if enclosure is not None:
                image_url = enclosure.get('url')
            
            if not image_url:
                media = item.find('{http://search.yahoo.com/mrss/}content')
                if media is not None:
                    image_url = media.get('url')
            
            if not image_url and description:
                # Extract from HTML img tag
                img_match = re.search(r'<img[^>]+src="([^"]+)"', description)
                if img_match:
                    image_url = img_match.group(1)
            
            return {
                'title': title,
                'link': link,
                'description': description,
                'pub_date': pub_date,
                'author': author,
                'image_url': image_url,
                'source': source,
            }
        except Exception as e:
            print(f"  ✗ Error parsing item: {e}")
            return None


class ArticleScraper:
    """Scrape full article content from websites."""
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    
    # Common article content selectors (class names)
    CONTENT_SELECTORS = [
        'article-body', 'article-content', 'post-content', 'entry-content',
        'story-body', 'content-body', 'prose', 'richtext', 'article__body',
        'c-content', 'article-text', 'post-body', 'entry-body',
        # PC Gamer specific
        'article_body_content', 'content--article', 'article-body__content'
    ]
    
    def __init__(self):
        self._newspaper_available = self._check_newspaper()
    
    def _check_newspaper(self) -> bool:
        """Check if newspaper3k is available for better extraction."""
        try:
            from newspaper import Article as NewspaperArticle
            return True
        except ImportError:
            return False
    
    def _scrape_with_newspaper(self, url: str, timeout: int = 10) -> Optional[str]:
        """Use newspaper3k for better article extraction."""
        try:
            from newspaper import Article as NewspaperArticle
            article = NewspaperArticle(url)
            article.download()
            article.parse()
            return article.text if article.text else None
        except Exception as e:
            print(f"   ⚠ newspaper3k failed: {e}")
            return None
    
    def scrape(self, url: str, timeout: int = 10, max_words: int = 600) -> Optional[str]:
        """Scrape full article text, truncated to max_words."""
        text = None
        
        # Try newspaper3k first if available (better extraction)
        if self._newspaper_available:
            text = self._scrape_with_newspaper(url, timeout)
            if text:
                print(f"   ✓ Extracted with newspaper3k")
        
        # Fallback to regex-based scraper
        if not text:
            text = self._scrape_with_regex(url, timeout)
        
        if text:
            # Truncate to max_words to save tokens and improve summary quality
            text = self._truncate_text(text, max_words)
            return text if len(text) > 200 else None
        
        return None
    
    def _scrape_with_regex(self, url: str, timeout: int = 10) -> Optional[str]:
        """Fallback regex-based scraper."""
        try:
            resp = requests.get(url, headers=self.HEADERS, timeout=timeout)
            resp.raise_for_status()
            
            content_type = resp.headers.get('content-type', '')
            if 'text/html' not in content_type and 'application/xhtml' not in content_type:
                return None
            
            html_content = resp.text
            text = self._extract_text(html_content)
            text = self._remove_boilerplate(text)
            
            return text
        except Exception as e:
            print(f"  ✗ Regex scrape failed for {url}: {e}")
            return None
    
    def _truncate_text(self, text: str, max_words: int = 600) -> str:
        """Truncate text to max_words. Key facts are usually in first 600 words."""
        words = text.split()
        if len(words) <= max_words:
            return text
        return ' '.join(words[:max_words])
    
    def _extract_text(self, html: str) -> str:
        """Extract article text from HTML."""
        # Remove scripts and styles
        html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL)
        html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.DOTALL)
        
        # Try semantic tags first
        for tag in ['article', 'main']:
            match = re.search(rf'<{tag}[^>]*>(.*?)</{tag}>', html, re.DOTALL | re.IGNORECASE)
            if match:
                text = self._extract_paragraphs(match.group(1))
                if len(text) > 200:
                    return text
        
        # Try content class patterns
        for selector in self.CONTENT_SELECTORS:
            pattern = rf'<div[^>]*class="[^"]*{selector}[^"]*"[^>]*>(.*?)</div>'
            match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
            if match:
                text = self._extract_paragraphs(match.group(1))
                if len(text) > 200:
                    return text
        
        # Fallback: all paragraphs
        text = self._extract_paragraphs(html)
        return text
    
    def _extract_paragraphs(self, html: str) -> str:
        """Extract text from <p> tags."""
        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL | re.IGNORECASE)
        texts = []
        for p in paragraphs:
            text = self._clean_html(p)
            if len(text) > 40:
                texts.append(text)
        return ' '.join(texts)
    
    def _clean_html(self, html_text: str) -> str:
        """Strip HTML tags and decode entities."""
        text = re.sub(r'<[^>]+>', ' ', html_text)
        text = html.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def _remove_boilerplate(self, text: str) -> str:
        """Remove common website boilerplate."""
        # Affiliate disclosures
        text = re.sub(r'When you (purchase|buy) through links[^.]+\.', '', text, flags=re.IGNORECASE)
        text = re.sub(r"Here's how it works\s*\.?\s*", '', text, flags=re.IGNORECASE)

        # Image credits
        text = re.sub(r'\(?Image credit:[^)\n.]{0,80}\)?', '', text, flags=re.IGNORECASE)
        text = re.sub(r'Image:\s*[^.|\n]{0,80}?(via\s+\w+\s*)?(?=[A-Z][a-z])', '', text)

        # Comments and social sharing buttons
        text = re.sub(r'\d+\s+comments?\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\bFollow\b\s*', '', text)
        text = re.sub(r'(Flipboard|Pinterest|Reddit|Whatsapp|Facebook|Twitter|Email)\s+(Share|Follow|it)', '', text, flags=re.IGNORECASE)
        text = re.sub(r'Copy link\s*', '', text, flags=re.IGNORECASE)

        # PC Gamer specific boilerplate
        text = re.sub(r'Join the conversation on\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'Add us as a preferred source on Google\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(
            r'(PC Gamer\s+)?The biggest gaming news,?\s*reviews and hardware deals[^.]*\.',
            '', text, flags=re.IGNORECASE
        )
        text = re.sub(
            r'Keep up to date with the most important stories[^.]*\.',
            '', text, flags=re.IGNORECASE
        )
        text = re.sub(r'as picked by the PC Gamer team[^.]*\.', '', text, flags=re.IGNORECASE)
        text = re.sub(r'Newsletter\s*(PC Gamer\s*)?', '', text, flags=re.IGNORECASE)
        # PC Gamer social/sharing junk
        text = re.sub(r'\d+\s+\.\s*\d+\s+comments?', '', text, flags=re.IGNORECASE)
        text = re.sub(r'PC Gamer is supported by its audience[^.]*\.', '', text, flags=re.IGNORECASE)
        text = re.sub(r'We may earn a (commission|fee)[^.]*\.', '', text, flags=re.IGNORECASE)
        text = re.sub(r'Learn more about how we evaluate and test products[^.]*\.', '', text, flags=re.IGNORECASE)

        # Generic newsletter / subscription prompts
        text = re.sub(r'Sign up (to|for)[^.]{0,80}newsletter[^.]*\.', '', text, flags=re.IGNORECASE)
        text = re.sub(r'Subscribe (to|for)[^.]{0,80}\.', '', text, flags=re.IGNORECASE)
        text = re.sub(r'By submitting your (information|email)[^.]*\.', '', text, flags=re.IGNORECASE)
        text = re.sub(r'You agree to (the\s+)?Terms[^.]*\.', '', text, flags=re.IGNORECASE)
        text = re.sub(r'Privacy Policy[^.]*\.', '', text, flags=re.IGNORECASE)
        text = re.sub(r'(Instant|Exclusive) access to[^.]*\.', '', text, flags=re.IGNORECASE)

        # Read more / Related
        text = re.sub(r'\b(Read more|Related|See also|Jump to)\s*:', '', text, flags=re.IGNORECASE)

        # Timestamps
        text = re.sub(r'\b[A-Z][a-z]{2}\s+\d{1,2},?\s+\d{4},?\s+\d{1,2}:\d{2}\b', '', text)

        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text


class AISummarizer:
    """Use AI (Groq API or Ollama local) to condense articles into summaries with validation + retry."""
    
    GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
    OLLAMA_URL = "http://localhost:11434/api/chat"
    GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    
    # Default models for each provider
    GROQ_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
    OLLAMA_MODELS = ["gemma4:e2b", "qwen3:8b", "deepseek-r1:8b"]
    GEMINI_MODELS = ["gemini-2.0-flash-lite", "gemini-2.0-flash"]  # Cheapest first
    
    # Target: 4-5 sentences ≈ 80-120 words for Inshorts style
    # (Models tend to write shorter sentences, so we adjust targets)
    # For local models (Ollama), we use more lenient ranges since they're slower
    TARGET_WORDS_MIN = 70  # Lower bound for local models
    TARGET_WORDS_MAX = 125
    TARGET_WORDS_IDEAL = 100
    TITLE_MIN_WORDS = 3
    TITLE_MAX_WORDS = 12
    MAX_RETRIES = 3
    
    def __init__(self, api_key: Optional[str] = None, provider: str = "auto", 
                 ollama_models: Optional[List[str]] = None, gemini_key: Optional[str] = None):
        """
        Initialize AI summarizer.
        
        Args:
            api_key: Groq API key (optional if using Ollama/Gemini)
            provider: "groq", "ollama", "gemini", or "auto" (tries Ollama/Gemini first)
            ollama_models: List of Ollama models to try (default: qwen3:8b, deepseek-r1:8b)
            gemini_key: Google Gemini API key (or set GEMINI_API_KEY env var)
        """
        self.api_key = api_key or os.getenv('GROQ_API_KEY')
        self.gemini_key = gemini_key or os.getenv('GEMINI_API_KEY')
        self.provider = provider or 'auto'
        self.ollama_models = ollama_models or self.OLLAMA_MODELS
        
        # Check Ollama availability
        self._ollama_available = self._check_ollama()
        
        if provider == "groq" and not self.api_key:
            raise ValueError("Groq API key required. Set GROQ_API_KEY environment variable.")
        
        if provider == "gemini" and not self.gemini_key:
            raise ValueError("Gemini API key required. Set GEMINI_API_KEY environment variable.")
        
        if provider == "ollama" and not self._ollama_available:
            raise ValueError("Ollama not available. Make sure it's running: ollama serve")
    
    def _check_ollama(self) -> bool:
        """Check if Ollama is running."""
        try:
            resp = requests.get("http://localhost:11434/api/tags", timeout=2)
            return resp.status_code == 200
        except:
            return False
    
    def _get_available_models(self) -> List[Tuple[str, str]]:
        """Get list of available models as (provider, model_name) tuples."""
        models = []
        
        # Priority order: Gemini (cheapest API) > Ollama (free local) > Groq (current)
        if self.provider in ("auto", "gemini") and self.gemini_key:
            for model in self.GEMINI_MODELS:
                models.append(("gemini", model))
        
        if self.provider in ("auto", "ollama") and self._ollama_available:
            # Check which Ollama models are actually available
            try:
                resp = requests.get("http://localhost:11434/api/tags", timeout=5)
                if resp.status_code == 200:
                    available = {m['name'] for m in resp.json().get('models', [])}
                    for model in self.ollama_models:
                        if model in available:
                            models.append(("ollama", model))
            except:
                pass
        
        if self.provider in ("auto", "groq") and self.api_key:
            for model in self.GROQ_MODELS:
                models.append(("groq", model))
        
        return models
    
    def _extract_json(self, text: str) -> Optional[Dict]:
        """Extract JSON from response, handling extra text around it."""
        # Try to find JSON object in the text
        match = re.search(r'\{[\s\S]*\}', text)
        if not match:
            return None
        try:
            return json.loads(match[0])
        except json.JSONDecodeError:
            return None
    
    def _count_words(self, text: str) -> int:
        """Count words in text."""
        return len(text.split())
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt for summarization."""
        return """You are a gaming news editor for "Rapid100" - an Inshorts-style news aggregator.
Your task: Condense gaming news into tight, informative summaries.

WRITING STYLE:
- Confident and specific — like a knowledgeable friend telling you what happened
- Direct, news-wire style. No filler phrases.
- Never use: "dives into", "it's worth noting", "in conclusion", "comprehensive", 
  "significantly", "moreover", "furthermore", "according to", "in a statement"
- Never start with: "In this article", "This article discusses", "This news covers"

SUMMARY STRUCTURE (4-5 sentences, 18-25 words each):
- Sentence 1: What happened (the core news fact) — aim for 20-25 words
- Sentence 2: Key details or context — aim for 20-25 words
- Sentence 3: Why it matters or additional detail — aim for 20-25 words
- Sentence 4: What comes next, reaction, or final context — aim for 20-25 words
- Optional Sentence 5: Brief wrap-up if needed

4-5 sentences × ~22 words = 100 words total. This is your target range (80-120 words).

EXAMPLE GOOD SUMMARY (98 words):
"FromSoftware announced the Shadow of the Erdtree DLC has sold 5 million copies in just three days since its June 21 release. The expansion introduces the Land of Shadow with challenging new bosses, powerful weapons, and fresh areas for players to discover and conquer. This remarkable sales milestone follows the base game's incredible success of 25 million copies sold worldwide since its February 2022 launch. The DLC's strong debut demonstrates the enduring popularity of the Soulslike genre and FromSoftware's masterful game design that keeps players engaged years after release."

TAG RULES (named entities only):
- Game titles: "GTA6", "EldenRing", "BaldursGate3" (PascalCase, no spaces)
- Studios: "RockstarGames", "FromSoftware", "Nintendo"
- People: "HideoKojima", "PhilSpencer"
- Events: "GameAwards2025", "E32025"
- Platform only if hardware-focused: "PS5", "Switch2"

BANNED TAGS (never include): Gaming, News, Game, Games, Update, RPG, FPS, Action, Adventure,
Horror, Review, Preview, Trailer, Gameplay, Streaming, Esports, Entertainment"""

    def _build_user_prompt(self, title: str, content: str, previous_attempt: Optional[Dict] = None) -> str:
        """Build user prompt, optionally including previous attempt feedback."""
        feedback = ""
        if previous_attempt:
            word_count = self._count_words(previous_attempt.get('summary', ''))
            title_word_count = self._count_words(previous_attempt.get('title', ''))
            
            feedback_parts = []
            
            # Check title length
            if title_word_count < self.TITLE_MIN_WORDS or title_word_count > self.TITLE_MAX_WORDS:
                feedback_parts.append(f'PREVIOUS TITLE FAILED: "{previous_attempt.get("title")}" was {title_word_count} words. Title must be {self.TITLE_MIN_WORDS}-{self.TITLE_MAX_WORDS} words. Try again.')
            
            # Check summary length
            if word_count < self.TARGET_WORDS_MIN:
                feedback_parts.append(f'PREVIOUS SUMMARY FAILED: {word_count} words (too short). Must be {self.TARGET_WORDS_MIN}-{self.TARGET_WORDS_MAX} words. Add one specific fact from the article.')
            elif word_count > self.TARGET_WORDS_MAX:
                feedback_parts.append(f'PREVIOUS SUMMARY FAILED: {word_count} words (too long). Must be {self.TARGET_WORDS_MIN}-{self.TARGET_WORDS_MAX} words. Identify the least important detail and CUT it entirely. Do not just rephrase — remove.')
            
            if feedback_parts:
                feedback = "\n\n" + "\n".join(feedback_parts) + "\n\nORIGINAL ARTICLE:\n"
        
        return f"""{feedback}Article Title: {title}

Article Content:
{content[:4000]}

Create a 4-5 sentence summary (target: {self.TARGET_WORDS_IDEAL} words, range: {self.TARGET_WORDS_MIN}-{self.TARGET_WORDS_MAX}).

OUTPUT FORMAT — return ONLY valid JSON, nothing else:
{{
  "title": "rewritten headline {self.TITLE_MIN_WORDS}-{self.TITLE_MAX_WORDS} words",
  "summary": "your 4-5 sentence summary here",
  "word_count": <integer>,
  "tags": ["tag1", "tag2", "tag3"]
}}"""

    def _call_api(self, system_prompt: str, user_prompt: str, provider: str, model: str) -> Optional[Dict]:
        """Call AI API (Groq, Ollama, or Gemini) and return parsed response."""
        try:
            if provider == "ollama":
                return self._call_ollama(system_prompt, user_prompt, model)
            elif provider == "gemini":
                return self._call_gemini(system_prompt, user_prompt, model)
            else:
                return self._call_groq(system_prompt, user_prompt, model)
        except Exception as e:
            print(f"  ⚠ API call failed ({provider}/{model}): {e}")
            return None
    
    def _call_groq(self, system_prompt: str, user_prompt: str, model: str) -> Optional[Dict]:
        """Call Groq API."""
        resp = requests.post(
            self.GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
                "response_format": {"type": "json_object"},
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        
        content_raw = data['choices'][0]['message']['content']
        result = self._extract_json(content_raw)
        
        if result:
            result['model_used'] = f"groq:{model}"
        return result
    
    def _call_ollama(self, system_prompt: str, user_prompt: str, model: str) -> Optional[Dict]:
        """Call Ollama local API."""
        # Combine system and user prompt for Ollama
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        resp = requests.post(
            self.OLLAMA_URL,
            json={
                "model": model,
                "messages": [
                    {"role": "user", "content": full_prompt},
                ],
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 800,  # Enough for 100w summary + JSON overhead
                },
            },
            timeout=90,  # Local models can be slower
        )
        resp.raise_for_status()
        data = resp.json()
        
        content_raw = data['message']['content']
        
        # Handle Deepseek-R1 thinking chains
        # Deepseek outputs: <thinking>...</thinking>actual response
        # or ...done thinking.\n\nactual response
        if '...done thinking.' in content_raw:
            content_raw = content_raw.split('...done thinking.')[-1].strip()
        
        result = self._extract_json(content_raw)
        
        if result:
            result['model_used'] = f"ollama:{model}"
        return result
    
    def _call_gemini(self, system_prompt: str, user_prompt: str, model: str) -> Optional[Dict]:
        """Call Google Gemini API."""
        url = f"{self.GEMINI_API_URL}/{model}:generateContent?key={self.gemini_key}"
        
        # Combine prompts for Gemini
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        resp = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{
                    "parts": [{"text": full_prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 500,
                    "responseMimeType": "application/json",
                }
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        
        # Extract text from Gemini response
        content_raw = data['candidates'][0]['content']['parts'][0]['text']
        result = self._extract_json(content_raw)
        
        if result:
            result['model_used'] = f"gemini:{model}"
        return result
    
    def _validate_result(self, result: Dict) -> Tuple[bool, List[str]]:
        """Validate the AI result. Returns (is_valid, list_of_errors)."""
        errors = []
        
        if not result:
            errors.append("No result returned")
            return False, errors
        
        # Check title
        title = result.get('title', '')
        title_word_count = self._count_words(title)
        if title_word_count < self.TITLE_MIN_WORDS or title_word_count > self.TITLE_MAX_WORDS:
            errors.append(f"Title length: {title_word_count} words (need {self.TITLE_MIN_WORDS}-{self.TITLE_MAX_WORDS})")
        
        # Check summary
        summary = result.get('summary', '')
        word_count = self._count_words(summary)
        if word_count < self.TARGET_WORDS_MIN or word_count > self.TARGET_WORDS_MAX:
            errors.append(f"Summary length: {word_count} words (need {self.TARGET_WORDS_MIN}-{self.TARGET_WORDS_MAX})")
        
        # Check tags
        tags = result.get('tags', [])
        if not tags or len(tags) < 2:
            errors.append("Too few tags")
        
        return len(errors) == 0, errors
    
    def summarize(self, title: str, content: str) -> Dict[str, str]:
        """
        Summarize article with validation + retry loop.
        Returns dict with validated summary or fallback.
        """
        system_prompt = self._build_system_prompt()
        previous_attempt = None
        
        # Get available models
        available_models = self._get_available_models()
        if not available_models:
            print("   ⚠ No AI models available (check Ollama or GROQ_API_KEY)")
            return self._create_fallback(title, content)
        
        for attempt in range(1, self.MAX_RETRIES + 1):
            # Build prompt with feedback from previous failed attempt
            user_prompt = self._build_user_prompt(title, content, previous_attempt)
            
            # Try each available model
            for provider, model in available_models:
                print(f"   🤖 Attempt {attempt}/{self.MAX_RETRIES} with {provider}:{model}...")
                
                result = self._call_api(system_prompt, user_prompt, provider, model)
                
                if not result:
                    continue
                
                # Validate result
                is_valid, errors = self._validate_result(result)
                
                if is_valid:
                    word_count = self._count_words(result['summary'])
                    print(f"   ✓ Valid summary: {word_count} words")
                    return {
                        'title': result['title'],
                        'summary_100w': result['summary'],
                        'full_summary': result['summary'],  # Same for now, could be expanded
                        'tags': result.get('tags', [])[:6],
                        'model_used': result.get('model_used', f'{provider}:{model}'),
                        'attempts': attempt,
                        'word_count': word_count,
                    }
                else:
                    print(f"   ⚠ Validation failed: {', '.join(errors)}")
                    previous_attempt = result
        
        # All retries failed - create fallback
        return self._create_fallback(title, content)
    
    def _create_fallback(self, title: str, content: str) -> Dict[str, str]:
        """Create a fallback summary when AI fails."""
        print(f"   ⚠ All retries failed, using fallback")
        words = content.split()[:self.TARGET_WORDS_IDEAL]
        fallback_summary = ' '.join(words) + ('...' if len(content.split()) > self.TARGET_WORDS_IDEAL else '')
        
        return {
            'title': title,
            'summary_100w': fallback_summary,
            'full_summary': content[:500],
            'tags': [],
            'model_used': 'fallback',
            'attempts': self.MAX_RETRIES,
            'word_count': self._count_words(fallback_summary),
            'needs_review': True,
        }


class PersonalizationEngine:
    """Track user preferences and rank articles by relevance."""
    
    def __init__(self, db_path: str = "rapid100.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS articles (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    summary_100w TEXT,
                    full_summary TEXT,
                    source TEXT,
                    source_url TEXT UNIQUE,
                    image_url TEXT,
                    author TEXT,
                    published_at TEXT,
                    tags TEXT,
                    category TEXT,
                    fetched_at TEXT
                );
                
                CREATE TABLE IF NOT EXISTS user_reads (
                    article_id TEXT,
                    read_at TEXT,
                    dwell_seconds INTEGER DEFAULT 0,
                    PRIMARY KEY (article_id, read_at)
                );
                
                CREATE TABLE IF NOT EXISTS user_preferences (
                    tag TEXT PRIMARY KEY,
                    score REAL DEFAULT 0,
                    last_updated TEXT
                );
                
                CREATE TABLE IF NOT EXISTS clicks (
                    article_id TEXT,
                    clicked_at TEXT,
                    PRIMARY KEY (article_id, clicked_at)
                );
                
                CREATE INDEX IF NOT EXISTS idx_articles_fetched ON articles(fetched_at);
                CREATE INDEX IF NOT EXISTS idx_articles_tags ON articles(tags);
            """)
    
    def save_article(self, article: Article):
        """Save article to database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO articles 
                (id, title, summary_100w, full_summary, source, source_url, image_url,
                 author, published_at, tags, category, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                article.id, article.title, article.summary_100w, article.full_summary,
                article.source, article.source_url, article.image_url, article.author,
                article.published_at, json.dumps(article.tags), article.category,
                article.fetched_at
            ))
    
    def record_read(self, article_id: str, dwell_seconds: int = 0):
        """Record that user read an article."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO user_reads (article_id, read_at, dwell_seconds)
                VALUES (?, datetime('now'), ?)
            """, (article_id, dwell_seconds))
            
            # Update preferences based on article tags
            tags_row = conn.execute(
                "SELECT tags FROM articles WHERE id = ?", (article_id,)
            ).fetchone()
            
            if tags_row:
                tags = json.loads(tags_row[0])
                for tag in tags:
                    conn.execute("""
                        INSERT INTO user_preferences (tag, score, last_updated)
                        VALUES (?, 1, datetime('now'))
                        ON CONFLICT(tag) DO UPDATE SET
                            score = score + 1,
                            last_updated = datetime('now')
                    """, (tag,))
    
    def record_click(self, article_id: str):
        """Record that user clicked 'Read More'."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO clicks (article_id, clicked_at)
                VALUES (?, datetime('now'))
            """, (article_id,))
    
    def get_personalized_feed(self, limit: int = 20) -> List[Article]:
        """Get articles ranked by user preferences."""
        with sqlite3.connect(self.db_path) as conn:
            # Get user preference scores
            prefs = dict(conn.execute(
                "SELECT tag, score FROM user_preferences"
            ).fetchall())
            
            # Get recent articles (last 7 days)
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()
            rows = conn.execute("""
                SELECT * FROM articles 
                WHERE fetched_at > ?
                ORDER BY fetched_at DESC
            """, (week_ago,)).fetchall()
            
            articles = []
            for row in rows:
                tags = json.loads(row[9])  # tags column
                # Calculate relevance score
                score = sum(prefs.get(tag, 0) for tag in tags)
                articles.append((score, row))
            
            # Sort by relevance score (descending)
            articles.sort(key=lambda x: x[0], reverse=True)
            
            # Convert to Article objects
            result = []
            for score, row in articles[:limit]:
                result.append(Article(
                    id=row[0], title=row[1], summary_100w=row[2], full_summary=row[3],
                    source=row[4], source_url=row[5], image_url=row[6], author=row[7],
                    published_at=row[8], tags=json.loads(row[9]), category=row[10],
                    read_time_seconds=len(row[2].split()) * 3,  # ~3 seconds per word
                    fetched_at=row[11]
                ))
            
            return result
    
    def get_stats(self) -> Dict:
        """Get reading statistics."""
        with sqlite3.connect(self.db_path) as conn:
            total_articles = conn.execute(
                "SELECT COUNT(*) FROM articles"
            ).fetchone()[0]
            
            total_reads = conn.execute(
                "SELECT COUNT(*) FROM user_reads"
            ).fetchone()[0]
            
            top_tags = conn.execute("""
                SELECT tag, score FROM user_preferences 
                ORDER BY score DESC LIMIT 10
            """).fetchall()
            
            return {
                'total_articles': total_articles,
                'total_reads': total_reads,
                'top_interests': [{'tag': t, 'score': s} for t, s in top_tags],
            }


class SupabaseWriter:
    """Write articles directly to Supabase cached_articles table."""

    def __init__(self, url: str, anon_key: str):
        self.url = url.rstrip("/")
        self.headers = {
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",
        }

    def is_cached(self, source_url: str) -> bool:
        """Return True if article already cached and not expired."""
        resp = requests.get(
            f"{self.url}/rest/v1/cached_articles",
            headers=self.headers,
            params={
                "select": "source_url",
                "source_url": f"eq.{source_url}",
                "expires_at": f"gt.{datetime.utcnow().isoformat()}",
            },
            timeout=10,
        )
        return resp.ok and len(resp.json()) > 0

    def upsert(self, article: "Article") -> bool:
        """Upsert article into cached_articles. Returns True on success."""
        expires_at = datetime.utcnow().replace(microsecond=0)
        expires_at = expires_at.replace(hour=expires_at.hour)
        from datetime import timedelta
        expires_at = (datetime.utcnow() + timedelta(hours=24)).isoformat()

        payload = {
            "original_id": f"{article.source}-{article.source_url[-60:]}",
            "title": article.title,
            "ai_title": article.title,
            "summary": article.summary_100w,
            "ai_summary": article.summary_100w,
            "source_url": article.source_url,
            "image_url": article.image_url or None,
            "og_image_url": None,
            "category": "Gaming",
            "source": article.source,
            "author": article.author,
            "tags": article.tags,
            "likes": 0,
            "article_date": article.published_at,
            "expires_at": expires_at,
        }

        resp = requests.post(
            f"{self.url}/rest/v1/cached_articles?on_conflict=source_url",
            headers={**self.headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
            json=payload,
            timeout=10,
        )
        if not resp.ok:
            print(f"   ✗ Supabase upsert failed: {resp.status_code} {resp.text[:120]}")
            return False
        return True


class Rapid100Scraper:
    """Main scraper that orchestrates the entire pipeline."""

    def __init__(self, groq_api_key: Optional[str] = None, db_path: str = "rapid100.db",
                 ai_provider: str = "auto", gemini_key: Optional[str] = None,
                 supabase_url: Optional[str] = None, supabase_key: Optional[str] = None):
        self.rss_parser = RSSParser()
        self.article_scraper = ArticleScraper()
        self._groq_api_key = groq_api_key
        self._gemini_key = gemini_key
        self._ai_provider = ai_provider or 'auto'
        self._ai = None  # Lazy initialization
        self.db = PersonalizationEngine(db_path)

        # Optional Supabase writer (write to Pixel Pulse DB)
        _sb_url = supabase_url or os.getenv("SUPABASE_URL")
        _sb_key = supabase_key or os.getenv("SUPABASE_ANON_KEY")
        self.supabase = SupabaseWriter(_sb_url, _sb_key) if (_sb_url and _sb_key) else None
        if self.supabase:
            print("☁️  Supabase writer enabled — articles will sync to Pixel Pulse")
    
    @property
    def ai(self) -> AISummarizer:
        """Lazy initialization of AI summarizer."""
        if self._ai is None:
            self._ai = AISummarizer(self._groq_api_key, provider=self._ai_provider, 
                                   gemini_key=self._gemini_key)
        return self._ai
    
    def generate_id(self, url: str) -> str:
        """Generate unique ID from URL."""
        return hashlib.md5(url.encode()).hexdigest()[:16]
    
    def scrape_feeds(self, max_per_feed: int = 5, article_delay: float = 0) -> List[Article]:
        """Scrape all RSS feeds and process articles.

        Args:
            max_per_feed: Max articles to pull from each RSS feed.
            article_delay: Seconds to sleep between each article's AI call (use ~3s for Groq free tier).
        """
        import time
        print("🚀 Starting Rapid100 scraper...")
        print(f"📡 Fetching from {len(RSS_FEEDS)} RSS feeds\n")
        if article_delay > 0:
            print(f"⏱️  Rate-limit delay: {article_delay}s between articles\n")

        all_items = []
        for feed in RSS_FEEDS:
            print(f"📰 {feed['source']}...")
            xml = self.rss_parser.fetch_feed(feed['url'])
            if xml:
                items = self.rss_parser.parse(xml, feed['source'], max_per_feed)
                print(f"   ✓ Found {len(items)} articles")
                all_items.extend(items)

        print(f"\n📊 Total articles from RSS: {len(all_items)}")

        # Filter out already-cached articles (Supabase dedup)
        if self.supabase:
            fresh = [i for i in all_items if not self.supabase.is_cached(i['link'])]
            skipped = len(all_items) - len(fresh)
            if skipped:
                print(f"⏭️  Skipping {skipped} already-cached articles")
            all_items = fresh

        # Process each article
        articles = []
        for i, item in enumerate(all_items, 1):
            print(f"\n📝 [{i}/{len(all_items)}] {item['title'][:60]}...")

            try:
                article = self._process_item(item)
                if article:
                    articles.append(article)
                    self.db.save_article(article)
                    if self.supabase:
                        ok = self.supabase.upsert(article)
                        print(f"   {'☁️  Synced to Supabase' if ok else '⚠️  Supabase sync failed'} | Tags: {', '.join(article.tags[:3])}")
                    else:
                        print(f"   ✓ Saved | Tags: {', '.join(article.tags[:3])}")
            except Exception as e:
                print(f"   ✗ Error: {e}")

            if article_delay > 0 and i < len(all_items):
                print(f"   💤 Waiting {article_delay}s (rate limit)...")
                time.sleep(article_delay)

        print(f"\n✅ Scraped {len(articles)} articles successfully!")
        return articles
    
    def _process_item(self, item: Dict) -> Optional[Article]:
        """Process a single RSS item into an Article."""
        article_id = self.generate_id(item['link'])
        source = item.get('source', '')
        
        # Clean RSS description
        rss_desc = self._clean_description(item['description'])
        rss_word_count = len(rss_desc.split())
        
        # Decide whether to scrape full article (cap at 600 words)
        # PC Gamer RSS descriptions are often truncated mid-sentence, so always scrape
        force_scrape = source == 'PCGamer' or rss_word_count < 50
        
        if force_scrape:
            reason = "PC Gamer RSS truncated" if source == 'PCGamer' and rss_word_count >= 50 else f"RSS too short ({rss_word_count}w)"
            print(f"   🔍 {reason}, scraping full article...")
            scraped = self.article_scraper.scrape(item['link'], max_words=600)

            # If direct scrape failed or returned too little, try Jina AI Reader
            if not scraped or len(scraped.split()) < 50:
                try:
                    jina_url = f"https://r.jina.ai/{item['link']}"
                    jina_resp = requests.get(
                        jina_url,
                        headers={"Accept": "text/plain", "User-Agent": "Rapid100Bot/1.0"},
                        timeout=20,
                    )
                    if jina_resp.ok and jina_resp.text.strip():
                        jina_text = self.article_scraper._truncate_text(jina_resp.text, max_words=600)
                        if len(jina_text.split()) > (len(scraped.split()) if scraped else 0):
                            print(f"   ✓ Jina fallback: {len(jina_text.split())} words")
                            scraped = jina_text
                except Exception as e:
                    print(f"   ⚠ Jina fallback failed: {e}")

            content = scraped or rss_desc
        else:
            # Truncate RSS description if too long
            content = self.article_scraper._truncate_text(rss_desc, max_words=600)
        
        content_word_count = len(content.split())
        print(f"   📝 Content: {content_word_count} words")
        
        # AI summarization with validation + retry
        ai_result = self.ai.summarize(item['title'], content)
        
        # Parse date
        try:
            pub_date = self._parse_date(item['pub_date'])
        except:
            pub_date = datetime.now().isoformat()
        
        # Build article
        article = Article(
            id=article_id,
            title=ai_result['title'],
            summary_100w=ai_result['summary_100w'],
            full_summary=ai_result['full_summary'],
            source=item['source'],
            source_url=item['link'],
            image_url=item['image_url'],
            author=item['author'],
            published_at=pub_date,
            tags=ai_result['tags'],
            category="Gaming",
            read_time_seconds=len(ai_result['summary_100w'].split()) * 3,
            fetched_at=datetime.now().isoformat(),
        )
        
        # Show validation info
        attempts = ai_result.get('attempts', 1)
        model = ai_result.get('model_used', 'unknown')
        word_count = ai_result.get('word_count', len(ai_result['summary_100w'].split()))
        
        if ai_result.get('needs_review'):
            print(f"   ⚠ Fallback used (needs review)")
        else:
            print(f"   ✓ Summary: {word_count} words | {model} | {attempts} attempt(s)")
        
        return article
    
    def _clean_description(self, html_desc: str) -> str:
        """Clean HTML description."""
        if not html_desc:
            return ""
        
        # Strip HTML
        text = re.sub(r'<[^>]+>', ' ', html_desc)
        text = html.unescape(text)
        
        # Remove common RSS suffixes
        text = re.sub(r'\s*The post .+ appeared first on .+\.?\s*$', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*(Read more|…\s*Source|Continue reading)[^.]*\.?\s*$', '', text, flags=re.IGNORECASE)
        
        # Clean whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Detect truncated descriptions (don't end with proper punctuation)
        # If description doesn't end with . ! ? and has 80+ words, it's likely truncated
        words = text.split()
        if len(words) >= 80 and not text[-1] in '.!?"':
            # Mark as truncated by adding ellipsis - will force full scrape for PC Gamer
            text = text.rstrip() + '...'
        
        return text
    
    def _parse_date(self, date_str: str) -> str:
        """Parse various date formats."""
        formats = [
            '%a, %d %b %Y %H:%M:%S %z',
            '%a, %d %b %Y %H:%M:%S GMT',
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%SZ',
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).isoformat()
            except:
                continue
        return datetime.now().isoformat()
    
    def get_feed(self, personalized: bool = True, limit: int = 20) -> List[Article]:
        """Get news feed - personalized or chronological."""
        if personalized:
            return self.db.get_personalized_feed(limit)
        
        # Get chronological feed
        with sqlite3.connect(self.db.db_path) as conn:
            rows = conn.execute("""
                SELECT * FROM articles ORDER BY fetched_at DESC LIMIT ?
            """, (limit,)).fetchall()
            
            return [Article(
                id=row[0], title=row[1], summary_100w=row[2], full_summary=row[3],
                source=row[4], source_url=row[5], image_url=row[6], author=row[7],
                published_at=row[8], tags=json.loads(row[9]), category=row[10],
                read_time_seconds=len(row[2].split()) * 3, fetched_at=row[11]
            ) for row in rows]
    
    def record_read(self, article_id: str, dwell_seconds: int = 0):
        """Record article read for personalization."""
        self.db.record_read(article_id, dwell_seconds)
    
    def get_stats(self) -> Dict:
        """Get scraper statistics."""
        return self.db.get_stats()


if __name__ == "__main__":
    # Example usage
    import sys
    
    # Check for API key
    if not os.getenv('GROQ_API_KEY'):
        print("❌ Error: GROQ_API_KEY environment variable not set!")
        print("   Get a free key at: https://console.groq.com")
        sys.exit(1)
    
    # Initialize scraper
    scraper = Rapid100Scraper()
    
    # Scrape latest articles
    articles = scraper.scrape_feeds(max_per_feed=3)
    
    # Display results
    print("\n" + "="*60)
    print("📱 YOUR RAPID100 FEED")
    print("   (4-5 sentences ≈ 100 words — Inshorts style)")
    print("="*60)
    
    for art in articles[:5]:
        word_count = len(art.summary_100w.split())
        print(f"\n🏷️  {' | '.join(art.tags[:3])}")
        print(f"📰 {art.title}")
        print(f"🏢 {art.source} • {word_count} words • ⏱️ {art.read_time_seconds}s read")
        print(f"\n   {art.summary_100w}")
        print(f"   [Read more: {art.source_url}]")
        print("-"*60)
    
    # Show stats
    stats = scraper.get_stats()
    print(f"\n📊 Stats: {stats['total_articles']} articles | {stats['total_reads']} reads")
    if stats['top_interests']:
        print(f"🔥 Top interests: {', '.join(t['tag'] for t in stats['top_interests'][:5])}")
