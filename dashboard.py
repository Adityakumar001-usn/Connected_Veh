import streamlit as st
import matplotlib.pyplot as plt
import numpy as np

# Set page configuration
st.set_page_config(
    page_title="Privacy Mitigation Dashboard",
    page_icon="🚗",
    layout="wide"
)

# --- 1. Header & Introduction ---
st.title("🚗 Privacy Mitigation in Connected Vehicles: Performance Dashboard")

st.markdown("""
**The Problem:** Connected vehicles continuously broadcast Basic Safety Messages (BSMs) containing their location, speed, and heading.
Unauthorized entities can passively collect these broadcasts and link them over time using spatial-temporal heuristics.
By tracking these persistent identifiers, an attacker can reconstruct full vehicle routes, revealing travel patterns and profiling users.

This dashboard visualizes the effectiveness of two different pseudonym-change mitigation strategies designed to break these tracking heuristics.
""")

st.divider()

# --- 2. The Strategy Comparison ---
st.header("The Strategies")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Version 1 - Naive Approach (Baseline)")
    st.markdown("""
    In the baseline approach, vehicles blindly swap their pseudonyms at a fixed time interval (e.g., every 30 seconds), regardless of their surroundings.
    Because the vehicle is easily visible before and after the swap, the attacker can seamlessly link the new pseudonym to the old one based on trajectory continuation.
    """)
    st.code("""
# Naive Time-Based Swap
if current_time - last_swap_time >= 30:
    vehicle.pseudonym = generate_new_pseudonym()
    last_swap_time = current_time
    """, language="python")

with col2:
    st.subheader("Version 2 - Smart Mitigation (Density + Silence)")
    st.markdown("""
    The smart approach introduces a **Vehicle-Level Mix Zone**. A vehicle only changes its ID if it detects at least 2 other vehicles within a 50-meter radius.
    Once triggered, it undergoes a **Radio Silence Period**, stopping BSM broadcasts for 3 to 6 seconds while moving, thoroughly breaking the attacker's trajectory tracking.
    """)
    st.code("""
# O(N^2) Optimized Bounding Box Check (50m Radius)
nearby = 0
if abs(ox - x) <= 50.0 and abs(oy - y) <= 50.0:
    if distance((ox, oy), (x, y)) <= 50.0:
        nearby += 1

# Density + Silence Logic
if nearby >= 2:
    vehicle.pseudonym = generate_new_pseudonym()
    vehicle.silence_timer = random.randint(3, 6)
    """, language="python")

st.divider()

# --- 3. The Key Metrics ---
st.header("Simulation Results")

# Hardcoded final metrics from the prompt
base_success = 99.9
base_link = 100.0
smart_success = 81.8
smart_link = 0.0

col_metric1, col_metric2 = st.columns(2)

with col_metric1:
    st.markdown("### 🔴 Baseline Metrics")
    st.metric(label="Tracking Success Rate", value=f"{base_success}%")
    st.metric(label="Linkability", value=f"{base_link}%")

with col_metric2:
    st.markdown("### 🟢 Smart Mitigation Metrics")
    st.metric(label="Tracking Success Rate", value=f"{smart_success}%", delta=f"{smart_success - base_success:.1f}%", delta_color="inverse")
    st.metric(label="Linkability", value=f"{smart_link}%", delta=f"{smart_link - base_link:.1f}%", delta_color="inverse")

# --- 4. Eye-Catching Visualizations ---
st.subheader("Performance Comparison Chart")

labels = ['Tracking Success Rate (%)', 'Linkability (%)']
baseline_values = [base_success, base_link]
smart_values = [smart_success, smart_link]

x = np.arange(len(labels))
width = 0.35

fig, ax = plt.subplots(figsize=(10, 5))
rects1 = ax.bar(x - width/2, baseline_values, width, label='V1 - Baseline', color='#ff9999', edgecolor='black')
rects2 = ax.bar(x + width/2, smart_values, width, label='V2 - Smart Mitigation', color='#66b3ff', edgecolor='black')

ax.set_ylabel('Percentage (%)')
ax.set_title('Privacy Metrics Drop: Baseline vs Smart Mitigation', pad=20)
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.set_ylim(0, 115)
ax.legend()

# Attach a text label above each bar
def autolabel(rects):
    for rect in rects:
        height = rect.get_height()
        ax.annotate(f'{height}%',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom', fontweight='bold')

autolabel(rects1)
autolabel(rects2)

plt.tight_layout()
st.pyplot(fig)

st.divider()

# --- 5. Insightful Summary ---
st.info("""
**Engineering Insights**

While the 81.8% tracking success shows that physical trajectory estimation is still possible due to road constraints, the 0% Linkability proves a massive digital privacy victory. The attacker can no longer mathematically prove the old pseudonym and the new pseudonym belong to the same vehicle, effectively breaking the digital identity chain without requiring heavy RSU infrastructure.
""")

st.markdown("""
---
**To run this dashboard locally:**
```bash
pip install streamlit
streamlit run dashboard.py
```
""")
