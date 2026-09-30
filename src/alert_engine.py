"""
Alert engine for detecting subtle functional decline in older adults.

Integrates:
  - Formal rolling-window baseline statistics (src/baseline.py)
  - Data quality / freshness / trust-state engine (src/data_quality.py)

Detection logic:
  1. Compute per-patient, per-domain rolling baseline (mean / median / std / z-score).
  2. Assess data quality and freshness.  If trust level does not permit alerting,
     no alert is generated — the system is conservative by design.
  3. Detect sustained decline (configurable consecutive days below z-score threshold).
  4. Build explainable multi-signal alert with full evidence trail.

All thresholds are PROTOTYPE / SYNTHETIC-BENCHMARK values only.
They have NOT been clinically validated.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import json

try:
    from .utils import (
        get_project_root, calculate_percentage_change, classify_severity,
        get_decline_component, create_alert_explanation, safe_numeric,
        load_csv_safely, validate_dataframe
    )
    from .baseline import (
        compute_patient_baseline_summary, compute_all_patient_baselines,
        get_recent_domain_evidence,
        BASELINE_WINDOW, MIN_BASELINE_OBSERVATIONS,
        SUSTAINED_DECLINE_DAYS, Z_SCORE_WARNING_THRESHOLD, Z_SCORE_ALERT_THRESHOLD,
        DOMAIN_COLUMNS, INSUFFICIENT_BASELINE,
    )
    from .data_quality import (
        assess_patient_data_quality, FreshnessStatus, TrustLevel,
        compute_domain_freshness, detect_contradictions,
    )
except ImportError:
    from utils import (
        get_project_root, calculate_percentage_change, classify_severity,
        get_decline_component, create_alert_explanation, safe_numeric,
        load_csv_safely, validate_dataframe
    )
    from baseline import (
        compute_patient_baseline_summary, compute_all_patient_baselines,
        get_recent_domain_evidence,
        BASELINE_WINDOW, MIN_BASELINE_OBSERVATIONS,
        SUSTAINED_DECLINE_DAYS, Z_SCORE_WARNING_THRESHOLD, Z_SCORE_ALERT_THRESHOLD,
        DOMAIN_COLUMNS, INSUFFICIENT_BASELINE,
    )
    from data_quality import (
        assess_patient_data_quality, FreshnessStatus, TrustLevel,
        compute_domain_freshness, detect_contradictions,
    )

# ─────────────────────────────────────────────────────────────────
# MODULE-LEVEL CONFIGURATION
# All prototype thresholds documented here.
# ─────────────────────────────────────────────────────────────────

# Minimum consecutive declining days to trigger an alert
MIN_CONSECUTIVE_DAYS: int = SUSTAINED_DECLINE_DAYS   # default 3

# Domain weights for the composite score (must sum to 1.0)
# Mobility is weighted slightly higher as it is the most direct
# functional measure for fall-risk assessment.
DOMAIN_WEIGHTS: Dict[str, float] = {
    "mobility":      0.40,
    "nutrition":     0.30,
    "participation": 0.30,
}

# Composite score thresholds for severity classification
SEVERITY_THRESHOLDS: Dict[str, float] = {
    "LOW":    0.20,
    "MEDIUM": 0.35,
    "HIGH":   0.50,
}


# ─────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────

def _z_to_composite_component(z_score: Optional[float]) -> float:
    """
    Convert a z-score to a composite decline component in [0, 1].

    Negative z-scores (below baseline) contribute to decline; positive ones
    do not.  The mapping is linear: z = Z_SCORE_ALERT_THRESHOLD → 1.0,
    z = 0 → 0.0.

    Args:
        z_score: Z-score from rolling baseline, or None.

    Returns:
        Float in [0, 1]; 0 if z_score is None or non-negative.
    """
    if z_score is None or z_score >= 0:
        return 0.0
    # Scale: z_alert (-2.0) → 1.0; z between 0 and z_alert → proportional
    # We clamp at 1.0 so very large negative z-scores don't exceed the max.
    component = abs(z_score) / abs(Z_SCORE_ALERT_THRESHOLD)
    return min(component, 1.0)


def _build_domain_evidence(domain_name: str, domain_baseline: Dict[str, Any]) -> Dict[str, Any]:
    """
    Construct the evidence dict for one domain.

    Args:
        domain_name:     "mobility", "nutrition", or "participation".
        domain_baseline: Entry from compute_patient_baseline_summary()[domain].

    Returns:
        Dict suitable for inclusion in an alert's evidence list.
    """
    col = DOMAIN_COLUMNS.get(domain_name, domain_name)
    z = domain_baseline.get("z_score")
    status = domain_baseline.get("decline_status", INSUFFICIENT_BASELINE)

    return {
        "domain":                domain_name,
        "column":                col,
        "current_value":         domain_baseline.get("latest_value"),
        "rolling_mean":          domain_baseline.get("rolling_mean"),
        "rolling_median":        domain_baseline.get("rolling_median"),
        "rolling_std":           domain_baseline.get("rolling_std"),
        "z_score":               z,
        "pct_from_mean":         domain_baseline.get("pct_from_mean"),
        "consecutive_declining": domain_baseline.get("consecutive_declining", 0),
        "is_sustained_decline":  domain_baseline.get("is_sustained_decline", False),
        "decline_status":        status,
        "baseline_state":        domain_baseline.get("baseline_state", INSUFFICIENT_BASELINE),
        "n_valid_obs":           domain_baseline.get("n_valid_obs", 0),
    }


def _compute_composite_score(baseline_summary: Dict[str, Any]) -> float:
    """
    Compute weighted composite decline score from rolling-baseline z-scores.

    Only z-scores indicating decline (negative) contribute.  If a domain's
    baseline is INSUFFICIENT, that domain contributes 0.

    Args:
        baseline_summary: Output of compute_patient_baseline_summary().

    Returns:
        Composite score in [0, 1].
    """
    score = 0.0
    for domain, weight in DOMAIN_WEIGHTS.items():
        domain_data = baseline_summary.get(domain, {})
        z = domain_data.get("z_score")
        score += _z_to_composite_component(z) * weight
    return round(score, 4)


def _classify_alert_severity(composite_score: float) -> str:
    """Map composite score to LOW / MEDIUM / HIGH / NONE severity label."""
    if composite_score >= SEVERITY_THRESHOLDS["HIGH"]:
        return "HIGH"
    if composite_score >= SEVERITY_THRESHOLDS["MEDIUM"]:
        return "MEDIUM"
    if composite_score >= SEVERITY_THRESHOLDS["LOW"]:
        return "LOW"
    return "NONE"


def _build_explanation(
    patient_id: str,
    domain_evidences: List[Dict[str, Any]],
    trust_state: Dict[str, Any],
    composite_score: float,
) -> str:
    """
    Build a human-readable, explainable alert reason.

    Answers: "Why was this patient flagged?"

    Args:
        patient_id:       Patient identifier.
        domain_evidences: List of per-domain evidence dicts.
        trust_state:      Output of compute_trust_state().
        composite_score:  Overall composite decline score.

    Returns:
        Multi-sentence explanation string.
    """
    parts = []
    for ev in domain_evidences:
        domain = ev["domain"]
        z = ev.get("z_score")
        consec = ev.get("consecutive_declining", 0)
        status = ev.get("decline_status", INSUFFICIENT_BASELINE)
        pct = ev.get("pct_from_mean")

        if status == INSUFFICIENT_BASELINE:
            parts.append(f"{domain.capitalize()}: insufficient baseline.")
            continue

        if z is not None and z <= Z_SCORE_ALERT_THRESHOLD:
            pct_str = f" ({pct:+.1f}% from mean)" if pct is not None else ""
            parts.append(
                f"{domain.capitalize()}: z-score {z:.2f}{pct_str} — significant deviation."
            )
        elif status in ("SUSTAINED_DECLINE", "DECLINING"):
            pct_str = f" ({pct:+.1f}% from mean)" if pct is not None else ""
            parts.append(
                f"{domain.capitalize()}: z-score {z:.2f}{pct_str}, "
                f"{consec} consecutive declining observation(s)."
            )

    trust_note = ""
    tl = trust_state.get("trust_level", TrustLevel.INSUFFICIENT_EVIDENCE)
    if tl == TrustLevel.MEDIUM_CONFIDENCE:
        trust_note = " [MEDIUM CONFIDENCE — non-critical stale data present]"
    elif tl == TrustLevel.LOW_CONFIDENCE:
        trust_note = " [LOW CONFIDENCE — stale/partial data]"

    if not parts:
        return f"Composite decline score {composite_score:.3f} from personal rolling baseline.{trust_note}"

    return "; ".join(parts) + f". Composite score: {composite_score:.3f}.{trust_note}"


# ─────────────────────────────────────────────────────────────────
# DECLINE DETECTOR CLASS
# ─────────────────────────────────────────────────────────────────

class DeclineDetector:
    """
    Detects functional decline using patient-specific rolling baselines
    and explicit data quality / trust-state assessment.

    Preserves the original public interface (generate_alerts,
    get_patient_current_status) so existing dashboard code continues
    to work unchanged while gaining the new capabilities.
    """

    def __init__(self, daily_data: pd.DataFrame):
        """
        Initialize the decline detector.

        Args:
            daily_data: DataFrame with daily patient observations.
                        Required columns: patient_id, observation_date,
                        mobility_steps, nutrition_kcal, participation_minutes.
        """
        self.daily_data = daily_data.copy() if daily_data is not None else pd.DataFrame()
        self.alerts: List[Dict[str, Any]] = []

        # Keyed by patient_id
        self._baseline_summaries: Dict[str, Dict[str, Any]] = {}
        self._quality_assessments: Dict[str, Dict[str, Any]] = {}

        # Keep legacy patient_baselines attribute so existing tests still pass
        self.patient_baselines: Dict[str, Dict[str, Any]] = {}

        # Validate input
        required_cols = [
            "patient_id", "observation_date",
            "mobility_steps", "nutrition_kcal", "participation_minutes",
        ]
        validation = validate_dataframe(self.daily_data, required_cols)
        if not validation["valid"]:
            print(f"Warning: Data validation issues: {validation['errors']}")

        self._prepare_data()
        self._compute_baselines()

    # ── private ──────────────────────────────────────────────────

    def _prepare_data(self) -> None:
        """Standardise types and sort order."""
        if self.daily_data.empty:
            return
        self.daily_data["observation_date"] = pd.to_datetime(
            self.daily_data["observation_date"]
        )
        self.daily_data = self.daily_data.sort_values(
            ["patient_id", "observation_date"]
        ).reset_index(drop=True)
        for col in ["mobility_steps", "nutrition_kcal", "participation_minutes"]:
            if col in self.daily_data.columns:
                self.daily_data[col] = pd.to_numeric(self.daily_data[col], errors="coerce")

    def _compute_baselines(self) -> None:
        """Compute rolling baseline summaries for all patients."""
        if self.daily_data.empty:
            return

        all_baselines = compute_all_patient_baselines(self.daily_data)
        self._baseline_summaries = all_baselines

        # Populate legacy patient_baselines dict for backward compatibility
        for pid, summary in all_baselines.items():
            mob  = summary.get("mobility", {})
            nut  = summary.get("nutrition", {})
            part = summary.get("participation", {})

            def _safe_mean(d: Dict) -> Optional[float]:
                v = d.get("rolling_mean")
                if v == INSUFFICIENT_BASELINE or v is None:
                    return None
                return float(v)

            m_mean = _safe_mean(mob)
            n_mean = _safe_mean(nut)
            p_mean = _safe_mean(part)

            # Require valid baseline window (n_valid_obs >= BASELINE_WINDOW) for legacy baseline entries
            m_valid = mob.get("n_valid_obs", 0) >= BASELINE_WINDOW
            n_valid = nut.get("n_valid_obs", 0) >= BASELINE_WINDOW
            p_valid = part.get("n_valid_obs", 0) >= BASELINE_WINDOW

            if m_mean is not None and n_mean is not None and p_mean is not None and m_valid and n_valid and p_valid:
                self.patient_baselines[pid] = {
                    "mobility_baseline":      m_mean,
                    "nutrition_baseline":     n_mean,
                    "participation_baseline": p_mean,
                    "baseline_period":        summary.get("n_observations", 0),
                }

    def _get_quality(self, patient_id: str) -> Dict[str, Any]:
        """Return (cached) data quality assessment for one patient."""
        if patient_id not in self._quality_assessments:
            patient_df = self.daily_data[
                self.daily_data["patient_id"] == patient_id
            ].copy()
            baseline_summary = self._baseline_summaries.get(patient_id)
            self._quality_assessments[patient_id] = assess_patient_data_quality(
                patient_df, patient_id, baseline_summary=baseline_summary
            )
        return self._quality_assessments[patient_id]

    def _should_alert(self, patient_id: str, composite_score: float) -> bool:
        """
        Gate alert generation on trust state and minimum composite score.

        Returns False if:
          - trust state does not allow alerts (stale / missing / contradictory)
          - composite_score is below the LOW severity threshold
        """
        quality = self._get_quality(patient_id)
        trust = quality["trust_state"]
        if not trust.get("allow_alert", False):
            return False
        return composite_score >= SEVERITY_THRESHOLDS["LOW"]

    def _find_first_alert_in_history(
        self, patient_id: str, reference_dt: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        """Find the earliest observation date where sustained decline + trust gating triggered an alert."""
        patient_data = self.daily_data[
            self.daily_data["patient_id"] == patient_id
        ].sort_values("observation_date").reset_index(drop=True)

        if len(patient_data) < MIN_BASELINE_OBSERVATIONS:
            return None

        for i in range(MIN_BASELINE_OBSERVATIONS - 1, len(patient_data)):
            slice_df = patient_data.iloc[:i+1]
            b_summary = compute_patient_baseline_summary(slice_df, patient_id)
            comp_score = _compute_composite_score(b_summary)

            obs_dates = pd.to_datetime(slice_df["observation_date"])
            curr_date = obs_dates.iloc[-1]
            step_ref_dt = (
                reference_dt if reference_dt is not None
                else datetime.combine(curr_date.date(), datetime.min.time())
            )

            quality = assess_patient_data_quality(
                slice_df, patient_id, baseline_summary=b_summary, reference_dt=step_ref_dt
            )
            trust = quality["trust_state"]
            if not trust.get("allow_alert", False) or comp_score < SEVERITY_THRESHOLDS["LOW"]:
                continue

            has_sustained = any(
                b_summary.get(d, {}).get("is_sustained_decline", False)
                for d in DOMAIN_COLUMNS
            )
            if not has_sustained:
                continue

            first_decline_date = curr_date
            max_streak = 0
            for d in DOMAIN_COLUMNS:
                d_data = b_summary.get(d, {})
                streak = d_data.get("consecutive_declining", 0)
                if d_data.get("is_sustained_decline") and streak > 0:
                    max_streak = max(max_streak, streak)
                    candidate = obs_dates.iloc[-streak]
                    if candidate < first_decline_date:
                        first_decline_date = candidate

            domain_evidences = [
                _build_domain_evidence(d, b_summary.get(d, {}))
                for d in DOMAIN_COLUMNS
            ]
            explanation = _build_explanation(
                patient_id, domain_evidences, trust, comp_score
            )
            severity = _classify_alert_severity(comp_score)
            affected_domains = [
                d.capitalize() for d in DOMAIN_COLUMNS
                if b_summary.get(d, {}).get("decline_status") not in (
                    INSUFFICIENT_BASELINE, "STABLE"
                )
            ]
            patient_name_series = patient_data["patient_name"]
            patient_name = patient_name_series.iloc[0] if not patient_name_series.empty else patient_id

            return {
                "alert_id":          f"ALT_{patient_id}_{first_decline_date.strftime('%Y%m%d')}",
                "patient_id":        patient_id,
                "patient_name":      patient_name,
                "decline_start_date": first_decline_date.strftime("%Y-%m-%d"),
                "alert_date":        curr_date.strftime("%Y-%m-%d"),
                "duration_days":     int(max_streak),
                "domains_affected":  ", ".join(affected_domains) if affected_domains else "Multiple",
                "composite_score":   round(comp_score, 3),
                "severity":          severity,
                "mobility_delta":    round(b_summary.get("mobility", {}).get("pct_from_mean") or 0.0, 1),
                "nutrition_delta":   round(b_summary.get("nutrition", {}).get("pct_from_mean") or 0.0, 1),
                "participation_delta": round(b_summary.get("participation", {}).get("pct_from_mean") or 0.0, 1),
                "explanation":       explanation,
                "status":            "ACTIVE",
                "created_at":        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "trust_level":       trust.get("trust_level", TrustLevel.INSUFFICIENT_EVIDENCE),
                "domain_evidence":   domain_evidences,
                "data_quality_summary": quality.get("summary", ""),
            }

        return None

    # ── public interface (preserves original API) ─────────────────

    def generate_alerts(self, reference_dt: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Generate alerts for all patients.

        Args:
            reference_dt: Optional reference datetime for data freshness assessment.

        Returns:
            List of alert dicts. Alerts are only generated when the trust
            state permits it (i.e. data is fresh and sufficient).
        """
        if self.daily_data.empty:
            print("Warning: No daily data available for alert generation")
            return []

        all_alerts: List[Dict[str, Any]] = []

        for patient_id in self.daily_data["patient_id"].unique():
            alert = self._find_first_alert_in_history(patient_id, reference_dt=reference_dt)
            if alert:
                all_alerts.append(alert)

        self.alerts = all_alerts
        return all_alerts

    def get_patient_current_status(self, patient_id: str) -> Dict[str, Any]:
        """
        Get current status for a specific patient.

        Preserved public API — extended with rolling-baseline and quality data.

        Returns:
            Dict.  Key 'status' is one of:
              'CURRENT'           – fresh data, baseline available
              'STALE_DATA'        – last observation is stale
              'NO_DATA'           – no observations at all
              'INSUFFICIENT_DATA' – insufficient baseline history
        """
        if self.daily_data.empty:
            return {"status": "NO_DATA", "message": "No observation data available"}

        if patient_id not in self._baseline_summaries or patient_id not in self.patient_baselines:
            return {"status": "INSUFFICIENT_DATA", "message": "No baseline data available"}

        patient_data = self.daily_data[
            self.daily_data["patient_id"] == patient_id
        ].sort_values("observation_date")

        if patient_data.empty:
            return {"status": "NO_DATA", "message": "No observation data available"}

        recent_obs = patient_data.iloc[-1].to_dict()
        last_obs_date = pd.to_datetime(recent_obs["observation_date"])
        days_since = (datetime.now() - last_obs_date).days

        if days_since > 1:
            return {
                "status":                "STALE_DATA",
                "message":               f"Data is {days_since} days old",
                "last_observation_date": str(recent_obs["observation_date"])[:10],
            }

        baseline_summary = self._baseline_summaries[patient_id]
        
        # Check if baseline data for any domain is insufficient
        insufficient = False
        for domain in DOMAIN_COLUMNS:
            d_info = baseline_summary.get(domain, {})
            if d_info.get("rolling_mean") == INSUFFICIENT_BASELINE or d_info.get("n_valid_obs", 0) < MIN_BASELINE_OBSERVATIONS:
                insufficient = True
                break
        if insufficient:
            return {"status": "INSUFFICIENT_DATA", "message": "No baseline data available"}

        quality = self._get_quality(patient_id)
        composite_score = _compute_composite_score(baseline_summary)

        # Build per-domain readable values from legacy structure (for existing dashboard)
        def _val(domain: str, key: str, fallback: float = 0.0) -> float:
            v = baseline_summary.get(domain, {}).get(key)
            if v is None or v == INSUFFICIENT_BASELINE:
                return fallback
            return float(v)

        return {
            "status":                "CURRENT",
            "patient_id":            patient_id,
            "last_observation_date": str(recent_obs["observation_date"])[:10],
            "days_since_observation": days_since,
            "current_values": {
                "mobility_steps":        recent_obs.get("mobility_steps"),
                "nutrition_kcal":        recent_obs.get("nutrition_kcal"),
                "participation_minutes": recent_obs.get("participation_minutes"),
            },
            "baseline_values": {
                "mobility_baseline":      _val("mobility",      "rolling_mean"),
                "nutrition_baseline":     _val("nutrition",     "rolling_mean"),
                "participation_baseline": _val("participation", "rolling_mean"),
            },
            "percentage_changes": {
                "mobility_delta":      _val("mobility",      "pct_from_mean"),
                "nutrition_delta":     _val("nutrition",     "pct_from_mean"),
                "participation_delta": _val("participation", "pct_from_mean"),
            },
            "composite_score":  round(composite_score, 3),
            "risk_level":       _classify_alert_severity(composite_score),
            # New fields
            "baseline_summary": baseline_summary,
            "data_quality":     quality,
            "trust_level":      quality["trust_state"].get("trust_level"),
        }

    def get_patient_drill_down(self, patient_id: str) -> Dict[str, Any]:
        """
        Return full drill-down evidence for one patient.

        Used by the dashboard evidence panel to answer "Why was this patient flagged?"

        Returns:
            Dict with per-domain stats, recent history, quality assessment,
            and trust state.
        """
        baseline_summary = self._baseline_summaries.get(patient_id, {})
        quality = self._get_quality(patient_id)
        patient_data = self.daily_data[
            self.daily_data["patient_id"] == patient_id
        ].sort_values("observation_date")

        domain_drill: Dict[str, Any] = {}
        for domain, col in DOMAIN_COLUMNS.items():
            d_data = baseline_summary.get(domain, {})
            hist = d_data.get("stats_history")
            obs_dates = patient_data["observation_date"]

            recent_history: List[Dict[str, Any]] = []
            if hist is not None and not hist.empty:
                recent_history = get_recent_domain_evidence(hist, obs_dates, n_recent=7)

            domain_drill[domain] = {
                "current_value":         d_data.get("latest_value"),
                "rolling_mean":          d_data.get("rolling_mean"),
                "rolling_median":        d_data.get("rolling_median"),
                "rolling_std":           d_data.get("rolling_std"),
                "z_score":               d_data.get("z_score"),
                "pct_from_mean":         d_data.get("pct_from_mean"),
                "consecutive_declining": d_data.get("consecutive_declining", 0),
                "is_sustained_decline":  d_data.get("is_sustained_decline", False),
                "decline_status":        d_data.get("decline_status", INSUFFICIENT_BASELINE),
                "baseline_state":        d_data.get("baseline_state", INSUFFICIENT_BASELINE),
                "n_valid_obs":           d_data.get("n_valid_obs", 0),
                "freshness":             quality.get("domain_freshness", {}).get(domain, {}),
                "recent_history":        recent_history,
            }

        return {
            "patient_id":     patient_id,
            "domain_drill":   domain_drill,
            "data_quality":   quality,
            "trust_state":    quality["trust_state"],
            "composite_score": _compute_composite_score(baseline_summary),
        }


