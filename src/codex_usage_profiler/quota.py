from __future__ import annotations

from typing import Any, Dict, Optional

from .config import Config
from .models import CodexBarTelemetry, Estimate, SessionRecord


FALLBACK_RATES: Dict[str, Dict[str, float]] = {
    "gpt-5.5": {"input": 5.0, "output": 30.0, "cache_read": 0.5},
    "openai/gpt-5.5": {"input": 5.0, "output": 30.0, "cache_read": 0.5},
    "gpt-5.4": {"input": 5.0, "output": 30.0, "cache_read": 0.5},
    "gpt-5.4-mini": {"input": 0.25, "output": 2.0, "cache_read": 0.025},
    "gpt-5.3-codex-spark": {"input": 0.5, "output": 4.0, "cache_read": 0.05},
}


def apply_estimates(records: list[SessionRecord], config: Config, telemetry: CodexBarTelemetry) -> None:
    rates = build_rate_map(config, telemetry)
    for record in records:
        record.estimate = estimate_session(record, rates, config)


def build_rate_map(config: Config, telemetry: CodexBarTelemetry) -> Dict[str, Dict[str, float]]:
    rates: Dict[str, Dict[str, float]] = {**FALLBACK_RATES}
    for model, rate in config.rates.items():
        rates[model] = {k: float(v) for k, v in rate.items() if isinstance(v, (int, float))}
    pricing = telemetry.pricing_cache or {}
    models = pricing.get("models") if isinstance(pricing, dict) else None
    if isinstance(models, dict):
        for model_id, payload in models.items():
            if not isinstance(payload, dict):
                continue
            cost = payload.get("cost") if isinstance(payload.get("cost"), dict) else None
            if not cost:
                continue
            rate = {
                "input": _float(cost.get("input")),
                "output": _float(cost.get("output")),
                "cache_read": _float(cost.get("cache_read")),
            }
            clean = {k: v for k, v in rate.items() if v is not None}
            if "input" in clean or "output" in clean:
                rates[str(model_id)] = clean  # last write wins from cache
    return rates


def estimate_session(record: SessionRecord, rates: Dict[str, Dict[str, float]], config: Config) -> Estimate:
    if not record.usage_known:
        return Estimate(confidence="unknown", evidence=["no token usage snapshot"])
    model = record.model or "unknown"
    rate = rates.get(model) or rates.get(f"openai/{model}")
    if not rate:
        return Estimate(confidence="unknown", evidence=[f"missing rate for {model}"])
    input_tokens = record.usage.get("input_tokens", 0)
    cached_tokens = record.usage.get("cached_input_tokens", 0)
    output_tokens = record.usage.get("output_tokens", 0)
    billable_uncached = max(0, input_tokens - cached_tokens)
    cost = (
        billable_uncached / 1_000_000 * rate.get("input", 0.0)
        + cached_tokens / 1_000_000 * rate.get("cache_read", rate.get("input", 0.0))
        + output_tokens / 1_000_000 * rate.get("output", 0.0)
    )
    dollars_per_credit = config.dollars_per_credit
    credits = cost / dollars_per_credit if dollars_per_credit else None
    evidence = [f"model_rate:{model}", "billable_input=input-cached_input", "rate_card_replacement_cost"]
    if credits is None:
        evidence.append("credits_unset_without_dollars_per_credit")
    return Estimate(
        credits=credits,
        cost_usd=cost,
        confidence="rate_card_estimate",
        evidence=evidence,
    )


def observed_share(record: SessionRecord, total_tokens: int) -> Optional[float]:
    if not total_tokens:
        return None
    return record.usage.get("total_tokens", 0) / total_tokens * 100


def _float(value: Any) -> Optional[float]:
    return float(value) if isinstance(value, (int, float)) else None
