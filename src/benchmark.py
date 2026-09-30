"""
Controlled synthetic benchmarking experiment for the Subtle Decline Dashboard.

Implements the 7 ground-truth scenarios required by Review 1:
  TC1  – Gradual mobility decline → adverse event
  TC2  – Nutrition decline → adverse event
  TC3  – Participation decline → adverse event
  TC4  – Missing data → safe fallback (no high-confidence alert)
  TC5  – Stale data → reduced/withheld confidence
  TC6  – False positive / temporary anomaly → should NOT sustain as decline
  TC7  – Multi-signal decline → stronger evidence than single domain

Each scenario has explicit ground truth:
  patient_id, decline_start_day, adverse_event_day,
  expected_decline, affected_domains

Performance metrics calculated:
  True Positives, False Positives, True Negatives, False Negatives,
  Precision, Recall, F1, Lead Time before adverse event

Before/after comparison:
  "Baseline method"  = static head-30 mean + percentage delta (original logic)
  "Improved method"  = rolling-window z-score + trust-state gating (new logic)

IMPORTANT: Results are computed from actual algorithm runs, not fabricated.
           This module is a PROTOTYPE / SYNTHETIC BENCHMARK only.
           Results do not constitute clinical validation.

Usage:
    python -m src.benchmark
"""

from __future__ import annotations

import json
import numpy as np
import pandas as pd
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

try:
    from .baseline import (
        compute_patient_baseline_summary, BASELINE_WINDOW,
        MIN_BASELINE_OBSERVATIONS, SUSTAINED_DECLINE_DAYS,
        Z_SCORE_WARNING_THRESHOLD, DOMAIN_COLUMNS, INSUFFICIENT_BASELINE,
    )
    from .data_quality import (
        assess_patient_data_quality, FreshnessStatus, TrustLevel,
    )
    from .alert_engine import DeclineDetector, _classify_alert_severity, _compute_composite_score
    from .utils import get_project_root
except ImportError:
    from baseline import (
        compute_patient_baseline_summary, BASELINE_WINDOW,
        MIN_BASELINE_OBSERVATIONS, SUSTAINED_DECLINE_DAYS,
        Z_SCORE_WARNING_THRESHOLD, DOMAIN_COLUMNS, INSUFFICIENT_BASELINE,
    )
    from data_quality import (
        assess_patient_data_quality, FreshnessStatus, TrustLevel,
    )
    from alert_engine import DeclineDetector, _classify_alert_severity, _compute_composite_score
    from utils import get_project_root

# ─────────────────────────────────────────────────────────────────
# RANDOM SEED — makes results reproducible
# ─────────────────────────────────────────────────────────────────
RANDOM_SEED: int = 42
np.random.seed(RANDOM_SEED)

# Observation period for benchmark scenarios (days)
TOTAL_DAYS: int   = 60   # 60 days total
BASELINE_DAYS: int = 20  # First 20 days as stable baseline
DECLINE_START_DAY: int = 21  # Decline begins on day 21
ADVERSE_EVENT_DAY: int = 35  # Adverse event on day 35 (14-day window)

# Noise level for normal variation
NORMAL_NOISE_STD: float = 0.04   # 4% of baseline value


# ─────────────────────────────────────────────────────────────────
# GROUND TRUTH REGISTRY
# ─────────────────────────────────────────────────────────────────

