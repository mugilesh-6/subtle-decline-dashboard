# System Architecture

## Overview

The Subtle-Decline Dashboard follows a modular architecture designed for clarity, maintainability, and safety in healthcare decision support.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SYNTHETIC DATA SOURCES                       │
├─────────────────┬─────────────────┬─────────────────────────────┤
│   Mobility      │   Nutrition     │      Participation          │
│   Provider      │   Provider      │      Provider               │
│ (Wearable Data) │ (Meal Tracking) │   (Activity Records)        │
└─────────┬───────┴─────────┬───────┴─────────────┬───────────────┘
          │                 │                     │
          ▼                 ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                     DATA VALIDATION                             │
│  • Required columns check    • Data type validation            │
│  • Duplicate detection       • Range validation                │
│  • Missing value handling    • Date format validation          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   FRESHNESS ASSESSMENT                         │
│  • FRESH: ≤1 day old       • STALE: 2-3 days old             │
│  • MISSING: >3 days old    • Explicit status indicators       │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PERSONAL BASELINE                            │
│  • 30-day baseline period  • Individual patient patterns      │
│  • Domain-specific means   • Minimum 15 valid observations    │
│  • Variability assessment  • Baseline sufficiency checks      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   DECLINE DETECTION                            │
│  • Personal baseline comparison                                │
│  • Percentage change calculation                               │
│  • Multi-domain weighted scoring                               │
│  • Consecutive day requirement (≥2 days)                       │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     ALERT ENGINE                               │
│  • Composite score calculation                                 │
│  • Severity classification (LOW/MEDIUM/HIGH)                   │
│  • Explainable alert generation                                │
│  • Safe fallback for poor data quality                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                  CAPACITY MANAGEMENT                           │
│  • Coordinator assignment limits                               │
│  • Workload distribution                                       │
│  • Over-capacity warnings                                      │
│  • Manual review queue                                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                 ROLE-BASED DASHBOARD                           │
├────────────┬─────────────┬─────────────┬────────────────────────┤
│   Family   │ Coordinator │  Clinician  │     Administrator      │
│    View    │    View     │    View     │        View            │
├────────────┴─────────────┴─────────────┴────────────────────────┤
│  • Simple status         • Detailed analysis                   │
│  • Key trends           • Clinical evidence                     │
│  • Important alerts     • System performance                   │
│  • Safety disclaimers   • Risk assessments                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              EXPERIMENT & EVALUATION                           │
│  • Alert-to-incident matching                                  │
│  • Early detection measurement                                 │
│  • Performance metrics (Precision/Recall/F1)                   │
│  • False positive/negative analysis                             │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Data Sources Layer

**Purpose**: Simulate multiple healthcare provider systems that contribute patient observations.

**Components**:
- **Mobility Provider**: Wearable devices, step counters, activity trackers
- **Nutrition Provider**: Meal tracking systems, dietary logs, calorie counters  
- **Participation Provider**: Activity schedules, therapy attendance, social engagement

**Data Flow**:
- Each provider generates timestamped observations
- Observations include quality indicators and source identification
- Data arrives at different intervals and may have gaps or delays

### 2. Data Validation Layer

**Purpose**: Ensure data integrity and identify quality issues before processing.

**Validation Rules**:
- Required columns: `patient_id`, `observation_date`, `mobility_steps`, `nutrition_kcal`, `participation_minutes`
- Data types: Numeric values for metrics, valid dates for observations
- Range checks: Reasonable bounds for each metric (e.g., steps 0-25000)
- Duplicate detection: Same patient on same date
- Missing value patterns: Identify systematic gaps

**Error Handling**:
- Log validation failures without crashing
- Provide user-friendly error messages
- Continue processing valid portions of data

### 3. Freshness Assessment Layer

**Purpose**: Classify data recency and reliability for decision-making.

