
import json
import subprocess
import sys
from pathlib import Path

import streamlit as st


# ==================================================
# 1. Page configuration
# ==================================================

PROJECT_DIR = Path(__file__).resolve().parent
PIPELINE_FILE = PROJECT_DIR / "test_news.py"

st.set_page_config(
    page_title="Manchester United News",
    page_icon="⚽",
    layout="wide"
)


# ==================================================
# 2. Page styling
# ==================================================

st.markdown("""
<style>
    .block-container {
        padding-top: 2rem;
        max-width: 1100px;
    }

    .story-card {
        padding: 1.2rem;
        border: 1px solid rgba(128,128,128,0.25);
        border-radius: 12px;
        margin-bottom: 1rem;
    }

    .story-meta {
        color: gray;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)


# ==================================================
# 3. Run the news pipeline
# ==================================================

def run_news_pipeline():

    try:
        result = subprocess.run(
            [sys.executable, "-u", str(PIPELINE_FILE)],
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=420
        )
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or ""
        stderr = error.stderr or ""

        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")

        last_output = (stdout + "\n" + stderr).strip()
        details = f"\n\nLast pipeline output:\n{last_output}" if last_output else ""
        raise RuntimeError(
            "The news pipeline exceeded its 420-second limit. "
            "The partial output below shows which step was running."
            f"{details}"
        ) from error

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr or result.stdout or "Pipeline execution failed."
        )

    output = result.stdout

    marker = "MANCHESTER UNITED - TOP NEWS STORIES"

    if marker not in output:
        raise ValueError("Could not find Gemini report in pipeline output.")

    json_start = output.find("{", output.find(marker))

    if json_start == -1:
        raise ValueError("Could not find JSON report.")

    decoder = json.JSONDecoder()

    report, _ = decoder.raw_decode(output[json_start:])

    if not isinstance(report, dict) or "stories" not in report:
        raise ValueError("Invalid report structure.")

    return report


# ==================================================
# 4. Header
# ==================================================

st.title("⚽ Manchester United News")

st.caption(
    "AI-powered football news monitoring | "
    "Official and reputable sports sources"
)

st.divider()


# ==================================================
# 5. Fetch news button
# ==================================================

if "report" not in st.session_state:
    st.session_state.report = None

if st.button("🔄 Fetch Latest News", type="primary"):

    try:
        with st.spinner(
            "Fetching articles, extracting content and analyzing stories..."
        ):
            st.session_state.report = run_news_pipeline()

        st.success("News analysis completed successfully!")

    except Exception as error:
        st.error(f"Something went wrong: {error}")


# ==================================================
# 6. Display news stories
# ==================================================

report = st.session_state.report

if report:

    stories = report.get("stories", [])

    st.subheader("Top Manchester United Stories")

    st.caption(f"{len(stories)} important developments identified")

    if not stories:
        st.info("No important stories were identified.")
    
    for story in stories:

        rank = story.get("rank", "")
        title = story.get("title", "Untitled story")
        summary = story.get("summary", "")
        importance = story.get("importance_score", "N/A")
        status = story.get("status", "Unknown")
        why_it_matters = story.get("why_it_matters", "")

        with st.container(border=True):

            st.markdown(f"### {rank}. {title}")

            col1, col2 = st.columns(2)

            with col1:
                st.markdown(
                    f"**Status:** {status}"
                )

            with col2:
                st.markdown(
                    f"**Importance:** {importance}/5"
                )

            st.markdown(summary)

            if why_it_matters:
                st.markdown("**Why it matters**")
                st.write(why_it_matters)

            with st.expander("Evidence and sources"):

                evidence = story.get("evidence", [])

                if evidence:
                    st.markdown("**Supporting evidence**")

                    for item in evidence:
                        st.markdown(
                            f"- {item.get('claim', '')}"
                        )
                        st.caption(
                            f"Source: {item.get('source_title', 'Unknown')}"
                        )

                sources = story.get("sources", [])

                if sources:
                    st.markdown("**Original articles**")

                    for source in sources:

                        article_title = source.get(
                            "article_title", "Read article"
                        )

                        publisher = source.get(
                            "publisher", "Unknown publisher"
                        )

                        url = source.get("url", "")

                        if url:
                            st.markdown(
                                f"- [{article_title}]({url}) "
                                f"— {publisher}"
                            )
                        else:
                            st.write(
                                f"- {article_title} — {publisher}"
                            )

else:

    st.info(
        "Click **Fetch Latest News** to discover and analyze "
        "the latest Manchester United stories."
    )


# ==================================================
# 7. Footer
# ==================================================

st.divider()


