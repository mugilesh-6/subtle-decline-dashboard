# Validation Documentation

## Overview

This document defines the validation approach, metrics definitions, and performance evaluation methodology for the Subtle-Decline Dashboard. It ensures mathematical correctness and clinical relevance of all experiment results.

**CRITICAL SAFETY REMINDER**: This system uses synthetic data and is designed for demonstration/research purposes only. It is NOT a medical device and requires appropriate professional oversight for any real-world application.

---

## Metric Definitions

### Core Principle: Incident-Based Evaluation

**CRITICAL**: All performance metrics are calculated at the **incident level**, not the alert level. Multiple alerts preceding the same incident count as **one successful detection**, not multiple detections.

### Primary Metrics

#### True Positive (Incident-Based)
- **Definition**: A major incident where at least one reliable alert occurred before the incident within the evaluation window (7 days)
- **Counting Rule**: Each incident can contribute at most **ONE** true positive, regardless of how many alerts preceded it
- **Lead Time Calculation**: Uses the **FIRST** alert before the incident, not all alerts

**Example**:
```
Patient P001 Fall on Day 85
Alerts: Day 80, Day 82, Day 84
Result: 1 True Positive (not 3)
Lead Time: 5 days (from first alert on Day 80)
```

#### False Negative (Incident-Based)
- **Definition**: A major incident where no reliable alert occurred before the incident within the evaluation window
- **Counting Rule**: Each missed incident counts as one false negative

#### False Positive (Alert-Based)
- **Definition**: An alert where no qualifying major incident occurs within the evaluation window after the alert
- **Counting Rule**: Each unmatched alert counts as one false positive

### Performance Calculations

#### Recall (Sensitivity)
```
Recall = Number of Incidents Detected / Total Number of Incidents
```
- **Valid Range**: 0% to 100%
- **Mathematical Constraint**: Cannot exceed 100% under any circumstances
- **Clinical Meaning**: Percentage of actual incidents that were detected in advance

#### Precision (Positive Predictive Value)
```
Precision = Number of Incidents Correctly Detected / Total Number of Alerts
```
- **Valid Range**: 0% to 100%
- **Clinical Meaning**: Percentage of alerts that correctly predicted an incident

#### Early Detection Rate
```
Early Detection Rate = Incidents Detected ≥N Days Early / Total Incidents
```
- **Variants**: ≥1 day, ≥2 days, ≥3 days, ≥5 days early
- **Valid Range**: 0% to 100%
- **Target Metric**: ≥2 days early detection rate

#### F1 Score
```
F1 = 2 × (Precision × Recall) / (Precision + Recall)
```
- **Valid Range**: 0.0 to 1.0
- **Clinical Meaning**: Balanced measure of detection accuracy

### Lead Time Analysis

#### Lead Time Calculation
- **Method**: Days between first alert and incident occurrence
- **Formula**: `Lead Time = Incident Date - First Alert Date`
- **Minimum**: 0 days (same-day detection, but not counted as early detection)
- **Maximum**: 7 days (evaluation window limit)

#### Lead Time Statistics
- **Mean Lead Time**: Average advance warning period
- **Median Lead Time**: Middle value of lead time distribution  
- **Range**: Minimum to maximum lead time observed
- **Distribution**: Percentage of detections by lead time category

---

## Validation Rules

### Mathematical Constraints

1. **Recall Bounds**: 0% ≤ Recall ≤ 100%
2. **Precision Bounds**: 0% ≤ Precision ≤ 100%  
3. **Detection Rate Bounds**: 0% ≤ Early Detection Rate ≤ 100%
4. **Incident Uniqueness**: Each incident counted exactly once
5. **Alert Uniqueness**: Each alert matched to at most one incident

### Data Quality Requirements

#### Minimum Data Standards
- **Patients**: ≥20 synthetic patients
- **Observation Period**: ≥90 days
- **Incidents**: 5-10 major adverse events
- **Baseline Period**: ≥30 days per patient (minimum 15 valid observations)

#### Data Completeness
- **Required Fields**: All primary data fields present
- **Missing Data**: <30% missing observations per patient
- **Data Quality**: Explicit quality indicators (Good/Fair/Poor)

### Experimental Validity

#### Reproducibility
- **Fixed Random Seed**: All random processes use seed=42
- **Deterministic Results**: Same inputs produce identical outputs
- **Version Control**: All algorithm parameters documented

#### Realistic Scenarios
- **Lead Times**: 3-14 days typical (not 40+ days)
- **Decline Patterns**: Gradual, realistic progression
- **Patient Diversity**: Multiple decline patterns represented
- **False Positives**: Temporary variations that recover

---

## Target Achievement Evaluation

### Primary Target
**Detect ≥70% of major incidents ≥2 days before occurrence**

### Evaluation Method
```
Target Achievement = (Incidents Detected ≥2 Days Early / Total Incidents) ≥ 0.70
```

### Result Interpretation
- **Target Achieved**: Detection rate ≥70%
- **Target Not Achieved**: Detection rate <70%
- **Reporting**: Report actual measured results, not manipulated values

### Secondary Targets
- **False Positive Rate**: <30% of alerts
- **Mean Lead Time**: ≥3 days advance warning
- **System Availability**: >95% uptime (fresh data)

---

## Error Analysis Framework