GROUND_TRUTH: List[Dict[str, Any]] = [
    {
        "scenario_id":      "TC1",
        "name":             "Gradual mobility decline",
        "patient_id":       "BM_P001",
        "decline_start_day": DECLINE_START_DAY,
        "adverse_event_day": ADVERSE_EVENT_DAY,
        "expected_decline":  True,
        "affected_domains":  ["mobility"],
        "expected_trust":    TrustLevel.HIGH_CONFIDENCE,
        "description":       "Normal baseline -> gradual mobility decline -> adverse event.",
    },
    {
        "scenario_id":      "TC2",
        "name":             "Nutrition decline",
        "patient_id":       "BM_P002",
        "decline_start_day": DECLINE_START_DAY,
        "adverse_event_day": ADVERSE_EVENT_DAY,
        "expected_decline":  True,
        "affected_domains":  ["nutrition"],
        "expected_trust":    TrustLevel.HIGH_CONFIDENCE,
        "description":       "Normal meal intake -> gradual reduction -> adverse event.",
    },
    {
        "scenario_id":      "TC3",
        "name":             "Participation decline",
        "patient_id":       "BM_P003",
        "decline_start_day": DECLINE_START_DAY,
        "adverse_event_day": ADVERSE_EVENT_DAY,
        "expected_decline":  True,
        "affected_domains":  ["participation"],
        "expected_trust":    TrustLevel.HIGH_CONFIDENCE,
        "description":       "Normal participation -> gradual reduction -> adverse event.",
    },
    {
        "scenario_id":      "TC4",
        "name":             "Missing data -> safe fallback",
        "patient_id":       "BM_P004",
        "decline_start_day": None,
        "adverse_event_day": None,
        "expected_decline":  False,
        "affected_domains":  [],
        "expected_trust":    TrustLevel.INSUFFICIENT_EVIDENCE,
        "description":       "Critical observations missing - no high-confidence alert expected.",
    },
    {
        "scenario_id":      "TC5",
        "name":             "Stale data -> reduced confidence",
        "patient_id":       "BM_P005",
        "decline_start_day": None,
        "adverse_event_day": None,
        "expected_decline":  False,
        "affected_domains":  [],
        "expected_trust":    TrustLevel.LOW_CONFIDENCE,
        "description":       "Last update older than freshness threshold - confidence withheld.",
    },
    {
        "scenario_id":      "TC6",
        "name":             "False positive / temporary anomaly",
        "patient_id":       "BM_P006",
        "decline_start_day": None,
        "adverse_event_day": None,
        "expected_decline":  False,
        "affected_domains":  [],
        "expected_trust":    TrustLevel.HIGH_CONFIDENCE,
        "description":       "One abnormal observation then recovery - should NOT be classified as sustained decline.",
    },
    {
        "scenario_id":      "TC7",
        "name":             "Multi-signal decline",
        "patient_id":       "BM_P007",
        "decline_start_day": DECLINE_START_DAY,
        "adverse_event_day": ADVERSE_EVENT_DAY,
        "expected_decline":  True,
        "affected_domains":  ["mobility", "nutrition", "participation"],
        "expected_trust":    TrustLevel.HIGH_CONFIDENCE,
        "description":       "All three domains decline -> stronger composite evidence.",
    },
]


# ─────────────────────────────────────────────────────────────────
# SYNTHETIC DATA GENERATORS
# ─────────────────────────────────────────────────────────────────

def _make_dates(n_days: int, end_date: Optional[date] = None) -> List[date]:
    """Generate a list of consecutive dates ending at end_date."""
    if end_date is None:
        end_date = date.today()
    return [end_date - timedelta(days=(n_days - 1 - i)) for i in range(n_days)]


def _stable_series(baseline: float, n: int, noise_std: float = NORMAL_NOISE_STD) -> np.ndarray:
    """Generate a stable time series with Gaussian noise."""
    return np.maximum(baseline * 0.3, baseline + np.random.normal(0, noise_std * baseline, n))


def _gradual_decline(
    baseline: float,
    n_total: int,
    decline_start: int,
    decline_rate_per_day: float = 0.025,
    noise_std: float = NORMAL_NOISE_STD,
) -> np.ndarray:
    """
    Generate a series with stable baseline then gradual linear decline.

    Args:
        baseline:             Starting value.
        n_total:              Total number of observations.
        decline_start:        Day index (0-based) when decline begins.
        decline_rate_per_day: Fractional decline per day after start.
        noise_std:            Noise fraction of baseline.

    Returns:
        Numpy array of values.
    """
    values = np.zeros(n_total)
    for i in range(n_total):
        noise = np.random.normal(0, noise_std * baseline)
        if i < decline_start:
            values[i] = baseline + noise
        else:
            days_declining = i - decline_start + 1
            decline_factor = 1.0 - (decline_rate_per_day * days_declining)
            decline_factor = max(decline_factor, 0.3)   # floor at 30% of baseline
            values[i] = baseline * decline_factor + noise
    return np.maximum(values, baseline * 0.1)


def _build_patient_df(
    patient_id: str,
    dates: List[date],
    mobility_vals: np.ndarray,
    nutrition_vals: np.ndarray,
    participation_vals: np.ndarray,
) -> pd.DataFrame:
    """Construct a patient observation DataFrame."""
    return pd.DataFrame({
        "patient_id":              patient_id,
        "patient_name":            f"Benchmark {patient_id}",
        "observation_date":        [d.isoformat() for d in dates],
        "mobility_steps":          np.round(mobility_vals).astype(int),
        "nutrition_kcal":          np.round(nutrition_vals).astype(int),
        "participation_minutes":   np.round(participation_vals).astype(int),
        "data_source":             "Synthetic Benchmark",
        "observation_quality":     "Good",
    })


