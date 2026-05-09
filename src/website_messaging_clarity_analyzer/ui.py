from typing import Any, Dict

import streamlit as st

from .llm_analysis import analyze_messaging
from .text_sources import (
    extract_homepage_text,
    find_official_website,
    is_url,
    normalize_input,
    normalize_url,
)

st.set_page_config(
    page_title="Website Messaging Clarity Analyzer",
    page_icon="🧭",
    layout="wide",
)


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


def run_app() -> None:
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
    except Exception as exc:
        st.error(f"Analysis failed: {exc}")
        return

    render_results(analysis, source_url, extracted_text)
