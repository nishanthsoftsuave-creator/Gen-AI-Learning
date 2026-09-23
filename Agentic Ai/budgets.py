"""The four agent budgets, and a tracker that actually enforces them.

These constants are deliberately tight relative to a single question so that
a real run can plausibly hit any one of them (verified in
budget_termination_test.py / output/budget_termination.log), rather than
being generous ceilings that never fire in practice.
"""

import time

from cost import calculate_cost

MAX_ITERATIONS = 8
MAX_TOKENS = 12000
MAX_COST = 0.02  # USD, per question
MAX_WALL_CLOCK_SECONDS = 90.0

TERMINATION_COMPLETED = "COMPLETED"
TERMINATION_MAX_ITERATIONS = "MAX_ITERATIONS_EXCEEDED"
TERMINATION_MAX_TOKENS = "MAX_TOKENS_EXCEEDED"
TERMINATION_MAX_COST = "MAX_COST_EXCEEDED"
TERMINATION_MAX_WALL_CLOCK = "MAX_WALL_CLOCK_EXCEEDED"


class BudgetTracker:
    """Tracks cumulative usage across ALL LLM calls in one agent run and
    tells the caller which budget (if any) has been exceeded."""

    def __init__(
        self,
        max_iterations=MAX_ITERATIONS,
        max_tokens=MAX_TOKENS,
        max_cost=MAX_COST,
        max_wall_clock_seconds=MAX_WALL_CLOCK_SECONDS,
    ):
        self.max_iterations = max_iterations
        self.max_tokens = max_tokens
        self.max_cost = max_cost
        self.max_wall_clock_seconds = max_wall_clock_seconds

        self.start_time = time.monotonic()
        self.iterations = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        self.llm_calls = []

    def elapsed_seconds(self):
        return time.monotonic() - self.start_time

    def begin_iteration(self):
        self.iterations += 1

    def record_llm_call(self, input_tokens, output_tokens, model):
        cost = calculate_cost(input_tokens, output_tokens, model=model)

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_tokens += input_tokens + output_tokens
        self.total_cost += cost

        self.llm_calls.append(
            {
                "iteration": self.iterations,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost": cost,
                "cumulative_tokens": self.total_tokens,
                "cumulative_cost": self.total_cost,
            }
        )

        return cost

    def check(self):
        """Returns a termination reason string, or None if all four budgets
        are still within bounds."""

        if self.iterations > self.max_iterations:
            return TERMINATION_MAX_ITERATIONS

        if self.total_tokens >= self.max_tokens:
            return TERMINATION_MAX_TOKENS

        if self.total_cost >= self.max_cost:
            return TERMINATION_MAX_COST

        if self.elapsed_seconds() >= self.max_wall_clock_seconds:
            return TERMINATION_MAX_WALL_CLOCK

        return None

    def snapshot(self):
        return {
            "iterations": self.iterations,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "elapsed_seconds": self.elapsed_seconds(),
            "budgets": {
                "max_iterations": self.max_iterations,
                "max_tokens": self.max_tokens,
                "max_cost": self.max_cost,
                "max_wall_clock_seconds": self.max_wall_clock_seconds,
            },
        }
