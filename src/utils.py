"""
Utility functions for the Subtle Decline Dashboard.
"""
from pathlib import Path
from typing import Optional, Dict, Any, List
import pandas as pd
from datetime import datetime, timedelta
import numpy as np


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).resolve().parent.parent


def validate_dataframe(df: pd.DataFrame, required_columns: List[str]) -> Dict[str, Any]:
    """
    Validate a dataframe has required columns and basic data integrity.
    
    Returns:
        Dict with 'valid' (bool) and 'errors' (list) keys
    """
    errors = []
    
    if df is None or df.empty:
        errors.append("DataFrame is empty")
        return {'valid': False, 'errors': errors}
    
    # Check required columns
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        errors.append(f"Missing required columns: {missing_cols}")
    
    # Check for duplicate rows if patient_id and observation_date exist
    if 'patient_id' in df.columns and 'observation_date' in df.columns:
        duplicates = df.duplicated(subset=['patient_id', 'observation_date'])
        if duplicates.any():
            errors.append(f"Found {duplicates.sum()} duplicate patient-date combinations")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors
    }


def get_freshness_status(last_observation_date: Optional[datetime]) -> Dict[str, str]:
    """
    Determine data freshness status based on last observation date.
    
    Returns:
        Dict with 'status' and 'explanation' keys
    """
    if last_observation_date is None:
        return {
            'status': 'MISSING',
            'explanation': 'No data received'
        }
    
    now = datetime.now()
    days_since = (now - last_observation_date).days
    
    if days_since <= 1:
        return {
            'status': 'FRESH',
            'explanation': f'Updated {days_since} day{"s" if days_since != 1 else ""} ago'
        }
    elif days_since <= 3:
        return {
            'status': 'STALE',
            'explanation': f'Last update {days_since} days ago'
        }
    else:
        return {
            'status': 'MISSING',
            'explanation': f'No data received for {days_since} days'
        }


def calculate_percentage_change(current: float, baseline: float) -> float:
    """Calculate percentage change from baseline."""
    if baseline == 0 or pd.isna(baseline) or pd.isna(current):
        return 0.0
    return ((current - baseline) / baseline) * 100


def classify_severity(composite_score: float) -> str:
    """Classify alert severity based on composite score."""
    if composite_score >= 0.50:
        return 'HIGH'
    elif composite_score >= 0.35:
        return 'MEDIUM'
    elif composite_score >= 0.20:
        return 'LOW'
    else:
        return 'NONE'


def safe_numeric(value: Any, default: float = 0.0) -> float:
    """Safely convert value to numeric, returning default if invalid."""
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def format_date(date_obj: datetime) -> str:
    """Format datetime object to readable string."""
    if date_obj is None:
        return "Unknown"
    return date_obj.strftime("%Y-%m-%d")


def calculate_capacity_utilization(assigned_patients: int, max_capacity: int) -> Dict[str, Any]:
    """
    Calculate capacity utilization for care coordinators.
    
    Returns:
        Dict with utilization percentage and status
    """
    if max_capacity == 0:
        return {
            'utilization_percent': 0,
            'status': 'UNKNOWN'
        }
    
    utilization = (assigned_patients / max_capacity) * 100
    
    if utilization > 100:
        status = 'OVER CAPACITY'
    elif utilization >= 80:
        status = 'WARNING'
    else:
        status = 'NORMAL'
    
    return {
        'utilization_percent': utilization,
        'status': status
    }


def get_decline_component(delta_percent: float, threshold: float = 20.0) -> float:
    """
    Calculate decline component for composite scoring.
    Only negative changes (decline) contribute to the score.
    """
    if delta_percent >= 0:  # No decline or improvement
        return 0.0
    
    # Convert to positive decline value and normalize against threshold
    decline_amount = abs(delta_percent)
    return min(decline_amount / threshold, 1.0)  # Cap at 1.0


def create_alert_explanation(mobility_delta: float, nutrition_delta: float, 
                           participation_delta: float, duration_days: int) -> str:
    """Create human-readable explanation for an alert."""
    explanations = []
    
    if mobility_delta < -5:  # Meaningful decline threshold
        explanations.append(f"Mobility declined {abs(mobility_delta):.1f}%")
    
    if nutrition_delta < -5:
        explanations.append(f"Nutrition declined {abs(nutrition_delta):.1f}%")
    
    if participation_delta < -5:
        explanations.append(f"Participation declined {abs(participation_delta):.1f}%")
    
    if not explanations:
        return "Subtle decline pattern detected from personal baseline"
    
    explanation = ", ".join(explanations) + " from personal baseline"
    
    if duration_days > 1:
        explanation += f" for {duration_days} consecutive days"
    
    return explanation + "."


def load_csv_safely(file_path: Path) -> Optional[pd.DataFrame]:
    """Safely load CSV file, returning None if file doesn't exist or is invalid."""
    try:
        if not file_path.exists():
            return None
        df = pd.read_csv(file_path)
        return df if not df.empty else None
    except Exception:
        return None