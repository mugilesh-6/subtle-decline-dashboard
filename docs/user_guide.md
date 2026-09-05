# User Guide

## Overview

The Subtle-Decline Dashboard is a decision-support tool designed to help families and care teams monitor functional decline in older adults. This guide provides role-specific instructions for using the dashboard effectively and safely.

**⚠️ CRITICAL SAFETY INFORMATION**
> This system is a prototype using synthetic data and is **NOT** intended for clinical diagnosis or decision-making without appropriate professional oversight. Always consult qualified healthcare professionals for care decisions.

---

## Getting Started

### Accessing the Dashboard

1. **Launch the Application**:
   ```bash
   streamlit run src/dashboard.py
   ```

2. **Open in Web Browser**: The dashboard will automatically open at `http://localhost:8501`

3. **Select Your Role**: Use the sidebar dropdown to choose your role:
   - 👨‍👩‍👧‍👦 Family
   - 🏥 Care Coordinator  
   - 🩺 Clinician
   - ⚙️ Administrator

### Understanding Data Status

Before using any information, always check the **Data Status** section in the sidebar:

- 🟢 **Fresh**: Data updated within 1 day (reliable for current assessment)
- 🟡 **Stale**: Data 2-3 days old (use with caution)
- 🔴 **Missing**: Data >3 days old (insufficient for reliable assessment)

---

## Family View Guide

### Purpose
The Family View provides a simplified, easy-to-understand overview of your loved one's status without overwhelming technical details.

### Getting Started

1. **Select Patient**: Choose your family member from the "Select Patient" dropdown in the sidebar
2. **Review Overall Status**: Check the status cards at the top of the page
3. **Monitor Trends**: Look at the trend charts showing recent patterns
4. **Check Alerts**: Review any active alerts and their explanations

### Understanding the Status Cards

#### Overall Status
- ✅ **Stable**: Normal patterns, no concerns detected
- ⚠️ **Monitor**: Some changes detected, increased attention recommended
- 🚨 **Attention Needed**: Significant changes detected, contact care team

#### Data Freshness
- 🟢 **Fresh**: Information is current and reliable
- 🟡 **Recent**: Information is slightly older but still useful
- 🔴 **Stale/Missing**: Information is too old to be reliable

#### Active Alerts
- Shows number and severity of current alerts
- Click on alerts to see detailed explanations

### Reading the Metrics

#### Daily Steps (Mobility)
- **Current Value**: Today's or most recent step count
- **Baseline**: Your family member's normal/average step count
- **Change**: Percentage increase (+) or decrease (-) from normal
- **Trend Chart**: Shows daily steps over the past 30 days with the red baseline line

#### Nutrition (kcal)
- **Current Value**: Daily caloric intake
- **Baseline**: Normal daily caloric intake for this person
- **Change**: How much above or below normal
- **Trend Chart**: Shows nutrition patterns over time

#### Participation (minutes)
- **Current Value**: Daily activity/engagement time
- **Baseline**: Normal activity level for this person
- **Change**: Increase or decrease in activity participation
- **Trend Chart**: Shows activity patterns over time

### Understanding Alerts

When alerts appear, they will include:
- **Severity Level**: LOW (monitor), MEDIUM (attention), HIGH (urgent attention)
- **Simple Explanation**: What changed and for how long
- **Date Information**: When the pattern started

**Example Alert**:
> 🟡 **MEDIUM** - Mobility declined 18% and nutrition declined 12% from personal baseline for 3 consecutive days.

### What To Do

#### Green Status (Stable)
- Continue normal routines
- Keep monitoring devices charged and worn
- Regular check-ins as usual

#### Yellow Status (Monitor)  
- Increase attention to daily activities
- Ensure monitoring devices are working properly
- Consider gentle encouragement for activity/nutrition
- No immediate alarm, but stay aware

#### Red Status (Attention Needed)
- **Contact the care team or primary healthcare provider**
- Share the dashboard information with them
- Do not wait - reach out within 24 hours
- Continue to monitor closely

