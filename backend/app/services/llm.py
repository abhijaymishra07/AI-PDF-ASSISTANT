import json
import os
import re
import time

import httpx

from backend.app.config import settings

SYSTEM_PROMPT = """You are a helpful assistant that answers questions using the provided context from PDF documents.
When you use information from the context, cite the source as (doc_id, page N).

For mathematical questions:
- Use formulas, definitions, and worked examples from the context as your starting point.
- Solve step by step. Show every step clearly.
- Write equations on separate lines. Use standard notation (e.g. x^2, integral, sum).
- If the PDF gives a similar example, follow the same method.
- If numbers in the context are incomplete, state what you can derive and what is missing."""

MATH_SYSTEM_PROMPT = """You are an expert math tutor helping a student with questions about their PDF notes.

Rules:
1. Use formulas, theorems, and examples from the provided PDF context.
2. Solve the problem step by step — show ALL working, never skip steps.
3. Label each step (Step 1, Step 2, …).
4. Write equations clearly, one per line where helpful.
5. Give the final answer boxed or marked clearly at the end.
6. Cite the PDF page when you use a formula from context: (doc_id, page N).
7. If the question asks to solve something not fully in the context, use the context method on the given problem.
8. Double-check arithmetic in your final step."""

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class LLMError(Exception):
    pass


def _env(key: str, fallback: str = "") -> str:
    """Prefer os.environ (Streamlit secrets) over cached Settings."""
    return os.environ.get(key, fallback) or getattr(settings, key.lower(), fallback)


def _groq_api_key() -> str:
    return _env("GROQ_API_KEY", settings.groq_api_key)


def _gemini_api_key() -> str:
    return _env("GEMINI_API_KEY", settings.gemini_api_key)


def _llm_provider() -> str:
    return _env("LLM_PROVIDER", settings.llm_provider).lower().strip()


def _require_key(value: str, name: str, signup_url: str) -> str:
    if not value or value.startswith("your-"):
        raise LLMError(
            f"Missing {name}. Get a free key at {signup_url} and add it to your .env file."
        )
    return value


def _gemini_complete(system: str, user: str, temperature: float) -> str:
    api_key = _require_key(
        _gemini_api_key(),
        "GEMINI_API_KEY",
        "https://aistudio.google.com/apikey",
    )
    url = GEMINI_URL.format(model=settings.gemini_model)
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"temperature": temperature},
    }
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, params={"key": api_key}, json=payload)
        if resp.status_code == 429:
            raise LLMError("Gemini rate limit hit. Wait a minute or switch LLM_PROVIDER=groq in .env")
        resp.raise_for_status()
        data = resp.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError) as e:
        raise LLMError(f"Unexpected Gemini response: {data}") from e


def _groq_complete(system: str, user: str, temperature: float, model: str | None = None) -> str:
    api_key = _require_key(
        _groq_api_key(),
        "GROQ_API_KEY",
        "https://console.groq.com/keys",
    )
    payload = {
        "model": model or settings.groq_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    last_error: Exception | None = None

    with httpx.Client(timeout=90.0) as client:
        for attempt in range(3):
            resp = client.post(GROQ_URL, json=payload, headers=headers)
            if resp.status_code == 429:
                last_error = LLMError(
                    "Groq rate limit reached. Wait 30–60 seconds and try again, "
                    "or reduce the number of questions."
                )
                if attempt < 2:
                    time.sleep(2 ** attempt * 5)
                    continue
                raise last_error
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise LLMError(f"Groq API error ({resp.status_code}): {resp.text[:200]}") from e
            data = resp.json()
            try:
                return data["choices"][0]["message"]["content"].strip()
            except (KeyError, IndexError) as e:
                raise LLMError(
                    f"Unexpected Groq response (model may have refused or context too large): {data}"
                ) from e

    raise last_error or LLMError("Groq request failed.")


def _ollama_complete(system: str, user: str, temperature: float) -> str:
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
    }
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    base = settings.llm_base_url.rstrip("/")
    with httpx.Client(timeout=300.0) as client:
        resp = client.post(f"{base}/chat/completions", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def complete(
    system: str,
    user: str,
    temperature: float = 0.2,
    model: str | None = None,
) -> str:
    provider = _llm_provider()
    if provider == "gemini":
        return _gemini_complete(system, user, temperature)
    if provider == "groq":
        return _groq_complete(system, user, temperature, model=model)
    if provider == "ollama":
        return _ollama_complete(system, user, temperature)
    raise LLMError(f"Unknown LLM_PROVIDER '{provider}'. Use gemini, groq, or ollama.")


def complete_json(system: str, user: str, temperature: float = 0.2) -> dict | list:
    prompt = user + "\n\nRespond with valid JSON only. No markdown fences."
    raw = complete(system, prompt, temperature)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    return json.loads(raw)
