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
    page_title="Care Coordination Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Safety constants
COORDINATOR_MAX_CAPACITY = 8
WARNING_THRESHOLD = 0.80

# UI Helper Functions
def translate_alert_to_human(alert_row: pd.Series, patient_name: str) -> Dict[str, str]:
    """Convert technical alert to human-friendly language."""
    explanation = alert_row['explanation']
    domains = alert_row['domains_affected']
    duration = alert_row['duration_days']
    
    # Parse domain information
    domain_changes = {
        'mobility': alert_row.get('mobility_delta', 0),
        'nutrition': alert_row.get('nutrition_delta', 0), 
        'participation': alert_row.get('participation_delta', 0)
    }
    
    # Create human-friendly summary
    affected_areas = []
    if 'Mobility' in domains and domain_changes['mobility'] < -5:
        affected_areas.append("less active")
    if 'Nutrition' in domains and domain_changes['nutrition'] < -5:
        affected_areas.append("eating less")  
    if 'Participation' in domains and domain_changes['participation'] < -5:
        affected_areas.append("participating less")
    
    if not affected_areas:
        # Fallback for unclear patterns
        affected_areas = ["showing some changes in routine"]
    
    # Create main message
    if len(affected_areas) == 1:
        main_message = f"{patient_name} has been {affected_areas[0]} than usual"
    elif len(affected_areas) == 2:
        main_message = f"{patient_name} has been {affected_areas[0]} and {affected_areas[1]} than usual"
    else:
        main_message = f"{patient_name} has been {', '.join(affected_areas[:-1])}, and {affected_areas[-1]} than usual"
    
    # Add duration context
    if duration == 1:
        duration_text = "since yesterday"
    elif duration <= 3:
        duration_text = f"for the past {duration} days"
    elif duration <= 7:
        duration_text = f"for the past week"
    else:
        duration_text = f"for the past {duration} days"
    
    summary = f"{main_message} {duration_text}."
    
    # Technical details for expandable section
    technical_details = {
        'mobility_change': f"{domain_changes['mobility']:.1f}%",
        'nutrition_change': f"{domain_changes['nutrition']:.1f}%", 
        'participation_change': f"{domain_changes['participation']:.1f}%",
        'consecutive_days': duration,
        'baseline_comparison': "Compared to their personal 30-day baseline",
        'original_explanation': explanation
    }
    
    return {
        'summary': summary,
        'technical_details': technical_details
    }

def get_overall_patient_status(current_status: Dict, alerts_data: pd.DataFrame, selected_patient: str) -> Dict[str, str]:
    """Determine overall patient status in human-friendly terms."""
    if current_status['status'] != 'CURRENT':
        return {
            'status': 'Needs Review',
            'status_icon': '⚠️',
            'status_color': 'warning',
            'description': 'Current information is not available.'
        }
    
    # Check for active alerts
    patient_alerts = alerts_data[alerts_data['patient_id'] == selected_patient] if alerts_data is not None else pd.DataFrame()
    
    if patient_alerts.empty:
        return {
            'status': 'Doing Well',
            'status_icon': '✅', 
            'status_color': 'success',
            'description': 'No concerning patterns detected.'
        }
    
    # Determine priority based on highest severity alert
    high_alerts = len(patient_alerts[patient_alerts['severity'] == 'HIGH'])
    medium_alerts = len(patient_alerts[patient_alerts['severity'] == 'MEDIUM'])
    
    if high_alerts > 0:
        return {
            'status': 'Needs Review',
            'status_icon': '🔴',
            'status_color': 'error', 
            'description': f'Important changes detected that may need attention.'
        }
    elif medium_alerts > 0:
        return {
            'status': 'Needs Attention',
            'status_icon': '🟡',
            'status_color': 'warning',
            'description': 'Some changes from usual patterns detected.'
        }
    else:
        return {
            'status': 'Monitor',
            'status_icon': '🟢',
            'status_color': 'info',
            'description': 'Minor changes from usual patterns detected.'
        }

def format_last_updated(current_status: Dict) -> str:
    """Format last updated time in human-friendly way."""
    if current_status['status'] != 'CURRENT':
        return "Information not available"
    
    days_since = current_status['days_since_observation']
    if days_since == 0:
        return "Updated today"
    elif days_since == 1:
        return "Updated yesterday" 
    else:
        return f"Updated {days_since} days ago"

