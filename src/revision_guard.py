"""Small deterministic guard for handbook revision-history answers."""
import json
import re
from pathlib import Path


def enforce_revision_authority(question, answer, source_path):
    if not re.search(r"revision|revised|latest revision|how many times.*handbook", question, re.I):
        return answer
    # Historical lookups ("when was Revision 6?") are legitimately not about the latest.
    if re.search(r"revisions?\s*\d+", question, re.I):
        return answer
    source = Path(source_path)
    if not source.exists():
        return answer
    data = json.loads(source.read_text(encoding="utf-8"))
    latest = data["latest_revision"]
    correct_count = re.search(rf"\b{data['total_revisions']}\b", answer) is not None
    correct_revision = re.search(rf"\brevision\s*{latest['revision']}\b", answer, re.I) is not None
    correct_date = latest["date"].casefold() in answer.casefold()
    if correct_count and correct_revision and correct_date:
        return answer
    return f"The Employee Handbook has {data['total_revisions']} revisions. The latest is Revision {latest['revision']}, dated {latest['date']}."
