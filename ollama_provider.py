"""
Ollama/Gemma 4 provider for Rapid100 scraper
Add this to your scraper for local AI processing
"""

import requests
import json
from typing import Optional, Dict, Any

class OllamaProvider:
    """Gemma 4 via Ollama for local AI summarization."""
    
    def __init__(self, model: str = "gemma4:e2b", host: str = "http://localhost:11434"):
        self.model = model
        self.host = host
        self.timeout = 120  # 2 min timeout for slow local inference
    
    def is_available(self) -> bool:
        """Check if Ollama is running."""
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=5)
            return resp.status_code == 200
        except:
            return False
    
    def summarize(self, title: str, content: str) -> Optional[Dict[str, Any]]:
        """
        Summarize article using Gemma 4.
        Returns: {"summary": str, "tags": list}
        """
        prompt = f"""You are a gaming news summarizer. Create a 3-sentence summary (55-75 words) of this article.

Title: {title}
Content: {content[:600]}

Respond ONLY with JSON in this format:
{{"summary": "3-sentence summary here", "tags": ["GameName", "CompanyName", "Platform"]}}

Keep sentences tight and informative."""

        try:
            resp = requests.post(
                f"{self.host}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3}
                },
                timeout=self.timeout
            )
            resp.raise_for_status()
            
            result = resp.json()
            text = result.get("response", "")
            
            # Extract JSON from response
            json_match = text.strip()
            if "```json" in text:
                json_match = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                json_match = text.split("```")[1].split("```")[0]
            
            data = json.loads(json_match.strip())
            return {
                "summary": data.get("summary", ""),
                "tags": data.get("tags", [])
            }
            
        except Exception as e:
            print(f"Ollama error: {e}")
            return None


# Usage example:
if __name__ == "__main__":
    provider = OllamaProvider()
    
    if provider.is_available():
        result = provider.summarize(
            "GTA 6 Release Date Announced",
            "Rockstar Games announced GTA 6 will release in Fall 2025..."
        )
        print(result)
    else:
        print("Ollama not running! Start with: ollama serve")
