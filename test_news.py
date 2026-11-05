import os
import json
import time

from google import genai
from google.genai import types
from tools.news_search import search_news

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import AgglomerativeClustering

from dateutil import parser

from dotenv import load_dotenv

load_dotenv()

# ==================================================
# 1. Fetch news articles
# ==================================================

print("\nFetching Manchester United news...\n")

articles = search_news(days=3)

if len(articles) < 2:
    raise SystemExit("Not enough articles found to perform clustering.")

print(f"\nArticles available for analysis: {len(articles)}")


# ==================================================
# 2. Prepare articles for semantic similarity
# ==================================================

documents = [
    f"{article['title']}. {article['content'][:3000]}"
    for article in articles
]


# ==================================================
# 3. Generate embeddings
# ==================================================

print("\nLoading embedding model...")

model = SentenceTransformer(
    "all-MiniLM-L6-v2",
    device="cpu"
)

print("\nGenerating embeddings...")

embeddings = model.encode(
    documents,
    normalize_embeddings=True,
    show_progress_bar=True
)


# ==================================================
# 4. Calculate similarity and apply time constraint
# ==================================================

similarity_matrix = cosine_similarity(embeddings)

distance_matrix = 1 - similarity_matrix

MAX_TIME_GAP_HOURS = 48

for i in range(len(articles)):
    for j in range(i + 1, len(articles)):

        date_i = parser.parse(articles[i]["published"])
        date_j = parser.parse(articles[j]["published"])

        time_gap = abs(
            (date_i - date_j).total_seconds()
        ) / 3600

        if time_gap > MAX_TIME_GAP_HOURS:
            distance_matrix[i, j] = 1.0
            distance_matrix[j, i] = 1.0


# ==================================================
# 5. Cluster similar articles into stories
# ==================================================

SIMILARITY_THRESHOLD = 0.75

clustering_model = AgglomerativeClustering(
    n_clusters=None,
    metric="precomputed",
    linkage="average",
    distance_threshold=1 - SIMILARITY_THRESHOLD
)

cluster_labels = clustering_model.fit_predict(distance_matrix)


story_groups = {}

for article_index, cluster_label in enumerate(cluster_labels):

    if cluster_label not in story_groups:
        story_groups[cluster_label] = []

    story_groups[cluster_label].append(
        articles[article_index]
    )


# Sort groups by number of articles, largest first

sorted_groups = sorted(
    story_groups.values(),
    key=len,
    reverse=True
)

print(f"\nNumber of distinct story groups: {len(sorted_groups)}")

for number, group in enumerate(sorted_groups, start=1):

    print(f"\nStory Group {number} ({len(group)} articles)")

    for article in group:
        print(f"- {article['title']}")


# ==================================================
# 6. Prepare grouped articles for Gemini
# ==================================================

stories_for_ai = []

for number, group in enumerate(sorted_groups, start=1):

    story_articles = []

    for article in group:

        story_articles.append({
            "title": article["title"],
            "source": article.get("source", "Unknown"),
            "published": article["published"],
            "url": article.get("link", article.get("url", "")),
            "content": article["content"][:2500]
        })

    stories_for_ai.append({
        "group_id": number,
        "articles": story_articles
    })


# ==================================================
# 7. Build Gemini prompt
# ==================================================

