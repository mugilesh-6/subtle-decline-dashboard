#!/bin/bash

# Subtle-Decline Dashboard - Complete Experiment Execution Script
# This script runs the complete workflow from data generation to evaluation

echo "=========================================="
echo "Subtle-Decline Dashboard Experiment"
echo "=========================================="
echo

# Function to check if command succeeded
check_success() {
    if [ $? -eq 0 ]; then
        echo "✓ $1 completed successfully"
        echo
    else
        echo "✗ $1 failed"
        exit 1
    fi
}

# Step 1: Generate Synthetic Data
echo "Step 1: Generating synthetic patient data..."
python src/generate_synthetic_data.py
check_success "Synthetic data generation"

# Step 2: Generate Alerts
echo "Step 2: Running decline detection and generating alerts..."
python src/alert_engine.py
check_success "Alert generation"

# Step 3: Run Experiment Evaluation  
echo "Step 3: Running experiment evaluation..."
python src/experiment.py
check_success "Experiment evaluation"

# Step 4: Run Tests
echo "Step 4: Running automated tests..."
python -m pytest tests/ -v
check_success "Automated tests"

# Step 5: Verify Generated Files
echo "Step 5: Verifying generated files..."
echo "Checking for required output files:"

if [ -f "data/synthetic_daily_data.csv" ]; then
    echo "✓ synthetic_daily_data.csv exists"
else
    echo "✗ synthetic_daily_data.csv missing"
    exit 1
fi

if [ -f "data/synthetic_incidents.csv" ]; then
    echo "✓ synthetic_incidents.csv exists"
else
    echo "✗ synthetic_incidents.csv missing"
    exit 1
fi

if [ -f "data/generated_alerts.csv" ]; then
    echo "✓ generated_alerts.csv exists"
else
    echo "✗ generated_alerts.csv missing"
    exit 1
fi

if [ -f "data/alert_summary.json" ]; then
    echo "✓ alert_summary.json exists"
else
    echo "✗ alert_summary.json missing"
    exit 1
fi

echo
echo "=========================================="
echo "EXPERIMENT COMPLETE"
echo "=========================================="
echo
echo "Generated Files:"
echo "- data/synthetic_daily_data.csv    (Patient observations)"
echo "- data/synthetic_incidents.csv     (Major adverse events)"
echo "- data/generated_alerts.csv        (System alerts)"
echo "- data/alert_summary.json          (Performance metrics)"
echo
echo "Next Steps:"
echo "1. Launch dashboard: streamlit run src/dashboard.py"
echo "2. Review results in data/alert_summary.json"
echo "3. Examine generated alerts in data/generated_alerts.csv"
echo
echo "Dashboard will be available at: http://localhost:8501"
echo
echo "⚠️  IMPORTANT: This system uses synthetic data and is for"
echo "    demonstration purposes only. Not for clinical use."
echo