"""Conservative per-attempt monetary cap for a separately approved live evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


def _nonnegative_decimal(value: str, name: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"invalid_{name}") from error
    if not parsed.is_finite() or parsed < 0:
        raise ValueError(f"invalid_{name}")
    return parsed


@dataclass
class AttemptBudget:
    max_attempts: int
    max_spend_usd: Decimal
    input_usd_per_million: Decimal
    output_usd_per_million: Decimal
    attempts: int = 0
    reserved_usd: Decimal = Decimal(0)

    @classmethod
    def from_strings(
        cls,
        *,
        max_attempts: int,
        max_spend_usd: str,
        input_usd_per_million: str,
        output_usd_per_million: str,
    ) -> AttemptBudget:
        if not 1 <= max_attempts <= 100:
            raise ValueError("invalid_eval_attempt_limit")
        return cls(
            max_attempts=max_attempts,
            max_spend_usd=_nonnegative_decimal(max_spend_usd, "eval_spend_limit"),
            input_usd_per_million=_nonnegative_decimal(input_usd_per_million, "eval_input_price"),
            output_usd_per_million=_nonnegative_decimal(
                output_usd_per_million, "eval_output_price"
            ),
        )

    def reserve(self, request_bytes: int, max_output_tokens: int) -> None:
        if request_bytes <= 0 or max_output_tokens <= 0 or max_output_tokens > 4096:
            raise ValueError("invalid_eval_attempt_shape")
        if self.attempts >= self.max_attempts:
            raise RuntimeError("eval_call_budget_exhausted")
        # UTF-8 request bytes are a conservative upper bound on input tokens;
        # reserve the full allowed output even if the provider later fails.
        maximum_charge = (
            Decimal(request_bytes) * self.input_usd_per_million
            + Decimal(max_output_tokens) * self.output_usd_per_million
        ) / Decimal(1_000_000)
        if self.reserved_usd + maximum_charge > self.max_spend_usd:
            raise RuntimeError("eval_spend_budget_exhausted")
        self.attempts += 1
        self.reserved_usd += maximum_charge