def get_data_status_message(current_status: Dict) -> Dict[str, str]:
    """Get human-friendly data status message."""
    if current_status['status'] != 'CURRENT':
        return {
            'message': 'Some information is outdated',
            'color': 'warning',
            'details': 'Current data is not available for this person.'
        }
    
    days_since = current_status['days_since_observation']
    if days_since <= 1:
        return {
            'message': 'Information is current', 
            'color': 'success',
            'details': f'Last updated {format_last_updated(current_status).lower()}'
        }
    elif days_since <= 3:
        return {
            'message': 'Information is recent',
            'color': 'info',
            'details': f'Last updated {format_last_updated(current_status).lower()}'
        }
    else:
        return {
            'message': 'Some information is outdated',
            'color': 'warning', 
            'details': f'Last updated {format_last_updated(current_status).lower()}'
        }

def get_suggested_actions(alert_severity: str) -> List[str]:
    """Get suggested actions based on alert severity."""
    if alert_severity == 'HIGH':
        return [
            "Review the recent changes with the care team",
            "Check if there's a known reason for these changes",
            "Consider whether additional support might be helpful"
        ]
    elif alert_severity == 'MEDIUM':
        return [
            "Review the recent changes", 
            "Check if there's a known reason for the pattern",
            "Monitor to see if the pattern continues"
        ]
    else:
        return [
            "Keep an eye on the pattern",
            "Note any known reasons for the changes",
            "Continue regular monitoring"
        ]

