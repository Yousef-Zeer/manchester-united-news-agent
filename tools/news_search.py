
import feedparser
import requests
import trafilatura
import re
import html
import calendar

from datetime import datetime, timedelta, timezone


RSS_FEEDS = {
    "BBC Sport": "https://feeds.bbci.co.uk/sport/football/rss.xml",
    "The Guardian": "https://www.theguardian.com/football/rss",
    "Sky Sports": "https://www.skysports.com/rss/11667",
}


def clean_text(text):
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def is_relevant_article(title, summary):

    title_lower = title.lower()
    text = f"{title} {summary}".lower()

    excluded_terms = [
        "manchester united women",
        "man utd women",
        "women's super league",
        "women's team",
        "women team",
        "under-18",
        "under 18",
        "under-21",
        "under 21",
        "u18",
        "u21",
        "academy team",
        "youth team",
        "youth football",
    ]

    if any(term in text for term in excluded_terms):
        return False

    club_terms = [
        "manchester united",
        "man utd",
        "man united",
        "manutd",
        "red devils",
    ]

    return any(term in title_lower for term in club_terms)


def get_published_date(entry):

    published = (
        entry.get("published_parsed")
        or entry.get("updated_parsed")
    )

    if not published:
        return None

    timestamp = calendar.timegm(published)

    return datetime.fromtimestamp(
        timestamp,
        tz=timezone.utc
    )


def extract_article_content(link):

    try:
        downloaded = trafilatura.fetch_url(link)

        if not downloaded:
            return None

        content = trafilatura.extract(downloaded)

        if not content:
            return None

        content = content.strip()
        lower_content = content.lower()

        blocked_terms = [
            "this content is provided by",
            "this content is not available in your location",
            "you need your permission to use cookies",
            "available to uk users only",
        ]

        if len(content) < 500:
            return None

        if any(term in lower_content for term in blocked_terms):
            return None

        return content

    except Exception:
        return None


def search_news(query="Manchester United", days=3):

    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days)

    articles = []
    seen_titles = set()

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    # Collect relevant RSS entries
    for source_name, feed_url in RSS_FEEDS.items():

        print(f"\nFetching: {source_name}")

        try:
            response = requests.get(
                feed_url,
                headers=headers,
                timeout=20
            )

            response.raise_for_status()
            feed = feedparser.parse(response.content)

        except requests.RequestException as error:
            print(f"Could not retrieve {source_name}: {error}")
            continue

        print("Entries received:", len(feed.entries))

        for entry in feed.entries:

            published_date = get_published_date(entry)

            if published_date is None:
                continue

            if published_date < start_date or published_date > now:
                continue

            title = clean_text(entry.get("title", ""))
            summary = clean_text(entry.get("summary", ""))
            link = entry.get("link", "")

            if not title or not link:
                continue

            if not is_relevant_article(title, summary):
                continue

            normalized_title = re.sub(
                r"\s+",
                " ",
                title.lower()
            )

            if normalized_title in seen_titles:
                continue

            seen_titles.add(normalized_title)

            articles.append({
                "title": title,
                "source": source_name,
                "published": published_date.isoformat(),
                "link": link,
                "summary": summary
            })

    articles.sort(
        key=lambda article: article["published"],
        reverse=True
    )

    print("\nTotal relevant articles:", len(articles))

    # Extract article content
    successful_articles = []

    for index, article in enumerate(articles, start=1):

        print(
            f"Extracting {index}/{len(articles)}: "
            f"{article['title']}"
        )

        content = extract_article_content(article["link"])

        if content is None:
            continue

        article["content"] = content
        article["content_length"] = len(content)

        successful_articles.append(article)

    print("\nSuccessful extractions:", len(successful_articles))
    print("Failed or insufficient:", len(articles) - len(successful_articles))

    return successful_articles
