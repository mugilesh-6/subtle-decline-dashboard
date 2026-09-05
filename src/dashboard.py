"""
Streamlit dashboard for the Subtle Decline Trend Dashboard.
Multi-role interface for monitoring functional decline in older adults.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from pathlib import Path
import json
from typing import Dict, List, Any, Optional

try:
    from .utils import (
        get_project_root, load_csv_safely, get_freshness_status,
        calculate_capacity_utilization, format_date, validate_dataframe
    )
    from .alert_engine import DeclineDetector
except ImportError:
    from utils import (
        get_project_root, load_csv_safely, get_freshness_status,
        calculate_capacity_utilization, format_date, validate_dataframe
    )
    from alert_engine import DeclineDetector

# Page configuration
st.set_page_config(
    page_title="Subtle-Decline Trend Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Safety constants
COORDINATOR_MAX_CAPACITY = 8
WARNING_THRESHOLD = 0.80

# Load data with caching
@st.cache_data
def load_dashboard_data():
    """Load all required data for the dashboard."""
    project_root = get_project_root()
    data_dir = project_root / "data"
    
    daily_data = load_csv_safely(data_dir / "synthetic_daily_data.csv")
    incidents_data = load_csv_safely(data_dir / "synthetic_incidents.csv")
    alerts_data = load_csv_safely(data_dir / "generated_alerts.csv")
    
    # Load experiment results if available
    summary_file = data_dir / "alert_summary.json"
    experiment_results = None
    if summary_file.exists():
        try:
            with open(summary_file, 'r') as f:
                experiment_results = json.load(f)
        except:
            experiment_results = None
    
    return daily_data, incidents_data, alerts_data, experiment_results

def get_data_freshness_summary(daily_data: pd.DataFrame) -> Dict:
    """Calculate data freshness summary across all patients."""
    if daily_data is None or daily_data.empty:
        return {'fresh': 0, 'stale': 0, 'missing': 0, 'total': 0}
    
    freshness_counts = {'FRESH': 0, 'STALE': 0, 'MISSING': 0}
    
    # Get latest observation per patient
    latest_obs = daily_data.groupby('patient_id')['observation_date'].max().reset_index()
    
    for _, row in latest_obs.iterrows():
        try:
            last_date = pd.to_datetime(row['observation_date'])
            freshness = get_freshness_status(last_date)
            status = freshness['status']
            freshness_counts[status] += 1
        except:
            freshness_counts['MISSING'] += 1
    
    total = sum(freshness_counts.values())
    return {
        'fresh': freshness_counts['FRESH'],
        'stale': freshness_counts['STALE'], 
        'missing': freshness_counts['MISSING'],
        'total': total,
        'fresh_pct': (freshness_counts['FRESH'] / total * 100) if total > 0 else 0
    }

def create_trend_chart(patient_data: pd.DataFrame, metric: str, baseline_value: float, 
                      patient_name: str, alerts_data: pd.DataFrame = None):
    """Create a trend chart for a specific metric."""
    if patient_data.empty:
        return None
    
    # Prepare data
    chart_data = patient_data.copy()
    chart_data['observation_date'] = pd.to_datetime(chart_data['observation_date'])
    chart_data = chart_data.sort_values('observation_date')
    
    # Create figure
    fig = go.Figure()
    
    # Add actual values line
    fig.add_trace(go.Scatter(
        x=chart_data['observation_date'],
        y=chart_data[metric],
        mode='lines+markers',
        name=f'Actual {metric.replace("_", " ").title()}',
        line=dict(color='#1f77b4', width=2),
        marker=dict(size=4)
    ))
    
    # Add baseline line
    fig.add_hline(
        y=baseline_value,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Personal Baseline: {baseline_value:.0f}"
    )
    
    # Add alert markers if available
    if alerts_data is not None and not alerts_data.empty:
        patient_id = patient_data['patient_id'].iloc[0]
        patient_alerts = alerts_data[alerts_data['patient_id'] == patient_id]
        
        for _, alert in patient_alerts.iterrows():
            alert_date = pd.to_datetime(alert['alert_date'])
            # Find the metric value on alert date
            alert_day_data = chart_data[chart_data['observation_date'] == alert_date]
            if not alert_day_data.empty:
                fig.add_trace(go.Scatter(
                    x=[alert_date],
                    y=[alert_day_data[metric].iloc[0]],
                    mode='markers',
                    name=f'{alert["severity"]} Alert',
                    marker=dict(
                        size=12,
                        color='red' if alert['severity'] == 'HIGH' else 'orange' if alert['severity'] == 'MEDIUM' else 'yellow',
                        symbol='triangle-up'
                    ),
                    showlegend=True
                ))
    
    # Update layout
    fig.update_layout(
        title=f'{metric.replace("_", " ").title()} Trend - {patient_name}',
        xaxis_title='Date',
        yaxis_title=metric.replace('_', ' ').title(),
        height=400,
        showlegend=True,
        hovermode='x unified'
    )
    
    return fig

def show_family_view(daily_data, alerts_data, incidents_data, selected_patient):
    """Display family-focused view."""
    st.header("👨‍👩‍👧‍👦 Family Dashboard")
    
    # Safety disclaimer
    st.warning("⚠️ **Decision-support prototype using synthetic data.** "
               "This dashboard does not diagnose medical conditions, predict individual clinical outcomes, "
               "or replace professional clinical judgment. Alerts indicate patterns that may warrant review.")
    
    if daily_data is None or daily_data.empty:
        st.error("No patient data available")
        return
    
    # Get patient data
    patient_data = daily_data[daily_data['patient_id'] == selected_patient].copy()
    if patient_data.empty:
        st.error(f"No data found for patient {selected_patient}")
        return
    
    patient_name = patient_data['patient_name'].iloc[0]
    st.subheader(f"Patient: {patient_name}")
    
    # Initialize detector for baseline calculation
    detector = DeclineDetector(daily_data)
    current_status = detector.get_patient_current_status(selected_patient)
    
    # Overall status
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if current_status['status'] == 'CURRENT':
            risk_level = current_status['risk_level']
            if risk_level == 'NONE':
                st.success("✅ **Status: Stable**")
            elif risk_level == 'LOW':
                st.warning("⚠️ **Status: Monitor**")
            elif risk_level in ['MEDIUM', 'HIGH']:
                st.error("🚨 **Status: Attention Needed**")
        else:
            st.error(f"⚠️ **Status: {current_status['status'].replace('_', ' ')}**")
    
    with col2:
        # Data freshness
        if current_status['status'] == 'CURRENT':
            days_since = current_status['days_since_observation']
            if days_since <= 1:
                st.success(f"🟢 **Data: Fresh** (Updated {days_since} day(s) ago)")
            else:
                st.warning(f"🟡 **Data: Recent** (Updated {days_since} day(s) ago)")
        else:
            st.error("🔴 **Data: Missing/Stale**")
    
    with col3:
        # Active alerts count
        if alerts_data is not None and not alerts_data.empty:
            patient_alerts = alerts_data[alerts_data['patient_id'] == selected_patient]
            alert_count = len(patient_alerts)
            if alert_count > 0:
                high_alerts = len(patient_alerts[patient_alerts['severity'] == 'HIGH'])
                if high_alerts > 0:
                    st.error(f"🚨 **{alert_count} Active Alerts** ({high_alerts} High)")
                else:
                    st.warning(f"⚠️ **{alert_count} Active Alerts**")
            else:
                st.success("✅ **No Active Alerts**")
        else:
            st.info("No alert data available")
    
    # Current metrics vs baseline
    if current_status['status'] == 'CURRENT':
        st.subheader("📊 Current Status vs Personal Baseline")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                label="🚶 Daily Steps",
                value=f"{current_status['current_values']['mobility_steps']:,.0f}",
                delta=f"{current_status['percentage_changes']['mobility_delta']:.1f}%",
                delta_color="inverse"
            )
            st.caption(f"Baseline: {current_status['baseline_values']['mobility_baseline']:,.0f}")
        
        with col2:
            st.metric(
                label="🍽️ Nutrition (kcal)",
                value=f"{current_status['current_values']['nutrition_kcal']:,.0f}",
                delta=f"{current_status['percentage_changes']['nutrition_delta']:.1f}%",
                delta_color="inverse"
            )
            st.caption(f"Baseline: {current_status['baseline_values']['nutrition_baseline']:,.0f}")
        
        with col3:
            st.metric(
                label="🎯 Participation (min)",
                value=f"{current_status['current_values']['participation_minutes']:,.0f}",
                delta=f"{current_status['percentage_changes']['participation_delta']:.1f}%",
                delta_color="inverse"
            )
            st.caption(f"Baseline: {current_status['baseline_values']['participation_baseline']:,.0f}")
    
    # Trend charts
    if current_status['status'] == 'CURRENT' and len(patient_data) > 1:
        st.subheader("📈 Recent Trends (Last 30 Days)")
        
        # Filter to last 30 days
        patient_data_sorted = patient_data.sort_values('observation_date')
        recent_data = patient_data_sorted.tail(30)
        
        baseline_values = current_status['baseline_values']
        
        # Create trend charts
        col1, col2 = st.columns(2)
        
        with col1:
            fig_mobility = create_trend_chart(
                recent_data, 'mobility_steps', 
                baseline_values['mobility_baseline'], 
                patient_name, alerts_data
            )
            if fig_mobility:
                st.plotly_chart(fig_mobility, use_container_width=True)
        
        with col2:
            fig_nutrition = create_trend_chart(
                recent_data, 'nutrition_kcal', 
                baseline_values['nutrition_baseline'], 
                patient_name, alerts_data
            )
            if fig_nutrition:
                st.plotly_chart(fig_nutrition, use_container_width=True)
        
        fig_participation = create_trend_chart(
            recent_data, 'participation_minutes', 
            baseline_values['participation_baseline'], 
            patient_name, alerts_data
        )
        if fig_participation:
            st.plotly_chart(fig_participation, use_container_width=True)
    
    # Active alerts
    if alerts_data is not None and not alerts_data.empty:
        patient_alerts = alerts_data[alerts_data['patient_id'] == selected_patient]
        if not patient_alerts.empty:
            st.subheader("🚨 Active Alerts")
            for _, alert in patient_alerts.iterrows():
                severity_color = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}
                st.write(f"{severity_color.get(alert['severity'], '⚪')} **{alert['severity']}** - {alert['explanation']}")
                st.caption(f"Alert Date: {alert['alert_date']} | Score: {alert['composite_score']:.3f}")
    
    # Recent incidents
    if incidents_data is not None and not incidents_data.empty:
        patient_incidents = incidents_data[incidents_data['patient_id'] == selected_patient]
        if not patient_incidents.empty:
            st.subheader("🏥 Recent Incidents")
            for _, incident in patient_incidents.iterrows():
                st.write(f"• **{incident['incident_type']}** - {incident['incident_date']} (Severity: {incident['severity']})")

def show_coordinator_view(daily_data, alerts_data, incidents_data):
    """Display care coordinator view."""
    st.header("🏥 Care Coordinator Dashboard")
    
    if alerts_data is None or alerts_data.empty:
        st.warning("No alert data available")
        return
    
    # Capacity management
    st.subheader("📋 Capacity Management")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_patients = daily_data['patient_id'].nunique() if daily_data is not None else 0
        st.metric("Total Patients", total_patients)
    
    with col2:
        active_alerts = len(alerts_data)
        st.metric("Active Alerts", active_alerts)
    
    with col3:
        high_priority = len(alerts_data[alerts_data['severity'] == 'HIGH'])
        st.metric("High Priority", high_priority, delta_color="off")
    
    with col4:
        capacity_info = calculate_capacity_utilization(high_priority, COORDINATOR_MAX_CAPACITY)
        utilization_pct = capacity_info['utilization_percent']
        status = capacity_info['status']
        
        if status == 'OVER CAPACITY':
            st.error(f"⚠️ **{utilization_pct:.0f}%** - {status}")
        elif utilization_pct >= WARNING_THRESHOLD * 100:
            st.warning(f"⚠️ **{utilization_pct:.0f}%** - {status}")
        else:
            st.success(f"✅ **{utilization_pct:.0f}%** - {status}")
    
    # Alert queue
    st.subheader("🚨 Alert Queue")
    
    # Priority filter
    severity_filter = st.selectbox(
        "Filter by Severity",
        options=["All", "HIGH", "MEDIUM", "LOW"],
        key="coord_severity_filter"
    )
    
    # Filter alerts
    filtered_alerts = alerts_data.copy()
    if severity_filter != "All":
        filtered_alerts = filtered_alerts[filtered_alerts['severity'] == severity_filter]
    
    if not filtered_alerts.empty:
        # Display alert table
        display_columns = ['patient_name', 'alert_date', 'severity', 'composite_score', 'domains_affected', 'explanation']
        alert_display = filtered_alerts[display_columns].copy()
        alert_display['alert_date'] = pd.to_datetime(alert_display['alert_date']).dt.strftime('%Y-%m-%d')
        alert_display['composite_score'] = alert_display['composite_score'].round(3)
        
        # Color code by severity
        def highlight_severity(row):
            if row['severity'] == 'HIGH':
                return ['background-color: #ffebee'] * len(row)
            elif row['severity'] == 'MEDIUM':
                return ['background-color: #fff3e0'] * len(row)
            else:
                return ['background-color: #f3e5f5'] * len(row)
        
        st.dataframe(
            alert_display.style.apply(highlight_severity, axis=1),
            use_container_width=True
        )
    else:
        st.info("No alerts match the current filter")
    
    # Stale data warning
    if daily_data is not None:
        freshness_summary = get_data_freshness_summary(daily_data)
        if freshness_summary['stale'] > 0 or freshness_summary['missing'] > 0:
            st.warning(f"⚠️ **Data Quality Alert**: {freshness_summary['stale']} patients with stale data, "
                      f"{freshness_summary['missing']} patients with missing data")

def show_clinician_view(daily_data, alerts_data, incidents_data, selected_patient):
    """Display clinician view with detailed clinical information."""
    st.header("🩺 Clinician Dashboard")
    
    if daily_data is None or daily_data.empty:
        st.error("No patient data available")
        return
    
    # Get patient data
    patient_data = daily_data[daily_data['patient_id'] == selected_patient].copy()
    if patient_data.empty:
        st.error(f"No data found for patient {selected_patient}")
        return
    
    patient_name = patient_data['patient_name'].iloc[0]
    st.subheader(f"Clinical Review: {patient_name}")
    
    # Initialize detector
    detector = DeclineDetector(daily_data)
    current_status = detector.get_patient_current_status(selected_patient)
    
    # Clinical summary
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Current Assessment")
        if current_status['status'] == 'CURRENT':
            st.write(f"**Risk Level:** {current_status['risk_level']}")
            st.write(f"**Composite Score:** {current_status['composite_score']:.3f}")
            st.write(f"**Last Observation:** {current_status['last_observation_date']}")
            st.write(f"**Data Age:** {current_status['days_since_observation']} days")
        else:
            st.error(f"**Status:** {current_status['status'].replace('_', ' ')}")
            st.write(current_status.get('message', ''))
    
    with col2:
        st.subheader("📈 Baseline Comparison")
        if current_status['status'] == 'CURRENT':
            baseline = current_status['baseline_values']
            current = current_status['current_values']
            changes = current_status['percentage_changes']
            
            st.write(f"**Mobility:** {current['mobility_steps']:,.0f} steps "
                    f"(Baseline: {baseline['mobility_baseline']:,.0f}, Change: {changes['mobility_delta']:.1f}%)")
            st.write(f"**Nutrition:** {current['nutrition_kcal']:,.0f} kcal "
                    f"(Baseline: {baseline['nutrition_baseline']:,.0f}, Change: {changes['nutrition_delta']:.1f}%)")
            st.write(f"**Participation:** {current['participation_minutes']:,.0f} min "
                    f"(Baseline: {baseline['participation_baseline']:,.0f}, Change: {changes['participation_delta']:.1f}%)")
    
    # Detailed trend analysis
    if len(patient_data) > 1:
        st.subheader("📈 Comprehensive Trend Analysis")
        
        # Prepare data for detailed analysis
        patient_data_sorted = patient_data.sort_values('observation_date')
        baseline_values = current_status.get('baseline_values', {})
        
        # Create comprehensive charts
        tabs = st.tabs(["Mobility Trends", "Nutrition Trends", "Participation Trends"])
        
        with tabs[0]:
            if 'mobility_baseline' in baseline_values:
                fig = create_trend_chart(
                    patient_data_sorted, 'mobility_steps',
                    baseline_values['mobility_baseline'], 
                    patient_name, alerts_data
                )
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
        
        with tabs[1]:
            if 'nutrition_baseline' in baseline_values:
                fig = create_trend_chart(
                    patient_data_sorted, 'nutrition_kcal',
                    baseline_values['nutrition_baseline'], 
                    patient_name, alerts_data
                )
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
        
        with tabs[2]:
            if 'participation_baseline' in baseline_values:
                fig = create_trend_chart(
                    patient_data_sorted, 'participation_minutes',
                    baseline_values['participation_baseline'], 
                    patient_name, alerts_data
                )
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
    
    # Alert evidence
    if alerts_data is not None and not alerts_data.empty:
        patient_alerts = alerts_data[alerts_data['patient_id'] == selected_patient]
        if not patient_alerts.empty:
            st.subheader("🔍 Alert Evidence")
            
            for _, alert in patient_alerts.iterrows():
                with st.expander(f"Alert: {alert['alert_date']} - {alert['severity']} (Score: {alert['composite_score']:.3f})"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**Alert Details:**")
                        st.write(f"• Start Date: {alert['decline_start_date']}")
                        st.write(f"• Duration: {alert['duration_days']} days")
                        st.write(f"• Affected Domains: {alert['domains_affected']}")
                        st.write(f"• Explanation: {alert['explanation']}")
                    
                    with col2:
                        st.write("**Domain Changes:**")
                        st.write(f"• Mobility: {alert['mobility_delta']:.1f}%")
                        st.write(f"• Nutrition: {alert['nutrition_delta']:.1f}%")
                        st.write(f"• Participation: {alert['participation_delta']:.1f}%")
                        st.write(f"• Composite Score: {alert['composite_score']:.3f}")
    
    # Incident history
    if incidents_data is not None and not incidents_data.empty:
        patient_incidents = incidents_data[incidents_data['patient_id'] == selected_patient]
        if not patient_incidents.empty:
            st.subheader("🏥 Incident History")
            for _, incident in patient_incidents.iterrows():
                st.write(f"• **{incident['incident_type']}** - {incident['incident_date']} (Severity: {incident['severity']})")

def show_admin_view(daily_data, alerts_data, incidents_data, experiment_results):
    """Display administrative overview."""
    st.header("⚙️ Administrative Dashboard")
    
    # System health overview
    st.subheader("🔧 System Health")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_patients = daily_data['patient_id'].nunique() if daily_data is not None else 0
        st.metric("Total Patients", total_patients)
    
    with col2:
        total_observations = len(daily_data) if daily_data is not None else 0
        st.metric("Total Observations", f"{total_observations:,}")
    
    with col3:
        total_alerts = len(alerts_data) if alerts_data is not None else 0
        st.metric("Total Alerts", total_alerts)
    
    with col4:
        total_incidents = len(incidents_data) if incidents_data is not None else 0
        st.metric("Total Incidents", total_incidents)
    
    # Data freshness distribution
    if daily_data is not None:
        st.subheader("📊 Data Freshness Distribution")
        freshness_summary = get_data_freshness_summary(daily_data)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Fresh Data", f"{freshness_summary['fresh']}", 
                     delta=f"{freshness_summary['fresh_pct']:.1f}%")
        with col2:
            st.metric("Stale Data", freshness_summary['stale'], delta_color="off")
        with col3:
            st.metric("Missing Data", freshness_summary['missing'], delta_color="off")
    
    # Alert severity distribution
    if alerts_data is not None and not alerts_data.empty:
        st.subheader("🚨 Alert Severity Distribution")
        severity_counts = alerts_data['severity'].value_counts()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("High Priority", severity_counts.get('HIGH', 0), delta_color="off")
        with col2:
            st.metric("Medium Priority", severity_counts.get('MEDIUM', 0), delta_color="off")
        with col3:
            st.metric("Low Priority", severity_counts.get('LOW', 0), delta_color="off")
    
    # Experiment results
    if experiment_results:
        st.subheader("🧪 Experiment Summary")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Performance Metrics:**")
            st.write(f"• Precision: {experiment_results['precision']:.1%}")
            st.write(f"• Recall: {experiment_results['recall']:.1%}")
            st.write(f"• F1 Score: {experiment_results['f1_score']:.3f}")
            st.write(f"• Early Detection Rate: {experiment_results['early_detection_rate']:.1%}")
        
        with col2:
            st.write("**Detection Analysis:**")
            st.write(f"• True Positives: {experiment_results['true_positives']}")
            st.write(f"• False Positives: {experiment_results['false_positives']}")
            st.write(f"• False Negatives: {experiment_results['false_negatives']}")
            st.write(f"• Average Lead Time: {experiment_results['avg_lead_time_days']:.1f} days")
        
        # Target achievement
        target_info = experiment_results.get('target_achievement', {})
        if target_info:
            target_met = target_info.get('target_met', False)
            achieved_rate = target_info.get('achieved_detection_rate', 0)
            target_rate = target_info.get('target_detection_rate', 0)
            
            if target_met:
                st.success(f"✅ **Target Achievement:** {achieved_rate:.1%} (Target: {target_rate:.1%})")
            else:
                st.warning(f"⚠️ **Target Achievement:** {achieved_rate:.1%} (Target: {target_rate:.1%})")

def main():
    """Main dashboard application."""
    
    # Custom CSS
    st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 1rem;
        color: #1f77b4;
    }
    .safety-disclaimer {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 4px;
        padding: 10px;
        margin: 10px 0;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Load data
    daily_data, incidents_data, alerts_data, experiment_results = load_dashboard_data()
    
    # Sidebar
    st.sidebar.markdown('<h1 class="main-header">🏥 Subtle-Decline Dashboard</h1>', unsafe_allow_html=True)
    st.sidebar.markdown("*Monitoring mobility, nutrition and participation*")
    
    # Role selection
    role = st.sidebar.selectbox(
        "Select Your Role",
        ["Family", "Care Coordinator", "Clinician", "Admin"],
        key="role_selector"
    )
    
    # Patient selection (for Family and Clinician views)
    selected_patient = None
    if role in ["Family", "Clinician"] and daily_data is not None:
        patients = daily_data['patient_id'].unique()
        patient_options = []
        for patient_id in patients:
            patient_name = daily_data[daily_data['patient_id'] == patient_id]['patient_name'].iloc[0]
            patient_options.append(f"{patient_id} - {patient_name}")
        
        selected_display = st.sidebar.selectbox("Select Patient", patient_options)
        if selected_display:
            selected_patient = selected_display.split(' - ')[0]
    
    # Data status
    if daily_data is not None:
        freshness_summary = get_data_freshness_summary(daily_data)
        st.sidebar.markdown("### 📊 Data Status")
        st.sidebar.write(f"🟢 Fresh: {freshness_summary['fresh']}")
        st.sidebar.write(f"🟡 Stale: {freshness_summary['stale']}")
        st.sidebar.write(f"🔴 Missing: {freshness_summary['missing']}")
    
    # Display appropriate view
    if role == "Family":
        if selected_patient:
            show_family_view(daily_data, alerts_data, incidents_data, selected_patient)
        else:
            st.warning("Please select a patient to view family dashboard")
    elif role == "Care Coordinator":
        show_coordinator_view(daily_data, alerts_data, incidents_data)
    elif role == "Clinician":
        if selected_patient:
            show_clinician_view(daily_data, alerts_data, incidents_data, selected_patient)
        else:
            st.warning("Please select a patient for clinical review")
    elif role == "Admin":
        show_admin_view(daily_data, alerts_data, incidents_data, experiment_results)

if __name__ == "__main__":
    main()