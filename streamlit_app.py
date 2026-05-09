import json
import os
import re
from typing import Any, Dict, List

import ollama
import streamlit as st
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()


st.set_page_config(
    page_title="Website Messaging Clarity Analyzer",
    page_icon="🧭",
    layout="wide",
)


def normalize_input(value: str) -> str:
    return value.strip()


def is_url(value: str) -> bool:
    lowered = value.lower()
    return lowered.startswith(("http://", "https://", "www."))


def normalize_url(value: str) -> str:
    stripped = value.strip()
    lowered = stripped.lower()
    if lowered.startswith("http://") or lowered.startswith("https://"):
        return stripped
    if lowered.startswith("www."):
        return f"https://{stripped}"
    if " " not in stripped and "." in stripped:
        return f"https://{stripped}"
    return stripped


def get_tavily_client() -> TavilyClient:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEY is missing from the environment.")
    return TavilyClient(api_key=api_key)


def find_official_website(company_name: str) -> str:
    client = get_tavily_client()
    response = client.search(
        query=f"official website for {company_name}",
        max_results=5,
        search_depth="advanced",
        include_answer=False,
    )

    results = response.get("results", []) if isinstance(response, dict) else []
    for result in results:
        url = result.get("url") if isinstance(result, dict) else None
        if url:
            return url

    raise RuntimeError("Tavily could not find an official website URL.")


def extract_homepage_text(url: str) -> str:
    client = get_tavily_client()
    response = None
    extract_attempts = (
        lambda: client.extract(url),
        lambda: client.extract(urls=[url]),
    )

    last_error: Exception | None = None
    for attempt in extract_attempts:
        try:
            response = attempt()
            break
        except TypeError as exc:
            last_error = exc

    if response is None:
        raise RuntimeError(
            f"Tavily extract could not be called successfully: {last_error}"
        )

    results = response.get("results", []) if isinstance(response, dict) else []
    if not results:
        raise RuntimeError("Tavily did not return any extracted text.")

    extracted_sections: List[str] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        content = (
            result.get("raw_content") or result.get("content") or result.get("text")
        )
        if content:
            extracted_sections.append(str(content).strip())

    combined_text = "\n\n".join(section for section in extracted_sections if section)
    if not combined_text:
        raise RuntimeError("Tavily extract completed, but no usable text was returned.")

    return combined_text


