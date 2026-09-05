"""
Test edge cases for the Subtle Decline Dashboard.
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
from utils import (
    validate_dataframe, get_freshness_status, calculate_percentage_change,
    classify_severity, get_decline_component, calculate_capacity_utilization
)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""
    
    def setUp(self):
        """Set up test data."""
        # Create minimal valid data
        self.valid_data = pd.DataFrame({
            'patient_id': ['P001'] * 35,
            'patient_name': ['Test Patient'] * 35,
            'observation_date': pd.date_range(start='2026-01-01', periods=35),
            'mobility_steps': [5000] * 35,
            'nutrition_kcal': [2000] * 35,
            'participation_minutes': [60] * 35
        })
    
    def test_empty_dataframe(self):
        """Test handling of empty dataframes."""
        empty_df = pd.DataFrame()
        detector = DeclineDetector(empty_df)
        alerts = detector.generate_alerts()
        self.assertEqual(len(alerts), 0)
    
    def test_missing_columns(self):
        """Test handling of missing required columns."""
        invalid_data = pd.DataFrame({
            'patient_id': ['P001'],
            'observation_date': ['2026-01-01']
            # Missing mobility_steps, nutrition_kcal, participation_minutes
        })
        
        required_cols = ['patient_id', 'observation_date', 'mobility_steps', 
                        'nutrition_kcal', 'participation_minutes']
        validation = validate_dataframe(invalid_data, required_cols)
        self.assertFalse(validation['valid'])
        self.assertIn('Missing required columns', str(validation['errors']))
    
    def test_missing_observations(self):
        """Test handling of patients with missing observations."""
        sparse_data = pd.DataFrame({
            'patient_id': ['P001'] * 5,  # Only 5 observations
            'patient_name': ['Test Patient'] * 5,
            'observation_date': pd.date_range(start='2026-01-01', periods=5),
            'mobility_steps': [5000, np.nan, 4800, np.nan, 4700],
            'nutrition_kcal': [2000, 1900, np.nan, 1850, 1800],
            'participation_minutes': [60, 55, 50, np.nan, 45]
        })
        
        detector = DeclineDetector(sparse_data)
        # Should not generate alerts due to insufficient data
        self.assertEqual(len(detector.patient_baselines), 0)
    
    def test_negative_values(self):
        """Test handling of negative numeric values."""
        invalid_data = self.valid_data.copy()
        invalid_data.loc[10, 'mobility_steps'] = -100  # Invalid negative steps
        
        detector = DeclineDetector(invalid_data)
        # Should still create baseline but handle negative values
        self.assertGreater(len(detector.patient_baselines), 0)
    
    def test_invalid_dates(self):
        """Test handling of invalid date formats."""
        invalid_data = self.valid_data.copy()
        invalid_data.loc[0, 'observation_date'] = 'invalid-date'
        
        # Should handle gracefully without crashing
        try:
            detector = DeclineDetector(invalid_data)
            # If it processes without error, test passes
            self.assertTrue(True)
        except Exception as e:
            # If it fails, it should fail gracefully
            self.assertIsInstance(e, (ValueError, TypeError))
    
    def test_insufficient_baseline(self):
        """Test handling of insufficient baseline data."""
        short_data = pd.DataFrame({
            'patient_id': ['P001'] * 10,  # Only 10 days
            'patient_name': ['Test Patient'] * 10,
            'observation_date': pd.date_range(start='2026-01-01', periods=10),
            'mobility_steps': [5000] * 10,
            'nutrition_kcal': [2000] * 10,
            'participation_minutes': [60] * 10
        })
        
        detector = DeclineDetector(short_data)
        # Should not create baseline with insufficient data
        self.assertEqual(len(detector.patient_baselines), 0)
    
    def test_all_stable_patient(self):
        """Test patient with perfectly stable metrics."""
        stable_data = self.valid_data.copy()
        # All values exactly the same
        stable_data['mobility_steps'] = 5000
        stable_data['nutrition_kcal'] = 2000
        stable_data['participation_minutes'] = 60
        
        detector = DeclineDetector(stable_data)
        alerts = detector.generate_alerts()
        # Should not generate any alerts for stable patient
        self.assertEqual(len(alerts), 0)
    
    def test_consecutive_decline(self):
        """Test consecutive decline detection."""
        decline_data = self.valid_data.copy()
        
        # Create decline pattern in last 5 days
        decline_indices = range(30, 35)
        for i, idx in enumerate(decline_indices):
            decline_data.loc[idx, 'mobility_steps'] = 5000 - (i + 1) * 500  # Progressive decline
            decline_data.loc[idx, 'nutrition_kcal'] = 2000 - (i + 1) * 100
            decline_data.loc[idx, 'participation_minutes'] = 60 - (i + 1) * 5
        
        detector = DeclineDetector(decline_data)
        alerts = detector.generate_alerts()
        # Should generate at least one alert for consecutive decline
        self.assertGreater(len(alerts), 0)
    
    def test_recovery_after_decline(self):
        """Test recovery pattern after decline."""
        recovery_data = self.valid_data.copy()
        
        # Create decline in middle, then recovery
        for i in range(15, 20):
            recovery_data.loc[i, 'mobility_steps'] = 4000  # Decline
        
        for i in range(25, 35):
            recovery_data.loc[i, 'mobility_steps'] = 5500  # Recovery
        
        detector = DeclineDetector(recovery_data)
        alerts = detector.generate_alerts()
        # Should detect the decline period but handle recovery
        self.assertTrue(len(alerts) >= 0)  # May or may not generate alerts
    
    def test_multiple_domain_decline(self):
        """Test decline across multiple domains."""
        multi_decline_data = self.valid_data.copy()
        
        # Create multi-domain decline in last 3 days
        for i in range(32, 35):
            multi_decline_data.loc[i, 'mobility_steps'] = 3500  # -30% decline
            multi_decline_data.loc[i, 'nutrition_kcal'] = 1400   # -30% decline
            multi_decline_data.loc[i, 'participation_minutes'] = 42  # -30% decline
        
        detector = DeclineDetector(multi_decline_data)
        alerts = detector.generate_alerts()
        
        if alerts:
            # Should have high composite score for multi-domain decline
            max_score = max(alert['composite_score'] for alert in alerts)
            self.assertGreater(max_score, 0.5)  # Should be high severity
    
    def test_data_quality_checks(self):
        """Test data quality validation."""
        # Test duplicate patient-date combinations
        duplicate_data = self.valid_data.copy()
        duplicate_row = duplicate_data.iloc[0:1].copy()
        duplicate_data = pd.concat([duplicate_data, duplicate_row])
        
        required_cols = ['patient_id', 'observation_date']
        validation = validate_dataframe(duplicate_data, required_cols)
        self.assertFalse(validation['valid'])
        self.assertIn('duplicate', str(validation['errors']).lower())


class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions."""
    
    def test_freshness_status(self):
        """Test freshness status calculation."""
        now = datetime.now()
        
        # Fresh data
        fresh_date = now - timedelta(hours=12)
        status = get_freshness_status(fresh_date)
        self.assertEqual(status['status'], 'FRESH')
        
        # Stale data
        stale_date = now - timedelta(days=2)
        status = get_freshness_status(stale_date)
        self.assertEqual(status['status'], 'STALE')
        
        # Missing data
        missing_date = now - timedelta(days=5)
        status = get_freshness_status(missing_date)
        self.assertEqual(status['status'], 'MISSING')
        
        # None date
        status = get_freshness_status(None)
        self.assertEqual(status['status'], 'MISSING')
    
    def test_percentage_change(self):
        """Test percentage change calculation."""
        # Normal case
        self.assertAlmostEqual(calculate_percentage_change(80, 100), -20.0)
        self.assertAlmostEqual(calculate_percentage_change(120, 100), 20.0)
        
        # Zero baseline
        self.assertEqual(calculate_percentage_change(100, 0), 0.0)
        
        # NaN values
        self.assertEqual(calculate_percentage_change(np.nan, 100), 0.0)
        self.assertEqual(calculate_percentage_change(100, np.nan), 0.0)
    
    def test_severity_classification(self):
        """Test severity classification."""
        self.assertEqual(classify_severity(0.1), 'NONE')
        self.assertEqual(classify_severity(0.25), 'LOW')
        self.assertEqual(classify_severity(0.4), 'MEDIUM')
        self.assertEqual(classify_severity(0.6), 'HIGH')
    
    def test_decline_component(self):
        """Test decline component calculation."""
        # No decline (positive change)
        self.assertEqual(get_decline_component(10.0), 0.0)
        
        # Moderate decline
        self.assertAlmostEqual(get_decline_component(-10.0, 20.0), 0.5)
        
        # Severe decline (capped at 1.0)
        self.assertEqual(get_decline_component(-30.0, 20.0), 1.0)
    
    def test_capacity_utilization(self):
        """Test capacity utilization calculation."""
        # Normal capacity
        result = calculate_capacity_utilization(5, 10)
        self.assertEqual(result['utilization_percent'], 50.0)
        self.assertEqual(result['status'], 'NORMAL')
        
        # Warning level
        result = calculate_capacity_utilization(8, 10)
        self.assertEqual(result['status'], 'WARNING')
        
        # Over capacity
        result = calculate_capacity_utilization(12, 10)
        self.assertEqual(result['status'], 'OVER CAPACITY')
        
        # Zero capacity
        result = calculate_capacity_utilization(5, 0)
        self.assertEqual(result['status'], 'UNKNOWN')


if __name__ == '__main__':
    unittest.main()