"""Central cost calculation for Groq LLM calls.

Pricing is per the model actually configured for this project (GROQ_MODEL,
default "openai/gpt-oss-20b"). Source: Groq's published per-model pricing
(see README.md "Cost Calculation" section for the exact figures and link).
All cost math for both agent.py and workflow.py must go through
`calculate_cost` so there is exactly one place pricing assumptions live.
"""

PRICING_PER_MILLION_TOKENS = {
    "openai/gpt-oss-20b": {
        "input": 0.075,
        "output": 0.30,
    },
}

# Fallback used only if GROQ_MODEL is changed to something not in the table
# above -- keeps cost tracking from silently going to zero.
_DEFAULT_PRICING = PRICING_PER_MILLION_TOKENS["openai/gpt-oss-20b"]


def calculate_cost(input_tokens, output_tokens, model="openai/gpt-oss-20b"):
    """Return the estimated USD cost of one LLM call.

    input_tokens / output_tokens must be the actual usage figures returned by
    the Groq API for that single call (not cumulative) -- callers accumulate
    the returned cost themselves across calls.
    """
    pricing = PRICING_PER_MILLION_TOKENS.get(model, _DEFAULT_PRICING)

    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]

    return input_cost + output_cost
