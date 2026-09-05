# Subtle-Decline Trend Dashboard

**An end-to-end Streamlit decision-support prototype that combines mobility, nutrition, and participation signals to identify sustained changes relative to personal baselines, with explainable alerts, freshness handling, role-based views, and synthetic evaluation.**

A comprehensive decision-support dashboard for monitoring functional decline in older adults across mobility, nutrition, and participation domains. The system combines synthetic daily observations from multiple care sources to detect subtle changes before they become major adverse events.

## ⚠️ Important Safety Disclaimer

**This is a demonstration prototype using synthetic data. It is NOT a medical device and must NOT be used to diagnose diseases or make clinical decisions without appropriate professional oversight.**

## Problem Statement

Families and care coordinators often notice functional decline in older adults only after a major adverse event occurs (falls, hospitalizations, severe malnutrition). This reactive approach can lead to:

- Late intervention opportunities
- Preventable emergency situations  
- Increased healthcare costs
- Reduced quality of life

## Solution Approach

The Subtle-Decline Dashboard provides:

- **Personal Baseline Comparison**: Individual baselines rather than population averages
- **Multi-Domain Monitoring**: Mobility, nutrition, and participation tracking
- **Sustained Decline Detection**: Requires consecutive days of meaningful decline 
- **Data Freshness Management**: Explicit handling of stale/missing data
- **Safe Fallback Mode**: Clear warnings when data quality is insufficient
- **Role-Based Views**: Tailored interfaces for families, coordinators, clinicians, and administrators
- **Early Detection Measurement**: Quantified performance against synthetic incidents

## Features

### Core Functionality
- ✅ Synthetic patient data generation (23 patients, 90 days)
- ✅ Personal baseline calculation (30-day baseline period)
- ✅ Composite decline scoring with domain weights
- ✅ Consecutive-day decline detection (minimum 2 days)
- ✅ Explainable alert generation
- ✅ Data freshness status (FRESH/STALE/MISSING)
- ✅ Safe fallback mode for insufficient data
- ✅ Capacity management for care coordinators

### Dashboard Views
- 👨‍👩‍👧‍👦 **Family View**: Simple status, trends, and alerts
- 🏥 **Care Coordinator View**: Alert queue, capacity management, priority filtering
- 🩺 **Clinician View**: Detailed trends, baseline comparison, alert evidence
- ⚙️ **Administrator View**: System health, performance metrics, experiment results

### Performance Measurement
- 🧪 Experiment evaluation against synthetic incidents
- 📊 Early detection rate calculation
- 📈 Precision, recall, and F1 score metrics
- 🔍 False positive and false negative analysis

## Architecture

```
Data Sources → Data Validation → Freshness Assessment → Personal Baseline
     ↓              ↓                    ↓                     ↓
Decline Detection → Alert Engine → Capacity Management → Role-Based Dashboard
     ↓              ↓                    ↓                     ↓
Performance → Experiment → Evaluation → Evidence & Documentation
```

## Technology Stack

- **Python 3.10+**: Core application logic
- **Streamlit**: Web dashboard interface  
- **Pandas**: Data processing and analysis
- **NumPy**: Numerical computations
- **Plotly**: Interactive trend visualization
- **Pytest**: Automated testing framework
- **Faker**: Synthetic data generation

## Installation

### Prerequisites
- Python 3.10 or higher
- pip package manager

### Setup Instructions

1. **Clone/Download Project**
   ```bash
   cd subtle-decline-dashboard
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Generate Synthetic Data**
   ```bash
   python src/generate_synthetic_data.py
   ```

4. **Generate Alerts**
   ```bash
   python src/alert_engine.py
   ```

5. **Run Experiment Evaluation**
   ```bash
   python src/experiment.py
   ```

6. **Launch Dashboard**
   ```bash
   streamlit run src/dashboard.py
   ```

7. **Run Tests**
   ```bash
   pytest tests/
   ```

## Quick Start Commands

Execute all components in sequence:

```bash
# Setup
pip install -r requirements.txt

# Data Generation
python src/generate_synthetic_data.py

# Alert Generation  
python src/alert_engine.py

# Experiment Evaluation
python src/experiment.py

# Launch Dashboard
streamlit run src/dashboard.py

