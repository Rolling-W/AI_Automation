# Website Messaging Clarity Analyzer

This Streamlit app takes a company name or website URL, fetches homepage text, and uses a local Ollama model to return structured messaging feedback.

## Why Tavily

The app uses Tavily instead of BeautifulSoup-based scraping because Tavily can resolve official websites and extract clean page text without depending on fragile HTML scraping flows that are often blocked by bot protections, lazy loading, or inconsistent markup.

## Requirements

- Python 3.9+
- A running local Ollama instance
- Tavily API key

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and set your Tavily key:

```bash
TAVILY_API_KEY=your_real_key_here
```

4. Start Ollama and pull the model if needed:

```bash
ollama run llama3
```

That command ensures the model is available locally before the app tries to call it.

## Run the app

```bash
streamlit run streamlit_app.py
```

## Project Structure

- [streamlit_app.py](streamlit_app.py) is the lightweight launcher.
- [src/website_messaging_clarity_analyzer/text_sources.py](src/website_messaging_clarity_analyzer/text_sources.py) handles Tavily lookup and homepage extraction.
- [src/website_messaging_clarity_analyzer/llm_analysis.py](src/website_messaging_clarity_analyzer/llm_analysis.py) handles Ollama prompting and JSON parsing.
- [src/website_messaging_clarity_analyzer/ui.py](src/website_messaging_clarity_analyzer/ui.py) contains the Streamlit layout and app flow.

## How it works

1. Enter a company name or a website URL.
2. If you enter a company name, Tavily searches for the official website URL.
3. Tavily Extract then returns clean text from the homepage.
4. The extracted text is sent to local Ollama with `llama3` and `format='json'`.
5. The app parses the JSON response and displays the summary, score, and suggestions.

## Fallback behavior

If Tavily cannot resolve or extract a page, paste homepage copy into the manual text field and analyze that instead.

## Output format

The model must return valid JSON with these keys:

- `summary`
- `score`
- `suggestions`

## Troubleshooting

- If Tavily fails, confirm `TAVILY_API_KEY` is present in `.env`.
- If Ollama fails, make sure `ollama run llama3` works in a terminal before launching Streamlit.
- If the model returns invalid JSON, rerun the analysis or tighten the system prompt in [src/website_messaging_clarity_analyzer/llm_analysis.py](src/website_messaging_clarity_analyzer/llm_analysis.py).