def create_modern_trend_chart(patient_data: pd.DataFrame, metric: str, baseline_value: float, 
                            patient_name: str, alerts_data: pd.DataFrame = None):
    """Create a modern, user-friendly trend chart."""
    if patient_data.empty:
        return None
    
    # Prepare data
    chart_data = patient_data.copy()
    chart_data['observation_date'] = pd.to_datetime(chart_data['observation_date'])
    chart_data = chart_data.sort_values('observation_date')
    
    # Create figure with improved styling
    fig = go.Figure()
    
    # Add actual values line with smooth styling
    fig.add_trace(go.Scatter(
        x=chart_data['observation_date'],
        y=chart_data[metric],
        mode='lines+markers',
        name='Daily Values',
        line=dict(color='#2E86AB', width=3, shape='spline'),
        marker=dict(size=6, color='#2E86AB', line=dict(width=2, color='white')),
        hovertemplate='<b>%{y:,.0f}</b><br>%{x}<extra></extra>'
    ))
    
    # Add baseline line with improved styling
    fig.add_hline(
        y=baseline_value,
        line_dash="dash",
        line_color="#A23B72",
        line_width=2,
        annotation_text=f"Personal Baseline: {baseline_value:,.0f}",
        annotation_position="top right"
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
                color_map = {'HIGH': '#F18F01', 'MEDIUM': '#F18F01', 'LOW': '#C73E1D'}
                fig.add_trace(go.Scatter(
                    x=[alert_date],
                    y=[alert_day_data[metric].iloc[0]],
                    mode='markers',
                    name=f'Alert: {alert["severity"]}',
                    marker=dict(
                        size=12,
                        color=color_map.get(alert['severity'], '#F18F01'),
                        symbol='diamond',
                        line=dict(width=2, color='white')
                    ),
                    showlegend=False,
                    hovertemplate=f'<b>Alert: {alert["severity"]}</b><br>%{{x}}<extra></extra>'
                ))
    
    # Improved layout
    metric_labels = {
        'mobility_steps': 'Daily Activity (steps)',
        'nutrition_kcal': 'Food Intake (calories)', 
        'participation_minutes': 'Participation (minutes)'
    }
    
    fig.update_layout(
        title=dict(
            text=metric_labels.get(metric, metric.replace('_', ' ').title()),
            font=dict(size=16, color='#2C3E50'),
            x=0
        ),
        xaxis_title=None,
        yaxis_title=None,
        height=300,
        showlegend=False,
        hovermode='x unified',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=20, r=20, t=40, b=20),
        font=dict(color='#2C3E50')
    )
    
    # Clean axis styling
    fig.update_xaxes(
        gridcolor='rgba(128,128,128,0.1)',
        showline=True,
        linecolor='rgba(128,128,128,0.3)',
        tickformat='%b %d'
    )
    fig.update_yaxes(
        gridcolor='rgba(128,128,128,0.1)', 
        showline=True,
        linecolor='rgba(128,128,128,0.3)',
        tickformat=',.0f'
    )

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
    """Display redesigned family-focused view with improved UX."""
    
    # Modern header with improved styling
    st.markdown("""
    <style>
    .main-header { 
        font-size: 2rem; 
        font-weight: 600; 
        color: #2C3E50; 
        margin-bottom: 0.5rem;
        border-bottom: 3px solid #3498DB;
        padding-bottom: 0.5rem;
    }
    .status-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: white;
        border: 1px solid #E8E8E8;
        border-radius: 8px;
        padding: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }
    .alert-card {
        border-left: 4px solid #F39C12;
        background: #FDF8E7;
        padding: 1rem;
        border-radius: 0 8px 8px 0;
        margin-bottom: 1rem;
    }
    .alert-card-high {
        border-left-color: #E74C3C;
        background: #FDEAEA;
    }
    .alert-card-medium {
        border-left-color: #F39C12;
        background: #FDF8E7;
    }
    .alert-card-low {
        border-left-color: #27AE60;
        background: #E8F8F5;
    }
    .info-box {
        background: #F8F9FA;
        border: 1px solid #DEE2E6;
        border-radius: 6px;
        padding: 0.75rem;
        margin: 0.5rem 0;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<h1 class="main-header">👨‍👩‍👧‍👦 Family Care Dashboard</h1>', unsafe_allow_html=True)
    
    # Concise safety disclaimer
    st.info("ℹ️ **Research Demo** - This dashboard uses synthetic data and provides decision-support information only. Always consult with healthcare professionals for medical decisions.")
    
    if daily_data is None or daily_data.empty:
        st.error("📊 No patient information is currently available.")
        return
    
    # Get patient data
    patient_data = daily_data[daily_data['patient_id'] == selected_patient].copy()
    if patient_data.empty:
        st.error(f"📊 No information found for the selected person.")
        return
    
    patient_name = patient_data['patient_name'].iloc[0]
    
    # Initialize detector for baseline calculation
    detector = DeclineDetector(daily_data)
    current_status = detector.get_patient_current_status(selected_patient)
    
    # Get alerts for this patient
    patient_alerts = alerts_data[alerts_data['patient_id'] == selected_patient] if alerts_data is not None else pd.DataFrame()
    
    # PATIENT SUMMARY SECTION
    overall_status = get_overall_patient_status(current_status, alerts_data, selected_patient)
    data_status = get_data_status_message(current_status)
    
    # Main status card
    st.markdown(f"""
    <div class="status-card">
        <h2>{overall_status['status_icon']} {patient_name}</h2>
        <h3>Status: {overall_status['status']}</h3>
        <p>{overall_status['description']}</p>
        <p><strong>Last Updated:</strong> {format_last_updated(current_status)}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Data freshness status
    if data_status['color'] == 'warning':
        st.warning(f"⚠️ **Data Status:** {data_status['message']} - {data_status['details']}")
        with st.expander("📋 Data Details"):
            st.write("Some information may be outdated. This could affect the accuracy of the current status assessment.")
    elif data_status['color'] == 'success':
        st.success(f"✅ **Data Status:** {data_status['message']}")
    else:
        st.info(f"ℹ️ **Data Status:** {data_status['message']}")
    
    # CURRENT STATUS SECTION
    if current_status['status'] == 'CURRENT':
        st.subheader("📈 Current Activity Levels")
        
        col1, col2, col3 = st.columns(3)
        
        baseline_values = current_status['baseline_values']
        current_values = current_status['current_values'] 
        changes = current_status['percentage_changes']
        
        with col1:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric(
                label="🚶 Daily Activity",
                value=f"{current_values['mobility_steps']:,.0f} steps",
                delta=f"{changes['mobility_delta']:.1f}%",
                delta_color="inverse"
            )
            st.caption(f"Usual level: {baseline_values['mobility_baseline']:,.0f} steps")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric(
                label="🍽️ Food Intake", 
                value=f"{current_values['nutrition_kcal']:,.0f} calories",
                delta=f"{changes['nutrition_delta']:.1f}%",
                delta_color="inverse"
            )
            st.caption(f"Usual level: {baseline_values['nutrition_baseline']:,.0f} calories")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col3:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric(
                label="🎯 Participation",
                value=f"{current_values['participation_minutes']:,.0f} minutes",
                delta=f"{changes['participation_delta']:.1f}%",
                delta_color="inverse"
            )
            st.caption(f"Usual level: {baseline_values['participation_baseline']:,.0f} minutes")
            st.markdown('</div>', unsafe_allow_html=True)
    
    # ALERTS SECTION - Human-friendly
    if not patient_alerts.empty:
        st.subheader("🔔 Important Updates")
        
        for _, alert in patient_alerts.iterrows():
            # Get human-friendly alert translation
            alert_translation = translate_alert_to_human(alert, patient_name)
            severity = alert['severity']
            
            # Determine card style
            if severity == 'HIGH':
                card_class = "alert-card alert-card-high"
                priority_label = "Needs Review"
                priority_icon = "🔴"
            elif severity == 'MEDIUM':
                card_class = "alert-card alert-card-medium" 
                priority_label = "Needs Attention"
                priority_icon = "🟡"
            else:
                card_class = "alert-card alert-card-low"
                priority_label = "Monitor" 
                priority_icon = "🟢"
            
            st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)
            st.markdown(f"**{priority_icon} {priority_label}**")
            st.write(alert_translation['summary'])
            
            # What to do section
            st.markdown("**What you can do:**")
            actions = get_suggested_actions(severity)
            for action in actions:
                st.write(f"• {action}")
            
            # Expandable technical details
            with st.expander("Why are we showing this?"):
                details = alert_translation['technical_details']
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Changes from usual patterns:**")
                    st.write(f"• Activity: {details['mobility_change']}")
                    st.write(f"• Food intake: {details['nutrition_change']}")
                    st.write(f"• Participation: {details['participation_change']}")
                
                with col2:
                    st.write(f"**Duration:** {details['consecutive_days']} consecutive days")
                    st.write(f"**Comparison:** {details['baseline_comparison']}")
                    
                st.write(f"**Technical details:** {details['original_explanation']}")
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    # TREND CHARTS SECTION
    if current_status['status'] == 'CURRENT' and len(patient_data) > 1:
        st.subheader("📊 Recent Patterns (Last 30 Days)")
        st.write("These charts show daily patterns compared to personal usual levels.")
        
        # Filter to last 30 days
        patient_data_sorted = patient_data.sort_values('observation_date')
        recent_data = patient_data_sorted.tail(30)
        baseline_values = current_status['baseline_values']
        
        # Create modern trend charts
        col1, col2 = st.columns(2)
        
        with col1:
            fig_mobility = create_modern_trend_chart(
                recent_data, 'mobility_steps',
                baseline_values['mobility_baseline'], 
                patient_name, alerts_data
            )
            if fig_mobility:
                st.plotly_chart(fig_mobility, use_container_width=True)
        
        with col2:
            fig_nutrition = create_modern_trend_chart(
                recent_data, 'nutrition_kcal',
                baseline_values['nutrition_baseline'],
                patient_name, alerts_data  
            )
            if fig_nutrition:
                st.plotly_chart(fig_nutrition, use_container_width=True)
        
        fig_participation = create_modern_trend_chart(
            recent_data, 'participation_minutes',
            baseline_values['participation_baseline'],
            patient_name, alerts_data
        )
        if fig_participation:
            st.plotly_chart(fig_participation, use_container_width=True)
    
    # RECENT EVENTS SECTION
    if incidents_data is not None and not incidents_data.empty:
        patient_incidents = incidents_data[incidents_data['patient_id'] == selected_patient]
        if not patient_incidents.empty:
            st.subheader("🏥 Recent Events")
            
            for _, incident in patient_incidents.iterrows():
                incident_date = pd.to_datetime(incident['incident_date']).strftime('%B %d, %Y')
                severity_icon = '🔴' if incident['severity'] == 'High' else '🟡'
                
                st.markdown(f"""
                <div class="info-box">
                    <strong>{severity_icon} {incident['incident_type']}</strong><br>
                    <em>{incident_date}</em><br>
                    Severity: {incident['severity']}
                </div>
                """, unsafe_allow_html=True)
    
    # HELP SECTION
    with st.expander("❓ Understanding This Dashboard"):
        st.write("""
        **How to read the information:**
        - **Status** shows the overall situation based on recent patterns
        - **Activity Levels** compare current values to the person's usual patterns
        - **Important Updates** highlight any significant changes that may need attention
        - **Recent Patterns** show trends over the past 30 days
        
        **About the data:**
        - All comparisons are made to the person's individual usual patterns, not population averages
        - The system looks for sustained changes over multiple days
        - This is a research demonstration using synthetic data
        
        **Remember:** This dashboard provides information to support decision-making. Always consult healthcare professionals for medical concerns.
        """)

