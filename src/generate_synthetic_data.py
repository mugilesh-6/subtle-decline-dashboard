"""
Generate synthetic daily observation data for the Subtle Decline Dashboard.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from faker import Faker
from pathlib import Path
from typing import List, Dict, Any
import random

# Fixed random seed for reproducible results
RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)
fake = Faker()
Faker.seed(RANDOM_SEED)


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).resolve().parent.parent


def generate_patient_profiles() -> List[Dict[str, Any]]:
    """Generate individual patient profiles with different patterns."""
    patients = [
        # Core scenario patients (P001-P010)
        {
            'patient_id': 'P001',
            'patient_name': 'Alice Johnson',
            'pattern': 'stable',
            'mobility_baseline': 6500,
            'nutrition_baseline': 2000,
            'participation_baseline': 75
        },
        {
            'patient_id': 'P002',
            'patient_name': 'Bob Smith',
            'pattern': 'mobility_decline',
            'mobility_baseline': 7200,
            'nutrition_baseline': 2200,
            'participation_baseline': 90
        },
        {
            'patient_id': 'P003',
            'patient_name': 'Carol Wilson',
            'pattern': 'nutrition_decline',
            'mobility_baseline': 5800,
            'nutrition_baseline': 1800,
            'participation_baseline': 65
        },
        {
            'patient_id': 'P004',
            'patient_name': 'David Brown',
            'pattern': 'participation_decline',
            'mobility_baseline': 4500,
            'nutrition_baseline': 1600,
            'participation_baseline': 110
        },
        {
            'patient_id': 'P005',
            'patient_name': 'Emma Davis',
            'pattern': 'combined_decline',
            'mobility_baseline': 8000,
            'nutrition_baseline': 2400,
            'participation_baseline': 85
        },
        {
            'patient_id': 'P006',
            'patient_name': 'Frank Miller',
            'pattern': 'decline_recovery',
            'mobility_baseline': 6000,
            'nutrition_baseline': 1900,
            'participation_baseline': 70
        },
        {
            'patient_id': 'P007',
            'patient_name': 'Grace Taylor',
            'pattern': 'noisy_stable',
            'mobility_baseline': 5500,
            'nutrition_baseline': 1700,
            'participation_baseline': 60
        },
        {
            'patient_id': 'P008',
            'patient_name': 'Henry Anderson',
            'pattern': 'missing_data',
            'mobility_baseline': 7500,
            'nutrition_baseline': 2100,
            'participation_baseline': 95
        },
        {
            'patient_id': 'P009',
            'patient_name': 'Isabel Garcia',
            'pattern': 'stale_data',
            'mobility_baseline': 4800,
            'nutrition_baseline': 1500,
            'participation_baseline': 50
        },
        {
            'patient_id': 'P010',
            'patient_name': 'Jack Thompson',
            'pattern': 'rapid_decline_incident',
            'mobility_baseline': 6800,
            'nutrition_baseline': 2000,
            'participation_baseline': 80
        },
        # Additional patients to meet 20+ requirement (P011-P023)
        {
            'patient_id': 'P011',
            'patient_name': 'Karen White',
            'pattern': 'stable',
            'mobility_baseline': 5200,
            'nutrition_baseline': 1900,
            'participation_baseline': 68
        },
        {
            'patient_id': 'P012',
            'patient_name': 'Luke Martinez',
            'pattern': 'gradual_mobility_incident',
            'mobility_baseline': 7800,
            'nutrition_baseline': 2300,
            'participation_baseline': 88
        },
        {
            'patient_id': 'P013',
            'patient_name': 'Maria Rodriguez',
            'pattern': 'stable',
            'mobility_baseline': 4200,
            'nutrition_baseline': 1600,
            'participation_baseline': 52
        },
        {
            'patient_id': 'P014',
            'patient_name': 'Nathan Clark',
            'pattern': 'false_positive_pattern',
            'mobility_baseline': 6200,
            'nutrition_baseline': 2100,
            'participation_baseline': 72
        },
        {
            'patient_id': 'P015',
            'patient_name': 'Olivia Lewis',
            'pattern': 'nutrition_incident',
            'mobility_baseline': 5900,
            'nutrition_baseline': 2000,
            'participation_baseline': 78
        },
        {
            'patient_id': 'P016',
            'patient_name': 'Paul Walker',
            'pattern': 'stable',
            'mobility_baseline': 7100,
            'nutrition_baseline': 2400,
            'participation_baseline': 92
        },
        {
            'patient_id': 'P017',
            'patient_name': 'Quinn Hall',
            'pattern': 'temporary_variation',
            'mobility_baseline': 5600,
            'nutrition_baseline': 1800,
            'participation_baseline': 64
        },
        {
            'patient_id': 'P018',
            'patient_name': 'Rachel Young',
            'pattern': 'participation_incident',
            'mobility_baseline': 6400,
            'nutrition_baseline': 2200,
            'participation_baseline': 82
        },
        {
            'patient_id': 'P019',
            'patient_name': 'Samuel King',
            'pattern': 'insufficient_baseline',
            'mobility_baseline': 5800,
            'nutrition_baseline': 1950,
            'participation_baseline': 70
        },
        {
            'patient_id': 'P020',
            'patient_name': 'Tina Green',
            'pattern': 'stable',
            'mobility_baseline': 4800,
            'nutrition_baseline': 1700,
            'participation_baseline': 58
        },
        {
            'patient_id': 'P021',
            'patient_name': 'Victor Adams',
            'pattern': 'multi_domain_incident',
            'mobility_baseline': 6600,
            'nutrition_baseline': 2100,
            'participation_baseline': 76
        },
        {
            'patient_id': 'P022',
            'patient_name': 'Wendy Baker',
            'pattern': 'stable',
            'mobility_baseline': 5400,
            'nutrition_baseline': 1850,
            'participation_baseline': 66
        },
        {
            'patient_id': 'P023',
            'patient_name': 'Xavier Scott',
            'pattern': 'capacity_overflow',
            'mobility_baseline': 7000,
            'nutrition_baseline': 2250,
            'participation_baseline': 84
        }
    ]
    return patients


def apply_decline_pattern(base_value: float, day: int, pattern: str, metric: str, total_days: int = 90) -> float:
    """Apply specific decline patterns to base values."""
    # Add some natural daily variation
    daily_noise = np.random.normal(0, 0.05) * base_value
    
    if pattern == 'stable':
        return base_value + daily_noise
    
    elif pattern == 'mobility_decline' and metric == 'mobility':
        # Gradual decline starting around day 60 (more realistic timeline)
        if day > 60:
            decline_factor = (day - 60) * 0.015  # 1.5% decline per day
            return base_value * (1 - decline_factor) + daily_noise
        return base_value + daily_noise
    
    elif pattern == 'nutrition_decline' and metric == 'nutrition':
        # Gradual decline starting around day 65
        if day > 65:
            decline_factor = (day - 65) * 0.012  # 1.2% decline per day
            return base_value * (1 - decline_factor) + daily_noise
        return base_value + daily_noise
    
    elif pattern == 'participation_decline' and metric == 'participation':
        # Gradual decline starting around day 70
        if day > 70:
            decline_factor = (day - 70) * 0.018  # 1.8% decline per day
            return base_value * (1 - decline_factor) + daily_noise
        return base_value + daily_noise
    
    elif pattern == 'combined_decline':
        # All metrics decline after day 80 for hospitalization around day 90 (10-day lead time)
        if day > 80:
            decline_factor = (day - 80) * 0.014  # 1.4% decline per day
            return base_value * (1 - decline_factor) + daily_noise
        return base_value + daily_noise
    
    elif pattern == 'decline_recovery':
        # Decline from day 30-60, then recovery
        if 30 < day <= 60:
            decline_factor = (day - 30) * 0.012  # Decline
            return base_value * (1 - decline_factor) + daily_noise
        elif day > 60:
            # Recovery phase
            recovery_factor = (day - 60) * 0.008
            decline_at_60 = 0.012 * 30  # Max decline reached
            current_decline = max(0, decline_at_60 - recovery_factor)
            return base_value * (1 - current_decline) + daily_noise
        return base_value + daily_noise
    
    elif pattern == 'noisy_stable':
        # Stable but with high variability
        noise = np.random.normal(0, 0.15) * base_value
        return base_value + noise
    
    elif pattern == 'rapid_decline_incident':
        # Sharp decline before incident (around day 87, realistic 5-day lead time)
        if day > 82:
            decline_factor = (day - 82) * 0.025  # 2.5% decline per day
            return base_value * (1 - decline_factor) + daily_noise
        return base_value + daily_noise
    
    elif pattern == 'gradual_mobility_incident' and metric == 'mobility':
        # Gradual mobility decline leading to fall (around day 85, 7-day lead time) 
        if day > 78:
            decline_factor = (day - 78) * 0.020  # 2.0% decline per day
            return base_value * (1 - decline_factor) + daily_noise
        return base_value + daily_noise
    
    elif pattern == 'nutrition_incident' and metric == 'nutrition':
        # Nutrition decline leading to malnutrition (around day 89, 10-day lead time)
        if day > 79:
            decline_factor = (day - 79) * 0.015  # 1.5% decline per day
            return base_value * (1 - decline_factor) + daily_noise
        return base_value + daily_noise
    
    elif pattern == 'participation_incident' and metric == 'participation':
        # Participation decline leading to functional deterioration (around day 87, 8-day lead time)
        if day > 79:
            decline_factor = (day - 79) * 0.022  # 2.2% decline per day
            return base_value * (1 - decline_factor) + daily_noise
        return base_value + daily_noise
    
    elif pattern == 'multi_domain_incident':
        # Multi-domain decline leading to emergency visit (around day 88, 9-day lead time)
        if day > 79:
            decline_factor = (day - 79) * 0.018  # 1.8% decline per day
            return base_value * (1 - decline_factor) + daily_noise
        return base_value + daily_noise
    
    elif pattern == 'false_positive_pattern':
        # Temporary decline that doesn't lead to incident (days 40-50)
        if 40 < day <= 50:
            decline_factor = (day - 40) * 0.015
            return base_value * (1 - decline_factor) + daily_noise
        elif 50 < day <= 60:
            # Recovery
            recovery_factor = (day - 50) * 0.015
            decline_at_50 = 0.015 * 10
            current_decline = max(0, decline_at_50 - recovery_factor)
            return base_value * (1 - current_decline) + daily_noise
        return base_value + daily_noise
    
    elif pattern == 'temporary_variation':
        # Short-term variations that shouldn't trigger alerts
        if 20 < day <= 25 or 60 < day <= 62:
            decline_factor = 0.08  # 8% temporary decline
            return base_value * (1 - decline_factor) + daily_noise
        return base_value + daily_noise
    
    elif pattern == 'insufficient_baseline':
        # Patient starts monitoring late (only 20 days of baseline)
        if day <= 20:
            return base_value + daily_noise
        # Missing most early data
        if day <= 40 and random.random() < 0.6:
            return np.nan  # 60% missing data in baseline period
        return base_value + daily_noise
    
    elif pattern == 'capacity_overflow':
        # Multiple patients with alerts around same time
        if day > 78:
            decline_factor = (day - 78) * 0.020
            return base_value * (1 - decline_factor) + daily_noise
        return base_value + daily_noise
    
    else:
        return base_value + daily_noise


def generate_daily_observations() -> pd.DataFrame:
    """Generate 90 days of daily observations for all patients."""
    patients = generate_patient_profiles()
    observations = []
    
    # Generate dates for 90 days
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=89)
    date_range = pd.date_range(start=start_date, end=end_date)
    
    for patient in patients:
        pattern = patient['pattern']
        
        for day_idx, obs_date in enumerate(date_range):
            day_num = day_idx + 1
            
            # Handle missing data patterns
            if pattern == 'missing_data' and day_num > 70:
                # Skip observations after day 70
                continue
            
            if pattern == 'stale_data' and day_num > 87:
                # Skip recent observations to simulate stale data
                continue
            
            # Generate values based on pattern
            mobility_steps = apply_decline_pattern(
                patient['mobility_baseline'], day_num, pattern, 'mobility'
            )
            nutrition_kcal = apply_decline_pattern(
                patient['nutrition_baseline'], day_num, pattern, 'nutrition'
            )
            participation_minutes = apply_decline_pattern(
                patient['participation_baseline'], day_num, pattern, 'participation'
            )
            
            # Ensure reasonable bounds
            mobility_steps = max(500, min(15000, mobility_steps))
            nutrition_kcal = max(800, min(4000, nutrition_kcal))
            participation_minutes = max(0, min(180, participation_minutes))
            
            # Simulate data quality issues occasionally
            observation_quality = 'Good'
            data_source = 'Wearable Device'
            
            if random.random() < 0.05:  # 5% chance of quality issues
                observation_quality = random.choice(['Fair', 'Poor'])
                data_source = random.choice(['Manual Entry', 'Estimated', 'Wearable Device'])
            
            observation = {
                'patient_id': patient['patient_id'],
                'patient_name': patient['patient_name'],
                'observation_date': obs_date.strftime('%Y-%m-%d'),
                'mobility_steps': int(mobility_steps),
                'nutrition_kcal': int(nutrition_kcal),
                'participation_minutes': int(participation_minutes),
                'data_source': data_source,
                'observation_quality': observation_quality
            }
            
            observations.append(observation)
    
    return pd.DataFrame(observations)


def generate_incidents() -> pd.DataFrame:
    """Generate synthetic incidents for evaluation."""
    incidents = []
    
    # Current date for calculating incident dates
    current_date = datetime.now().date()
    
    # Patient P010 (rapid_decline_incident pattern) has a fall
    incidents.append({
        'incident_id': 'INC001',
        'patient_id': 'P010',
        'incident_date': (current_date - timedelta(days=5)).strftime('%Y-%m-%d'),  # Day 85
        'incident_type': 'Fall',
        'severity': 'Moderate'
    })
    
    # Patient P012 (gradual_mobility_incident) has a fall  
    incidents.append({
        'incident_id': 'INC002',
        'patient_id': 'P012',
        'incident_date': (current_date - timedelta(days=8)).strftime('%Y-%m-%d'),  # Day 82
        'incident_type': 'Fall',
        'severity': 'High'
    })
    
    # Patient P015 (nutrition_incident) has malnutrition
    incidents.append({
        'incident_id': 'INC003',
        'patient_id': 'P015',
        'incident_date': (current_date - timedelta(days=3)).strftime('%Y-%m-%d'),  # Day 87
        'incident_type': 'Severe Malnutrition',
        'severity': 'High'
    })
    
    # Patient P018 (participation_incident) has functional deterioration
    incidents.append({
        'incident_id': 'INC004',
        'patient_id': 'P018',
        'incident_date': (current_date - timedelta(days=6)).strftime('%Y-%m-%d'),  # Day 84
        'incident_type': 'Functional Deterioration',
        'severity': 'Moderate'
    })
    
    # Patient P021 (multi_domain_incident) has emergency visit
    incidents.append({
        'incident_id': 'INC005',
        'patient_id': 'P021',
        'incident_date': (current_date - timedelta(days=4)).strftime('%Y-%m-%d'),  # Day 86
        'incident_type': 'Emergency Visit',
        'severity': 'Moderate'
    })
    
    # Patient P005 (combined_decline) has hospitalization - longer decline but still realistic
    incidents.append({
        'incident_id': 'INC006',
        'patient_id': 'P005',
        'incident_date': (current_date - timedelta(days=2)).strftime('%Y-%m-%d'),  # Day 88
        'incident_type': 'Hospitalization',
        'severity': 'High'
    })
    
    # Patient P006 had an incident during their decline period (historical)
    incidents.append({
        'incident_id': 'INC007',
        'patient_id': 'P006',
        'incident_date': (current_date - timedelta(days=45)).strftime('%Y-%m-%d'),  # Day 45 (during decline phase)
        'incident_type': 'Emergency Visit',
        'severity': 'Moderate'
    })
    
    return pd.DataFrame(incidents)


def main():
    """Generate and save synthetic data files."""
    print("Generating synthetic daily observations...")
    
    # Get project root and data directory
    project_root = get_project_root()
    data_dir = project_root / "data"
    
    # Generate daily observations
    daily_data = generate_daily_observations()
    daily_file = data_dir / "synthetic_daily_data.csv"
    daily_data.to_csv(daily_file, index=False)
    print(f"✓ Generated {len(daily_data)} daily observations -> {daily_file}")
    
    # Generate incidents
    incidents_data = generate_incidents()
    incidents_file = data_dir / "synthetic_incidents.csv"
    incidents_data.to_csv(incidents_file, index=False)
    print(f"✓ Generated {len(incidents_data)} incidents -> {incidents_file}")
    
    # Print summary statistics
    print("\nData Summary:")
    print(f"- Patients: {daily_data['patient_id'].nunique()}")
    print(f"- Date range: {daily_data['observation_date'].min()} to {daily_data['observation_date'].max()}")
    print(f"- Total observations: {len(daily_data)}")
    print(f"- Data quality distribution:")
    print(daily_data['observation_quality'].value_counts().to_string())
    
    return daily_data, incidents_data


if __name__ == "__main__":
    main()