prompt = f"""
You are a Manchester United first-team football news analyst.

Your task is to identify up to THREE of the most important DISTINCT
news developments from the articles provided below.

STRICT EDITORIAL AND EVIDENCE RULES:

1. Use ONLY information explicitly stated in the provided articles.
   Do not use outside knowledge or assumptions.

2. Every factual claim in a story's summary must be supported by
   at least one specific article.

3. For EVERY claim in the evidence list:
   - Identify the exact article that supports it.
   - Use that article's exact title as source_title.
   - Do not cite an article just because it belongs to the same group.
   - The article must explicitly contain the information in the claim.

4. Do not add details from memory, general football knowledge,
   or assumptions.

5. ONE STORY MUST REPRESENT ONE DISTINCT NEWS DEVELOPMENT.

6. Do NOT combine separate transfer rumours into one story.
   For example:
   - Interest in Ivan Toney is one development.
   - Interest in another player is a separate development.
   - Do not combine them just because both concern transfers.

7. An article may mention several unrelated developments.
   Treat each development separately when appropriate.

8. Multiple articles may be grouped into one story ONLY when
   they report on the same underlying development.

9. Do not confuse:
   - Confirmed events with speculation.
   - A club enquiry with an official transfer bid.
   - Reported interest with an agreement.
   - A journalist's opinion with a factual development.

10. If an article does not provide enough evidence for a claim,
    exclude that claim.

11. Do not invent dates, quotes, names, sources, or URLs.

12. Copy article titles, publishers, and URLs exactly as provided.

13. Rank stories by sporting impact, managerial implications,
    injuries, transfers, and important club decisions.
    Do not rank by article count alone.

14. If fewer than three distinct developments are sufficiently
    important and supported, return fewer than three.

15. Include only Manchester United men's first-team news.
    Exclude women's team and academy news.

OUTPUT REQUIREMENTS:

Return ONLY valid JSON. No Markdown or additional text.

Use exactly this structure:

{{
  "stories": [
    {{
      "rank": 1,
      "title": "Short title describing ONE distinct development",
      "summary": "A factual summary supported by the evidence below.",
      "why_it_matters": "Explain the significance without adding
      unsupported factual claims.",
      "importance_score": 5,
      "status": "Reported",
      "evidence": [
        {{
          "claim": "One specific factual claim.",
          "source_title": "Exact article title supporting this claim."
        }}
      ],
      "sources": [
        {{
          "article_title": "Exact article title.",
          "publisher": "Publisher name.",
          "url": "Exact article URL."
        }}
      ]
    }}
  ]
}}

STATUS RULES:
- Confirmed: The development is officially confirmed or directly
  established by the provided reporting.
- Reported: A reputable source reports the development, but it is
  not officially confirmed.
- Rumour: The information is speculative or comes from transfer gossip.

IMPORTANCE SCORE:
Use an integer from 1 to 5.

IMPORTANT FINAL CHECK BEFORE RETURNING JSON:

For every story:
- Does every factual claim have a supporting article?
- Does that article actually support the claim?
- Have unrelated developments been kept separate?
- Are the source titles and URLs copied from the input?
- Is the story genuinely important enough to appear in the top three?

Remove any claim or story that fails these checks.

ARTICLES:

{json.dumps(stories_for_ai, ensure_ascii=False, indent=2)}
"""

# ==================================================
# 8. Send prompt to Gemini
# ==================================================

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GEMINI_API_KEY is missing.")

client = genai.Client(
    api_key=api_key,
    http_options=types.HttpOptions(
        timeout=60_000,
        retry_options=types.HttpRetryOptions(attempts=1)
    )
)

print("\nSending articles to Gemini...\n")

GEMINI_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
]

response = None
model_errors = []

for model_index, model_name in enumerate(GEMINI_MODELS):
    try:
        print(f"Trying Gemini model: {model_name}", flush=True)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        break
    except Exception as error:
        error_text = str(error).lower()
        model_errors.append(f"{model_name}: {error}")

        daily_quota_exhausted = (
            "per day limit exceeded" in error_text
            or "requests_per_day" in error_text
        )

        transient = any(term in error_text for term in (
            "503", "504", "service_unavailable", "deadline_exceeded",
            "high demand",
            "rate_limit_exceeded", "too_many_requests",
            "temporarily unavailable"
        ))

        can_fallback = daily_quota_exhausted or transient

        if not can_fallback:
            raise RuntimeError(
                f"Gemini request failed on {model_name}. Original error: {error}"
            ) from error

        if model_index < len(GEMINI_MODELS) - 1:
            next_model = GEMINI_MODELS[model_index + 1]
            reason = "daily quota exhausted" if daily_quota_exhausted else "temporary service/deadline error"
            print(
                f"{model_name} failed ({reason}); falling back to {next_model}.",
                flush=True
            )

if response is None:
    raise RuntimeError(
        "All configured Gemini models failed. " + " | ".join(model_errors)
    )


# ==================================================
# 9. Parse and display Gemini JSON response
# ==================================================

raw_output = response.text.strip()

# Remove Markdown code fences if Gemini includes them

if raw_output.startswith("```"):

    raw_output = raw_output.split("\n", 1)[1]

    raw_output = raw_output.rsplit("```", 1)[0].strip()


try:

    report = json.loads(raw_output)

    if not isinstance(report, dict) or "stories" not in report:
        raise ValueError("Unexpected JSON structure.")

    print("\n" + "=" * 60)
    print("MANCHESTER UNITED - TOP NEWS STORIES")
    print("=" * 60)

    print(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2
        )
    )

except (json.JSONDecodeError, ValueError) as error:

    print("\nGemini returned an invalid response.")

    print("Error:", error)

    print("\nRaw response:")
    print(response.output_text)
