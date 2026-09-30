"""
Data quality, freshness, and trust-state engine for the Subtle Decline Dashboard.

Implements:
  - Hour-based data freshness classification (FRESH / STALE / MISSING)
  - Per-domain freshness for the dashboard
  - Missing observation detection
  - Contradictory data detection (impossible values, duplicates, timestamp conflicts)
  - Trust / evidence state computation
      HIGH_CONFIDENCE / MEDIUM_CONFIDENCE / LOW_CONFIDENCE /
      INSUFFICIENT_EVIDENCE / DATA_QUALITY_ISSUE

IMPORTANT: This module deliberately refuses to produce high-confidence results
when data is stale, missing, or contradictory.  The system must be conservative
rather than presenting uncertain recommendations as reliable findings.

All thresholds are PROTOTYPE / SYNTHETIC-BENCHMARK values only and have NOT
been clinically validated.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple


# ─────────────────────────────────────────────────────────────────
# FRESHNESS THRESHOLDS (hours)
# Prototype defaults — adjust in this one location if needed.
# ─────────────────────────────────────────────────────────────────

FRESHNESS_FRESH_HOURS: float   =  24.0   # 0 – 24 h  → FRESH
FRESHNESS_STALE_HOURS: float   =  72.0   # >24 – 72 h → STALE
# > 72 h                                 →            MISSING / TOO OLD

# Domains that are considered "critical" for overall assessment
CRITICAL_DOMAINS: List[str] = ["mobility", "nutrition", "participation"]

# Mapping domain name → DataFrame column
DOMAIN_COLUMNS: Dict[str, str] = {
    "mobility":      "mobility_steps",
    "nutrition":     "nutrition_kcal",
    "participation": "participation_minutes",
}

# Value validation ranges — values outside these are flagged CONTRADICTORY
VALID_RANGES: Dict[str, Tuple[float, float]] = {
    "mobility_steps":         (0.0, 25000.0),
    "nutrition_kcal":         (200.0, 6000.0),
    "participation_minutes":  (0.0, 1440.0),  # max = 24 hours in minutes
}


# ─────────────────────────────────────────────────────────────────
# FRESHNESS STATES
# ─────────────────────────────────────────────────────────────────

class FreshnessStatus:
    FRESH        = "FRESH"
    STALE        = "STALE"
    MISSING      = "MISSING"
    INSUFFICIENT = "INSUFFICIENT"   # not enough valid observations for baseline
    CONTRADICTORY = "CONTRADICTORY"


class TrustLevel:
    HIGH_CONFIDENCE      = "HIGH_CONFIDENCE"
    MEDIUM_CONFIDENCE    = "MEDIUM_CONFIDENCE"
    LOW_CONFIDENCE       = "LOW_CONFIDENCE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    DATA_QUALITY_ISSUE   = "DATA_QUALITY_ISSUE"


# ─────────────────────────────────────────────────────────────────
# HOUR-BASED FRESHNESS CALCULATION
# ─────────────────────────────────────────────────────────────────

def compute_freshness(
    last_observation_dt: Optional[datetime],
    reference_dt: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Compute data freshness based on elapsed hours since last observation.

    Thresholds (prototype):
      0 – FRESHNESS_FRESH_HOURS hours  → FRESH
      > FRESHNESS_FRESH_HOURS – FRESHNESS_STALE_HOURS hours → STALE
      > FRESHNESS_STALE_HOURS hours    → MISSING

    Args:
        last_observation_dt: Datetime of the most recent observation.
                             Pass None if no data is available at all.
        reference_dt:        "Now" reference time.  Defaults to datetime.now().

    Returns:
        Dict with:
          freshness_status    – FreshnessStatus constant string
          data_age_hours      – float or None
          last_observation_time – ISO string or None
          explanation         – human-readable description
    """
    if reference_dt is None:
        reference_dt = datetime.now()

    if last_observation_dt is None:
        return {
            "freshness_status":       FreshnessStatus.MISSING,
            "data_age_hours":         None,
            "last_observation_time":  None,
            "explanation":            "No observation data received.",
        }

    age_delta = reference_dt - last_observation_dt
    age_hours = age_delta.total_seconds() / 3600.0
    age_days  = age_delta.total_seconds() / 86400.0

    if age_hours < 0:
        # Future timestamp — treat as contradictory
        return {
            "freshness_status":       FreshnessStatus.CONTRADICTORY,
            "data_age_hours":         round(age_hours, 1),
            "last_observation_time":  last_observation_dt.isoformat(),
            "explanation":            "Observation timestamp is in the future.",
        }

    # WHY: A 0.05-hour (+3 min) tolerance is added to boundary comparisons to prevent 
    # sub-second timestamp floating-point rounding precision errors from incorrectly 
    # categorizing data that is exactly 24 or 72 hours old as STALE or MISSING.
    if age_hours <= FRESHNESS_FRESH_HOURS + 0.05:
        status = FreshnessStatus.FRESH
        days_int = int(age_days)
        explanation = f"Data is {days_int} days old ({age_hours:.1f} hours) — current."
    elif age_hours <= FRESHNESS_STALE_HOURS + 0.05:
        status = FreshnessStatus.STALE
        days_int = int(round(age_days))
        explanation = (
            f"Data is {days_int} days old "
            f"(last update: {last_observation_dt.strftime('%Y-%m-%d %H:%M')}). "
            f"Data older than {FRESHNESS_FRESH_HOURS:.0f} hours is considered stale."
        )
    else:
        status = FreshnessStatus.MISSING
        days_int = int(round(age_days))
        explanation = (
            f"Data is {days_int} days old — too old to be reliable "
            f"(threshold: {FRESHNESS_STALE_HOURS:.0f} hours). "
            f"Last known observation: {last_observation_dt.strftime('%Y-%m-%d')}."
        )

    return {
        "freshness_status":       status,
        "data_age_hours":         round(age_hours, 1),
        "last_observation_time":  last_observation_dt.isoformat(),
        "explanation":            explanation,
    }