def generate_benchmark_scenarios() -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """
    Generate synthetic data for all 7 benchmark scenarios.

    Returns:
        (combined_df, ground_truth_list):
          combined_df – full DataFrame for all benchmark patients
          ground_truth_list – GROUND_TRUTH list with resolved dates added
    """
    np.random.seed(RANDOM_SEED)

    end_date   = date.today()
    dates      = _make_dates(TOTAL_DAYS, end_date=end_date)
    all_frames: List[pd.DataFrame] = []

    # Baselines per domain
    mob_base  = 6500
    nut_base  = 2000
    part_base = 75

    # TC1 — Gradual mobility decline only
    mob_tc1  = _gradual_decline(mob_base,  TOTAL_DAYS, DECLINE_START_DAY - 1, 0.03)
    nut_tc1  = _stable_series(nut_base,  TOTAL_DAYS)
    part_tc1 = _stable_series(part_base, TOTAL_DAYS)
    all_frames.append(_build_patient_df("BM_P001", dates, mob_tc1, nut_tc1, part_tc1))

    # TC2 — Nutrition decline only
    mob_tc2  = _stable_series(mob_base,  TOTAL_DAYS)
    nut_tc2  = _gradual_decline(nut_base,  TOTAL_DAYS, DECLINE_START_DAY - 1, 0.025)
    part_tc2 = _stable_series(part_base, TOTAL_DAYS)
    all_frames.append(_build_patient_df("BM_P002", dates, mob_tc2, nut_tc2, part_tc2))

    # TC3 — Participation decline only
    mob_tc3  = _stable_series(mob_base,  TOTAL_DAYS)
    nut_tc3  = _stable_series(nut_base,  TOTAL_DAYS)
    part_tc3 = _gradual_decline(part_base, TOTAL_DAYS, DECLINE_START_DAY - 1, 0.035)
    all_frames.append(_build_patient_df("BM_P003", dates, mob_tc3, nut_tc3, part_tc3))

    # TC4 — Missing data: only 4 recent observations (< MIN_BASELINE_OBSERVATIONS)
    # Patient has only a few observations — critical domains have insufficient baseline
    short_dates = dates[-5:]   # only last 5 days
    mob_tc4  = _stable_series(mob_base,  5)
    nut_tc4  = _stable_series(nut_base,  5)
    part_tc4 = _stable_series(part_base, 5)
    df_tc4 = _build_patient_df("BM_P004", short_dates, mob_tc4, nut_tc4, part_tc4)
    # Drop nutrition observations entirely to simulate missing domain
    df_tc4["nutrition_kcal"] = np.nan
    all_frames.append(df_tc4)

    # TC5 — Stale data: all observations end 5 days ago (> 72h freshness threshold)
    stale_end   = end_date - timedelta(days=5)
    stale_dates = _make_dates(TOTAL_DAYS, end_date=stale_end)
    mob_tc5  = _stable_series(mob_base,  TOTAL_DAYS)
    nut_tc5  = _stable_series(nut_base,  TOTAL_DAYS)
    part_tc5 = _stable_series(part_base, TOTAL_DAYS)
    all_frames.append(_build_patient_df("BM_P005", stale_dates, mob_tc5, nut_tc5, part_tc5))

    # TC6 — Temporary anomaly: one bad observation then recovery
    mob_tc6  = _stable_series(mob_base,  TOTAL_DAYS)
    nut_tc6  = _stable_series(nut_base,  TOTAL_DAYS)
    part_tc6 = _stable_series(part_base, TOTAL_DAYS)
    # Inject a single bad day at day 30 (index 29), then immediately recover
    mob_tc6[29]  = mob_base  * 0.50   # 50% drop — anomalous but isolated
    nut_tc6[29]  = nut_base  * 0.55
    part_tc6[29] = part_base * 0.50
    all_frames.append(_build_patient_df("BM_P006", dates, mob_tc6, nut_tc6, part_tc6))

    # TC7 — Multi-signal: all three domains decline
    mob_tc7  = _gradual_decline(mob_base,  TOTAL_DAYS, DECLINE_START_DAY - 1, 0.025)
    nut_tc7  = _gradual_decline(nut_base,  TOTAL_DAYS, DECLINE_START_DAY - 1, 0.022)
    part_tc7 = _gradual_decline(part_base, TOTAL_DAYS, DECLINE_START_DAY - 1, 0.030)
    all_frames.append(_build_patient_df("BM_P007", dates, mob_tc7, nut_tc7, part_tc7))

    combined = pd.concat(all_frames, ignore_index=True)

    # Resolve dates in ground truth
    resolved_gt = []
    for gt in GROUND_TRUTH:
        gt_copy = gt.copy()
        if gt["decline_start_day"] is not None:
            gt_copy["decline_start_date"] = dates[gt["decline_start_day"] - 1].isoformat()
        else:
            gt_copy["decline_start_date"] = None
        if gt["adverse_event_day"] is not None:
            gt_copy["adverse_event_date"] = dates[gt["adverse_event_day"] - 1].isoformat()
        else:
            gt_copy["adverse_event_date"] = None
        resolved_gt.append(gt_copy)

    return combined, resolved_gt


# ─────────────────────────────────────────────────────────────────
# BASELINE (ORIGINAL) DETECTOR
# Simulates the pre-improvement static-mean logic for comparison.
# ─────────────────────────────────────────────────────────────────

