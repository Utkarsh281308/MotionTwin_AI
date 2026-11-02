"""Muse Spark: explains simulation results in plain language.

Rule: Muse NEVER computes numbers. It only receives numbers and verdicts produced by the
deterministic simulation and data-quality checks, and explains them. If Muse is
unavailable we fall back to a template explanation so the demo still works.
"""
import json
import logging

from app.meta_client import get_client
from app.schemas.models import Bottleneck, Calibration, Notice, SimResult

MODEL = "muse-spark-1.3"
log = logging.getLogger(__name__)


def _summarise(r: SimResult) -> dict:
    """Rounded, human-labelled numbers so the model can quote them naturally."""
    rng = lambda e, d=1: f"{e.mean:.{d}f} (95% range {e.ci_low:.{d}f}-{e.ci_high:.{d}f})"
    return {
        "throughput_per_hour": rng(r.throughput_per_hour, 0),
        "avg_time_through_line_seconds": rng(r.avg_cycle_time),
        "stations": [
            {
                "name": s.name,
                "workers_or_machines": s.capacity,
                "busy_percent": f"{s.utilisation.mean * 100:.0f}%",
                "avg_items_waiting": f"{s.avg_queue_length.mean:.1f}",
                "avg_wait_seconds": f"{s.avg_wait.mean:.1f}",
            }
            for s in r.stations
        ],
    }


def build_prompt(observed_tph, calibration, baseline, scenario, changes, bottleneck, scenario_bottleneck, notices) -> str:
    data = {
        "model_check_against_video": {
            "video_seconds": f"{calibration.window_seconds:.0f}",
            "objects_completed_in_video": calibration.observed_completed,
            "objects_completed_predicted_by_model": f"{calibration.simulated_completed.mean:.1f}",
        },
        "baseline_simulation": _summarise(baseline),
        "baseline_bottleneck_verdict": bottleneck.reason,
        "scenario_changes": changes or ["none"],
        "scenario_simulation": _summarise(scenario) if scenario else None,
        "scenario_bottleneck_verdict": scenario_bottleneck.reason if scenario_bottleneck else None,
        "data_quality_warnings": [n.message for n in notices if n.level != "info"],
    }
    return (
        "You are an operations analyst talking to a warehouse manager. In 3-5 short sentences of "
        "plain English: (1) say whether the model matches the video, (2) state the bottleneck verdict "
        "exactly as given (if it says no station is constrained, say there is no bottleneck), "
        "(3) say what the scenario changes and its effect, (4) if there are data-quality warnings, "
        "say the results are provisional. Use ONLY the numbers below, rounded as given; never calculate "
        "new numbers. Don't use field names, JSON keys or jargon. Mention the 95% range only for throughput.\n\n"
        + json.dumps(data, indent=2)
    )


def _call_muse_spark(prompt: str) -> str:
    response = get_client().responses.create(model=MODEL, input=prompt)
    return response.output_text.strip()


def explain(
    observed_tph: float,
    calibration: Calibration,
    baseline: SimResult,
    scenario: SimResult | None,
    changes: list[str],
    bottleneck: Bottleneck,
    scenario_bottleneck: Bottleneck | None,
    notices: list[Notice],
) -> str:
    args = (observed_tph, calibration, baseline, scenario, changes, bottleneck, scenario_bottleneck, notices)
    try:
        text = _call_muse_spark(build_prompt(*args))
        if text:
            return text
    except Exception as e:  # no key, network error, API error -> keep the demo working
        log.warning("Muse Spark unavailable, using template explanation: %s", e)
    return _fallback_explanation(*args)


def _fallback_explanation(observed_tph, calibration, baseline, scenario, changes, bottleneck,
                          scenario_bottleneck, notices) -> str:
    c = calibration
    text = (
        f"In the {c.window_seconds:.0f} s video, {c.observed_completed} objects completed the line; the model "
        f"predicts {c.simulated_completed.mean:.1f} for the same window. {bottleneck.reason} "
        f"Baseline throughput is {baseline.throughput_per_hour.mean:.0f}/h "
        f"(95% range {baseline.throughput_per_hour.ci_low:.0f}-{baseline.throughput_per_hour.ci_high:.0f})."
    )
    if scenario and changes:
        delta = scenario.throughput_per_hour.mean - baseline.throughput_per_hour.mean
        text += (f" With {', '.join(changes)}, throughput changes by {delta:+.0f}/h to "
                 f"{scenario.throughput_per_hour.mean:.0f}/h. {scenario_bottleneck.reason}")
    elif scenario:
        text += " The scenario has no changes, so it matches the baseline."
    if any(n.level != "info" for n in notices):
        text += " These results are provisional: see the data-quality warnings."
    return text
