"""
Alert engine for detecting subtle functional decline in older adults.
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
except ImportError:
    from utils import (
        get_project_root, calculate_percentage_change, classify_severity,
        get_decline_component, create_alert_explanation, safe_numeric,
        load_csv_safely, validate_dataframe
    )

# Alert severity thresholds
SEVERITY_THRESHOLDS = {
    'LOW': 0.20,
    'MEDIUM': 0.35,
    'HIGH': 0.50
}

# Domain weights for composite scoring
DOMAIN_WEIGHTS = {
    'mobility': 0.40,
    'nutrition': 0.30,
    'participation': 0.30
}

# Minimum consecutive days for alert generation
MIN_CONSECUTIVE_DAYS = 2

# Baseline period (days)
BASELINE_PERIOD_DAYS = 30


class DeclineDetector:
    """Detects functional decline patterns in patient observation data."""
    
    def __init__(self, daily_data: pd.DataFrame):
        """
        Initialize the decline detector.
        
        Args:
            daily_data: DataFrame with daily patient observations
        """
        self.daily_data = daily_data.copy() if daily_data is not None else pd.DataFrame()
        self.patient_baselines = {}
        self.alerts = []
        
        # Validate input data
        required_cols = [
            'patient_id', 'observation_date', 'mobility_steps',
            'nutrition_kcal', 'participation_minutes'
        ]
        validation = validate_dataframe(self.daily_data, required_cols)
        if not validation['valid']:
            print(f"Warning: Data validation issues: {validation['errors']}")
        
        # Prepare data
        self._prepare_data()
        self._calculate_baselines()
    
    def _prepare_data(self):
        """Prepare and clean the daily data."""
        if self.daily_data.empty:
            return
        
        # Convert observation_date to datetime
        self.daily_data['observation_date'] = pd.to_datetime(
            self.daily_data['observation_date']
        )
        
        # Sort by patient and date
        self.daily_data = self.daily_data.sort_values(
            ['patient_id', 'observation_date']
        ).reset_index(drop=True)
        
        # Ensure numeric columns are numeric
        numeric_cols = ['mobility_steps', 'nutrition_kcal', 'participation_minutes']
        for col in numeric_cols:
            self.daily_data[col] = pd.to_numeric(self.daily_data[col], errors='coerce')
    
    def _calculate_baselines(self):
        """Calculate personal baselines for each patient."""
        if self.daily_data.empty:
            return
            
        for patient_id in self.daily_data['patient_id'].unique():
            patient_data = self.daily_data[
                self.daily_data['patient_id'] == patient_id
            ].copy()
            
            # Get first 30 valid observations as baseline
            baseline_data = patient_data.head(BASELINE_PERIOD_DAYS)
            baseline_data = baseline_data.dropna(
                subset=['mobility_steps', 'nutrition_kcal', 'participation_minutes']
            )
            
            if len(baseline_data) < 15:  # Minimum baseline data requirement
                print(f"Warning: Insufficient baseline data for {patient_id} "
                      f"({len(baseline_data)} observations)")
                continue
            
            self.patient_baselines[patient_id] = {
                'mobility_baseline': baseline_data['mobility_steps'].mean(),
                'nutrition_baseline': baseline_data['nutrition_kcal'].mean(),
                'participation_baseline': baseline_data['participation_minutes'].mean(),
                'baseline_period': len(baseline_data)
            }
    
    def _calculate_decline_deltas(self, current_obs: Dict, patient_id: str) -> Dict[str, float]:
        """Calculate decline deltas from personal baseline."""
        if patient_id not in self.patient_baselines:
            return {
                'mobility_delta': 0.0,
                'nutrition_delta': 0.0,
                'participation_delta': 0.0
            }
        
        baseline = self.patient_baselines[patient_id]
        
        mobility_delta = calculate_percentage_change(
            safe_numeric(current_obs.get('mobility_steps', 0)),
            baseline['mobility_baseline']
        )
        
        nutrition_delta = calculate_percentage_change(
            safe_numeric(current_obs.get('nutrition_kcal', 0)),
            baseline['nutrition_baseline']
        )
        
        participation_delta = calculate_percentage_change(
            safe_numeric(current_obs.get('participation_minutes', 0)),
            baseline['participation_baseline']
        )
        
        return {
            'mobility_delta': mobility_delta,
            'nutrition_delta': nutrition_delta,
            'participation_delta': participation_delta
        }
    
    def _calculate_composite_score(self, deltas: Dict[str, float]) -> float:
        """Calculate weighted composite decline score."""
        # Only negative changes (decline) contribute to score
        mobility_component = get_decline_component(deltas['mobility_delta'])
        nutrition_component = get_decline_component(deltas['nutrition_delta'])
        participation_component = get_decline_component(deltas['participation_delta'])
        
        composite_score = (
            mobility_component * DOMAIN_WEIGHTS['mobility'] +
            nutrition_component * DOMAIN_WEIGHTS['nutrition'] +
            participation_component * DOMAIN_WEIGHTS['participation']
        )
        
        return composite_score
    
    def _is_sufficient_data_quality(self, recent_obs: List[Dict]) -> bool:
        """Check if recent observations have sufficient data quality."""
        if len(recent_obs) < MIN_CONSECUTIVE_DAYS:
            return False
        
        # Check for missing critical metrics
        for obs in recent_obs:
            if (pd.isna(obs.get('mobility_steps')) or 
                pd.isna(obs.get('nutrition_kcal')) or
                pd.isna(obs.get('participation_minutes'))):
                return False
        
        return True
    
    def _detect_consecutive_decline(self, patient_id: str) -> List[Dict]:
        """Detect consecutive days of meaningful decline for a patient."""
        patient_data = self.daily_data[
            self.daily_data['patient_id'] == patient_id
        ].copy()
        
        if len(patient_data) < MIN_CONSECUTIVE_DAYS:
            return []
        
        alerts = []
        consecutive_decline_days = []
        
        for _, row in patient_data.iterrows():
            obs = row.to_dict()
            deltas = self._calculate_decline_deltas(obs, patient_id)
            composite_score = self._calculate_composite_score(deltas)
            
            # Check if this day shows meaningful decline
            if composite_score >= SEVERITY_THRESHOLDS['LOW']:
                consecutive_decline_days.append({
                    'date': row['observation_date'],
                    'observation': obs,
                    'deltas': deltas,
                    'composite_score': composite_score
                })
            else:
                # Reset consecutive days if no decline
                if len(consecutive_decline_days) >= MIN_CONSECUTIVE_DAYS:
                    # Generate alert for the consecutive decline period
                    alert = self._create_alert(patient_id, consecutive_decline_days)
                    if alert:
                        alerts.append(alert)
                
                consecutive_decline_days = []
        
        # Check for decline period at the end
        if len(consecutive_decline_days) >= MIN_CONSECUTIVE_DAYS:
            alert = self._create_alert(patient_id, consecutive_decline_days)
            if alert:
                alerts.append(alert)
        
        return alerts
    
    def _create_alert(self, patient_id: str, decline_days: List[Dict]) -> Optional[Dict]:
        """Create an alert from consecutive decline days."""
        if not decline_days:
            return None
        
        # Check data quality
        if not self._is_sufficient_data_quality([d['observation'] for d in decline_days]):
            return None
        
        # Calculate average deltas and score
        avg_mobility_delta = np.mean([d['deltas']['mobility_delta'] for d in decline_days])
        avg_nutrition_delta = np.mean([d['deltas']['nutrition_delta'] for d in decline_days])
        avg_participation_delta = np.mean([d['deltas']['participation_delta'] for d in decline_days])
        avg_composite_score = np.mean([d['composite_score'] for d in decline_days])
        
        # Determine affected domains
        affected_domains = []
        if avg_mobility_delta < -5:
            affected_domains.append('Mobility')
        if avg_nutrition_delta < -5:
            affected_domains.append('Nutrition')
        if avg_participation_delta < -5:
            affected_domains.append('Participation')
        
        # Create explanation
        explanation = create_alert_explanation(
            avg_mobility_delta, avg_nutrition_delta, avg_participation_delta,
            len(decline_days)
        )
        
        # Get patient name
        patient_name = self.daily_data[
            self.daily_data['patient_id'] == patient_id
        ]['patient_name'].iloc[0]
        
        alert = {
            'alert_id': f"ALT_{patient_id}_{decline_days[0]['date'].strftime('%Y%m%d')}",
            'patient_id': patient_id,
            'patient_name': patient_name,
            'decline_start_date': decline_days[0]['date'].strftime('%Y-%m-%d'),
            'alert_date': decline_days[-1]['date'].strftime('%Y-%m-%d'),
            'duration_days': len(decline_days),
            'domains_affected': ', '.join(affected_domains) if affected_domains else 'Multiple',
            'composite_score': round(avg_composite_score, 3),
            'severity': classify_severity(avg_composite_score),
            'mobility_delta': round(avg_mobility_delta, 1),
            'nutrition_delta': round(avg_nutrition_delta, 1),
            'participation_delta': round(avg_participation_delta, 1),
            'explanation': explanation,
            'status': 'ACTIVE',
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return alert
    
    def generate_alerts(self) -> List[Dict]:
        """Generate alerts for all patients."""
        if self.daily_data.empty:
            print("Warning: No daily data available for alert generation")
            return []
        
        all_alerts = []
        
        for patient_id in self.daily_data['patient_id'].unique():
            if patient_id not in self.patient_baselines:
                print(f"Skipping {patient_id}: No baseline available")
                continue
            
            patient_alerts = self._detect_consecutive_decline(patient_id)
            all_alerts.extend(patient_alerts)
        
        self.alerts = all_alerts
        return all_alerts
    
    def get_patient_current_status(self, patient_id: str) -> Dict[str, Any]:
        """Get current status for a specific patient."""
        # Check if we have any data at all
        if self.daily_data.empty:
            return {
                'status': 'NO_DATA',
                'message': 'No observation data available'
            }
            
        if patient_id not in self.patient_baselines:
            return {
                'status': 'INSUFFICIENT_DATA',
                'message': 'No baseline data available'
            }
        
        # Get most recent observation
        patient_data = self.daily_data[
            self.daily_data['patient_id'] == patient_id
        ].sort_values('observation_date')
        
        if patient_data.empty:
            return {
                'status': 'NO_DATA',
                'message': 'No observation data available'
            }
        
        recent_obs = patient_data.iloc[-1].to_dict()
        
        # Check data freshness
        last_obs_date = pd.to_datetime(recent_obs['observation_date'])
        days_since = (datetime.now() - last_obs_date).days
        
        if days_since > 1:  # Changed from 3 to 1 to match stale definition
            return {
                'status': 'STALE_DATA',
                'message': f'Data is {days_since} days old',
                'last_observation_date': recent_obs['observation_date']
            }
        
        # Calculate current deltas
        deltas = self._calculate_decline_deltas(recent_obs, patient_id)
        composite_score = self._calculate_composite_score(deltas)
        
        baseline = self.patient_baselines[patient_id]
        
        return {
            'status': 'CURRENT',
            'patient_id': patient_id,
            'last_observation_date': recent_obs['observation_date'],
            'days_since_observation': days_since,
            'current_values': {
                'mobility_steps': recent_obs['mobility_steps'],
                'nutrition_kcal': recent_obs['nutrition_kcal'],
                'participation_minutes': recent_obs['participation_minutes']
            },
            'baseline_values': {
                'mobility_baseline': round(baseline['mobility_baseline'], 1),
                'nutrition_baseline': round(baseline['nutrition_baseline'], 1),
                'participation_baseline': round(baseline['participation_baseline'], 1)
            },
            'percentage_changes': {
                'mobility_delta': round(deltas['mobility_delta'], 1),
                'nutrition_delta': round(deltas['nutrition_delta'], 1),
                'participation_delta': round(deltas['participation_delta'], 1)
            },
            'composite_score': round(composite_score, 3),
            'risk_level': classify_severity(composite_score)
        }


def main():
    """Main function to run alert generation."""
    print("Running decline detection and alert generation...")
    
    # Load data
    project_root = get_project_root()
    data_dir = project_root / "data"
    
    daily_data_file = data_dir / "synthetic_daily_data.csv"
    daily_data = load_csv_safely(daily_data_file)
    
    if daily_data is None:
        print(f"Error: Could not load daily data from {daily_data_file}")
        return
    
    # Initialize detector
    detector = DeclineDetector(daily_data)
    
    # Generate alerts
    alerts = detector.generate_alerts()
    
    # Save alerts to CSV
    alerts_file = data_dir / "generated_alerts.csv"
    if alerts:
        alerts_df = pd.DataFrame(alerts)
        alerts_df.to_csv(alerts_file, index=False)
        print(f"✓ Generated {len(alerts)} alerts -> {alerts_file}")
    else:
        # Create empty file with headers
        empty_df = pd.DataFrame(columns=[
            'alert_id', 'patient_id', 'patient_name', 'decline_start_date',
            'alert_date', 'duration_days', 'domains_affected', 'composite_score',
            'severity', 'mobility_delta', 'nutrition_delta', 'participation_delta',
            'explanation', 'status', 'created_at'
        ])
        empty_df.to_csv(alerts_file, index=False)
        print(f"✓ No alerts generated -> Created empty {alerts_file}")
    
    # Print summary
    print(f"\nAlert Generation Summary:")
    print(f"- Total patients processed: {daily_data['patient_id'].nunique()}")
    print(f"- Patients with baselines: {len(detector.patient_baselines)}")
    print(f"- Total alerts generated: {len(alerts)}")
    
    if alerts:
        severity_counts = {}
        for alert in alerts:
            severity = alert['severity']
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        print(f"- Alerts by severity:")
        for severity, count in severity_counts.items():
            print(f"  {severity}: {count}")
    
    return alerts


if __name__ == "__main__":
    main()