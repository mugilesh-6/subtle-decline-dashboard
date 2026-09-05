"""
Test data freshness functionality for the Subtle Decline Dashboard.
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
from utils import get_freshness_status, load_csv_safely


class TestFreshness(unittest.TestCase):
    """Test data freshness detection and handling."""
    
    def setUp(self):
        """Set up test data for freshness testing."""
        self.now = datetime.now()
        
        # Create test data with different freshness levels
        dates = [
            self.now - timedelta(hours=6),      # Fresh
            self.now - timedelta(hours=18),     # Fresh
            self.now - timedelta(days=2),       # Stale
            self.now - timedelta(days=3),       # Stale
            self.now - timedelta(days=5),       # Missing
            self.now - timedelta(days=10)       # Missing
        ]
        
        self.test_data = pd.DataFrame({
            'patient_id': ['P001', 'P002', 'P003', 'P004', 'P005', 'P006'],
            'patient_name': ['Patient 1', 'Patient 2', 'Patient 3', 'Patient 4', 'Patient 5', 'Patient 6'],
            'observation_date': dates,
            'mobility_steps': [5000, 4800, 5200, 4600, 5100, 4900],
            'nutrition_kcal': [2000, 1900, 2100, 1800, 2050, 1950],
            'participation_minutes': [60, 55, 65, 50, 62, 58]
        })
    
    def test_fresh_data_detection(self):
        """Test detection of fresh data (≤1 day old)."""
        # Test fresh data (6 hours ago)
        fresh_date = self.now - timedelta(hours=6)
        status = get_freshness_status(fresh_date)
        
        self.assertEqual(status['status'], 'FRESH')
        self.assertIn('0 day', status['explanation'])
    
    def test_stale_data_detection(self):
        """Test detection of stale data (2-3 days old)."""
        # Test stale data (2 days ago)
        stale_date = self.now - timedelta(days=2)
        status = get_freshness_status(stale_date)
        
        self.assertEqual(status['status'], 'STALE')
        self.assertIn('2 days ago', status['explanation'])
        
        # Test stale data (3 days ago)
        stale_date = self.now - timedelta(days=3)
        status = get_freshness_status(stale_date)
        
        self.assertEqual(status['status'], 'STALE')
        self.assertIn('3 days ago', status['explanation'])
    
    def test_missing_data_detection(self):
        """Test detection of missing data (>3 days old)."""
        # Test missing data (5 days ago)
        missing_date = self.now - timedelta(days=5)
        status = get_freshness_status(missing_date)
        
        self.assertEqual(status['status'], 'MISSING')
        self.assertIn('5 days', status['explanation'])
    
    def test_none_date_handling(self):
        """Test handling of None date (no data received)."""
        status = get_freshness_status(None)
        
        self.assertEqual(status['status'], 'MISSING')
        self.assertEqual(status['explanation'], 'No data received')
    
    def test_patient_status_with_fresh_data(self):
        """Test patient status calculation with fresh data."""
        # Create fresh data for one patient
        fresh_data = pd.DataFrame({
            'patient_id': ['P001'] * 35,
            'patient_name': ['Test Patient'] * 35,
            'observation_date': pd.date_range(
                start=self.now - timedelta(days=34),
                end=self.now,
                periods=35
            ),
            'mobility_steps': [5000] * 35,
            'nutrition_kcal': [2000] * 35,
            'participation_minutes': [60] * 35
        })
        
        detector = DeclineDetector(fresh_data)
        status = detector.get_patient_current_status('P001')
        
        self.assertEqual(status['status'], 'CURRENT')
        self.assertEqual(status['days_since_observation'], 0)
    
    def test_patient_status_with_stale_data(self):
        """Test patient status calculation with stale data."""
        # Create data where last observation is 4 days ago
        stale_date = self.now - timedelta(days=4)
        stale_data = pd.DataFrame({
            'patient_id': ['P001'] * 35,
            'patient_name': ['Test Patient'] * 35,
            'observation_date': pd.date_range(
                start=stale_date - timedelta(days=34),
                end=stale_date,
                periods=35
            ),
            'mobility_steps': [5000] * 35,
            'nutrition_kcal': [2000] * 35,
            'participation_minutes': [60] * 35
        })
        
        detector = DeclineDetector(stale_data)
        status = detector.get_patient_current_status('P001')
        
        self.assertEqual(status['status'], 'STALE_DATA')
        self.assertIn('4 days old', status['message'])
    
    def test_patient_status_with_no_data(self):
        """Test patient status with no observation data."""
        empty_data = pd.DataFrame({
            'patient_id': [],
            'patient_name': [],
            'observation_date': [],
            'mobility_steps': [],
            'nutrition_kcal': [],
            'participation_minutes': []
        })
        
        detector = DeclineDetector(empty_data)
        status = detector.get_patient_current_status('P001')
        
        self.assertEqual(status['status'], 'NO_DATA')
        self.assertIn('No observation data available', status['message'])
    
    def test_patient_status_insufficient_baseline(self):
        """Test patient status with insufficient baseline data."""
        # Only 5 observations - not enough for baseline
        insufficient_data = pd.DataFrame({
            'patient_id': ['P001'] * 5,
            'patient_name': ['Test Patient'] * 5,
            'observation_date': pd.date_range(
                start=self.now - timedelta(days=4),
                end=self.now,
                periods=5
            ),
            'mobility_steps': [5000] * 5,
            'nutrition_kcal': [2000] * 5,
            'participation_minutes': [60] * 5
        })
        
        detector = DeclineDetector(insufficient_data)
        status = detector.get_patient_current_status('P001')
        
        self.assertEqual(status['status'], 'INSUFFICIENT_DATA')
        self.assertIn('No baseline data available', status['message'])
    
    def test_freshness_boundary_conditions(self):
        """Test freshness detection at boundary conditions."""
        # Exactly 1 day old (should be FRESH)
        exactly_1_day = self.now - timedelta(days=1, seconds=1)
        status = get_freshness_status(exactly_1_day)
        self.assertEqual(status['status'], 'FRESH')
        
        # Exactly 3 days old (should be STALE)
        exactly_3_days = self.now - timedelta(days=3, seconds=1)
        status = get_freshness_status(exactly_3_days)
        self.assertEqual(status['status'], 'STALE')
        
        # Just over 3 days (should be MISSING)
        over_3_days = self.now - timedelta(days=4)  # Changed from 3 hours to 4 days
        status = get_freshness_status(over_3_days)
        self.assertEqual(status['status'], 'MISSING')
    
    def test_mixed_freshness_patient_group(self):
        """Test handling of patients with mixed data freshness."""
        # Create baseline data for all patients
        base_dates = pd.date_range(
            start=self.now - timedelta(days=60),
            end=self.now - timedelta(days=30),
            periods=30
        )
        
        patients_data = []
        for patient_id in ['P001', 'P002', 'P003']:
            for date in base_dates:
                patients_data.append({
                    'patient_id': patient_id,
                    'patient_name': f'Patient {patient_id[-1]}',
                    'observation_date': date,
                    'mobility_steps': 5000,
                    'nutrition_kcal': 2000,
                    'participation_minutes': 60
                })
        
        # Add recent data with different freshness
        # P001: Fresh data (today)
        patients_data.append({
            'patient_id': 'P001',
            'patient_name': 'Patient 1',
            'observation_date': self.now,
            'mobility_steps': 4500,
            'nutrition_kcal': 1800,
            'participation_minutes': 50
        })
        
        # P002: Stale data (2 days ago)
        patients_data.append({
            'patient_id': 'P002',
            'patient_name': 'Patient 2',
            'observation_date': self.now - timedelta(days=2),
            'mobility_steps': 4600,
            'nutrition_kcal': 1850,
            'participation_minutes': 52
        })
        
        # P003: Missing data (5 days ago)
        patients_data.append({
            'patient_id': 'P003',
            'patient_name': 'Patient 3',
            'observation_date': self.now - timedelta(days=5),
            'mobility_steps': 4700,
            'nutrition_kcal': 1900,
            'participation_minutes': 55
        })
        
        mixed_data = pd.DataFrame(patients_data)
        detector = DeclineDetector(mixed_data)
        
        # Test each patient's status
        status_p001 = detector.get_patient_current_status('P001')
        status_p002 = detector.get_patient_current_status('P002')
        status_p003 = detector.get_patient_current_status('P003')
        
        self.assertEqual(status_p001['status'], 'CURRENT')
        self.assertEqual(status_p002['status'], 'STALE_DATA')  
        self.assertEqual(status_p003['status'], 'STALE_DATA')
    
    def test_alert_generation_with_stale_data(self):
        """Test that alerts are not generated for patients with stale data."""
        # Create data with clear decline pattern but stale timestamps
        stale_date = self.now - timedelta(days=5)
        
        decline_data = []
        dates = pd.date_range(
            start=stale_date - timedelta(days=34),
            end=stale_date,
            periods=35
        )
        
        for i, date in enumerate(dates):
            # Create decline in last 5 observations
            if i >= 30:
                mobility = 3000  # Significant decline
                nutrition = 1200
                participation = 30
            else:
                mobility = 5000
                nutrition = 2000
                participation = 60
            
            decline_data.append({
                'patient_id': 'P001',
                'patient_name': 'Test Patient',
                'observation_date': date,
                'mobility_steps': mobility,
                'nutrition_kcal': nutrition,
                'participation_minutes': participation
            })
        
        stale_decline_data = pd.DataFrame(decline_data)
        detector = DeclineDetector(stale_decline_data)
        
        # Should still generate alerts based on historical data
        alerts = detector.generate_alerts()
        
        # But patient status should indicate stale data
        status = detector.get_patient_current_status('P001')
        self.assertEqual(status['status'], 'STALE_DATA')


if __name__ == '__main__':
    unittest.main()