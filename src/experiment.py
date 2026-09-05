"""
Experiment evaluation for the Subtle Decline Dashboard.
Measures early detection performance against synthetic incidents.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Tuple
import json

try:
    from .utils import get_project_root, load_csv_safely, format_date
except ImportError:
    from utils import get_project_root, load_csv_safely, format_date

# Early detection window (days before incident)
EARLY_DETECTION_WINDOW_DAYS = 7


class ExperimentEvaluator:
    """Evaluates alert performance against known incidents."""
    
    def __init__(self, alerts_df: pd.DataFrame, incidents_df: pd.DataFrame):
        """
        Initialize the evaluator.
        
        Args:
            alerts_df: DataFrame with generated alerts
            incidents_df: DataFrame with known incidents
        """
        self.alerts_df = alerts_df.copy() if not alerts_df.empty else pd.DataFrame()
        self.incidents_df = incidents_df.copy() if not incidents_df.empty else pd.DataFrame()
        self.results = {}
        
        self._prepare_data()
    
    def _prepare_data(self):
        """Prepare and clean the evaluation data."""
        if not self.alerts_df.empty:
            self.alerts_df['alert_date'] = pd.to_datetime(self.alerts_df['alert_date'])
        
        if not self.incidents_df.empty:
            self.incidents_df['incident_date'] = pd.to_datetime(self.incidents_df['incident_date'])
    
    def _match_alerts_to_incidents(self) -> List[Dict]:
        """Match alerts to incidents and calculate lead times - ONE MATCH PER INCIDENT."""
        matches = []
        
        if self.incidents_df.empty:
            return matches
        
        for _, incident in self.incidents_df.iterrows():
            patient_id = incident['patient_id']
            incident_date = incident['incident_date']
            
            # Find alerts for this patient before the incident  
            if not self.alerts_df.empty:
                patient_alerts = self.alerts_df[
                    (self.alerts_df['patient_id'] == patient_id) &
                    (self.alerts_df['alert_date'] <= incident_date)
                ].sort_values('alert_date')
            else:
                patient_alerts = pd.DataFrame()  # Empty DataFrame if no alerts
            
            if not patient_alerts.empty:
                # CRITICAL FIX: Use only the FIRST alert before the incident
                first_alert = patient_alerts.iloc[0]
                lead_time = (incident_date - first_alert['alert_date']).days
                
                # Only count if within evaluation window and meaningful lead time
                if lead_time >= 0 and lead_time <= EARLY_DETECTION_WINDOW_DAYS:
                    match = {
                        'incident_id': incident['incident_id'],
                        'patient_id': patient_id,
                        'incident_date': incident_date,
                        'incident_type': incident['incident_type'],
                        'incident_severity': incident['severity'],
                        'alert_id': first_alert['alert_id'],
                        'alert_date': first_alert['alert_date'],
                        'alert_severity': first_alert['severity'],
                        'lead_time_days': lead_time,
                        'is_early_detection': lead_time >= 1,
                        'is_2day_early': lead_time >= 2,
                        'is_3day_early': lead_time >= 3,
                        'is_5day_early': lead_time >= 5,
                        'is_within_window': lead_time <= EARLY_DETECTION_WINDOW_DAYS,
                        'composite_score': first_alert['composite_score'],
                        'detection_status': 'TRUE_POSITIVE'
                    }
                    matches.append(match)
                else:
                    # Alert exists but outside evaluation window or same-day
                    match = {
                        'incident_id': incident['incident_id'],
                        'patient_id': patient_id,
                        'incident_date': incident_date,
                        'incident_type': incident['incident_type'],
                        'incident_severity': incident['severity'],
                        'alert_id': None,
                        'alert_date': None,
                        'alert_severity': None,
                        'lead_time_days': None,
                        'is_early_detection': False,
                        'is_2day_early': False,
                        'is_3day_early': False,
                        'is_5day_early': False,
                        'is_within_window': False,
                        'composite_score': None,
                        'detection_status': 'FALSE_NEGATIVE'
                    }
                    matches.append(match)
            else:
                # No alert found for this incident (false negative)
                match = {
                    'incident_id': incident['incident_id'],
                    'patient_id': patient_id,
                    'incident_date': incident_date,
                    'incident_type': incident['incident_type'],
                    'incident_severity': incident['severity'],
                    'alert_id': None,
                    'alert_date': None,
                    'alert_severity': None,
                    'lead_time_days': None,
                    'is_early_detection': False,
                    'is_2day_early': False,
                    'is_3day_early': False,
                    'is_5day_early': False,
                    'is_within_window': False,
                    'composite_score': None,
                    'detection_status': 'FALSE_NEGATIVE'
                }
                matches.append(match)
        
        return matches
    
    def _identify_false_positives(self, matches: List[Dict]) -> List[Dict]:
        """Identify alerts that did not precede any incident (false positives)."""
        false_positives = []
        
        if self.alerts_df.empty:
            return false_positives
        
        # Get all alert IDs that matched to incidents
        matched_alert_ids = set()
        for match in matches:
            if match['alert_id']:
                matched_alert_ids.add(match['alert_id'])
        
        # Find alerts that didn't match any incident
        for _, alert in self.alerts_df.iterrows():
            if alert['alert_id'] not in matched_alert_ids:
                false_positives.append({
                    'alert_id': alert['alert_id'],
                    'patient_id': alert['patient_id'],
                    'alert_date': alert['alert_date'],
                    'alert_severity': alert['severity'],
                    'composite_score': alert['composite_score'],
                    'explanation': alert['explanation']
                })
        
        return false_positives
    
    def calculate_performance_metrics(self) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics."""
        # Match alerts to incidents (ONE MATCH PER INCIDENT)
        matches = self._match_alerts_to_incidents()
        false_positives = self._identify_false_positives(matches)
        
        # Basic counts - INCIDENT-BASED, NOT ALERT-BASED
        total_incidents = len(self.incidents_df)
        total_alerts = len(self.alerts_df)
        
        # Handle empty DataFrames safely
        alert_patients = set(self.alerts_df['patient_id']) if not self.alerts_df.empty else set()
        incident_patients = set(self.incidents_df['patient_id']) if not self.incidents_df.empty else set()
        total_patients = len(alert_patients | incident_patients)
        
        # CORRECTED: Count unique incidents, not alerts
        true_positive_incidents = [m for m in matches if m['detection_status'] == 'TRUE_POSITIVE']
        false_negative_incidents = [m for m in matches if m['detection_status'] == 'FALSE_NEGATIVE']
        
        num_true_positives = len(true_positive_incidents)
        num_false_negatives = len(false_negative_incidents)
        num_false_positives = len(false_positives)
        
        # Early detection metrics (INCIDENT-BASED)
        early_detections_1day = [m for m in true_positive_incidents if m['is_early_detection']]
        early_detections_2day = [m for m in true_positive_incidents if m['is_2day_early']]  
        early_detections_3day = [m for m in true_positive_incidents if m['is_3day_early']]
        early_detections_5day = [m for m in true_positive_incidents if m['is_5day_early']]
        
        # Lead time statistics (only for detected incidents)
        lead_times = [m['lead_time_days'] for m in true_positive_incidents if m['lead_time_days'] is not None]
        
        # CORRECTED CALCULATIONS - Must be between 0% and 100%
        recall = (num_true_positives / total_incidents) if total_incidents > 0 else 0
        precision = (num_true_positives / total_alerts) if total_alerts > 0 else 0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        # Detection rates (INCIDENT-BASED)
        early_detection_rate = len(early_detections_1day) / total_incidents if total_incidents > 0 else 0
        detection_rate_2day = len(early_detections_2day) / total_incidents if total_incidents > 0 else 0
        detection_rate_3day = len(early_detections_3day) / total_incidents if total_incidents > 0 else 0
        detection_rate_5day = len(early_detections_5day) / total_incidents if total_incidents > 0 else 0
        
        results = {
            'experiment_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_patients': total_patients,
            'total_incidents': total_incidents,
            'total_alerts': total_alerts,
            'true_positives': num_true_positives,
            'false_positives': num_false_positives,
            'false_negatives': num_false_negatives,
            'precision': round(precision, 3),
            'recall': round(recall, 3),
            'f1_score': round(f1_score, 3),
            'early_detections_1day': len(early_detections_1day),
            'early_detection_rate': round(early_detection_rate, 3),
            'detection_rate_2day': round(detection_rate_2day, 3),
            'detection_rate_3day': round(detection_rate_3day, 3),
            'detection_rate_5day': round(detection_rate_5day, 3),
            'avg_lead_time_days': round(np.mean(lead_times), 1) if lead_times else 0,
            'median_lead_time_days': round(np.median(lead_times), 1) if lead_times else 0,
            'min_lead_time_days': min(lead_times) if lead_times else 0,
            'max_lead_time_days': max(lead_times) if lead_times else 0,
            'lead_times': lead_times,
            'matches': matches,
            'false_positives': false_positives,
            'target_achievement': {
                'target_detection_rate': 0.70,  # 70% target
                'achieved_detection_rate': detection_rate_2day,  # Use 2-day early detection
                'target_met': detection_rate_2day >= 0.70
            }
        }
        
        self.results = results
        return results
    
    def generate_error_analysis(self) -> Dict[str, List[Dict]]:
        """Generate detailed error analysis."""
        if not self.results:
            self.calculate_performance_metrics()
        
        false_positives = self.results['false_positives']
        false_negatives = [m for m in self.results['matches'] if m['alert_id'] is None]
        
        # Analyze false positive patterns
        fp_analysis = []
        for fp in false_positives[:5]:  # Top 5 examples
            fp_analysis.append({
                'patient_id': fp['patient_id'],
                'alert_date': format_date(fp['alert_date']),
                'severity': fp['alert_severity'],
                'score': fp['composite_score'],
                'explanation': fp['explanation'],
                'likely_cause': 'Temporary variation or insufficient incident data'
            })
        
        # Analyze false negative patterns
        fn_analysis = []
        for fn in false_negatives:
            fn_analysis.append({
                'patient_id': fn['patient_id'],
                'incident_date': format_date(fn['incident_date']),
                'incident_type': fn['incident_type'],
                'incident_severity': fn['incident_severity'],
                'likely_cause': 'Rapid onset event or insufficient observation data'
            })
        
        return {
            'false_positive_examples': fp_analysis,
            'false_negative_examples': fn_analysis,
            'false_positive_count': len(false_positives),
            'false_negative_count': len(false_negatives)
        }
    
    def print_summary_report(self):
        """Print a comprehensive summary report."""
        if not self.results:
            self.calculate_performance_metrics()
        
        error_analysis = self.generate_error_analysis()
        
        print("\n" + "="*60)
        print("SUBTLE DECLINE DETECTION - EXPERIMENT RESULTS")
        print("="*60)
        
        print(f"\nEXPERIMENT OVERVIEW:")
        print(f"- Evaluation Date: {self.results['experiment_date']}")
        print(f"- Total Patients: {self.results['total_patients']}")
        print(f"- Synthetic Incidents: {self.results['total_incidents']}")
        print(f"- Generated Alerts: {self.results['total_alerts']}")
        
        print(f"\nTARGET vs MEASURED RESULTS:")
        target_info = self.results['target_achievement']
        print(f"- Target: Detect ≥70% of incidents ≥2 days before event")
        print(f"- Measured: {target_info['achieved_detection_rate']:.1%}")
        print(f"- Status: {'✓ TARGET ACHIEVED' if target_info['target_met'] else '✗ TARGET NOT ACHIEVED'}")
        
        print(f"\nDETECTION PERFORMANCE (INCIDENT-BASED):")
        print(f"- Unique Incidents Detected: {self.results['true_positives']} / {self.results['total_incidents']}")
        print(f"- False Positives (Alerts without incidents): {self.results['false_positives']}")
        print(f"- False Negatives (Missed incidents): {self.results['false_negatives']}")
        print(f"- Precision: {self.results['precision']:.1%}")
        print(f"- Recall: {self.results['recall']:.1%}")
        print(f"- F1 Score: {self.results['f1_score']:.3f}")
        
        print(f"\nEARLY DETECTION ANALYSIS:")
        print(f"- Incidents detected ≥1 day early: {self.results['early_detections_1day']} ({self.results['early_detection_rate']:.1%})")
        print(f"- Incidents detected ≥2 days early: {self.results['detection_rate_2day']:.1%}")
        print(f"- Incidents detected ≥3 days early: {self.results['detection_rate_3day']:.1%}")
        print(f"- Incidents detected ≥5 days early: {self.results['detection_rate_5day']:.1%}")
        
        if self.results['lead_times']:
            print(f"\nLEAD TIME ANALYSIS:")
            print(f"- Average Lead Time: {self.results['avg_lead_time_days']} days")
            print(f"- Median Lead Time: {self.results['median_lead_time_days']} days")
            print(f"- Lead Time Range: {self.results['min_lead_time_days']}-{self.results['max_lead_time_days']} days")
        
        print(f"\nTRUE POSITIVE EXAMPLES:")
        successful_detections = [m for m in self.results['matches'] if m['detection_status'] == 'TRUE_POSITIVE']
        if successful_detections:
            for match in successful_detections:
                print(f"  • {match['patient_id']}: {match['incident_type']} detected {match['lead_time_days']} days early")
        else:
            print("  • No successful early detections")
        
        print(f"\nFALSE NEGATIVE EXAMPLES:")
        missed_incidents = [m for m in self.results['matches'] if m['detection_status'] == 'FALSE_NEGATIVE']
        if missed_incidents:
            for match in missed_incidents:
                print(f"  • {match['patient_id']}: {match['incident_type']} on {format_date(match['incident_date'])} - No prior alert")
        else:
            print("  • No missed incidents")
        
        print(f"\nFALSE POSITIVE EXAMPLES:")
        if error_analysis['false_positive_examples']:
            for fp in error_analysis['false_positive_examples'][:3]:
                print(f"  • {fp['patient_id']}: Alert on {fp['alert_date']} - No subsequent incident")
        else:
            print("  • No false positive alerts")
        
        print("\n" + "="*60)