# ─────────────────────────────────────────────────────────────────
# MAIN — batch alert generation
# ─────────────────────────────────────────────────────────────────

def main() -> List[Dict[str, Any]]:
    """Run alert generation and save results."""
    print("Running decline detection and alert generation...")

    project_root = get_project_root()
    data_dir     = project_root / "data"

    daily_data = load_csv_safely(data_dir / "synthetic_daily_data.csv")
    if daily_data is None:
        print(f"Error: Could not load daily data from {data_dir / 'synthetic_daily_data.csv'}")
        return []

    detector = DeclineDetector(daily_data)
    alerts   = detector.generate_alerts()

    alerts_file = data_dir / "generated_alerts.csv"
    if alerts:
        alerts_df = pd.DataFrame(alerts)
        # Drop non-serialisable nested columns before CSV write
        csv_cols = [c for c in alerts_df.columns if c not in ("domain_evidence",)]
        alerts_df[csv_cols].to_csv(alerts_file, index=False)
        print(f"[OK] Generated {len(alerts)} alerts -> {alerts_file}")
    else:
        empty_df = pd.DataFrame(columns=[
            "alert_id", "patient_id", "patient_name", "decline_start_date",
            "alert_date", "duration_days", "domains_affected", "composite_score",
            "severity", "mobility_delta", "nutrition_delta", "participation_delta",
            "explanation", "status", "created_at", "trust_level",
            "data_quality_summary",
        ])
        empty_df.to_csv(alerts_file, index=False)
        print(f"[OK] No alerts generated -> created empty {alerts_file}")

    print(f"\nAlert Generation Summary:")
    print(f"  Total patients processed : {daily_data['patient_id'].nunique()}")
    print(f"  Patients with baselines  : {len(detector._baseline_summaries)}")
    print(f"  Total alerts generated   : {len(alerts)}")
    if alerts:
        from collections import Counter
        counts = Counter(a["severity"] for a in alerts)
        for sev, cnt in counts.items():
            print(f"    {sev}: {cnt}")

    return alerts


if __name__ == "__main__":
    main()