# Run Tests
pytest tests/
```

## Project Structure

```
subtle-decline-dashboard/
├── data/                          # Generated data files
│   ├── synthetic_daily_data.csv   # Daily patient observations
│   ├── synthetic_incidents.csv    # Major adverse events
│   ├── generated_alerts.csv       # System-generated alerts
│   └── alert_summary.json         # Experiment results
├── src/                           # Source code
│   ├── generate_synthetic_data.py # Data generation
│   ├── alert_engine.py           # Decline detection logic
│   ├── dashboard.py              # Streamlit interface
│   ├── experiment.py             # Performance evaluation
│   └── utils.py                  # Utility functions
├── tests/                        # Automated tests
│   ├── test_edge_cases.py        # Edge case testing
│   └── test_freshness.py         # Data freshness testing
├── docs/                         # Documentation
│   ├── architecture_diagram.md   # System architecture
│   ├── data_schema.md           # Data structure documentation
│   ├── risk_register.md         # Risk analysis
│   ├── user_guide.md            # User instructions
│   └── failure_modes.md         # Operational failure analysis
├── requirements.txt              # Python dependencies
└── README.md                    # This file
```

## Dataset

The system uses synthetic data for demonstration and research purposes:

### Generated Dataset
- **23 synthetic older-adult profiles**
- **90-day observation period** (2026-06-08 to 2026-09-05)
- **2,047 daily observations** across all patients
- **7 synthetic incidents** (falls, hospitalizations, emergency visits)
- **64 generated alerts** (LOW: 35, MEDIUM: 21, HIGH: 8)

### Data Structure

### Patient Profiles (23 different patterns)
- **P001-P023**: Comprehensive scenarios covering:
  - Stable baseline patients  
  - Gradual single-domain decline (mobility/nutrition/participation)
  - Multi-domain decline patterns
  - Recovery after decline
  - Missing and stale data scenarios
  - False positive patterns  
  - Rapid-onset incident scenarios

### Observation Metrics
- **Mobility**: Daily steps (2,500-10,000 range)
- **Nutrition**: Daily calories (1,200-2,800 range)  
- **Participation**: Activity minutes (10-120 range)

## Alert Generation

### Decline Detection Logic
1. **Personal Baseline**: Calculate from first 30 valid observations
2. **Domain Changes**: Compare current values to personal baseline
3. **Composite Scoring**: Weighted combination (Mobility 40%, Nutrition 30%, Participation 30%)
4. **Sustained Pattern**: Require minimum 2 consecutive decline days
5. **Severity Classification**: LOW (≥0.20), MEDIUM (≥0.35), HIGH (≥0.50)

### Safe Fallback Conditions
- Insufficient baseline data (< 15 observations)
- Missing critical metrics
- Stale data (> 1 day old)  
- Poor observation quality
- Invalid numeric values

## Dashboard Usage

### Family View
- Select patient from sidebar
- View overall status and risk level
- Monitor mobility, nutrition, participation trends
- Review active alerts and recent incidents
- Access simple explanations in non-technical language

### Care Coordinator View  
- Monitor alert queue across all patients
- Filter alerts by severity (HIGH/MEDIUM/LOW)
- Track capacity utilization and workload
- Identify patients with stale/missing data
- Manage alert assignments and follow-up

### Clinician View
- Deep-dive into individual patient data
- Compare current values against personal baselines
- Review detailed trend charts with alert markers
- Examine alert evidence and explanations
- Access raw observation data and quality metrics

### Administrator View
- Monitor system health and data quality
- Review performance metrics and experiment results
- Track alert distribution by severity
- Assess data freshness across patient population
- Evaluate target achievement and detection rates

## Experiment Evaluation

The experiment measures early detection performance:

### Key Metrics
- **Precision**: True positives / (True positives + False positives)
- **Recall**: True positives / (True positives + False negatives)
- **F1 Score**: Harmonic mean of precision and recall
- **Early Detection Rate**: Incidents detected ≥1 day before occurrence
- **Average Lead Time**: Mean days between first alert and incident

### Measured Performance (Current Results)
- **Target**: Detect ≥70% of major events at least 2 days in advance  
- **Measured Result**: 14.3% (1 of 7 incidents detected ≥2 days early)
- **Status**: **TARGET NOT ACHIEVED**
- **Detection Details**: 
  - Incidents detected: 1/7 (14.3% recall)
  - False positives: 63 alerts without subsequent incidents (1.6% precision)
  - Average lead time: 5.0 days (for detected incidents)
- **Error Analysis**: System demonstrates high false positive rate, indicating need for improved specificity

## Testing

### Automated Test Coverage
- **Edge Cases**: Empty data, missing columns, invalid values, insufficient baselines
- **Data Freshness**: Fresh, stale, and missing data scenarios  
- **Decline Detection**: Stable patients, gradual decline, multi-domain decline, recovery patterns
- **Utility Functions**: Percentage changes, severity classification, capacity management

### Running Tests
```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run specific test file
pytest tests/test_edge_cases.py
```

**Expected Result**: 38 tests passing

## Configuration

### Alert Severity Thresholds
```python
SEVERITY_THRESHOLDS = {
    'LOW': 0.20,      # 20% composite decline score
    'MEDIUM': 0.35,   # 35% composite decline score  
    'HIGH': 0.50      # 50% composite decline score
}
```

### Domain Weights
```python
DOMAIN_WEIGHTS = {
    'mobility': 0.40,      # 40% weight
    'nutrition': 0.30,     # 30% weight
    'participation': 0.30  # 30% weight
}
```

### System Limits
```python
MIN_CONSECUTIVE_DAYS = 2        # Minimum decline duration
BASELINE_PERIOD_DAYS = 30       # Baseline calculation period
COORDINATOR_MAX_CAPACITY = 8    # Maximum alerts per coordinator
EARLY_DETECTION_WINDOW_DAYS = 7 # Early detection evaluation window
```

## Data Schema

### Daily Observations
- `patient_id`: Unique patient identifier
- `patient_name`: Patient display name
- `observation_date`: Date of observation (YYYY-MM-DD)
- `mobility_steps`: Daily step count
- `nutrition_kcal`: Daily caloric intake
- `participation_minutes`: Daily activity participation
- `data_source`: Source system (e.g., "Wearable Device")
- `observation_quality`: Data quality ("Good", "Fair", "Poor")

### Generated Alerts
- `alert_id`: Unique alert identifier
- `patient_id`: Associated patient  
- `decline_start_date`: When decline pattern began
- `alert_date`: When alert was generated
- `duration_days`: Length of decline period
- `domains_affected`: Which domains show decline
- `composite_score`: Calculated decline severity
- `severity`: Classification (LOW/MEDIUM/HIGH)
- `explanation`: Human-readable alert reason

## Known Limitations

### Current System Limitations
- **Detection Performance**: Currently achieving 14.3% recall vs 70% target
- **High False Positive Rate**: 63 false alerts for 1 true detection (precision 1.6%)
- **Algorithmic Limitations**: Rule-based detection may be too sensitive
- **Rapid-Onset Events**: Cannot reliably detect incidents with <2 day warning periods
- **Data Patterns**: May require more sophisticated pattern recognition for subtle decline

### Operational Limitations  
- Requires consistent daily observations
- Cannot detect rapid-onset emergencies
- May generate false positives during temporary illness
- Depends on data quality from external sources
- Limited to three monitored domains

### Clinical Limitations
- **NOT a medical diagnostic tool**
- **NOT validated for clinical decision-making**
- **Requires human professional oversight**
- **Does not replace clinical judgment**
- **Synthetic data does not reflect real patient complexity**

## Safety Considerations

### Risk Mitigation
1. **Clear Disclaimers**: Every interface includes medical disclaimer
2. **Safe Fallback**: System refuses recommendations with poor data quality  
3. **Human Oversight**: All alerts require professional review
4. **Data Quality Warnings**: Explicit stale/missing data indicators
5. **Capacity Limits**: Prevents coordinator overload
6. **Audit Trail**: Complete alert history and explanations

### Data Privacy
- Uses only synthetic/test data
- No real patient information processed
- No external data transmission  
- Local file-based storage only

## Future Improvements

### Technical Enhancements
- Machine learning-based decline detection
- Personalized domain weights and thresholds  
- Integration with real electronic health records
- Mobile application for family members
- Advanced time-series analysis

### Clinical Enhancements  
- Additional monitoring domains (sleep, cognition, social)
- Clinical decision support integration
- Care plan recommendation engine
- Provider workflow optimization
- Outcome tracking and validation

### Operational Enhancements
- Real-time data streaming
- Automated care coordination workflows
- Family notification systems
- Quality improvement analytics
- Multi-site deployment support

## Support and Documentation

### Additional Resources
- `docs/user_guide.md`: Detailed user instructions
- `docs/risk_register.md`: Complete risk analysis  
- `docs/failure_modes.md`: Operational failure scenarios
- `docs/architecture_diagram.md`: Technical architecture
- `docs/data_schema.md`: Complete data documentation

### Getting Help
- Review test files for usage examples
- Check experiment output for performance validation
- Examine generated alerts for detection patterns
- Run dashboard locally for interactive exploration

## License and Disclaimer

**PROTOTYPE SYSTEM FOR DEMONSTRATION PURPOSES ONLY**

This software is provided "as is" without warranty of any kind. It is intended solely for educational, research, and demonstration purposes. The system:

- Uses synthetic data only
- Is NOT intended for clinical use  
- Does NOT provide medical advice
- Requires professional oversight for any care decisions
- Has NOT been validated in clinical settings

For any care coordination decisions, consult with qualified healthcare professionals and follow established clinical protocols.

---

*Last Updated: September 2026*  
*Version: 1.0.0 - MVP Prototype*