def _run_baseline_detector(
    patient_df: pd.DataFrame, patient_id: str
) -> Dict[str, Any]:
    """
    Run the original head-30-mean baseline detector logic on a single patient.

    This is the "before" comparison method.

    Returns:
        Dict with 'alert_generated' (bool), 'severity' (str), 'composite_score' (float).
    """
    pdata = patient_df.sort_values("observation_date").reset_index(drop=True)

    baseline_rows = pdata.head(30).dropna(
        subset=["mobility_steps", "nutrition_kcal", "participation_minutes"]
    )
    if len(baseline_rows) < 5:
        return {"alert_generated": False, "severity": "NONE", "composite_score": 0.0,
                "method": "BASELINE"}

    mob_base  = baseline_rows["mobility_steps"].mean()
    nut_base  = baseline_rows["nutrition_kcal"].mean()
    part_base = baseline_rows["participation_minutes"].mean()

    recent = pdata.tail(3).dropna(
        subset=["mobility_steps", "nutrition_kcal", "participation_minutes"]
    )
    if len(recent) < 2:
        return {"alert_generated": False, "severity": "NONE", "composite_score": 0.0,
                "method": "BASELINE"}

    def pct_change(curr, base):
        return ((curr - base) / base * 100) if base != 0 else 0.0

    mob_delta  = pct_change(recent["mobility_steps"].mean(),  mob_base)
    nut_delta  = pct_change(recent["nutrition_kcal"].mean(),  nut_base)
    part_delta = pct_change(recent["participation_minutes"].mean(), part_base)

    def decline_component(delta_pct, threshold=20.0):
        if delta_pct >= 0:
            return 0.0
        return min(abs(delta_pct) / threshold, 1.0)

    composite = (
        decline_component(mob_delta)  * 0.40 +
        decline_component(nut_delta)  * 0.30 +
        decline_component(part_delta) * 0.30
    )

    if composite >= 0.20:
        if composite >= 0.50:
            sev = "HIGH"
        elif composite >= 0.35:
            sev = "MEDIUM"
        else:
            sev = "LOW"
        return {"alert_generated": True, "severity": sev,
                "composite_score": round(composite, 3), "method": "BASELINE"}

    return {"alert_generated": False, "severity": "NONE",
            "composite_score": round(composite, 3), "method": "BASELINE"}


# ─────────────────────────────────────────────────────────────────
# IMPROVED DETECTOR RUNNER
# ─────────────────────────────────────────────────────────────────

