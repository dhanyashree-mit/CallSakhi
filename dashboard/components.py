import pandas as pd
import plotly.express as px
import streamlit as st

def render_kpis(data):
    """Render the top row KPI cards using custom HTML/CSS for premium styling."""
    if "error" in data:
        st.error("Could not fetch KPIs")
        return
        
    total_calls = data.get("total_calls", 0)
    students = data.get("students_helped", 0)
    hours = data.get("total_hours", 0)
    accuracy = data.get("avg_accuracy", 0)

    # We use Streamlit columns to layout our custom HTML cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f'''
        <div class="kpi-card kpi-cyan">
            <div class="kpi-title">📞 Total Calls</div>
            <div class="kpi-value">{total_calls}</div>
        </div>
        ''', unsafe_allow_html=True)
        
    with col2:
        st.markdown(f'''
        <div class="kpi-card kpi-orange">
            <div class="kpi-title">👥 Students Helped</div>
            <div class="kpi-value">{students}</div>
        </div>
        ''', unsafe_allow_html=True)
        
    with col3:
        st.markdown(f'''
        <div class="kpi-card kpi-purple">
            <div class="kpi-title">⏱️ Learning Hours</div>
            <div class="kpi-value">{hours}h</div>
        </div>
        ''', unsafe_allow_html=True)
        
    with col4:
        st.markdown(f'''
        <div class="kpi-card kpi-green">
            <div class="kpi-title">🎯 Avg Accuracy</div>
            <div class="kpi-value">{accuracy}%</div>
        </div>
        ''', unsafe_allow_html=True)

def render_chapter_performance(data):
    """Render a horizontal bar chart for chapter accuracy."""
    st.markdown('<h3 style="color: #F59E0B; font-size: 1.2rem; margin-bottom: 1rem;">🎯 % Quiz Accuracy by Chapter</h3>', unsafe_allow_html=True)
    if not data or "error" in data:
        st.info("No chapter data available.")
        return
        
    df = pd.DataFrame(data)
    if df.empty:
        return
        
    # Sort by accuracy so the chart looks nice
    df = df.sort_values(by='avg_accuracy', ascending=True)
    
    # Create horizontal bar chart
    fig = px.bar(
        df,
        x='avg_accuracy',
        y='_id',
        orientation='h',
        text='avg_accuracy',
        color='avg_accuracy',
        color_continuous_scale=[(0, '#EF4444'), (0.5, '#F59E0B'), (1, '#10B981')] # Red to Yellow to Green
    )
    
    fig.update_traces(
        texttemplate='%{text:.0f}%', 
        textposition='outside',
        marker_line_width=0,
        textfont=dict(color='#F9FAFB', size=14, family="Inter"),
        cliponaxis=False
    )
    
    # Workaround for Plotly hiding text on exactly 0-width bars
    for i, row in df.iterrows():
        if row['avg_accuracy'] == 0:
            fig.add_annotation(
                x=5, # Position slightly to the right of the y-axis
                y=row['_id'],
                text="0%",
                showarrow=False,
                font=dict(color='#F9FAFB', size=14, family="Inter")
            )
            
    fig.update_layout(
        plot_bgcolor="#1A2238",
        paper_bgcolor="#1A2238",
        font_color="#CBD5E1",
        coloraxis_showscale=False,
        margin=dict(l=0, r=40, t=10, b=40),
        xaxis=dict(
            title="",
            range=[0, 100],
            tickvals=[0, 20, 40, 60, 80, 100], # Force clear ticks
            gridcolor='rgba(255, 255, 255, 0.1)',
            zerolinecolor='rgba(255, 255, 255, 0.2)',
            tickfont=dict(size=12, color="#CBD5E1")
        ),
        yaxis=dict(
            title="",
            gridcolor='rgba(255, 255, 255, 0.0)',
            tickfont=dict(size=14, color="#F9FAFB")
        ),
        height=350
    )
    
    st.plotly_chart(fig, use_container_width=True)

def render_live_monitor(data):
    """Render the live monitor table."""
    st.markdown('<h3 style="color: #22D3EE; font-size: 1.2rem; margin-bottom: 1rem;">📡 Live Mission Monitor</h3>', unsafe_allow_html=True)
    if not data or "error" in data:
        st.info("Waiting for live incoming calls...")
        return
        
    df = pd.DataFrame(data)
    if df.empty:
        st.write("No active missions.")
        return
        
    # Format the dataframe for display
    df['accuracy_percentage'] = df['accuracy_percentage'].apply(lambda x: f"{x}%")
    df['duration_seconds'] = df['duration_seconds'].apply(lambda x: f"{x}s")
    
    # Hide the raw timestamp or format it
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%H:%M:%S')
    
    # Rename columns for presentation
    df = df.rename(columns={
        "call_sid": "Session ID",
        "chapter": "Active Chapter",
        "duration_seconds": "Duration",
        "accuracy_percentage": "Accuracy",
        "timestamp": "Time"
    })
    
    # Render as custom HTML to apply our exact CSS styling
    html_table = df.to_html(classes='dataframe', index=False, border=0)
    st.markdown(html_table, unsafe_allow_html=True)