def compute_domain_freshness(
    patient_df: pd.DataFrame,
    domain: str,
    reference_dt: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Compute freshness for a specific domain for one patient.

    A domain observation is considered present on a date only if the
    corresponding column has a non-NaN value on that row.

    Args:
        patient_df:   Patient-filtered daily observations, sorted by date.
        domain:       One of "mobility", "nutrition", "participation".
        reference_dt: Reference "now" time.

    Returns:
        Freshness dict (see compute_freshness) plus:
          domain  – domain name
          n_valid_obs – count of non-NaN observations for this domain
    """
    col = DOMAIN_COLUMNS.get(domain)
    if col is None or col not in patient_df.columns:
        return {
            "domain":             domain,
            "freshness_status":   FreshnessStatus.MISSING,
            "data_age_hours":     None,
            "last_observation_time": None,
            "explanation":        f"Domain '{domain}' column not found.",
            "n_valid_obs":        0,
        }

    # Rows where this domain has a valid value
    valid = patient_df[patient_df[col].notna()].copy()
    valid["observation_date"] = pd.to_datetime(valid["observation_date"])

    n_valid = len(valid)

    if n_valid == 0:
        result = compute_freshness(None, reference_dt)
    else:
        last_dt = valid["observation_date"].max()
        # Convert date to datetime at midnight for hour calculation
        if not isinstance(last_dt, datetime):
            last_dt = datetime.combine(last_dt.date(), datetime.min.time())
        result = compute_freshness(last_dt, reference_dt)

    result["domain"]       = domain
    result["n_valid_obs"]  = n_valid
    return result


# ─────────────────────────────────────────────────────────────────
# CONTRADICTORY DATA DETECTION
# ─────────────────────────────────────────────────────────────────

def detect_contradictions(
    patient_df: pd.DataFrame,
    patient_id: str,
) -> Dict[str, Any]:
    """
    Detect contradictory or impossible data for one patient.

    Checks performed:
      1. Duplicate (patient_id, observation_date) pairs
      2. Values outside valid physiological ranges
      3. Negative values in non-negative columns
      4. Future observation timestamps

    Args:
        patient_df: Patient-filtered daily observations.
        patient_id: Patient ID (for logging).

    Returns:
        Dict with:
          has_contradictions – bool
          issues             – list of issue dicts
          affected_columns   – set of column names with issues
          contradiction_count – int
    """
    issues: List[Dict[str, Any]] = []
    affected_columns: set = set()

    if patient_df.empty:
        return {
            "has_contradictions":   False,
            "issues":               [],
            "affected_columns":     set(),
            "contradiction_count":  0,
        }

    now = datetime.now()

    # 1. Duplicate observation dates
    dates = pd.to_datetime(patient_df["observation_date"])
    dup_mask = dates.duplicated(keep=False)
    if dup_mask.any():
        dup_dates = dates[dup_mask].unique().tolist()
        issues.append({
            "type":    "DUPLICATE_DATES",
            "detail":  f"Patient {patient_id} has duplicate observation dates: {dup_dates[:3]}",
            "rows":    int(dup_mask.sum()),
        })
        affected_columns.add("observation_date")

    # 2. Future timestamps
    future_mask = dates > pd.Timestamp(now)
    if future_mask.any():
        issues.append({
            "type":   "FUTURE_TIMESTAMP",
            "detail": f"Patient {patient_id} has {future_mask.sum()} observation(s) with future dates.",
            "rows":   int(future_mask.sum()),
        })
        affected_columns.add("observation_date")

    # 3. Out-of-range / negative values
    for col, (lo, hi) in VALID_RANGES.items():
        if col not in patient_df.columns:
            continue
        col_numeric = pd.to_numeric(patient_df[col], errors="coerce")

        # Negative where not allowed
        neg_mask = col_numeric < 0
        if neg_mask.any():
            issues.append({
                "type":   "NEGATIVE_VALUE",
                "column": col,
                "detail": f"Column '{col}' has {neg_mask.sum()} negative value(s).",
                "rows":   int(neg_mask.sum()),
            })
            affected_columns.add(col)

        # Below minimum (non-negative minimum)
        low_mask = (col_numeric < lo) & col_numeric.notna() & (~neg_mask)
        if low_mask.any():
            issues.append({
                "type":   "BELOW_MINIMUM",
                "column": col,
                "detail": f"Column '{col}' has {low_mask.sum()} value(s) below minimum {lo}.",
                "rows":   int(low_mask.sum()),
            })
            affected_columns.add(col)

        # Above maximum
        high_mask = (col_numeric > hi) & col_numeric.notna()
        if high_mask.any():
            issues.append({
                "type":   "ABOVE_MAXIMUM",
                "column": col,
                "detail": f"Column '{col}' has {high_mask.sum()} value(s) above maximum {hi}.",
                "rows":   int(high_mask.sum()),
            })
            affected_columns.add(col)

    return {
        "has_contradictions":   len(issues) > 0,
        "issues":               issues,
        "affected_columns":     affected_columns,
        "contradiction_count":  len(issues),
    }


# ─────────────────────────────────────────────────────────────────
# MISSING DOMAIN ASSESSMENT
# ─────────────────────────────────────────────────────────────────

def assess_missing_domains(
    patient_df: pd.DataFrame,
    min_recent_obs: int = 3,
) -> Dict[str, Any]:
    """
    Identify which domains have missing recent observations.

    "Missing" here means: fewer than min_recent_obs non-NaN values
    in the most recent min_recent_obs rows.

    Args:
        patient_df:    Patient-filtered daily observations.
        min_recent_obs: Number of recent rows to inspect.

    Returns:
        Dict with:
          missing_domains     – list of domain names with missing data
          present_domains     – list of domain names with sufficient recent data
          partial_domains     – list of domain names with some but insufficient data
          domain_detail       – dict keyed by domain with availability stats
    """
    if patient_df.empty:
        return {
            "missing_domains":  list(DOMAIN_COLUMNS.keys()),
            "present_domains":  [],
            "partial_domains":  [],
            "domain_detail":    {},
        }

    sorted_df = patient_df.sort_values("observation_date").tail(min_recent_obs)

    missing: List[str] = []
    present: List[str] = []
    partial: List[str] = []
    detail:  Dict[str, Any] = {}

    for domain, col in DOMAIN_COLUMNS.items():
        if col not in sorted_df.columns:
            missing.append(domain)
            detail[domain] = {"available": 0, "required": min_recent_obs, "status": "MISSING"}
            continue

        n_avail = int(sorted_df[col].notna().sum())
        detail[domain] = {
            "available":      n_avail,
            "required":       min_recent_obs,
            "coverage_pct":   round(n_avail / min_recent_obs * 100, 0) if min_recent_obs > 0 else 0,
        }

        if n_avail == 0:
            missing.append(domain)
            detail[domain]["status"] = "MISSING"
        elif n_avail < min_recent_obs:
            partial.append(domain)
            detail[domain]["status"] = "PARTIAL"
        else:
            present.append(domain)
            detail[domain]["status"] = "PRESENT"

    return {
        "missing_domains": missing,
        "present_domains": present,
        "partial_domains": partial,
        "domain_detail":   detail,
    }


# ─────────────────────────────────────────────────────────────────
# TRUST / EVIDENCE STATE
# ─────────────────────────────────────────────────────────────────

def compute_trust_state(
    domain_freshness: Dict[str, Dict[str, Any]],
    missing_assessment: Dict[str, Any],
    contradiction_result: Dict[str, Any],
    baseline_insufficiency: Dict[str, bool],
) -> Dict[str, Any]:
    """
    Compute the overall trust / evidence level for a patient assessment.

    Decision table (most-severe condition wins):
      1. DATA_QUALITY_ISSUE      → contradictory data detected
      2. INSUFFICIENT_EVIDENCE   → any critical domain has MISSING freshness,
                                   OR any critical domain has INSUFFICIENT_BASELINE
      3. LOW_CONFIDENCE          → any critical domain has STALE freshness,
                                   OR any critical domain has partial data
      4. MEDIUM_CONFIDENCE       → all domains fresh but ≥1 non-critical concern
      5. HIGH_CONFIDENCE         → all critical domains FRESH and sufficient baseline

    Args:
        domain_freshness:       Dict[domain] → freshness result dict.
        missing_assessment:     Output of assess_missing_domains().
        contradiction_result:   Output of detect_contradictions().
        baseline_insufficiency: Dict[domain] → bool; True if baseline is insufficient.

    Returns:
        Dict with:
          trust_level      – TrustLevel constant
          reasons          – list of reason strings explaining the level
          recommended_action – safe fallback action string
          allow_alert      – bool; False means do not escalate automatically
    """
    reasons: List[str] = []

    # ── Rule 1: Contradictory data ────────────────────────────────
    if contradiction_result.get("has_contradictions", False):
        for issue in contradiction_result.get("issues", []):
            reasons.append(f"Data quality issue: {issue['detail']}")
        return {
            "trust_level":         TrustLevel.DATA_QUALITY_ISSUE,
            "reasons":             reasons,
            "recommended_action":  (
                "Recommendation withheld — source observations are contradictory. "
                "Review raw data before escalating."
            ),
            "allow_alert":         False,
        }

    # ── Rule 2: Missing critical domain data ─────────────────────
    missing_domains = missing_assessment.get("missing_domains", [])
    freshness_missing = [
        d for d, fr in domain_freshness.items()
        if fr.get("freshness_status") == FreshnessStatus.MISSING and d in CRITICAL_DOMAINS
    ]
    critical_missing = list(set(missing_domains + freshness_missing))
    critical_missing = [d for d in critical_missing if d in CRITICAL_DOMAINS]
    critical_insufficient = [
        d for d, insuff in baseline_insufficiency.items()
        if insuff and d in CRITICAL_DOMAINS
    ]

    if critical_missing:
        for d in critical_missing:
            reasons.append(f"Domain '{d}' has no recent observations (MISSING).")
    if critical_insufficient:
        for d in critical_insufficient:
            reasons.append(f"Domain '{d}' has insufficient baseline history.")

    if critical_missing or critical_insufficient:
        return {
            "trust_level":         TrustLevel.INSUFFICIENT_EVIDENCE,
            "reasons":             reasons,
            "recommended_action":  (
                "Insufficient current evidence — collect updated observations "
                "before making any escalation decision."
            ),
            "allow_alert":         False,
        }

    # ── Rule 3: Stale or partial critical domain data ─────────────
    stale_domains = [
        d for d, fr in domain_freshness.items()
        if fr.get("freshness_status") in (FreshnessStatus.STALE,) and d in CRITICAL_DOMAINS
    ]
    partial_domains = missing_assessment.get("partial_domains", [])
    critical_partial = [d for d in partial_domains if d in CRITICAL_DOMAINS]

    if stale_domains or critical_partial:
        for d in stale_domains:
            age = domain_freshness[d].get("data_age_hours", "?")
            reasons.append(f"Domain '{d}' data is STALE ({age} hours old).")
        for d in critical_partial:
            reasons.append(f"Domain '{d}' has only partial recent observations.")
        return {
            "trust_level":         TrustLevel.LOW_CONFIDENCE,
            "reasons":             reasons,
            "recommended_action":  (
                "Low confidence — stale or partial data detected. "
                "Do not escalate automatically. Add to review queue and "
                "collect updated observations."
            ),
            "allow_alert":         False,
        }

    # ── Rule 4: Non-critical concerns ────────────────────────────
    non_critical_stale = [
        d for d, fr in domain_freshness.items()
        if fr.get("freshness_status") == FreshnessStatus.STALE and d not in CRITICAL_DOMAINS
    ]
    if non_critical_stale:
        for d in non_critical_stale:
            reasons.append(f"Non-critical domain '{d}' is STALE.")
        return {
            "trust_level":         TrustLevel.MEDIUM_CONFIDENCE,
            "reasons":             reasons,
            "recommended_action":  (
                "Medium confidence — non-critical data is stale. "
                "Alert may be generated but should be reviewed promptly."
            ),
            "allow_alert":         True,
        }

    # ── Rule 5: All good ─────────────────────────────────────────
    reasons.append("All critical domains have fresh data and sufficient baselines.")
    return {
        "trust_level":         TrustLevel.HIGH_CONFIDENCE,
        "reasons":             reasons,
        "recommended_action":  "Normal detection logic applies.",
        "allow_alert":         True,
    }


# ─────────────────────────────────────────────────────────────────
# FULL DATA QUALITY ASSESSMENT FOR ONE PATIENT
# ─────────────────────────────────────────────────────────────────

def assess_patient_data_quality(
    patient_df: pd.DataFrame,
    patient_id: str,
    baseline_summary: Optional[Dict[str, Any]] = None,
    reference_dt: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Run the complete data quality assessment for one patient.

    Combines freshness, missing-data, contradiction, and baseline checks
    into a single result dict suitable for use by the alert engine and dashboard.

    Args:
        patient_df:       Patient-filtered daily observations.
        patient_id:       Patient ID string.
        baseline_summary: Output of compute_patient_baseline_summary() or None.
        reference_dt:     Reference "now" time.

    Returns:
        Dict with:
          patient_id          – str
          domain_freshness    – dict[domain] → freshness result
          missing_assessment  – dict (see assess_missing_domains)
          contradiction_result – dict (see detect_contradictions)
          baseline_insufficiency – dict[domain] → bool
          trust_state         – dict (see compute_trust_state)
          summary             – one-line human-readable summary
    """
    # Per-domain freshness
    domain_freshness: Dict[str, Dict[str, Any]] = {}
    for domain in DOMAIN_COLUMNS:
        domain_freshness[domain] = compute_domain_freshness(
            patient_df, domain, reference_dt=reference_dt
        )

    # Missing observations
    missing_assessment = assess_missing_domains(patient_df)

    # Contradictions
    contradiction_result = detect_contradictions(patient_df, patient_id)

    # Baseline insufficiency per domain
    baseline_insufficiency: Dict[str, bool] = {}
    if baseline_summary:
        for domain in DOMAIN_COLUMNS:
            domain_data = baseline_summary.get(domain, {})
            baseline_insufficiency[domain] = (
                domain_data.get("baseline_state") == "INSUFFICIENT_BASELINE"
                or domain_data.get("n_valid_obs", 0) < 7
            )
    else:
        # No baseline summary provided — assume insufficient for all domains
        for domain in DOMAIN_COLUMNS:
            baseline_insufficiency[domain] = True

    # Overall trust state
    trust_state = compute_trust_state(
        domain_freshness, missing_assessment, contradiction_result, baseline_insufficiency
    )

    # One-line summary
    tl = trust_state["trust_level"]
    if tl == TrustLevel.HIGH_CONFIDENCE:
        summary = "All data is current and sufficient — normal assessment."
    elif tl == TrustLevel.MEDIUM_CONFIDENCE:
        summary = "Assessment available with reduced confidence (non-critical stale data)."
    elif tl == TrustLevel.LOW_CONFIDENCE:
        summary = "Low confidence — stale or partial data. Do not auto-escalate."
    elif tl == TrustLevel.INSUFFICIENT_EVIDENCE:
        summary = "INSUFFICIENT CURRENT EVIDENCE — collect updated observations before escalation."
    else:  # DATA_QUALITY_ISSUE
        summary = "DATA QUALITY ISSUE — contradictory observations detected. Review required."

    return {
        "patient_id":             patient_id,
        "domain_freshness":       domain_freshness,
        "missing_assessment":     missing_assessment,
        "contradiction_result":   contradiction_result,
        "baseline_insufficiency": baseline_insufficiency,
        "trust_state":            trust_state,
        "summary":                summary,
    }


# ─────────────────────────────────────────────────────────────────
# BACKWARD-COMPATIBLE freshness wrapper (replaces utils.get_freshness_status)
# ─────────────────────────────────────────────────────────────────

def get_freshness_status_hours(
    last_observation_date: Optional[datetime],
) -> Dict[str, str]:
    """
    Drop-in replacement for utils.get_freshness_status using hour-based thresholds.

    Args:
        last_observation_date: Last observation as a datetime, or None.

    Returns:
        Dict with 'status' (FRESH/STALE/MISSING) and 'explanation' keys,
        compatible with the existing dashboard code that calls get_freshness_status.
    """
    result = compute_freshness(last_observation_date)
    return {
        "status":      result["freshness_status"],
        "explanation": result["explanation"],
    }
