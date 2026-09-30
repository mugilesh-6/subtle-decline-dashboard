"""
Regression test suite for subtle decline dashboard edge cases and safety fallbacks.
"""
import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from alert_engine import DeclineDetector
from utils import get_freshness_status
from data_quality import (
    compute_freshness, FreshnessStatus, detect_contradictions,
    compute_trust_state, TrustLevel, DOMAIN_COLUMNS, assess_patient_data_quality,
    assess_missing_domains
)
from baseline import (
    MIN_BASELINE_OBSERVATIONS, BASELINE_WINDOW, compute_patient_baseline_summary,
    INSUFFICIENT_BASELINE
)


class TestRegressionSuite(unittest.TestCase):
    """Regression test cases covering edge conditions, boundaries, and safe fallbacks."""

    def setUp(self):
        self.now = datetime.now()

    def test_1_insufficient_baseline(self):
        """Test insufficient baseline when data length is less than MIN_BASELINE_OBSERVATIONS."""
        short_df = pd.DataFrame({
            'patient_id': ['P_SHORT'] * 5,
            'patient_name': ['Short Patient'] * 5,
            'observation_date': pd.date_range(start=self.now - timedelta(days=4), end=self.now, periods=5),
            'mobility_steps': [5000] * 5,
            'nutrition_kcal': [2000] * 5,
            'participation_minutes': [60] * 5
        })
        detector = DeclineDetector(short_df)
        status = detector.get_patient_current_status('P_SHORT')
        self.assertEqual(status['status'], 'INSUFFICIENT_DATA')
        self.assertIn('No baseline data available', status['message'])

    def test_2_exactly_7_valid_observations(self):
        """Test exactly 7 valid observations allows basic rolling stats computation."""
        df_7 = pd.DataFrame({
            'patient_id': ['P_SEVEN'] * 7,
            'patient_name': ['Seven Patient'] * 7,
            'observation_date': pd.date_range(start=self.now - timedelta(days=6), end=self.now, periods=7),
            'mobility_steps': [5000, 5100, 5200, 5300, 5400, 5500, 5600],
            'nutrition_kcal': [2000] * 7,
            'participation_minutes': [60] * 7
        })
        summary = compute_patient_baseline_summary(df_7, 'P_SEVEN')
        self.assertEqual(summary['mobility']['n_valid_obs'], 7)
        self.assertNotEqual(summary['mobility']['rolling_mean'], INSUFFICIENT_BASELINE)

    def test_3_less_than_7_valid_observations(self):
        """Test less than 7 valid observations returns INSUFFICIENT_BASELINE."""
        df_6 = pd.DataFrame({
            'patient_id': ['P_SIX'] * 6,
            'patient_name': ['Six Patient'] * 6,
            'observation_date': pd.date_range(start=self.now - timedelta(days=5), end=self.now, periods=6),
            'mobility_steps': [5000] * 6,
            'nutrition_kcal': [2000] * 6,
            'participation_minutes': [60] * 6
        })
        summary = compute_patient_baseline_summary(df_6, 'P_SIX')
        self.assertEqual(summary['mobility']['rolling_mean'], INSUFFICIENT_BASELINE)
        self.assertEqual(summary['mobility']['baseline_state'], INSUFFICIENT_BASELINE)

    def test_4_exactly_24_hour_freshness(self):
        """Test exactly 24 hours is classified as FRESH."""
        exact_24h = self.now - timedelta(hours=24)
        status = get_freshness_status(exact_24h)
        self.assertEqual(status['status'], FreshnessStatus.FRESH)

    def test_5_just_above_24_hours(self):
        """Test just above 24 hours (e.g. 24h 5m) is classified as STALE."""
        above_24h = self.now - timedelta(hours=24, minutes=5)
        status = get_freshness_status(above_24h)
        self.assertEqual(status['status'], FreshnessStatus.STALE)

    def test_6_exactly_72_hour_freshness(self):
        """Test exactly 72 hours is classified as STALE."""
        exact_72h = self.now - timedelta(hours=72)
        status = get_freshness_status(exact_72h)
        self.assertEqual(status['status'], FreshnessStatus.STALE)

    def test_7_just_above_72_hours(self):
        """Test just above 72 hours (e.g. 72h 5m) is classified as MISSING."""
        above_72h = self.now - timedelta(hours=72, minutes=5)
        status = get_freshness_status(above_72h)
        self.assertEqual(status['status'], FreshnessStatus.MISSING)

    def test_8_integer_freshness_explanation_formatting(self):
        """Test human-readable freshness explanation does not contain floating point decimals for days."""
        two_days_ago = self.now - timedelta(days=2)
        status = get_freshness_status(two_days_ago)
        self.assertIn("2 days ago", status['explanation'])
        self.assertNotIn("2.0 days", status['explanation'])

    def test_9_missing_domain(self):
        """Test assessment when a critical domain is missing from DataFrame."""
        df_missing_domain = pd.DataFrame({
            'patient_id': ['P_MISSING'] * 10,
            'patient_name': ['Missing Domain Patient'] * 10,
            'observation_date': pd.date_range(start=self.now - timedelta(days=9), end=self.now, periods=10),
            'mobility_steps': [5000] * 10,
            # Missing nutrition_kcal column
            'participation_minutes': [60] * 10
        })
        assessment = assess_missing_domains(df_missing_domain)
        self.assertIn('nutrition', assessment['missing_domains'])

    def test_10_stale_domain(self):
        """Test detection when patient data last update is 3 days old."""
        stale_date = self.now - timedelta(days=3)
        stale_df = pd.DataFrame({
            'patient_id': ['P_STALE'] * 15,
            'patient_name': ['Stale Patient'] * 15,
            'observation_date': pd.date_range(start=stale_date - timedelta(days=14), end=stale_date, periods=15),
            'mobility_steps': [5000] * 15,
            'nutrition_kcal': [2000] * 15,
            'participation_minutes': [60] * 15
        })
        detector = DeclineDetector(stale_df)
        status = detector.get_patient_current_status('P_STALE')
        self.assertEqual(status['status'], 'STALE_DATA')

    def test_11_contradictory_data(self):
        """Test detection of contradictory physiological values (e.g. negative steps)."""
        invalid_df = pd.DataFrame({
            'patient_id': ['P_BAD'] * 10,
            'patient_name': ['Bad Data Patient'] * 10,
            'observation_date': pd.date_range(start=self.now - timedelta(days=9), end=self.now, periods=10),
            'mobility_steps': [5000] * 9 + [-500],  # Negative steps
            'nutrition_kcal': [2000] * 10,
            'participation_minutes': [60] * 10
        })
        contradictions = detect_contradictions(invalid_df, 'P_BAD')
        self.assertTrue(contradictions['has_contradictions'])
        self.assertIn('mobility_steps', contradictions['affected_columns'])

    def test_12_safe_fallback(self):
        """Test that contradictory or missing data prevents high confidence alerts."""
        invalid_df = pd.DataFrame({
            'patient_id': ['P_BAD'] * 10,
            'patient_name': ['Bad Data Patient'] * 10,
            'observation_date': pd.date_range(start=self.now - timedelta(days=9), end=self.now, periods=10),
            'mobility_steps': [5000] * 9 + [-500],  # Negative steps
            'nutrition_kcal': [2000] * 10,
            'participation_minutes': [60] * 10
        })
        quality = assess_patient_data_quality(invalid_df, 'P_BAD')
        self.assertEqual(quality['trust_state']['trust_level'], TrustLevel.DATA_QUALITY_ISSUE)
        self.assertFalse(quality['trust_state']['allow_alert'])


if __name__ == '__main__':
    unittest.main()