### Important Reminders

1. **This is Decision Support Only**: The dashboard provides information to help discussions with healthcare providers, not medical advice
2. **Trust Your Instincts**: If you're concerned about something not shown on the dashboard, still contact healthcare providers
3. **Device Maintenance**: Ensure monitoring devices are charged, worn consistently, and working properly
4. **Regular Communication**: Stay in touch with care coordinators about any changes or concerns

---

## Care Coordinator View Guide

### Purpose
The Care Coordinator View helps manage multiple patients, prioritize cases, and coordinate care team responses efficiently.

### Dashboard Overview

1. **Capacity Management**: Monitor your current workload and capacity limits
2. **Alert Queue**: Review and manage active alerts across all patients
3. **Data Quality**: Identify patients with stale or missing data requiring follow-up

### Capacity Management Section

#### Key Metrics
- **Total Patients**: All patients under your coordination
- **Active Alerts**: Current alerts requiring attention
- **High Priority**: Alerts classified as HIGH severity
- **Capacity Utilization**: Percentage of maximum workload (target <80%)

#### Status Indicators
- ✅ **Normal** (0-79%): Workload within normal limits
- ⚠️ **Warning** (80-99%): Approaching capacity, prioritize efficiently
- 🚨 **Over Capacity** (100%+): Immediate attention needed, consider help/escalation

### Alert Queue Management

#### Filtering Alerts
- Use the **"Filter by Severity"** dropdown to focus on specific priority levels
- **HIGH**: Immediate attention required (same day response)
- **MEDIUM**: Attention needed (within 2-3 days)
- **LOW**: Monitor closely (within 1 week)

#### Alert Information
Each alert shows:
- **Patient Name**: For easy identification
- **Alert Date**: When the alert was generated
- **Severity**: Priority level
- **Score**: Numerical severity (0.0-1.0, higher = more severe)
- **Domains**: Which areas are affected (Mobility, Nutrition, Participation)
- **Explanation**: Clear description of what changed

#### Priority Actions

**For HIGH Severity Alerts**:
1. Review patient immediately (same day)
2. Contact patient/family to verify status
3. Coordinate with healthcare providers if needed
4. Document actions taken
5. Schedule appropriate follow-up

**For MEDIUM Severity Alerts**:
1. Schedule review within 2-3 days
2. Assess need for family contact
3. Monitor for progression to HIGH
4. Coordinate care plan adjustments

**For LOW Severity Alerts**:
1. Add to weekly review schedule
2. Monitor trend progression
3. Consider preventive interventions
4. Update family as appropriate

### Workload Management

#### When Approaching Capacity
- Prioritize HIGH severity alerts first
- Delegate appropriate cases to other coordinators
- Consider temporary alert threshold adjustments
- Request additional resources if needed

#### When Over Capacity
- Focus only on HIGH severity alerts
- Escalate MEDIUM alerts to available coordinators
- Request immediate support
- Document capacity issues for management review

### Data Quality Monitoring

#### Stale Data Warning
When you see: "⚠️ Data Quality Alert: X patients with stale data, Y patients with missing data"

**Actions**:
1. Contact patients/families with missing data
2. Verify monitoring device functionality
3. Troubleshoot connectivity issues
4. Arrange device replacement if needed
5. Set up temporary manual reporting if necessary

### Communication Protocols

#### With Families
- Use simple, non-alarming language
- Focus on specific actionable items
- Provide clear next steps
- Schedule regular check-ins

#### With Healthcare Providers
- Share specific alert details and trends
- Provide baseline comparison data
- Include data quality context
- Recommend specific assessments or interventions

#### With Team Members
- Escalate capacity issues promptly
- Share patient status updates
- Coordinate care transitions
- Document all significant communications

---

## Clinician View Guide

### Purpose
The Clinician View provides detailed clinical information for comprehensive patient assessment and evidence-based decision making.

### Patient Assessment Process