def build_analysis_prompt(text: str) -> List[Dict[str, str]]:
    system_prompt = (
        "You are a senior conversion copywriter and brand strategist. "
        "Return ONLY a valid JSON object and nothing else. "
        "No markdown, no code fences, no commentary, no leading or trailing text. "
        "The JSON object must contain exactly these keys: summary, score, suggestions. "
        "summary must be a 1-2 sentence string explaining what the business does. "
        "score must be an integer from 1 to 10 rating how clearly the site communicates its value. "
        "suggestions must be an array of 2-3 specific, actionable strings for improving clarity. "
        "Use double quotes for all JSON strings."
    )
    user_prompt = "Website text to analyze:\n\n" + text[:12000]
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def extract_json_object(raw_content: str) -> Dict[str, Any]:
    try:
        return json.loads(raw_content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_content, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def get_response_content(response: Any) -> str:
    if isinstance(response, dict):
        message = response.get("message")
        if isinstance(message, dict):
            return str(message.get("content") or "")
        if message is not None:
            return str(getattr(message, "content", "") or "")

    message = getattr(response, "message", None)
    if message is not None:
        content = getattr(message, "content", None)
        if content is not None:
            return str(content)

    content = getattr(response, "content", None)
    if content is not None:
        return str(content)

    return ""


def analyze_messaging(text: str) -> Dict[str, Any]:
    base_messages = build_analysis_prompt(text)
    last_error: Exception | None = None

    for attempt in range(2):
        messages = base_messages
        if attempt == 1:
            messages = [
                base_messages[0],
                {
                    "role": "user",
                    "content": (
                        "Your previous response was not valid JSON. "
                        "Return only the JSON object with exactly the required keys. "
                        "Do not wrap it in markdown or add any extra text."
                    ),
                },
                base_messages[1],
            ]

        response = ollama.chat(
            model="llama3.1:8b",
            messages=messages,
            format="json",
            options={"temperature": 0},
        )

        raw_content = get_response_content(response)
        if not raw_content and hasattr(response, "model_dump"):
            dumped = response.model_dump()
            raw_content = get_response_content(dumped)

        try:
            parsed = extract_json_object(raw_content)
            break
        except Exception as exc:
            last_error = exc
            parsed = None

    if parsed is None:
        raise ValueError(
            f"Ollama returned content that could not be parsed as JSON: {last_error}"
        )

    summary = parsed.get("summary")
    score = parsed.get("score")
    suggestions = parsed.get("suggestions")

    if not isinstance(summary, str):
        raise ValueError("The LLM response is missing a valid 'summary' string.")
    if not isinstance(score, int):
        raise ValueError("The LLM response is missing a valid 'score' integer.")
    if not isinstance(suggestions, list) or not all(
        isinstance(item, str) for item in suggestions
    ):
        raise ValueError(
            "The LLM response is missing a valid 'suggestions' array of strings."
        )

    return {"summary": summary, "score": score, "suggestions": suggestions}


def render_results(
    analysis: Dict[str, Any], source_url: str, extracted_text: str
) -> None:
    st.success("Analysis complete")
    if source_url.lower().startswith(("http://", "https://")):
        st.markdown(f"**Website analyzed:** [{source_url}]({source_url})")
    else:
        st.markdown(f"**Text source:** {source_url}")

    metric_col_1, metric_col_2 = st.columns(2)
    with metric_col_1:
        st.metric("Clarity Score", analysis["score"], help="A score from 1 to 10")
    with metric_col_2:
        st.metric("Source text length", f"{len(extracted_text):,} chars")

    st.subheader("Summary")
    st.write(analysis["summary"])

    st.subheader("Suggestions")
    for suggestion in analysis["suggestions"]:
        st.markdown(f"- {suggestion}")

    with st.expander("View extracted homepage text"):
        st.text_area("Extracted text", value=extracted_text, height=320)


def main() -> None:
    st.title("Website Messaging Clarity Analyzer")
    st.write(
        "Enter a company name or website URL, extract the homepage messaging, and get structured clarity feedback."
    )

    with st.form("analysis_form"):
        input_value = st.text_input(
            "Company name or website URL", placeholder="Acme Inc or https://example.com"
        )
        manual_text = st.text_area(
            "Manual text fallback",
            placeholder="Paste homepage text here if API fetching fails or you want to analyze custom copy.",
            height=180,
        )
        submitted = st.form_submit_button("Analyze messaging")

    if not submitted:
        return

    normalized_input = normalize_input(input_value)
    if not normalized_input and not manual_text.strip():
        st.error("Provide a company name, website URL, or manual text fallback.")
        return

    source_url = ""
    extracted_text = ""

    if normalized_input:
        try:
            with st.spinner("Resolving website source..."):
                source_url = (
                    normalize_url(normalized_input)
                    if is_url(normalized_input)
                    else find_official_website(normalized_input)
                )
        except Exception as exc:
            st.error(f"Could not resolve a website URL: {exc}")
            if not manual_text.strip():
                return

    if source_url:
        try:
            with st.spinner("Extracting clean homepage text with Tavily..."):
                extracted_text = extract_homepage_text(source_url)
        except Exception as exc:
            st.warning(f"Website extraction failed: {exc}")

    if not extracted_text and manual_text.strip():
        extracted_text = manual_text.strip()
        if not source_url:
            source_url = "Manual text input"

    if not extracted_text:
        st.error("No text was available to analyze. Try the manual text fallback.")
        return

    try:
        with st.spinner("Running local Ollama analysis..."):
            analysis = analyze_messaging(extracted_text)
    except json.JSONDecodeError:
        st.error("The model returned invalid JSON. Try again or tighten the prompt.")
        return
    except Exception as exc:
        st.error(f"Analysis failed: {exc}")
        return

    render_results(analysis, source_url, extracted_text)


if __name__ == "__main__":
    main()