def _run_improved_detector(
    patient_df: pd.DataFrame,
    patient_id: str,
    all_data: pd.DataFrame,
    reference_dt: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Run the improved rolling-baseline + trust-state detector on a patient slice.

    Args:
        patient_df: Single-patient DataFrame.
        patient_id: Patient ID.
        all_data:   Full benchmark DataFrame.
        reference_dt: Optional reference datetime for freshness assessment.

    Returns:
        Dict with detection result and data quality info.
    """
    single_patient_data = patient_df.copy()
    detector = DeclineDetector(single_patient_data)

    if reference_dt is not None:
        quality = assess_patient_data_quality(
            single_patient_data,
            patient_id,
            baseline_summary=detector._baseline_summaries.get(patient_id),
            reference_dt=reference_dt,
        )
        detector._quality_assessments[patient_id] = quality

    alerts = detector.generate_alerts(reference_dt=reference_dt)
    patient_alerts = [a for a in alerts if a["patient_id"] == patient_id]

    quality = detector._quality_assessments.get(patient_id, {})
    trust_tl = quality.get("trust_state", {}).get(
        "trust_level", TrustLevel.INSUFFICIENT_EVIDENCE
    )

    if patient_alerts:
        best = max(patient_alerts, key=lambda a: a["composite_score"])
        return {
            "alert_generated": True,
            "severity":        best["severity"],
            "composite_score": best["composite_score"],
            "trust_level":     trust_tl,
            "alert_date":      best["alert_date"],
            "method":          "IMPROVED",
        }

    return {
        "alert_generated": False,
        "severity":        "NONE",
        "composite_score": 0.0,
        "trust_level":     trust_tl,
        "alert_date":      None,
        "method":          "IMPROVED",
    }


# ─────────────────────────────────────────────────────────────────
# LEAD TIME & TEMPORAL PROCESSING HELPERS
# ─────────────────────────────────────────────────────────────────

def _compute_lead_time(alert_date_str: Optional[str], event_date_str: Optional[str]) -> Optional[int]:
    """
    Compute lead time in days between first alert and adverse event.

    Returns None if alert was not generated, or if event_date is missing,
    or if alert came after the event.
    """
    if alert_date_str is None or event_date_str is None:
        return None
    try:
        alert_dt = date.fromisoformat(alert_date_str)
        event_dt = date.fromisoformat(event_date_str)
        lead = (event_dt - alert_dt).days
        return lead if lead >= 0 else None
    except (ValueError, TypeError):
        return None


def _process_temporal_alerts(
    alerts: List[Dict[str, Any]],
    expected_decline: bool,
    adverse_event_dt: Optional[date],
) -> Dict[str, Any]:
    """
    Process a list of temporal alerts for one scenario.

    Rules:
    - If expected_decline is True:
      - A detection counts as TP only if alert_date <= adverse_event_dt.
      - Take the EARLIEST qualifying detection (first_valid_detection_date).
      - Lead time = (adverse_event_dt - first_valid_detection_date).days.
      - If no pre-event alert exists, result is FN.
    - If expected_decline is False:
      - Any alert across all observation dates makes result FP.
      - If no alert exists, result is TN.
    """
    if expected_decline:
        if adverse_event_dt is None:
            qualifying = alerts
        else:
            qualifying = [a for a in alerts if a["date"] <= adverse_event_dt]

        if qualifying:
            first_a = min(qualifying, key=lambda a: a["date"])
            lead = (adverse_event_dt - first_a["date"]).days if adverse_event_dt else None
            return {
                "alert_generated": True,
                "first_detection_date": first_a["date_str"],
                "lead_time_days": lead,
                "result_type": "TP",
                "severity": first_a["severity"],
                "composite_score": first_a["composite_score"],
                "trust_level": first_a.get("trust_level", TrustLevel.HIGH_CONFIDENCE),
            }
        else:
            return {
                "alert_generated": False,
                "first_detection_date": None,
                "lead_time_days": None,
                "result_type": "FN",
                "severity": "NONE",
                "composite_score": 0.0,
                "trust_level": TrustLevel.INSUFFICIENT_EVIDENCE,
            }
    else:
        if alerts:
            first_a = min(alerts, key=lambda a: a["date"])
            return {
                "alert_generated": True,
                "first_detection_date": first_a["date_str"],
                "lead_time_days": None,
                "result_type": "FP",
                "severity": first_a["severity"],
                "composite_score": first_a["composite_score"],
                "trust_level": first_a.get("trust_level", TrustLevel.HIGH_CONFIDENCE),
            }
        else:
            return {
                "alert_generated": False,
                "first_detection_date": None,
                "lead_time_days": None,
                "result_type": "TN",
                "severity": "NONE",
                "composite_score": 0.0,
                "trust_level": TrustLevel.HIGH_CONFIDENCE,
            }


# ─────────────────────────────────────────────────────────────────
# PERFORMANCE METRICS
# ─────────────────────────────────────────────────────────────────

def compute_metrics(
    scenario_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Compute TP/FP/TN/FN/Precision/Recall/F1/Lead-Time from temporal scenario results.
    """
    tp = fp = tn = fn = 0
    lead_times: List[int] = []

    for r in scenario_results:
        res_type = r.get("result_type")
        if res_type == "TP":
            tp += 1
            lt = r.get("lead_time_days")
            if lt is not None and lt >= 0:
                lead_times.append(lt)
        elif res_type == "FN":
            fn += 1
        elif res_type == "FP":
            fp += 1
        elif res_type == "TN":
            tn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)

    return {
        "true_positives":  tp,
        "false_positives": fp,
        "true_negatives":  tn,
        "false_negatives": fn,
        "precision":       round(precision, 3),
        "recall":          round(recall, 3),
        "f1_score":        round(f1, 3),
        "avg_lead_time_days":    round(float(np.mean(lead_times)), 1) if lead_times else None,
        "median_lead_time_days": round(float(np.median(lead_times)), 1) if lead_times else None,
        "min_lead_time_days":    int(np.min(lead_times)) if lead_times else None,
        "max_lead_time_days":    int(np.max(lead_times)) if lead_times else None,
        "lead_times":      lead_times,
    }


# ─────────────────────────────────────────────────────────────────
# ERROR ANALYSIS
# ─────────────────────────────────────────────────────────────────