def main():
    """Run the complete experiment evaluation."""
    print("Running Subtle Decline Detection Experiment...")
    
    # Load data
    project_root = get_project_root()
    data_dir = project_root / "data"
    
    # Load alerts and incidents
    alerts_df = load_csv_safely(data_dir / "generated_alerts.csv")
    incidents_df = load_csv_safely(data_dir / "synthetic_incidents.csv")
    
    if alerts_df is None:
        print("Error: Could not load generated alerts. Run alert_engine.py first.")
        return
    
    if incidents_df is None:
        print("Error: Could not load synthetic incidents.")
        return
    
    # Run evaluation
    evaluator = ExperimentEvaluator(alerts_df, incidents_df)
    results = evaluator.calculate_performance_metrics()
    
    # Generate comprehensive report
    evaluator.print_summary_report()
    
    # Save results
    summary_file = data_dir / "alert_summary.json"
    with open(summary_file, 'w') as f:
        # Convert datetime objects to strings for JSON serialization
        json_results = results.copy()
        if 'matches' in json_results:
            for match in json_results['matches']:
                if match.get('incident_date'):
                    match['incident_date'] = match['incident_date'].strftime('%Y-%m-%d')
                if match.get('alert_date'):
                    match['alert_date'] = match['alert_date'].strftime('%Y-%m-%d')
        
        if 'false_positives' in json_results:
            for fp in json_results['false_positives']:
                if fp.get('alert_date'):
                    fp['alert_date'] = fp['alert_date'].strftime('%Y-%m-%d')
        
        json.dump(json_results, f, indent=2)
    
    print(f"\n✓ Experiment results saved to {summary_file}")
    
    return results


if __name__ == "__main__":
    main()