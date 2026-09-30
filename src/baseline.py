"""
Formal patient-specific baseline engine for the Subtle Decline Dashboard.

Implements rolling-window statistical baselines per patient per domain:
  - Rolling mean, median, standard deviation
  - Z-score calculation with zero-std safety handling
  - Sustained decline detection over configurable windows
  - Explicit INSUFFICIENT_BASELINE markers when data is inadequate

All thresholds are PROTOTYPE / SYNTHETIC-BENCHMARK values only.
They have NOT been clinically validated and should not be used for
real clinical decision-making without expert review.

Mathematical formulas used:
  rolling_mean_t   = mean(x[t-window+1 : t])
  rolling_median_t = median(x[t-window+1 : t])
  rolling_std_t    = std(x[t-window+1 : t], ddof=1)
  z_score_t        = (x_t - rolling_mean_t) / rolling_std_t
                     (safe: returns None when std == 0 or data insufficient)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple


# ─────────────────────────────────────────────────────────────────
# CONFIGURATION — all prototype thresholds in one place
# Change these values here; they propagate throughout the system.
# ─────────────────────────────────────────────────────────────────

# Rolling window for baseline statistics (number of observations)
BASELINE_WINDOW: int = 14

# Minimum observations required before a rolling stat is trusted
MIN_BASELINE_OBSERVATIONS: int = 7

# Number of consecutive below-baseline observations to confirm sustained decline
SUSTAINED_DECLINE_DAYS: int = 3

# Z-score thresholds (negative = below baseline = potential decline)
# WARNING: deviation worth monitoring but not yet actionable
# ALERT:   statistically significant deviation from personal baseline
Z_SCORE_WARNING_THRESHOLD: float = -1.0   # prototype value
Z_SCORE_ALERT_THRESHOLD: float   = -2.0   # prototype value

# Domains tracked by this system
DOMAINS: List[str] = ["mobility", "nutrition", "participation"]

# Mapping from domain name to raw column name in daily_data DataFrame
DOMAIN_COLUMNS: Dict[str, str] = {
    "mobility":      "mobility_steps",
    "nutrition":     "nutrition_kcal",
    "participation": "participation_minutes",
}

# Sentinel returned when a baseline stat cannot be computed
INSUFFICIENT_BASELINE: str = "INSUFFICIENT_BASELINE"


# ─────────────────────────────────────────────────────────────────
# ROLLING STATISTICS
# ─────────────────────────────────────────────────────────────────

def rolling_mean(values: pd.Series, window: int = BASELINE_WINDOW) -> pd.Series:
    """
    Compute rolling mean over a fixed window.

    Uses min_periods = MIN_BASELINE_OBSERVATIONS so the first valid value
    appears only after MIN_BASELINE_OBSERVATIONS observations are available.

    Args:
        values: Numeric series sorted oldest-to-newest.
        window: Look-back window size.

    Returns:
        Series of rolling means; NaN where insufficient data.
    """
    return values.rolling(window=window, min_periods=MIN_BASELINE_OBSERVATIONS).mean()


def rolling_median(values: pd.Series, window: int = BASELINE_WINDOW) -> pd.Series:
    """
    Compute rolling median over a fixed window.

    The median is less sensitive to occasional extreme outliers than the mean,
    making it useful as a robustness check alongside the mean.

    Args:
        values: Numeric series sorted oldest-to-newest.
        window: Look-back window size.

    Returns:
        Series of rolling medians; NaN where insufficient data.
    """
    return values.rolling(window=window, min_periods=MIN_BASELINE_OBSERVATIONS).median()


def rolling_std(values: pd.Series, window: int = BASELINE_WINDOW) -> pd.Series:
    """
    Compute rolling standard deviation (ddof=1, sample std) over a fixed window.

    ddof=1 is used so the estimate is unbiased for a finite sample.

    Args:
        values: Numeric series sorted oldest-to-newest.
        window: Look-back window size.

    Returns:
        Series of rolling std deviations; NaN where insufficient data.
    """
    return values.rolling(window=window, min_periods=MIN_BASELINE_OBSERVATIONS).std(ddof=1)


def compute_z_score(current_value: float, mean_val: float, std_val: float) -> Optional[float]:
    """
    Compute a single z-score safely.

    z = (x - mean) / std

    Returns None (never 0.0) when:
      - std_val is 0 (division would be undefined)
      - std_val is NaN (insufficient observations)
      - current_value or mean_val is NaN

    This explicit None signals INSUFFICIENT_BASELINE to the caller
    rather than silently producing a misleading 0.0.

    Args:
        current_value: The observation to score.
        mean_val:       Rolling mean at this time step.
        std_val:        Rolling std at this time step.

    Returns:
        Z-score float, or None if mathematically undefined.
    """
    if any(v is None or (isinstance(v, float) and np.isnan(v))
           for v in [current_value, mean_val, std_val]):
        return None
    # WHY: Zero variance means all values in the baseline window were identical.
    # In this case, z-score is mathematically undefined (0/0). Returning None
    # prevents generating false zero-z-scores that could mask actual deviations.
    if std_val == 0.0:
        return None   # Zero variance → z-score is undefined, not 0
    return (current_value - mean_val) / std_val


# ─────────────────────────────────────────────────────────────────
# PER-PATIENT, PER-DOMAIN BASELINE STATISTICS
# ─────────────────────────────────────────────────────────────────

def compute_patient_domain_stats(
    patient_series: pd.Series,
    window: int = BASELINE_WINDOW,
) -> pd.DataFrame:
    """
    Compute the full rolling-baseline table for one patient's single domain.

    Each row corresponds to one observation date and contains:
      value          – raw observation
      rolling_mean   – rolling mean over the window ending at this row
      rolling_median – rolling median
      rolling_std    – rolling sample standard deviation
      z_score        – (value - rolling_mean) / rolling_std; None if undefined
      pct_from_mean  – percentage deviation from rolling mean
      baseline_state – "OK" or INSUFFICIENT_BASELINE sentinel

    Args:
        patient_series: Raw domain values, indexed by observation_date,
                        sorted oldest-to-newest, NaN for missing observations.
        window:         Rolling window size.

    Returns:
        DataFrame with one row per observation.
    """
    values = patient_series.astype(float)

    r_mean   = rolling_mean(values, window)
    r_median = rolling_median(values, window)
    r_std    = rolling_std(values, window)

    z_scores: List[Optional[float]] = []
    pct_devs: List[Optional[float]] = []
    baseline_states: List[str] = []

    for i in range(len(values)):
        v    = values.iloc[i]
        m    = r_mean.iloc[i]
        s    = r_std.iloc[i]

        if pd.isna(v) or pd.isna(m):
            z_scores.append(None)
            pct_devs.append(None)
            baseline_states.append(INSUFFICIENT_BASELINE)
        else:
            z = compute_z_score(float(v), float(m), float(s) if not pd.isna(s) else float('nan'))
            z_scores.append(z)
            pct = ((v - m) / m * 100) if m != 0 else None
            pct_devs.append(float(pct) if pct is not None else None)
            state = "OK" if z is not None else INSUFFICIENT_BASELINE
            baseline_states.append(state)

    return pd.DataFrame({
        "value":          values.values,
        "rolling_mean":   r_mean.values,
        "rolling_median": r_median.values,
        "rolling_std":    r_std.values,
        "z_score":        z_scores,
        "pct_from_mean":  pct_devs,
        "baseline_state": baseline_states,
    }, index=patient_series.index)


# ─────────────────────────────────────────────────────────────────
# SUSTAINED DECLINE DETECTION
# ─────────────────────────────────────────────────────────────────

def detect_sustained_decline(
    stats_df: pd.DataFrame,
    sustained_days: int = SUSTAINED_DECLINE_DAYS,
    z_warning: float = Z_SCORE_WARNING_THRESHOLD,
) -> Dict[str, Any]:
    """
    Detect whether the most recent observations show a sustained decline.

    A "declining observation" is one where:
      - z_score is not None, AND
      - z_score <= z_warning threshold

    A "sustained decline" is N or more consecutive declining observations
    ending at the most recent valid data point.

    Args:
        stats_df:      Output of compute_patient_domain_stats().
        sustained_days: Minimum consecutive declining observations.
        z_warning:     Z-score threshold below which a value counts as declining.

    Returns:
        Dict with keys:
          is_sustained_decline  – bool
          consecutive_count     – int (declining observations at end of series)
          z_score_latest        – float or None
          mean_z_score_recent   – float or None (mean z over recent declining streak)
          decline_start_index   – int or None (index of first declining obs in streak)
          insufficient_baseline – bool (True if latest obs has no valid z-score)
    """
    result: Dict[str, Any] = {
        "is_sustained_decline":  False,
        "consecutive_count":     0,
        "z_score_latest":        None,
        "mean_z_score_recent":   None,
        "decline_start_index":   None,
        "insufficient_baseline": False,
    }

    if stats_df.empty:
        return result

    # Work with rows that have a valid z-score (non-null value and sufficient baseline)
    valid_rows = stats_df[stats_df["z_score"].notna()].copy()

    if valid_rows.empty:
        result["insufficient_baseline"] = True
        return result

    latest_z = valid_rows["z_score"].iloc[-1]
    result["z_score_latest"] = float(latest_z)

    # Count consecutive declining observations from the end
    z_values = valid_rows["z_score"].tolist()
    count = 0
    for z in reversed(z_values):
        if z <= z_warning:
            count += 1
        else:
            break

    result["consecutive_count"] = count

    if count >= sustained_days:
        result["is_sustained_decline"] = True
        recent_streak = z_values[-count:]
        result["mean_z_score_recent"] = float(np.mean(recent_streak))
        # Map back to position in the original stats_df index
        streak_start_pos = len(valid_rows) - count
        if streak_start_pos >= 0:
            result["decline_start_index"] = int(valid_rows.index[streak_start_pos])

    return result


# ─────────────────────────────────────────────────────────────────
# DECLINE STATUS CLASSIFIER
# ─────────────────────────────────────────────────────────────────

def classify_domain_decline_status(
    z_score: Optional[float],
    consecutive_count: int,
    is_sustained: bool,
    baseline_state: str,
) -> str:
    """
    Return a human-readable decline status label for a single domain.

    Possible statuses (ordered from most severe):
      SIGNIFICANT_DEVIATION  – z < Z_SCORE_ALERT_THRESHOLD
      SUSTAINED_DECLINE      – sustained_days+ consecutive below-warning z-scores
      DECLINING              – z < Z_SCORE_WARNING_THRESHOLD (but not yet sustained)
      STABLE                 – z >= Z_SCORE_WARNING_THRESHOLD
      INSUFFICIENT_BASELINE  – cannot assess (insufficient data)

    Args:
        z_score:          Latest z-score, or None.
        consecutive_count: Consecutive below-warning observations.
        is_sustained:     Whether sustained decline was detected.
        baseline_state:   "OK" or INSUFFICIENT_BASELINE.

    Returns:
        Status string.
    """
    if baseline_state == INSUFFICIENT_BASELINE or z_score is None:
        return INSUFFICIENT_BASELINE

    if z_score <= Z_SCORE_ALERT_THRESHOLD:
        return "SIGNIFICANT_DEVIATION"

    if is_sustained:
        return "SUSTAINED_DECLINE"

    if z_score <= Z_SCORE_WARNING_THRESHOLD:
        return "DECLINING"

    return "STABLE"


# ─────────────────────────────────────────────────────────────────
# FULL PATIENT BASELINE SUMMARY
# ─────────────────────────────────────────────────────────────────

def compute_patient_baseline_summary(
    patient_df: pd.DataFrame,
    patient_id: str,
    window: int = BASELINE_WINDOW,
    sustained_days: int = SUSTAINED_DECLINE_DAYS,
) -> Dict[str, Any]:
    """
    Compute the complete rolling-baseline summary for one patient across all domains.

    This is the main entry point called by alert_engine and dashboard.

    Args:
        patient_df:    Subset of daily_data for this patient only,
                       sorted oldest-to-newest, 'observation_date' as a column.
        patient_id:    Patient ID string.
        window:        Rolling baseline window size.
        sustained_days: Min consecutive observations to confirm sustained decline.

    Returns:
        Dict keyed by domain name (mobility / nutrition / participation), each
        containing:
          domain           – str
          column           – raw DataFrame column name
          latest_value     – float or None
          rolling_mean     – float or INSUFFICIENT_BASELINE
          rolling_median   – float or INSUFFICIENT_BASELINE
          rolling_std      – float or INSUFFICIENT_BASELINE
          z_score          – float or None
          pct_from_mean    – float or None
          consecutive_declining – int
          is_sustained_decline  – bool
          decline_status   – status string
          baseline_state   – "OK" or INSUFFICIENT_BASELINE
          n_valid_obs      – int (total non-NaN observations available)
          stats_history    – DataFrame (full rolling stats table for this domain)

        Plus top-level keys:
          patient_id       – str
          n_observations   – int (total rows for this patient)
          window_used      – int
    """
    result: Dict[str, Any] = {
        "patient_id":     patient_id,
        "n_observations": len(patient_df),
        "window_used":    window,
    }

    # Sort chronologically
    pdata = patient_df.sort_values("observation_date").reset_index(drop=True)

    for domain, col in DOMAIN_COLUMNS.items():
        domain_result: Dict[str, Any] = {
            "domain":  domain,
            "column":  col,
            "latest_value":          None,
            "rolling_mean":          INSUFFICIENT_BASELINE,
            "rolling_median":        INSUFFICIENT_BASELINE,
            "rolling_std":           INSUFFICIENT_BASELINE,
            "z_score":               None,
            "pct_from_mean":         None,
            "consecutive_declining": 0,
            "is_sustained_decline":  False,
            "decline_status":        INSUFFICIENT_BASELINE,
            "baseline_state":        INSUFFICIENT_BASELINE,
            "n_valid_obs":           0,
            "stats_history":         pd.DataFrame(),
        }

        if col not in pdata.columns:
            result[domain] = domain_result
            continue

        series = pd.to_numeric(pdata[col], errors="coerce")
        n_valid = int(series.notna().sum())
        domain_result["n_valid_obs"] = n_valid

        if n_valid < MIN_BASELINE_OBSERVATIONS:
            result[domain] = domain_result
            continue

        # Compute rolling stats table
        stats_history = compute_patient_domain_stats(series, window=window)
        domain_result["stats_history"] = stats_history

        # Latest row
        last_stats = stats_history.iloc[-1]
        latest_val = last_stats["value"]
        latest_mean = last_stats["rolling_mean"]
        latest_median = last_stats["rolling_median"]
        latest_std = last_stats["rolling_std"]
        latest_z = last_stats["z_score"]
        latest_pct = last_stats["pct_from_mean"]
        latest_state = last_stats["baseline_state"]

        domain_result["latest_value"] = (
            float(latest_val) if not pd.isna(latest_val) else None
        )
        domain_result["rolling_mean"] = (
            round(float(latest_mean), 2)
            if not pd.isna(latest_mean) else INSUFFICIENT_BASELINE
        )
        domain_result["rolling_median"] = (
            round(float(latest_median), 2)
            if not pd.isna(latest_median) else INSUFFICIENT_BASELINE
        )
        domain_result["rolling_std"] = (
            round(float(latest_std), 2)
            if (latest_std is not None and not pd.isna(latest_std))
            else INSUFFICIENT_BASELINE
        )
        domain_result["z_score"] = (
            round(float(latest_z), 3) if latest_z is not None else None
        )
        domain_result["pct_from_mean"] = (
            round(float(latest_pct), 1) if latest_pct is not None else None
        )
        domain_result["baseline_state"] = latest_state

        # Sustained decline
        sustained = detect_sustained_decline(
            stats_history, sustained_days=sustained_days, z_warning=Z_SCORE_WARNING_THRESHOLD
        )
        domain_result["consecutive_declining"] = sustained["consecutive_count"]
        domain_result["is_sustained_decline"]  = sustained["is_sustained_decline"]

        domain_result["decline_status"] = classify_domain_decline_status(
            z_score=latest_z,
            consecutive_count=sustained["consecutive_count"],
            is_sustained=sustained["is_sustained_decline"],
            baseline_state=latest_state,
        )

        result[domain] = domain_result

    return result


# ─────────────────────────────────────────────────────────────────
# BATCH COMPUTATION FOR ALL PATIENTS
# ─────────────────────────────────────────────────────────────────

def compute_all_patient_baselines(
    daily_data: pd.DataFrame,
    window: int = BASELINE_WINDOW,
    sustained_days: int = SUSTAINED_DECLINE_DAYS,
) -> Dict[str, Dict[str, Any]]:
    """
    Compute baseline summaries for every patient in daily_data.

    Args:
        daily_data:    Full daily observations DataFrame.
        window:        Rolling baseline window.
        sustained_days: Consecutive observations for sustained decline.

    Returns:
        Dict mapping patient_id → baseline summary dict (see compute_patient_baseline_summary).
    """
    if daily_data is None or daily_data.empty:
        return {}

    all_baselines: Dict[str, Dict[str, Any]] = {}

    for patient_id in daily_data["patient_id"].unique():
        patient_df = daily_data[daily_data["patient_id"] == patient_id].copy()
        summary = compute_patient_baseline_summary(
            patient_df, patient_id, window=window, sustained_days=sustained_days
        )
        all_baselines[patient_id] = summary

    return all_baselines


# ─────────────────────────────────────────────────────────────────
# RECENT HISTORY HELPER (for drill-down evidence panel)
# ─────────────────────────────────────────────────────────────────

def get_recent_domain_evidence(
    stats_df: pd.DataFrame,
    observation_dates: pd.Index,
    n_recent: int = 7,
) -> List[Dict[str, Any]]:
    """
    Return the most recent N rows of rolling stats as a list of dicts.

    Used by the dashboard drill-down panel to show the evidence trail.

    Args:
        stats_df:          Output of compute_patient_domain_stats().
        observation_dates: Corresponding observation dates (same length as stats_df).
        n_recent:          Number of recent observations to return.

    Returns:
        List of dicts, newest first, each with:
          date, value, rolling_mean, rolling_std, z_score, baseline_state
    """
    if stats_df.empty:
        return []

    recent = stats_df.tail(n_recent).copy()
    dates_tail = observation_dates[-len(recent):]

    rows = []
    for i, (_, row) in enumerate(recent.iterrows()):
        rows.append({
            "date":          str(dates_tail.iloc[i])[:10] if hasattr(dates_tail, 'iloc') else str(dates_tail[i])[:10],
            "value":         row["value"] if not pd.isna(row["value"]) else None,
            "rolling_mean":  round(row["rolling_mean"], 1) if not pd.isna(row["rolling_mean"]) else None,
            "rolling_std":   round(row["rolling_std"], 1)  if (row["rolling_std"] is not None and not pd.isna(row["rolling_std"])) else None,
            "z_score":       round(row["z_score"], 2) if row["z_score"] is not None else None,
            "baseline_state": row["baseline_state"],
        })

    return list(reversed(rows))  # Newest first
