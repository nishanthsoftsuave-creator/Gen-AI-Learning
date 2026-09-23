import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
TRACE_DIR = BASE_DIR / "output" / "traces"

GROQ_MODEL = "openai/gpt-oss-20b"

groq_client = Groq()


def replay_trace(trace_id):
    trace_file = TRACE_DIR / f"{trace_id}.json"

    if not trace_file.exists():
        print(f"Trace not found: {trace_file}")
        return

    trace = json.loads(
        trace_file.read_text(encoding="utf-8")
    )

    prompt = trace["prompt"]
    model = trace["model"]
    temperature = trace["temperature"]

    response = groq_client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        temperature=temperature,
    )

    replayed_output = response.choices[0].message.content

    print("\n========== TRACE ==========")
    print(trace_id)

    print("\n========== ORIGINAL OUTPUT ==========")
    print(trace["raw_output"])

    print("\n========== REPLAYED OUTPUT ==========")
    print(replayed_output)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python replay_trace.py <trace_id>")
        sys.exit(1)

    replay_trace(sys.argv[1])