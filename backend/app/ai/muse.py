"""Muse Spark: explains simulation results in plain language.

Rule: Muse NEVER computes numbers. It only receives the numbers produced by the
deterministic simulation and explains them. If Muse is unavailable we fall back
to a template explanation so the demo still works.
"""
import json
import os

from app.schemas.models import SimResult

META_API_KEY = os.getenv("META_API_KEY")


def build_prompt(observed_tph: float, baseline: SimResult, scenario: SimResult | None) -> str:
    data = {
        "observed_throughput_per_hour": round(observed_tph, 1),
        "baseline": baseline.model_dump(),
        "scenario": scenario.model_dump() if scenario else None,
    }
    return (
        "You are an operations analyst. Explain the bottleneck and the effect of the scenario "
        "in 3-5 sentences for a warehouse manager. Use ONLY the numbers below; do not invent "
        "or recompute any figures. Mention uncertainty (confidence intervals) when relevant.\n\n"
        + json.dumps(data, indent=2)
    )


def _call_muse_spark(prompt: str) -> str:
    # TODO: implement with Meta's official Muse Spark API once credentials are available.
    raise NotImplementedError


def explain(observed_tph: float, baseline: SimResult, scenario: SimResult | None, bottleneck_id: str) -> str:
    if META_API_KEY:
        try:
            return _call_muse_spark(build_prompt(observed_tph, baseline, scenario))
        except NotImplementedError:
            pass
    return _fallback_explanation(observed_tph, baseline, scenario, bottleneck_id)


def _fallback_explanation(observed_tph, baseline, scenario, bottleneck_id) -> str:
    b = next(s for s in baseline.stations if s.zone_id == bottleneck_id)
    text = (
        f"The bottleneck is {b.name}: it is busy {b.utilisation.mean:.0%} of the time with an "
        f"average queue of {b.avg_queue_length.mean:.1f} items. Baseline throughput is "
        f"{baseline.throughput_per_hour.mean:.0f}/h "
        f"(95% CI {baseline.throughput_per_hour.ci_low:.0f}-{baseline.throughput_per_hour.ci_high:.0f}) "
        f"vs {observed_tph:.0f}/h observed in the video."
    )
    if b.utilisation.mean > 0.97:
        text += " Utilisation near 100% means the queue keeps growing: this station cannot keep up with arrivals."
    if scenario:
        delta = scenario.throughput_per_hour.mean - baseline.throughput_per_hour.mean
        sb = next(s for s in scenario.stations if s.zone_id == bottleneck_id)
        text += (
            f" Under '{scenario.name}', throughput changes by {delta:+.0f}/h to "
            f"{scenario.throughput_per_hour.mean:.0f}/h and the queue at {sb.name} becomes "
            f"{sb.avg_queue_length.mean:.1f}."
        )
    return text