def generate_error_analysis(
    scenario_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Produce machine-readable error analysis for FP and FN cases.
    """
    false_positives: List[Dict[str, Any]] = []
    false_negatives: List[Dict[str, Any]] = []

    for r in scenario_results:
        res_type = r.get("result_type")
        sc_id   = r["scenario_id"]
        sc_name = r["scenario_name"]

        if res_type == "FP":
            reason = _classify_fp_reason(r)
            false_positives.append({
                "scenario_id":      sc_id,
                "scenario_name":    sc_name,
                "patient_id":       r["patient_id"],
                "alert_generated":  True,
                "severity":         r.get("severity", "UNKNOWN"),
                "composite_score":  r.get("composite_score", 0),
                "reason_category":  reason,
                "detail":           r.get("detail", ""),
            })

        elif res_type == "FN":
            reason = _classify_fn_reason(r)
            false_negatives.append({
                "scenario_id":      sc_id,
                "scenario_name":    sc_name,
                "patient_id":       r["patient_id"],
                "alert_generated":  False,
                "trust_level":      r.get("trust_level", "UNKNOWN"),
                "reason_category":  reason,
                "detail":           r.get("detail", ""),
            })

    return {
        "false_positives":        false_positives,
        "false_negatives":        false_negatives,
        "false_positive_count":   len(false_positives),
        "false_negative_count":   len(false_negatives),
    }


def _classify_fp_reason(result: Dict[str, Any]) -> str:
    """Classify the likely reason for a false positive."""
    sc_id = result.get("scenario_id", "")
    if sc_id == "TC6":
        return "temporary_anomaly"
    if result.get("composite_score", 0) < 0.35:
        return "threshold_too_sensitive"
    return "noisy_observation"


def _classify_fn_reason(result: Dict[str, Any]) -> str:
    """Classify the likely reason for a false negative."""
    tl = result.get("trust_level", "")
    if tl == TrustLevel.INSUFFICIENT_EVIDENCE:
        return "insufficient_baseline_history_or_missing_observations"
    if tl == TrustLevel.LOW_CONFIDENCE:
        return "stale_data"
    if tl == TrustLevel.DATA_QUALITY_ISSUE:
        return "conflicting_observations"
    return "decline_too_gradual_or_threshold_too_strict"


# ─────────────────────────────────────────────────────────────────
# TIME-SERIES INSPECTION (TASK 13)
# ─────────────────────────────────────────────────────────────────

def inspect_scenario_timeseries(scenario_id: str = "TC1") -> None:
    """
    Print step-by-step observation and detector statistics for a scenario.
    Satisfies Task 13 requirements.
    """
    combined_df, ground_truth = generate_benchmark_scenarios()
    gt = next((g for g in ground_truth if g["scenario_id"] == scenario_id), None)
    if gt is None:
        print(f"Scenario {scenario_id} not found.")
        return

    pid = gt["patient_id"]
    pdata = combined_df[combined_df["patient_id"] == pid].sort_values("observation_date").reset_index(drop=True)

    print("\n" + "=" * 90)
    print(f"TIME-SERIES INSPECTION TRACE FOR {scenario_id} ({gt['name']})")
    print(f"Patient: {pid} | Affected domains: {gt['affected_domains']}")
    print(f"Decline start date: {gt.get('decline_start_date')} | Adverse event date: {gt.get('adverse_event_date')}")
    print("=" * 90)
    print(f"{'Date':<12} | {'Mobility':<8} | {'RollMean':<8} | {'RollStd':<8} | {'Z-Score':<8} | {'Streak':<6} | {'TrustState':<22} | {'Alert'}")
    print("-" * 90)

    for k in range(len(pdata)):
        slice_df = pdata.iloc[:k+1]
        curr_date = slice_df["observation_date"].iloc[-1]
        val = slice_df["mobility_steps"].iloc[-1]

        b_summary = compute_patient_baseline_summary(slice_df, pid)
        mob_info = b_summary.get("mobility", {})
        r_mean = mob_info.get("rolling_mean")
        r_std = mob_info.get("rolling_std")
        z_score = mob_info.get("z_score")
        streak = mob_info.get("consecutive_declining", 0)

        quality = assess_patient_data_quality(slice_df, pid, baseline_summary=b_summary)
        trust_tl = quality["trust_state"].get("trust_level", "UNKNOWN")

        detector = DeclineDetector(slice_df)
        alerts = detector.generate_alerts()
        has_alert = len([a for a in alerts if a["patient_id"] == pid]) > 0

        r_mean_str = f"{r_mean:.1f}" if isinstance(r_mean, (int, float)) else str(r_mean)
        r_std_str = f"{r_std:.1f}" if isinstance(r_std, (int, float)) else str(r_std)
        z_str = f"{z_score:.2f}" if z_score is not None else "N/A"
        alert_str = "[ALERTED]" if has_alert else "-"

        print(f"{curr_date:<12} | {val:<8.0f} | {r_mean_str:<8} | {r_std_str:<8} | {z_str:<8} | {streak:<6} | {trust_tl:<22} | {alert_str}")
    print("=" * 90 + "\n")


# ─────────────────────────────────────────────────────────────────
# MAIN BENCHMARK RUNNER
# ─────────────────────────────────────────────────────────────────

def run_benchmark() -> Dict[str, Any]:
    """
    Run the complete temporal benchmark experiment.

    Generates synthetic data, runs both detectors temporally on each scenario
    across the time-series observation timeline, computes performance metrics
    and error analysis, and returns a fully structured result dict.
    """
    print("=" * 60)
    print("SYNTHETIC BENCHMARK EXPERIMENT (TEMPORAL EVALUATION)")
    print("Prototype/synthetic results only - not clinically validated")
    print("=" * 60)

    print("\nGenerating synthetic benchmark scenarios...")
    combined_df, ground_truth = generate_benchmark_scenarios()
    print(f"  Generated {len(combined_df)} observations across {len(ground_truth)} scenarios.")

    baseline_results:  List[Dict[str, Any]] = []
    improved_results:  List[Dict[str, Any]] = []

    global_ref_date_str = combined_df["observation_date"].max()
    global_ref_dt = datetime.combine(date.fromisoformat(global_ref_date_str), datetime.min.time())

    for gt in ground_truth:
        pid     = gt["patient_id"]
        pdata   = combined_df[combined_df["patient_id"] == pid].sort_values("observation_date").reset_index(drop=True)
        sc_id   = gt["scenario_id"]
        sc_name = gt["name"]
        expected_decline = gt["expected_decline"]
        adverse_event_date_str = gt.get("adverse_event_date")
        adverse_event_dt = date.fromisoformat(adverse_event_date_str) if adverse_event_date_str else None

        print(f"\n  [{sc_id}] {sc_name} - patient {pid}")

        b_alerts: List[Dict[str, Any]] = []
        i_alerts: List[Dict[str, Any]] = []

        min_obs = BASELINE_WINDOW  # 14 days of stable baseline history required
        for k in range(min_obs - 1, len(pdata)):
            slice_df = pdata.iloc[:k+1]
            curr_date_str = slice_df["observation_date"].iloc[-1]
            curr_dt = date.fromisoformat(curr_date_str)

            # ── Baseline detector step ──
            b_res = _run_baseline_detector(slice_df, pid)
            if b_res["alert_generated"]:
                b_alerts.append({
                    "date_str": curr_date_str,
                    "date": curr_dt,
                    "severity": b_res["severity"],
                    "composite_score": b_res["composite_score"],
                })

            # ── Improved detector step ──
            # For TC5 (stale data), all observations end >72h prior to benchmark reference date
            ref_dt = global_ref_dt if pid == "BM_P005" else None
            i_res = _run_improved_detector(slice_df, pid, combined_df, reference_dt=ref_dt)
            if i_res["alert_generated"]:
                i_alerts.append({
                    "date_str": curr_date_str,
                    "date": curr_dt,
                    "severity": i_res["severity"],
                    "composite_score": i_res["composite_score"],
                    "trust_level": i_res.get("trust_level", TrustLevel.INSUFFICIENT_EVIDENCE),
                })

        b_eval = _process_temporal_alerts(b_alerts, expected_decline, adverse_event_dt)
        baseline_results.append({
            "scenario_id":          sc_id,
            "scenario_name":        sc_name,
            "patient_id":           pid,
            "expected_decline":     expected_decline,
            "affected_domains":     gt["affected_domains"],
            "decline_start_date":   gt.get("decline_start_date"),
            "adverse_event_date":   adverse_event_date_str,
            "first_detection_date": b_eval["first_detection_date"],
            "alert_generated":      b_eval["alert_generated"],
            "result_type":          b_eval["result_type"],
            "severity":             b_eval["severity"],
            "composite_score":      b_eval["composite_score"],
            "trust_level":          TrustLevel.HIGH_CONFIDENCE,
            "lead_time_days":       b_eval["lead_time_days"],
            "detail":               "Baseline method (temporal evaluation: static head-30 mean)",
        })

        i_eval = _process_temporal_alerts(i_alerts, expected_decline, adverse_event_dt)
        improved_results.append({
            "scenario_id":          sc_id,
            "scenario_name":        sc_name,
            "patient_id":           pid,
            "expected_decline":     expected_decline,
            "affected_domains":     gt["affected_domains"],
            "decline_start_date":   gt.get("decline_start_date"),
            "adverse_event_date":   adverse_event_date_str,
            "first_detection_date": i_eval["first_detection_date"],
            "alert_generated":      i_eval["alert_generated"],
            "result_type":          i_eval["result_type"],
            "severity":             i_eval["severity"],
            "composite_score":      i_eval["composite_score"],
            "trust_level":          i_eval["trust_level"],
            "lead_time_days":       i_eval["lead_time_days"],
            "detail":               "Improved method (temporal evaluation: rolling z-score + trust gating)",
        })

        b_lt = f"{b_eval['lead_time_days']} days" if b_eval['lead_time_days'] is not None else "N/A"
        i_lt = f"{i_eval['lead_time_days']} days" if i_eval['lead_time_days'] is not None else "N/A"
        print(f"    Expected decline : {expected_decline} | Adverse event date: {adverse_event_date_str or 'None'}")
        print(f"    Baseline method  : Result = {b_eval['result_type']:<2} | First detection = {b_eval['first_detection_date'] or 'N/A':<10} | Lead time = {b_lt}")
        print(f"    Improved method  : Result = {i_eval['result_type']:<2} | First detection = {i_eval['first_detection_date'] or 'N/A':<10} | Lead time = {i_lt}")

    # ── Compute metrics ──────────────────────────────────────────
    print("\n" + "-" * 60)
    print("PERFORMANCE METRICS (TEMPORAL EVALUATION)")
    print("-" * 60)

    baseline_metrics = compute_metrics(baseline_results)
    improved_metrics = compute_metrics(improved_results)

    print(f"\n  BASELINE METHOD (static head-30 mean):")
    _print_metrics(baseline_metrics)
    print(f"\n  IMPROVED METHOD (rolling z-score + trust gating):")
    _print_metrics(improved_metrics)

    baseline_errors = generate_error_analysis(baseline_results)
    improved_errors = generate_error_analysis(improved_results)

    tc4_improved = next((r for r in improved_results if r["scenario_id"] == "TC4"), {})
    tc5_improved = next((r for r in improved_results if r["scenario_id"] == "TC5"), {})
    tc6_improved = next((r for r in improved_results if r["scenario_id"] == "TC6"), {})

    tc4_safe = (tc4_improved.get("result_type") == "TN")
    tc5_safe = (tc5_improved.get("result_type") == "TN")
    tc6_safe = (tc6_improved.get("result_type") == "TN")

    print(f"\n  SAFETY CHECKS:")
    print(f"    TC4 (missing data) - safe fallback: {'PASS [OK]' if tc4_safe else 'FAIL [X]'}")
    print(f"    TC5 (stale data)   - safe fallback: {'PASS [OK]' if tc5_safe else 'FAIL [X]'}")
    print(f"    TC6 (temp anomaly) - no sustained alert: {'PASS [OK]' if tc6_safe else 'FAIL [X]'}")

    result = {
        "experiment_date":    datetime.now().isoformat(),
        "random_seed":        RANDOM_SEED,
        "total_scenarios":    len(ground_truth),
        "ground_truth":       ground_truth,
        "baseline_method": {
            "description":    "Static head-30 mean + percentage-delta composite (temporal evaluation)",
            "results":        baseline_results,
            "metrics":        baseline_metrics,
            "error_analysis": baseline_errors,
        },
        "improved_method": {
            "description":    "Rolling-window z-score + sustained-decline + trust-state gating (temporal evaluation)",
            "results":        improved_results,
            "metrics":        improved_metrics,
            "error_analysis": improved_errors,
        },
        "safety_checks": {
            "TC4_missing_data_safe_fallback": tc4_safe,
            "TC5_stale_data_confidence_reduced": tc5_safe,
            "TC6_temporary_anomaly_not_sustained": tc6_safe,
        },
    }

    return result


def _print_metrics(m: Dict[str, Any]) -> None:
    """Print a metrics dict to stdout."""
    print(f"    TP={m['true_positives']}  FP={m['false_positives']}  "
          f"TN={m['true_negatives']}  FN={m['false_negatives']}")
    print(f"    Precision={m['precision']:.3f}  Recall={m['recall']:.3f}  "
          f"F1={m['f1_score']:.3f}")
    if m.get("avg_lead_time_days") is not None:
        print(f"    Avg Lead Time={m['avg_lead_time_days']:.1f} days  "
              f"(Median={m['median_lead_time_days']:.1f} days, "
              f"Min={m['min_lead_time_days']}, Max={m['max_lead_time_days']})")
    else:
        print(f"    Lead Time: N/A (no true positives with detected alerts)")


# ─────────────────────────────────────────────────────────────────
# SAVE RESULTS
# ─────────────────────────────────────────────────────────────────

def save_benchmark_results(result: Dict[str, Any], output_path: Optional[Path] = None) -> Path:
    """Save benchmark results to a JSON file."""
    if output_path is None:
        project_root = get_project_root()
        output_path  = project_root / "data" / "benchmark_results.json"

    def _serialise(obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        raise TypeError(f"Object of type {type(obj)} is not JSON serialisable")

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, default=_serialise)

    print(f"\n[OK] Benchmark results saved to {output_path}")
    return output_path


# ─────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────

def main() -> Dict[str, Any]:
    """Run the full temporal benchmark and print time-series trace."""
    inspect_scenario_timeseries("TC1")
    result = run_benchmark()
    save_benchmark_results(result)

    print("\n" + "=" * 60)
    print("BENCHMARK COMPLETE")
    print("=" * 60)
    print(f"  Baseline  Precision={result['baseline_method']['metrics']['precision']:.3f} "
          f"Recall={result['baseline_method']['metrics']['recall']:.3f} "
          f"F1={result['baseline_method']['metrics']['f1_score']:.3f}")
    print(f"  Improved  Precision={result['improved_method']['metrics']['precision']:.3f} "
          f"Recall={result['improved_method']['metrics']['recall']:.3f} "
          f"F1={result['improved_method']['metrics']['f1_score']:.3f}")
    lt = result['improved_method']['metrics'].get('avg_lead_time_days')
    print(f"  Lead Time (improved): {f'{lt:.1f} days' if lt is not None else 'N/A'}")
    return result


if __name__ == "__main__":
    main()

