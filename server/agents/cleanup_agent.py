"""
Cleanup Agent — instant regex-based text cleanup.
No API calls, no network round-trip → zero latency.
"""
from tts import clean_text


def cleanup_agent(raw_response: str) -> str:
    """
    Cleans up the LLM response for TTS using regex only.
    No network call required → instant.
    """
    cleaned = clean_text(raw_response)
    print(f"[Cleanup Agent] Cleaned (regex): {cleaned[:80]}")
    return cleaned