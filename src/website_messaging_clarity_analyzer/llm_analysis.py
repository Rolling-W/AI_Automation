import json
import re
from typing import Any, Dict, List

import ollama

DEFAULT_MODEL = "llama3.1:8b"


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


def validate_analysis(parsed: Dict[str, Any]) -> Dict[str, Any]:
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
            model=DEFAULT_MODEL,
            messages=messages,
            format="json",
            options={"temperature": 0},
        )

        raw_content = get_response_content(response)
        if not raw_content and hasattr(response, "model_dump"):
            raw_content = get_response_content(response.model_dump())

        try:
            parsed = extract_json_object(raw_content)
            return validate_analysis(parsed)
        except Exception as exc:
            last_error = exc

    raise ValueError(
        f"Ollama returned content that could not be parsed as JSON: {last_error}"
    )
