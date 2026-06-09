import httpx

from backend.app.config import settings
from backend.app.services.llm import LLMError, _require_key

GROQ_TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    if settings.llm_provider.lower() == "groq" and settings.groq_api_key:
        api_key = _require_key(
            settings.groq_api_key,
            "GROQ_API_KEY",
            "https://console.groq.com/keys",
        )
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                GROQ_TRANSCRIBE_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                data={"model": "whisper-large-v3"},
                files={"file": (filename, audio_bytes, "audio/webm")},
            )
            resp.raise_for_status()
            return resp.json()["text"].strip()
    raise LLMError("Voice transcription requires LLM_PROVIDER=groq with a valid GROQ_API_KEY.")