**Freshness States**:
- **FRESH** (≤1 day): Suitable for current status assessment
- **STALE** (2-3 days): Usable but with appropriate caveats
- **MISSING** (>3 days): Insufficient for reliable automated assessment

**Business Logic**:
- Each patient has independent freshness assessment
- Dashboard displays freshness status prominently
- Alerts include freshness context
- Safe fallback triggered for missing/stale critical data

### 4. Personal Baseline Layer

**Purpose**: Establish individual patient patterns rather than using population averages.

**Baseline Calculation**:
- Use first 30 valid observation days per patient
- Calculate domain-specific means (mobility, nutrition, participation)
- Require minimum 15 valid observations for baseline sufficiency
- Store baseline metadata (period length, data quality)

**Advantages**:
- Accounts for individual patient capabilities and lifestyle
- More sensitive to personal pattern changes
- Reduces false positives from population variance
- Supports personalized care approaches

### 5. Decline Detection Layer

**Purpose**: Identify meaningful deviations from personal baseline patterns.

**Detection Algorithm**:
1. Calculate percentage change from baseline for each domain
2. Apply decline component scoring (only negative changes contribute)
3. Normalize against reasonable thresholds (20% decline = high contribution)
4. Generate domain-specific decline indicators

**Mathematical Model**:
```python
delta_percent = (current_value - baseline_value) / baseline_value * 100
decline_component = max(0, -delta_percent) / 20.0  # Capped at 1.0
```

### 6. Alert Engine Layer

**Purpose**: Generate actionable, explainable alerts based on sustained decline patterns.

**Alert Generation Process**:
1. **Composite Scoring**: Weight domain contributions (Mobility 40%, Nutrition 30%, Participation 30%)
2. **Consecutive Day Requirement**: Minimum 2 days of meaningful decline
3. **Severity Classification**: LOW (≥0.20), MEDIUM (≥0.35), HIGH (≥0.50)
4. **Explanation Generation**: Human-readable alert reasoning
5. **Safe Fallback**: Refuse to generate alerts when data quality is insufficient

**Alert Structure**:
```json
{
  "alert_id": "ALT_P001_20260825",
  "patient_id": "P001",
  "severity": "MEDIUM",
  "composite_score": 0.42,
  "explanation": "Mobility declined 18%, nutrition declined 12% from personal baseline for 3 consecutive days",
  "domains_affected": "Mobility, Nutrition",
  "duration_days": 3
}
```

### 7. Capacity Management Layer

**Purpose**: Prevent care coordinator overload and ensure appropriate workload distribution.

**Capacity Rules**:
- Maximum 8 high-priority alerts per coordinator
- Warning at 80% capacity utilization
- Over-capacity alerts routed to manual review queue
- Load balancing across available coordinators

**Failure Modes**:
- **Capacity Exceeded**: New alerts wait for coordinator availability
- **No Available Coordinators**: Alerts escalated to supervisory review
- **System Overload**: Emergency capacity expansion protocols

### 8. Role-Based Dashboard Layer

**Purpose**: Present appropriate information and controls for different stakeholder roles.

#### Family View
- **Focus**: Simple, understandable status and trends
- **Content**: Overall patient status, key metrics, important alerts
- **Language**: Non-technical, reassuring but informative
- **Actions**: View trends, understand alerts, contact care team

#### Coordinator View  
- **Focus**: Efficient case management and triage
- **Content**: Alert queue, capacity status, patient priority ranking
- **Language**: Care coordination terminology
- **Actions**: Assign cases, update status, manage workload

#### Clinician View
- **Focus**: Clinical evidence and detailed patient assessment  
- **Content**: Baseline comparisons, trend analysis, alert evidence
- **Language**: Clinical terminology with statistical details
- **Actions**: Review evidence, validate alerts, adjust care plans

#### Administrator View
- **Focus**: System performance and organizational oversight
- **Content**: Performance metrics, capacity utilization, system health
- **Language**: Management and quality metrics
- **Actions**: Monitor performance, assess targets, resource planning

