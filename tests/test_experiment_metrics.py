"""
Test experiment metrics validity for the Subtle Decline Dashboard.
Ensures mathematical correctness of performance calculations.
"""
import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from experiment import ExperimentEvaluator


class TestExperimentMetrics(unittest.TestCase):
    """Test experiment metrics for mathematical validity."""
    
    def setUp(self):
        """Set up test data for metrics testing."""
        # Create test incidents
        self.test_incidents = pd.DataFrame({
            'incident_id': ['INC001', 'INC002', 'INC003'],
            'patient_id': ['P001', 'P002', 'P003'],
            'incident_date': [
                datetime.now().date() - timedelta(days=5),
                datetime.now().date() - timedelta(days=3),
                datetime.now().date() - timedelta(days=1)
            ],
            'incident_type': ['Fall', 'Hospitalization', 'Emergency Visit'],
            'severity': ['High', 'Moderate', 'High']
        })
        
        # Create test alerts - multiple alerts for same incident
        self.test_alerts_multiple = pd.DataFrame({
            'alert_id': ['ALT001', 'ALT002', 'ALT003', 'ALT004', 'ALT005'],
            'patient_id': ['P001', 'P001', 'P001', 'P002', 'P999'],  # P001 has 3 alerts, P999 has false positive
            'alert_date': [
                datetime.now().date() - timedelta(days=10),  # P001 first alert
                datetime.now().date() - timedelta(days=8),   # P001 second alert
                datetime.now().date() - timedelta(days=6),   # P001 third alert
                datetime.now().date() - timedelta(days=5),   # P002 alert (same day as incident)
                datetime.now().date() - timedelta(days=2)    # P999 false positive
            ],
            'severity': ['MEDIUM', 'HIGH', 'HIGH', 'MEDIUM', 'LOW'],
            'composite_score': [0.35, 0.50, 0.55, 0.40, 0.25],
            'explanation': [
                'Test alert 1 - mobility declined',
                'Test alert 2 - multiple domains declined', 
                'Test alert 3 - significant decline pattern',
                'Test alert 4 - moderate decline',
                'Test alert 5 - false positive pattern'
            ]
        })
        
        # Create test alerts - one alert per incident
        self.test_alerts_single = pd.DataFrame({
            'alert_id': ['ALT001', 'ALT002'],
            'patient_id': ['P001', 'P002'],
            'alert_date': [
                datetime.now().date() - timedelta(days=8),   # P001: 3 days before incident
                datetime.now().date() - timedelta(days=6)    # P002: 3 days before incident  
            ],
            'severity': ['MEDIUM', 'HIGH'],
            'composite_score': [0.35, 0.50],
            'explanation': [
                'Test single alert 1 - mobility declined',
                'Test single alert 2 - multiple domains'
            ]
        })
    
    def test_recall_cannot_exceed_100_percent(self):
        """Test that recall never exceeds 100%, even with multiple alerts per incident."""
        evaluator = ExperimentEvaluator(self.test_alerts_multiple, self.test_incidents)
        results = evaluator.calculate_performance_metrics()
        
        # Recall must be between 0 and 1
        self.assertLessEqual(results['recall'], 1.0, "Recall cannot exceed 100%")
        self.assertGreaterEqual(results['recall'], 0.0, "Recall cannot be negative")
    
    def test_early_detection_rate_cannot_exceed_100_percent(self):
        """Test that early detection rate never exceeds 100%."""
        evaluator = ExperimentEvaluator(self.test_alerts_multiple, self.test_incidents)
        results = evaluator.calculate_performance_metrics()
        
        # Early detection rates must be between 0 and 1
        self.assertLessEqual(results['early_detection_rate'], 1.0, "Early detection rate cannot exceed 100%")
        self.assertLessEqual(results['detection_rate_2day'], 1.0, "2-day detection rate cannot exceed 100%")
        self.assertLessEqual(results['detection_rate_3day'], 1.0, "3-day detection rate cannot exceed 100%")
        self.assertLessEqual(results['detection_rate_5day'], 1.0, "5-day detection rate cannot exceed 100%")
    
    def test_one_incident_multiple_alerts_counts_as_one_detection(self):
        """Test that multiple alerts for one incident count as single detection."""
        evaluator = ExperimentEvaluator(self.test_alerts_multiple, self.test_incidents)
        results = evaluator.calculate_performance_metrics()
        
        # Should have at most as many true positives as incidents
        self.assertLessEqual(results['true_positives'], results['total_incidents'],
                           "True positives cannot exceed total incidents")
        
        # With 3 incidents and multiple alerts for P001, should still count as max 3 detections
        self.assertLessEqual(results['true_positives'], 3, "Cannot have more detections than incidents")
    
    def test_incident_level_vs_alert_level_counting(self):
        """Test that metrics are calculated at incident level, not alert level."""
        evaluator = ExperimentEvaluator(self.test_alerts_multiple, self.test_incidents)
        results = evaluator.calculate_performance_metrics()
        
        # Get matches to analyze
        matches = results['matches']
        
        # Each incident should appear exactly once in matches
        incident_ids_in_matches = [m['incident_id'] for m in matches]
        unique_incidents_in_matches = set(incident_ids_in_matches)
        
        self.assertEqual(len(incident_ids_in_matches), len(unique_incidents_in_matches),
                        "Each incident should appear exactly once in matches")
        
        # Number of matches should equal number of incidents
        self.assertEqual(len(matches), results['total_incidents'],
                        "Number of matches should equal number of incidents")
    
    def test_first_alert_used_for_lead_time(self):
        """Test that lead time uses first alert, not all alerts."""
        evaluator = ExperimentEvaluator(self.test_alerts_multiple, self.test_incidents)
        results = evaluator.calculate_performance_metrics()
        
        # Find P001 match (has multiple alerts)
        p001_matches = [m for m in results['matches'] if m['patient_id'] == 'P001']
        
        if p001_matches:
            p001_match = p001_matches[0]
            # Lead time should be calculated from first alert (10 days ago)
            # Incident is 5 days ago, so lead time should be 5 days
            expected_lead_time = 5
            self.assertEqual(p001_match['lead_time_days'], expected_lead_time,
                           f"Lead time should use first alert. Expected {expected_lead_time}, got {p001_match['lead_time_days']}")
    
    def test_false_positive_identification(self):
        """Test that alerts without subsequent incidents are identified as false positives."""
        evaluator = ExperimentEvaluator(self.test_alerts_multiple, self.test_incidents)
        results = evaluator.calculate_performance_metrics()
        
        # Should identify P999 alert as false positive (no incident for P999)
        false_positive_patients = [fp['patient_id'] for fp in results['false_positives']]
        self.assertIn('P999', false_positive_patients, "Should identify P999 alert as false positive")
    
    def test_false_negative_identification(self):
        """Test that incidents without prior alerts are identified as false negatives."""
        # Create scenario with incident but no alert
        incidents_with_missed = pd.DataFrame({
            'incident_id': ['INC001'],
            'patient_id': ['P001'],
            'incident_date': [datetime.now().date() - timedelta(days=5)],
            'incident_type': ['Fall'],
            'severity': ['High']
        })
        
        # No alerts for P001
        no_alerts = pd.DataFrame(columns=['alert_id', 'patient_id', 'alert_date', 'severity', 'composite_score', 'explanation'])
        
        evaluator = ExperimentEvaluator(no_alerts, incidents_with_missed)
        results = evaluator.calculate_performance_metrics()
        
        # Should have 1 false negative, 0 true positives
        self.assertEqual(results['false_negatives'], 1, "Should identify missed incident as false negative")
        self.assertEqual(results['true_positives'], 0, "Should have no true positives when no alerts exist")
        self.assertEqual(results['recall'], 0.0, "Recall should be 0% when no incidents detected")
    
    def test_precision_calculation(self):
        """Test precision calculation with known scenario."""
        evaluator = ExperimentEvaluator(self.test_alerts_single, self.test_incidents)
        results = evaluator.calculate_performance_metrics()
        
        # With 2 alerts and 2 detected incidents: precision should be 2/2 = 100%
        # But P003 has no alert, so only 2 incidents can be detected
        # So precision = detected_incidents / total_alerts
        expected_precision = min(results['true_positives'] / results['total_alerts'], 1.0)
        self.assertAlmostEqual(results['precision'], expected_precision, places=3,
                             msg="Precision calculation should be correct")
    
    def test_metrics_with_no_incidents(self):
        """Test metrics calculation when no incidents exist."""
        no_incidents = pd.DataFrame(columns=['incident_id', 'patient_id', 'incident_date', 'incident_type', 'severity'])
        
        evaluator = ExperimentEvaluator(self.test_alerts_single, no_incidents)
        results = evaluator.calculate_performance_metrics()
        
        # Should handle empty incidents gracefully
        self.assertEqual(results['total_incidents'], 0)
        self.assertEqual(results['true_positives'], 0)
        self.assertEqual(results['false_negatives'], 0)
        self.assertEqual(results['recall'], 0.0)
        
        # All alerts should be false positives
        self.assertEqual(len(results['false_positives']), len(self.test_alerts_single))
    
    def test_metrics_with_no_alerts(self):
        """Test metrics calculation when no alerts exist."""
        no_alerts = pd.DataFrame(columns=['alert_id', 'patient_id', 'alert_date', 'severity', 'composite_score', 'explanation'])
        
        evaluator = ExperimentEvaluator(no_alerts, self.test_incidents)
        results = evaluator.calculate_performance_metrics()
        
        # Should handle empty alerts gracefully
        self.assertEqual(results['total_alerts'], 0)
        self.assertEqual(results['true_positives'], 0)
        self.assertEqual(len(results['false_positives']), 0)
        self.assertEqual(results['precision'], 0.0)
        
        # All incidents should be false negatives
        self.assertEqual(results['false_negatives'], len(self.test_incidents))
        self.assertEqual(results['recall'], 0.0)
    
    def test_lead_time_statistics(self):
        """Test lead time statistics are calculated correctly."""
        evaluator = ExperimentEvaluator(self.test_alerts_single, self.test_incidents)
        results = evaluator.calculate_performance_metrics()
        
        if results['lead_times']:
            # Lead times should be positive
            for lead_time in results['lead_times']:
                self.assertGreaterEqual(lead_time, 0, "Lead times should be non-negative")
            
            # Statistics should be consistent
            self.assertGreaterEqual(results['max_lead_time_days'], results['min_lead_time_days'],
                                  "Max lead time should be >= min lead time")
            self.assertGreaterEqual(results['avg_lead_time_days'], results['min_lead_time_days'],
                                  "Average lead time should be >= min lead time")
            self.assertLessEqual(results['avg_lead_time_days'], results['max_lead_time_days'],
                               "Average lead time should be <= max lead time")


if __name__ == '__main__':
    unittest.main()