1. **Select Patient**: Choose patient from sidebar dropdown
2. **Review Clinical Summary**: Check current assessment and baseline comparison
3. **Analyze Trends**: Examine detailed trend charts for each domain
4. **Examine Alert Evidence**: Review specific alert details and supporting data
5. **Consider Clinical Context**: Integrate dashboard information with clinical knowledge

### Clinical Assessment Section

#### Current Assessment
- **Risk Level**: NONE, LOW, MEDIUM, HIGH based on composite decline score
- **Composite Score**: Numerical assessment (0.0-1.0) of overall decline
- **Last Observation**: Date of most recent data
- **Data Age**: How current the information is

#### Baseline Comparison
Shows current values vs. personal baseline for:
- **Mobility**: Current steps vs. baseline (with % change)
- **Nutrition**: Current kcal vs. baseline (with % change)  
- **Participation**: Current minutes vs. baseline (with % change)

### Trend Analysis

#### Chart Features
- **Blue Line**: Actual daily values
- **Red Dashed Line**: Personal baseline
- **Triangle Markers**: Alert dates (color-coded by severity)
- **Interactive**: Hover for specific values and dates

#### Clinical Interpretation
- **Gradual Decline**: Steady downward trend over time
- **Acute Changes**: Sudden drops in metrics
- **Variability**: Day-to-day fluctuations around baseline
- **Recovery Patterns**: Improvement after decline periods
- **Seasonal Effects**: Weather or routine-related changes

### Alert Evidence Review

For each alert, examine:

#### Alert Details
- **Start Date**: When decline pattern began
- **Duration**: How many consecutive days
- **Affected Domains**: Which metrics show decline
- **Explanation**: Narrative description of changes

#### Domain Changes  
- **Mobility Delta**: Percentage change in daily steps
- **Nutrition Delta**: Percentage change in caloric intake
- **Participation Delta**: Percentage change in activity time
- **Composite Score**: Weighted combination of all domains

### Clinical Decision Support

#### When to Act on Alerts

**HIGH Severity (Score ≥0.50)**:
- Consider immediate clinical assessment
- Evaluate for acute medical conditions
- Review medications and recent changes
- Assess for depression, pain, or functional decline
- Consider referrals to specialists as appropriate

**MEDIUM Severity (Score 0.35-0.49)**:
- Schedule clinical evaluation within 1-2 weeks
- Monitor for progression or improvement
- Consider preventive interventions
- Review care plan and goals
- Increase monitoring frequency

**LOW Severity (Score 0.20-0.34)**:
- Add to routine assessment agenda
- Monitor trends over longer period
- Consider lifestyle or environmental factors
- Engage family in monitoring
- Document for future reference

#### Integrating with Clinical Assessment

**Questions to Consider**:
- Do the patterns match clinical observations?
- Are there medical explanations for the changes?
- What interventions might address the decline?
- How does this fit with overall care goals?
- What additional assessments are needed?

### Data Quality Considerations

#### When Data is Stale or Missing
- Use clinical judgment about information reliability
- Consider alternative assessment methods
- Document data quality issues in clinical notes
- Arrange for improved monitoring if indicated

#### Device and Data Issues
- Verify patient is wearing/using monitoring devices properly
- Check for technical problems affecting data accuracy  
- Consider multiple data sources for validation
- Document any data quality concerns

### Documentation and Communication

#### Clinical Notes
- Include relevant dashboard findings
- Note data quality and timeline
- Describe clinical correlation
- Document actions taken

#### Care Team Communication
- Share significant findings with care coordinators
- Coordinate with other providers as needed
- Update families appropriately
- Plan follow-up assessments

---

## Administrator View Guide

### Purpose
The Administrator View provides system oversight, performance monitoring, and organizational insights for dashboard management.

### System Health Monitoring

#### Key System Metrics
- **Total Patients**: Current patient census
- **Total Observations**: Volume of data being processed
- **Total Alerts**: Current alert volume
- **Total Incidents**: Known adverse events for comparison