### True Positive Analysis
For each successful detection:
- **Patient ID**: Patient identifier
- **Incident Type**: Type of adverse event
- **Alert Date**: Date of first alert
- **Incident Date**: Date of adverse event
- **Lead Time**: Days of advance warning
- **Domains Affected**: Which metrics showed decline
- **Composite Score**: Decline severity measure

### False Positive Analysis
For each unmatched alert:
- **Patient ID**: Patient identifier
- **Alert Date**: Date of alert generation
- **Alert Severity**: HIGH/MEDIUM/LOW
- **Likely Cause**: Temporary variation, recovery, noise, etc.
- **Duration**: How long the alert pattern lasted
- **Outcome**: What actually happened (recovery, stable, etc.)

### False Negative Analysis  
For each missed incident:
- **Patient ID**: Patient identifier
- **Incident Date**: Date of adverse event
- **Incident Type**: Type of adverse event
- **Why Missed**: Rapid onset, missing data, weak signal, etc.
- **Available Data**: What observations were available
- **Potential Signals**: Any detectable patterns that were missed

---

## Statistical Validation

### Confidence Intervals
For key metrics with sufficient sample size:
- **95% Confidence Intervals**: For recall, precision, detection rates
- **Sample Size Considerations**: Note limitations with small incident counts
- **Statistical Significance**: Avoid over-interpreting small sample results

### Performance Stability
- **Cross-Validation**: Test with different random seeds where appropriate
- **Sensitivity Analysis**: Evaluate impact of threshold changes
- **Robustness Testing**: Performance with varying data quality

---

## Clinical Validation Framework

### Stakeholder Validation (Simulated)
Since this is a prototype with synthetic data, validation includes:

#### Family User Validation
- **Understandability**: Are alerts clear and actionable?
- **Trust Level**: Appropriate confidence in recommendations
- **Workflow Integration**: Fits into family care routines
- **Safety Awareness**: Understands system limitations

#### Care Coordinator Validation  
- **Workflow Efficiency**: Reduces coordination burden
- **Priority Clarity**: High-priority cases easily identified
- **Capacity Management**: Workload stays within limits
- **Evidence Quality**: Sufficient detail for decision-making

#### Clinician Validation
- **Clinical Relevance**: Alerts correspond to meaningful decline
- **Evidence Sufficiency**: Adequate data for clinical assessment
- **Integration**: Complements existing clinical surveillance
- **Safety Features**: Appropriate disclaimers and limitations

### Validation Questionnaire Results (Simulated)
*Note: These are simulated responses for demonstration purposes*

| Question | Family | Coordinator | Clinician | Score |
|----------|---------|-------------|-----------|-------|
| Alert Clarity | Good | Excellent | Good | 4.2/5 |
| Trust Level | Appropriate | High | Appropriate | 4.0/5 |
| Workflow Fit | Good | Excellent | Good | 4.1/5 |
| Safety Awareness | High | High | High | 4.8/5 |

---

## Limitations and Constraints

### Technical Limitations
- **Synthetic Data Only**: Results do not reflect real patient complexity
- **Limited Scope**: Only three domains monitored
- **Simple Algorithms**: Rule-based detection, not machine learning
- **Small Sample Size**: Limited number of incidents for robust statistics

### Clinical Limitations  
- **Not Validated Clinically**: No real-world patient outcomes data
- **Professional Oversight Required**: Cannot replace clinical judgment
- **Context Limitations**: May miss important clinical context
- **Rapid Events**: Cannot detect sudden-onset emergencies

### Statistical Limitations
- **Sample Size**: Small number of incidents limits statistical power
- **Selection Bias**: Synthetic patterns may not reflect real distributions
- **Validation Bias**: Same team created data and evaluation
- **Generalizability**: Results may not apply to different populations

---

## Quality Assurance

### Automated Validation
- **Unit Tests**: 30+ automated tests covering edge cases
- **Metric Validation**: Mathematical constraint checking
- **Data Quality Tests**: Input validation and completeness
- **Regression Tests**: Ensure changes don't break existing functionality

### Manual Review Process
- **Code Review**: All algorithms reviewed for correctness
- **Data Review**: Synthetic data patterns validated for realism
- **Results Review**: Performance metrics manually verified
- **Documentation Review**: All claims supported by evidence

### Continuous Monitoring
- **Performance Tracking**: Monitor key metrics over time
- **Error Analysis**: Regular review of false positives/negatives
- **User Feedback**: Collect and analyze user experiences
- **System Health**: Monitor data quality and availability

---

## Reporting Standards

### Required Report Elements
1. **Dataset Characteristics**: Patients, days, observations, incidents
2. **Performance Metrics**: Recall, precision, F1, detection rates  
3. **Target Achievement**: Measured vs. target performance
4. **Lead Time Analysis**: Mean, median, distribution of advance warning
5. **Error Analysis**: Examples of true/false positives and negatives
6. **Limitations**: Clear statement of system constraints
7. **Safety Disclaimers**: Appropriate warnings about system use

### Forbidden Claims
- **Clinical Accuracy**: Cannot claim clinical validation
- **Medical Diagnosis**: Cannot claim diagnostic capability  
- **Perfect Performance**: Cannot claim 100% accuracy without evidence
- **Production Ready**: Cannot claim ready for clinical deployment
- **Regulatory Approval**: Cannot imply FDA or other regulatory approval

---

*Validation Documentation Version: 1.0*  
*Last Updated: September 2026*  
*Next Review: December 2026*