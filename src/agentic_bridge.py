"""Bridge from the FastAPI app to the Week 7 Task Set E code in
`Agentic Ai/` (a sibling folder, not a Python package -- its name has a
space, so it can't be dotted-imported). Adding its directory to sys.path
lets its own internal top-level imports (`from budgets import ...` etc.)
resolve exactly as they do when those scripts are run directly.
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
AGENTIC_DIR = BASE_DIR / "Agentic Ai"

if str(AGENTIC_DIR) not in sys.path:
    sys.path.insert(0, str(AGENTIC_DIR))

from agent import run_agent  # noqa: E402
from workflow import run_workflow  # noqa: E402

__all__ = ["run_agent", "run_workflow"]