### 9. Experiment & Evaluation Layer

**Purpose**: Measure and validate system performance against known outcomes.

**Evaluation Process**:
1. **Alert-Incident Matching**: Connect generated alerts to synthetic major events
2. **Lead Time Calculation**: Measure days between first alert and incident
3. **Performance Metrics**: Calculate precision, recall, F1, early detection rate
4. **Error Analysis**: Categorize false positives and false negatives
5. **Target Assessment**: Compare results against predefined success criteria

**Key Metrics**:
- **Early Detection Rate**: Percentage of incidents detected ≥1 day in advance
- **Precision**: Accuracy of alert predictions
- **Recall**: Coverage of actual incidents  
- **Average Lead Time**: Mean advance warning period
- **Target Achievement**: Meeting 70% early detection goal

## Data Flow Architecture

### 1. Data Ingestion Flow
```
Provider Systems → CSV Files → Pandas DataFrames → Validation → Storage
```

### 2. Processing Flow  
```
Raw Data → Freshness Check → Baseline Calculation → Decline Detection → Alert Generation
```

### 3. User Interface Flow
```
Role Selection → Data Loading → View Filtering → Interactive Visualization → Action Items
```

### 4. Evaluation Flow
```
Historical Alerts → Incident Matching → Performance Calculation → Results Reporting
```

## Technical Implementation

### Core Technologies
- **Python 3.10+**: Primary programming language
- **Pandas**: Data manipulation and analysis
- **NumPy**: Numerical computations  
- **Streamlit**: Web dashboard framework
- **Plotly**: Interactive visualization
- **Pytest**: Automated testing

### Design Patterns
- **Modular Architecture**: Clear separation of concerns
- **Configuration-Driven**: Adjustable thresholds and parameters
- **Error Handling**: Graceful degradation and user feedback
- **Caching Strategy**: Efficient data loading and processing
- **Testable Components**: Unit and integration test coverage

### Security Considerations
- **Synthetic Data Only**: No real patient information processed
- **Local Processing**: No external data transmission
- **Access Control**: Role-based view restrictions
- **Audit Trail**: Complete alert and decision history
- **Safe Defaults**: Conservative approach to recommendations

### Scalability Considerations
- **File-Based Storage**: Simple deployment and maintenance
- **Configurable Limits**: Adjustable capacity and thresholds  
- **Modular Components**: Easy to extend and modify
- **Performance Monitoring**: Built-in system health metrics
- **Error Recovery**: Robust handling of edge cases

## Failure Modes and Resilience

### Data Quality Failures
- **Missing Data**: Safe fallback mode with explicit warnings
- **Stale Data**: Clear status indicators and reduced confidence
- **Invalid Data**: Validation errors with user-friendly messages
- **Inconsistent Data**: Quality scoring and reliability indicators

### System Performance Failures
- **Overload**: Capacity management and manual review queues
- **Processing Errors**: Graceful error handling and logging
- **UI Failures**: Fallback displays and error messages
- **Integration Issues**: Isolated component failures

### Operational Failures  
- **False Positives**: Error analysis and threshold adjustment
- **False Negatives**: Missed case review and system improvement
- **User Errors**: Clear interfaces and safety confirmations
- **Workflow Issues**: Manual override and escalation paths

## Integration Points

### Current Integration
- **File System**: CSV data storage and retrieval
- **Local Processing**: In-memory data manipulation
- **Web Interface**: Browser-based dashboard access
- **Test Framework**: Automated validation and verification

### Future Integration Opportunities
- **EHR Systems**: Electronic health record connectivity
- **Provider APIs**: Real-time data streaming  
- **Notification Systems**: Automated alert delivery
- **Care Management**: Workflow integration
- **Analytics Platforms**: Advanced reporting and insights

---

*This architecture supports the current MVP requirements while providing a foundation for future enhancements and real-world deployment.*