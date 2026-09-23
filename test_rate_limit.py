"""Test Groq API rate limit (30 requests/min)."""

import time
from pathlib import Path
from dotenv import load_dotenv
import os
from groq import Groq

load_dotenv(Path(__file__).parent / ".env")

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def send_request(i):
    """Send a single request and return (success, error_msg)."""
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": f"Say 'hello {i}'"}],
            temperature=0,
            max_tokens=10,
        )
        return True, response.choices[0].message.content.strip()
    except Exception as e:
        return False, str(e)


def test_rate_limit(total_requests=40, delay_between=1.0):
    """
    Send `total_requests` requests with `delay_between` seconds pause.
    This helps find where the 30 req/min limit kicks in.
    """
    print("=" * 60)
    print("Groq Rate Limit Test")
    print(f"Model: {GROQ_MODEL}")
    print("Limit: 30 requests/min")
    print(f"Sending: {total_requests} requests, {delay_between}s apart")
    print("=" * 60)

    success_count = 0
    fail_count = 0
    start = time.time()

    for i in range(1, total_requests + 1):
        elapsed = time.time() - start
        ok, msg = send_request(i)

        if ok:
            success_count += 1
            status = "OK  "
        else:
            fail_count += 1
            status = "FAIL"

        print(f"  [{i:2d}] {status} {elapsed:6.1f}s | {msg[:60]}")

        if i < total_requests:
            time.sleep(delay_between)

    total_time = time.time() - start
    print()
    print("=" * 60)
    print("Results:")
    print(f"  Success : {success_count}/{total_requests}")
    print(f"  Failed  : {fail_count}/{total_requests}")
    print(f"  Total   : {total_time:.1f}s ({total_time/60:.1f} min)")
    print("=" * 60)


if __name__ == "__main__":
    # 40 requests, 1.5s apart = covers ~60s window to hit the limit
    test_rate_limit(total_requests=40, delay_between=1.5)