def show_coordinator_view(daily_data, alerts_data, incidents_data):
    """Display improved care coordinator view."""
    st.markdown('<h1 class="main-header">🏥 Care Coordinator Dashboard</h1>', unsafe_allow_html=True)
    
    if alerts_data is None or alerts_data.empty:
        st.warning("📊 No alert data is currently available.")
        return
    
    # Capacity management with improved styling  
    st.subheader("📋 Capacity Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_patients = daily_data['patient_id'].nunique() if daily_data is not None else 0
        st.metric("👥 Total Patients", total_patients)
    
    with col2:
        active_alerts = len(alerts_data)
        st.metric("🔔 Active Alerts", active_alerts)
    
    with col3:
        high_priority = len(alerts_data[alerts_data['severity'] == 'HIGH'])
        st.metric("🔴 High Priority", high_priority, delta_color="off")
    
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
    
    # Alert queue with improved presentation
    st.subheader("🚨 Alert Queue")
    
    # Priority filter
    severity_filter = st.selectbox(
        "Filter by Priority Level",
        options=["All Alerts", "High Priority", "Medium Priority", "Low Priority"],
        key="coord_severity_filter"
    )
    
    # Filter alerts
    filtered_alerts = alerts_data.copy()
    if severity_filter == "High Priority":
        filtered_alerts = filtered_alerts[filtered_alerts['severity'] == 'HIGH']
    elif severity_filter == "Medium Priority":
        filtered_alerts = filtered_alerts[filtered_alerts['severity'] == 'MEDIUM']
    elif severity_filter == "Low Priority":
        filtered_alerts = filtered_alerts[filtered_alerts['severity'] == 'LOW']
    
    if not filtered_alerts.empty:
        # Display alerts as cards instead of table
        for _, alert in filtered_alerts.iterrows():
            severity = alert['severity']
            if severity == 'HIGH':
                priority_label = "🔴 Needs Review"
                card_color = "#FDEAEA"
            elif severity == 'MEDIUM':
                priority_label = "🟡 Needs Attention"  
                card_color = "#FDF8E7"
            else:
                priority_label = "🟢 Monitor"
                card_color = "#E8F8F5"
            
            st.markdown(f"""
            <div style="background: {card_color}; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid {'#E74C3C' if severity=='HIGH' else '#F39C12' if severity=='MEDIUM' else '#27AE60'};">
                <h4>{alert['patient_name']} - {priority_label}</h4>
                <p><strong>Alert Date:</strong> {alert['alert_date']}</p>
                <p><strong>Pattern:</strong> {alert['explanation']}</p>
                <p><strong>Affected Areas:</strong> {alert['domains_affected']}</p>
                <p><strong>Risk Score:</strong> {alert['composite_score']:.2f}</p>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("🎉 No alerts match the current filter criteria.")
    
    # Data quality summary with improved presentation
    if daily_data is not None:
        freshness_summary = get_data_freshness_summary(daily_data)
        if freshness_summary['stale'] > 0 or freshness_summary['missing'] > 0:
            st.warning(f"⚠️ **Data Quality Alert**: {freshness_summary['stale']} patients with stale data, "
                      f"{freshness_summary['missing']} patients with missing data")
            
            with st.expander("📋 Data Quality Details"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("✅ Fresh Data", freshness_summary['fresh'])
                with col2:
                    st.metric("🟡 Stale Data", freshness_summary['stale'])  
                with col3:
                    st.metric("🔴 Missing Data", freshness_summary['missing'])

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
    """Main dashboard application with improved UX."""
    
    # Load data
    daily_data, incidents_data, alerts_data, experiment_results = load_dashboard_data()
    
    # Improved sidebar
    st.sidebar.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1.5rem; border-radius: 10px; margin-bottom: 1rem;">
        <h1 style="color: white; margin: 0; font-size: 1.5rem;">🏥 Care Dashboard</h1>
        <p style="color: white; margin: 0.5rem 0 0 0; opacity: 0.9;">Monitoring wellness patterns</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Role selection with improved labels
    role_options = {
        "👨‍👩‍👧‍👦 Family Member": "Family",
        "🏥 Care Coordinator": "Care Coordinator", 
        "🩺 Clinician": "Clinician",
        "⚙️ Administrator": "Admin"
    }
    
    selected_role_display = st.sidebar.selectbox(
        "👤 I am a:",
        list(role_options.keys()),
        key="role_selector"
    )
    role = role_options[selected_role_display]
    
    # Patient selection with improved interface
    selected_patient = None
    if role in ["Family", "Clinician"] and daily_data is not None:
        st.sidebar.markdown("### 👤 Select Person")
        patients = daily_data['patient_id'].unique()
        patient_options = []
        for patient_id in patients:
            patient_name = daily_data[daily_data['patient_id'] == patient_id]['patient_name'].iloc[0]
            patient_options.append(f"{patient_name}")
        
        if patient_options:
            selected_name = st.sidebar.selectbox("Choose person to view:", patient_options)
            if selected_name:
                # Find patient_id from name
                patient_id = daily_data[daily_data['patient_name'] == selected_name]['patient_id'].iloc[0]
                selected_patient = patient_id
    
    # Simplified data status for sidebar  
    if daily_data is not None and role != "Family":
        freshness_summary = get_data_freshness_summary(daily_data)
        st.sidebar.markdown("### 📊 System Status")
        
        total_patients = freshness_summary['fresh'] + freshness_summary['stale'] + freshness_summary['missing']
        if freshness_summary['fresh'] == total_patients:
            st.sidebar.success("✅ All data current")
        elif freshness_summary['stale'] > 0 or freshness_summary['missing'] > 0:
            st.sidebar.warning(f"⚠️ {freshness_summary['stale'] + freshness_summary['missing']} data issues")
        
        with st.sidebar.expander("Details"):
            st.write(f"Current: {freshness_summary['fresh']}")
            st.write(f"Outdated: {freshness_summary['stale']}")
            st.write(f"Missing: {freshness_summary['missing']}")
    
    # Navigation help
    if role == "Family":
        st.sidebar.markdown("""
        ### 💡 Quick Guide
        - **Status** shows overall wellness
        - **Updates** highlight important changes  
        - **Patterns** show recent trends
        - Expand sections for more details
        """)
    
    # Display appropriate view
    if role == "Family":
        if selected_patient:
            show_family_view(daily_data, alerts_data, incidents_data, selected_patient)
        else:
            st.markdown('<h1 class="main-header">👨‍👩‍👧‍👦 Family Care Dashboard</h1>', unsafe_allow_html=True)
            st.info("👈 Please select a person from the sidebar to view their wellness information.")
    elif role == "Care Coordinator":
        show_coordinator_view(daily_data, alerts_data, incidents_data)
    elif role == "Clinician":
        if selected_patient:
            show_clinician_view(daily_data, alerts_data, incidents_data, selected_patient)
        else:
            st.markdown('<h1 class="main-header">🩺 Clinical Dashboard</h1>', unsafe_allow_html=True)
            st.info("👈 Please select a patient from the sidebar for clinical review.")
    elif role == "Admin":
        show_admin_view(daily_data, alerts_data, incidents_data, experiment_results)

if __name__ == "__main__":
    main()