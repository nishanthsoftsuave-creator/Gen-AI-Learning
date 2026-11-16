"""Redact secrets and personal data from text before it is logged or sent to a model.

Employees paste API keys, connection strings and personal details into HR questions, so this
runs on write (trace files, MCP audit log) and on the question before any LLM call.
`python src/redact.py` runs the self-check.
"""
import re

KEEP_EMAILS = {"teamhr@softsuave.com"}  # the handbook's published HR contact, not personal data

_RULES = [
    ("connection_string", re.compile(r"\b[a-z][a-z0-9+.\-]*://[^\s/:@]+:[^\s/@]+@[^\s]+", re.I)),
    ("api_key", re.compile(r"\b(?:sk|gsk|pk|rk)[_\-][A-Za-z0-9_\-]{16,}\b|\bAKIA[0-9A-Z]{16}\b|\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("bearer_token", re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{16,}", re.I)),
    ("secret_assignment", re.compile(r"\b(?:password|passwd|pwd|secret|token|api[_\-]?key)\s*[=:]\s*\S+", re.I)),
    ("aadhaar", re.compile(r"\b\d{4}\s\d{4}\s\d{4}\b")),
    ("pan", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    ("phone", re.compile(r"(?<![\d.])(?:\+?\d{1,3}[\s\-]?)?\d{10}(?![\d.])")),
]
_EMAIL = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")


def redact(text):
    if not isinstance(text, str):
        return text
    for label, pattern in _RULES:
        text = pattern.sub(f"[REDACTED:{label}]", text)
    return _EMAIL.sub(lambda m: m.group(0) if m.group(0).lower() in KEEP_EMAILS else "[REDACTED:email]", text)


def redact_obj(value):
    """Redact every string inside nested dicts/lists (for whole trace records)."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {k: redact_obj(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_obj(v) for v in value]
    return value


if __name__ == "__main__":
    cases = {
        "my key is gsk_abcdEFGH1234567890abcdEFGH": "api_key",
        "AKIAIOSFODNN7EXAMPLE leaked": "api_key",
        "use postgres://hr_admin:S3cret!@db.internal:5432/hr": "connection_string",
        "password=hunter2 please": "secret_assignment",
        "Authorization: Bearer abcdefghijklmnop1234": "bearer_token",
        "call me on 9876543210": "phone",
        "my PAN is ABCDE1234F": "pan",
        "aadhaar 1234 5678 9012": "aadhaar",
        "mail ravi.kumar@gmail.com": "email",
    }
    for text, label in cases.items():
        out = redact(text)
        assert f"[REDACTED:{label}]" in out, (text, out)
    keep = "Reach HR at teamhr@softsuave.com or 1000 INR per day, 500 INR, Revision 11 June 2025."
    assert redact(keep) == keep, redact(keep)  # contact email, short numbers and dates survive
    assert redact_obj({"a": ["x gsk_abcdEFGH1234567890abcdEFGH"], "n": 3})["a"][0] == "x [REDACTED:api_key]"
    print("redact self-check OK")
