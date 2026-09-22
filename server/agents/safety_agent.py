"""
Safety Agent — instant keyword-based check.
No API calls, no network round-trip → zero latency.
"""

# Phrases that should be blocked immediately
_BLOCKED_PATTERNS = [
    "how to make bomb", "how to kill", "suicide method", "self harm",
    "child porn", "cp ", "rape", "sexual abuse", "drug synthesis",
    "how to hack", "exploit code", "malware", "ransomware",
    "shoot people", "murder someone",
]


def safety_agent(user_message: str) -> bool:
    """
    Returns True if the message is safe, False if it should be blocked.
    Uses instant keyword matching — no network call required.
    """
    text = user_message.lower().strip()
    for pattern in _BLOCKED_PATTERNS:
        if pattern in text:
            print(f"[Safety Agent] BLOCKED — matched pattern: '{pattern}'")
            return False
    print(f"[Safety Agent] PASS (keyword check) — '{user_message[:60]}'")
    return True