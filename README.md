# Manchester United News Agent

A Streamlit app that gathers recent Manchester United news, groups reports about the same development, and uses Gemini to create a short, sourced briefing.

## Preview

[Watch the app demo](united-agent.mp4)

## How it works

1. Reads BBC Sport, The Guardian, and Sky Sports RSS feeds for articles published in the last three days.
2. Filters for Manchester United stories, removes duplicates, and extracts article text. Inaccessible or short articles are skipped.
3. Creates sentence embeddings and groups similar reports, keeping stories more than 48 hours apart in separate groups.
4. Sends the groups to Gemini to produce up to three evidence-based developments with source links.
5. Shows the results in the Streamlit app.

Article availability depends on each publisher. Gemini access and quotas depend on your API project.

## Requirements

- Python 3.10 or newer
- A Gemini API key

## Setup

Create and activate a virtual environment from the project directory.

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### macOS or Linux

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your Gemini API key:

```text
GEMINI_API_KEY=your_gemini_api_key
```

Keep `.env` private. It is excluded by `.gitignore`.

## Run

```bash
streamlit run app.py
```

Click **Fetch Latest News** to get the latest briefing. The first run may take longer while the sentence embedding model downloads.

To run the news pipeline directly:

```bash
python test_news.py
```

## Project files

- `app.py` - Streamlit interface
- `test_news.py` - news grouping and Gemini pipeline
- `tools/news_search.py` - RSS collection and article extraction
- `requirements.txt` - Python dependencies
- `.env.example` - environment variable template
- `united-agent.mp4` - app demo

The pipeline script is named `test_news.py` for historical reasons; `app.py` launches it.
