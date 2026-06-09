import json

import feedparser
import requests
from textblob import TextBlob

from app.config import NEWS_API_KEY, OPENAI_API_KEY, OPENAI_NEWS_MAX_ARTICLES, OPENAI_NEWS_MODEL

class NewsAgent:

    def __init__(self):
        self._openai_client = None
        self._openai_disabled = False

    def _get_openai_client(self):
        if self._openai_client is not None:
            return self._openai_client

        if OPENAI_API_KEY and OPENAI_API_KEY != "your_openai_api_key_here":
            try:
                from openai import OpenAI

                self._openai_client = OpenAI(api_key=OPENAI_API_KEY)
            except Exception:
                self._openai_client = None

        return self._openai_client

    def _extract_textblob_sentiment(self, articles):
        sentiments = []

        for article in articles:
            title = article.get('title', '')

            if not title:
                continue

            polarity = TextBlob(title).sentiment.polarity
            sentiments.append(polarity)

        if len(sentiments) == 0:
            return 0.0

        return sum(sentiments) / len(sentiments)

    def _openai_sentiment(self, articles):
        if self._openai_disabled:
            return None

        client = self._get_openai_client()
        if client is None:
            return None

        snippets = []
        for article in articles[:OPENAI_NEWS_MAX_ARTICLES]:
            title = article.get('title', '').strip()
            description = article.get('description', '').strip()
            if title:
                snippets.append(f"- {title}{': ' + description if description else ''}")

        if not snippets:
            return None

        prompt = (
            "You are scoring short-term market news sentiment for gold and macro assets. "
            "Return only compact JSON with keys sentiment and confidence. "
            "sentiment must be a number between -1 and 1 where -1 is strongly bearish, 1 is strongly bullish, and 0 is neutral. "
            "confidence must be a number between 0 and 1. "
            "Use the headlines only and be conservative.\n\n"
            + "News items:\n"
            + "\n".join(snippets)
        )

        try:
            response = client.chat.completions.create(
                model=OPENAI_NEWS_MODEL,
                messages=[
                    {"role": "system", "content": "You are a precise financial news sentiment classifier."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_tokens=120,
            )
        except Exception:
            self._openai_disabled = True
            return None

        content = response.choices[0].message.content or ""
        content = content.strip().strip("`")

        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start == -1 or end == -1 or end <= start:
                return None
            payload = json.loads(content[start:end + 1])

        score = float(payload.get('sentiment', 0.0))
        return max(-1.0, min(1.0, score))

    def fetch_news(self, query="gold OR bitcoin OR federal reserve"):

        if NEWS_API_KEY and NEWS_API_KEY != "your_news_api_key_here":
            try:
                response = requests.get(
                    "https://newsapi.org/v2/everything",
                    params={
                        "q": query,
                        "language": "en",
                        "sortBy": "publishedAt",
                        "pageSize": 20,
                        "apiKey": NEWS_API_KEY,
                    },
                    timeout=10,
                )
                response.raise_for_status()
                data = response.json()

                articles = data.get('articles', [])
                if articles:
                    return articles
            except requests.RequestException:
                pass

        feed_url = (
            "https://news.google.com/rss/search?"
            f"q={query.replace(' ', '+')}"
            "&hl=en-US&gl=US&ceid=US:en"
        )
        feed = feedparser.parse(feed_url)

        articles = []
        for entry in feed.entries[:10]:
            articles.append({
                'title': entry.get('title', ''),
                'description': entry.get('summary', ''),
                'source': {
                    'name': 'Google News RSS'
                }
            })

        return articles

    def analyze_sentiment(self, articles):
        textblob_sentiment = self._extract_textblob_sentiment(articles)
        openai_sentiment = self._openai_sentiment(articles)

        if openai_sentiment is None:
            return textblob_sentiment

        # Blend the model-backed sentiment with lexical sentiment so the OpenAI score is primary.
        return round((0.7 * openai_sentiment) + (0.3 * textblob_sentiment), 4)