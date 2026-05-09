import os
from typing import Any, List

from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()


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


def get_response_items(response: Any) -> List[Any]:
    if isinstance(response, dict):
        items = response.get("results", [])
    else:
        items = getattr(response, "results", [])

    return list(items) if items else []


def get_item_value(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def find_official_website(company_name: str) -> str:
    client = get_tavily_client()
    response = client.search(
        query=f"official website for {company_name}",
        max_results=5,
        search_depth="advanced",
        include_answer=False,
    )

    for result in get_response_items(response):
        url = get_item_value(result, "url")
        if url:
            return str(url)

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

    results = get_response_items(response)
    if not results:
        raise RuntimeError("Tavily did not return any extracted text.")

    extracted_sections: List[str] = []
    for result in results:
        content = (
            get_item_value(result, "raw_content")
            or get_item_value(result, "content")
            or get_item_value(result, "text")
        )
        if content:
            extracted_sections.append(str(content).strip())

    combined_text = "\n\n".join(section for section in extracted_sections if section)
    if not combined_text:
        raise RuntimeError("Tavily extract completed, but no usable text was returned.")

    return combined_text