#### Data Quality Overview
- **Fresh Data**: Patients with current, reliable information
- **Stale Data**: Patients with older but usable data  
- **Missing Data**: Patients requiring data source attention

### Performance Analysis

#### Alert Distribution
- **High Priority**: Immediate attention cases
- **Medium Priority**: Standard attention cases
- **Low Priority**: Monitoring cases

#### Capacity Management
Monitor care coordinator workload:
- **Normal**: Efficient operations
- **Warning**: Approaching limits
- **Over Capacity**: Immediate intervention needed

### Experiment Results Review

#### Performance Metrics
- **Precision**: Accuracy of alert predictions (target >60%)
- **Recall**: Coverage of actual incidents (target >70%)  
- **F1 Score**: Balanced performance measure (target >0.65)
- **Early Detection Rate**: Incidents detected in advance (target >70%)

#### Detection Analysis
- **True Positives**: Correct early detections
- **False Positives**: Alerts without subsequent incidents  
- **False Negatives**: Missed incidents without alerts
- **Average Lead Time**: Advance warning period

### Target Achievement Assessment

#### Success Criteria
- **Target**: Detect ≥70% of incidents ≥2 days early
- **Achieved**: Current system performance
- **Status**: Whether target is being met

#### When Targets Are Not Met
1. Review false negative cases
2. Assess alert threshold adjustments
3. Evaluate data quality issues
4. Consider algorithm improvements
5. Plan system enhancements

### Quality Improvement

#### Regular Reviews
- **Weekly**: System performance and capacity
- **Monthly**: Alert effectiveness and user feedback
- **Quarterly**: Target achievement and improvements
- **Annually**: Complete system evaluation

#### Performance Optimization
- Monitor alert response rates
- Track user satisfaction
- Assess clinical outcomes where possible
- Identify system improvement opportunities

### Resource Planning

#### Staffing Considerations
- Monitor care coordinator capacity utilization
- Plan for peak alert periods
- Assess training needs
- Evaluate workflow efficiency

#### Technology Needs
- Review system performance and scalability
- Plan data storage and archival
- Assess integration requirements
- Evaluate upgrade opportunities

---

## General Best Practices

### For All Users

1. **Always Check Data Status**: Verify data freshness before making decisions
2. **Use Professional Judgment**: Dashboard provides information, not decisions
3. **Maintain Device Compliance**: Ensure monitoring devices are working properly
4. **Communicate Changes**: Report system issues or patient concerns promptly
5. **Follow Safety Protocols**: Remember this is decision support, not medical diagnosis

### Troubleshooting Common Issues

#### Dashboard Not Loading
- Check internet connection
- Refresh browser page
- Restart application if needed
- Contact technical support

#### Missing Patient Data
- Verify patient selection in dropdown
- Check if patient has recent observations
- Review data source connectivity
- Contact data management team

#### Alerts Not Showing
- Confirm alert generation has run recently
- Check if patient meets minimum baseline requirements
- Verify data quality is sufficient
- Review alert severity filter settings

#### Charts Not Displaying
- Ensure patient has sufficient observation history
- Check data quality for selected period
- Try selecting different date range
- Refresh page if needed

---

## Support and Training

### Getting Help
- Review this user guide for role-specific instructions
- Check system documentation for technical details
- Contact care coordination supervisors for workflow issues
- Report system problems to technical support

### Training Resources
- Initial system training for all users
- Role-specific workflow training
- Regular refresher sessions
- Updates training for system changes

### Feedback and Improvement
- User feedback is essential for system improvement
- Report usability issues and suggestions
- Participate in user satisfaction surveys
- Contribute to continuous quality improvement

---

**Remember**: This system is designed to support, not replace, professional healthcare judgment. Always maintain appropriate clinical oversight and follow established care protocols.

*User Guide Version: 1.0*  
*Last Updated: September 2026*  
*Compatible with: Dashboard v1.0.0*